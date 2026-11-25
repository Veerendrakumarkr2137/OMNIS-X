import hashlib
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import OperationalError
from .analytics import has_assignment_outage, risks_and_score
from .admin import ProfileInput, IdentityInput, LessonInput, add_lesson, save_profile
from .accounts import (
    AccountUpdate,
    PasswordChange,
    PasswordReset,
    active,
    add_user,
    identity,
    lookup_login,
    reset_password,
    student_attends,
    update_user,
    verify_password,
)
from .database import (
    Audit,
    Account,
    Case,
    CollegeEvent,
    Consent,
    Dependency,
    Enrollment,
    LeaveRequest,
    Resource,
    Login,
    Notice,
    Plan,
    State,
    User,
    factory,
    fields,
    rows,
)
from .engine.graph import graph, inventory, overlaps
from .events import (
    EventInput,
    blocks_session,
    create_event,
    event_includes,
    reservation_keys,
)
from .imports import ImportInput, import_accounts
from .schemas import (
    AbsenceInterval,
    ConsentDecision,
    Credentials,
    Failure,
    Generate,
    Interval,
    Policy,
)
from .seed import extend_demo_accounts, seed, seed_batch_demo
from .services import (
    CASE_FIELDS,
    PLAN_FIELDS,
    apply_plan,
    generate,
    lessons,
    lock_state,
    notify,
    report,
    reviewers,
    visible,
)


