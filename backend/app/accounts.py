from datetime import date
from time import time
from typing import Literal

from argon2.exceptions import VerificationError
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func

from .database import Account, Audit, Enrollment, Lesson, Login, Resource, User, fields
from .engine.graph import cohort_members
from .seed import HASH
from .services import lock_state


class AccountUpdate(BaseModel):
    active: bool | None = None
    email: str | None = Field(
        default=None, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    designation: str | None = Field(default=None, max_length=100)
    semester: str | None = Field(default=None, max_length=32)
    section: str | None = Field(default=None, max_length=32)
    batch: str | None = Field(default=None, max_length=32)
    dept: str | None = None
    resource: str | None = None
    enrollments: dict[str, Literal["Core", "PCC", "AEC", "Elective"]] | None = None
    inherit_cohort_courses: bool = False


class PasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class PasswordChange(PasswordReset):
    current_password: str = Field(min_length=1, max_length=256)


def identity(db, user):
    account = db.get(Account, user.id)
    unit = department(db, user.dept) if user.dept and not account else None
    cohort = (
        db.get(Resource, user.resource)
        if user.role == "Student" and user.resource
        else None
    )
    details = {
        key: cohort.details[key]
        for key in ("semester", "section", "batch")
        if cohort and cohort.details.get(key)
    }
    details.update(
        {key: value for key, value in account.details.items() if value != ""}
        if account
        else {}
    )
    return {
        **fields(user, "id name role dept resource"),
        "department_id": account.department_id
        if account
        else unit.id
        if unit
        else None,
        "email": account.email if account else None,
        "active": account_enabled(account),
        "profile": details,
        "enrollments": {
            x.subject: x.category
            for x in db.query(Enrollment).filter_by(student_id=user.id)
        }
        if user.role == "Student"
        else {},
    }


def active(db, user):
    return account_enabled(db.get(Account, user.id))


def account_enabled(account):
    if account is None:
        return True
    expires = account.details.get("access_expires")
    return account.active and (expires is None or expires > time())


def lookup_login(db, identifier):
    key = identifier.strip().lower()
    if "@" in key:
        account = db.query(Account).filter_by(email=key).one_or_none()
        return db.get(User, account.user_id) if account else None
    return (
        db.get(User, identifier.strip())
        or db.query(User).filter(func.lower(User.id) == key).first()
    )


def verify_password(user, password):
    try:
        return HASH.verify(user.password_hash, password)
    except VerificationError:
        return False


def reset_password(db, user, password):
    user.password_hash = HASH.hash(password)
    db.query(Login).filter_by(user_id=user.id).delete()


def department(db, name):
    return db.query(Resource).filter_by(kind="Department", name=name).one_or_none()


def check_scope(db, role, dept, resource):
    scoped = role in ("Faculty", "Student", "HOD")
    unit = department(db, dept) if scoped and dept else None
    if scoped and not unit:
        raise HTTPException(422, "Select an existing department.")
    if role in ("Faculty", "Student"):
        record = db.get(Resource, resource) if resource else None
        kind = "Faculty" if role == "Faculty" else "Cohort"
        if not record or record.kind != kind or record.dept != dept:
            raise HTTPException(422, "Select a matching faculty or cohort identity.")
    elif resource:
        raise HTTPException(422, "This role does not use a faculty or cohort identity.")
    return unit


def set_profile(db, user, account, data):
    if "email" in data:
        email = data["email"].strip().lower() if data["email"] else None
        if (
            email
            and db.query(Account)
            .filter(Account.email == email, Account.user_id != user.id)
            .first()
        ):
            raise HTTPException(409, "Institutional email is already registered.")
        account.email = email
    details = dict(account.details or {})
    for key in ("designation", "semester", "section", "batch"):
        if key in data and data[key] is not None:
            details[key] = data[key].strip()
    if data.get("enrollments") is not None or data.get("inherit_cohort_courses"):
        if user.role != "Student":
            raise HTTPException(422, "Course registration belongs to student accounts.")
        courses = data.get("enrollments") or {}
        if len(courses) > 100 or any(
            not subject.strip() or len(subject) > 160 for subject in courses
        ):
            raise HTTPException(422, "Enter up to 100 valid subject names.")
        db.query(Enrollment).filter_by(student_id=user.id).delete()
        for subject, category in courses.items():
            db.add(Enrollment(student_id=user.id, subject=subject, category=category))
        details["has_registrations"] = not data.get("inherit_cohort_courses", False)
    account.details = details


def add_user(db, actor, data, demo, *, locked=False):
    if not locked:
        lock_state(db)
    if lookup_login(db, data.username):
        raise HTTPException(409, "Login ID is already registered.")
    if data.role == "Faculty" and not data.resource and data.subjects:
        from .admin import ProfileInput, save_profile

        faculty = save_profile(
            db,
            actor,
            ProfileInput(
                name=data.name, kind="Faculty", dept=data.dept, subjects=data.subjects
            ),
            locked=True,
        )
        data = data.model_copy(update={"resource": faculty.id})
    unit = check_scope(db, data.role, data.dept, data.resource)
    if (
        data.role == "Faculty"
        and db.query(User).filter_by(role="Faculty", resource=data.resource).first()
    ):
        raise HTTPException(
            409,
            "This faculty member already has an account. Use password reset to restore access.",
        )
    user = User(
        id=data.username,
        name=data.name,
        role=data.role,
        dept=unit.name if unit else None,
        resource=data.resource,
        password_hash=HASH.hash(data.password),
        demo=demo,
    )
    db.add(user)
    db.flush()
    account = Account(
        user_id=user.id, department_id=unit.id if unit else None, details={}
    )
    db.add(account)
    set_profile(db, user, account, data.model_dump())
    db.flush()
    db.add(Audit(actor=actor.name, action=f"Created {user.role} account · {user.id}"))
    return user


def update_user(db, actor, user, patch):
    lock_state(db)
    data = patch.model_dump(exclude_unset=True)
    if user.id == actor.id and data.get("active") is False:
        raise HTTPException(
            409, "An administrator cannot deactivate their own account."
        )
    dept = data.get("dept", user.dept)
    resource = data.get("resource", user.resource)
    if user.role == "Faculty" and resource != user.resource:
        raise HTTPException(
            422, "A faculty login is permanently linked to its teaching identity."
        )
    if user.role == "Faculty" and dept != user.dept:
        target = department(db, dept)
        faculty = db.get(Resource, user.resource)
        if not target or not faculty:
            raise HTTPException(422, "Select a destination department.")
        if (
            db.query(Lesson)
            .filter(
                Lesson.faculty == faculty.id, Lesson.day >= date.today().isoformat()
            )
            .first()
        ):
            raise HTTPException(
                409,
                "Reassign future published lessons before transferring this faculty member.",
            )
        faculty.details = {
            **faculty.details,
            "former_departments": {
                **faculty.details.get("former_departments", {}),
                faculty.dept: date.today().isoformat(),
            },
        }
        faculty.dept = target.name
        db.flush()
    unit = check_scope(db, user.role, dept, resource)
    account = db.get(Account, user.id)
    if not account:
        account = Account(user_id=user.id, active=True, details={})
        db.add(account)
    account.department_id = unit.id if unit else None
    user.dept, user.resource = (unit.name if unit else None), resource
    set_profile(db, user, account, data)
    if data.get("active") is not None:
        account.active = data["active"]
    db.query(Login).filter_by(user_id=user.id).delete()
    db.add(Audit(actor=actor.name, action=f"Updated {user.role} account · {user.id}"))
    db.flush()
    return user


def student_attends(user, session, resources, account=None, subjects=()):
    if user.dept != session["dept"] or user.resource not in resources:
        return False
    # A section-level assignment includes common classes. A specific lab
    # appears only when the student's assigned group fits that lab's group.
    batch = cohort_members(user.resource, resources)
    if not batch or not batch <= cohort_members(session["cohort"], resources):
        return False
    return (
        not account
        or not account.details.get("has_registrations")
        or session["subject"] in subjects
    )
