"""Transcription of the supplied Indian CSE Semester V-B timetable."""

from datetime import timedelta

from .database import Dependency, Lesson, Resource

FACULTY = {
    "np": "Dr. Vikram Nair",
    "ugr": "Dr. Kavita Rao",
    "acs": "Dr. Rohan Verma",
    "rbr": "Prof. Siddharth Kulkarni",
    "mnh": "Prof. Meera Deshmukh",
    "rp": "Prof. Priya Menon",
    "aa": "Prof. Sneha Joshi",
    "ah": "Prof. Aditya Iyer",
    "mmr": "Prof. Farhan Khan",
    "ssp": "Prof. Karthik Bhat",
    "project": "Project supervisor (demo)",
    "club": "Club coordinator (demo)",
    "mentor": "Mentor (demo)",
    "library": "Library coordinator (demo)",
    "backup": "Dr. Vivek Sharma",
}

EXTRA_FACULTY = {
    "skc": "Dr. Arvind Menon",
    "jan": "Prof. Nikhil Shetty",
    "sas": "Prof. Deepak Kulkarni",
    "nr": "Dr. Sameer Rao",
    "vhu": "Prof. Nandini Hegde",
    "ncr": "Dr. Shalini Deshpande",
    "vkp": "Prof. Varsha Kulkarni",
    "ar": "Dr. Ananya Sharma",
    "cmv": "Prof. Chetan Murthy",
    "ds": "Prof. Divya Sastry",
    "nhm": "Dr. Naveen Hegde",
    "an": "Prof. Aarti Nair",
    "rgs": "Prof. Rashmi Deshmukh",
    "vvk": "Dr. Vinay Kulkarni",
    "kvs": "Prof. Kiran Verma",
    "s_fac": "Prof. Sanjay Rao",
    "ckc": "Prof. Chitra Iyer",
    "rhs": "Prof. Ritu Hegde",
    "nc": "Prof. Niharika Sen",
    "archana": "Prof. Archana Joshi",
    "jgc": "Dr. Jayant Gokhale",
    "km": "Prof. Kavya Murthy",
    "pb": "Dr. Pallavi Bhat",
    "vkl": "Prof. Vidya Kulkarni",
    "wk": "Prof. Wasim Qureshi",
    "supreeth": "Prof. Suresh Hegde",
}

ALL_FACULTY = {**FACULTY, **EXTRA_FACULTY}

# Title, source code, and faculty in charge as listed in the supplied timetable.
COURSES = {
    "ATC": ("Automata Theory and Computability", "BCSPCC501", ["np"]),
    "CN": ("Computer Networks", "BCSPCC502", ["ugr", "acs", "rbr"]),
    "SE&PM": ("Software Engineering and Project Management", "BCSMAE503", ["mnh"]),
    "PEC": ("Professional Elective Course", "BXXPEC504X", ["rp"]),
    "RM": ("Research Methodology and IPR", "BHSRMI505", ["aa"]),
    "Web Lab": ("Web Technology Lab", "BCSPCL507", ["ah", "mnh", "mmr"]),
    "AEC Lab": ("Ability / Skill Enhancement Course", "BXXAEC508X", ["rbr", "ssp"]),
    "CCD": ("Career Competency Development", "BMNCCD509", ["ssp"]),
    "Pre-placement": (
        "Pre-placement Activity (LeetCode/Hackerrank)",
        "",
        ["np", "aa", "ssp"],
    ),
    "CN Lab": ("Computer Networks Lab", "BCSPCC502", ["ugr", "acs", "rbr"]),
    "Mini Project": ("Mini Project", "", []),
    "Club activity": ("Club activity", "", []),
    "Mentoring": ("Mentoring", "", []),
    "Library": ("Library", "", []),
}

CLASSROOM = "r0"
SECTION = "c00"
B1 = "c01"
B2 = "c02"

