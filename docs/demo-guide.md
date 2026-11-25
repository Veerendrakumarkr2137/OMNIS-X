# OMNIS-X demo walkthrough

Use a fresh SQLite database for a repeatable demo. The IIET fixture models the CSE Semester V timetable for Sections A–F and includes a fictional ECE department for demonstrating access scope.

## Start with a fresh week

From the project directory in PowerShell, run the commands below. The seed date anchors the first week to Monday, November 23, 2026.

```powershell
$demoFile = Join-Path (Get-Location) ('backend\demo-walkthrough-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.db')
$env:DATABASE_URL = 'sqlite:///' + ($demoFile -replace '\\','/')
$env:OMNIS_DEMO = '1'
$env:OMNIS_DEMO_DATASET = 'iiet'
$env:OMNIS_DEMO_DATE = '2026-11-25'
.\scripts\start_windows.bat
```

Open [OMNIS-X](http://127.0.0.1:8000) once FastAPI is listening. Use **Demo week** in Timetable or **Demo Monday** on a dashboard to return to the seed week.

## Compare access portals

1. Open **Student** under **OMNIS-X Access** and select **Batch B1 demo**. Open **Timetable → Demo week**.
2. Sign out and repeat with **Batch B2 demo**. Both accounts see the common Section B classes. Their 08:00 laboratory assignments differ by batch.

   | Batch | Monday | Friday |
   | --- | --- | --- |
   | B1 | Web Technology Lab | Computer Networks Lab |
   | B2 | Computer Networks Lab | Web Technology Lab |

3. Sign in with the **Faculty** demo. On the Timetable page, **My teaching** shows the instructor's assignments and **Campus timetable** shows read-only published bookings.
4. Use **Admin → Timetable → Demo week** to view both batches and other sections. Open the Section B Monday ATC card to see course code `BCSPCC501`, Room A126 and the demo teaching assignment.

The timetable has Day, Week and List views. Week runs Monday through Sunday. Dates without published records show an empty timetable.

## Explore the Digital twin

1. As **Admin**, **HOD** or **Operator**, open [Digital twin](http://127.0.0.1:8000/twin). In **Resources**, search for `Room A126`, select the room and choose a date with sessions.
2. Select a session to follow its instructor, room and cohort relationships. Use **Graph** beside **Resources** for the dependency map, zoom controls and optional connection labels. The two views share filters and selection.
3. Open **Scenario lab** and set the date to the demo Monday. Choose **Laboratory outage**, set 08:00–10:00 and run impact analysis. Compare the original lab assignment with the proposed recovery.
4. Try **No backup laboratory** for the same interval and compare coverage. Scenario Lab labels these cases as hypothetical.

## Publish a recovery in the demo

1. Sign in with the **Faculty** demo for Dr. Vikram Nair. Choose **Report absence**, select the demo Monday and set 10:30–11:30. The interval overlaps Section B's ATC session.
2. As **Admin**, open **Recovery studio** and choose the report. Compare the before and after assignments and their impact. The demo includes Dr. Vivek Sharma as a qualified ATC substitute when available.
3. Approve a valid plan and confirm publication. Under a consent policy, first request and collect the proposed substitute's consent. Publication advances the timetable version and notifies the affected signed-in roles through their inboxes.
4. Open either Section B demo student account. Check the updated assignment and the notice under **Notifications**.

On a staff **Overview**, change the date and choose **Inspect** under **Resilience overview**. Analytics opens on the selected date with its individual factors. See the [score definitions](architecture.md#date-scoped-resilience).

## Find the imported data in Supabase

The default Tables page opens the `public` schema. Use the direct link to open the authorized project's private schema. [OMNIS-X tables in omnisx](https://supabase.com/dashboard/project/wwzockububqslawmsrkv/database/tables?schema=omnisx).

| Entry | Contents |
| --- | --- |
| `student_roster` | 399 students in 12 batches. Includes names, institutional IDs, sections, batches and source pages. |
| `timetable_reference_pages` | Six weekly source grids with rooms and 54 listed course assignments. |
| `student_timetable` | A roster view of published section and batch sessions. |

The source timetable names Bapuji Institute of Engineering & Technology. The running demo uses IIET identities and modeled rooms, backups, capacities and faculty availability. The private roster and the demo account directory are separate. Individual PEC and AEC allocations still need readable copies of the separate update PDFs.

