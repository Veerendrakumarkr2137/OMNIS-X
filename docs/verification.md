# Verification record

Executed on Windows on November 25, 2026, using Python 3.14, Node.js 22.23.1, SQLite and locally installed Chrome. Every backend fixture used an isolated database. The browser suite started its own disposable FastAPI server and served the built frontend.

| Check | Observed result |
| --- | --- |
| Python API, solver and persistence suite | 21 passed in 79.93 seconds |
| Vitest and React Testing Library | 3 passed |
| Playwright desktop and mobile suite | 4 passed in 36.2 seconds |
| TypeScript and Vite production build | Completed successfully |
| Live localhost smoke check | HTTP 200 for the application, OpenAPI document available, demo enabled |

**28 automated tests passed.**

The backend suite exercises all five logins, logout, departmental and owner isolation, full- and partial-day absence, automatic generation, qualification, equipment, capacity, intervals, cohort and faculty bookings, daily and consecutive workloads, inter-building travel, simultaneous failures, partial and infeasible recovery, distinct ranked alternatives, stale and repeated approval, independent plan validation, atomic publication, targeted notifications, simulation isolation, persistence after restart, consent, manual and automatic policies, explicit HOD approval, concurrent approval and safe directory edits.

The browser tests rapidly switched among all five roles, submitted a faculty absence, approved its plan as administrator and verified the student's revised timetable and private-reason exclusion. At a 390-pixel viewport they opened the navigation drawer, simulated a power cascade and checked for horizontal overflow. The administration flow edited room capacity, inspected the audit entry, opened the weekly calendar and changed the theme. Desktop login, desktop dashboard and mobile dashboard renders were visually inspected.

The final backend run emitted one upstream Starlette deprecation warning for its HTTPX test client. Vite reported a large entry-chunk advisory and removed two dependency annotations during bundling. These checks returned successful exit codes. The verification covers local SQLite and Chrome. Cloud deployment, PostgreSQL, Safari, Firefox and operational load testing remain unverified.

