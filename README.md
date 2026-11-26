<h1 align="center">
  <img src="docs/assets/omnis-x-banner.svg" alt="OMNIS-X — Institutional digital twin and timetable recovery" width="1200">
</h1>

<p align="center">
  <img src="docs/assets/omnis-x-stack.svg" alt="React, FastAPI, Supabase, and OR-Tools" width="676">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/api.md">API reference</a> ·
  <a href="docs/demo-guide.md">Demo walkthrough</a> ·
  <a href="docs/verification.md">Verification</a> ·
  <a href="#contributors">Contributors</a>
</p>

OMNIS-X is an institutional digital twin and recovery portal for colleges. It connects published timetables, teaching resources and campus disruptions so staff can compare recovery plans and students can see changes that affect their own classes.

The portal runs locally with SQLite or uses Supabase PostgreSQL through a FastAPI backend. The IIET demo includes section and batch timetables, faculty assignments and sample outages for trying the recovery workflow.

## Features

- **Role-based workspaces** for administrators, department heads, faculty, students and operations staff.
- **Timetables** with Day, Week and List views, individual faculty assignments, and section, batch and course filtering for students.
- **Digital twin** with a searchable resource list and an interactive dependency graph that share the same filters.
- **Scenario Lab** for testing room, power, network and faculty disruptions against the campus model.
- **Recovery Studio** for comparing room changes, substitute instructors and makeup slots, then reviewing and publishing an eligible plan.
- **Date-scoped resilience** showing the score, its contributing factors and scheduled-session coverage.
- **Campus administration** for resource and account management, CSV or XLSX imports, events, leave and policy settings.
- **Publication tracking** through timetable versions, targeted notifications and an audit log.

## Tech stack

| Layer | Tools |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS and React Router |
| Data and visuals | TanStack Query, React Flow and Recharts |
| API and persistence | FastAPI, Pydantic, SQLAlchemy, SQLite and PostgreSQL via Psycopg |
| Recovery engine | NetworkX for dependency analysis and OR-Tools CP-SAT for constrained scheduling |
| Testing | Pytest, Vitest, React Testing Library and Playwright |

## Requirements

- Python 3.11 or later with pip.
- Node.js 22.12 or later with npm to develop or build the frontend.
- A browser and internet access for the initial dependency install.
- A Supabase project and PostgreSQL connection details when using the hosted database.

## Quick start

Run the appropriate launcher from the repository root. The launchers install the backend dependencies and build the frontend when `frontend/dist/index.html` is missing.

**Windows**

```bat
scripts\start_windows.bat
```

**Linux or macOS**

```sh
bash scripts/start_linux.sh
```

