from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from app.database import Case, Lesson, Plan, Resource, State, User
from app.engine.graph import inventory
from app.engine.validation import eligible, workload, compatible
from app.seed import HASH
from app.services import lessons
from test_platform import as_role, absent, campus


def policy(c, **updates):
    as_role(c, "admin")
    r = c.patch("/api/settings", json={**c.get("/api/settings").json(), **updates})
    assert r.status_code == 200


def test_automatic_low_risk_policy(campus):
    c, _ = campus
    policy(c, mode="Automatic", auto_penalty_limit=50)
    day = c.get("/api/dashboard").json()["anchor"]
    case = c.post(
        "/api/incidents",
        json=dict(title="Room outage", roots=["r0"], day=day, start=510, end=630),
    ).json()
    assert case["status"] == "Recovered"
    assert c.get("/api/timetable/version").json()["version"] == 2
    reported = absent(c)
    assert reported["status"] == "Pending review"


def test_consent_and_targeted_notifications(campus):
    c, app = campus
    policy(c, require_consent=True)
    case = absent(c)
    as_role(c, "admin")
    p = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()[0]
    base = f"/api/recovery/plans/{p['id']}"
    assert c.post(base + "/approve").status_code == 409
    requests = c.post(base + "/request-consent").json()
    assert requests
    with app.state.sessions.begin() as db:
        for r in requests:
            db.query(User).filter_by(
                resource=r["faculty"]
            ).one().password_hash = HASH.hash("PrivateTestPassword!")
    for r in requests:
        assert (
            c.post(
                "/api/auth/login",
                json={
                    "username": "campus-" + r["faculty"],
                    "password": "PrivateTestPassword!",
                },
            ).status_code
            == 200
        )
        assert c.get("/api/faculty/substitutions").json()[0]["plan_id"] == p["id"]
        assert (
            c.post(
                f"/api/faculty/substitutions/{p['id']}", json={"decision": "Accepted"}
            ).status_code
            == 200
        )
    as_role(c, "admin")
    assert c.post(base + "/approve").status_code == 200


def test_admin_directory_preserves_timetable(campus):
    c, _ = campus
    as_role(c, "admin")
    room = c.get("/api/resources/r0").json()
    payload = dict(
        name="Learning space",
        kind="Classroom",
        dept="CSE",
        building="b0",
        capacity=1,
        equipment=["Projector"],
    )
    assert c.put("/api/resources/r0", json=payload).status_code == 409
    assert c.get("/api/resources/r0").json() == room
    assert (
        c.put("/api/resources/r0", json={**payload, "capacity": 75}).status_code == 200
    )
    assert (
        c.post(
            "/api/resources", json={"name": "Design", "kind": "Department"}
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/api/users",
            json=dict(
                username="design-head",
                name="Design Head",
                role="HOD",
                dept="Design",
                password="DesignTestPassword!",
            ),
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"username": "design-head", "password": "DesignTestPassword!"},
        ).status_code
        == 200
    )
    assert c.get("/api/timetable").json() == []
    assert c.get("/api/users").status_code == 403


def test_parallel_approval_only_publishes_once(campus):
    c, _ = campus
    case = absent(c)
    as_role(c, "admin")
    p = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()[0]
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda _: c.post(f"/api/recovery/plans/{p['id']}/approve").status_code,
                range(2),
            )
        )
    assert sorted(results) == [200, 409]
    assert c.get("/api/timetable/version").json()["version"] == 2


def test_partial_day_and_hod_authorization(campus):
    c, _ = campus
    policy(c, hod_approval=True)
    as_role(c, "faculty")
    day = c.get("/api/dashboard").json()["anchor"]
    case = c.post("/api/faculty/absence", json=dict(day=day, start=555, end=570)).json()
    assert len(case["impact"]["sessions"]) == 1
    as_role(c, "hod")
    p = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()[0]
    assert c.post(f"/api/recovery/plans/{p['id']}/approve").status_code == 200


def test_consecutive_travel_and_availability(campus):
    _, app = campus
    with app.state.sessions() as db:
        res = inventory(db)
        session = lessons(db, db.get(State, 1).anchor)[0]
        f = res[session["faculty"]]["details"]
        f["consecutive"] = 60
        assert not workload([session, {**session, "start": session["start"] + 60}], res)
        assert workload([session, {**session, "start": session["start"] + 61}], res)
        assert not compatible(
            session, {**session, "start": session["start"] + 60, "room": "r1"}, res, 15
        )
        f["available"] = [720, 900]
        assert not eligible(session, session, res, [])
