import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  CheckCheck,
  Download,
  GitCompareArrows,
  RefreshCw,
  ShieldCheck,
  Trophy,
} from "lucide-react";
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { toast } from "sonner";
import { api, errorText, get } from "./api";
import { Empty, Modal, Pill } from "./ui";
import {
  pretty,
  time,
  type Campus,
  type Incident,
  type Plan,
  type Slot,
} from "./types";
export function PlanComparison({
  c,
  incident,
  items,
}: {
  c: Campus;
  incident: Incident;
  items: Plan[];
}) {
  const [detail, setDetail] = useState<Plan | null>(null),
    [confirm, setConfirm] = useState<Plan | null>(null),
    [busy, setBusy] = useState(false);
  const available = items.filter((p) => !["Superseded"].includes(p.status));
  const canApprove =
    c.user.role === "Admin" || (c.user.role === "HOD" && c.dash.hod_approval);
  const display = (s: Slot) =>
    (s.day ? pretty(s.day) + " · " : "") +
    time(s.start) +
    " · " +
    c.name(s.faculty) +
    " · " +
    c.name(s.room);
  const subjectsOf = (id: string) =>
    c.resources.find((r) => r.id === id)?.details?.subjects || [];
  async function act(id: number, action: string) {
    if (busy) return;
    setBusy(true);
    try {
      const result = (await api.post("/recovery/plans/" + id + "/" + action))
        .data;
      await c.refresh();
      setConfirm(null);
      setDetail(null);
      toast.success(
        action === "approve"
          ? "Timetable v" + result.version + " published"
          : action === "recommend"
            ? "Recommendation sent"
            : "Plan rejected",
      );
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function regenerate() {
    setBusy(true);
    try {
      await api.post("/recovery/generate", { case_id: incident.id });
      await c.refresh();
      toast.success("Alternatives recalculated");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  function save() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify({ incident, plans: available }, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "omnis-x-case-" + incident.id + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const changes = (p: Plan) => (
    <div className="changes">
      {p.data.changes.map((ch) => (
        <div key={ch.id}>
          <b>
            {ch.subject} · {c.name(ch.cohort)}
          </b>
          <small>Original · {display({ ...ch.before, day: ch.day })}</small>
          <small>
            Proposed ·{" "}
            {ch.after
              ? display({ ...ch.after, day: ch.after.day || ch.day })
              : "No one available · Class free (notify students)"}
          </small>
        </div>
      ))}
    </div>
  );
  return (
    <>
      <div className="sectionline">
        <div>
          <h3>{incident.title}</h3>
          <small>
            {pretty(incident.day)} · {incident.impact.sessions.length} affected
            sessions · {incident.impact.students} students
          </small>
        </div>
        <div className="actions">
          {!incident.simulation &&
            !["No impact", "Recovered", "Partial recovery"].includes(
              incident.status,
            ) && (
              <button
                className="secondary"
                disabled={busy}
                onClick={regenerate}
              >
                <RefreshCw size={14} />
                Regenerate
              </button>
            )}
          <button
            className="icon"
            onClick={save}
            aria-label="Export plans as JSON"
          >
            <Download size={17} />
          </button>
        </div>
      </div>
      <div className="plan-grid">
        {available.map((p) => (
          <section
            className={"plan " + (p.rank === 1 ? "best" : "")}
            key={p.id}
          >
            <div className="panel-head">
              <span className="eyebrow">
                ALTERNATIVE {String(p.rank).padStart(2, "0")}
              </span>
              {p.rank === 1 && p.data.recovered > 0 && (
                <span className="mini">
                  <Trophy size={12} />
                  First ranked
                </span>
              )}
            </div>
            <div className="coverage">
              {Math.round(
                (100 * p.data.recovered) / (p.data.changes.length || 1),
              )}
              <small>%</small>
            </div>
            <b>Session recovery</b>
            <div className="progress">
              <i
                style={{
                  width: (100 * p.data.recovered) / p.data.changes.length + "%",
                }}
              />
            </div>
            <dl>
              {[
                ["Sessions recovered", p.data.recovered],
                ["Unresolved sessions", p.data.unresolved],
                ["Room changes", p.data.rooms],
                ["Substitutions", p.data.subs],
                ["Student-minutes delayed", p.data.delay],
                ["Disruption penalty", p.data.penalty],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            {p.data.changes.length > 0 && (
              <div className="changes">
                {p.data.changes.map((ch) => {
                  const sameFaculty =
                    !!ch.after && ch.after.faculty === ch.before.faculty;
                  const diffSub =
                    ch.after && !sameFaculty
                      ? subjectsOf(ch.after.faculty).find(
                          (s) => s !== ch.subject,
                        )
                      : undefined;
                  return (
                    <div key={ch.id}>
                      <b>
                        {ch.subject} · {c.name(ch.cohort)}
                      </b>
                      <small>
                        Taking this subject · {c.name(ch.before.faculty)}
                        {sameFaculty ? " · continues" : ""}
                      </small>
                      {ch.after ? (
                        <>
                          {!sameFaculty && (
                            <small>
                              Handling faculty · {c.name(ch.after.faculty)}
                              {diffSub ? ` (${diffSub})` : ""}
                            </small>
                          )}
                          <small>
                            {c.name(ch.after.room)}
                            {ch.after.room === ch.before.room
                              ? " (same class)"
                              : ""}{" "}
                            · {time(ch.after.start)}
                          </small>
                        </>
                      ) : (
                        <small>
                          No one available · Class free (notify students)
                        </small>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <Pill tone={p.status === "Pending" ? "amber" : "neutral"}>
              {p.status}
            </Pill>
            {!incident.simulation &&
              c.dash.require_consent &&
              p.data.subs > 0 &&
              p.status === "Pending" &&
              p.revision === c.dash.revision && (
                <button
                  className="secondary wide"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const response = await api.post<
                        { faculty: string; decision: string }[]
                      >("/recovery/plans/" + p.id + "/request-consent");
                      toast.info(
                        response.data
                          .map((x) => c.name(x.faculty) + " · " + x.decision)
                          .join(", "),
                      );
                    } catch (e) {
                      toast.error(errorText(e));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Request / check consent
                </button>
              )}
            <button className="secondary wide" onClick={() => setDetail(p)}>
              <GitCompareArrows size={15} />
              View details
            </button>
            {!incident.simulation &&
              p.status === "Pending" &&
              (p.revision !== c.dash.revision ? (
                <small className="stale">Stale · regenerate to review</small>
              ) : canApprove ? (
                <button className="primary wide" onClick={() => setConfirm(p)}>
                  <ShieldCheck size={15} />
                  Approve plan
                </button>
              ) : (
                <button
                  className="secondary wide"
                  disabled={busy}
                  onClick={() => act(p.id, "recommend")}
                >
                  Recommend plan
                </button>
              ))}
          </section>
        ))}
      </div>
      {!available.length && (
        <Empty>
          {incident.impact.sessions.length
            ? "Planning status · " +
              (incident.impact.solver_status || "Awaiting generation") +
              ". Generate alternatives or review the constraints."
            : "The outage interval affects no scheduled sessions."}
        </Empty>
      )}
      {available.length > 1 && (
        <section className="panel comparison">
          <h3>Disruption penalty by alternative</h3>
          <p>
            Plans rank by sessions recovered, then by the lowest configured
            penalty. Tied alternatives share the same cost.
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart
              data={available.map((p) => ({
                name: "Alternative " + p.rank,
                Penalty: p.data.penalty,
              }))}
            >
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: "var(--muted)" }}
              />
              <YAxis width={40} tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <Tooltip />
              <Bar
                dataKey="Penalty"
                fill="#1da98f"
                maxBarSize={58}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}
      {detail && (
        <Modal
          title={"Alternative " + detail.rank + " details"}
          description={detail.data.explanation}
          close={() => setDetail(null)}
        >
          <div className="chips">
            <Pill>{detail.data.solver} solver result</Pill>
            <Pill tone="purple">{detail.data.outcome} recovery</Pill>
          </div>
          <div className="validation">
            <CheckCheck size={16} />
            Independent validation · {detail.data.violations} violations
          </div>
          <p>
            Checked qualifications, availability, outages, room capacity and
            equipment, overlap, duration, institutional hours, workload,
            protected exam times and travel policy.
          </p>
          {changes(detail)}
          {detail.data.blockers.map((x) => (
            <p key={x.session} className="error">
              {x.session} · {x.reason}
            </p>
          ))}
          {canApprove &&
            !incident.simulation &&
            detail.status === "Pending" && (
              <button
                className="secondary"
                disabled={busy}
                onClick={() => act(detail.id, "reject")}
              >
                Reject alternative
              </button>
            )}
        </Modal>
      )}
      {confirm && (
        <Modal
          title="Approve timetable changes?"
          description={
            "Publish alternative " +
            confirm.rank +
            " for " +
            incident.title +
            ". The affected faculty and students will receive a notification."
          }
          close={() => {
            if (!busy) setConfirm(null);
          }}
        >
          {changes(confirm)}
          <button
            disabled={busy}
            className="primary"
            onClick={() => act(confirm.id, "approve")}
          >
            <Check size={16} />
            {busy ? "Publishing…" : "Confirm and publish"}
          </button>
        </Modal>
      )}
    </>
  );
}
export function Recovery({ c }: { c: Campus }) {
  const [params, setParams] = useSearchParams();
  const selected =
    c.cases.find((x) => x.id === Number(params.get("case"))) || c.cases[0];
  return (
    <>
      <div className="page-intro">
        <div className="eyebrow">DECISION SUPPORT</div>
        <h1>Intelligent Recovery Studio</h1>
        <p>
          Compare validated alternatives and review the timetable changes before
          publication.
        </p>
      </div>
      {selected ? (
        <>
          <label className="inlinefield">
            Incident
            <select
              value={selected.id}
              onChange={(e) => setParams({ case: e.target.value })}
            >
              {c.cases.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.title} · {x.status}
                </option>
              ))}
            </select>
          </label>
          <PlanComparison
            key={selected.id}
            c={c}
            incident={selected}
            items={c.plans.filter((p) => p.case_id === selected.id)}
          />
        </>
      ) : (
        <Empty>No incidents to review.</Empty>
      )}
    </>
  );
}
export function SimulationResults({
  c,
  incident,
}: {
  c: Campus;
  incident: Incident;
}) {
  const query = useQuery({
    queryKey: ["sim-plans", incident.id],
    queryFn: () => get<Plan[]>("/recovery/plans?case_id=" + incident.id),
  });
  return query.isError ? (
    <p role="alert">{errorText(query.error)}</p>
  ) : query.isPending ? (
    <p>Loading alternatives…</p>
  ) : (
    <PlanComparison c={c} incident={incident} items={query.data} />
  );
}
