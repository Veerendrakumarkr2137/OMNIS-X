import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errorText, get } from "./api";
import { Empty, Pill } from "./ui";
import { pretty, time, type Campus, type Change } from "./types";
type Request = {
  plan_id: number;
  day: string;
  decision: string;
  changes: Change[];
};
export function Substitutions({ c }: { c: Campus }) {
  const query = useQuery({
    queryKey: ["substitutions", c.user.id],
    queryFn: () => get<Request[]>("/faculty/substitutions"),
    refetchInterval: 5000,
  });
  const [busy, setBusy] = useState(false);
  async function decide(id: number, decision: string) {
    setBusy(true);
    try {
      await api.post("/faculty/substitutions/" + id, { decision });
      await c.refresh();
      toast.success("Response recorded");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-intro">
        <div className="eyebrow">TEACHING WORKSPACE</div>
        <h1>Substitute requests</h1>
        <p>
          Review proposed teaching assignments and share your availability with
          the reviewer.
        </p>
      </div>
      <section className="panel">
        {query.isError ? (
          <p>{errorText(query.error)}</p>
        ) : query.isPending ? (
          <p>Loading requests…</p>
        ) : !query.data.length ? (
          <Empty>No current substitution requests.</Empty>
        ) : (
          query.data.map((r) => (
            <div key={r.plan_id} className="detailstrip">
              <div className="panel-head">
                <h3>{pretty(r.day)}</h3>
                <Pill>{r.decision}</Pill>
              </div>
              {r.changes.map((ch) => (
                <p key={ch.id}>
                  {ch.subject} · {time(ch.after!.start)} ·{" "}
                  {c.name(ch.after!.room)} · {ch.duration} min
                </p>
              ))}
              {r.decision === "Pending" && (
                <div className="actions">
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => decide(r.plan_id, "Accepted")}
                  >
                    Accept substitution
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => decide(r.plan_id, "Declined")}
                  >
                    Decline
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </section>
    </>
  );
}
