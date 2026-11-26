from datetime import date, timedelta
import os
import secrets
from argon2 import PasswordHasher
from sqlalchemy import func, text
from .iiet import B2, metadata as iiet_metadata, seed_all_sections, seed_timetable
from .database import (
    Account,
    Audit,
    Dependency,
    Enrollment,
    Lesson,
    Notice,
    Resource,
    State,
    User,
)

HASH = PasswordHasher()
DEPTS = ["CSE", "ECE", "Mechanical"]
NAMES = [
    ["Mira Shah", "Theo Park", "Anika Rao", "Evan Cole"],
    ["Leah Chen", "Noah Iyer", "Ari Patel", "Zoe Lin"],
    ["Sara Roy", "Omar Ali", "Ada Kim", "Leo Fox"],
]
SUBJECTS = [
    ["Algorithms", "Data Structures", "Systems Lab"],
    ["Signal Processing", "Circuit Theory", "Electronics Lab"],
    ["Thermodynamics", "Solid Mechanics", "Materials Lab"],
]


def ensure_production_admin(db):
    """Bootstrap a real admin once, without altering any existing account."""
    if db.query(User).filter(User.role == "Admin", User.demo.is_(False)).first():
        return
    username = os.environ.get("OMNIS_ADMIN", "").strip()
    password = os.environ.get("OMNIS_ADMIN_PASSWORD", "")
    if not username or len(password) < 12:
        raise RuntimeError(
            "Initial setup requires OMNIS_ADMIN and OMNIS_ADMIN_PASSWORD (12+ characters)."
        )
    if "@" in username:
        raise RuntimeError("OMNIS_ADMIN must be a login ID, not an email address.")
    if db.query(User).filter(func.lower(User.id) == username.lower()).first():
        raise RuntimeError(
            "OMNIS_ADMIN is already registered. Choose a distinct production admin login."
        )
    db.add(
        User(
            id=username,
            name=username,
            role="Admin",
            password_hash=HASH.hash(password),
            demo=False,
        )
    )


def seed(db, demo=True, dataset="meridian"):
    if not demo and db.get_bind().dialect.name == "postgresql":
        # Serialize cold-start bootstrapping, including an entirely empty database.
        db.execute(text("SELECT pg_advisory_xact_lock(1876453912)"))
    state = db.query(State).filter_by(id=1).with_for_update().one_or_none()
    if state is not None:
        if not demo:
            ensure_production_admin(db)
            db.commit()
        return
    anchor = date.fromisoformat(os.getenv("OMNIS_DEMO_DATE", date.today().isoformat()))
    iiet = demo and dataset == "iiet"
    if iiet:
        anchor -= timedelta(days=anchor.weekday())
    state = State(
        id=1,
        anchor=anchor.isoformat(),
        settings={
            **(
                {
                    "demo_profile": iiet_metadata(),
                    "teaching_windows": [[480, 600], [630, 750], [840, 1020]],
                    "saturday_end": 750,
                }
                if iiet
                else {}
            ),
            "mode": "Assisted",
            "allow_substitution": demo,
            "hod_approval": False,
            "delay_weight": 1,
            "room_weight": 50,
            "faculty_weight": 100,
            "travel_minutes": 0,
            "auto_penalty_limit": 50,
        },
    )
    db.add(state)
    if not demo:
        ensure_production_admin(db)
        db.commit()
        return

    if iiet:
        seed_timetable(db, anchor)
    else:
        seed_meridian(db, anchor)
    seed_accounts(db, iiet)
    db.commit()


