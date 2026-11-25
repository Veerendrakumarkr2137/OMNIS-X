from datetime import date, timedelta
from itertools import combinations

from fastapi.testclient import TestClient

from app.database import Account, State
from app.engine.graph import inventory, unique_students
from app.engine.validation import compatible, eligible
from app.main import create_app
from app.services import lessons
from test_platform import as_role


def test_access_portals_share_staff_timetable_and_isolate_student_batches(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OMNIS_DEMO_DATE", "2026-11-25")
    app = create_app(
        "sqlite:///" + (tmp_path / "access.db").as_posix(), True, dataset="iiet"
    )
    with TestClient(app) as client:
        as_role(client, "admin")
        assert (
            client.post(
                "/api/users",
                json={
                    "username": "section-student",
                    "name": "Section Student (demo)",
                    "role": "Student",
                    "dept": "CSE",
                    "resource": "c00",
                    "password": "SectionStudent!26",
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/users",
                json={
                    "username": "registered-b2",
                    "name": "Registered B2 (demo)",
                    "role": "Student",
                    "dept": "CSE",
                    "resource": "c02",
                    "password": "RegisteredB2!26",
                    "enrollments": {"Web Technology Lab": "Core"},
                },
            ).status_code
            == 201
        )
        as_role(client, "faculty")
        mine = client.get("/api/timetable/me").json()
        shared = client.get("/api/timetable/shared").json()
        assert mine and all(s["faculty"] == "f00" for s in mine)
        assert {s["dept"] for s in shared["sessions"]} == {"CSE", "ECE"}
        assert len(shared["assignment_names"]) > len({s["faculty"] for s in mine})
        as_role(client, "hod")
        assert {
            s["dept"] for s in client.get("/api/timetable/shared").json()["sessions"]
        } == {"CSE"}
        as_role(client, "student")
        assert client.get("/api/timetable/shared").status_code == 403
        assert {s["cohort"] for s in client.get("/api/timetable").json()} == {
            "c00",
            "c01",
        }
        for username, password in (
            ("section-student", "SectionStudent!26"),
            ("registered-b2", "RegisteredB2!26"),
        ):
            assert (
                client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                ).status_code
                == 200
            )
            timetable = client.get("/api/timetable").json()
            assert timetable
            assert client.get("/api/timetable/shared").status_code == 403
            if username == "section-student":
                assert {s["cohort"] for s in timetable} == {"c00"}
            else:
                assert len(timetable) == 1
                assert (
                    timetable[0]["cohort"] == "c02"
                    and timetable[0]["subject"] == "Web Technology Lab"
                )

        b2 = {"username": "student-b2", "password": "DemoB2-Student!26"}
        assert (
            client.post("/api/auth/login", json={**b2, "portal": "Faculty"}).status_code
            == 403
        )
        response = client.post("/api/auth/login", json={**b2, "portal": "Student"})
        assert response.status_code == 200
        assert response.json()["profile"]["batch"] == "B2"
        assert {s["cohort"] for s in client.get("/api/timetable").json()} == {
            "c00",
            "c02",
        }
        assert client.get("/api/timetable/shared").status_code == 403
        with app.state.sessions() as db:
            account = db.get(Account, "student-b2")
            account.details = {**account.details, "access_expires": 1}
            db.commit()
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json=b2).status_code == 401


