from datetime import date, timedelta
import os
import secrets
from argon2 import PasswordHasher
from .database import Audit, Dependency, Lesson, Notice, Resource, State, User

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


def seed(db, demo=True):
    if db.get(State, 1):
        return
    anchor = date.fromisoformat(os.getenv("OMNIS_DEMO_DATE", date.today().isoformat()))
    state = State(
        id=1,
        anchor=anchor.isoformat(),
        settings={
            "mode": "Assisted",
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
        username, password = (
            os.environ.get("OMNIS_ADMIN"),
            os.environ.get("OMNIS_ADMIN_PASSWORD", ""),
        )
        if not username or len(password) < 12:
            raise RuntimeError(
                "Initial setup requires OMNIS_ADMIN and OMNIS_ADMIN_PASSWORD (12+ characters)."
            )
        db.add(
            User(
                id=username,
                name=username,
                role="Admin",
                password_hash=HASH.hash(password),
            )
        )
        db.commit()
        return

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
    for id, role, name, dept, res in [
        ("admin", "Admin", "Alex Morgan", None, None),
        ("hod", "HOD", "Rowan Ellis", "CSE", None),
        ("faculty", "Faculty", "Mira Shah", "CSE", "f00"),
        ("student", "Student", "Jamie Reed", "CSE", "c00"),
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
        if r.id not in ("f00", "c00"):
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
                message="The five-day demonstration timetable is available.",
                route="/timetable",
            )
        )
    db.add(Audit(actor="System", action="Published the initial campus timetable"))
    db.commit()
