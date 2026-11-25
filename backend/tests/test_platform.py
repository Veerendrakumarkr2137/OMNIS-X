from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.database import Notice, State, Plan, Case, Lesson, User
from app.engine.graph import inventory, overlaps
from app.engine.validation import compatible, eligible, workload, assignment, validate
from app.engine.optimizer import solve
from app.services import lessons


@pytest.fixture
def campus(tmp_path):
    app = create_app("sqlite:///" + (tmp_path / "campus.db").as_posix(), True)
    with TestClient(app) as client:
        yield client, app


def as_role(client, role):
    res = client.post(
        "/api/auth/login",
        json={"username": role, "password": role.capitalize() + "@123"},
    )
    assert res.status_code == 200, res.text


def absent(c):
    as_role(c, "faculty")
    day = c.get("/api/dashboard").json()["anchor"]
    r = c.post(
        "/api/faculty/absence",
        json=dict(day=day, start=480, end=1080, reason="Private leave reason"),
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize("role", ["admin", "hod", "faculty", "student", "operator"])
def test_login(campus, role):
    c, _ = campus
    assert c.get("/api/dashboard").status_code == 401
    assert (
        c.post(
            "/api/auth/login", json={"username": role, "password": "wrong"}
        ).status_code
        == 401
    )
    as_role(c, role)
    assert c.get("/api/auth/me").json()["id"] == role
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_recovery_cycle(campus):
    c, app = campus
    case = absent(c)
    assert len(case["impact"]["sessions"]) == 2 and case["impact"]["students"] == 60
    as_role(c, "admin")
    before = c.get("/api/timetable").json()
    plans = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()
    assert 1 <= len(plans) <= 3
    assert [p["data"]["penalty"] for p in plans] == sorted(
        p["data"]["penalty"] for p in plans
    )
    assert len({str(p["data"]["changes"]) for p in plans}) == len(plans)
    top = plans[0]
    assert all(p["data"]["recovered"] == 2 for p in plans)
    for ch in top["data"]["changes"]:
        assert ch["after"]["faculty"] != "f00"
    route = f"/api/recovery/plans/{top['id']}/approve"
    for role in ("student", "faculty", "operator", "hod"):
        as_role(c, role)
        assert c.post(route).status_code == 403
    as_role(c, "admin")
    assert c.get("/api/timetable").json() == before
    assert c.post(route).status_code == 200
    assert c.post(route).status_code == 409
    assert c.get("/api/timetable/version").json()["version"] == 2
    assert (
        len([s for s in c.get("/api/timetable").json() if s["status"] == "Recovered"])
        == 2
    )
    assert c.get("/api/audit").json()[0]["actor"] == "Alex Morgan"
    as_role(c, "student")
    assert all(s["cohort"] == "c00" for s in c.get("/api/timetable/me").json())
    notices = c.get("/api/notifications").json()
    assert "Algorithms" in notices[0]["title"] and "Private leave reason" not in str(
        notices
    )
    assert c.get("/api/incidents").status_code == 403
    assert c.patch(f"/api/notifications/{notices[0]['id']}/read").status_code == 200
    as_role(c, "faculty")
    assert all(s["faculty"] == "f00" for s in c.get("/api/timetable/me").json())
    assert c.patch(f"/api/notifications/{notices[0]['id']}/read").status_code == 404
    with app.state.sessions() as db:
        assert db.get(State, 1).version == 2
        assert db.query(Notice).filter_by(user_id="operator").count() == 1


def test_stale_and_rebuild(campus):
    c, _ = campus
    as_role(c, "admin")
    p = c.get("/api/recovery/plans").json()[0]
    absent(c)
    as_role(c, "admin")
    assert c.post(f"/api/recovery/plans/{p['id']}/approve").status_code == 409
    fresh = c.post("/api/recovery/generate", json={"case_id": p["case_id"]}).json()
    assert c.post(f"/api/recovery/plans/{fresh[0]['id']}/approve").status_code == 200


def test_department_isolation(campus):
    c, _ = campus
    as_role(c, "hod")
    assert all(s["dept"] == "CSE" for s in c.get("/api/timetable").json())
    assert c.get("/api/incidents/1").status_code == 404
    assert c.get("/api/recovery/plans").json() == []
    assert all(r["dept"] == "CSE" for r in c.get("/api/resources").json())


def test_simulated_multi_failure(campus):
    c, _ = campus
    as_role(c, "operator")
    state = c.get("/api/timetable/version").json()
    schedule = c.get("/api/timetable").json()
    result = c.post(
        "/api/simulations",
        json={
            "title": "Multiple failures",
            "roots": ["f00", "p0"],
            "day": state["anchor"],
            "start": 480,
            "end": 1080,
        },
    )
    assert result.status_code == 201, result.text
    case = result.json()
    assert case["impact"]["depths"]["l0"] == 2 and case["impact"]["depths"]["f00"] == 0
    assert c.get("/api/timetable").json() == schedule
    assert c.get("/api/timetable/version").json() == state
    as_role(c, "admin")
    p = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()[0]
    assert c.post(f"/api/recovery/plans/{p['id']}/apply").status_code == 409


@pytest.mark.parametrize(
    "roots,covered,unresolved", [(["l0", "l3"], 0, 1), (["l0", "l3", "f00"], 1, 1)]
)
def test_unsatisfied_requirements(campus, roots, covered, unresolved):
    c, _ = campus
    as_role(c, "admin")
    day = c.get("/api/dashboard").json()["anchor"]
    case = c.post(
        "/api/simulations",
        json={
            "title": "Laboratory offline",
            "roots": roots,
            "day": day,
            "start": 480,
            "end": 1080,
        },
    ).json()
    p = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()[0]
    assert (p["data"]["recovered"], p["data"]["unresolved"]) == (covered, unresolved)
    assert p["data"]["blockers"]


def test_constraints(campus):
    _, app = campus
    with app.state.sessions() as db:
        res = inventory(db)
        s = lessons(db, db.get(State, 1).anchor)[0]
        assert eligible(s, s, res, [])
        assert not eligible(s, {**s, "faculty": "f10"}, res, [])
        assert not eligible(s, {**s, "room": "l0"}, res, [])
        assert not eligible(s, {**s, "duration": s["duration"] + 10}, res, [])
        assert not eligible(
            s, s, res, [({s["faculty"]}, s["start"] + 1, s["start"] + 5)]
        )
        assert not compatible(s, {**s, "start": s["start"] + 15}, res, 0)
        assert not compatible(
            s, {**s, "faculty": "f01", "room": "r2", "start": s["start"] + 10}, res, 0
        )
        assert not compatible(s, {**s, "faculty": "f01", "cohort": "c01"}, res, 0)
        assert compatible(s, {**s, "start": s["start"] + s["duration"]}, res, 0)
        assert not overlaps(0, 60, 60, 120)
        res[s["faculty"]]["details"]["limit"] = 45
        assert not workload([s], res)
        res[s["room"]]["details"]["capacity"] = 1
        assert not eligible(s, s, res, [])


def test_invalid_change_is_atomic(campus):
    c, app = campus
    case = absent(c)
    as_role(c, "admin")
    before = c.get("/api/timetable").json()
    with app.state.sessions.begin() as db:
        p = db.query(Plan).filter_by(case_id=case["id"], rank=1).one()
        data = deepcopy(p.data)
        data["changes"][-1]["after"]["faculty"] = "f10"
        p.data = data
        pid = p.id
    assert c.post(f"/api/recovery/plans/{pid}/apply").status_code == 409
    assert c.get("/api/timetable").json() == before
    assert c.get("/api/timetable/version").json()["version"] == 1


def test_manual_policy(campus):
    c, _ = campus
    as_role(c, "admin")
    settings = c.get("/api/settings").json()
    assert (
        c.patch("/api/settings", json={**settings, "mode": "Manual"}).status_code == 200
    )
    case = absent(c)
    assert case["status"] == "Open"
    as_role(c, "admin")
    assert (
        c.post("/api/recovery/generate", json={"case_id": case["id"]}).json()[0][
            "data"
        ]["recovered"]
        == 2
    )


def test_persistence_after_restart(tmp_path):
    url = "sqlite:///" + (tmp_path / "restart.db").as_posix()
    with TestClient(create_app(url, True)) as c:
        case = absent(c)
    with TestClient(create_app(url, True)) as c:
        as_role(c, "admin")
        assert (
            c.get(f"/api/incidents/{case['id']}").json()["reason"]
            == "Private leave reason"
        )