def seed_meridian(db, anchor):
    def resource(id, name, kind, dept=None, **details):
        db.add(Resource(id=id, name=name, kind=kind, dept=dept, details=details))

    for b, name in enumerate(["North Hall", "East Hall", "West Hall"]):
        resource(f"b{b}", name, "Building")
        resource(f"p{b}", name + " power", "Power")
        resource(f"n{b}", name + " network", "Network")
    for d, dept in enumerate(DEPTS):
        resource(f"dept{d}", dept, "Department", dept)
        for i, name in enumerate(NAMES[d]):
            # The fourth lecturer also covers the specialist laboratory.
            subjects = SUBJECTS[d] if i in (0, 3) else SUBJECTS[d][:2]
            resource(
                f"f{d}{i}",
                name,
                "Faculty",
                dept,
                subjects=subjects,
                limit=360,
                consecutive=180,
                available=[480, 1080],
            )
        for i in range(2):
            resource(
                f"c{d}{i}", f"{dept} · Year {i + 1}", "Cohort", dept, size=28 + 4 * i
            )
    for i in range(8):
        resource(
            f"r{i}",
            f"Room {101 + i}",
            "Classroom",
            DEPTS[i % 3],
            capacity=40 + 5 * (i % 3),
            building=f"b{i % 3}",
            equipment=["Projector"],
        )
    for i in range(4):
        resource(
            f"l{i}",
            ["Systems Lab A", "Electronics Lab", "Materials Lab", "Systems Lab B"][i],
            "Laboratory",
            DEPTS[i % 3],
            capacity=36,
            building=f"b{[0, 1, 2, 1][i]}",
            equipment=[
                ["Workstations", "Oscilloscopes", "Test rig", "Workstations"][i],
                "Network",
            ],
        )
        resource(
            f"e{i}",
            [
                "Compute cluster A",
                "Oscilloscope bank",
                "Materials test rig",
                "Compute cluster B",
            ][i],
            "Equipment",
            DEPTS[i % 3],
        )
    db.flush()
    for r in db.query(Resource).filter(Resource.kind.in_(["Laboratory", "Classroom"])):
        b = r.details["building"][-1]
        db.add(
            Dependency(
                source="b" + b, target=r.id, rule="requires building access and power"
            )
        )
        if r.kind == "Laboratory":
            db.add(
                Dependency(
                    source="n" + b, target=r.id, rule="requires network connectivity"
                )
            )
            db.add(
                Dependency(
                    source="e" + r.id[-1],
                    target=r.id,
                    rule="requires dedicated equipment",
                )
            )
    for b in range(3):
        db.add(Dependency(source=f"p{b}", target=f"b{b}", rule="supplies power"))
    for d, dept in enumerate(DEPTS):
        for offset in range(5):
            for i in range(2):
                lab = (offset + i) % 3 == 1
                db.add(
                    Lesson(
                        id=f"S{d}{offset}{i}",
                        day=(anchor + timedelta(days=offset)).isoformat(),
                        subject=SUBJECTS[d][2 if lab else (offset + i) % 2],
                        dept=dept,
                        faculty=f"f{d}{0 if offset == 0 or lab else i}",
                        cohort=f"c{d}{i}",
                        room=f"l{d}" if lab else f"r{d}",
                        start=540 + 120 * i,
                        duration=60,
                        kind="Examination"
                        if lab and offset == 0
                        else "Laboratory"
                        if lab
                        else "Lecture",
                        needs=[
                            ["Workstations", "Oscilloscopes", "Test rig"][d],
                            "Network",
                        ]
                        if lab
                        else ["Projector"],
                        protected=lab and offset == 0,
                    )
                )


def seed_accounts(db, iiet):
    cohort = "c01" if iiet else "c00"
    instructor = "Dr. Vikram Nair" if iiet else "Mira Shah"
    for id, role, name, dept, res in [
        ("admin", "Admin", "Alex Morgan", None, None),
        ("hod", "HOD", "Rowan Ellis", "CSE", None),
        ("faculty", "Faculty", instructor, "CSE", "f00"),
        (
            "student",
            "Student",
            "Student B1 (demo)" if iiet else "Jamie Reed",
            "CSE",
            cohort,
        ),
        ("operator", "Operator", "Casey Lane", None, None),
    ]:
        db.add(
            User(
                id=id,
                name=name,
                role=role,
                dept=dept,
                resource=res,
                password_hash=HASH.hash(id.capitalize() + "@123"),
                demo=True,
            )
        )
    # Each remaining lecturer and cohort has an inbox for targeted schedule updates.
    # Only the five published demo identities have shared demonstration passwords.
    for r in db.query(Resource).filter(Resource.kind.in_(["Faculty", "Cohort"])):
        if r.id not in {"f00", cohort, *({"c00"} if iiet else set())}:
            db.add(
                User(
                    id="campus-" + r.id,
                    name=r.name if r.kind == "Faculty" else r.name + " representative",
                    role="Faculty" if r.kind == "Faculty" else "Student",
                    dept=r.dept,
                    resource=r.id,
                    password_hash=HASH.hash(secrets.token_urlsafe(32)),
                    demo=True,
                )
            )
    db.flush()
    for u in db.query(User):
        db.add(
            Notice(
                user_id=u.id,
                title="Campus timetable published",
                message="The IIET CSE Semester V-B demonstration timetable is available."
                if iiet
                else "The five-day demonstration timetable is available.",
                route="/timetable",
            )
        )
    db.add(Audit(actor="System", action="Published the initial campus timetable"))


