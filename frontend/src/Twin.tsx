import { lazy, Suspense, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowUpRight,
  Building2,
  CalendarDays,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  GraduationCap,
  List,
  Network,
  Search,
  Users,
} from "lucide-react";
import { get, errorText } from "./api";
import { Empty, Pill } from "./ui";
import {
  pretty,
  time,
  type Campus,
  type Incident,
  type Resource,
  type Twin as TwinData,
} from "./types";

const TwinGraph = lazy(() => import("./TwinGraph"));

const groups = [
  { name: "Rooms & labs", kinds: ["Classroom", "Laboratory"], icon: Building2 },
  {
    name: "Infrastructure",
    kinds: ["Building", "Power", "Network", "Equipment"],
    icon: Network,
  },
  { name: "Faculty", kinds: ["Faculty"], icon: Users },
  { name: "Classes", kinds: ["Cohort", "Department"], icon: GraduationCap },
  {
    name: "Sessions",
    kinds: ["Academic session", "Examination"],
    icon: CalendarDays,
  },
];
const otherGroup = { name: "Other resources", kinds: [], icon: Network };
const statusLabels = {
  operational: "Operational",
  failed: "Failed",
  affected: "Affected",
};
const statusTones = { operational: "teal", failed: "red", affected: "amber" };

function groupFor(resource: Resource) {
  return (
    groups.find((group) => group.kinds.includes(resource.kind)) ?? otherGroup
  );
}

function buildModel(
  { cases: campusCases, lessons }: Pick<Campus, "cases" | "lessons">,
  data: TwinData,
  day: string,
  incident?: Incident,
) {
  const cases = incident
    ? [incident]
    : campusCases.filter(
        (item) => item.day <= day && day <= (item.impact.end_day || item.day),
      );
  const depths: Record<string, number> = Object.create(null);
  for (const item of cases) {
    for (const [id, depth] of Object.entries(item.impact.depths)) {
      depths[id] = Math.min(depths[id] ?? Infinity, depth);
    }
  }
  const sessions = lessons.filter((lesson) => lesson.day === day);
  const nodes: Resource[] = [...data.nodes];
  const edges = [...data.edges];
  for (const lesson of sessions) {
    nodes.push({
      id: lesson.id,
      name: lesson.subject,
      kind: lesson.kind === "Examination" ? "Examination" : "Academic session",
      dept: lesson.dept,
      details: {},
    });
    edges.push(
      {
        source: lesson.faculty,
        target: lesson.id,
        rule: "Requires a qualified instructor",
      },
      {
        source: lesson.room,
        target: lesson.id,
        rule: "Requires teaching space",
      },
      {
        source: lesson.id,
        target: lesson.cohort,
        rule: "Scheduled attendance",
      },
    );
    const affected = cases.some(
      (item) =>
        item.impact.sessions.includes(lesson.id) &&
        (item.simulation ||
          !["Recovered", "Partial recovery"].includes(item.status)),
    );
    if (affected) {
      const parentDepth = Math.min(
        depths[lesson.faculty] ?? Infinity,
        depths[lesson.room] ?? Infinity,
      );
      depths[lesson.id] = 1 + (Number.isFinite(parentDepth) ? parentDepth : 0);
      depths[lesson.cohort] = Math.min(
        depths[lesson.cohort] ?? Infinity,
        depths[lesson.id] + 1,
      );
    }
  }
  const status = (id: string) =>
    depths[id] === 0 ? "failed" : id in depths ? "affected" : "operational";
  return {
    nodes,
    edges,
    sessions,
    status,
    byId: new Map(nodes.map((node) => [node.id, node])),
  };
}

type Relation = { id: string; name: string; rule: string };