def create_app(url=None, demo=None, dataset=None):
    demo = os.getenv("OMNIS_DEMO", "1") == "1" if demo is None else demo
    dataset = dataset or os.getenv("OMNIS_DEMO_DATASET", "iiet")
    if demo and dataset not in ("iiet", "meridian"):
        raise ValueError("OMNIS_DEMO_DATASET must be iiet or meridian.")

    @asynccontextmanager
    async def lifespan(app):
        app.state.sessions = factory(
            url, "omnis-iiet.db" if demo and dataset == "iiet" else "omnis.db"
        )
        with app.state.sessions() as db:
            fresh = db.get(State, 1) is None
            seed(db, demo, dataset)
            extend_demo_accounts(db, demo)
            app.state.batch_demo = seed_batch_demo(db, demo)
            db.commit()
            if demo and fresh and dataset == "meridian":
                day = db.get(State, 1).anchor
                report(
                    db,
                    db.get(User, "operator"),
                    dict(
                        title="East Hall classroom outage",
                        day=day,
                        start=510,
                        end=630,
                        roots=["r1"],
                        severity="Medium",
                        reason="Projector maintenance.",
                    ),
                )
                db.commit()
            elif demo and fresh and dataset == "iiet":
                anchor = date.fromisoformat(db.get(State, 1).anchor)
                operator = db.get(User, "operator")
                report(
                    db,
                    operator,
                    dict(
                        title="Room A126 projector outage",
                        day=(anchor + timedelta(days=3)).isoformat(),
                        start=480,
                        end=600,
                        roots=["r0"],
                        severity="Medium",
                        reason="Projector lamp maintenance in Room A126.",
                    ),
                )
                report(
                    db,
                    operator,
                    dict(
                        title="Dr. Vikram Nair morning unavailability",
                        day=(anchor + timedelta(days=5)).isoformat(),
                        start=480,
                        end=540,
                        roots=["f00"],
                        severity="Low",
                        reason="Attending academic review meeting.",
                    ),
                )
                db.commit()
        yield
        app.state.sessions.kw["bind"].dispose()

    app = FastAPI(
        title="OMNIS-X · Institutional Recovery", version="1.0", lifespan=lifespan
    )
    if demo:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", "testserver", "[::1]"],
        )

    @app.middleware("http")
    async def origin(request, call_next):
        source = request.headers.get("origin")
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and source
            and urlsplit(source).netloc != request.headers.get("host")
        ):
            from starlette.responses import JSONResponse

            return JSONResponse({"detail": "Cross-origin write denied."}, 403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def session():
        with app.state.sessions() as db:
            try:
                yield db
                db.commit()
            except OperationalError as exc:
                db.rollback()
                raise HTTPException(
                    409, "Database is busy. Refresh and retry."
                ) from exc

    # Publish responses only after the transaction is durable and visible to other requests.
    database = Depends(session, scope="function")

    def auth(request: Request, db=database):
        token = request.cookies.get("omnis_session", "")
        login = db.get(Login, hashlib.sha256(token.encode()).hexdigest())
        if not login or login.expires <= time.time():
            raise HTTPException(401, "Sign in to your workspace.")
        user = db.get(User, login.user_id)
        if not user or (user.demo and not demo) or not active(db, user):
            raise HTTPException(401, "Sign in to an active account.")
        return user

    def roles(*allowed):
        def check(u=Depends(auth)):
            if u.role not in allowed:
                raise HTTPException(403, "Your role cannot perform this action.")
            return u

        return check

    staff = roles("Admin", "HOD", "Operator")

    @app.get("/api/config")
    def config():
        return {"demo": demo, "batch_demo": app.state.batch_demo}

    @app.post("/api/auth/login")
    def login(data: Credentials, response: Response, db=database):
        u = lookup_login(db, data.username)
        if (
            not u
            or (u.demo and not demo)
            or not active(db, u)
            or not verify_password(u, data.password)
        ):
            raise HTTPException(401, "Incorrect username or password.")
        if data.portal and data.portal != u.role:
            raise HTTPException(
                403, "This account belongs to a different Access portal."
            )
        token = secrets.token_urlsafe(40)
        ttl = 604800 if data.remember else 28800
        db.add(
            Login(
                digest=hashlib.sha256(token.encode()).hexdigest(),
                user_id=u.id,
                expires=int(time.time()) + ttl,
            )
        )
        response.set_cookie(
            "omnis_session",
            token,
            httponly=True,
            secure=not demo,
            samesite="strict",
            max_age=ttl if data.remember else None,
        )
        return identity(db, u)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, u=Depends(auth), db=database):
        db.delete(
            db.get(
                Login,
                hashlib.sha256(request.cookies["omnis_session"].encode()).hexdigest(),
            )
        )
        response.delete_cookie("omnis_session")
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(u=Depends(auth), db=database):
        return identity(db, u)

    @app.post("/api/auth/password")
    def change_password(
        data: PasswordChange, response: Response, u=Depends(auth), db=database
    ):
        if not verify_password(u, data.current_password):
            raise HTTPException(400, "Current password is incorrect.")
        reset_password(db, u, data.password)
        response.delete_cookie("omnis_session")
        return {"ok": True}

    def timetable(db, u, day=None):
        if u.role == "HOD":
            return lessons(db, day, dept=u.dept) if u.dept else []
        if u.role == "Faculty":
            return lessons(db, day, faculty=u.resource) if u.resource else []
        if u.role == "Student":
            if not u.dept or not u.resource:
                return []
            memberships = inventory(db)
            account = db.get(Account, u.id)
            subjects = {
                row.subject for row in db.query(Enrollment).filter_by(student_id=u.id)
            }
            return [
                s
                for s in lessons(db, day, dept=u.dept)
                if student_attends(u, s, memberships, account, subjects)
            ]
        return lessons(db, day)

    @app.get("/api/timetable")
    @app.get("/api/timetable/me")
    @app.get("/api/faculty/me/timetable")
    def schedule(u=Depends(auth), db=database):
        return timetable(db, u)

    @app.get("/api/timetable/shared")
    def shared_schedule(
        u=Depends(roles("Admin", "HOD", "Faculty", "Operator")), db=database
    ):
        # Faculty may read published bookings across campus. Their personal
        # schedule remains the basis for absence reporting and room issues.
        schedule = lessons(db) if u.role == "Faculty" else timetable(db, u)
        resources = inventory(db)
        cases_by_day = group_outages(db.query(Case).filter_by(simulation=False).all())
        return {
            "sessions": schedule,
            "assignment_names": assignment_names(schedule, resources),
            "disrupted_sessions": disrupted_sessions(
                db, schedule, resources, cases_by_day
            ),
        }

    def group_outages(cases):
        by_day = {}
        for case in cases:
            by_day.setdefault(case.day, []).append(case)
        return by_day

    def assignment_names(schedule, resources):
        ids = set()
        for session in schedule:
            ids.update(session[key] for key in ("faculty", "room", "cohort"))
            if session["previous"]:
                ids.update(session["previous"][key] for key in ("faculty", "room"))
        return {id: resources[id]["name"] for id in ids}

    def disrupted_sessions(db, schedule, resources, cases_by_day):
        reservations = [
            (event, reservation_keys(db, event, schedule, resources))
            for event in db.query(CollegeEvent)
        ]
        return [
            s["id"]
            for s in schedule
            if s["status"] != "Unresolved"
            and (
                has_assignment_outage(s, cases_by_day.get(s["day"], []))
                or any(
                    blocks_session(s, event, keys, resources)
                    for event, keys in reservations
                )
            )
        ]

    @app.post("/api/timetable", status_code=201)
    def publish_lesson(data: LessonInput, u=Depends(roles("Admin")), db=database):
        return add_lesson(db, u, data, lock_state(db))

    @app.get("/api/timetable/version")
    def version(u=Depends(auth), db=database):
        state = db.get(State, 1)
        return fields(state, "version revision anchor")

    @app.get("/api/resources")
    def resources(u=Depends(auth), db=database):
        res = inventory(db)
        if u.role in ("Faculty", "Student"):
            ids = {
                s[k] for s in timetable(db, u) for k in ("room", "faculty", "cohort")
            }
            for s in timetable(db, u):
                if s["previous"]:
                    ids.update([s["previous"]["faculty"], s["previous"]["room"]])
            return [dict(r, details={}) for r in res.values() if r["id"] in ids]
        return [r for r in res.values() if u.role != "HOD" or r["dept"] == u.dept]

    @app.get("/api/resources/{id}")
    def resource(id: str, u=Depends(auth), db=database):
        return next((r for r in resources(u, db) if r["id"] == id), None) or missing()

    @app.post("/api/resources", status_code=201)
    def create_resource(data: ProfileInput, u=Depends(roles("Admin")), db=database):
        return fields(save_profile(db, u, data), "id name kind dept details")

    @app.put("/api/resources/{id}")
    def update_resource(
        id: str, data: ProfileInput, u=Depends(roles("Admin")), db=database
    ):
        return fields(save_profile(db, u, data, id), "id name kind dept details")

    @app.get("/api/users")
    def users(u=Depends(roles("Admin")), db=database):
        return [identity(db, person) for person in rows(db, User)]

    @app.post("/api/users", status_code=201)
    def create_user(data: IdentityInput, u=Depends(roles("Admin")), db=database):
        return identity(db, add_user(db, u, data, demo))

    @app.post("/api/users/import", status_code=201)
    def bulk_import(data: ImportInput, u=Depends(roles("Admin")), db=database):
        return import_accounts(db, u, data, demo)

    @app.patch("/api/users/{id}")
    def edit_user(id: str, data: AccountUpdate, u=Depends(roles("Admin")), db=database):
        target = db.get(User, id)
        if not target:
            missing()
        return identity(db, update_user(db, u, target, data))

    @app.post("/api/users/{id}/password")
    def admin_reset(
        id: str, data: PasswordReset, u=Depends(roles("Admin")), db=database
    ):
        target = db.get(User, id)
        if not target:
            missing()
        reset_password(db, target, data.password)
        db.add(Audit(actor=u.name, action=f"Reset credentials for {target.id}"))
        return {"ok": True}

    @app.get("/api/faculty")
    @app.get("/api/faculty/availability")
    def faculty(u=Depends(staff), db=database):
        active = [c for c in rows(db, Case) if not c.simulation and visible(c, u)]
        return [
            {
                **r,
                "unavailable": [
                    fields(c, "day start end") for c in active if r["id"] in c.roots
                ],
            }
            for r in resources(u, db)
            if r["kind"] == "Faculty"
        ]

    @app.get("/api/faculty/substitutes")
    def substitutes(session_id: str, u=Depends(staff), db=database):
        from .engine.optimizer import candidates

        lesson = next((s for s in timetable(db, u) if s["id"] == session_id), None)
        if not lesson:
            missing()
        res = inventory(db)
        fixed = [
            s
            for s in lessons(db, lesson["day"])
            if s["id"] != session_id and s["status"] != "Unresolved"
        ]
        outages = [
            (set(c.impact["depths"]), c.start, c.end)
            for c in db.query(Case).filter_by(simulation=False, day=lesson["day"])
        ]
        options = candidates(
            {**lesson, "protected": True},
            fixed,
            res,
            outages,
            db.get(State, 1).settings,
        )
        ids = sorted(
            {
                o["faculty"]
                for o in options
                if o["faculty"] != lesson["faculty"] and o["room"] == lesson["room"]
            }
        )
        return [{"id": id, "name": res[id]["name"]} for id in ids]

    @app.get("/api/digital-twin")
    @app.get("/api/dependencies")
    def twin(u=Depends(staff), db=database):
        nodes = resources(u, db)
        ids = {r["id"] for r in nodes}
        return {
            "nodes": nodes,
            "edges": [
                fields(e, "source target rule")
                for e in rows(db, Dependency)
                if e.source in ids and e.target in ids
            ],
        }

    def missing():
        raise HTTPException(404, "Record unavailable.")

    def getcase(db, id, u):
        c = db.get(Case, id)
        if not c or not visible(c, u):
            missing()
        return c

    def card(c, u):
        result = fields(c, CASE_FIELDS)
        if u.role in ("Admin", "HOD") or c.actor == u.id:
            result["reason"] = c.reason
        return result

    @app.post("/api/faculty/absence", status_code=201)
    def absence(data: AbsenceInterval, u=Depends(roles("Faculty")), db=database):
        end_day = data.end_day or data.day
        days = (end_day - data.day).days + 1
        first = None
        for offset in range(days):
            current = data.day + timedelta(days=offset)
            day_start = data.start if offset == 0 else 0
            day_end = data.end if offset == days - 1 else 1440
            created = report(
                db,
                u,
                {
                    "day": current.isoformat(),
                    "start": day_start,
                    "end": day_end,
                    "reason": data.reason,
                    "roots": [u.resource],
                    "title": u.name + " absence",
                    "severity": "High",
                },
            )
            if first is None:
                first = created
        return card(first, u)

    @app.post("/api/faculty/leave", status_code=201)
    def request_leave(data: Interval, u=Depends(roles("Faculty")), db=database):
        db.add(LeaveRequest(user_id=u.id, **data.model_dump(mode="json")))
        notify(
            db,
            db.query(User).filter(
                (User.role == "Admin") | ((User.role == "HOD") & (User.dept == u.dept))
            ),
            "Leave request",
            f"{u.name} requested leave for {data.day}.",
            "/events",
        )
        return {"status": "Pending"}

    def visible_leave(request, target, viewer):
        return (
            viewer.id == request.user_id
            or viewer.role == "Admin"
            or (viewer.role == "HOD" and target.dept == viewer.dept)
        )

    @app.get("/api/leave")
    def leave_requests(u=Depends(roles("Admin", "HOD", "Faculty")), db=database):
        return [
            {
                **fields(request, "id user_id day start end reason status"),
                "name": target.name,
            }
            for request, target in db.query(LeaveRequest, User).join(
                User, LeaveRequest.user_id == User.id
            )
            if visible_leave(request, target, u)
        ]

    @app.post("/api/leave/{id}/{decision}")
    def decide_leave(
        id: int, decision: str, u=Depends(roles("Admin", "HOD")), db=database
    ):
        request = db.get(LeaveRequest, id)
        if not request:
            missing()
        target = db.get(User, request.user_id)
        if not visible_leave(request, target, u):
            missing()
        if request.status != "Pending" or decision not in ("approve", "decline"):
            raise HTTPException(409, "Select a pending leave request.")
        updated = (
            db.query(LeaveRequest)
            .filter_by(id=id, status="Pending")
            .update({"status": "Approved" if decision == "approve" else "Declined"})
        )
        if not updated:
            raise HTTPException(409, "The request was already reviewed.")
        if decision == "approve":
            report(
                db,
                target,
                {
                    **fields(request, "day start end reason"),
                    "roots": [target.resource],
                    "title": f"{target.name} approved leave",
                    "severity": "High",
                },
            )
        notify(db, [target], "Leave " + request.status.lower(), request.day, "/events")
        return {"status": request.status}

    @app.post("/api/faculty/issues", status_code=201)
    def report_issue(data: Failure, u=Depends(roles("Faculty")), db=database):
        assigned = {
            s["room"]
            for s in timetable(db, u, data.day.isoformat())
            if overlaps(s["start"], s["start"] + s["duration"], data.start, data.end)
        }
        if not set(data.roots) <= assigned:
            raise HTTPException(
                403, "Select a room assigned to your classes in this time window."
            )
        return card(report(db, u, data.model_dump(mode="json")), u)

    def event_view(event, viewer, db):
        case = db.get(Case, event.case_id) if event.case_id else None
        result = fields(event, "id name department_id day end_day start end mandatory")
        result["department"] = event.scope["department"]
        result["rooms"] = [db.get(Resource, id).name for id in event.scope["rooms"]]
        if viewer.role == "Admin" or (
            viewer.role == "HOD" and event.scope["department"] == viewer.dept
        ):
            result["faculty"] = [
                db.get(Resource, id).name for id in event.scope["faculty"]
            ]
            result["cohorts"] = [
                db.get(Resource, id).name for id in event.scope["cohorts"]
            ]
            result["student_count"] = len(event.scope["students"])
            result["whole_scope"] = event.scope["whole_scope"]
        result["case_id"] = (
            case.id
            if case and viewer.role in ("Admin", "HOD") and visible(case, viewer)
            else None
        )
        return result

    @app.get("/api/events")
    def events(u=Depends(auth), db=database):
        res = inventory(db)
        return [
            event_view(e, u, db)
            for e in db.query(CollegeEvent).order_by(
                CollegeEvent.day, CollegeEvent.start
            )
            if u.role == "Admin"
            or (u.role == "HOD" and e.scope["department"] in (None, u.dept))
            or event_includes(e, u, res)
        ]

    @app.get("/api/events/students")
    def event_students(u=Depends(roles("Admin", "HOD")), db=database):
        return [
            fields(person, "id name dept")
            for person in db.query(User).filter_by(role="Student")
            if (u.role == "Admin" or person.dept == u.dept) and active(db, person)
        ]

    @app.post("/api/events", status_code=201)
    def add_event(data: EventInput, u=Depends(roles("Admin", "HOD")), db=database):
        res = inventory(db)
        state = lock_state(db)
        event = create_event(db, u, data, res)
        case = Case(
            actor=u.id,
            title=event.name,
            day=event.day,
            start=event.start,
            end=event.end,
            roots=event.scope["rooms"],
            impact={},
            severity="High" if event.mandatory else "Medium",
            simulation=False,
        )
        db.add(case)
        db.flush()
        event.case_id = case.id
        db.flush()
        generate(db, case, state)
        recipients = [
            person for person in rows(db, User) if event_includes(event, person, res)
        ]
        notify(
            db, recipients, "College event", f"{event.name} · {event.day}", "/events"
        )
        db.add(
            Audit(
                actor=u.name, action=f"Scheduled event · {event.name}", case_id=case.id
            )
        )
        return event_view(event, u, db)

    @app.post("/api/incidents", status_code=201)
    @app.post("/api/resources/outage", status_code=201)
    def incident(data: Failure, u=Depends(staff), db=database):
        return card(report(db, u, data.model_dump(mode="json")), u)

    @app.post("/api/simulations", status_code=201)
    def simulation(data: Failure, u=Depends(staff), db=database):
        return card(report(db, u, data.model_dump(mode="json"), True), u)

    @app.get("/api/incidents")
    def incidents(u=Depends(roles("Admin", "HOD", "Operator", "Faculty")), db=database):
        return [
            card(c, u)
            for c in db.query(Case).filter_by(simulation=False).order_by(Case.id.desc())
            if visible(c, u)
        ]

    @app.get("/api/simulations")
    def simulations(u=Depends(staff), db=database):
        return [
            card(c, u)
            for c in db.query(Case).filter_by(simulation=True).order_by(Case.id.desc())
            if visible(c, u)
        ]

    @app.get("/api/incidents/{id}")
    def incident_detail(id: int, u=Depends(auth), db=database):
        c = getcase(db, id, u)
        if c.simulation:
            missing()
        return card(c, u)

    @app.get("/api/simulations/{id}")
    def simulation_detail(id: int, u=Depends(staff), db=database):
        c = getcase(db, id, u)
        if not c.simulation:
            missing()
        return card(c, u)

    @app.post("/api/recovery/generate")
    def regenerate(data: Generate, u=Depends(staff), db=database):
        c = getcase(db, data.case_id, u)
        state = db.get(State, 1) if c.simulation else lock_state(db)
        return [
            fields(p, PLAN_FIELDS)
            for p in generate(db, c, state, u.dept if u.role == "HOD" else None)
        ]

    @app.get("/api/recovery/plans")
    def plans(case_id: int | None = None, u=Depends(staff), db=database):
        query = db.query(Plan).join(Case)
        query = (
            query.filter(Case.simulation == False)
            if case_id is None
            else query.filter(Case.id == case_id)
        )
        return [
            fields(p, PLAN_FIELDS)
            for p in query.order_by(Plan.case_id.desc(), Plan.rank)
            if visible(db.get(Case, p.case_id), u)
        ]

    def getplan(db, id, u):
        p = db.get(Plan, id)
        if not p:
            missing()
        return p, getcase(db, p.case_id, u)

    @app.get("/api/recovery/plans/{id}")
    def plan_detail(id: int, u=Depends(staff), db=database):
        return fields(getplan(db, id, u)[0], PLAN_FIELDS)

    @app.post("/api/recovery/plans/{id}/request-consent")
    def request_consent(id: int, u=Depends(staff), db=database):
        p, c = getplan(db, id, u)
        state = db.get(State, 1)
        if (
            not state.settings.get("require_consent")
            or c.simulation
            or p.status != "Pending"
            or p.revision != state.revision
        ):
            raise HTTPException(
                409,
                "Consent is available for current, official plans under the consent policy.",
            )
        substitutes = {
            ch["after"]["faculty"]
            for ch in p.data["changes"]
            if ch["after"] and ch["after"]["faculty"] != ch["before"]["faculty"]
        }
        for f in substitutes:
            if not db.get(Consent, (p.id, f)):
                db.add(Consent(plan_id=p.id, faculty=f))
                notify(
                    db,
                    db.query(User).filter_by(role="Faculty", resource=f),
                    "Substitute teaching request",
                    f"Review alternative {p.rank} for {c.day}.",
                    "/substitutions",
                )
        db.flush()
        return [
            fields(r, "faculty decision")
            for r in db.query(Consent).filter_by(plan_id=p.id)
        ]

    @app.get("/api/faculty/substitutions")
    def substitutions(u=Depends(roles("Faculty")), db=database):
        return [
            dict(
                plan_id=p.id,
                decision=r.decision,
                day=c.day,
                changes=[
                    ch
                    for ch in p.data["changes"]
                    if ch["after"]
                    and ch["after"]["faculty"] == u.resource
                    and ch["before"]["faculty"] != u.resource
                ],
            )
            for r, p, c in db.query(Consent, Plan, Case)
            .join(Plan, Consent.plan_id == Plan.id)
            .join(Case, Plan.case_id == Case.id)
            .filter(
                Consent.faculty == u.resource,
                Plan.status == "Pending",
                Plan.revision == db.get(State, 1).revision,
            )
        ]

    @app.post("/api/faculty/substitutions/{id}")
    def decide(
        id: int, data: ConsentDecision, u=Depends(roles("Faculty")), db=database
    ):
        p = db.get(Plan, id)
        r = db.get(Consent, (id, u.resource))
        if not p or not r:
            missing()
        if (
            r.decision != "Pending"
            or p.status != "Pending"
            or p.revision != db.get(State, 1).revision
        ):
            raise HTTPException(409, "The substitution request is no longer pending.")
        updated = (
            db.query(Consent)
            .filter_by(plan_id=id, faculty=u.resource, decision="Pending")
            .update({"decision": data.decision})
        )
        if not updated:
            raise HTTPException(409, "This request has already been answered.")
        c = db.get(Case, p.case_id)
        notify(
            db,
            reviewers(db, c),
            "Substitution " + data.decision.lower(),
            f"{u.name} · alternative {p.rank} · {c.day}",
            "/recovery",
        )
        db.add(
            Audit(
                actor=u.name,
                action=f"{data.decision} substitution for plan {id}",
                case_id=c.id,
            )
        )
        return {"decision": data.decision}

    @app.post("/api/recovery/plans/{id}/approve")
    @app.post("/api/recovery/plans/{id}/apply")
    def approve(id: int, u=Depends(roles("Admin", "HOD")), db=database):
        p, c = getplan(db, id, u)
        state = lock_state(db)
        if u.role == "HOD" and not state.settings["hod_approval"]:
            raise HTTPException(403, "Department approval is disabled.")
        if u.role == "HOD" and any(
            db.get(Resource, change["after"]["room"]).dept not in (None, u.dept)
            for change in p.data["changes"]
            if change["after"] and change["after"]["room"] != change["before"]["room"]
        ):
            raise HTTPException(
                403,
                "A recovery that uses another department's room requires administrator approval.",
            )
        if p.revision != state.revision - 1:
            raise HTTPException(409, "Stale plan. Generate new alternatives.")
        apply_plan(db, p, c, state, u.name)
        return {
            "status": p.status,
            "version": state.version,
            "changes": p.data["changes"],
        }

    @app.post("/api/recovery/plans/{id}/reject")
    def reject(id: int, u=Depends(roles("Admin", "HOD")), db=database):
        p, c = getplan(db, id, u)
        state = lock_state(db)
        if u.role == "HOD" and not state.settings["hod_approval"]:
            raise HTTPException(403, "Department approval is disabled.")
        if c.simulation or p.status != "Pending":
            raise HTTPException(409, "Only pending official plans can be rejected.")
        p.status = "Rejected"
        for other in db.query(Plan).filter_by(
            case_id=c.id, status="Pending", revision=state.revision - 1
        ):
            other.revision = state.revision
        db.flush()
        if not db.query(Plan).filter_by(case_id=c.id, status="Pending").count():
            c.status = "Needs intervention"
        db.add(Audit(actor=u.name, action=f"Rejected plan {id}", case_id=c.id))
        notify(db, reviewers(db, c), "Recovery plan rejected", c.title, "/recovery")
        return {"status": p.status}

    @app.post("/api/recovery/plans/{id}/recommend")
    def recommend(id: int, u=Depends(roles("HOD", "Operator")), db=database):
        p, c = getplan(db, id, u)
        if c.simulation or p.status != "Pending":
            raise HTTPException(409, "Select a pending official plan.")
        notify(
            db,
            [a for a in reviewers(db, c) if a.role == "Admin"],
            "Plan recommended",
            f"{u.name} recommends alternative {p.rank} for {c.title}.",
            "/recovery",
        )
        db.add(Audit(actor=u.name, action=f"Recommended plan {id}", case_id=c.id))
        return {"ok": True}

    @app.get("/api/notifications")
    def notifications(u=Depends(auth), db=database):
        categories = {
            "timetable": "Timetable",
            "events": "Events & leave",
            "recovery": "Recovery",
            "incidents": "Incidents",
            "substitutions": "Substitutions",
        }
        return [
            {
                **fields(n, "id title message route seen created"),
                "category": categories.get(n.route.split("?")[0].strip("/"), "General"),
            }
            for n in db.query(Notice).filter_by(user_id=u.id).order_by(Notice.id.desc())
        ]

    @app.patch("/api/notifications/{id}/read")
    def read(id: int, u=Depends(auth), db=database):
        n = db.get(Notice, id)
        if not n or n.user_id != u.id:
            missing()
        n.seen = True
        return {"ok": True}

    @app.post("/api/notifications/read-all")
    def read_all(u=Depends(auth), db=database):
        db.query(Notice).filter_by(user_id=u.id).update({"seen": True})
        return {"ok": True}

    @app.get("/api/audit")
    def audit(u=Depends(roles("Admin")), db=database):
        return [
            fields(a, "id actor action case_id created")
            for a in db.query(Audit).order_by(Audit.id.desc())
        ]

    @app.get("/api/settings")
    def settings(u=Depends(roles("Admin")), db=database):
        return db.get(State, 1).settings

    @app.patch("/api/settings")
    def save_settings(policy: Policy, u=Depends(roles("Admin")), db=database):
        state = lock_state(db)
        state.settings = {**state.settings, **policy.model_dump(exclude_none=True)}
        db.add(
            Audit(actor=u.name, action="Updated recovery policy and objective weights")
        )
        return state.settings

    def analytics_resources(resources, schedule, user):
        if user.role != "HOD":
            return resources
        assigned_rooms = {s["room"] for s in schedule}
        return {
            key: r
            for key, r in resources.items()
            if r["dept"] == user.dept or key in assigned_rooms or r["kind"] == "Power"
        }

    @app.get("/api/analytics/resilience")
    def resilience(day: date, u=Depends(staff), db=database):
        """Calculate readiness for the selected timetable date."""
        date_key = day.isoformat()
        schedule = timetable(db, u, date_key)
        official_cases = db.query(Case).filter_by(day=date_key, simulation=False).all()
        visible_cases = [case for case in official_cases if visible(case, u)]
        all_resources = inventory(db)
        resources = analytics_resources(all_resources, schedule, u)
        reservations = [
            (e, reservation_keys(db, e, schedule, all_resources))
            for e in db.query(CollegeEvent).filter(
                CollegeEvent.day <= date_key, CollegeEvent.end_day >= date_key
            )
        ]
        disrupted = {
            s["id"]
            for s in schedule
            if s["status"] != "Unresolved"
            and (
                has_assignment_outage(s, official_cases)
                or any(
                    blocks_session(s, event, keys, all_resources)
                    for event, keys in reservations
                )
            )
        }
        risks, factors, score = risks_and_score(
            resources,
            schedule,
            visible_cases,
            graph(db),
            selected_day=True,
            disrupted=disrupted,
        )
        return {
            "day": date_key,
            "sessions": len(schedule),
            "score": score,
            "factors": factors,
            "risks": risks,
        }

    @app.get("/api/dashboard")
    def dashboard(u=Depends(auth), db=database):
        state = db.get(State, 1)
        schedule = timetable(db, u)
        campus_resources = inventory(db)
        official_cases = db.query(Case).filter_by(simulation=False).all()
        outages_by_day = group_outages(official_cases)
        demo_profile = state.settings.get("demo_profile") if demo else None
        result = {
            "user": identity(db, u),
            "anchor": state.anchor,
            "today": date.today().isoformat(),
            "demo": demo,
            "campus_name": demo_profile.get("campus_name") if demo_profile else None,
            "demo_profile": demo_profile
            if not demo_profile
            or u.dept in (None, demo_profile.get("department", "CSE"))
            else None,
            "version": state.version,
            "revision": state.revision,
            "mode": state.settings["mode"],
            "hod_approval": state.settings["hod_approval"],
            "require_consent": state.settings.get("require_consent", False),
            "allow_substitution": state.settings.get("allow_substitution", False),
            "assignment_names": assignment_names(schedule, campus_resources),
            "disrupted_sessions": disrupted_sessions(
                db, schedule, campus_resources, outages_by_day
            ),
        }
        if u.role == "Faculty":
            faculty = campus_resources.get(u.resource)
            if faculty:
                result["teaching_profile"] = {
                    key: faculty["details"][key]
                    for key in ("subjects", "available", "limit")
                }
        if u.role == "HOD":
            result["department_summary"] = {
                "students": sum(
                    active(db, person)
                    for person in db.query(User).filter_by(role="Student", dept=u.dept)
                ),
                "pending_leave": sum(
                    1
                    for leave, person in db.query(LeaveRequest, User).join(
                        User, LeaveRequest.user_id == User.id
                    )
                    if leave.status == "Pending" and person.dept == u.dept
                ),
            }
        if u.role not in ("Student", "Faculty"):
            resource_ids = {
                r["id"]
                for r in campus_resources.values()
                if u.role != "HOD" or r["dept"] == u.dept
            }
            outage_resources = {}
            for day, cases in outages_by_day.items():
                blocked = resource_ids.intersection(
                    id for case in cases for id in case.impact["depths"]
                )
                if blocked:
                    outage_resources[day] = sorted(blocked)
            result["outage_resources"] = outage_resources
            res = analytics_resources(campus_resources, schedule, u)
            cs = [c for c in official_cases if visible(c, u)]
            risk, factors, score = risks_and_score(res, schedule, cs, graph(db))
            result.update(risks=risk, factors=factors, score=score)
        return result

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (dist / "index.html").is_file() and (dist / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=dist / "assets", check_dir=False),
            name="assets",
        )

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                missing()
            return FileResponse(
                dist / "index.html", headers={"Cache-Control": "no-cache"}
            )

    return app


app = create_app()