Open [OMNIS-X](http://127.0.0.1:8000). Select a demo role on the sign-in page. Under **Student Access**, choose **Batch B1 demo** or **Batch B2 demo**, then open **Timetable → Demo week** to see the lab rotation.

| Batch | Monday at 08:00 | Friday at 08:00 |
| --- | --- | --- |
| B1 | Web Technology Lab | Computer Networks Lab |
| B2 | Computer Networks Lab | Web Technology Lab |

The [demo walkthrough](docs/demo-guide.md) shows how to start with a fresh database, report a faculty absence and publish a recovery.

## Database setup

The backend reads process environment variables first and fills unset values from the ignored root `.env`. The [environment example](.env.example) lists the available settings.

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | Selects SQLite or PostgreSQL. The default is `backend/omnis-iiet.db` for the IIET demo and `backend/omnis.db` otherwise. |
| `OMNIS_DEMO` | `1` enables local demo mode. `0` enables non-demo mode with secure session cookies. |
| `OMNIS_DEMO_DATASET` | `iiet` selects the default timetable fixture. `meridian` selects the fictional campus fixture. |
| `OMNIS_DEMO_DATE` | Seed date for a new database. The IIET fixture starts on the Monday of that week. |
| `OMNIS_ADMIN` and `OMNIS_ADMIN_PASSWORD` | Initial administrator credentials for a new non-demo database. The password requires at least 12 characters. |

### Local SQLite

With no `DATABASE_URL`, the app initializes a local SQLite file on startup and reuses it on later runs. To start over without overwriting your current data, set `DATABASE_URL` to a new SQLite file. Run `python scripts/seed_database.py` in the backend environment to initialize the selected database without serving the UI.

### Supabase PostgreSQL

Use the project's **Session pooler** details and the dedicated `omnisx_app` database login. The connection string belongs in the backend environment or root `.env`. URL-encode the password and query values. Use `sslmode=verify-full` and the CA appropriate for the connection. [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

```dotenv
DATABASE_URL=postgresql+psycopg://omnisx_app.PROJECT_REF:URL_ENCODED_PASSWORD@SESSION_POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=ABSOLUTE_CA_PATH
```

For an empty project, generate the operational SQL with `python scripts/supabase_schema.py`, apply it as a PostgreSQL administrator, and provision the dedicated role for password login. To copy an existing SQLite installation, stop its writer, keep a backup, and run `python scripts/migrate_sqlite_to_supabase.py backend/omnis-iiet.db` against the empty target before starting the portal. The copy verifies row counts and leaves users to sign in again.

## Project structure

```text
.
├── README.md
├── .env.example
├── backend/
│   ├── app/
│   │   ├── engine/          Dependency analysis, candidate generation and validation
│   │   ├── main.py          FastAPI routes and startup
│   │   ├── database.py      Models and database configuration
│   │   ├── services.py      Incident, recovery and publication workflows
│   │   └── iiet.py          IIET timetable fixture
│   ├── tests/               Backend tests
│   └── requirements.txt
├── frontend/
│   ├── src/                 Role workspaces and UI components
│   ├── e2e/                 Playwright scenarios
│   └── vite.config.ts
├── scripts/                 Startup, seeding, database migration and test server
└── docs/                    Architecture, API, walkthrough and verification
```

## Source package guide

| File | Responsibility |
| --- | --- |
| [main.tsx](frontend/src/main.tsx) | Sign-in state, protected navigation and workspace refresh |
| [Twin.tsx](frontend/src/Twin.tsx) and [TwinGraph.tsx](frontend/src/TwinGraph.tsx) | Resource browsing and the dependency graph |
| [Dashboard.tsx](frontend/src/Dashboard.tsx) and [Recovery.tsx](frontend/src/Recovery.tsx) | Role dashboards, plan comparison and publication controls |
| [accounts.py](backend/app/accounts.py) and [imports.py](backend/app/imports.py) | Account profiles, enrollment filtering and CSV or XLSX import |
| [events.py](backend/app/events.py) and [analytics.py](backend/app/analytics.py) | Campus event scope, reservations and resilience calculations |
| [optimizer.py](backend/app/engine/optimizer.py) and [validation.py](backend/app/engine/validation.py) | Scheduling search, ranking and independent validation |

## Application flow

```mermaid
flowchart LR
    R["Report disruption"] --> I["Trace impact"] --> P["Compare recovery plans"]
    P --> V["Review and validate"] --> U["Publish timetable"]
    P --> S["Show simulation results"]

    classDef report fill:#4338a5,color:#fff,stroke:#a5b4fc
    classDef impact fill:#155e9d,color:#fff,stroke:#7dd3fc
    classDef plans fill:#15766a,color:#fff,stroke:#6ee7b7
    classDef review fill:#824720,color:#fff,stroke:#fdba74
    classDef publish fill:#246747,color:#fff,stroke:#86efac
    classDef scenario fill:#694598,color:#fff,stroke:#d8b4fe
    class R report
    class I impact
    class P plans
    class V review
    class U publish
    class S scenario
```

1. FastAPI opens the configured database and initializes its seed state when needed.
2. The React workspace signs in through FastAPI. The server scopes sessions, resources and actions to the account's role.
3. A staff report, faculty absence or event is checked against booked sessions and campus dependencies.
4. The recovery engine ranks eligible plans. A scenario displays hypothetical results, while an official case follows the configured review policy.
5. Publication checks the pending plan against the current timetable and policy, applies changes in one transaction, then updates the version, inboxes and audit log.
6. The workspace polls for refreshed data and shows the published assignments to the affected accounts.

See the [system and recovery diagrams](docs/architecture.md).

## Screens and routes

| Screen | Route | Who uses it |
| --- | --- | --- |
| Overview | `/` | All roles, with role-specific metrics |
| Timetable | `/timetable` | All roles, with personal or campus views according to access |
| Digital twin | `/twin` | Admin, HOD and Operator |
| Scenario Lab | `/scenarios` | Admin, HOD and Operator |
| Recovery Studio | `/recovery` | Admin, HOD and Operator |
| Incident Center | `/incidents` | Admin, HOD, Faculty and Operator |
| Substitute requests | `/substitutions` | Faculty |
| Resources and Analytics | `/resources`, `/analytics` | Admin, HOD and Operator |
| College events and Notifications | `/events`, `/notifications` | All roles, with account- or department-scoped data |
| Audit history and Settings | `/audit`, `/settings` | Admin |

The backend serves [interactive API docs](http://127.0.0.1:8000/docs) when running locally. The [API guide](docs/api.md) describes access and request formats.

## Data model

| Records | Purpose |
| --- | --- |
| `resources` and `resource_dependencies` | Faculty, rooms, infrastructure, cohorts and the dependencies between them |
| `academic_sessions` | Dated subject, instructor, room and cohort assignments |
| `users`, `account_profiles`, `student_enrollments` and `auth_sessions` | Portal identities, access scope and sign-in sessions |
| `incidents`, `recovery_plans` and `substitution_requests` | Impact analysis, proposed schedules and substitute consent |
| `college_events` and `leave_requests` | Event scheduling and faculty availability workflows |
| `institution_state`, `notifications` and `audit_logs` | Timetable version, policy, messages and decision history |

The connected [OMNIS-X Supabase project](https://supabase.com/dashboard/project/wwzockububqslawmsrkv/database/tables?schema=omnisx) also contains the private `student_roster` with 399 students in 12 batches, `timetable_reference_pages` with six section grids and 54 course assignments, and a `student_timetable` view that joins roster batches to published sessions. The source import is separate from portal account creation. The individual PEC and AEC allocations require their separate readable source files.

## Recovery behavior

The optimizer prioritizes the number of covered sessions. It then minimizes the configured costs of delay, room changes and instructor substitutions. Candidate checks include room capacity, equipment, faculty qualifications, workload, bookings, outages and reservations. Protected sessions retain their scheduled date and time. The [architecture guide](docs/architecture.md#recovery-pipeline) explains the search horizon, validation and publication rules.

## Build and test commands

For frontend development, start the backend in one PowerShell terminal.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start Vite from the repository root in a second terminal. It proxies `/api` to the local FastAPI process.

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

From `frontend`, run `npm.cmd run build` for a production build and `npm.cmd test` for UI unit tests. Backend and full browser-suite commands are in the [verification guide](docs/verification.md).

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The local page or API does not open | Confirm that FastAPI started on port 8000 and that the frontend was built or Vite is running. |
| Supabase Tables shows zero tables | Open the schema-specific link above or select `omnisx` in the schema dropdown. |
| A future week is empty | Check whether sessions were published for that date. **Demo week** returns to the seeded schedule. |
| A browser tab was open during a rebuild | Reload the tab to fetch the current frontend assets. The app also offers a reload action after an asset-load failure. |
| A recovery plan is stale | Refresh the incident and generate alternatives from the current timetable. |

## Contributors

- [ssinchanagn@gmail.com](mailto:ssinchanagn@gmail.com)
- [NaveenCB25](https://github.com/NaveenCB25)

