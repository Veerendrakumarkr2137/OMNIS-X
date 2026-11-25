import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Bell,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  Filter,
  GitBranch,
  Layers,
  MapPin,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { api, errorText, get } from "./api";
import { Empty, Modal, Pill } from "./ui";
import { Accounts, ResourceEditor } from "./Directory";
import { FailureForm } from "./FailureForm";
import { SimulationResults } from "./Recovery";
import { Twin } from "./Twin";
import {
  pretty,
  time,
  type Audit,
  type Campus,
  type Incident,
  type Lesson,
  type Policy,
} from "./types";
export function Intro({
  tag,
  title,
  children,
}: {
  tag: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-intro">
      <div className="eyebrow">{tag}</div>
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  );
}
function SearchBox({
  value,
  set,
  label,
}: {
  value: string;
  set: (v: string) => void;
  label: string;
}) {
  return (
    <label className="searchbox">
      <Search size={15} />
      <input
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={(e) => set(e.target.value)}
      />
    </label>
  );
}
const shift = (s: string, n: number) => {
  const d = new Date(s + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
export function Timetable({ c }: { c: Campus }) {
  const [params] = useSearchParams();
  const linked = params.get("day") || "";
  const [view, setView] = useState("Day"),
    [date, setDate] = useState(
      c.lessons.some((s) => s.day === linked) ? linked : c.dash.anchor,
    ),
    [search, setSearch] = useState(""),
    [kind, setKind] = useState(""),
    [scope, setScope] = useState(""),
    [selected, setSelected] = useState<Lesson | null>(null);
  const filtered = c.lessons.filter(
    (s) =>
      (view === "List" ||
        (s.day >= date && s.day < shift(date, view === "Week" ? 7 : 1))) &&
      (!kind || s.kind === kind) &&
      (!scope || [s.dept, s.faculty, s.room, s.cohort].includes(scope)) &&
      [s.subject, c.name(s.faculty), c.name(s.room), c.name(s.cohort)]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <Intro tag="ACADEMIC OPERATIONS" title="Timetable">
        Published academic sessions and approved schedule changes.
      </Intro>
      <section className="panel">
        <div className="panel-head">
          <div className="segmented">
            {["Day", "Week", "List"].map((v) => (
              <button
                aria-pressed={view === v}
                className={view === v ? "active" : ""}
                key={v}
                onClick={() => setView(v)}
              >
                {v}
              </button>
            ))}
          </div>
          <Pill>Published v{c.dash.version}</Pill>
        </div>
        <div className="filters">
          <SearchBox label="Search timetable" value={search} set={setSearch} />
          <select
            aria-label="Session type"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="">All session types</option>
            {["Lecture", "Laboratory", "Examination"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <select
            aria-label="Timetable filter"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="">All assignments</option>
            {[...new Set(c.lessons.map((s) => s.dept))].map((d) => (
              <option key={d}>{d}</option>
            ))}
            {c.resources
              .filter((r) =>
                ["Faculty", "Cohort", "Classroom", "Laboratory"].includes(
                  r.kind,
                ),
              )
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
          </select>
        </div>
        {view !== "List" && (
          <div className="datebar">
            <button
              className="icon"
              aria-label="Previous period"
              onClick={() => setDate(shift(date, view === "Week" ? -7 : -1))}
            >
              <ArrowLeft size={16} />
            </button>
            <input
              aria-label="Timetable date"
              type="date"
              value={date}
              onChange={(e) => {
                if (e.target.value) setDate(e.target.value);
              }}
            />
            <button
              className="icon"
              aria-label="Next period"
              onClick={() => setDate(shift(date, view === "Week" ? 7 : 1))}
            >
              <ArrowRight size={16} />
            </button>
          </div>
        )}
        {view === "Week" && (
          <div className="weekgrid">
            {Array.from({ length: 7 }, (_, i) => shift(date, i)).map((day) => (
              <div key={day}>
                <div className="dayheading">{pretty(day)}</div>
                {filtered
                  .filter((s) => s.day === day)
                  .map((s) => (
                    <button
                      className="week-session"
                      onClick={() => setSelected(s)}
                      key={s.id}
                    >
                      <small>
                        {time(s.start)} – {time(s.start + s.duration)}
                      </small>
                      <b>{s.subject}</b>
                      <small>
                        {c.name(s.room)} · {c.name(s.faculty)}
                      </small>
                      <small>{s.status}</small>
                    </button>
                  ))}
                {!filtered.some((s) => s.day === day) && <small>Free</small>}
              </div>
            ))}
          </div>
        )}
        {view !== "Week" &&
          Array.from(new Set(filtered.map((s) => s.day))).map((day) => (
            <div key={day}>
              <div className="dayheading">{pretty(day)}</div>
              {filtered
                .filter((s) => s.day === day)
                .map((s) => (
                  <button
                    className="row linkrow"
                    key={s.id}
                    onClick={() => setSelected(s)}
                  >
                    <span className="time-chip">
                      {time(s.start)}
                      <small>{time(s.start + s.duration)}</small>
                    </span>
                    <span className="grow">
                      <b>{s.subject}</b>
                      <small>
                        {c.name(s.faculty)} · {c.name(s.room)} ·{" "}
                        {c.name(s.cohort)}
                      </small>
                    </span>
                    <Pill tone={s.previous ? "purple" : "neutral"}>
                      {s.previous ? s.status : s.kind}
                    </Pill>
                    <ChevronRight size={14} />
                  </button>
                ))}
            </div>
          ))}
        {!filtered.length && <Empty>No sessions match this view.</Empty>}
      </section>
      {selected && (
        <Modal
          title={selected.subject}
          description={selected.kind + " · " + pretty(selected.day)}
          close={() => setSelected(null)}
        >
          <dl>
            {[
              [
                "Time",
                time(selected.start) +
                  " – " +
                  time(selected.start + selected.duration),
              ],
              ["Faculty", c.name(selected.faculty)],
              ["Room", c.name(selected.room)],
              ["Cohort", c.name(selected.cohort)],
              ["Status", selected.status],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          {selected.previous && (
            <p>
              Previous assignment · {time(selected.previous.start)} ·{" "}
              {c.name(selected.previous.faculty)} ·{" "}
              {c.name(selected.previous.room)}
            </p>
          )}
        </Modal>
      )}
    </>
  );
}
export function Resources({ c }: { c: Campus }) {
  const [q, setQ] = useState(""),
    [type, setType] = useState(""),
    [status, setStatus] = useState(""),
    [sel, setSel] = useState("");
  const [editor, setEditor] = useState<string | null>(null);
  const rows = c.resources.filter(
    (r) =>
      (!type || r.kind === type) &&
      r.name.toLowerCase().includes(q.toLowerCase()),
  );
  const state = (id: string) =>
    c.cases.some((x) => x.day === c.dash.anchor && id in x.impact.depths)
      ? "Outage on demo day"
      : "Operational";
  const r = c.resources.find((x) => x.id === sel);
  return (
    <>
      <Intro tag="CAMPUS MODEL" title="Resource inventory">
        Inspect campus spaces, teaching staff and infrastructure.
      </Intro>
      {editor !== null && (
        <ResourceEditor
          c={c}
          resource={c.resources.find((x) => x.id === editor)}
          close={() => setEditor(null)}
        />
      )}
      <section className="panel">
        <div className="filters">
          {c.user.role === "Admin" && (
            <button className="primary" onClick={() => setEditor("")}>
              Add resource
            </button>
          )}
          <SearchBox label="Search resources" value={q} set={setQ} />
          <select
            aria-label="Resource type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">All resource types</option>
            {[...new Set(c.resources.map((x) => x.kind))].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <select
            aria-label="Operational status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option>Operational</option>
            <option>Outage on demo day</option>
          </select>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Resource</th>
                <th>Type</th>
                <th>Department</th>
                <th>Availability</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows
                .filter((r) => !status || state(r.id) === status)
                .map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button className="textbtn" onClick={() => setSel(r.id)}>
                        {r.name}
                      </button>
                    </td>
                    <td>{r.kind}</td>
                    <td>{r.dept || "Campus"}</td>
                    <td>
                      <Pill
                        tone={state(r.id) === "Operational" ? "teal" : "amber"}
                      >
                        {state(r.id)}
                      </Pill>
                    </td>
                    <td />
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
      {r && (
        <Modal
          title={r.name}
          description={r.kind + " · " + (r.dept || "Institution")}
          close={() => setSel("")}
        >
          <dl>
            {Object.entries(r.details).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>
                  {Array.isArray(v)
                    ? v.join(", ")
                    : k === "building"
                      ? c.name(String(v))
                      : String(v)}
                </dd>
              </div>
            ))}
          </dl>
          <p>
            {
              c.lessons.filter((s) =>
                [s.faculty, s.room, s.cohort].includes(r.id),
              ).length
            }{" "}
            assigned sessions in the timetable.
          </p>
          {c.user.role === "Admin" &&
            [
              "Faculty",
              "Classroom",
              "Laboratory",
              "Cohort",
              "Building",
            ].includes(r.kind) && (
              <button
                className="secondary"
                onClick={() => {
                  setSel("");
                  setEditor(r.id);
                }}
              >
                Edit resource
              </button>
            )}
        </Modal>
      )}
    </>
  );
}
export function Incidents({ c, report }: { c: Campus; report: () => void }) {
  const nav = useNavigate(),
    [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [sort, setSort] = useState("Newest"),
    [open, setOpen] = useState<Incident | null>(null);
  const filtered = c.cases
    .filter(
      (x) =>
        (!status || x.status === status) &&
        x.title.toLowerCase().includes(q.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "Newest"
        ? b.id - a.id
        : b.impact.sessions.length - a.impact.sessions.length,
    );
  return (
    <>
      <Intro
        title={
          c.user.role === "Faculty" ? "My absence reports" : "Incident center"
        }
        tag="OPERATIONS LOG"
      />{" "}
      <section className="panel">
        <div className="filters">
          <SearchBox value={q} set={setQ} label="Search incidents" />
          <select
            aria-label="Incident status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {[...new Set(c.cases.map((x) => x.status))].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Sort incidents"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option>Newest</option>
            <option>Most affected sessions</option>
          </select>
          <button className="primary" onClick={report}>
            {c.user.role === "Faculty" ? "Report absence" : "Report incident"}
          </button>
        </div>
        {filtered.map((x) => (
          <button className="row linkrow" key={x.id} onClick={() => setOpen(x)}>
            <span className="tile-icon amber">
              <GitBranch size={18} />
            </span>
            <span className="grow">
              <b>{x.title}</b>
              <small>
                INC-{String(x.id).padStart(3, "0")} · {pretty(x.day)} ·{" "}
                {x.severity}
              </small>
            </span>
            <Pill tone="neutral">{x.status}</Pill>
            <ChevronRight size={15} />
          </button>
        ))}
        {!filtered.length && <Empty>No matching reports.</Empty>}
      </section>
      {open && (
        <Modal
          title={open.title}
          description={
            pretty(open.day) + " · " + time(open.start) + "–" + time(open.end)
          }
          close={() => setOpen(null)}
        >
          <Pill>{open.status}</Pill>
          <p>{open.reason}</p>
          <dl>
            {[
              ["Sources", open.roots.map(c.name).join(", ")],
              [
                "Downstream resources",
                Object.values(open.impact.depths).filter((d) => d > 0).length,
              ],
              ["Affected sessions", open.impact.sessions.length],
              ["Affected students", open.impact.students],
              ["Examinations", open.impact.exams],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          {c.user.role !== "Faculty" && (
            <button
              className="primary"
              onClick={() => nav("/recovery?case=" + open.id)}
            >
              Review recovery <ArrowRight size={15} />
            </button>
          )}
        </Modal>
      )}
    </>
  );
}
export function Scenarios({ c }: { c: Campus }) {
  const [sel, setSel] = useState<Incident | null>(null);
  const history = useQuery({
    queryKey: ["simulations", c.user.id],
    queryFn: () => get<Incident[]>("/simulations"),
  });
  return (
    <>
      <Intro title="Scenario lab" tag="WHAT-IF SIMULATION">
        Explore campus failures in a hypothetical timetable and compare recovery
        options.
      </Intro>
      <FailureForm
        c={c}
        kind="simulation"
        done={(x) => {
          setSel(x);
          history.refetch();
        }}
      />
      {!!history.data?.length && (
        <label className="inlinefield">
          Simulation history
          <select
            aria-label="Simulation history"
            value={sel?.id || ""}
            onChange={(e) =>
              setSel(
                history.data?.find((x) => x.id === Number(e.target.value)) ||
                  null,
              )
            }
          >
            <option value="">Select a simulation</option>
            {history.data.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} · {s.title}
              </option>
            ))}
          </select>
        </label>
      )}
      {sel && (
        <>
          <div className="sectionline">
            <h2>Simulated impact</h2>
            <Pill tone="purple">Hypothetical</Pill>
          </div>
          <Twin c={c} incident={sel} />
          <SimulationResults c={c} incident={sel} />
        </>
      )}
    </>
  );
}
export function Notices({ c }: { c: Campus }) {
  const nav = useNavigate();
  async function read(id?: number) {
    try {
      if (id) await api.patch("/notifications/" + id + "/read");
      else await api.post("/notifications/read-all");
      await c.refresh();
    } catch (e) {
      toast.error(errorText(e));
    }
  }
  return (
    <>
      <Intro tag="WORKSPACE INBOX" title="Notification center" />
      <section className="panel">
        <div className="panel-head">
          <h3>Updates</h3>
          <button
            className="secondary"
            disabled={c.notices.every((n) => n.seen)}
            onClick={() => read()}
          >
            <Check size={15} />
            Mark all as read
          </button>
        </div>
        {c.notices.map((n) => (
          <div className="row" key={n.id}>
            <span className={"tile-icon " + (n.seen ? "neutral" : "teal")}>
              <Bell size={16} />
            </span>
            <div className="grow">
              <b>{n.title}</b>
              <p>{n.message}</p>
              <small>{new Date(n.created).toLocaleString()}</small>
            </div>
            <button
              className="textbtn"
              onClick={async () => {
                await read(n.id);
                nav(n.route);
              }}
            >
              Open <ArrowRight size={14} />
            </button>
          </div>
        ))}
        {!c.notices.length && <Empty>Your inbox is clear.</Empty>}
      </section>
    </>
  );
}
export function Analytics({ c }: { c: Campus }) {
  return (
    <>
      <Intro title="Resilience analytics" tag="INSTITUTIONAL READINESS">
        Readiness indicators calculated from the published timetable and modeled
        dependencies.
      </Intro>
      <div className="dash-row">
        <section className="panel">
          <h3>Resilience score · {c.dash.score ?? "—"}/100</h3>
          <p>
            Equal-weight mean of the measured factors. Recovery success enters
            the score after a settled incident.
          </p>
          {Object.entries(c.dash.factors || {}).map(([k, v]) => (
            <div className="factor" key={k}>
              <div>
                <b>{k}</b>
                <small>{v === null ? "No observations" : v + "%"}</small>
              </div>
              <div className="progress">
                <i style={{ width: (v || 0) + "%" }} />
              </div>
            </div>
          ))}
        </section>
        <section className="panel">
          <h3>Proactive risk alerts</h3>
          {c.dash.risks?.map((r) => (
            <div key={r.title + r.detail} className="row">
              <div className="grow">
                <b>{r.title}</b>
                <small>{r.detail}</small>
              </div>
              <Pill tone="amber">{r.severity}</Pill>
            </div>
          ))}
          {!c.dash.risks?.length && <Empty>No rule-based alerts.</Empty>}
        </section>
      </div>
    </>
  );
}
export function AuditPage() {
  const a = useQuery({
    queryKey: ["audit"],
    queryFn: () => get<Audit[]>("/audit"),
    refetchInterval: 5000,
  });
  return (
    <>
      <Intro title="Audit history" tag="INSTITUTIONAL RECORD" />
      <section className="panel">
        {a.isError && <p>{errorText(a.error)}</p>}
        {a.data?.map((x) => (
          <div className="row" key={x.id}>
            <Clock3 size={17} />
            <div className="grow">
              <b>{x.action}</b>
              <small>
                {x.actor} · {new Date(x.created).toLocaleString()}
              </small>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}
export function Settings({ c }: { c: Campus }) {
  const query = useQuery({
    queryKey: ["settings"],
    queryFn: () => get<Policy>("/settings"),
  });
  return (
    <>
      <Intro title="Recovery settings" tag="INSTITUTIONAL POLICY" />
      {query.data ? (
        <>
          <PolicyForm c={c} policy={query.data} />
          <Accounts c={c} />
        </>
      ) : (
        <p>{query.isError ? errorText(query.error) : "Loading policy…"}</p>
      )}
    </>
  );
}
function PolicyForm({ c, policy }: { c: Campus; policy: Policy }) {
  const [p, set] = useState(policy),
    [busy, setBusy] = useState(false);
  return (
    <form
      className="panel policy"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await api.patch("/settings", p);
          await c.refresh();
          toast.success("Policy saved");
        } catch (e) {
          toast.error(errorText(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3>Automation and approvals</h3>
      <label>
        Recovery mode
        <select
          value={p.mode}
          onChange={(e) => set({ ...p, mode: e.target.value })}
        >
          {["Manual", "Assisted", "Automatic"].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </label>
      <p>
        {p.mode === "Automatic"
          ? "Automatically apply complete plans with no delay or substitutions and a penalty within the threshold."
          : p.mode === "Assisted"
            ? "Generate alternatives when an outage is reported. A reviewer approves timetable changes."
            : "Reviewers initiate recovery generation from the incident."}
      </p>
      <label className="check">
        <input
          type="checkbox"
          checked={p.hod_approval}
          onChange={(e) => set({ ...p, hod_approval: e.target.checked })}
        />
        Allow HOD approval for departmental incidents
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={p.require_consent || false}
          onChange={(e) => set({ ...p, require_consent: e.target.checked })}
        />
        Require consent from substitute faculty before approval
      </label>
      <div className="form-grid">
        {(
          [
            ["delay_weight", "Student-minute weight"],
            ["room_weight", "Room change weight"],
            ["faculty_weight", "Substitution weight"],
            ["travel_minutes", "Inter-building travel minutes"],
            ["auto_penalty_limit", "Automatic approval penalty limit"],
          ] as const
        ).map(([k, label]) => (
          <label key={k}>
            {label}
            <input
              type="number"
              min="0"
              required
              value={p[k]}
              onChange={(e) => set({ ...p, [k]: Number(e.target.value) })}
            />
          </label>
        ))}
      </div>
      <button className="primary" disabled={busy}>
        Save policy
      </button>
    </form>
  );
}