function Connections({
  title,
  incoming,
  rows,
  choose,
}: {
  title: string;
  incoming?: boolean;
  rows: Relation[];
  choose: (id: string) => void;
}) {
  const Icon = incoming ? ArrowDownRight : ArrowUpRight;
  return (
    <section className="twin-relation">
      <h4>
        <Icon size={16} aria-hidden="true" />
        {title}
      </h4>
      <ul>
        {rows.map((row) => (
          <li key={row.id}>
            <button className="twin-connection" onClick={() => choose(row.id)}>
              <span>
                <b>{row.name}</b>
                <small>{row.rule}</small>
              </span>
              <ChevronRight size={15} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Explorer({
  c,
  data,
  incident,
}: {
  c: Campus;
  data: TwinData;
  incident?: Incident;
}) {
  const [day, setDay] = useState(incident?.day ?? c.dash.today);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [department, setDepartment] = useState("");
  const [affectedOnly, setAffectedOnly] = useState(Boolean(incident));
  const [chosen, setChosen] = useState("");
  const [view, setView] = useState<"list" | "graph">("list");
  const detail = useRef<HTMLElement>(null);
  const { cases, lessons } = c;
  const { nodes, edges, sessions, status, byId } = useMemo(
    () => buildModel({ cases, lessons }, data, day, incident),
    [cases, lessons, data, day, incident],
  );
  const counts = { operational: 0, failed: 0, affected: 0 };
  for (const node of nodes) counts[status(node.id)]++;

  const departments = [
    ...new Set(nodes.flatMap((node) => (node.dept ? [node.dept] : []))),
  ].sort();
  const needle = search.trim().toLowerCase();
  const visible = nodes.filter(
    (node) =>
      (!category || groupFor(node).name === category) &&
      (!department || node.dept === department) &&
      (!affectedOnly || status(node.id) !== "operational") &&
      [node.name, node.kind, node.dept]
        .join(" ")
        .toLowerCase()
        .includes(needle),
  );
  const catalog = [...groups, otherGroup].map((group) => ({
    ...group,
    resources: visible
      .filter((node) => groupFor(node).name === group.name)
      .sort((a, b) => a.name.localeCompare(b.name)),
  }));
  const selected =
    visible.find((node) => node.id === chosen) ??
    (incident
      ? visible.find((node) => status(node.id) === "failed")
      : undefined) ??
    visible.find(
      (node) =>
        node.kind === "Classroom" &&
        sessions.some((lesson) => lesson.room === node.id),
    ) ??
    catalog.find((group) => group.resources.length)?.resources[0];
  const scheduled = selected
    ? sessions.filter((lesson) =>
        [lesson.faculty, lesson.room, lesson.cohort].includes(selected.id),
      )
    : [];
  const sessionIds = new Set(scheduled.map((lesson) => lesson.id));

  function related(incoming: boolean): Relation[] {
    if (!selected) return [];
    return edges
      .flatMap((edge) => {
        const endpoint = byId.get(incoming ? edge.source : edge.target);
        return (incoming ? edge.target : edge.source) === selected.id &&
          endpoint &&
          !sessionIds.has(endpoint.id)
          ? [{ id: endpoint.id, name: endpoint.name, rule: edge.rule }]
          : [];
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  function choose(id: string) {
    if (!visible.some((node) => node.id === id)) {
      setSearch("");
      setCategory("");
      setDepartment("");
      if (status(id) === "operational") setAffectedOnly(false);
    }
    setChosen(id);
    if (window.matchMedia("(max-width: 900px)").matches) {
      detail.current?.scrollIntoView({ block: "start" });
    }
  }

  const SelectedIcon = selected ? groupFor(selected).icon : Network;
  const dependencies = related(true);
  const dependents = related(false);
  return (
    <section className="panel twin-explorer" aria-label="Campus dependencies">
      <div className="twin-toolbar">
        <div
          className="segmented twin-views"
          role="group"
          aria-label="Digital twin view"
        >
          <button
            className={view === "list" ? "active" : ""}
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List size={16} aria-hidden="true" /> Resources
          </button>
          <button
            className={view === "graph" ? "active" : ""}
            aria-pressed={view === "graph"}
            onClick={() => setView("graph")}
          >
            <Network size={16} aria-hidden="true" /> Graph
          </button>
        </div>
        <label className="searchbox">
          <Search size={17} aria-hidden="true" />
          <input
            aria-label="Search resources"
            placeholder="Search rooms, people or classes"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <select
          aria-label="Resource category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="">All resource types</option>
          {[...groups, otherGroup]
            .filter(
              (group) =>
                nodes.some((node) => groupFor(node).name === group.name) ||
                category === group.name,
            )
            .map((group) => (
              <option key={group.name}>{group.name}</option>
            ))}
        </select>
        {departments.length > 1 && (
          <select
            aria-label="Department"
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
          >
            <option value="">All departments</option>
            {departments.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        )}
        {incident ? (
          <span className="twin-date">
            <CalendarDays size={16} />
            {pretty(day)}
          </span>
        ) : (
          <input
            type="date"
            aria-label="Campus model date"
            value={day}
            onChange={(event) =>
              event.target.value && setDay(event.target.value)
            }
          />
        )}
      </div>

      <div className="twin-statusbar">
        <div className="twin-summary" aria-label="Resource status">
          <span>
            <CircleCheck size={15} aria-hidden="true" />{" "}
            <b>{counts.operational}</b> operational
          </span>
          <span>
            <CircleAlert size={15} aria-hidden="true" /> <b>{counts.failed}</b>{" "}
            failed
          </span>
          <span>
            <Network size={15} aria-hidden="true" /> <b>{counts.affected}</b>{" "}
            affected
          </span>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={affectedOnly}
            onChange={(event) => setAffectedOnly(event.target.checked)}
          />{" "}
          Affected only
        </label>
      </div>

      {selected ? (
        <div
          className={
            view === "graph" ? "twin-body twin-graph-view" : "twin-body"
          }
        >
          {view === "graph" ? (
            <Suspense
              fallback={
                <p className="twin-graph" role="status">
                  Loading the graph…
                </p>
              }
            >
              <TwinGraph
                resources={visible}
                connections={edges}
                status={status}
                selected={selected.id}
                select={setChosen}
              />
            </Suspense>
          ) : (
            <div className="twin-catalog">
              <div className="twin-catalog-head">
                <h2>Resources</h2>
                <span>{visible.length}</span>
              </div>
              <div className="twin-catalog-list">
                {catalog
                  .filter((group) => group.resources.length > 0)
                  .map(({ name, icon: Icon, resources }) => (
                    <section key={name} className="twin-group">
                      <h3>{name}</h3>
                      <ul>
                        {resources.map((resource) => (
                          <li key={resource.id}>
                            <button
                              className="twin-resource"
                              aria-pressed={selected.id === resource.id}
                              onClick={() => choose(resource.id)}
                            >
                              <span className="twin-icon">
                                <Icon size={17} aria-hidden="true" />
                              </span>
                              <span className="twin-name">
                                <b>{resource.name}</b>
                                <small>
                                  {resource.kind}
                                  {status(resource.id) !== "operational" &&
                                    " · " + statusLabels[status(resource.id)]}
                                </small>
                              </span>
                              <ChevronRight size={16} aria-hidden="true" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ))}
              </div>
            </div>
          )}

          <section
            className="twin-detail"
            ref={detail}
            aria-label="Resource details"
          >
            <div className="twin-resource-header">
              <span className="twin-icon">
                <SelectedIcon size={25} aria-hidden="true" />
              </span>
              <div>
                <h2>{selected.name}</h2>
                <p>
                  {[
                    selected.kind,
                    selected.dept,
                    selected.details.capacity &&
                      `${selected.details.capacity} seats`,
                    selected.details.size &&
                      `${selected.details.size} students`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <Pill tone={statusTones[status(selected.id)]}>
                {statusLabels[status(selected.id)]}
              </Pill>
            </div>
            {(dependencies.length > 0 || dependents.length > 0) && (
              <div className="twin-relations">
                {dependencies.length > 0 && (
                  <Connections
                    title="Depends on"
                    incoming
                    rows={dependencies}
                    choose={choose}
                  />
                )}
                {dependents.length > 0 && (
                  <Connections
                    title="Supports"
                    rows={dependents}
                    choose={choose}
                  />
                )}
              </div>
            )}
            {scheduled.length > 0 && (
              <section className="twin-schedule">
                <h3>Sessions on {pretty(day)}</h3>
                <ul>
                  {scheduled.map((lesson) => (
                    <li key={lesson.id}>
                      <button
                        className="twin-connection"
                        onClick={() => choose(lesson.id)}
                      >
                        <time>
                          {time(lesson.start)}–
                          {time(lesson.start + lesson.duration)}
                        </time>
                        <b>{lesson.subject}</b>
                        <ChevronRight size={15} aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {!dependencies.length &&
              !dependents.length &&
              !scheduled.length && (
                <Empty>No connected resources or sessions for this date.</Empty>
              )}
          </section>
        </div>
      ) : (
        <Empty>
          {affectedOnly && !counts.failed && !counts.affected
            ? "No affected resources for this date."
            : "No resources match your filters."}
        </Empty>
      )}
    </section>
  );
}

export function Twin({ c, incident }: { c: Campus; incident?: Incident }) {
  const query = useQuery({
    queryKey: ["twin", c.user.id],
    queryFn: () => get<TwinData>("/digital-twin"),
  });
  const cascade = Object.entries(incident?.impact.depths ?? {}).sort(
    (a, b) => a[1] - b[1],
  );
  return (
    <>
      {!incident && (
        <div className="page-intro">
          <h1>Digital twin</h1>
          <p>Explore campus resources and see how they connect.</p>
        </div>
      )}
      {query.data ? (
        <Explorer
          key={incident?.id ?? "campus"}
          data={query.data}
          c={c}
          incident={incident}
        />
      ) : query.isError ? (
        <div role="alert" className="panel">
          <p>{errorText(query.error)}</p>
          <button className="secondary" onClick={() => query.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <p role="status">Loading the campus model…</p>
      )}
      {cascade.length > 0 && (
        <div className="cascade" aria-label="Impact sequence">
          {cascade.map(([id, depth]) => (
            <span key={id}>
              {depth ? "Impact " + depth : "Source"} · {c.name(id)}
            </span>
          ))}
        </div>
      )}
    </>
  );
}
