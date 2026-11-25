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
import { ResourceEditor } from "./Directory";
import { Accounts } from "./AccountDirectory";
import { FailureForm } from "./FailureForm";
import { SimulationResults } from "./Recovery";
import { Twin } from "./Twin";
import { useResilience } from "./useResilience";
import {
  fromTime,
  pretty,
  selectedDay,
  shiftDay as shift,
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
export function Timetable({ c }: { c: Campus }) {
  const [params] = useSearchParams();
  const [publishing, setPublishing] = useState(false);
  const [campusView, setCampusView] = useState(false);
  const [view, setView] = useState(
      params.get("view") === "week" ? "Week" : "Day",
    ),
    [date, setDate] = useState(selectedDay(params.get("day"), c.dash.today)),
    [search, setSearch] = useState(""),
    [kind, setKind] = useState(params.get("kind") || ""),
    [department, setDepartment] = useState(""),
    [scope, setScope] = useState(""),
    [selectedId, setSelected] = useState(params.get("session"));
  const profile = c.dash.demo_profile;
  const { role, name, dept, profile: person, resource } = c.user;
  const viewingCampus = role === "Faculty" && campusView;
  const shared = useQuery({
    queryKey: ["shared-timetable", c.user.id],
    queryFn: () =>
      get<{
        sessions: Lesson[];
        assignment_names: Record<string, string>;
        disrupted_sessions: string[];
      }>("/timetable/shared"),
    enabled: viewingCampus,
    refetchInterval: 5000,
  });
  const schedule = viewingCampus ? (shared.data?.sessions ?? []) : c.lessons;
  const label = (id: string) =>
    viewingCampus
      ? (shared.data?.assignment_names[id] ?? c.name(id))
      : c.name(id);
  const selected = schedule.find((s) => s.id === selectedId);
  const personal = role === "Student" || (role === "Faculty" && !viewingCampus);
  const timetableTitle = {
    Admin: "Institution timetable",
    HOD: "Department timetable",
    Faculty: viewingCampus ? "Campus timetable" : "My teaching timetable",
    Student: "My class timetable",
    Operator: "Campus room timetable",
  }[role];
  const timetableContext =
    role === "Student"
      ? [
          name,
          dept,
          person?.semester && "Semester " + person.semester,
          person?.section && "Section " + person.section,
          person?.batch && "Batch " + person.batch,
        ]
          .filter(Boolean)
          .join(" · ")
      : role === "Faculty"
        ? viewingCampus
          ? "Read-only published sessions across departments"
          : [name, dept].filter(Boolean).join(" · ")
        : role === "HOD"
          ? dept
          : role === "Operator"
            ? "Published bookings across campus"
            : "Published sessions across departments";
  const departments = [...new Set(schedule.map((s) => s.dept))].sort();
  const assignmentIds = new Set(
    schedule
      .filter((s) => !department || s.dept === department)
      .flatMap((s) =>
        role === "Operator" ? [s.room] : [s.cohort, s.faculty, s.room],
      ),
  );
  const assignmentOptions = [...assignmentIds]
    .filter((id) => !personal || id !== resource)
    .map((id) => ({ id, name: label(id) }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const course = selected ? profile?.courses[selected.subject] : undefined;
  const affected = new Set(
    viewingCampus ? shared.data?.disrupted_sessions : c.dash.disrupted_sessions,
  );
  const weekday = new Date(date + "T12:00:00Z").getUTCDay();
  const from = view === "Week" ? shift(date, -((weekday + 6) % 7)) : date;
  const until = shift(from, view === "Week" ? 7 : 1);
  const filtered = schedule.filter(
    (s) =>
      (view === "List" || (s.day >= from && s.day < until)) &&
      (!kind || s.kind === kind) &&
      (!department || s.dept === department) &&
      (!scope || [s.faculty, s.room, s.cohort].includes(scope)) &&
      [s.subject, label(s.faculty), label(s.room), label(s.cohort)]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <Intro tag={role + " access"} title={timetableTitle}>
        {timetableContext}
      </Intro>
      <section className="panel">
        {profile && <p className="meta">{profile.breaks}</p>}
        {role === "Faculty" && (
          <div
            className="segmented timetable-scope"
            role="group"
            aria-label="Faculty timetable access"
          >
            {[false, true].map((campus) => (
              <button
                key={String(campus)}
                aria-pressed={campus === campusView}
                className={campus === campusView ? "active" : ""}
                onClick={() => {
                  setCampusView(campus);
                  setScope("");
                  setDepartment("");
                  setSelected(null);
                }}
              >
                {campus ? "Campus timetable" : "My teaching"}
              </button>
            ))}
          </div>
        )}
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
          <div className="actions">
            {c.user.role === "Admin" && (
              <button className="primary" onClick={() => setPublishing(true)}>
                Add session
              </button>
            )}
            {profile && (
              <button
                className="secondary"
                onClick={() => {
                  setDate(c.dash.anchor);
                  setView("Week");
                }}
              >
                Demo week
              </button>
            )}
            <Pill>Published v{c.dash.version}</Pill>
            <Pill tone="neutral">
              {filtered.length} {filtered.length === 1 ? "session" : "sessions"}
            </Pill>
          </div>
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
          {!personal && departments.length > 1 && (
            <select
              aria-label="Timetable department"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setScope("");
              }}
            >
              <option value="">All departments</option>
              {departments.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          )}
          {assignmentOptions.length > 1 && (
            <select
              aria-label={
                role === "Operator" ? "Timetable room" : "Timetable filter"
              }
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            >
              <option value="">
                {role === "Operator" ? "All booked rooms" : "All assignments"}
              </option>
              {assignmentOptions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          )}
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
            {Array.from({ length: 7 }, (_, i) => shift(from, i)).map((day) => (
              <div key={day}>
                <div className="dayheading">{pretty(day)}</div>
                {filtered
                  .filter((s) => s.day === day)
                  .map((s) => (
                    <button
                      className="week-session"
                      onClick={() => setSelected(s.id)}
                      key={s.id}
                    >
                      <small>
                        {time(s.start)} – {time(s.start + s.duration)}
                      </small>
                      <b title={s.subject}>
                        {profile?.courses[s.subject]?.abbr ?? s.subject}
                      </b>
                      <small>
                        {label(s.room)} · {label(s.faculty)}
                      </small>
                      <small>{label(s.cohort)}</small>
                      <small>{affected.has(s.id) ? "At risk" : s.status}</small>
                    </button>
                  ))}
                {!filtered.some((s) => s.day === day) && (
                  <small>
                    {schedule.some((s) => s.day === day)
                      ? "No matching sessions"
                      : "No sessions scheduled"}
                  </small>
                )}
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
                    onClick={() => setSelected(s.id)}
                  >
                    <span className="time-chip">
                      {time(s.start)}
                      <small>{time(s.start + s.duration)}</small>
                    </span>
                    <span className="grow">
                      <b>{s.subject}</b>
                      <small>
                        {label(s.faculty)} · {label(s.room)} · {label(s.cohort)}
                      </small>
                    </span>
                    <Pill
                      tone={
                        affected.has(s.id) || s.status === "Unresolved"
                          ? "amber"
                          : s.previous
                            ? "purple"
                            : "neutral"
                      }
                    >
                      {affected.has(s.id)
                        ? "At risk"
                        : s.status === "Unresolved"
                          ? "Class canceled · Free"
                          : s.previous
                            ? s.status
                            : s.kind}
                    </Pill>
                    <ChevronRight size={14} />
                  </button>
                ))}
            </div>
          ))}
        {viewingCampus && shared.isPending ? (
          <p role="status">Loading campus timetable…</p>
        ) : viewingCampus && shared.isError ? (
          <p role="alert">{errorText(shared.error)}</p>
        ) : (
          !filtered.length && <Empty>No sessions match this view.</Empty>
        )}
      </section>
      {publishing && (
        <PublishLesson c={c} day={date} close={() => setPublishing(false)} />
      )}
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
              ["Faculty", label(selected.faculty)],
              ["Room", label(selected.room)],
              ["Cohort", label(selected.cohort)],
              ...(course?.code ? [["Course code", course.code]] : []),
              ...(course?.faculty.length
                ? [
                    [
                      "Faculty listed on source timetable",
                      course.faculty.join(", "),
                    ],
                  ]
                : []),
              [
                "Status",
                affected.has(selected.id)
                  ? "At risk · awaiting recovery"
                  : selected.status,
              ],
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
              {selected.previous.day && pretty(selected.previous.day) + " · "}
              {label(selected.previous.faculty)} ·{" "}
              {label(selected.previous.room)}
            </p>
          )}
        </Modal>
      )}
    </>
  );
}