# Source cells are represented once per activity, with two simultaneous rows for each lab rotation.
# Each tuple contains course, start, duration, the lead assignment, and any room or cohort override.
WEEK = [
    [
        ("Web Lab", 480, 120, "ah", "l0", B1),
        ("CN Lab", 480, 120, "rbr", "l1", B2),
        ("ATC", 630, 60, "np"),
        ("RM", 690, 60, "aa"),
        ("PEC", 840, 60, "rp"),
        ("SE&PM", 900, 60, "mnh"),
        ("CN", 960, 60, "ugr"),
    ],
    [
        ("Pre-placement", 480, 120, "np"),
        ("RM", 630, 60, "aa"),
        ("SE&PM", 690, 60, "mnh"),
        ("CN", 840, 60, "ugr"),
        ("PEC", 900, 60, "rp"),
        ("Library", 960, 60, "library", "library"),
    ],
    [
        ("Mini Project", 480, 120, "project"),
        ("ATC", 630, 60, "np"),
        ("SE&PM", 690, 60, "mnh"),
        ("Club activity", 840, 180, "club", "club"),
    ],
    [
        ("SE&PM", 480, 60, "mnh"),
        ("ATC", 540, 60, "np"),
        ("CCD", 630, 120, "ssp"),
        ("PEC", 840, 60, "rp"),
        ("Mini Project", 900, 120, "project"),
    ],
    [
        ("Web Lab", 480, 120, "mmr", "l0", B2),
        ("CN Lab", 480, 120, "acs", "l1", B1),
        ("CN", 630, 60, "ugr"),
        ("Mentoring", 690, 60, "mentor"),
        ("AEC Lab", 840, 120, "rbr", "l2"),
        ("Library", 960, 60, "library", "library"),
    ],
    [
        ("ATC", 480, 60, "np"),
        ("CN", 540, 60, "ugr"),
        ("Mentoring", 630, 60, "mentor"),
        ("Library", 690, 60, "library", "library"),
    ],
]


def metadata():
    return {
        "campus_name": "Indian Institute of Engineering & Technology",
        "demo_label": "CSE · Semester V · Sections A–F",
        "source_label": "Odd semester 2026–2027 · Rooms A126–A252 · Timetable dated 15 September 2026",
        "breaks": "Break 10:00–10:30 · Lunch 12:30–14:00 · Saturday ends at 12:30",
        "courses": {
            title: {
                "abbr": abbr,
                "code": code,
                "faculty": [FACULTY[f] for f in teachers],
            }
            for abbr, (title, code, teachers) in COURSES.items()
        },
    }


def seed_timetable(db, monday):
    def resource(id, name, kind, department="CSE", **details):
        db.add(Resource(id=id, name=name, kind=kind, dept=department, details=details))

    resource("dept0", "CSE", "Department")
    resource(SECTION, "Semester V-B", "Cohort", size=60, members=[B1, B2])
    resource(B1, "Semester V-B · B1", "Cohort", size=30)
    resource(B2, "Semester V-B · B2", "Cohort", size=30)
    for id, name in (("b0", "CSE block (demo)"), ("b1", "Annex (demo)")):
        resource(id, name, "Building", None)
    for id, name, kind in (
        ("p0", "CSE block power", "Power"),
        ("n1", "Teaching lab network", "Network"),
    ):
        resource(id, name + " (demo)", kind, None)
    spaces = [
        ("r0", "Room A126", "Classroom", "b0", 72, ["Projector"]),
        ("r1", "Backup classroom (demo)", "Classroom", "b1", 72, ["Projector"]),
        ("library", "Library (demo space)", "Classroom", "b1", 72, ["Library"]),
        ("club", "Activity space (demo)", "Classroom", "b1", 72, ["Activity space"]),
        (
            "l0",
            "Web Technology Lab (demo)",
            "Laboratory",
            "b0",
            36,
            ["Web tools", "Network"],
        ),
        (
            "l1",
            "Computer Networks Lab (demo)",
            "Laboratory",
            "b0",
            36,
            ["Networking kits", "Network"],
        ),
        (
            "l2",
            "AEC Lab (demo)",
            "Laboratory",
            "b0",
            72,
            ["AEC workstations", "Network"],
        ),
        (
            "l3",
            "Backup Web Lab (demo)",
            "Laboratory",
            "b1",
            36,
            ["Web tools", "Network"],
        ),
        (
            "l4",
            "Backup Networks Lab (demo)",
            "Laboratory",
            "b1",
            36,
            ["Networking kits", "Network"],
        ),
    ]
    equipment = {}
    for id, name, kind, building, capacity, tools in spaces:
        equipment[id] = tools
        resource(id, name, kind, capacity=capacity, building=building, equipment=tools)
    ids = {"np": "f00"} | {f: f"iiet-{f}" for f in FACULTY if f != "np"}
    qualifications = {key: set() for key in FACULTY}
    for title, _, teachers in COURSES.values():
        for teacher in teachers:
            qualifications[teacher].add(title)
    qualifications["backup"].add(COURSES["ATC"][0])
    for daily_cells in WEEK:
        for course, _, _, faculty, *_ in daily_cells:
            qualifications[faculty].add(COURSES[course][0])
    for key, name in FACULTY.items():
        resource(
            ids[key],
            name,
            "Faculty",
            subjects=sorted(qualifications[key]),
            limit=360,
            consecutive=180,
            available=[480, 1020],
        )
    db.flush()
    db.add(Dependency(source="p0", target="b0", rule="supplies power"))
    for id, _, kind, building, _, _ in spaces:
        db.add(
            Dependency(
                source=building, target=id, rule="requires building access and power"
            )
        )
        if kind == "Laboratory" and building == "b0":
            db.add(
                Dependency(source="n1", target=id, rule="requires network connectivity")
            )
    for offset, cells in enumerate(WEEK):
        day = (monday + timedelta(days=offset)).isoformat()
        for index, (course, start, duration, faculty, *location) in enumerate(cells):
            room = location[0] if location else CLASSROOM
            cohort = location[1] if len(location) > 1 else SECTION
            db.add(
                Lesson(
                    id=f"IIET-{offset + 1}-{index + 1}",
                    day=day,
                    subject=COURSES[course][0],
                    dept="CSE",
                    faculty=ids[faculty],
                    cohort=cohort,
                    room=room,
                    start=start,
                    duration=duration,
                    kind="Laboratory"
                    if room.startswith("l") and room != "library"
                    else "Lecture",
                    needs=equipment[room],
                    protected=course
                    in ("Library", "Club activity", "Mentoring", "Mini Project"),
                )
            )


