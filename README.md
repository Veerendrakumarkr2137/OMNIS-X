# OMNIS-X

**Intelligent Institutional Digital Twin and Automated Recovery Platform**  
Predict. Adapt. Recover.

OMNIS-X is a runnable hackathon application for a fictional institution. A faculty member can report an absence, an authorized reviewer can compare qualified recovery alternatives, and approval publishes a revised timetable to the affected faculty and students.

## Start the local project

The release ZIP contains the working source and a built frontend. Install Python 3.11 or newer with pip. Rebuilding the frontend requires Node.js 22.12 or newer and npm. The project was exercised on Windows with Python 3.14 and Node.js 22.

From the extracted project directory on Windows, run:

```bat
scripts\start_windows.bat
```

On Linux or macOS, run:

```sh
bash scripts/start_linux.sh
```

Open **http://127.0.0.1:8000**. The launchers create a local Python virtual environment, install backend dependencies and serve the bundled frontend. If the frontend build is missing, they install the locked npm dependencies and build it. Initial dependency installation requires internet access.

### Development terminals

In PowerShell, from the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open the Vite localhost URL printed in that terminal. Vite proxies API requests to port 8000. Run `npm.cmd run build` to type-check the client and refresh the production assets.

### Database setup

The first launch creates **backend/omnis.db** and seeds the fictional campus once. The seed includes three departments, twelve lecturers, six cohorts, eight classrooms, four labs, thirty sessions, infrastructure dependencies, one official classroom outage and initial notifications. The database persists across restarts.

Use `OMNIS_DEMO_DATE=YYYY-MM-DD` before first launch to anchor a reproducible demonstration. Use a new `DATABASE_URL` to start another campus without overwriting data. The standalone initializer is `python scripts/seed_database.py` from an activated backend environment. The variables in `.env.example` are read from the process environment.

## Local demo access

Select a role on the sign-in screen or enter its credentials. The backend determines the role from the authenticated identity.

| Role | Username | Password |
| --- | --- | --- |
| Administrator | admin | Admin@123 |
| Head of department | hod | Hod@123 |
| Faculty | faculty | Faculty@123 |
| Student | student | Student@123 |
| Operations | operator | Operator@123 |

The five public demo accounts are for local use. Additional faculty and cohort identities have individual inboxes. An administrator can create an account linked to any of those identities to demonstrate recipient-specific delivery or substitute consent.

## Implemented features

- Five authenticated roles with scoped dashboards, protected routes, department and owner checks, expiring HTTP-only sessions and Argon2 password hashes.
- Partial-day and full-day faculty absences, automatic impact analysis, qualified faculty substitution, room reassignment, same-day rescheduling and up to three distinct ranked plans.
- Constraint-aware CP-SAT selection and independent revalidation. Complete, partial and unrecoverable cases have distinct outcomes and explainable session-level changes.
- Reviewer recommendation, rejection and transactional approval, configurable departmental authority, optional substitute consent, and manual, assisted and limited automatic modes.
- Versioned daily, weekly and list timetables, five-second live refresh, targeted notifications, safe stale-plan handling and an audit trail.
- Role-scoped resource inventory, administrative accounts, department and resource creation, and validated editing of capacity, available teaching intervals and qualifications.
- Interactive campus dependency graph and isolated what-if simulations, including concurrent failures, power cascades, network outages and protected examinations.
- Plan comparison, JSON export, operational readiness analytics, responsive navigation, dark and light themes and accessible dialogs.

## Source and documentation

| Location | Contents |
| --- | --- |
| frontend/src | React workspaces, digital twin, scenario form, recovery comparison, timetable, directory and notifications |
| frontend/e2e | Desktop and mobile browser acceptance tests |
| backend/app | FastAPI routes, database models, seed data, administration, policies and workflow services |
| backend/app/engine | Dependency traversal, constraint validation, candidates, CP-SAT and ranking |
| backend/tests | API, security, optimization, transaction and persistence checks |
| scripts | Windows and Unix startup, database initialization and isolated browser test server |
| docs | Architecture, API reference, demonstration guide and verification record |

**Frontend** uses React, Vite, TypeScript, Tailwind CSS, Radix UI Dialog, Lucide, Framer Motion, React Router, React Flow, Recharts, TanStack Query, React Hook Form, Zod, Sonner and Axios. **Backend** uses FastAPI, Uvicorn, Pydantic, SQLAlchemy, SQLite, NetworkX, OR-Tools CP-SAT and Argon2.

See the [demo walkthrough](docs/demo-guide.md), [architecture and score formulas](docs/architecture.md), [API guide](docs/api.md) and [test record](docs/verification.md).

## Run the tests

From the project directory in PowerShell:

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
cd ..\frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
$env:OMNIS_PYTHON = (Resolve-Path ..\.venv\Scripts\python.exe).Path
$env:OMNIS_CHROME_CHANNEL = 'chrome'
npm.cmd run test:e2e
```

The browser suite launches a separate disposable demo on port 8127. For Playwright-managed Chromium, omit the Chrome-channel variable and run `npx playwright install chromium` first. Tests use fresh databases and leave the live demo timetable intact.

## Scope and limitations

- The local release uses SQLite. PostgreSQL, public hosting, external identity providers, email delivery, schema upgrades and production deployment have not been verified.
- Recovery searches later half-hour slots on the same date. It preserves protected exam times and unaffected sessions. Multi-day reoptimization and post-publication rollback are outside this release.
- Readiness indicators use explicit rules and inventory coverage. Student counts derive from non-overlapping fictional cohorts. The demo models an outage as a bounded time interval and shows resource exposure over the selected demo day.
- Faculty reports take effect as availability events. Formal HR leave adjudication, an announcements editor and a separate examination authoring workflow are outside the hackathon build.
- The schema is created on first run using SQLAlchemy. Supply a fresh database when switching between demo and non-demo modes.

