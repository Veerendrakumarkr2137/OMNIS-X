import networkx as nx
from ..database import Dependency, Resource, fields, rows


def inventory(db):
    return {r.id: fields(r, "id name kind dept details") for r in rows(db, Resource)}


def graph(db):
    g = nx.DiGraph()
    g.add_nodes_from(r.id for r in rows(db, Resource))
    for edge in rows(db, Dependency):
        g.add_edge(edge.source, edge.target, rule=edge.rule)
    return g


def propagation(g, roots):
    distance = nx.multi_source_dijkstra_path_length(g, roots, weight=None)
    return dict(sorted(distance.items(), key=lambda pair: (pair[1], pair[0])))


def overlaps(start, end, other_start, other_end):
    return start < other_end and other_start < end


def analyze(g, resources, lessons, roots, start, end):
    depths = propagation(g, roots)
    affected = [
        s
        for s in lessons
        if s["status"] != "Unresolved"
        and overlaps(s["start"], s["start"] + s["duration"], start, end)
        and (s["room"] in depths or s["faculty"] in depths)
    ]
    cohorts = sorted({s["cohort"] for s in affected})
    return {
        "depths": depths,
        "sessions": [s["id"] for s in affected],
        "cohorts": cohorts,
        "students": sum(resources[c]["details"]["size"] for c in cohorts),
        "student_sessions": sum(
            resources[s["cohort"]]["details"]["size"] for s in affected
        ),
        "departments": sorted(
            {s["dept"] for s in affected}
            | {resources[r]["dept"] for r in roots if resources[r]["dept"]}
        ),
        "exams": sum(s["kind"] == "Examination" for s in affected),
        "minutes": end - start,
    }
