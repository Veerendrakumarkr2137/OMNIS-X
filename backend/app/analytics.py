import networkx as nx
from .engine.validation import compatible, workload


def risks_and_score(resources, sessions, cases, g):
    risks = []
    faculty = [r for r in resources.values() if r["kind"] == "Faculty"]
    rooms = [r for r in resources.values() if r["kind"] in ("Laboratory", "Classroom")]
    active = [s for s in sessions if s["status"] != "Unresolved"]
    violations = set()
    redundant, coverage = 0, 0
    for s in active:
        size = resources[s["cohort"]]["details"]["size"]
        suitable = [
            r
            for r in rooms
            if r["kind"] == resources[s["room"]]["kind"]
            and r["details"]["capacity"] >= size
            and set(s["needs"]) <= set(r["details"]["equipment"])
        ]
        if s["room"] not in {r["id"] for r in suitable}:
            violations.add(s["id"])
        if len(suitable) > 1:
            redundant += 1
        elif s["kind"] != "Lecture":
            risks.append(
                {
                    "title": "Single compatible laboratory",
                    "detail": s["subject"] + " · " + resources[s["room"]]["name"],
                    "severity": "High",
                }
            )
        backups = [
            r
            for r in faculty
            if r["id"] != s["faculty"]
            and r["dept"] == s["dept"]
            and s["subject"] in r["details"]["subjects"]
        ]
        coverage += bool(backups)
        if not backups:
            risks.append(
                {
                    "title": "No qualified substitute",
                    "detail": s["subject"],
                    "severity": "High",
                }
            )
    for i, s in enumerate(active):
        peers = [o for o in active[i + 1 :] if o["day"] == s["day"]]
        for o in peers:
            if not compatible(s, o, resources, 0):
                violations.update((s["id"], o["id"]))
        same_day = [
            o for o in active if o["day"] == s["day"] and o["faculty"] == s["faculty"]
        ]
        if not workload(same_day, resources):
            violations.add(s["id"])
    if violations:
        risks.append(
            {
                "title": "Timetable constraints require review",
                "detail": f"{len(violations)} sessions",
                "severity": "Critical",
            }
        )
    settled = [
        c
        for c in cases
        if c.status in ("Recovered", "Partial recovery", "Needs intervention")
    ]
    n = len(active)
    power_sources = {r["id"] for r in resources.values() if r["kind"] == "Power"}
    modeled = [nx.ancestors(g, r["id"]) & power_sources for r in rooms]
    powered = [sources for sources in modeled if sources]
    for power in sorted(power_sources):
        dependent = sum(sources == {power} for sources in powered)
        if dependent:
            risks.append(
                {
                    "title": "Single power supply",
                    "detail": resources[power]["name"]
                    + f" · {dependent} teaching spaces",
                    "severity": "Medium",
                }
            )
    factors = {
        "Room redundancy": round(100 * redundant / n) if n else None,
        "Qualified backup": round(100 * coverage / n) if n else None,
        "Schedule compliance": round(100 * (1 - len(violations) / n)) if n else None,
        "Recovery success": round(
            100 * sum(c.status == "Recovered" for c in settled) / len(settled)
        )
        if settled
        else None,
        "Independent power": round(
            100 * sum(len(sources) > 1 for sources in powered) / len(powered)
        )
        if powered
        else None,
    }
    unique = {(r["title"], r["detail"]): r for r in risks}
    measured = [v for v in factors.values() if v is not None]
    return (
        list(unique.values()),
        factors,
        round(sum(measured) / len(measured)) if measured else None,
    )
