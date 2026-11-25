from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import update
from .database import (
    Audit,
    Account,
    Case,
    Consent,
    CollegeEvent,
    Enrollment,
    Lesson,
    Notice,
    Plan,
    State,
    User,
    fields,
    rows,
)
from .engine.graph import analyze, graph, inventory, unique_students
from .engine.optimizer import solve, swap_alternatives
from .engine.validation import validate
from .events import blocks_session, dates, reservation_keys

LESSON_FIELDS = "id day subject dept faculty room cohort start duration kind needs protected status previous"
CASE_FIELDS = (
    "id actor title day start end roots impact severity simulation status created"
)
PLAN_FIELDS = "id case_id revision rank data status"


def lessons(db, day=None, *, dept=None, faculty=None, days=None):
    q = db.query(Lesson)
    if day:
        q = q.filter_by(day=day)
    if dept is not None:
        q = q.filter_by(dept=dept)
    if faculty is not None:
        q = q.filter_by(faculty=faculty)
    if days is not None:
        q = q.filter(Lesson.day.in_(days))
    return [
        fields(s, LESSON_FIELDS)
        for s in q.order_by(Lesson.day, Lesson.start, Lesson.id)
    ]


def lock_state(db):
    state = db.get(State, 1)
    # Compare-and-swap serializes official decisions even on SQLite.
    revision = state.revision
    result = db.execute(
        update(State)
        .where(State.id == 1, State.revision == revision)
        .values(revision=revision + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Campus data changed. Refresh and retry.")
    db.refresh(state)
    return state


def visible(c, u):
    if u.role in ("Admin", "Operator"):
        return True
    if u.role == "Faculty":
        return c.actor == u.id
    return u.role == "HOD" and c.impact["departments"] == [u.dept]


def notify(db, users, title, message, route):
    for u in users:
        account = db.get(Account, u.id)
        if not account or account.active:
            db.add(Notice(user_id=u.id, title=title, message=message, route=route))


def reviewers(db, c):
    return [
        u
        for u in rows(db, User)
        if u.role == "Admin" or (u.role == "HOD" and visible(c, u))
    ]


def context(db, c):
    res = inventory(db)
    g = graph(db)
    event = db.query(CollegeEvent).filter_by(case_id=c.id).one_or_none()
    actor = db.get(User, c.actor)
    last_day = event.end_day if event else c.day
    horizon = (
        (date.fromisoformat(last_day) + timedelta(days=6)).isoformat()
        if (
            event or (actor and actor.role == "Faculty" and c.roots == [actor.resource])
        )
        else last_day
    )
    outages = {
        day: []
        for day in dates(c.day, horizon)
        if date.fromisoformat(day).weekday() != 6 or day <= last_day
    }
    schedule = lessons(db, days=list(outages))
    if event:
        keys = reservation_keys(db, event, schedule, res)
        affected = [
            s
            for s in schedule
            if s["status"] != "Unresolved" and blocks_session(s, event, keys, res)
        ]
        cohorts = sorted({s["cohort"] for s in affected})
        impact = {
            "depths": {id: 0 for id in event.scope["rooms"] + event.scope["faculty"]},
            "sessions": [s["id"] for s in affected],
            "cohorts": cohorts,
            "students": unique_students(cohorts, res),
            "departments": sorted(
                {s["dept"] for s in affected}
                or {event.scope["department"] or "Institution"}
            ),
            "exams": sum(s["kind"] == "Examination" for s in affected),
            "minutes": (event.end - event.start)
            * len(list(dates(event.day, event.end_day))),
            "end_day": event.end_day,
        }
        if not event.department_id:
            impact["departments"] = sorted({"Institution", *impact["departments"]})
    else:
        impact = analyze(
            g, res, [s for s in schedule if s["day"] == c.day], c.roots, c.start, c.end
        )
        affected = [s for s in schedule if s["id"] in impact["sessions"]]
    reservations = (
        db.query(CollegeEvent)
        .filter(CollegeEvent.day <= horizon, CollegeEvent.end_day >= c.day)
        .all()
    )
    event_cases = {reservation.case_id for reservation in reservations}
    for other in db.query(Case).filter(
        Case.simulation.is_(False), Case.day.in_(outages)
    ):
        if other.id not in event_cases:
            outages[other.day].append(
                (set(other.impact["depths"]), other.start, other.end)
            )
    for reservation in reservations:
        keys = reservation_keys(db, reservation, schedule, res)
        for day in outages:
            if reservation.day <= day <= reservation.end_day:
                outages[day].append((keys, reservation.start, reservation.end))
    if c.simulation:
        outages[c.day].append((set(impact["depths"]), c.start, c.end))
    fixed = [
        s
        for s in schedule
        if s["id"] not in impact["sessions"] and s["status"] != "Unresolved"
    ]
    return impact, affected, fixed, res, outages


def generate(db, c, state, scope_dept=None):
    if c.status in ("Recovered", "Partial recovery", "No impact", "Class canceled"):
        raise HTTPException(409, "This incident is already settled.")
    impact, affected, fixed, res, outages = context(db, c)
    if scope_dept and impact["departments"] != [scope_dept]:
        raise HTTPException(
            403, "Cross-department recovery requires administrator review."
        )
    for p in db.query(Plan).filter_by(case_id=c.id, status="Pending"):
        p.status = "Superseded"
    plans = []
    settings = {**state.settings, "recovery_days": tuple(outages)}
    alternatives, status = solve(affected, fixed, res, outages, settings)
    person = db.get(User, c.actor)
    if (
        not c.simulation
        and person
        and person.role == "Faculty"
        and c.roots == [person.resource]
    ):
        alternatives += swap_alternatives(affected, fixed, res, outages, settings)
        alternatives.sort(
            key=lambda entry: (
                -entry["recovered"],
                entry["penalty"],
                len(entry["changes"]),
            )
        )
    if (
        state.settings.get("demo_profile")
        and affected
        and alternatives
        and alternatives[0]["recovered"] > 0
    ):
        class_free = {
            "recovered": 0,
            "unresolved": len(affected),
            "rooms": 0,
            "subs": 0,
            "delay": 0,
            "penalty": max(alternatives[0]["penalty"] + 100, 1000 * len(affected)),
            "class_free": True,
            "changes": [
                {
                    "id": s["id"],
                    "day": s["day"],
                    "subject": s["subject"],
                    "cohort": s["cohort"],
                    "before": {
                        "start": s["start"],
                        "faculty": s["faculty"],
                        "room": s["room"],
                    },
                    "after": None,
                }
                for s in affected
            ],
        }
        alternatives = [alternatives[0], class_free]
    else:
        alternatives = alternatives[:2]
    c.impact = {**impact, "solver_status": status}
    for i, data in enumerate(alternatives, 1):
        p = Plan(
            case_id=c.id,
            rank=i,
            revision=state.revision,
            data=data,
            status="Pending" if (data["recovered"] or data.get("class_free")) else "Escalated",
        )
        db.add(p)
        plans.append(p)
    c.status = (
        "No impact"
        if not affected
        else "Pending review"
        if plans and plans[0].data["recovered"]
        else "Needs intervention"
    )
    db.flush()
    if not c.simulation:
        notify(
            db,
            reviewers(db, c),
            c.title,
            c.status + " · " + str(len(affected)) + " affected sessions",
            f"/recovery?case={c.id}",
        )
    return plans


def report(db, u, data, simulation=False):
    res = inventory(db)
    if not data["roots"] or any(
        r not in res or res[r]["kind"] in ("Cohort", "Department")
        for r in data["roots"]
    ):
        raise HTTPException(422, "Choose a supported campus resource.")
    state = db.get(State, 1) if simulation else lock_state(db)
    if not simulation:
        duplicate = next(
            (
                c
                for c in db.query(Case).filter_by(
                    simulation=False,
                    day=data["day"],
                    start=data["start"],
                    end=data["end"],
                )
                if set(c.roots) == set(data["roots"])
            ),
            None,
        )
        if duplicate:
            raise HTTPException(409, "This outage has already been reported.")
    impact = analyze(
        graph(db),
        res,
        lessons(db, data["day"]),
        data["roots"],
        data["start"],
        data["end"],
    )
    if u.role == "HOD" and (
        impact["departments"] != [u.dept]
        or any(res[r]["dept"] != u.dept for r in data["roots"])
    ):
        raise HTTPException(403, "Outside your department.")
    c = Case(actor=u.id, simulation=simulation, impact=impact, **data)
    db.add(c)
    db.flush()
    if simulation or state.settings["mode"] != "Manual":
        plans = generate(db, c, state)
        if (
            not simulation
            and state.settings["mode"] == "Automatic"
            and plans
            and plans[0].data["outcome"] == "Complete"
            and not plans[0].data["delay"]
            and not plans[0].data["subs"]
            and plans[0].data["penalty"] <= state.settings["auto_penalty_limit"]
        ):
            apply_plan(db, plans[0], c, state, "Automation policy")
    elif not simulation:
        notify(
            db,
            reviewers(db, c),
            c.title,
            "Impact analysis ready for manual planning.",
            "/incidents",
        )
    if not simulation:
        db.add(Audit(actor=u.name, action="Reported " + c.title, case_id=c.id))
        if any(res[id]["kind"] != "Faculty" for id in c.roots):
            notify(
                db,
                db.query(User).filter(User.role == "Operator", User.id != u.id),
                "Infrastructure issue",
                f"{c.title} · {c.day}",
                f"/incidents?day={c.day}",
            )
    return c


def apply_plan(db, p, c, state, actor):
    if c.simulation or p.status != "Pending":
        raise HTTPException(409, "This plan cannot be applied.")
    if state.settings.get("require_consent"):
        substitutes = {
            ch["after"]["faculty"]
            for ch in p.data["changes"]
            if ch["after"] and ch["after"]["faculty"] != ch["before"]["faculty"]
        }
        accepted = {
            r.faculty
            for r in db.query(Consent).filter_by(plan_id=p.id, decision="Accepted")
        }
        if not substitutes <= accepted:
            raise HTTPException(
                409, "Ask the proposed substitute faculty for consent before approval."
            )
    impact, affected, fixed, res, outages = context(db, c)
    changes = p.data["changes"]
    settings = {**state.settings, "recovery_days": tuple(outages)}
    if p.data.get("class_free"):
        valid = all(ch["after"] is None for ch in changes)
    elif p.data.get("swap"):
        valid = any(
            changes == option["changes"]
            for option in swap_alternatives(affected, fixed, res, outages, settings)
        )
    else:
        valid = validate(affected, fixed, changes, res, outages, settings)
    if not valid:
        raise HTTPException(
            409, "Plan failed current schedule validation. Generate fresh alternatives."
        )
    from .accounts import student_attends

    students = db.query(User).filter_by(role="Student").all()
    profiles = {student.id: db.get(Account, student.id) for student in students}
    registrations = {}
    for row in rows(db, Enrollment):
        registrations.setdefault(row.student_id, set()).add(row.subject)
    for change in changes:
        lesson = db.get(Lesson, change["id"])
        target = change["after"]
        original_day = lesson.day
        lesson.previous = change["before"]
        if target and "day" in target:
            lesson.previous = {**lesson.previous, "day": original_day}
        if target:
            for k, v in target.items():
                setattr(lesson, k, v)
            lesson.status = "Recovered"
        else:
            lesson.status = "Unresolved"
        recipients = (
            db.query(User)
            .filter(
                User.role == "Faculty",
                User.resource.in_({lesson.faculty, change["before"]["faculty"]}),
            )
            .all()
        )
        recipients.extend(
            student
            for student in students
            if student_attends(
                student,
                fields(lesson, LESSON_FIELDS),
                res,
                profiles[student.id],
                registrations.get(student.id, ()),
            )
        )

        def description(slot):
            h, m = divmod(slot["start"], 60)
            return f"{h:02}:{m:02}, {res[slot['room']]['name']}, {res[slot['faculty']]['name']}"

        message = (
            original_day
            + " · "
            + description(change["before"])
            + " → "
            + (
                (lesson.day + " · " if lesson.day != original_day else "")
                + description(target)
                if target
                else "Class canceled (free period — no teacher available)"
            )
        )
        notify(
            db,
            recipients,
            lesson.subject + (" timetable update" if target else " class canceled"),
            message,
            f"/timetable?day={lesson.day}&session={lesson.id}",
        )
    state.version += 1
    p.status = "Applied"
    c.status = "Partial recovery" if p.data["unresolved"] else "Recovered"
    for other in db.query(Plan).filter(
        Plan.case_id == c.id, Plan.id != p.id, Plan.status == "Pending"
    ):
        other.status = "Superseded"
    notify(
        db,
        reviewers(db, c),
        "Recovery applied",
        f"{c.title} · Timetable v{state.version}",
        f"/recovery?case={c.id}",
    )
    db.add(
        Audit(
            actor=actor,
            action=f"Approved plan {p.id} and published timetable v{state.version}",
            case_id=c.id,
        )
    )
