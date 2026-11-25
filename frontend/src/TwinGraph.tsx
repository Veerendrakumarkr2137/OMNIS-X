import { useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Resource, Twin } from "./types";

const lanes = [
  ["Power", "Network", "Equipment", "Department"],
  ["Building"],
  ["Classroom", "Laboratory"],
  ["Faculty"],
  ["Academic session", "Examination"],
  ["Cohort"],
];
const colors = {
  operational: "var(--teal)",
  failed: "#cf5753",
  affected: "#b67a27",
};
type Status = keyof typeof colors;

function placeResources(resources: Resource[]) {
  const columns: Resource[][] = lanes.map(() => []);
  const other: Resource[] = [];
  for (const resource of resources) {
    const column = lanes.findIndex((kinds) => kinds.includes(resource.kind));
    (columns[column] ?? other).push(resource);
  }
  const filled = [...columns, other].filter((column) => column.length);
  const rows = Math.max(...filled.map((column) => column.length));
  return filled.flatMap((column, x) =>
    [...column]
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((resource, y) => ({
        resource,
        position: { x: x * 252, y: (y + (rows - column.length) / 2) * 76 },
      })),
  );
}

export default function TwinGraph({
  resources,
  connections,
  status,
  selected,
  select,
}: {
  resources: Resource[];
  connections: Twin["edges"];
  status: (id: string) => Status;
  selected: string;
  select: (id: string) => void;
}) {
  const [labels, setLabels] = useState(false);
  const layout = useMemo(() => placeResources(resources), [resources]);
  const ids = new Set(resources.map((resource) => resource.id));
  const nodes: Node[] = layout.map(({ resource, position }) => {
    const state = status(resource.id);
    return {
      id: resource.id,
      position,
      data: {
        label: (
          <div className="twin-graph-label">
            <small>
              {resource.kind}
              {state !== "operational" && " · " + state}
            </small>
            <b>{resource.name}</b>
          </div>
        ),
      },
      className: "twin-graph-node",
      ariaLabel: resource.name + ", " + resource.kind + ", " + state,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      selected: resource.id === selected,
      style: { borderLeftColor: colors[state] },
    };
  });
  const edges: Edge[] = connections.flatMap(({ source, target, rule }) => {
    if (!ids.has(source) || !ids.has(target)) return [];
    const highlighted = source === selected || target === selected;
    const color =
      status(source) !== "operational"
        ? colors[status(source)]
        : highlighted
          ? "var(--teal)"
          : "var(--twin-edge)";
    return [
      {
        id: JSON.stringify([source, target, rule]),
        source,
        target,
        markerEnd: { type: MarkerType.ArrowClosed, color },
        label: labels ? rule : undefined,
        labelStyle: { fill: "var(--text)", fontSize: 11 },
        labelBgStyle: { fill: "var(--card)" },
        style: { stroke: color, strokeWidth: highlighted ? 2 : 1.4 },
      },
    ];
  });

  return (
    <section className="twin-graph" aria-label="Resource dependency graph">
      <div className="twin-graph-heading">
        <h2>Resource connections</h2>
        <label className="check">
          <input
            type="checkbox"
            checked={labels}
            onChange={(event) => setLabels(event.target.checked)}
          />
          Connection labels
        </label>
      </div>
      <div className="twin-graph-canvas">
        <ReactFlow
          key={JSON.stringify([...ids])}
          nodes={nodes}
          edges={edges}
          onNodesChange={(changes) => {
            const change = changes.find(
              (item) => item.type === "select" && item.selected,
            );
            if (change?.type === "select") select(change.id);
          }}
          fitView
          fitViewOptions={{ padding: 0.13, minZoom: 0.38, maxZoom: 1 }}
          minZoom={0.2}
          maxZoom={1.8}
          nodesDraggable={false}
          nodesConnectable={false}
          edgesFocusable={false}
          zoomOnScroll={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} color="var(--border)" />
          <Controls showInteractive={false} />
          <MiniMap
            nodeColor="var(--teal)"
            maskColor="var(--twin-map-mask)"
            pannable
            zoomable
          />
        </ReactFlow>
      </div>
    </section>
  );
}