function PublishLesson({
  c,
  day,
  close,
}: {
  c: Campus;
  day: string;
  close: () => void;
}) {
  const departments = c.resources.filter((r) => r.kind === "Department");
  const [dept, setDept] = useState(departments[0]?.name || "");
  const [kind, setKind] = useState("Lecture");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const rooms = c.resources.filter(
    (r) => r.kind === (kind === "Lecture" ? "Classroom" : "Laboratory"),
  );
  return (
    <Modal title="Publish teaching session" close={close}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const values = new FormData(e.currentTarget);
          setBusy(true);
          setError("");
          try {
            await api.post("/timetable", {
              ...Object.fromEntries(values),
              dept,
              kind,
              start: fromTime(String(values.get("start"))),
              duration: Number(values.get("duration")),
              protected: values.get("protected") === "on",
              needs: String(values.get("needs") || "")
                .split("|")
                .map((s) => s.trim())
                .filter(Boolean),
            });
            await c.refresh();
            toast.success("Session published");
            close();
          } catch (problem) {
            setError(errorText(problem));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          <label>
            Session ID
            <input name="id" required maxLength={80} />
          </label>
          <label>
            Subject
            <input name="subject" required maxLength={160} />
          </label>
          <label>
            Department
            <select
              value={dept}
              required
              onChange={(e) => setDept(e.target.value)}
            >
              {departments.map((r) => (
                <option key={r.id}>{r.name}</option>
              ))}
            </select>
          </label>
          <label>
            Session type
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {["Lecture", "Laboratory", "Examination"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Assigned faculty
            <select name="faculty" key={"faculty" + dept} required>
              {c.resources
                .filter((r) => r.kind === "Faculty" && r.dept === dept)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Section or batch
            <select name="cohort" key={"cohort" + dept} required>
              {c.resources
                .filter((r) => r.kind === "Cohort" && r.dept === dept)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Room
            <select name="room" required>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date
            <input name="day" type="date" defaultValue={day} required />
          </label>
          <label>
            Start time
            <input name="start" type="time" required defaultValue="09:00" />
          </label>
          <label>
            Duration in minutes
            <input
              name="duration"
              type="number"
              min="15"
              max="600"
              required
              defaultValue="60"
            />
          </label>
        </div>
        <label>
          Required equipment separated by |<input name="needs" />
        </label>
        <label className="check">
          <input name="protected" type="checkbox" /> Protect the scheduled date
          and time
        </label>
        {error && <p role="alert">{error}</p>}
        <button className="primary" disabled={busy}>
          Publish session
        </button>
      </form>
    </Modal>
  );
}

export function Resources({ c }: { c: Campus }) {
  const [params] = useSearchParams();
  const date = selectedDay(params.get("day"), c.dash.today);
  const [q, setQ] = useState(""),
    [type, setType] = useState(params.get("type") || ""),
    [status, setStatus] = useState(""),
    [sel, setSel] = useState("");
  const [editor, setEditor] = useState<string | null>(null);
  const rows = c.resources.filter(
    (r) =>
      (!type ||
        r.kind === type ||
        (type === "Teaching spaces" &&
          ["Classroom", "Laboratory"].includes(r.kind))) &&
      r.name.toLowerCase().includes(q.toLowerCase()),
  );
  const outages = new Set(c.dash.outage_resources?.[date]);
  const state = (id: string) =>
    outages.has(id) ? "Disruption reported" : "No disruption reported";
  const r = c.resources.find((x) => x.id === sel);
  return (
    <>
      <Intro tag="CAMPUS MODEL" title="Resource inventory">
        Resource availability for {pretty(date)}.
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
            <option>Teaching spaces</option>
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
            <option>No disruption reported</option>
            <option>Disruption reported</option>
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
                      <Pill tone={outages.has(r.id) ? "amber" : "teal"}>
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
  const [params, setParams] = useSearchParams();
  const date = params.get("day");
  const nav = useNavigate(),
    [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [sort, setSort] = useState("Newest"),
    [open, setOpen] = useState<Incident | null>(null);
  const filtered = c.cases
    .filter(
      (x) =>
        (!date || x.day === date) &&
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
          {date && (
            <button className="secondary" onClick={() => setParams({})}>
              Clear date · {pretty(selectedDay(date, c.dash.today))}
            </button>
          )}
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
              {n.category && <small>{n.category}</small>}
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
  const [params, setParams] = useSearchParams();
  const day = selectedDay(params.get("day"), c.dash.today);
  const query = useResilience(c.user, day);
  const result = query.data;
  return (
    <>
      <Intro title="Resilience analytics" tag="INSTITUTIONAL READINESS">
        Readiness indicators for {pretty(day)}, based on the published timetable
        and modeled dependencies.
      </Intro>
      <div className="datebar">
        <input
          aria-label="Analytics date"
          type="date"
          value={day}
          onChange={(e) => {
            if (e.target.value)
              setParams({ day: selectedDay(e.target.value, day) });
          }}
        />
      </div>
      {query.isPending && (
        <p role="status">Calculating resilience for {pretty(day)}…</p>
      )}
      {query.isError && (
        <p role="alert">
          {result
            ? "Showing the last successful resilience calculation."
            : errorText(query.error)}
        </p>
      )}
      {result && result.sessions === 0 && (
        <Empty>No scheduled sessions on this date.</Empty>
      )}
      {result && result.sessions > 0 && (
        <div className="dash-row">
          <section className="panel">
            <h3>Resilience score · {result.score ?? "—"}/100</h3>
            <p>
              Equal-weight mean of the measured factors. Recovery success enters
              the score when the selected day has a settled incident.
            </p>
            {Object.entries(result.factors).map(([k, v]) => (
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
            {result.risks.map((r) => (
              <div key={r.title + r.detail} className="row">
                <div className="grow">
                  <b>{r.title}</b>
                  <small>{r.detail}</small>
                </div>
                <Pill tone="amber">{r.severity}</Pill>
              </div>
            ))}
            {!result.risks.length && (
              <Empty>No rule-based alerts for this date.</Empty>
            )}
          </section>
        </div>
      )}
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
          checked={p.allow_substitution || false}
          onChange={(e) => set({ ...p, allow_substitution: e.target.checked })}
        />
        Allow qualified faculty substitution
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
