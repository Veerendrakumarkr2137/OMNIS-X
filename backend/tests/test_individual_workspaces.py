import base64
from datetime import date, timedelta
from io import BytesIO
from zipfile import ZipFile

from test_platform import as_role, campus


def login(client, id, password):
    response = client.post(
        "/api/auth/login", json={"username": id, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_personal_authentication_and_account_lifecycle(campus):
    c, _ = campus
    as_role(c, "faculty")
    original = c.get("/api/timetable/me").json()
    assert original and {s["faculty"] for s in original} == {"f00"}
    assert (
        c.post(
            "/api/auth/password",
            json={"current_password": "wrong", "password": "NewFaculty!26"},
        ).status_code
        == 400
    )
    as_role(c, "admin")
    new_password = "DemoSecondFaculty!26"
    assert (
        c.post(
            "/api/users/campus-f01/password", json={"password": new_password}
        ).status_code
        == 200
    )
    account = login(c, "CAMPUS-F01@DEMO.OMNIS.EXAMPLE", new_password)
    assert account["department_id"] == "dept0" and account["resource"] == "f01"
    personal = c.get("/api/timetable/me").json()
    assert personal and {s["faculty"] for s in personal} == {"f01"}
    lesson = personal[0]
    report = c.post(
        "/api/faculty/absence",
        json={
            "day": lesson["day"],
            "start": lesson["start"],
            "end": lesson["start"] + lesson["duration"],
            "roots": ["f00"],
        },
    )
    assert report.status_code == 201, report.text
    assert report.json()["roots"] == ["f01"]
    assert set(report.json()["impact"]["sessions"]) == {lesson["id"]}
    assert c.patch("/api/users/faculty", json={"active": False}).status_code == 403
    assert (
        c.post(
            "/api/auth/password",
            json={"current_password": new_password, "password": "ChangedFaculty!26"},
        ).status_code
        == 200
    )
    assert c.get("/api/auth/me").status_code == 401
    login(c, "campus-f01", "ChangedFaculty!26")
    as_role(c, "admin")
    assert c.patch("/api/users/campus-f01", json={"active": False}).status_code == 200
    assert (
        c.post(
            "/api/auth/login",
            json={"username": "campus-f01", "password": "ChangedFaculty!26"},
        ).status_code
        == 401
    )
    assert c.get("/api/timetable").json()
    file = BytesIO()
    with ZipFile(file, "w") as workbook:
        workbook.writestr(
            "xl/worksheets/sheet1.xml",
            """
        <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
          <sheetData>
            <row><c r="A1" t="inlineStr"><is><t>record</t></is></c><c r="B1" t="inlineStr"><is><t>name</t></is></c></row>
            <row><c r="A2" t="inlineStr"><is><t>department</t></is></c><c r="B2" t="inlineStr"><is><t>AIML</t></is></c></row>
          </sheetData>
        </worksheet>
        """,
        )
    result = c.post(
        "/api/users/import",
        json={
            "filename": "directory.xlsx",
            "content": base64.b64encode(file.getvalue()).decode(),
        },
    )
    assert result.status_code == 201, result.text
    assert any(r["name"] == "AIML" for r in c.get("/api/resources").json())


def test_registrations_and_effective_recovery_notifications(campus):
    c, _ = campus
    as_role(c, "admin")
    settings = c.get("/api/settings").json()
    assert (
        c.patch(
            "/api/settings", json={**settings, "allow_substitution": False}
        ).status_code
        == 200
    )
    day = c.get("/api/dashboard").json()["anchor"]
    records = "username,name,role,dept,resource,password,enrollments\n" + "\n".join(
        [
            "usn-alpha,Alpha Student,Student,CSE,c00,AlphaStudent!26,Algorithms:PCC",
            "usn-beta,Beta Student,Student,CSE,c00,BetaStudent!26,Data Structures:Elective",
        ]
    )
    imported = c.post(
        "/api/users/import",
        json={
            "filename": "students.csv",
            "content": base64.b64encode(records.encode()).decode(),
        },
    )
    assert imported.status_code == 201, imported.text
    assert (
        c.post(
            "/api/users/import",
            json={
                "filename": "students.csv",
                "content": base64.b64encode(records.encode()).decode(),
            },
        ).status_code
        == 409
    )
    login(c, "usn-alpha", "AlphaStudent!26")
    assert {s["subject"] for s in c.get("/api/timetable").json()} == {"Algorithms"}
    login(c, "usn-beta", "BetaStudent!26")
    assert {s["subject"] for s in c.get("/api/timetable").json()} == {"Data Structures"}
    as_role(c, "faculty")
    case = c.post(
        "/api/faculty/absence", json={"day": day, "start": 0, "end": 1440}
    ).json()
    as_role(c, "hod")
    plans = c.get("/api/recovery/plans", params={"case_id": case["id"]}).json()
    assert plans and plans[0]["data"]["recovered"] > 0 and plans[0]["data"]["subs"] == 0
    moved = next(
        change
        for change in plans[0]["data"]["changes"]
        if change["subject"] == "Algorithms"
    )
    assert (
        moved["after"]["day"] > day
        and moved["before"]["faculty"] == moved["after"]["faculty"]
    )
    as_role(c, "admin")
    assert c.post(f"/api/recovery/plans/{plans[0]['id']}/approve").status_code == 200
    login(c, "usn-alpha", "AlphaStudent!26")
    assert any(
        s["id"] == moved["id"] and s["day"] == moved["after"]["day"]
        for s in c.get("/api/timetable").json()
    )
    assert any("Algorithms" in n["title"] for n in c.get("/api/notifications").json())
    login(c, "usn-beta", "BetaStudent!26")
    assert not any(
        "Algorithms" in n["title"] for n in c.get("/api/notifications").json()
    )


def test_department_events_and_institution_escalation(campus):
    c, _ = campus
    as_role(c, "hod")
    dashboard = c.get("/api/dashboard").json()
    day = dashboard["anchor"]
    base = {
        "name": "Department workshop",
        "day": day,
        "start": 480,
        "end": 1020,
        "department_id": "dept0",
        "mandatory": True,
        "faculty": ["f00"],
        "whole_scope": False,
    }
    assert (
        c.post("/api/events", json={**base, "department_id": "dept1"}).status_code
        == 403
    )
    assert c.post("/api/events", json={**base, "faculty": ["f10"]}).status_code == 422
    event = c.post("/api/events", json=base)
    assert event.status_code == 201, event.text
    case_id = event.json()["case_id"]
    assert c.get(f"/api/incidents/{case_id}").json()["impact"]["departments"] == ["CSE"]
    cse_ids = {s["id"] for s in c.get("/api/timetable").json()}
    login(c, "hod-ece", "DemoECEHead!26")
    ece = c.get("/api/timetable").json()
    assert ece and {s["dept"] for s in ece} == {"ECE"}
    assert not cse_ids & {s["id"] for s in ece}
    assert c.get("/api/events").json() == []
    assert c.get(f"/api/incidents/{case_id}").status_code == 404
    assert not any(
        "workshop" in n["title"].lower() for n in c.get("/api/notifications").json()
    )
    as_role(c, "admin")
    last = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    event = c.post(
        "/api/events",
        json={
            "name": "Campus meeting",
            "day": day,
            "end_day": last,
            "start": 525,
            "end": 615,
            "whole_scope": True,
            "mandatory": True,
        },
    )
    assert event.status_code == 201, event.text
    case_id = event.json()["case_id"]
    case = c.get(f"/api/incidents/{case_id}").json()
    assert case["impact"]["end_day"] == last
    assert {"CSE", "ECE", "Institution"} <= set(case["impact"]["departments"])
    assert c.get("/api/recovery/plans", params={"case_id": case_id}).json()
    as_role(c, "hod")
    assert c.get("/api/recovery/plans", params={"case_id": case_id}).json() == []

    as_role(c, "faculty")
    assert (
        c.post(
            "/api/faculty/leave",
            json={"day": last, "start": 640, "end": 725, "reason": "Private duty"},
        ).status_code
        == 201
    )
    leave_id = c.get("/api/leave").json()[0]["id"]
    login(c, "hod-ece", "DemoECEHead!26")
    assert c.get("/api/leave").json() == []
    assert c.post(f"/api/leave/{leave_id}/approve").status_code == 404
    as_role(c, "hod")
    assert c.post(f"/api/leave/{leave_id}/approve").status_code == 200
    as_role(c, "faculty")
    assert c.get("/api/leave").json()[0]["status"] == "Approved"