EXTRA_SECTIONS = {
    "A": {
        "room": ("r-sec-a", "Room A126 (Sec A)"),
        "extra_rooms": [("r-a348", "Room A348", "Classroom", "b1", 72, ["Projector"])],
        "week": [
            [
                ("ATC", 480, 60, "ssp"),
                ("CN", 540, 60, "skc"),
                ("Mini Project", 630, 120, "project"),
                ("PEC", 840, 60, "rbr"),
                ("CCD", 900, 120, "ncr", "r-a348"),
            ],
            [
                ("RM", 480, 60, "sas"),
                ("ATC", 540, 60, "ssp"),
                ("Web Lab", 630, 120, "nr", "l0-a", "sec-a-1"),
                ("CN Lab", 630, 120, "mmr", "l1-a", "sec-a-2"),
                ("Library", 840, 60, "library", "library"),
                ("PEC", 900, 60, "rbr"),
                ("SE&PM", 960, 60, "jan"),
            ],
            [
                ("SE&PM", 480, 60, "jan"),
                ("CN", 540, 60, "skc"),
                ("ATC", 630, 60, "ssp"),
                ("Mentoring", 690, 60, "mentor"),
                ("Club activity", 840, 180, "club", "club"),
            ],
            [
                ("Pre-placement", 480, 120, "skc"),
                ("SE&PM", 630, 60, "jan"),
                ("RM", 690, 60, "sas"),
                ("PEC", 840, 60, "rbr"),
                ("Mini Project", 900, 120, "project"),
            ],
            [
                ("CN", 480, 60, "skc"),
                ("ATC", 540, 60, "ssp"),
                ("SE&PM", 630, 60, "jan"),
                ("Mentoring", 690, 60, "mentor"),
                ("AEC Lab", 840, 120, "ugr", "l2-a"),
                ("Library", 960, 60, "library", "library"),
            ],
            [
                ("Web Lab", 480, 120, "jan", "l0-a", "sec-a-2"),
                ("CN Lab", 480, 120, "skc", "l1-a", "sec-a-1"),
                ("CN", 630, 60, "skc"),
                ("Library", 690, 60, "library", "library"),
            ],
        ],
    },
    "C": {
        "room": ("r-sec-c", "Room A124"),
        "week": [
            [
                ("SE&PM", 480, 60, "vhu"),
                ("CN", 540, 60, "aa"),
                ("Mini Project", 630, 120, "project"),
                ("PEC", 840, 60, "cmv"),
                ("Web Lab", 900, 120, "ds", "l0-c", "sec-c-1"),
                ("CN Lab", 900, 120, "cmv", "l1-c", "sec-c-2"),
            ],
            [
                ("Pre-placement", 480, 120, "rp"),
                ("SE&PM", 630, 60, "vhu"),
                ("ATC", 690, 60, "vkp"),
                ("CN", 840, 60, "aa"),
                ("PEC", 900, 60, "cmv"),
                ("Library", 960, 60, "library", "library"),
            ],
            [
                ("ATC", 480, 60, "vkp"),
                ("RM", 540, 60, "mmr"),
                ("CCD", 630, 120, "an"),
                ("Club activity", 840, 180, "club", "club"),
            ],
            [
                ("Mini Project", 480, 120, "project"),
                ("RM", 630, 60, "mmr"),
                ("CN", 690, 60, "aa"),
                ("PEC", 840, 60, "cmv"),
                ("SE&PM", 900, 60, "vhu"),
                ("Library", 960, 60, "library", "library"),
            ],
            [
                ("Web Lab", 480, 120, "ds", "l0-c", "sec-c-2"),
                ("CN Lab", 480, 120, "ar", "l1-c", "sec-c-1"),
                ("ATC", 630, 60, "vkp"),
                ("Mentoring", 690, 60, "mentor"),
                ("AEC Lab", 840, 120, "rp", "l2-c"),
                ("Mentoring", 960, 60, "mentor"),
            ],
            [
                ("CN", 480, 60, "aa"),
                ("ATC", 540, 60, "vkp"),
                ("SE&PM", 630, 60, "vhu"),
                ("Library", 690, 60, "library", "library"),
            ],
        ],
    },
    "D": {
        "room": ("r-sec-d", "Room A252"),
        "week": [
            [
                ("CN", 480, 60, "vvk"),
                ("RM", 540, 60, "jan"),
                ("Mini Project", 630, 120, "project"),
                ("PEC", 840, 60, "ah"),
                ("Web Lab", 900, 120, "ckc", "l0-d", "sec-d-1"),
                ("CN Lab", 900, 120, "kvs", "l1-d", "sec-d-2"),
            ],
            [
                ("SE&PM", 480, 60, "kvs"),
                ("CN", 540, 60, "vvk"),
                ("ATC", 630, 60, "rgs"),
                ("Library", 690, 60, "library", "library"),
                ("RM", 840, 60, "jan"),
                ("PEC", 900, 60, "ah"),
                ("Library", 960, 60, "library", "library"),
            ],
            [
                ("CN", 480, 60, "vvk"),
                ("SE&PM", 540, 60, "kvs"),
                ("ATC", 630, 60, "rgs"),
                ("Mentoring", 690, 60, "mentor"),
                ("Club activity", 840, 180, "club", "club"),
            ],
            [
                ("ATC", 480, 60, "rgs"),
                ("SE&PM", 540, 60, "kvs"),
                ("CN", 630, 60, "vvk"),
                ("Library", 690, 60, "library", "library"),
                ("PEC", 840, 60, "ah"),
                ("CCD", 900, 120, "rhs"),
            ],
            [
                ("Pre-placement", 480, 120, "jan"),
                ("Web Lab", 630, 120, "s_fac", "l0-d", "sec-d-2"),
                ("CN Lab", 630, 120, "rp", "l1-d", "sec-d-1"),
                ("AEC Lab", 840, 120, "jan", "l2-d"),
                ("Mentoring", 960, 60, "mentor"),
            ],
            [
                ("SE&PM", 480, 60, "kvs"),
                ("ATC", 540, 60, "rgs"),
                ("Mini Project", 630, 120, "project"),
            ],
        ],
    },
    "E": {
        "room": ("r-sec-e", "Room A251"),
        "week": [
            [
                ("SE&PM", 480, 60, "ckc"),
                ("ATC", 540, 60, "nc"),
                ("CN", 630, 60, "ah"),
                ("RM", 690, 60, "vhu"),
                ("PEC", 840, 60, "an"),
                ("Mini Project", 900, 120, "project"),
            ],
            [
                ("Web Lab", 480, 120, "mmr", "l0-e", "sec-e-1"),
                ("CN Lab", 480, 120, "archana", "l1-e", "sec-e-2"),
                ("CCD", 630, 120, "nc"),
                ("SE&PM", 840, 60, "ckc"),
                ("PEC", 900, 60, "an"),
                ("Mentoring", 960, 60, "mentor"),
            ],
            [
                ("Pre-placement", 480, 60, "nc"),
                ("ATC", 540, 60, "nc"),
                ("Web Lab", 630, 120, "ckc", "l0-e", "sec-e-2"),
                ("CN Lab", 630, 120, "rp", "l1-e", "sec-e-1"),
                ("Club activity", 840, 180, "club", "club"),
            ],
            [
                ("ATC", 480, 60, "nc"),
                ("SE&PM", 540, 60, "ckc"),
                ("CN", 630, 60, "ah"),
                ("Mentoring", 690, 60, "mentor"),
                ("PEC", 840, 60, "an"),
                ("Mini Project", 900, 120, "project"),
            ],
            [
                ("RM", 480, 60, "vhu"),
                ("CN", 540, 60, "ah"),
                ("Pre-placement", 630, 120, "nc"),
                ("AEC Lab", 840, 180, "acs", "l2-e"),
            ],
            [
                ("SE&PM", 480, 60, "ckc"),
                ("CN", 540, 60, "ah"),
                ("ATC", 630, 60, "nc"),
                ("Library", 690, 60, "library", "library"),
            ],
        ],
    },
    "F": {
        "room": ("r-sec-f", "Room A244"),
        "week": [
            [
                ("ATC", 480, 60, "jgc"),
                ("CN", 540, 60, "cmv"),
                ("SE&PM", 630, 60, "km"),
                ("RM", 690, 60, "ckc"),
                ("PEC", 840, 60, "mmr"),
                ("Mini Project", 900, 120, "project"),
            ],
            [
                ("SE&PM", 480, 60, "km"),
                ("CN", 540, 60, "cmv"),
                ("CCD", 630, 120, "supreeth"),
                ("ATC", 840, 60, "jgc"),
                ("PEC", 900, 60, "mmr"),
                ("Mentoring", 960, 60, "mentor"),
            ],
            [
                ("CN", 480, 60, "cmv"),
                ("SE&PM", 540, 60, "km"),
                ("Web Lab", 630, 120, "vhu", "l0-f", "sec-f-1"),
                ("CN Lab", 630, 120, "acs", "l1-f", "sec-f-2"),
                ("Club activity", 840, 180, "club", "club"),
            ],
            [
                ("ATC", 480, 60, "jgc"),
                ("SE&PM", 540, 60, "km"),
                ("Mini Project", 630, 120, "project"),
                ("PEC", 840, 60, "mmr"),
                ("Mentoring", 900, 60, "mentor"),
                ("Library", 960, 60, "library", "library"),
            ],
            [
                ("ATC", 480, 60, "jgc"),
                ("CN", 540, 60, "cmv"),
                ("RM", 630, 60, "ckc"),
                ("Library", 690, 60, "library", "library"),
                ("AEC Lab", 840, 120, "wk", "l2-f"),
                ("Library", 960, 60, "library", "library"),
            ],
            [
                ("Web Lab", 480, 120, "vkl", "l0-f", "sec-f-2"),
                ("CN Lab", 480, 120, "cmv", "l1-f", "sec-f-1"),
                ("Pre-placement", 630, 120, "pb"),
            ],
        ],
    },
}


