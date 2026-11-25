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
} from "lucide-react";
import { useNavigate } from "react-router-dom";
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
import { pretty, privileged, time, type Campus } from "./types";
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
}: {
  c: Campus;
  report: () => void;
}) {
  const nav = useNavigate(),
    staff = privileged(c.user),
    today = c.dash.anchor;
  const todayRows = c.lessons.filter((s) => s.day === today);
  const active = c.cases.filter(
    (x) => !["Recovered", "No impact"].includes(x.status),
  );
  const pending = c.cases.filter((x) => x.status === "Pending review");
  const rooms = c.resources.filter((x) =>
    ["Classroom", "Laboratory"].includes(x.kind),
  );
  const failed = new Set(
    c.cases
      .filter((x) => x.day === today)
      .flatMap((x) => Object.keys(x.impact.depths)),
  );
  const faculty = c.resources.filter((x) => x.kind === "Faculty");
  const chart = Array.from(new Set(c.lessons.map((x) => x.day)))
    .sort()
    .map((day) => ({
      day: pretty(day).split(",")[0],
      Sessions: c.lessons.filter((s) => s.day === day).length,
      Covered: c.lessons.filter(
        (s) =>
          s.day === day &&
          s.status !== "Unresolved" &&
          !active.some((x) => x.impact.sessions.includes(s.id)),
      ).length,
    }));
  const stats = staff
    ? [
        {
          label: "Faculty available",
          value: faculty.filter((r) => !failed.has(r.id)).length,
          detail: "of " + faculty.length + " faculty · demo day",
          icon: Users,
          path: "/resources",
          cls: "teal",
        },
        {
          label: "Teaching spaces",
          value: rooms.length,
          detail:
            rooms.filter((r) => r.kind === "Laboratory" && !failed.has(r.id))
              .length + " operational laboratories",
          icon: Building2,
          path: "/resources",
          cls: "purple",
        },
        {
          label: "Active incidents",
          value: active.length,
          detail:
            new Set(active.flatMap((x) => x.impact.sessions)).size +
            " affected sessions",
          icon: CircleAlert,
          path: "/incidents",
          cls: "amber",
        },
        {
          label: "Awaiting review",
          value: pending.length,
          detail: "Recovery decisions",
          icon: GitPullRequest,
          path: "/recovery",
          cls: "blue",
        },
      ]
    : [
        {
          label: "Sessions today",
          value: todayRows.length,
          detail: pretty(today),
          icon: CalendarDays,
          path: "/timetable",
          cls: "teal",
        },
        {
          label: "Upcoming exams",
          value: c.lessons.filter((s) => s.kind === "Examination").length,
          detail: "In the published timetable",
          icon: Layers3,
          path: "/timetable",
          cls: "purple",
        },
        {
          label: "Schedule updates",
          value: c.lessons.filter((s) => s.previous).length,
          detail: "Published changes",
          icon: CalendarClock,
          path: "/timetable",
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
            {staff
              ? "Monitor operational health, anticipate failures and coordinate intelligent recovery."
              : "Your sessions, schedule changes and campus notifications in one place."}
          </p>
          <div className="actions">
            {staff ? (
              <>
                <button className="accent" onClick={() => nav("/scenarios")}>
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
                  c.user.role === "Faculty" ? report : () => nav("/timetable")
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
        <span className="date">
          <CalendarDays size={14} />
          {pretty(today)}
        </span>
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
      {staff && (
        <div className="dash-row">
          <section className="panel">
            <div className="panel-head">
              <div className="smallhead">
                <Activity size={18} />
                <h3>Academic continuity</h3>
              </div>
              <span className="meta">5-day timetable</span>
            </div>
            <div className="chart-legend">
              <i /> Scheduled sessions <i /> Covered sessions
            </div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={190}>
                <AreaChart
                  data={chart}
                  margin={{ left: -24, right: 10, top: 14 }}
                >
                  <defs>
                    <linearGradient id="fillT" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#20b99c" stopOpacity=".3" />
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
          </section>
          <section className="panel">
            <div className="panel-head">
              <div className="smallhead">
                <ShieldCheck size={18} />
                <h3>Resilience overview</h3>
              </div>
              <button
                aria-label="See resilience analytics"
                className="icon"
                onClick={() => nav("/analytics")}
              >
                <ArrowUpRight size={16} />
              </button>
            </div>
            <div className="resilience">
              <div
                className="ring"
                style={{
                  background:
                    "conic-gradient(#27b69b " +
                    (c.dash.score ?? 0) +
                    "%,var(--border) 0)",
                }}
              >
                <b>
                  {c.dash.score ?? "—"}
                  <small>/ 100</small>
                </b>
              </div>
              <div>
                <h4>Institutional resilience</h4>
                <p>Mean of measured recovery and readiness factors.</p>
              </div>
            </div>
            <div className="risk-foot">
              <Radar size={15} />
              {c.dash.risks?.length ?? 0} proactive risk alerts{" "}
              <button className="textbtn" onClick={() => nav("/analytics")}>
                Inspect <ArrowRight size={13} />
              </button>
            </div>
          </section>
        </div>
      )}
      <div className="dash-row">
        <section className="panel">
          <div className="panel-head">
            <div className="smallhead">
              <CalendarDays size={18} />
              <h3>{staff ? "Today's timetable" : "My sessions today"}</h3>
            </div>
            <button className="textbtn" onClick={() => nav("/timetable")}>
              View all <ArrowRight size={14} />
            </button>
          </div>
          {todayRows.slice(0, 4).map((s) => (
            <div className="row" key={s.id}>
              <span className="time-chip">{time(s.start)}</span>
              <div className="grow">
                <b>{s.subject}</b>
                <small>
                  {c.name(s.room)} · {c.name(s.faculty)}
                </small>
              </div>
              <Pill tone={s.previous ? "purple" : "neutral"}>{s.status}</Pill>
            </div>
          ))}
          {!todayRows.length && <Empty>No sessions on this day.</Empty>}
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
