"""Persistent campus records. All official mutations share a versioned state row."""

import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.engine import make_url
from dotenv import load_dotenv


POSTGRES_SCHEMA = "omnisx"
PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(PROJECT_ENV)


class Base(DeclarativeBase):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Resource(Base):
    __tablename__ = "resources"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    kind = Column(String, index=True)
    dept = Column(String, index=True)
    details = Column(JSON, default=dict)


class Dependency(Base):
    __tablename__ = "resource_dependencies"
    source = Column(ForeignKey("resources.id"), primary_key=True)
    target = Column(ForeignKey("resources.id"), primary_key=True)
    rule = Column(String, nullable=False)


class Lesson(Base):
    __tablename__ = "academic_sessions"
    id = Column(String, primary_key=True)
    day = Column(String, index=True, nullable=False)
    subject = Column(String, nullable=False)
    dept = Column(String, index=True)
    faculty = Column(ForeignKey("resources.id"), nullable=False)
    room = Column(ForeignKey("resources.id"), nullable=False)
    cohort = Column(ForeignKey("resources.id"), nullable=False)
    start = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    kind = Column(String, nullable=False)
    needs = Column(JSON, nullable=False)
    protected = Column(Boolean, default=False)
    status = Column(String, default="Scheduled")
    previous = Column(JSON, nullable=True)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String, index=True)
    dept = Column(String)
    resource = Column(ForeignKey("resources.id"))
    password_hash = Column(String, nullable=False)
    demo = Column(Boolean, default=False)


class Login(Base):
    __tablename__ = "auth_sessions"
    digest = Column(String, primary_key=True)
    user_id = Column(ForeignKey("users.id"), index=True)
    expires = Column(Integer, nullable=False)


class Account(Base):
    """Optional extension of legacy identities. A missing row keeps legacy login valid."""

    __tablename__ = "account_profiles"
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    department_id = Column(ForeignKey("resources.id"), index=True)
    email = Column(String, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    details = Column(JSON, nullable=False, default=dict)


class Enrollment(Base):
    __tablename__ = "student_enrollments"
    student_id = Column(ForeignKey("users.id"), primary_key=True)
    subject = Column(String, primary_key=True)
    category = Column(String, nullable=False, default="Core")


class Case(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    actor = Column(ForeignKey("users.id"))
    title = Column(String, nullable=False)
    day = Column(String, index=True)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    roots = Column(JSON, nullable=False)
    impact = Column(JSON, nullable=False)
    reason = Column(String, default="")
    severity = Column(String)
    simulation = Column(Boolean, index=True, default=False)
    status = Column(String, default="Open")
    created = Column(String, default=now)


class Plan(Base):
    __tablename__ = "recovery_plans"
    id = Column(Integer, primary_key=True)
    case_id = Column(ForeignKey("incidents.id"), index=True)
    revision = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    status = Column(String, default="Pending")


class CollegeEvent(Base):
    __tablename__ = "college_events"
    id = Column(Integer, primary_key=True)
    department_id = Column(ForeignKey("resources.id"), index=True)
    name = Column(String, nullable=False)
    day = Column(String, index=True, nullable=False)
    end_day = Column(String, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    mandatory = Column(Boolean, nullable=False)
    scope = Column(JSON, nullable=False)
    case_id = Column(ForeignKey("incidents.id"), unique=True, index=True)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    day = Column(String, index=True, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default="Pending")


class Notice(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id"), index=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    route = Column(String, nullable=False)
    seen = Column(Boolean, default=False)
    created = Column(String, default=now)


class Consent(Base):
    __tablename__ = "substitution_requests"
    plan_id = Column(ForeignKey("recovery_plans.id"), primary_key=True)
    faculty = Column(ForeignKey("resources.id"), primary_key=True)
    decision = Column(String, nullable=False, default="Pending")


class Audit(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    case_id = Column(ForeignKey("incidents.id"), nullable=True)
    created = Column(String, default=now)


class State(Base):
    __tablename__ = "institution_state"
    id = Column(Integer, primary_key=True)
    revision = Column(Integer, default=1, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    settings = Column(JSON, nullable=False)
    anchor = Column(String, nullable=False)


def database_engine(url=None, filename="omnis.db"):
    path = Path(__file__).resolve().parents[1] / filename
    target = make_url(
        url or os.getenv("DATABASE_URL") or f"sqlite:///{path.as_posix()}"
    )
    if target.get_backend_name() in ("postgresql", "postgres"):
        args = {"connect_timeout": 10}
        if target.host and target.host.endswith((".supabase.co", ".supabase.com")):
            mode = target.query.get("sslmode", "verify-full")
            if mode not in ("verify-full", "verify-ca"):
                raise ValueError(
                    "Supabase connections require certificate verification."
                )
            import certifi

            args["sslmode"] = mode
            # Supabase database certificates may use its private root CA.
            # Keep verification enabled and honor an explicitly supplied CA.
            bundled_ca = Path(__file__).with_name("prod-ca-2021.crt")
            args["sslrootcert"] = target.query.get("sslrootcert") or (
                str(bundled_ca) if bundled_ca.is_file() else certifi.where()
            )
            if target.port == 6543:
                args["prepare_threshold"] = None
        return create_engine(
            target.set(drivername="postgresql+psycopg"),
            connect_args=args,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            execution_options={"schema_translate_map": {None: POSTGRES_SCHEMA}},
        )
    if target.get_backend_name() != "sqlite":
        raise ValueError("Use a SQLite or PostgreSQL DATABASE_URL.")
    engine = create_engine(
        target, connect_args={"check_same_thread": False, "timeout": 30}
    )

    @event.listens_for(engine, "connect")
    def configure(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")

    return engine


def factory(url=None, filename="omnis.db"):
    engine = database_engine(url, filename)
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_users_lower_login_id ON users (lower(id))"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_users_department_role ON users (dept, role)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_lessons_department_day ON academic_sessions (dept, day)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_lessons_faculty_day ON academic_sessions (faculty, day)"
            )
    return sessionmaker(engine, expire_on_commit=False)


def rows(db: Session, model):
    return db.query(model).all()


def fields(obj, names):
    return {k: getattr(obj, k) for k in names.split()}
