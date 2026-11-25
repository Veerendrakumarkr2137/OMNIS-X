"""Administrative directory changes are validated against the published schedule."""

import secrets
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from .database import Audit, Dependency, Resource, User
from .engine.graph import inventory
from .engine.validation import eligible, workload
from .seed import HASH
from .services import lessons, lock_state


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal[
        "Classroom", "Laboratory", "Faculty", "Cohort", "Building", "Department"
    ]
    dept: str | None = None
    capacity: int = Field(default=40, ge=1, le=2000)
    equipment: list[str] = Field(default_factory=list, max_length=32)
    subjects: list[str] = Field(default_factory=list, max_length=32)
    building: str | None = None
    limit: int = Field(default=360, ge=30, le=600)
    consecutive: int = Field(default=180, ge=30, le=600)
    available: list[int] = Field(
        default_factory=lambda: [480, 1080], min_length=2, max_length=2
    )

    @model_validator(mode="after")
    def valid(self):
        if not 0 <= self.available[0] < self.available[1] <= 1440:
            raise ValueError("Provide a valid availability interval.")
        return self


class IdentityInput(BaseModel):
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(min_length=1, max_length=80)
    role: Literal["Admin", "HOD", "Faculty", "Student", "Operator"]
    dept: str | None = None
    resource: str | None = None
    password: str = Field(min_length=12, max_length=128)


def save_profile(db, actor, data, id=None):
    state = lock_state(db)
    r = db.get(Resource, id) if id else None
    if id and not r:
        raise HTTPException(404, "Resource unavailable.")
    if r and (r.kind != data.kind or r.dept != data.dept):
        raise HTTPException(422, "Keep the resource type and department.")
    if (
        data.kind not in ("Building", "Department")
        and not db.query(Resource).filter_by(kind="Department", name=data.dept).count()
    ):
        raise HTTPException(422, "Select an existing department.")
    if (
        data.kind == "Department"
        and db.query(Resource).filter_by(kind="Department", name=data.name).count()
    ):
        raise HTTPException(409, "Department already exists.")
    if r and data.kind == "Department":
        raise HTTPException(422, "Department names are stable directory identifiers.")
    details = {}
    if data.kind in ("Classroom", "Laboratory"):
        b = db.get(Resource, data.building) if data.building else None
        if not b or b.kind != "Building":
            raise HTTPException(422, "Select an existing building.")
        if r and data.building != r.details.get("building"):
            raise HTTPException(
                422, "Existing room dependencies require the original building."
            )
        details = dict(building=b.id, capacity=data.capacity, equipment=data.equipment)
    elif data.kind == "Faculty":
        if not data.subjects:
            raise HTTPException(422, "Add at least one qualified subject.")
        details = dict(
            subjects=data.subjects,
            limit=data.limit,
            consecutive=data.consecutive,
            available=data.available,
        )
    elif data.kind == "Cohort":
        details = dict(size=data.capacity)
    if r:
        r.name = data.name
        r.details = details
    else:
        r = Resource(
            id=data.kind[0].lower() + "-" + secrets.token_hex(5),
            name=data.name,
            kind=data.kind,
            dept=data.dept,
            details=details,
        )
        db.add(r)
        db.flush()
        if "building" in details:
            db.add(
                Dependency(
                    source=data.building,
                    target=r.id,
                    rule="requires building access and power",
                )
            )
    db.flush()
    res = inventory(db)
    sessions = [s for s in lessons(db) if s["status"] != "Unresolved"]
    if any(not eligible(s, s, res, []) for s in sessions) or any(
        not workload([s for s in sessions if s["day"] == day], res)
        for day in {s["day"] for s in sessions}
    ):
        raise HTTPException(
            409, "The change would invalidate a published teaching assignment."
        )
    db.add(
        Audit(
            actor=actor.name,
            action=("Updated " if id else "Added ") + r.kind.lower() + " · " + r.name,
        )
    )
    return r


def add_user(db, actor, data, demo):
    lock_state(db)
    if db.get(User, data.username):
        raise HTTPException(409, "Username already in use.")
    if (
        data.role in ("Student", "Faculty", "HOD")
        and not db.query(Resource).filter_by(kind="Department", name=data.dept).count()
    ):
        raise HTTPException(422, "Select an existing department.")
    if data.role in ("Student", "Faculty"):
        r = db.get(Resource, data.resource) if data.resource else None
        if (
            not r
            or r.dept != data.dept
            or r.kind != ("Cohort" if data.role == "Student" else "Faculty")
        ):
            raise HTTPException(422, "Select a matching faculty or cohort identity.")
    elif data.resource:
        raise HTTPException(
            422, "This role does not have a teaching or student identity."
        )
    u = User(
        id=data.username,
        name=data.name,
        role=data.role,
        dept=data.dept,
        resource=data.resource,
        password_hash=HASH.hash(data.password),
        demo=demo,
    )
    db.add(u)
    db.add(
        Audit(
            actor=actor.name,
            action="Created " + data.role + " account · " + data.username,
        )
    )
    return u
