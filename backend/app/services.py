from fastapi import HTTPException
from sqlalchemy import update
from .database import (
    Audit,
    Case,
    Consent,
    Lesson,
    Notice,
    Plan,
    State,
    User,
    fields,
    rows,
)
from .engine.graph import analyze, graph, inventory
from .engine.optimizer import solve
from .engine.validation import validate

LESSON_FIELDS = "id day subject dept faculty room cohort start duration kind needs protected status previous"
CASE_FIELDS = (
    "id actor title day start end roots impact severity simulation status created"
)
PLAN_FIELDS = "id case_id revision rank data status"


def lessons(db, day=None):
    q = db.query(Lesson)
    if day:
        q = q.filter_by(day=day)
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
    day = lessons(db, c.day)
    impact = analyze(g, res, day, c.roots, c.start, c.end)
    active = db.query(Case).filter_by(day=c.day, simulation=False).all()
    outages = [(set(x.impact["depths"]), x.start, x.end) for x in active]
    if c.simulation:
        outages.append((set(impact["depths"]), c.start, c.end))
    affected = [s for s in day if s["id"] in impact["sessions"]]
    fixed = [
        s
        for s in day
        if s["id"] not in impact["sessions"] and s["status"] != "Unresolved"
    ]
    return impact, affected, fixed, res, outages


def generate(db, c, state):
    if c.status in ("Recovered", "Partial recovery", "No impact"):
        raise HTTPException(409, "This incident is already settled.")
    impact, affected, fixed, res, outages = context(db, c)
    for p in db.query(Plan).filter_by(case_id=c.id, status="Pending"):
        p.status = "Superseded"
    plans = []
    alternatives, status = solve(affected, fixed, res, outages, state.settings)
    c.impact = {**impact, "solver_status": status}
    for i, data in enumerate(alternatives, 1):
        p = Plan(
            case_id=c.id,
            rank=i,
            revision=state.revision,
            data=data,
            status="Pending" if data["recovered"] else "Escalated",
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
            "/recovery",
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
    return c


def apply_plan(db, p, c, state, actor):
    if c.simulation or p.status != "Pending" or p.data["recovered"] == 0:
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
    if not validate(affected, fixed, changes, res, outages, state.settings):
        raise HTTPException(
            409, "Plan failed current schedule validation. Generate fresh alternatives."
        )
    for change in changes:
        lesson = db.get(Lesson, change["id"])
        target = change["after"]
        lesson.previous = change["before"]
        if target:
            for k, v in target.items():
                setattr(lesson, k, v)
            lesson.status = "Recovered"
        else:
            lesson.status = "Unresolved"
        recipients = [
            u
            for u in rows(db, User)
            if u.resource
            and u.resource
            in {lesson.faculty, change["before"]["faculty"], lesson.cohort}
        ]

        def description(slot):
            h, m = divmod(slot["start"], 60)
            return f"{h:02}:{m:02}, {res[slot['room']]['name']}, {res[slot['faculty']]['name']}"

        message = (
            lesson.day
            + " · "
            + description(change["before"])
            + " → "
            + (description(target) if target else "Awaiting a new assignment")
        )
        notify(
            db, recipients, lesson.subject + " timetable update", message, "/timetable"
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
        "/recovery",
    )
    db.add(
        Audit(
            actor=actor,
            action=f"Approved plan {p.id} and published timetable v{state.version}",
            case_id=c.id,
        )
    )