def seed_all_sections(db, monday):
    """Idempotently seed Sections A, C, D, E, and F alongside Section B."""
    if db.get(Resource, "sec-a"):
        return

    def ensure_resource(id, name, kind, department="CSE", **details):
        if not db.get(Resource, id):
            db.add(Resource(id=id, name=name, kind=kind, dept=department, details=details))

    qualifications = {key: set() for key in ALL_FACULTY}
    for sec in EXTRA_SECTIONS.values():
        for daily_cells in sec["week"]:
            for course, _, _, faculty, *_ in daily_cells:
                if faculty in qualifications:
                    qualifications[faculty].add(COURSES[course][0])
    for key, name in EXTRA_FACULTY.items():
        ensure_resource(
            f"iiet-{key}",
            name,
            "Faculty",
            subjects=sorted(qualifications[key]),
            limit=360,
            consecutive=180,
            available=[480, 1020],
        )
    for key in FACULTY:
        if qualifications[key]:
            rid = "f00" if key == "np" else f"iiet-{key}"
            existing = db.get(Resource, rid)
            if existing:
                details = dict(existing.details or {})
                subs = sorted(set(details.get("subjects") or []) | qualifications[key])
                details["subjects"] = subs
                existing.details = details

    equipment = {}
    for letter, sec in EXTRA_SECTIONS.items():
        low = letter.lower()
        sec_id, b1_id, b2_id = f"sec-{low}", f"sec-{low}-1", f"sec-{low}-2"
        ensure_resource(sec_id, f"Semester V-{letter}", "Cohort", size=60, members=[b1_id, b2_id])
        ensure_resource(b1_id, f"Semester V-{letter} · {letter}1", "Cohort", size=30)
        ensure_resource(b2_id, f"Semester V-{letter} · {letter}2", "Cohort", size=30)

        for role_key, subj in (
            ("project", "Mini Project"),
            ("club", "Club activity"),
            ("mentor", "Mentoring"),
            ("library", "Library"),
        ):
            ensure_resource(
                f"iiet-{role_key}-{low}",
                f"{FACULTY[role_key]} · Sec {letter}",
                "Faculty",
                subjects=[subj],
                limit=360,
                consecutive=180,
                available=[480, 1020],
            )

        room_id, room_name = sec["room"]
        spaces = [
            (room_id, room_name, "Classroom", "b0", 72, ["Projector"]),
            *sec.get("extra_rooms", []),
            (f"library-{low}", f"Library (Sec {letter})", "Classroom", "b1", 72, ["Library"]),
            (f"club-{low}", f"Activity space (Sec {letter})", "Classroom", "b1", 72, ["Activity space"]),
            (f"l0-{low}", f"Web Technology Lab (Sec {letter})", "Laboratory", "b0", 36, ["Web tools", "Network"]),
            (f"l1-{low}", f"Computer Networks Lab (Sec {letter})", "Laboratory", "b0", 36, ["Networking kits", "Network"]),
            (f"l2-{low}", f"AEC Lab (Sec {letter})", "Laboratory", "b0", 72, ["AEC workstations", "Network"]),
        ]
        for rid, rname, kind, building, capacity, tools in spaces:
            equipment[rid] = tools
            ensure_resource(rid, rname, kind, capacity=capacity, building=building, equipment=tools)
            db.flush()
            if not db.query(Dependency).filter_by(source=building, target=rid).first():
                db.add(Dependency(source=building, target=rid, rule="requires building access and power"))
            if kind == "Laboratory" and building == "b0":
                if not db.query(Dependency).filter_by(source="n1", target=rid).first():
                    db.add(Dependency(source="n1", target=rid, rule="requires network connectivity"))

    db.flush()
    for letter, sec in EXTRA_SECTIONS.items():
        low = letter.lower()
        sec_id = f"sec-{low}"
        default_room = sec["room"][0]
        for offset, cells in enumerate(sec["week"]):
            day = (monday + timedelta(days=offset)).isoformat()
            for index, (course, start, duration, faculty, *location) in enumerate(cells):
                raw_room = location[0] if location else default_room
                room = (
                    f"{raw_room}-{low}"
                    if raw_room in ("library", "club")
                    else raw_room
                )
                cohort = location[1] if len(location) > 1 else sec_id
                if faculty in ("project", "club", "mentor", "library"):
                    fid = f"iiet-{faculty}-{low}"
                elif faculty == "np":
                    fid = "f00"
                else:
                    fid = f"iiet-{faculty}"
                lid = f"IIET-{letter}-{offset + 1}-{index + 1}"
                if not db.get(Lesson, lid):
                    db.add(
                        Lesson(
                            id=lid,
                            day=day,
                            subject=COURSES[course][0],
                            dept="CSE",
                            faculty=fid,
                            cohort=cohort,
                            room=room,
                            start=start,
                            duration=duration,
                            kind="Laboratory"
                            if room.startswith("l") and not room.startswith("library")
                            else "Lecture",
                            needs=equipment[room],
                            protected=course
                            in ("Library", "Club activity", "Mentoring", "Mini Project"),
                        )
                    )