def test_iiet_database_timetable_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIS_DEMO_DATE", "2026-11-25")
    app = create_app(
        "sqlite:///" + (tmp_path / "iiet.db").as_posix(), True, dataset="iiet"
    )
    with TestClient(app) as client:
        as_role(client, "admin")
        dashboard = client.get("/api/dashboard").json()
        monday = dashboard["anchor"]
        assert monday == "2026-11-23"

        def resilience(day):
            response = client.get("/api/analytics/resilience", params={"day": day})
            assert response.status_code == 200, response.text
            return response.json()

        as_role(client, "hod")
        tuesday = resilience("2026-11-24")
        wednesday = resilience("2026-11-25")
        assert (tuesday["sessions"], wednesday["sessions"]) == (38, 28)
        assert isinstance(tuesday["score"], int) and isinstance(
            wednesday["score"], int
        )
        assert tuesday["factors"]["Qualified backup"] == 100
        assert wednesday["factors"]["Qualified backup"] == 100
        assert len(tuesday["risks"]) >= 1 and len(wednesday["risks"]) >= 1
        sunday = resilience("2026-11-29")
        assert (
            sunday["sessions"] == 0 and sunday["score"] is None and not sunday["risks"]
        )
        assert (
            dashboard["demo_profile"]["courses"]["Automata Theory and Computability"][
                "code"
            ]
            == "BCSPCC501"
        )
        schedule = [
            s
            for s in client.get("/api/timetable").json()
            if s["cohort"] in {"c00", "c01", "c02"}
        ]
        assert len(schedule) == 32
        assert [
            sum(
                s["day"] == (date.fromisoformat(monday) + timedelta(days=i)).isoformat()
                for s in schedule
            )
            for i in range(7)
        ] == [7, 6, 4, 5, 6, 4, 0]
        monday_rows = [s for s in schedule if s["day"] == monday]
        friday_rows = [s for s in schedule if s["day"] == "2026-11-27"]
        assert {
            s["subject"]: s["cohort"] for s in monday_rows if s["start"] == 480
        } == {
            "Web Technology Lab": "c01",
            "Computer Networks Lab": "c02",
        }
        assert {
            s["subject"]: s["cohort"] for s in friday_rows if s["start"] == 480
        } == {
            "Web Technology Lab": "c02",
            "Computer Networks Lab": "c01",
        }
        with app.state.sessions() as db:
            resources = inventory(db)
            settings = db.get(State, 1).settings
            for day in {s["day"] for s in schedule}:
                sessions = lessons(db, day)
                assert all(eligible(s, s, resources, [], settings) for s in sessions)
                assert all(
                    compatible(a, b, resources, 0) for a, b in combinations(sessions, 2)
                )
            assert unique_students(["c00", "c01", "c02"], resources) == 60
            lab, parallel_lab, lecture = monday_rows[:3]
            assert compatible(lab, parallel_lab, resources, 0)
            assert not compatible(lab, {**lecture, "start": 480}, resources, 0)
            assert not eligible(
                lecture, {**lecture, "start": 600}, resources, [], settings
            )

        as_role(client, "student")
        assert (
            client.get("/api/analytics/resilience", params={"day": monday}).status_code
            == 403
        )
        student_schedule = client.get("/api/timetable").json()
        assert {s["cohort"] for s in student_schedule} == {"c00", "c01"}
        as_role(client, "faculty")
        incident = client.post(
            "/api/faculty/absence", json={"day": monday, "start": 630, "end": 690}
        )
        assert incident.status_code == 201, incident.text
        assert incident.json()["impact"]["students"] == 60
        as_role(client, "admin")
        case_id = incident.json()["id"]
        as_role(client, "hod")
        assert resilience(monday)["factors"]["Schedule compliance"] < 100
        assert resilience("2026-11-24") == tuesday
        as_role(client, "admin")
        plans = client.get("/api/recovery/plans", params={"case_id": case_id}).json()
        assert plans[0]["data"]["recovered"] == 1
        assert (
            client.post(f"/api/recovery/plans/{plans[0]['id']}/approve").status_code
            == 200
        )
        as_role(client, "hod")
        assert resilience(monday)["factors"]["Schedule compliance"] == 100
        assert resilience(monday)["factors"]["Recovery success"] == 100
        as_role(client, "student")
        notices = client.get("/api/notifications").json()
        assert (
            notices[0]["title"] == "Automata Theory and Computability timetable update"
        )
        revised = next(
            s for s in client.get("/api/timetable").json() if s["id"] == lecture["id"]
        )
        assert revised["status"] == "Recovered" and revised["start"] == 630
