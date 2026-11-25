import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, errorText, get } from "./api";
import { Empty, Modal, Pill } from "./ui";
import { fromTime, pretty, selectedDay, time, type Campus } from "./types";

type Event = {
  id: number;
  name: string;
  day: string;
  end_day: string;
  start: number;
  end: number;
  department: string | null;
  mandatory: boolean;
  case_id: number | null;
  rooms: string[];
  faculty?: string[];
  cohorts?: string[];
  student_count?: number;
};
type Leave = {
  id: number;
  name: string;
  day: string;
  start: number;
  end: number;
  status: string;
  reason: string;
};
type Student = { id: string; name: string; dept: string };

export function useEvents(userId: string) {
  return useQuery({
    queryKey: ["events", userId],
    queryFn: () => get<Event[]>("/events"),
    refetchInterval: 5000,
  });
}

export function Events({ c }: { c: Campus }) {
  const [params, setParams] = useSearchParams();
  const view = params.get("action");
  const day = selectedDay(params.get("day"), c.dash.today);
  const staff = c.user.role === "Admin" || c.user.role === "HOD";
  const faculty = c.user.role === "Faculty";
  const events = useEvents(c.user.id);
  const leaves = useQuery({
    queryKey: ["leave", c.user.id],
    queryFn: () => get<Leave[]>("/leave"),
    enabled: staff || faculty,
    refetchInterval: 5000,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [unit, setUnit] = useState(c.user.department_id || "");
  const [wholeScope, setWholeScope] = useState(true);
  const departments = c.resources.filter((r) => r.kind === "Department");
  const department = departments.find((d) => d.id === unit)?.name;
  const students = useQuery({
    queryKey: ["event-students", c.user.id],
    queryFn: () => get<Student[]>("/events/students"),
    enabled: staff && view === "new" && !wholeScope,
  });
  const scoped = c.resources.filter(
    (r) => !department || r.dept === department,
  );
  const assignedRooms = [...new Set(c.lessons.map((s) => s.room))];
  const open = (action: string) => {
    setError("");
    setParams({ action, day });
  };

  async function send(path: string, data: unknown, message: string) {
    setBusy(true);
    setError("");
    try {
      await api.post(path, data);
      await c.refresh();
      setParams({});
      toast.success(message);
    } catch (problem) {
      setError(errorText(problem));
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const interval = {
      day: form.get("day"),
      start: fromTime(String(form.get("start"))),
      end: fromTime(String(form.get("end"))),
      reason: form.get("reason") || "",
    };
    if (view === "new") {
      void send(
        "/events",
        {
          ...interval,
          name: form.get("name"),
          department_id: unit || null,
          end_day: form.get("end_day") || null,
          mandatory: form.get("mandatory") === "on",
          whole_scope: wholeScope,
          faculty: form.getAll("faculty"),
          cohorts: form.getAll("cohorts"),
          students: form.getAll("students"),
          rooms: form.getAll("rooms"),
        },
        "Event scheduled. Recovery options are in Recovery studio.",
      );
    } else if (view === "leave") {
      void send("/faculty/leave", interval, "Leave request submitted");
    } else {
      void send(
        "/faculty/issues",
        { ...interval, title: form.get("title"), roots: [form.get("room")] },
        "Infrastructure issue reported",
      );
    }
  }
  return (
    <>
      <div className="page-intro">
        <h1>{faculty ? "Event duties and leave" : "College events"}</h1>
        <p>
          {c.user.dept || "Institution"} · {c.user.name}
        </p>
      </div>
      <div className="actions">
        {staff && (
          <button className="primary" onClick={() => open("new")}>
            Schedule event
          </button>
        )}
        {faculty && (
          <>
            <button className="primary" onClick={() => open("leave")}>
              Request leave
            </button>
            <button className="secondary" onClick={() => open("issue")}>
              Report classroom or laboratory issue
            </button>
          </>
        )}
      </div>
      <section className="panel directory">
        <h2>{faculty ? "Assigned event duties" : "Scheduled events"}</h2>
        {events.isPending && <p>Loading events…</p>}
        {events.isError && <p role="alert">{errorText(events.error)}</p>}
        {events.data?.length === 0 && (
          <Empty>No events for your account.</Empty>
        )}
        {events.data?.map((e) => (
          <div className="row" key={e.id}>
            <div className="grow">
              <b>{e.name}</b>
              <small>
                {e.department || "Institution-wide"} · {pretty(e.day)}
                {e.day !== e.end_day && " – " + pretty(e.end_day)} ·{" "}
                {time(e.start)}–{time(e.end)}
              </small>
              {e.rooms.length > 0 && (
                <small>Reserved rooms · {e.rooms.join(", ")}</small>
              )}
              {Boolean(e.faculty?.length) && (
                <small>Faculty · {e.faculty?.join(", ")}</small>
              )}
              {Boolean(e.cohorts?.length) && (
                <small>Sections and batches · {e.cohorts?.join(", ")}</small>
              )}
              {Boolean(e.student_count) && (
                <small>{e.student_count} individually invited students</small>
              )}
            </div>
            <Pill>{e.mandatory ? "Required" : "Optional"}</Pill>
            {e.case_id && (
              <Link className="secondary" to={"/recovery?case=" + e.case_id}>
                Recovery plans
              </Link>
            )}
          </div>
        ))}
      </section>
      {(staff || faculty) && (
        <section className="panel directory">
          <h2>Leave requests</h2>
          {leaves.isError && <p role="alert">{errorText(leaves.error)}</p>}
          {leaves.data?.length === 0 && <Empty>No leave requests.</Empty>}
          {leaves.data?.map((leave) => (
            <div className="row" key={leave.id}>
              <div className="grow">
                <b>{leave.name}</b>
                <small>
                  {pretty(leave.day)} · {time(leave.start)}–{time(leave.end)}
                </small>
                {leave.reason && <p>{leave.reason}</p>}
              </div>
              <Pill>{leave.status}</Pill>
              {staff && leave.status === "Pending" && (
                <div className="actions">
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      void send(
                        "/leave/" + leave.id + "/approve",
                        {},
                        "Leave approved",
                      )
                    }
                  >
                    Approve leave
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      void send(
                        "/leave/" + leave.id + "/decline",
                        {},
                        "Leave declined",
                      )
                    }
                  >
                    Decline
                  </button>
                </div>
              )}
            </div>
          ))}
          {error && !view && <p role="alert">{error}</p>}
        </section>
      )}
      {((staff && view === "new") ||
        (faculty && ["leave", "issue"].includes(view || ""))) && (
        <Modal
          title={
            view === "new"
              ? "Schedule event"
              : view === "leave"
                ? "Request leave"
                : "Report classroom or laboratory issue"
          }
          close={() => setParams({})}
        >
          <form onSubmit={submit}>
            {view === "new" && (
              <>
                <label>
                  Event name
                  <input name="name" required maxLength={100} />
                </label>
                <label>
                  Organizing department
                  <select
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    disabled={c.user.role === "HOD"}
                  >
                    {c.user.role === "Admin" && (
                      <option value="">Institution-wide</option>
                    )}
                    {departments.map((r) => (
                      <option value={r.id} key={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="check">
                  <input type="checkbox" name="mandatory" defaultChecked />{" "}
                  Mandatory participation
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={wholeScope}
                    onChange={(e) => setWholeScope(e.target.checked)}
                  />{" "}
                  Include everyone in scope
                </label>
                {!wholeScope && (
                  <>
                    <label>
                      Participating faculty
                      <select name="faculty" multiple key={"faculty" + unit}>
                        {scoped
                          .filter((r) => r.kind === "Faculty")
                          .map((r) => (
                            <option value={r.id} key={r.id}>
                              {r.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Participating sections or batches
                      <select name="cohorts" multiple key={"cohorts" + unit}>
                        {scoped
                          .filter((r) => r.kind === "Cohort")
                          .map((r) => (
                            <option value={r.id} key={r.id}>
                              {r.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Individual participating students
                      <select name="students" multiple key={"students" + unit}>
                        {students.data
                          ?.filter((s) => !department || s.dept === department)
                          .map((s) => (
                            <option value={s.id} key={s.id}>
                              {s.name} · {s.id}
                            </option>
                          ))}
                      </select>
                    </label>
                  </>
                )}
                <label>
                  Reserved teaching spaces
                  <select name="rooms" multiple key={"rooms" + unit}>
                    {scoped
                      .filter((r) =>
                        ["Classroom", "Laboratory"].includes(r.kind),
                      )
                      .map((r) => (
                        <option value={r.id} key={r.id}>
                          {r.name}
                        </option>
                      ))}
                  </select>
                </label>
              </>
            )}
            {view === "issue" && (
              <>
                <label>
                  Issue title
                  <input name="title" required />
                </label>
                <label>
                  Assigned room
                  <select name="room" required>
                    {assignedRooms.map((id) => (
                      <option key={id} value={id}>
                        {c.name(id)}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
            <div className="form-grid">
              <label>
                {view === "new" ? "First date" : "Date"}
                <input type="date" name="day" defaultValue={day} required />
              </label>
              {view === "new" && (
                <label>
                  Last date (optional)
                  <input type="date" name="end_day" />
                </label>
              )}
              <label>
                Start time
                <input type="time" name="start" defaultValue="09:00" required />
              </label>
              <label>
                End time
                <input type="time" name="end" defaultValue="10:00" required />
              </label>
            </div>
            {view !== "new" && (
              <label>
                Details
                <textarea name="reason" maxLength={500} />
              </label>
            )}
            {error && <p role="alert">{error}</p>}
            <button className="primary" disabled={busy}>
              {view === "new" ? "Schedule event" : "Submit"}
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
