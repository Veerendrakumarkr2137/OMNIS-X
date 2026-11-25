# OMNIS-X API

FastAPI generates [interactive API documentation](http://127.0.0.1:8000/docs) and an [OpenAPI document](http://127.0.0.1:8000/openapi.json) while the backend is running. **Staff** means Admin, HOD and Operator. Department-head requests are limited by department scope.

## Authentication

| Method and route | Behavior |
| --- | --- |
| `GET /api/config` | Returns demo flags, including whether the IIET batch guest accounts are configured. |
| `POST /api/auth/login` | Accepts `username`, `password` and optional `remember` and `portal`. The username field accepts a login ID or institutional email. A successful login sets `omnis_session`. |
| `GET /api/auth/me` | Returns the current identity and its profile and registration information. |
| `POST /api/auth/password` | Accepts `current_password` and `password`. The new password requires 12 or more characters. It revokes the account's prior sessions. |
| `POST /api/auth/logout` | Revokes the session and clears its cookie. |

The optional `portal` value must match the authenticated role when supplied. Its possible values are `Admin`, `HOD`, `Faculty`, `Student` and `Operator`. Use the same origin for cookie-authenticated writes. API responses specify `Cache-Control: no-store`.

## Timetable, workspace and resources

| Method and route | Access and behavior |
| --- | --- |
| `GET /api/dashboard` | Authenticated. Returns role information, campus date, version, names and disruption metadata. |
| `GET /api/analytics/resilience?day=YYYY-MM-DD` | Staff. Returns `day`, `sessions`, `score`, `factors` and `risks` for the selected date. |
| `GET /api/timetable`, `GET /api/timetable/me`, `GET /api/faculty/me/timetable` | Aliases for the signed-in role's published schedule. Faculty see their own assignments. Students see eligible section and batch sessions, filtered by explicit course registrations when present. |
| `GET /api/timetable/shared` | Admin, HOD, Faculty and Operator. Returns `sessions`, `assignment_names` and `disrupted_sessions`. HOD receives department sessions. Faculty can read campus bookings. |
| `GET /api/timetable/version` | Authenticated. Returns timetable version, state revision and seed anchor. |
| `POST /api/timetable` | Admin. Publishes a validated session with the ID, date, subject, department, instructor, room, cohort and time. |
| `GET /api/resources`, `GET /api/resources/{id}` | Authenticated. Returns resources within the account's role and assignment scope. |
| `POST /api/resources`, `PUT /api/resources/{id}` | Admin. Creates or edits validated resource profiles. |
| `GET /api/faculty`, `GET /api/faculty/availability` | Staff. Returns faculty and visible unavailability intervals. |
| `GET /api/faculty/substitutes?session_id=…` | Staff. Returns eligible substitute instructors for a visible session. |
| `GET /api/digital-twin`, `GET /api/dependencies` | Staff. Returns scoped `nodes` and `edges`. Edges have `source`, `target` and `rule`. The web client adds links for the selected day's sessions. |

Dates are ISO `YYYY-MM-DD`. Times are minutes after midnight. Intervals include the start and exclude the end. The interval `630–690` means 10:30–11:30, and `1440` is valid as an end time. Timetable Day and Week views filter dated session records in the client.

## Incidents, simulations and recovery

| Method and route | Access and behavior |
| --- | --- |
| `GET /api/incidents`, `GET /api/incidents/{id}` | Official records within the staff account's scope or the Faculty account's own reports. |
| `POST /api/incidents`, `POST /api/resources/outage` | Staff. Reports an official outage and analyzes its impact. |
| `GET /api/simulations`, `GET /api/simulations/{id}`, `POST /api/simulations` | Staff. Opens or runs a hypothetical scenario. |
| `POST /api/faculty/absence` | Faculty. Reports unavailability for the signed-in instructor. Optional `end_day` spans up to 31 dates and creates one incident per day. The response represents the first incident. |
| `POST /api/faculty/issues` | Faculty. Reports an issue in a room assigned to the instructor during the requested interval. |
| `POST /api/recovery/generate` | Staff. Takes `case_id` and generates alternatives for a visible unsettled case. |
| `GET /api/recovery/plans`, `GET /api/recovery/plans/{id}` | Staff. Lists or opens visible plans. Filter with `?case_id={id}` to see a particular case, including a simulation. |
| `POST /api/recovery/plans/{id}/recommend` | HOD or Operator. Recommends a pending official plan to the administrator. |
| `POST /api/recovery/plans/{id}/request-consent` | Staff. Requests consent from proposed substitutes for a current official plan under the consent policy. |
| `GET /api/faculty/substitutions`, `POST /api/faculty/substitutions/{id}` | Faculty. Views or answers requests for the linked instructor. Send `decision` with `Accepted` or `Declined`. |
| `POST /api/recovery/plans/{id}/approve`, `POST /api/recovery/plans/{id}/apply` | Admin or delegated HOD. Both aliases use the same publication transaction. |
| `POST /api/recovery/plans/{id}/reject` | Admin or delegated HOD. Rejects a pending official plan. |

Use this payload shape for a resource outage or simulation. The root ID in the example belongs to the IIET demo.

```json
{
  "day": "2026-11-23",
  "start": 480,
  "end": 600,
  "roots": ["l0"],
  "title": "Web lab outage",
  "severity": "High",
  "reason": "Equipment unavailable"
}
```

Faculty absence requests use `day`, `start`, `end`, optional `end_day` and optional `reason`. A multi-date request spans the selected start time on the first date through the selected end time on the last date. Approval checks reviewer scope, consent, revision and the current schedule. A stale or invalid plan returns `409`. Refresh the case and generate new alternatives before retrying.

## Events, accounts and administration

| Method and route | Access and behavior |
| --- | --- |
| `GET /api/events` | Authenticated. Returns visible events with role-appropriate details. |
| `GET /api/events/students` | Admin or HOD. Lists active portal students eligible for event selection. |
| `POST /api/events` | Admin or HOD. Creates a scoped event with `name`, `day`, `start`, `end` and optional `end_day`. The span is up to seven consecutive dates. Institution-wide events require Admin. |
| `POST /api/faculty/leave` | Faculty. Requests leave for a single date and interval. |
| `GET /api/leave`, `POST /api/leave/{id}/{decision}` | Faculty list their own requests. Admin and HOD review in-scope requests using `approve` or `decline`. |
| `GET /api/notifications`, `PATCH /api/notifications/{id}/read`, `POST /api/notifications/read-all` | Authenticated. Reads or updates the account's own inbox. |
| `GET /api/users`, `POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/password` | Admin. Manages portal identities, profiles and password resets. |
| `POST /api/users/import` | Admin. Imports accounts, department and cohort records, and timetable sessions. |
| `GET /api/settings`, `PATCH /api/settings` | Admin. Reads or updates recovery policy. Start from current editable values when making a partial policy change because omitted fields can take model defaults. |
| `GET /api/audit` | Admin. Reads recorded actions and associated case IDs. |

## CSV and XLSX import

In the portal, open **Settings → Campus accounts**. For API calls, send JSON containing `filename` and `content`, with the file bytes encoded in base64. Use a UTF-8 CSV or one XLSX worksheet, with 1–500 records. Keep IDs with leading zeros in text cells. The whole upload rolls back on an invalid or duplicate row.

| Record | Fields |
| --- | --- |
| Department | `record=department` and `name`. |
| Cohort | `record=cohort`, `name`, `dept` and optional `capacity`. Assign batches to sections in Resources. |
| Account | `username`, `name`, `role` and `password`, with optional `email` and role-specific `dept` and `resource`. Passwords require 12 or more characters. |
| New faculty | Leave `resource` blank and provide `subjects` separated by the pipe character. |
| Student | Use a cohort ID in `resource` or the exact `cohort` name with `dept`. Optional profile columns include `semester`, `section` and `batch`. |
| Student registrations | Put exact subject names in the pipe-separated `enrollments` column. Append `:PCC`, `:AEC` or `:Elective` to specify a category. The default is Core. An explicitly blank enrollment field registers zero courses. Omitting the column keeps the cohort schedule. |
| Session | `record=session`, `id`, `day`, `subject`, `dept`, `faculty`, `room`, `cohort`, `start`, `duration` and `kind`. Optional `needs` uses the pipe separator, and `protected` locks the date and time during recovery. |

The private PDF-backed roster and timetable references are available to project administrators in the Supabase dashboard. The [architecture guide](architecture.md#data-model) documents their relationship to the portal's operational tables.

