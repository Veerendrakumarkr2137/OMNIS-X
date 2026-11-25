import { useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Position,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { Maximize, Search } from "lucide-react";
import { get, errorText } from "./api";
import { Empty, Pill } from "./ui";
import type { Campus, Twin as TwinData, Incident } from "./types";
const colors = {
  Operational: "#15917c",
  Failed: "#d05551",
  Affected: "#c67922",
};
function Graph({
  c,
  data,
  incident,
}: {
  c: Campus;
  data: TwinData;
  incident?: Incident;
}) {
  const flow = useReactFlow(),
    [chosen, setChosen] = useState(""),
    [search, setSearch] = useState(""),
    [kind, setKind] = useState(incident ? "All" : "Infrastructure"),
    [dept, setDept] = useState(""),
    [labels, setLabels] = useState(false),
    [affectedOnly, setAffectedOnly] = useState(Boolean(incident));
  const cases = incident
    ? [incident]
    : c.cases.filter((x) => x.day === c.dash.anchor);
  const depths: Record<string, number> = Object.assign(
    {},
    ...cases.map((x) => x.impact.depths),
  );
  const daySessions = c.lessons.filter(
    (s) => s.day === (incident?.day || c.dash.anchor),
  );
  const graphNodes = [
    ...data.nodes,
    ...daySessions.map((s) => ({
      id: s.id,
      name: s.subject,
      kind: s.kind === "Examination" ? "Examination" : "Academic session",
      dept: s.dept,
      details: {},
    })),
  ];
  const graphEdges = [...data.edges];
  for (const s of daySessions) {
    graphEdges.push(
      {
        source: s.faculty,
        target: s.id,
        rule: "requires qualified instructor",
      },
      { source: s.room, target: s.id, rule: "requires teaching space" },
      { source: s.id, target: s.cohort, rule: "scheduled attendance" },
    );
    if (
      cases.some(
        (x) =>
          x.impact.sessions.includes(s.id) &&
          (x.simulation ||
            !["Recovered", "Partial recovery"].includes(x.status)),
      )
    ) {
      const parents = [depths[s.room], depths[s.faculty]].filter(
        (d) => d !== undefined,
      );
      depths[s.id] = 1 + (parents.length ? Math.min(...parents) : 0);
      depths[s.cohort] = Math.min(
        depths[s.cohort] ?? Infinity,
        depths[s.id] + 1,
      );
    }
  }
  const filtered = graphNodes.filter(
    (r) =>
      (kind === "All" ||
        (kind === "Infrastructure" &&
          ![
            "Faculty",
            "Cohort",
            "Department",
            "Academic session",
            "Examination",
          ].includes(r.kind)) ||
        r.kind === kind) &&
      (!dept || r.dept === dept) &&
      (!affectedOnly || r.id in depths),
  );
  const cols: Record<string, number> = {
      Power: 0,
      Network: 0,
      Equipment: 0,
      Building: 1,
      Laboratory: 2,
      Classroom: 2,
      Faculty: 2,
      "Academic session": 3,
      Examination: 3,
      Cohort: 4,
    },
    counts: Record<number, number> = {};
  const nodes: Node[] = filtered.map((r) => {
    const col = cols[r.kind] ?? 0,
      index = counts[col] || 0;
    counts[col] = index + 1;
    const state =
      depths[r.id] === 0
        ? "Failed"
        : r.id in depths
          ? "Affected"
          : "Operational";
    return {
      id: r.id,
      position: { x: col * 248, y: index * 73 },
      data: {
        label: (
          <div className="flow-label">
            <small>
              {r.kind} · {state}
            </small>
            <b>{r.name}</b>
          </div>
        ),
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: {
        width: 184,
        border: "1px solid " + (chosen === r.id ? "#8183e8" : colors[state]),
        background: "var(--card)",
        color: "var(--text)",
        borderRadius: 7,
        opacity:
          search && !r.name.toLowerCase().includes(search.toLowerCase())
            ? 0.3
            : 1,
      },
    };
  });
  const ids = new Set(filtered.map((r) => r.id));
  const edges: Edge[] = graphEdges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => ({
      id: e.source + "-" + e.target,
      source: e.source,
      target: e.target,
      label: labels ? e.rule : undefined,
      animated:
        (e.source in depths && e.target in depths) ||
        e.source === chosen ||
        e.target === chosen,
      style: {
        stroke:
          e.source in depths
            ? "#e28c3c"
            : e.source === chosen || e.target === chosen
              ? "#7172d7"
              : "#82a99f",
        strokeWidth: 1.6,
      },
    }));
  const r = graphNodes.find((r) => r.id === chosen) as
    TwinData["nodes"][number] | undefined;
  const kinds = Array.from(new Set(graphNodes.map((r) => r.kind)));
  return (
    <section className="panel graph-panel">
      <div className="filters">
        <label className="searchbox">
          <Search size={14} />
          <input
            aria-label="Find graph node"
            placeholder="Find a node"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Resource category"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {["Infrastructure", "All", ...kinds].map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
        <select
          aria-label="Graph department"
          value={dept}
          onChange={(e) => setDept(e.target.value)}
        >
          <option value="">All departments</option>
          {["CSE", "ECE", "Mechanical"].map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
        <button
          className="icon"
          aria-label="Fit graph to view"
          onClick={() => flow.fitView({ duration: 300 })}
        >
          <Maximize size={16} />
        </button>
      </div>
      <div className="graph-canvas">
        {nodes.length ? (
          <ReactFlow
            key={kind + dept + affectedOnly}
            nodes={nodes}
            edges={edges}
            onNodeClick={(_, n) => setChosen(n.id)}
            fitView
            fitViewOptions={{ padding: 0.12 }}
            minZoom={0.25}
            nodesDraggable={false}
            nodesConnectable={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={18} color="#9aaea8" />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable />
          </ReactFlow>
        ) : (
          <Empty>No resources match this filter.</Empty>
        )}
      </div>
      <div className="filters">
        <Pill>Operational</Pill>
        <Pill tone="red">Failed</Pill>
        <Pill tone="amber">Indirectly affected</Pill>
        <label className="check">
          <input
            type="checkbox"
            checked={labels}
            onChange={(e) => setLabels(e.target.checked)}
          />
          Edge labels
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={affectedOnly}
            onChange={(e) => setAffectedOnly(e.target.checked)}
          />
          Affected only
        </label>
      </div>
      {r && (
        <div className="detailstrip">
          <h3>{r.name}</h3>
          <p>
            {r.kind} · {r.dept || "Institution"}
            {r.details.capacity ? " · Capacity " + r.details.capacity : ""}
          </p>
          <p>
            Dependencies ·{" "}
            {graphEdges
              .filter((e) => e.target === r.id)
              .map(
                (e) =>
                  graphNodes.find((node) => node.id === e.source)?.name ||
                  c.name(e.source),
              )
              .join(", ") || "None modeled"}
          </p>
          <p>
            Scheduled sessions ·{" "}
            {c.lessons
              .filter((s) => [s.faculty, s.room, s.cohort, s.id].includes(r.id))
              .map((s) => s.subject)
              .join(", ") || "None directly assigned"}
          </p>
        </div>
      )}
    </section>
  );
}
export function Twin({ c, incident }: { c: Campus; incident?: Incident }) {
  const query = useQuery({
    queryKey: ["twin", c.user.id],
    queryFn: () => get<TwinData>("/digital-twin"),
  });
  const cascade = useMemo(
    () =>
      Object.entries(incident?.impact.depths ?? {}).sort((a, b) => a[1] - b[1]),
    [incident],
  );
  return (
    <>
      {!incident && (
        <div className="page-intro">
          <div className="eyebrow">CAMPUS MODEL</div>
          <h1>Institutional digital twin</h1>
          <p>
            Inspect resource dependencies and follow disruptions across the
            campus.
          </p>
        </div>
      )}
      {query.data ? (
        <ReactFlowProvider>
          <Graph data={query.data} c={c} incident={incident} />
        </ReactFlowProvider>
      ) : (
        <p>
          {query.isError ? errorText(query.error) : "Loading the campus model…"}
        </p>
      )}
      {!!cascade.length && (
        <div className="cascade">
          {cascade.map(([id, depth]) => (
            <span key={id} style={{ animationDelay: depth * 0.35 + "s" }}>
              {depth ? "Impact " + depth : "Source"} · {c.name(id)}
            </span>
          ))}
        </div>
      )}
    </>
  );
}
