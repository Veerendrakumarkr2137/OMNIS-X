from datetime import date, timedelta

from fastapi import HTTPException
from pydantic import Field, model_validator

from .database import Account, CollegeEvent, Enrollment, Resource, User
from .engine.graph import cohort_members, overlaps
from .schemas import Interval


class EventInput(Interval):
    name: str = Field(min_length=1, max_length=100)
    department_id: str | None = None
    end_day: date | None = None
    mandatory: bool = True
    whole_scope: bool = True
    faculty: list[str] = Field(default_factory=list, max_length=1000)
    students: list[str] = Field(default_factory=list, max_length=2000)
    cohorts: list[str] = Field(default_factory=list, max_length=100)
    rooms: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.end_day and not 0 <= (self.end_day - self.day).days <= 6:
            raise ValueError("An event can span up to seven consecutive dates.")
        return self


def dates(first, last):
    start = date.fromisoformat(first)
    for offset in range((date.fromisoformat(last) - start).days + 1):
        yield (start + timedelta(days=offset)).isoformat()


def event_department(db, event):
    return db.get(Resource, event.department_id).name if event.department_id else None


def create_event(db, user, data, resources):
    unit = resources.get(data.department_id)
    if data.department_id and (not unit or unit["kind"] != "Department"):
        raise HTTPException(422, "Select a valid department.")
    dept = unit["name"] if unit else None
    if user.role == "HOD" and dept != user.dept:
        raise HTTPException(
            403, "Only administrators can schedule events outside this department."
        )
    for ids, kinds in (
        (data.faculty, ("Faculty",)),
        (data.cohorts, ("Cohort",)),
        (data.rooms, ("Classroom", "Laboratory")),
    ):
        if any(
            id not in resources
            or resources[id]["kind"] not in kinds
            or (dept and resources[id]["dept"] != dept)
            for id in ids
        ):
            raise HTTPException(
                422, "Select participants and rooms belonging to the event scope."
            )
    for id in data.students:
        student = db.get(User, id)
        if not student or student.role != "Student" or (dept and student.dept != dept):
            raise HTTPException(422, "A selected student is outside the event scope.")
    scope = {
        "whole_scope": data.whole_scope,
        "department": dept,
        **{
            key: list(dict.fromkeys(getattr(data, key)))
            for key in ("faculty", "students", "cohorts", "rooms")
        },
    }
    last_day = (data.end_day or data.day).isoformat()
    for existing in db.query(CollegeEvent).filter(
        CollegeEvent.day <= last_day, CollegeEvent.end_day >= data.day.isoformat()
    ):
        if not overlaps(data.start, data.end, existing.start, existing.end):
            continue
        if set(scope["rooms"]) & set(existing.scope["rooms"]):
            raise HTTPException(
                409, "A selected room is already reserved for another event."
            )
        if (
            data.mandatory
            and existing.mandatory
            and set(scope["faculty"]) & set(existing.scope["faculty"])
        ):
            raise HTTPException(
                409,
                "An assigned faculty member already has an event duty during this time.",
            )
    event = CollegeEvent(
        name=data.name,
        department_id=data.department_id,
        day=data.day.isoformat(),
        end_day=last_day,
        start=data.start,
        end=data.end,
        mandatory=data.mandatory,
        scope=scope,
    )
    db.add(event)
    db.flush()
    return event


def event_includes(event, user, resources):
    scope = event.scope
    if user.role not in ("Faculty", "Student") or (
        scope["department"] and user.dept != scope["department"]
    ):
        return False
    if scope["whole_scope"]:
        return True
    if user.role == "Faculty":
        return user.resource in scope["faculty"]
    return user.id in scope["students"] or (
        user.resource in resources
        and any(
            cohort_members(user.resource, resources) & cohort_members(cohort, resources)
            for cohort in scope["cohorts"]
        )
    )


def reservation_keys(db, event, schedule, resources):
    scope = event.scope
    blocked = set(scope["rooms"])
    if not event.mandatory:
        return blocked
    blocked.update(scope["faculty"])
    for cohort in scope["cohorts"]:
        blocked.update(cohort_members(cohort, resources))
    if scope["whole_scope"]:
        dept = scope["department"]
        blocked.update(
            r["id"]
            for r in resources.values()
            if r["kind"] == "Faculty" and (not dept or r["dept"] == dept)
        )
        blocked.update(s["id"] for s in schedule if not dept or s["dept"] == dept)
    if scope["students"]:
        from .accounts import student_attends

        for student in db.query(User).filter(User.id.in_(scope["students"])):
            profile = db.get(Account, student.id)
            subjects = {
                row.subject
                for row in db.query(Enrollment).filter_by(student_id=student.id)
            }
            blocked.update(
                s["id"]
                for s in schedule
                if student_attends(student, s, resources, profile, subjects)
            )
    return blocked


def blocks_session(session, event, keys, resources):
    return (
        event.day <= session["day"] <= event.end_day
        and overlaps(
            session["start"],
            session["start"] + session["duration"],
            event.start,
            event.end,
        )
        and bool(
            (
                {session["faculty"], session["room"], session["id"]}
                | cohort_members(session["cohort"], resources)
            )
            & keys
        )
    )
