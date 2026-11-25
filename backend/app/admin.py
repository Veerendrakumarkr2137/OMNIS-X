"""Administrative directory changes are validated against the published schedule."""

import secrets
from datetime import date
from itertools import combinations
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from .database import Audit, Dependency, Lesson, Resource, fields
from .engine.graph import inventory
from .engine.validation import compatible, eligible, workload
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
    members: list[str] | None = Field(default=None, max_length=40)
    semester: str | None = Field(default=None, max_length=32)
    section: str | None = Field(default=None, max_length=32)
    batch: str | None = Field(default=None, max_length=32)
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
    email: str | None = Field(
        default=None, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    designation: str = Field(default="", max_length=100)
    semester: str = Field(default="", max_length=32)
    section: str = Field(default="", max_length=32)
    batch: str = Field(default="", max_length=32)
    enrollments: dict[str, Literal["Core", "PCC", "AEC", "Elective"]] | None = None
    subjects: list[str] = Field(default_factory=list, max_length=32)


class LessonInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    day: date
    subject: str = Field(min_length=1, max_length=160)
    dept: str
    faculty: str
    room: str
    cohort: str
    start: int = Field(ge=0, lt=1440)
    duration: int = Field(ge=15, le=600)
    kind: Literal["Lecture", "Laboratory", "Examination"]
    needs: list[str] = Field(default_factory=list, max_length=32)
    protected: bool = False


def add_lesson(db, actor, data, state):
    schedule = inventory(db)
    item = data.model_dump(mode="json")
    if db.get(Lesson, data.id):
        raise HTTPException(409, "A session already has this ID.")
    cohort = schedule.get(data.cohort)
    if (
        not cohort
        or cohort["kind"] != "Cohort"
        or cohort["dept"] != data.dept
        or data.faculty not in schedule
        or data.room not in schedule
    ):
        raise HTTPException(
            422, "Select valid and matching faculty, cohort and room records."
        )
    from .events import reservation_keys
    from .database import Case, CollegeEvent

    sessions = [s for s in lessons(db, item["day"]) if s["status"] != "Unresolved"]
    outages = [
        (set(c.impact.get("depths", {})), c.start, c.end)
        for c in db.query(Case).filter_by(day=item["day"], simulation=False)
    ]
    for e in db.query(CollegeEvent).filter(
        CollegeEvent.day <= item["day"], CollegeEvent.end_day >= item["day"]
    ):
        outages.append(
            (reservation_keys(db, e, [*sessions, item], schedule), e.start, e.end)
        )
    if (
        not eligible(item, item, schedule, outages, state.settings)
        or not all(
            compatible(item, s, schedule, state.settings["travel_minutes"])
            for s in sessions
        )
        or not workload([*sessions, item], schedule)
    ):
        raise HTTPException(
            409,
            "This session violates timetable, availability, room or workload constraints.",
        )
    lesson = Lesson(**item, status="Scheduled")
    db.add(lesson)
    state.version += 1
    db.add(Audit(actor=actor.name, action=f"Published session · {data.id}"))
    db.flush()
    return fields(
        lesson, "id day subject dept faculty room cohort start duration kind status"
    )


def save_profile(db, actor, data, id=None, *, locked=False):
    if not locked:
        lock_state(db)
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
            **(
                {k: v for k, v in r.details.items() if k in ("former_departments",)}
                if r
                else {}
            ),
            subjects=data.subjects,
            limit=data.limit,
            consecutive=data.consecutive,
            available=data.available,
        )
    elif data.kind == "Cohort":
        details = {**(r.details if r else {}), "size": data.capacity}
        for field in ("semester", "section", "batch"):
            if getattr(data, field) is not None:
                details[field] = getattr(data, field)
        if data.members is not None:
            members = [db.get(Resource, id) for id in dict.fromkeys(data.members)]
            if any(
                not member
                or member.id == id
                or member.kind != "Cohort"
                or member.dept != data.dept
                or member.details.get("members")
                for member in members
            ):
                raise HTTPException(
                    422, "Select individual batches from the same department."
                )
            if (
                members
                and id
                and any(
                    id in item.details.get("members", [])
                    for item in db.query(Resource).filter_by(
                        kind="Cohort", dept=data.dept
                    )
                )
            ):
                raise HTTPException(
                    422,
                    "A batch already linked to a section cannot contain other batches.",
                )
            if members:
                details["members"] = [member.id for member in members]
            else:
                details.pop("members", None)
    if r:
        r.name = data.name
        r.details = details
    else:
        r = Resource(
            id=data.kind[0].lower() + "-" + secrets.token_hex(5),
            name=data.name,
            kind=data.kind,
            dept=data.name if data.kind == "Department" else data.dept,
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
    if r.kind == "Cohort" and any(
        not compatible(a, b, res, 0) for a, b in combinations(sessions, 2)
    ):
        raise HTTPException(
            409, "The change would give a batch overlapping published classes."
        )
    db.add(
        Audit(
            actor=actor.name,
            action=("Updated " if id else "Added ") + r.kind.lower() + " · " + r.name,
        )
    )
    return r
