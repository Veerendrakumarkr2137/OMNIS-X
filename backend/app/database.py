"""Persistent campus records. All official mutations share a versioned state row."""

import os
import tempfile
from functools import lru_cache
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
from sqlalchemy.pool import NullPool
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


# Public CA from the Supabase project's SSL configuration. Embed it so the
# serverless runtime cannot omit the certificate during packaging.
SUPABASE_ROOT_CA = """-----BEGIN CERTIFICATE-----
MIIDxDCCAqygAwIBAgIUbLxMod62P2ktCiAkxnKJwtE9VPYwDQYJKoZIhvcNAQEL
BQAwazELMAkGA1UEBhMCVVMxEDAOBgNVBAgMB0RlbHdhcmUxEzARBgNVBAcMCk5l
dyBDYXN0bGUxFTATBgNVBAoMDFN1cGFiYXNlIEluYzEeMBwGA1UEAwwVU3VwYWJh
c2UgUm9vdCAyMDIxIENBMB4XDTIxMDQyODEwNTY1M1oXDTMxMDQyNjEwNTY1M1ow
azELMAkGA1UEBhMCVVMxEDAOBgNVBAgMB0RlbHdhcmUxEzARBgNVBAcMCk5ldyBD
YXN0bGUxFTATBgNVBAoMDFN1cGFiYXNlIEluYzEeMBwGA1UEAwwVU3VwYWJhc2Ug
Um9vdCAyMDIxIENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqQXW
QyHOB+qR2GJobCq/CBmQ40G0oDmCC3mzVnn8sv4XNeWtE5XcEL0uVih7Jo4Dkx1Q
DmGHBH1zDfgs2qXiLb6xpw/CKQPypZW1JssOTMIfQppNQ87K75Ya0p25Y3ePS2t2
GtvHxNjUV6kjOZjEn2yWEcBdpOVCUYBVFBNMB4YBHkNRDa/+S4uywAoaTWnCJLUi
cvTlHmMw6xSQQn1UfRQHk50DMCEJ7Cy1RxrZJrkXXRP3LqQL2ijJ6F4yMfh+Gyb4
O4XajoVj/+R4GwywKYrrS8PrSNtwxr5StlQO8zIQUSMiq26wM8mgELFlS/32Uclt
NaQ1xBRizkzpZct9DwIDAQABo2AwXjALBgNVHQ8EBAMCAQYwHQYDVR0OBBYEFKjX
uXY32CztkhImng4yJNUtaUYsMB8GA1UdIwQYMBaAFKjXuXY32CztkhImng4yJNUt
aUYsMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAB8spzNn+4VU
tVxbdMaX+39Z50sc7uATmus16jmmHjhIHz+l/9GlJ5KqAMOx26mPZgfzG7oneL2b
VW+WgYUkTT3XEPFWnTp2RJwQao8/tYPXWEJDc0WVQHrpmnWOFKU/d3MqBgBm5y+6
jB81TU/RG2rVerPDWP+1MMcNNy0491CTL5XQZ7JfDJJ9CCmXSdtTl4uUQnSuv/Qx
Cea13BX2ZgJc7Au30vihLhub52De4P/4gonKsNHYdbWjg7OWKwNv/zitGDVDB9Y2
CMTyZKG3XEu5Ghl1LEnI3QmEKsqaCLv12BnVjbkSeZsMnevJPs1Ye6TjjJwdik5P
o/bKiIz+Fq8=
-----END CERTIFICATE-----
"""


@lru_cache(maxsize=1)
def supabase_ca_bundle():
    """Use public trust roots plus the Supabase root without disabling TLS checks."""
    import certifi

    with tempfile.NamedTemporaryFile(
        mode="wb", prefix="omnisx-ca-", suffix=".pem", delete=False
    ) as bundle:
        bundle.write(Path(certifi.where()).read_bytes())
        bundle.write(b"\n")
        bundle.write(SUPABASE_ROOT_CA.encode("ascii"))
    return bundle.name


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
            args["sslmode"] = mode
            args["sslrootcert"] = target.query.get("sslrootcert") or supabase_ca_bundle()
            if target.port == 6543:
                args["prepare_threshold"] = None
        # Serverless workers must not reserve scarce Supavisor sessions
        # between requests. The transaction pooler already provides pooling.
        pool_options = (
            {"poolclass": NullPool}
            if os.getenv("VERCEL") == "1"
            or (
                target.host
                and target.host.endswith(".pooler.supabase.com")
                and target.port == 6543
            )
            else {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 2}
        )
        return create_engine(
            target.set(drivername="postgresql+psycopg"),
            connect_args=args,
            **pool_options,
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
