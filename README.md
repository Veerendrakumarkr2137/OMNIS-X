# OMNIS-X

OMNIS-X is a campus operations portal for publishing timetables, tracing campus dependencies and recovering teaching sessions after disruptions. Students see their section, batch and registered courses. Faculty see their own assignments and can report absences. Department heads, administrators and operations staff use separate workspaces to review resources, incidents and recovery options.

| Guide | What it covers |
| --- | --- |
| [Architecture](docs/architecture.md) | System design, data model, role boundaries, recovery and resilience |
| [API](docs/api.md) | Routes, request formats, access rules and institutional import |
| [Demo walkthrough](docs/demo-guide.md) | Student batches, faculty absence, recovery, Digital twin and Supabase table navigation |
| [Verification](docs/verification.md) | Reproducible checks, observed results and remaining coverage |

## Start the portal

Use Python 3.11 or later with pip. For frontend development or a fresh frontend build, use Node.js 22.12 or later with npm. The launchers bind to localhost, install Python dependencies and build the frontend if `frontend/dist/index.html` is missing. Initial dependency installation requires internet access.

On Windows, run the launcher from the project directory.

```bat
scripts\start_windows.bat
```

On Linux or macOS, run the shell launcher.

```sh
bash scripts/start_linux.sh
```

Open [OMNIS-X](http://127.0.0.1:8000). The built frontend and API are served from the same origin. In development, install the backend dependencies in a virtual environment, start the API, then run Vite in a second terminal.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Vite prints its local URL and proxies `/api` to port 8000. Run `npm.cmd run build` in `frontend` to type-check and build assets for FastAPI.

## Choose a database

FastAPI reads process environment variables and fills unset values from the ignored root `.env` file. See [environment examples](.env.example) for the variable names.

| Setting | Behavior |
| --- | --- |
| `DATABASE_URL` | Selects the SQLite file or PostgreSQL instance. The local default is `backend/omnis-iiet.db` in IIET demo mode, and `backend/omnis.db` otherwise. |
| `OMNIS_DEMO` | Defaults to `1` and enables local guest access. With `0`, new databases use the environment-provisioned administrator and secure cookies. |
| `OMNIS_DEMO_DATASET` | `iiet` is the portal default. `meridian` selects the fictional campus fixture. |
| `OMNIS_DEMO_DATE` | Sets the seed date when initializing a new database. IIET anchors to Monday in the selected week. |
| `OMNIS_ADMIN` and `OMNIS_ADMIN_PASSWORD` | Required when initializing a fresh non-demo database. The initial password must contain at least 12 characters. |

### Local SQLite

On first launch the IIET fixture supplies CSE Semester V schedules for Sections A–F, B1 and B2 guest students, fictional ECE records, and sample incidents. Data persists across restarts. For a clean demo, point `DATABASE_URL` at a new SQLite file and select a seed date before launch. To initialize a configured database without serving the UI, run `python scripts/seed_database.py` from the backend environment.

### Supabase PostgreSQL

The connected OMNIS-X Supabase project stores operational data in the private `omnisx` schema. Open the schema-specific link to see the tables directly. [OMNIS-X database tables](https://supabase.com/dashboard/project/wwzockububqslawmsrkv/database/tables?schema=omnisx).

- `omnisx.student_roster` contains 399 CSE Semester V student records for 12 batches in Sections A–F.
- `omnisx.timetable_reference_pages` contains six source timetable grids and 54 course assignments.
- `omnisx.student_timetable` joins the roster to published section and batch sessions. The individual PEC and AEC updates require readable copies of their separate source PDFs.

For an existing configured project, use its **Session pooler** connection details with the dedicated `omnisx_app` database login. Keep `DATABASE_URL` in the backend environment or root `.env`. Use certificate verification and the [bundled CA file](backend/supabase-root.crt) when appropriate for the project's connection details. URL-encode the password and query parameter values. [Supabase Postgres connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

```dotenv
DATABASE_URL=postgresql+psycopg://omnisx_app.PROJECT_REF:URL_ENCODED_PASSWORD@SESSION_POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=ABSOLUTE_CA_PATH
```

For a fresh Supabase deployment, generate the application schema with `python scripts/supabase_schema.py` and apply its SQL as a PostgreSQL administrator. Provision the generated dedicated role for password login using the project's secure administration tools. The schema generator covers the operational ORM tables. The imported roster, reference grids and timetable view belong to the connected project's separate data migration.

For a SQLite cutover, stop the source writer, retain a backup and provision an empty target. Configure `DATABASE_URL` and run `python scripts/migrate_sqlite_to_supabase.py backend/omnis-iiet.db` before starting FastAPI against that target. The copy runs in a transaction, checks table counts and omits active authentication sessions. Users sign in again after the cutover.

## Workspaces

| Workspace | Typical work |
| --- | --- |
| Administrator | Campus view, accounts and imports, resource directory, policy, recovery approval and audit |
| Department head | Department timetable, incident review, leave and events, and delegated approval when policy permits |
| Faculty | Personal teaching timetable, read-only campus bookings, absence reports, leave, room issues and substitute requests |
| Student | Section- and batch-scoped timetable, registered courses, college events and notifications |
| Operations | Campus bookings, infrastructure reports, Digital twin, simulations and plan recommendations |

On a local demo sign-in screen, choose a guest role. Under **Student Access**, choose **Batch B1 demo** or **Batch B2 demo**. The portal authenticates the account and checks the selected role when a role-specific sign-in is used. See the [demo guide](docs/demo-guide.md) for a step-by-step run.

## Repository map

| Location | Contents |
| --- | --- |
| [frontend/src](frontend/src) | React, TypeScript, routes, role views, React Query polling, React Flow and Recharts |
| [backend/app](backend/app) | FastAPI, Pydantic, SQLAlchemy, authentication, timetable, imports and publication |
| [backend/app/engine](backend/app/engine) | NetworkX dependency analysis, constraint checks, OR-Tools CP-SAT search and ranking |
| [backend/tests](backend/tests) and [frontend/e2e](frontend/e2e) | API, persistence, solver and browser coverage |
| [scripts](scripts) | Startup, initialization, Supabase schema generation, SQLite migration and browser test server |

The [verification guide](docs/verification.md) contains the backend, frontend, build and browser commands. The packaged demonstration is a loopback deployment. A hosted installation needs HTTPS, environment-specific secret management and its own operational validation.

