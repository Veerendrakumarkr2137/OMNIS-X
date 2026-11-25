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


def factory(url=None):
    path = Path(__file__).resolve().parents[1] / "omnis.db"
    url = url or os.getenv("DATABASE_URL") or f"sqlite:///{path.as_posix()}"
    sqlite = url.startswith("sqlite")
    engine = create_engine(
        url, connect_args={"check_same_thread": False, "timeout": 30} if sqlite else {}
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def configure(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def rows(db: Session, model):
    return db.query(model).all()


def fields(obj, names):
    return {k: getattr(obj, k) for k in names.split()}
