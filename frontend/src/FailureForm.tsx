import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  FlaskConical,
  GitMerge,
  Network,
  RadioTower,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "./api";
import { fromTime, type Campus, type Incident } from "./types";
import { Modal } from "./ui";
const presets = [
  { name: "Faculty absence", roots: ["f00"], icon: BookOpen },
  { name: "Laboratory outage", roots: ["l0"], icon: FlaskConical },
  { name: "Building power failure", roots: ["p0"], icon: Zap },
  { name: "Network failure", roots: ["n1"], icon: RadioTower },
  { name: "Multiple failures", roots: ["f00", "l0"], icon: GitMerge },
  { name: "No backup laboratory", roots: ["l0", "l3"], icon: AlertTriangle },
];
export function FailureForm({
  c,
  kind,
  done,
  close,
}: {
  c: Campus;
  kind: "absence" | "incident" | "simulation";
  done: (x: Incident) => void;
  close?: () => void;
}) {
  const absence = kind === "absence",
    sim = kind === "simulation",
    options = c.resources.filter(
      (r) => !["Cohort", "Department"].includes(r.kind),
    );
  const [roots, setRoots] = useState<string[]>(
      absence
        ? [c.user.resource!]
        : [options.find((r) => r.id === "f00")?.id || options[0]?.id].filter(
            Boolean,
          ),
    ),
    [day, setDay] = useState(c.dash.anchor),
    [start, setStart] = useState("08:00"),
    [end, setEnd] = useState("18:00"),
    [all, setAll] = useState(true),
    [title, setTitle] = useState(sim ? "Faculty absence" : ""),
    [reason, setReason] = useState(""),
    [severity, setSeverity] = useState("Medium"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError("");
    const interval = {
      day,
      start: all ? 0 : fromTime(start),
      end: all ? 1440 : fromTime(end),
      reason,
    };
    if (interval.end <= interval.start) {
      setError("Choose an end time after the start time.");
      return;
    }
    setBusy(true);
    try {
      const result = (
        await api.post<Incident>(
          absence ? "/faculty/absence" : sim ? "/simulations" : "/incidents",
          absence ? interval : { ...interval, title, roots, severity },
        )
      ).data;
      await c.refresh();
      toast.success(
        sim
          ? "Simulation complete"
          : absence
            ? "Absence recorded"
            : "Incident reported",
      );
      done(result);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const contents = (
    <>
      {sim && (
        <div className="presets">
          {presets
            .filter((p) =>
              p.roots.every((id) => options.some((r) => r.id === id)),
            )
            .map((p) => (
              <button
                key={p.name}
                className={title === p.name ? "selected" : ""}
                onClick={() => {
                  setRoots(p.roots);
                  setTitle(p.name);
                }}
              >
                <p.icon size={18} />
                {p.name}
              </button>
            ))}
        </div>
      )}
      <form onSubmit={submit}>
        {!absence && (
          <>
            <label>
              {sim ? "Scenario" : "Incident"} name
              <input
                required
                maxLength={100}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. North Hall power outage"
              />
            </label>
            <label>
              Affected resources
              <select
                value=""
                onChange={(e) => {
                  if (e.target.value && !roots.includes(e.target.value))
                    setRoots([...roots, e.target.value]);
                }}
              >
                <option value="">Select a resource to add</option>
                {options.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} · {r.kind}
                  </option>
                ))}
              </select>
            </label>
            <div className="chips">
              {roots.map((id) => (
                <button
                  type="button"
                  key={id}
                  aria-label={"Remove " + c.name(id)}
                  onClick={() => setRoots(roots.filter((x) => x !== id))}
                >
                  {c.name(id)} ×
                </button>
              ))}
            </div>
          </>
        )}
        <div className="form-grid">
          <label>
            Date
            <input
              type="date"
              required
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
          </label>
          {!absence && (
            <label>
              Severity
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                {["Low", "Medium", "High", "Critical"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
          )}
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={all}
            onChange={(e) => setAll(e.target.checked)}
          />
          Full day
        </label>
        {!all && (
          <div className="form-grid">
            <label>
              Start time
              <input
                required
                type="time"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              End time
              <input
                required
                type="time"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
          </div>
        )}
        <label>
          {absence ? "Private reason (optional)" : "Notes (optional)"}
          <textarea
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button className="primary" disabled={busy || !roots.length}>
          {busy
            ? "Analyzing impact…"
            : sim
              ? "Run impact analysis"
              : absence
                ? "Submit absence"
                : "Report incident"}
          <ArrowRight size={15} />
        </button>
      </form>
    </>
  );
  return close ? (
    <Modal
      title={absence ? "Report absence" : "Report incident"}
      description={
        absence
          ? "Select the interval you are unavailable to teach."
          : "Record an outage in the official campus workspace."
      }
      close={close}
    >
      {contents}
    </Modal>
  ) : (
    <section className="panel">
      <div className="smallhead">
        <Network size={18} />
        <h3>Configure a scenario</h3>
      </div>
      {contents}
    </section>
  );
}
