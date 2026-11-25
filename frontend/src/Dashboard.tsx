import {
  ArrowRight,
  ArrowUpRight,
  Boxes,
  CalendarDays,
  CheckCheck,
  ChevronRight,
  CircleAlert,
  GitPullRequest,
  Activity,
  Radar,
  Users,
  Layers3,
  Building2,
  CalendarClock,
  ShieldCheck,
  Plus,
  Network,
  ChevronLeft,
  RefreshCw,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { CampusArt, Empty, Pill } from "./ui";
import { useResilience } from "./useResilience";
import { useEvents } from "./Events";
import {
  pretty,
  privileged,
  selectedDay,
  shiftDay,
  time,
  type Campus,
} from "./types";
export const headings = {
  Admin: "Institutional Command Center",
  HOD: "Department Command Center",
  Operator: "Campus Operations Center",
  Faculty: "My Teaching Workspace",
  Student: "My Academic Workspace",
};
export function DashboardPage({
  c,
  report,
  refreshedAt,
  refreshing,
  stale,
}: {
  c: Campus;
  report: () => void;
  refreshedAt: number;
  refreshing: boolean;
  stale: boolean;
}) {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const staff = privileged(c.user);
  const day = selectedDay(params.get("day"), c.dash.today);
  const resilience = useResilience(c.user, day);
  const events = useEvents(c.user.id);
  const analyticsLink = "/analytics?day=" + day;
  const setDay = (value: string) => setParams({ day: value });
  const dayRows = c.lessons.filter((s) => s.day === day);
  const upcoming = c.lessons.find(
    (s) => s.day > day && s.status !== "Unresolved",
  );
  const affected = new Set(c.dash.disrupted_sessions);
  const needsCoverage = (s: (typeof dayRows)[number]) =>
    s.status === "Unresolved" || affected.has(s.id);
  const active = c.cases.filter(
    (x) =>
      x.day <= day &&
      day <= (x.impact.end_day || x.day) &&
      !["Recovered", "No impact"].includes(x.status),
  );
  const pending = active.filter((x) => x.status === "Pending review");
  const currentPlans = new Set(
    c.plans
      .filter((p) => p.status === "Pending" && p.revision === c.dash.revision)
      .map((p) => p.case_id),
  );
  const ready = pending.filter((x) => currentPlans.has(x.id)).length;
  const rooms = c.resources.filter((x) =>
    ["Classroom", "Laboratory"].includes(x.kind),
  );
  const failed = new Set(c.dash.outage_resources?.[day]);
  const faculty = c.resources.filter((x) => x.kind === "Faculty");
  const chart = Array.from({ length: 7 }, (_, i) => {
    const date = shiftDay(day, i);
    const sessions = c.lessons.filter((s) => s.day === date);
    return {
      date,
      day: pretty(date),
      Sessions: sessions.length,
      Covered: sessions.filter((s) => !needsCoverage(s)).length,
    };
  });
  const timetable = "/timetable?day=" + day;
  const stats = staff
    ? [
        {
          label: "Faculty without reported absence",
          value: faculty.filter((r) => !failed.has(r.id)).length,
          detail: "of " + faculty.length + " faculty",
          icon: Users,
          path: "/resources?type=Faculty&day=" + day,
          cls: "teal",
        },
        {
          label: "Teaching spaces without outages",
          value: rooms.filter((r) => !failed.has(r.id)).length,
          detail:
            rooms.filter((r) => r.kind === "Laboratory" && !failed.has(r.id))
              .length +
            " of " +
            rooms.filter((r) => r.kind === "Laboratory").length +
            " laboratories",
          icon: Building2,
          path: "/resources?type=Teaching+spaces&day=" + day,
          cls: "purple",
        },
        {
          label: "Open incidents",
          value: active.length,
          detail:
            dayRows.filter(needsCoverage).length + " sessions need coverage",
          icon: CircleAlert,
          path: "/incidents?day=" + day,
          cls: "amber",
        },
        {
          label: "Awaiting review",
          value: pending.length,
          detail:
            ready +
            " ready · " +
            (pending.length - ready) +
            " need recalculation",
          icon: GitPullRequest,
          path: pending.length
            ? "/recovery?case=" + pending[0].id
            : "/recovery",
          cls: "blue",
        },
      ]
    : [
        {
          label: "Sessions on selected day",
          value: dayRows.length,
          detail: dayRows.filter(needsCoverage).length + " need coverage",
          icon: CalendarDays,
          path: timetable,
          cls: "teal",
        },
        {
          label: "Exams on selected day",
          value: dayRows.filter((s) => s.kind === "Examination").length,
          detail: "In the published timetable",
          icon: Layers3,
          path: timetable + "&kind=Examination",
          cls: "purple",
        },
        {
          label: "Schedule updates",
          value: dayRows.filter((s) => s.previous).length,
          detail: "Published changes",
          icon: CalendarClock,
          path: timetable,
          cls: "blue",
        },
        {
          label: "Unread updates",
          value: c.notices.filter((n) => !n.seen).length,
          detail: "In your notification center",
          icon: Activity,
          path: "/notifications",
          cls: "amber",
        },
      ];
  return (
    <>
      <section className="hero">
        <div className="hero-text">
          <div className="eyebrow mint">
            <span className="line" />
            {c.user.dept ? c.user.dept + " DEPARTMENT" : "CAMPUS OPERATIONS"}
          </div>
          <h1>{headings[c.user.role]}</h1>
          <p>
            {c.user.name}
            {c.user.profile?.designation && " · " + c.user.profile.designation}
          </p>
          <p>
            {staff
              ? "Monitor operational health, anticipate failures and coordinate intelligent recovery."
              : "Your sessions, schedule changes and campus notifications in one place."}
          </p>
          <div className="actions">
            {staff ? (
              <>
                <button
                  className="accent"
                  onClick={() =>
                    nav("/scenarios" + (params.has("day") ? "?day=" + day : ""))
                  }
                >
                  <Radar size={16} />
                  Run simulation
                </button>
                <button className="hero-link" onClick={() => nav("/recovery")}>
                  View recovery plans <ArrowUpRight size={15} />
                </button>
              </>
            ) : (
              <button
                className="accent"
                onClick={
                  c.user.role === "Faculty" ? report : () => nav(timetable)
                }
              >
                {c.user.role === "Faculty" ? (
                  <Plus size={15} />
                ) : (
                  <CalendarDays size={15} />
                )}{" "}
                {c.user.role === "Faculty"
                  ? "Report absence"
                  : "View timetable"}
              </button>
            )}
          </div>
        </div>
        <CampusArt />
      </section>
      <div className="sectionline">
        <div>
          <div className="eyebrow">WORKSPACE OVERVIEW</div>
          <h2>{staff ? "Campus at a glance" : "My schedule at a glance"}</h2>
        </div>
        <div className="overview-date">
          <button
            className="icon"
            aria-label="Previous dashboard day"
            onClick={() => setDay(shiftDay(day, -1))}
          >
            <ChevronLeft size={16} />
          </button>
          <input
            type="date"
            aria-label="Dashboard date"
            value={day}
            onChange={(e) => {
              if (e.target.value) setDay(selectedDay(e.target.value, day));
            }}
          />
          <button
            className="icon"
            aria-label="Next dashboard day"
            onClick={() => setDay(shiftDay(day, 1))}
          >
            <ChevronRight size={16} />
          </button>
          {day !== c.dash.today && (
            <button className="secondary" onClick={() => setDay(c.dash.today)}>
              Today
            </button>
          )}
          {c.dash.demo && day !== c.dash.anchor && (
            <button className="secondary" onClick={() => setDay(c.dash.anchor)}>
              {c.dash.demo_profile ? "Demo Monday" : "Demo day"}
            </button>
          )}
        </div>
      </div>
      <div className="overview-sync">
        <span>
          {stale ? "Showing the last successful update" : "Last synced"} ·{" "}
          <time dateTime={new Date(refreshedAt).toISOString()}>
            {new Date(refreshedAt).toLocaleTimeString()}
          </time>{" "}
          · Timetable v{c.dash.version}
        </span>
        <button
          className="textbtn"
          disabled={refreshing}
          onClick={() => void c.refresh()}
        >
          <RefreshCw size={14} />
          {refreshing ? "Refreshing…" : "Refresh now"}
        </button>
      </div>
      <div className="stats">
        {stats.map((s) => (
          <button key={s.label} className="stat" onClick={() => nav(s.path)}>
            <span className={"tile-icon " + s.cls}>
              <s.icon size={18} />
            </span>
            <ArrowUpRight className="corner" size={15} />
            <span>{s.label}</span>
            <strong>{String(s.value).padStart(2, "0")}</strong>
            <small>{s.detail}</small>
          </button>
        ))}
      </div>
      {["Faculty", "Student", "HOD"].includes(c.user.role) && (
        <div className="dash-row">
          <section className="panel">
            <h3>
              {c.user.role === "HOD"
                ? "Department teaching"
                : c.user.role === "Faculty"
                  ? "My teaching assignments"
                  : "My academic registration"}
            </h3>
            {c.user.role === "HOD" && (
              <p>
                {c.dash.department_summary?.students ?? 0} student accounts ·{" "}
                {faculty.length} faculty ·{" "}
                {faculty.filter((r) => failed.has(r.id)).length} with reported
                absence · {c.dash.department_summary?.pending_leave ?? 0}{" "}
                pending leave
              </p>
            )}
            {c.user.role === "Faculty" && c.dash.teaching_profile && (
              <p>
                {dayRows.reduce((total, s) => total + s.duration, 0)} teaching
                minutes on this date · Daily workload limit{" "}
                {c.dash.teaching_profile.limit} minutes ·{" "}
                {failed.has(c.user.resource || "") ||
                c.cases.some(
                  (x) =>
                    x.day === day && x.roots.includes(c.user.resource || ""),
                )
                  ? "Absence reported"
                  : "No absence reported"}{" "}
                · Availability{" "}
                {c.dash.teaching_profile.available.map(time).join("–")}
              </p>
            )}
            {c.user.role === "Student" && (
              <p>
                {[
                  c.user.dept,
                  c.user.profile?.semester &&
                    "Semester " + c.user.profile.semester,
                  c.user.profile?.section &&
                    "Section " + c.user.profile.section,
                  c.user.profile?.batch,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
            <div className="row">
              <div className="grow">
                <b>{c.user.role === "Student" ? "Courses" : "Subjects"}</b>
                <small>
                  {[...new Set(c.lessons.map((s) => s.subject))]
                    .map(
                      (subject) =>
                        subject +
                        (c.user.enrollments?.[subject]
                          ? " · " + c.user.enrollments[subject]
                          : ""),
                    )
                    .join(", ") || "No sessions assigned"}
                </small>
              </div>
            </div>
            {c.user.role !== "Student" && (
              <div className="row">
                <div className="grow">
                  <b>Sections and batches</b>
                  <small>
                    {[...new Set(c.lessons.map((s) => c.name(s.cohort)))].join(
                      ", ",
                    ) || "No sections assigned"}
                  </small>
                  <small>
                    {dayRows.reduce((total, s) => total + s.duration, 0)}{" "}
                    scheduled teaching minutes ·{" "}
                    {
                      dayRows.filter(
                        (s) => s.status === "Unresolved" || affected.has(s.id),
                      ).length
                    }{" "}
                    sessions need makeup or coverage
                  </small>
                </div>
              </div>
            )}
            {c.user.role === "Student" &&
              Object.entries(c.user.enrollments || {})
                .filter(
                  ([subject]) => !c.lessons.some((s) => s.subject === subject),
                )
                .map(([subject, category]) => (
                  <small key={subject}>
                    {subject} · {category} · Schedule pending
                  </small>
                ))}
            <button
              className="secondary"
              onClick={() => nav("/timetable?view=week&day=" + day)}
            >
              Weekly timetable
            </button>
            {c.user.role === "Faculty" && upcoming && (
              <div className="row">
                <div className="grow">
                  <b>Next scheduled class</b>
                  <small>
                    {upcoming.subject} · {pretty(upcoming.day)} ·{" "}
                    {time(upcoming.start)}
                  </small>
                </div>
              </div>
            )}
          </section>
          <section className="panel">
            <h3>
              {c.user.role === "Faculty" ? "Event duties" : "College events"}
            </h3>
            {events.data
              ?.filter((e) => e.end_day >= day)
              .slice(0, 3)
              .map((e) => (
                <div className="row" key={e.id}>
                  <div className="grow">
                    <b>{e.name}</b>
                    <small>
                      {pretty(e.day)} · {time(e.start)}–{time(e.end)}
                    </small>
                  </div>
                </div>
              ))}
            {events.data && !events.data.some((e) => e.end_day >= day) && (
              <Empty>No upcoming events for your account.</Empty>
            )}
            <div className="actions">
              <button className="secondary" onClick={() => nav("/events")}>
                View events
              </button>
              {c.user.role === "Faculty" && (
                <>
                  <button
                    className="secondary"
                    onClick={() => nav("/events?action=leave&day=" + day)}
                  >
                    Request leave
                  </button>
                  <button
                    className="secondary"
                    onClick={() => nav("/events?action=issue&day=" + day)}
                  >
                    Report room issue
                  </button>
                </>
              )}
            </div>
          </section>
        </div>
      )}
      {staff && (
        <div className="dash-row">
          <section className="panel">
            <div className="panel-head">
              <div className="smallhead">
                <Activity size={18} />
                <h3>Academic continuity</h3>
              </div>
              <span className="meta">7 days from {pretty(day)}</span>
            </div>
            <div className="chart-legend">
              <i /> Scheduled sessions <i /> Covered sessions
            </div>
            {chart.some((point) => point.Sessions) ? (
              <>
                <div className="chart">
                  <ResponsiveContainer width="100%" height={190}>
                    <AreaChart
                      data={chart}
                      margin={{ left: -24, right: 10, top: 14 }}
                    >
                      <defs>
                        <linearGradient id="fillT" x1="0" y1="0" x2="0" y2="1">
                          <stop
                            offset="0%"
                            stopColor="#20b99c"
                            stopOpacity=".3"
                          />
                          <stop
                            offset="100%"
                            stopColor="#20b99c"
                            stopOpacity=".02"
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        vertical={false}
                        strokeDasharray="3 4"
                        stroke="var(--border)"
                      />
                      <XAxis
                        dataKey="day"
                        tickFormatter={(label: string) => label.split(",")[0]}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 11, fill: "var(--muted)" }}
                      />
                      <YAxis
                        allowDecimals={false}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 11, fill: "var(--muted)" }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "var(--card)",
                          borderColor: "var(--border)",
                        }}
                      />
                      <Area
                        isAnimationActive={false}
                        dataKey="Sessions"
                        type="linear"
                        stroke="#9a88cf"
                        fill="transparent"
                        strokeDasharray="5 3"
                      />
                      <Area
                        isAnimationActive={false}
                        dataKey="Covered"
                        type="linear"
                        stroke="#16a68a"
                        fill="url(#fillT)"
                        strokeWidth={2.3}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div
                  className="continuity-days"
                  aria-label="Open a day's timetable"
                >
                  {chart.map((point) => (
                    <button
                      key={point.date}
                      className="secondary"
                      onClick={() => nav("/timetable?day=" + point.date)}
                      aria-label={
                        point.day +
                        ", " +
                        point.Covered +
                        " of " +
                        point.Sessions +
                        " sessions covered"
                      }
                    >
                      <small>{point.day}</small>
                      <b>
                        {point.Covered}/{point.Sessions}
                      </b>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <Empty>No published sessions in this seven-day period.</Empty>
            )}
          </section>
          <section className="panel" aria-label="Resilience overview">
            <div className="panel-head">
              <div className="smallhead">
                <ShieldCheck size={18} />
                <h3>Resilience overview</h3>
              </div>
              <span className="meta">{pretty(day)}</span>
              <button
                aria-label="See resilience analytics"
                className="icon"
                onClick={() => nav(analyticsLink)}
              >
                <ArrowUpRight size={16} />
              </button>
            </div>
            {resilience.isPending ? (
              <p role="status">Calculating resilience for {pretty(day)}…</p>
            ) : !resilience.data ? (
              <p role="alert">
                Resilience could not be loaded for {pretty(day)}.
              </p>
            ) : resilience.data.sessions === 0 ? (
              <Empty>No scheduled sessions on this date.</Empty>
            ) : (
              <>
                <div className="resilience">
                  <div
                    className="ring"
                    style={{
                      background:
                        "conic-gradient(#27b69b " +
                        (resilience.data.score ?? 0) +
                        "%,var(--border) 0)",
                    }}
                  >
                    <b
                      aria-label={
                        resilience.data.score === null
                          ? "Resilience score unavailable"
                          : "Resilience score " +
                            resilience.data.score +
                            " out of 100"
                      }
                    >
                      {resilience.data.score ?? "—"}
                      <small>/ 100</small>
                    </b>
                  </div>
                  <div>
                    <h4>Daily resilience</h4>
                    <p>
                      Readiness across {resilience.data.sessions} scheduled
                      sessions.
                    </p>
                  </div>
                </div>
                <div className="risk-foot">
                  <Radar size={15} />
                  {resilience.data.risks.length}{" "}
                  {resilience.data.risks.length === 1
                    ? "risk alert"
                    : "risk alerts"}
                  <button
                    className="textbtn"
                    onClick={() => nav(analyticsLink)}
                  >
                    Inspect <ArrowRight size={13} />
                  </button>
                </div>
              </>
            )}
            {resilience.isError && resilience.data && (
              <p role="status">
                Showing the last successful resilience calculation.
              </p>
            )}
          </section>
        </div>
      )}
      <div className="dash-row">
        <section className="panel">
          <div className="panel-head">
            <div className="smallhead">
              <CalendarDays size={18} />
              <h3>{staff ? "Day timetable" : "My sessions for the day"}</h3>
            </div>
            <button className="textbtn" onClick={() => nav(timetable)}>
              View all <ArrowRight size={14} />
            </button>
          </div>
          {dayRows.slice(0, 4).map((s) => (
            <button
              className="row linkrow"
              key={s.id}
              onClick={() => nav(timetable + "&session=" + s.id)}
            >
              <span className="time-chip">{time(s.start)}</span>
              <div className="grow">
                <b>{s.subject}</b>
                <small>
                  {c.name(s.room)} · {c.name(s.faculty)}
                </small>
              </div>
              <Pill
                tone={
                  needsCoverage(s) ? "amber" : s.previous ? "purple" : "neutral"
                }
              >
                {affected.has(s.id) ? "At risk" : s.status}
              </Pill>
            </button>
          ))}
          {!dayRows.length && <Empty>No sessions on this day.</Empty>}
        </section>
        <section className="panel">
          <div className="panel-head">
            <div className="smallhead">
              {staff ? <Network size={18} /> : <CheckCheck size={18} />}
              <h3>{staff ? "Recovery queue" : "Recent updates"}</h3>
            </div>
          </div>
          {staff ? (
            pending.length ? (
              pending.slice(0, 4).map((x) => (
                <button
                  className="row linkrow"
                  key={x.id}
                  onClick={() => nav("/recovery?case=" + x.id)}
                >
                  <span className="tile-icon amber">
                    <Boxes size={17} />
                  </span>
                  <span className="grow">
                    <b>{x.title}</b>
                    <small>
                      {x.impact.sessions.length} affected sessions ·{" "}
                      {x.severity}
                      {" · "}
                      {currentPlans.has(x.id)
                        ? "Ready to review"
                        : "Needs recalculation"}
                    </small>
                  </span>
                  <ChevronRight size={16} />
                </button>
              ))
            ) : (
              <Empty>No recoveries awaiting review.</Empty>
            )
          ) : (
            c.notices.slice(0, 3).map((n) => (
              <button
                className="row linkrow"
                key={n.id}
                onClick={() => nav("/notifications")}
              >
                <div className="grow">
                  <b>{n.title}</b>
                  <small>{n.message}</small>
                </div>
              </button>
            ))
          )}
        </section>
      </div>
    </>
  );
}
