# Five-minute demonstration

Use a fresh demo database. The first seeded day defaults to the date the database was initialized. The five-day timetable stays anchored to that date when you reopen the application.

1. Select **Faculty** on the login screen. Mira Shah has two sessions on the first demo day. Click **Report absence**, keep **Full day** selected and submit. The result shows two affected sessions and 60 students across two fictional cohorts.
2. Sign out through the account menu. Select **HOD**. The incident center shows the CSE absence and the department's recovery alternatives. Recommend an alternative. Departmental approval is disabled by default.
3. Select **Admin** and open **Recovery studio**. Choose **Mira Shah absence**. Check the ranked alternatives and open **View details** to inspect the original and proposed faculty, room and time. Approve the first alternative and confirm publication.
4. Select **Student**. Open **Timetable** for the revised Algorithms assignment and **Notifications** for the old and new details. Return as Faculty to see Mira's updated schedule. Concurrent open workspaces refresh every five seconds. Separate browser profiles allow different roles to stay signed in.
5. Select **Operator**, open **Scenario lab**, choose **Building power failure** and run impact analysis. Inspect the graph and dependency depths. Compare plans, then return to the official timetable to check the publication version.
6. Choose **No backup laboratory** to take both compatible CSE labs offline during the protected exam. Inspect the blocking resources and unresolved session. **Multiple failures** exercises simultaneous faculty and infrastructure disruption.

## Additional demonstrations

- **Manual planning** in Settings records the outage and waits for a reviewer to generate alternatives. **Assisted** generates immediately. **Automatic** may publish complete room-only recoveries with zero delay and a penalty within the administrator's limit.
- **Consent** in Settings requires substitutes to accept before an official plan can be applied. Use **Request / check consent** in Recovery Studio. For a live demonstration, add a Faculty account linked to the proposed lecturer in Settings, sign in as that lecturer, then open **Substitute requests**.
- **Stale proposals** can be demonstrated by creating an incident, generating alternatives, then changing a policy weight. Regenerate the earlier case before approval.
- **Administration** supports adding departments, buildings, classrooms, laboratories, faculty, cohorts and accounts. Editing capacity or faculty availability that would invalidate an existing published session returns a conflict.

## Repeat with a fresh campus

Choose a new SQLite file with DATABASE_URL before starting the server. An empty database initializes automatically. Keep the previous file to retain its decisions and audit history.

