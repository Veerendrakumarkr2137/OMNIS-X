# Architecture

The React client and FastAPI API share an origin in the built demo. During development Vite forwards API requests to the backend. The client polls its role-scoped workspace snapshot every five seconds and refreshes immediately after a mutation.

## Official state and simulation state

SQLAlchemy stores typed resources, dependency edges, academic sessions, users, expiring authentication sessions, incidents, recovery plans, substitute consent, notifications, audit events and a versioned campus policy. Resource attributes and immutable proposed assignments use JSON columns. Faculty absences and infrastructure outages are interval-based incidents. Hypothetical cases carry a simulation flag. They do not contribute to official outages, change the timetable version, or send real incident notifications.

Each session references its faculty, room and cohort. Cohorts have disjoint fictional rosters represented by counts. Impact counts each affected cohort once. Student-session counts sum attendance across affected sessions.

## Recovery

1. Intersect the reported interval with the academic sessions on that date. NetworkX traverses directed, mandatory dependencies from each failed resource. Building power outages reach the building and its rooms. Network outages affect connected laboratories. A faculty absence reaches only that faculty member's actual sessions.
2. Generate same-day candidates in half-hour increments starting at the original time. Exams keep their protected start time. Check subject expertise, department, daily availability, teaching limits, capacity, equipment, room type and every recorded outage.
3. CP-SAT selects one assignment or one unresolved marker per affected session. Optional intervals enforce room, cohort and faculty exclusivity. Daily workload includes unaffected bookings.
4. The objective weights each unresolved session more heavily than the sum of the maximum possible placement penalties. Among solutions with equal coverage it minimizes student-minutes delayed, room changes and substitutions using the configured weights.
5. An independent validator rebuilds the proposed schedule. It checks preserved duration, intervals, protected times, workloads, consecutive teaching and inter-building travel. Combinations that fail the independent checks are excluded and the solver searches again. The solver also excludes each returned assignment tuple before finding another alternative. Plans display the solver's actual optimal or feasible status. The solver search has an eight-second budget per generation.
6. The authenticated administrator, an explicitly delegated HOD or a qualifying automatic policy publishes a current official plan. Optional consent requires each proposed substitute to accept the selected plan. Approval rechecks the entire assignment against fresh data.
7. A compare-and-swap on the campus revision serializes official changes. The same database transaction writes the lessons, increments the timetable version, settles the incident, supersedes alternatives, delivers notifications and records the actor. Failed transactions roll back. New official incidents, resource changes and policy edits can invalidate earlier proposals.

## Resilience calculation

The score is the rounded, equal-weight average of measured component percentages. The dashboard shows each component individually.

| Factor | Measurement |
| --- | --- |
| Room redundancy | Share of scheduled sessions with two or more equipment-, type- and capacity-compatible spaces |
| Qualified backup | Share with another subject-qualified faculty member in the department |
| Schedule compliance | Share free of modeled capacity, equipment, booking and workload violations |
| Recovery success | Completely recovered incidents divided by settled or intervention-required incidents |
| Independent power | Share of teaching spaces with modeled power that have more than one upstream supply |

A component with no observations is omitted from the mean. Structural backup measurements describe alternatives in the inventory. The recovery engine checks their availability at the actual time before making an assignment.

## Security and scope

Opaque random authentication tokens are stored as SHA-256 digests. Passwords use Argon2. The browser holds an HTTP-only, SameSite=Strict session cookie. Standard sessions expire after eight hours and remembered sessions after seven days. Non-demo cookies require HTTPS. Same-origin write checking complements cookie protection. The server checks each user's identity, role, department and record ownership.

Demo scripts bind to loopback. Demo mode permits local hostnames and publishes five synthetic credentials. A separate non-demo database starts with an environment-provisioned administrator and an empty directory. Public production deployment requires a separate operational review.

