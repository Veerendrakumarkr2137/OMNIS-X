import hashlib
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import OperationalError
from .analytics import risks_and_score
from .admin import ProfileInput, IdentityInput, save_profile, add_user
from .database import (
    Audit,
    Case,
    Consent,
    Dependency,
    Login,
    Notice,
    Plan,
    State,
    User,
    factory,
    fields,
    rows,
)
from .engine.graph import graph, inventory
from .schemas import ConsentDecision, Credentials, Failure, Generate, Interval, Policy
from .seed import HASH, seed
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


def create_app(url=None, demo=None):
    demo = os.getenv("OMNIS_DEMO", "1") == "1" if demo is None else demo

    @asynccontextmanager
    async def lifespan(app):
        app.state.sessions = factory(url)
        with app.state.sessions() as db:
            fresh = db.get(State, 1) is None
            seed(db, demo)
            if demo and fresh:
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
        if user.demo and not demo:
            raise HTTPException(403, "Demo identities are disabled.")
        return user

    def roles(*allowed):
        def check(u=Depends(auth)):
            if u.role not in allowed:
                raise HTTPException(403, "Your role cannot perform this action.")
            return u

        return check

    staff = roles("Admin", "HOD", "Operator")

    def identity(u):
        return fields(u, "id name role dept resource")

    @app.get("/api/config")
    def config():
        return {"demo": demo}

    @app.post("/api/auth/login")
    def login(data: Credentials, response: Response, db=database):
        u = db.get(User, data.username.strip())
        try:
            if (
                not u
                or (u.demo and not demo)
                or not HASH.verify(u.password_hash, data.password)
            ):
                raise HTTPException(401, "Incorrect username or password.")
        except VerificationError:
            raise HTTPException(401, "Incorrect username or password.")
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
        return identity(u)

    @app.post("/api/auth/logout")
    def logout(
        request: Request, response: Response, u=Depends(auth), db=database
    ):
        db.delete(
            db.get(
                Login,
                hashlib.sha256(request.cookies["omnis_session"].encode()).hexdigest(),
            )
        )
        response.delete_cookie("omnis_session")
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(u=Depends(auth)):
        return identity(u)

    def timetable(db, u):
        items = lessons(db)
        if u.role == "HOD":
            items = [s for s in items if s["dept"] == u.dept]
        if u.role == "Faculty":
            items = [s for s in items if s["faculty"] == u.resource]
        if u.role == "Student":
            items = [s for s in items if s["cohort"] == u.resource]
        return items

    @app.get("/api/timetable")
    @app.get("/api/timetable/me")
    @app.get("/api/faculty/me/timetable")
    def schedule(u=Depends(auth), db=database):
        return timetable(db, u)

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
    def create_resource(
        data: ProfileInput, u=Depends(roles("Admin")), db=database
    ):
        return fields(save_profile(db, u, data), "id name kind dept details")

    @app.put("/api/resources/{id}")
    def update_resource(
        id: str, data: ProfileInput, u=Depends(roles("Admin")), db=database
    ):
        return fields(save_profile(db, u, data, id), "id name kind dept details")

    @app.get("/api/users")
    def users(u=Depends(roles("Admin")), db=database):
        return [identity(person) for person in rows(db, User)]

    @app.post("/api/users", status_code=201)
    def create_user(
        data: IdentityInput, u=Depends(roles("Admin")), db=database
    ):
        return identity(add_user(db, u, data, demo))

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
    def absence(data: Interval, u=Depends(roles("Faculty")), db=database):
        return card(
            report(
                db,
                u,
                {
                    **data.model_dump(mode="json"),
                    "roots": [u.resource],
                    "title": u.name + " absence",
                    "severity": "High",
                },
            ),
            u,
        )

    @app.post("/api/incidents", status_code=201)
    @app.post("/api/resources/outage", status_code=201)
    def incident(data: Failure, u=Depends(staff), db=database):
        return card(report(db, u, data.model_dump(mode="json")), u)

    @app.post("/api/simulations", status_code=201)
    def simulation(data: Failure, u=Depends(staff), db=database):
        return card(report(db, u, data.model_dump(mode="json"), True), u)

    @app.get("/api/incidents")
    def incidents(
        u=Depends(roles("Admin", "HOD", "Operator", "Faculty")), db=database
    ):
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
        return [fields(p, PLAN_FIELDS) for p in generate(db, c, state)]

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
        return [
            fields(n, "id title message route seen created")
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
        state.settings = policy.model_dump()
        db.add(
            Audit(actor=u.name, action="Updated recovery policy and objective weights")
        )
        return state.settings

    @app.get("/api/dashboard")
    def dashboard(u=Depends(auth), db=database):
        state = db.get(State, 1)
        result = {
            "user": identity(u),
            "anchor": state.anchor,
            "version": state.version,
            "revision": state.revision,
            "mode": state.settings["mode"],
            "hod_approval": state.settings["hod_approval"],
            "require_consent": state.settings.get("require_consent", False),
        }
        if u.role not in ("Student", "Faculty"):
            res = inventory(db)
            sc = timetable(db, u)
            cs = [c for c in rows(db, Case) if not c.simulation and visible(c, u)]
            if u.role == "HOD":
                res = {
                    k: v
                    for k, v in res.items()
                    if v["dept"] == u.dept
                    or k in {s["room"] for s in sc}
                    or v["kind"] == "Power"
                }
            risk, factors, score = risks_and_score(res, sc, cs, graph(db))
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
            return FileResponse(dist / "index.html")

    return app


app = create_app()