def extend_demo_accounts(db, demo):
    """Add demo roles to new and existing databases without replacing credentials."""
    state = db.get(State, 1)
    if not demo or state.settings.get("individual_demo"):
        return
    is_iiet = bool(state.settings.get("demo_profile"))
    anchor = date.fromisoformat(state.anchor)
    if is_iiet:
        seed_all_sections(db, anchor)
    if (
        is_iiet
        and not db.query(Resource).filter_by(kind="Department", name="ECE").first()
    ):
        db.add_all(
            [
                Resource(
                    id="demo-ece", kind="Department", name="ECE", dept="ECE", details={}
                ),
                Resource(
                    id="demo-ece-b1",
                    kind="Cohort",
                    name="ECE · Semester V · Section A · B1",
                    dept="ECE",
                    details={"size": 25},
                ),
                Resource(
                    id="demo-ece-room",
                    kind="Classroom",
                    name="ECE Demo Room",
                    dept="ECE",
                    details={
                        "capacity": 35,
                        "building": "b1",
                        "equipment": ["Projector"],
                    },
                ),
                Resource(
                    id="demo-ece-faculty",
                    kind="Faculty",
                    name="Leah Chen (fictional)",
                    dept="ECE",
                    details={
                        "subjects": ["Digital Signal Processing"],
                        "available": [480, 1020],
                        "limit": 300,
                        "consecutive": 120,
                    },
                ),
            ]
        )
        db.flush()
        db.add(
            Dependency(
                source="b1",
                target="demo-ece-room",
                rule="requires building access and power",
            )
        )
        for offset in (0, 2, 4):
            db.add(
                Lesson(
                    id=f"demo-ece-{offset}",
                    day=(anchor + timedelta(days=offset)).isoformat(),
                    start=540,
                    duration=60,
                    subject="Digital Signal Processing",
                    dept="ECE",
                    faculty="demo-ece-faculty",
                    cohort="demo-ece-b1",
                    room="demo-ece-room",
                    kind="Lecture",
                    needs=["Projector"],
                )
            )
        db.add_all(
            [
                User(
                    id="faculty-ece",
                    name="Leah Chen (fictional)",
                    role="Faculty",
                    dept="ECE",
                    resource="demo-ece-faculty",
                    password_hash=HASH.hash("DemoEceFaculty!26"),
                    demo=True,
                ),
                User(
                    id="student-ece",
                    name="Avery Shah (fictional)",
                    role="Student",
                    dept="ECE",
                    resource="demo-ece-b1",
                    password_hash=HASH.hash("DemoEceStudent!26"),
                    demo=True,
                ),
            ]
        )
    for unit in db.query(Resource).filter_by(kind="Department"):
        if not db.query(User).filter_by(role="HOD", dept=unit.name).first():
            login = "hod-" + unit.name.lower().replace(" ", "-")
            if not db.get(User, login):
                db.add(
                    User(
                        id=login,
                        role="HOD",
                        name=f"{unit.name} HOD (fictional)",
                        dept=unit.name,
                        password_hash=HASH.hash(f"Demo{unit.name}Head!26"),
                        demo=True,
                    )
                )
    units = {
        unit.name: unit.id for unit in db.query(Resource).filter_by(kind="Department")
    }
    for user in db.query(User).filter_by(demo=True):
        if db.get(Account, user.id):
            continue
        details = {}
        if user.role == "Faculty":
            details["designation"] = "Demo faculty"
        if user.role == "Student" and is_iiet:
            details.update(
                semester="V",
                section="A" if user.dept == "ECE" else "B",
                batch="B2" if user.resource == "c02" else "B1",
            )
            if user.id == "student-ece":
                details["has_registrations"] = True
                db.add(
                    Enrollment(
                        student_id=user.id,
                        subject="Digital Signal Processing",
                        category="PCC",
                    )
                )
        db.add(
            Account(
                user_id=user.id,
                department_id=units.get(user.dept),
                email=f"{user.id}@demo.omnis.example",
                details=details,
            )
        )
    state.settings = {
        **state.settings,
        "allow_substitution": state.settings.get("allow_substitution", True),
        "individual_demo": True,
    }


def seed_batch_demo(db, demo):
    """Make B2 available as a guest without reusing a student's own account."""
    if not demo or not db.get(State, 1).settings.get("demo_profile"):
        return False
    if not db.get(Resource, B2):
        return False
    guest = db.get(User, "student-b2")
    if guest:
        return guest.demo and guest.role == "Student" and guest.resource == B2
    unit = db.query(Resource).filter_by(kind="Department", name="CSE").one()
    db.add(
        User(
            id="student-b2",
            name="Student B2 (demo)",
            role="Student",
            dept=unit.name,
            resource=B2,
            password_hash=HASH.hash("DemoB2-Student!26"),
            demo=True,
        )
    )
    db.flush()
    db.add(
        Account(
            user_id="student-b2",
            department_id=unit.id,
            email="student-b2@demo.omnis.example",
            details={"semester": "V", "section": "B", "batch": "B2"},
        )
    )
    return True
