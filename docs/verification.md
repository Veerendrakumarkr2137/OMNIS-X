# OMNIS-X verification

The November 26, 2026 verification used Windows, Python 3.14.0, Node.js 22.23.1, npm 12.2.0 and installed Chrome. Backend and browser tests used disposable SQLite databases. Database checks queried the connected Supabase project separately.

| Check | Result |
| --- | --- |
| Pytest backend suite | 26 passed |
| Vitest UI suite | 3 passed |
| Playwright Meridian workflow suite | 5 passed |
| Playwright IIET workspace suite | 6 passed |
| TypeScript and Vite build | Passed. The staged entry point matched the local served build. |
| Supabase roster and references | 399 unique students, 12 batches, six timetable pages and 54 course assignment rows verified. |

## Reproduce the checks

From the project directory in PowerShell, use the backend environment and enter the frontend directory for npm and browser checks.

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
.\.venv\Scripts\python.exe -m pytest -q backend/tests

Set-Location frontend
npm.cmd ci
npm.cmd test
npm.cmd run build

$env:OMNIS_PYTHON = (Resolve-Path ..\.venv\Scripts\python.exe).Path
$env:OMNIS_CHROME_CHANNEL = 'chrome'
$env:OMNIS_BROWSER_DATASET = 'meridian'
$env:OMNIS_DEMO_DATE = Get-Date -Format 'yyyy-MM-dd'
npm.cmd run test:e2e -- workflow.spec.ts

$env:OMNIS_BROWSER_DATASET = 'iiet'
$env:OMNIS_DEMO_DATE = '2026-11-25'
npm.cmd run test:e2e -- iiet.spec.ts
```

The browser harness starts its own server on port `8127` and serves the built frontend. It creates a temporary SQLite database for each suite. To use Playwright-managed Chromium, install it with `npx playwright install chromium` and omit `OMNIS_CHROME_CHANNEL`.

## What the tests verify

- **Backend.** Five demo roles, authentication and revocation, department and owner boundaries, batch membership and explicit enrollment, event and leave workflows, CSV and XLSX import, and persistence after restart.
- **Recovery.** Impact analysis, candidate feasibility, protected sessions, faculty and room constraints, stale and repeated approval, consent, concurrent approval, publication and targeted notices. Simulation coverage checks that the official timetable remains intact.
- **Meridian browser workflows.** Role login, fault-tolerant dashboard loading, faculty report through administrator publication and student notice, mobile power-cascade simulation, resource editing, audit, calendar views and theme switching.
- **IIET browser workflows.** Section B lab rotation, personal faculty and shared campus bookings, department accounts, source course details, and Digital twin search, graph switching and selection.

The resilience browser check verifies that each selected date loads the expected session count and displays the score returned by the API. It also checks date carryover to Analytics and the Sunday empty state. Two dates may share the same rounded score.

## Connected Supabase project

The academic checks used the private `omnisx` schema. [OMNIS-X database tables](https://supabase.com/dashboard/project/wwzockububqslawmsrkv/database/tables?schema=omnisx).

| Check | Observed result |
| --- | --- |
| Roster fidelity | Imported rows matched the PDF extraction checksum and contained 399 distinct institutional IDs. |
| Batch mapping | All 12 batches resolved to a section and batch cohort. All 399 students linked to published sessions in the joined view. |
| Timetable reference | One grid per section for A–F, with 54 course assignment rows overall. |
| Visibility | Both source tables have row-level security. The joined view runs with invoker permissions. Anonymous, authenticated Data API and portal application roles do not have roster read access. |

The three objects above document source and publication separately. In the connected project, the Section B demo was extended through January 21, 2027. The weekly source grids cover all six sections. Individual PEC and AEC allocations remain pending readable copies of the separate update files.

Pytest reported a Starlette HTTPX test-client deprecation warning. Vite reported a large entry chunk and discarded two dependency annotations while completing the build. Browser verification used Chrome on localhost. Public hosting, other browsers and load testing require separate verification.

