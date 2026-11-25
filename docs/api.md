# API guide

Run the backend and open [interactive API documentation](http://127.0.0.1:8000/docs) or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json). The generated documentation contains the method, payload and response for each implemented route.

| Area | Main entry points |
| --- | --- |
| Authentication | POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout |
| Timetables | GET /api/timetable, /api/timetable/me, /api/timetable/version |
| Absence and consent | POST /api/faculty/absence, GET /api/faculty/substitutions, POST /api/faculty/substitutions/{id} |
| Incident reporting | GET or POST /api/incidents, GET /api/incidents/{id} |
| Simulations | GET or POST /api/simulations, GET /api/simulations/{id} |
| Digital twin | GET /api/digital-twin, /api/dependencies |
| Resources | GET or POST /api/resources, GET or PUT /api/resources/{id} |
| Recovery | POST /api/recovery/generate, GET /api/recovery/plans?case_id={id} |
| Review | POST /api/recovery/plans/{id}/recommend, /request-consent, /reject, /approve or /apply |
| Inbox | GET /api/notifications, PATCH /api/notifications/{id}/read, POST /api/notifications/read-all |
| Administration | GET /api/dashboard, /api/audit, GET or POST /api/users, GET or PATCH /api/settings |

A failure request contains a date in ISO format, start and end minutes after midnight, root resource identifiers, title, severity and optional notes. A faculty absence uses the signed-in faculty identity and accepts only the interval and optional private reason. Intervals use an inclusive start and exclusive end.

Approval and application are a single atomic operation. Both route aliases enforce the same authorization, version, consent and validity checks. Clients should refresh after a 409 response. Repeated approval cannot publish twice.

