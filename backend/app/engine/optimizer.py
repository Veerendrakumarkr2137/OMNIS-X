"""Maximize the number of covered sessions, then minimize configured disruption."""

from time import monotonic
from ortools.sat.python import cp_model
from .validation import assignment, compatible, eligible, validate, workload
from .graph import overlaps


def explain_blocker(s, resources, outages):
    room_type = "Classroom" if s["kind"] == "Lecture" else "Laboratory"
    rooms = [
        r
        for r in resources.values()
        if r["kind"] == room_type
        and r["details"]["capacity"] >= resources[s["cohort"]]["details"]["size"]
        and set(s["needs"]) <= set(r["details"]["equipment"])
    ]
    if not rooms:
        return f"No {room_type.lower()} provides the required capacity and equipment ({', '.join(s['needs'])})."
    qualified = [
        r
        for r in resources.values()
        if r["kind"] == "Faculty"
        and r["dept"] == s["dept"]
        and s["subject"] in r["details"]["subjects"]
    ]
    if not qualified:
        return f"No faculty member in {s['dept']} is qualified to teach {s['subject']}."
    if s["protected"] and all(
        any(
            r["id"] in blocked
            and overlaps(s["start"], s["start"] + s["duration"], a, b)
            for blocked, a, b in outages
        )
        for r in rooms
    ):
        return (
            "Every compatible laboratory is offline at the protected examination time: "
            + ", ".join(r["name"] for r in rooms)
            + "."
        )
    return f"{len(qualified)} qualified faculty and {len(rooms)} compatible rooms were checked. Availability, workload and joint bookings prevent a complete assignment."


def candidates(s, fixed, resources, outages, settings):
    faculty = [
        r["id"]
        for r in resources.values()
        if r["kind"] == "Faculty"
        and r["dept"] == s["dept"]
        and s["subject"] in r["details"]["subjects"]
    ]
    rooms = [
        r["id"] for r in resources.values() if r["kind"] in ("Laboratory", "Classroom")
    ]
    starts = (
        [s["start"]] if s["protected"] else range(s["start"], 1081 - s["duration"], 30)
    )
    for t in starts:
        for f in faculty:
            for r in rooms:
                opt = {**s, "start": t, "faculty": f, "room": r}
                if (
                    eligible(s, opt, resources, outages)
                    and all(
                        compatible(opt, other, resources, settings["travel_minutes"])
                        for other in fixed
                    )
                    and workload([*fixed, opt], resources)
                ):
                    yield opt


def metrics(original, opt, resources, settings):
    delay = (opt["start"] - original["start"]) * resources[original["cohort"]][
        "details"
    ]["size"]
    room = int(opt["room"] != original["room"])
    sub = int(opt["faculty"] != original["faculty"])
    return (
        delay,
        room,
        sub,
        delay * settings["delay_weight"]
        + room * settings["room_weight"]
        + sub * settings["faculty_weight"],
    )


def solve(affected, fixed, resources, outages, settings):
    if not affected:
        return [], "No affected sessions"
    model = cp_model.CpModel()
    groups, assignments, intervals, loads = [], [], {}, {}
    costs, skips = [], []
    max_total = 0
    for original in affected:
        group = []
        penalties = []
        for option in candidates(original, fixed, resources, outages, settings):
            pick = model.new_bool_var("")
            interval = model.new_optional_fixed_size_interval_var(
                option["start"], option["duration"], pick, ""
            )
            for key in ("faculty", "cohort", "room"):
                intervals.setdefault(option[key], []).append(interval)
            loads.setdefault(option["faculty"], []).append(option["duration"] * pick)
            penalty = metrics(original, option, resources, settings)[3]
            costs.append(penalty * pick)
            penalties.append(penalty)
            group.append((pick, option))
        skip = model.new_bool_var("")
        group.append((skip, None))
        skips.append(skip)
        model.add_exactly_one(pick for pick, _ in group)
        groups.append(group)
        max_total += max(penalties, default=0)
    for values in intervals.values():
        model.add_no_overlap(values)
    for f, terms in loads.items():
        remaining = resources[f]["details"]["limit"] - sum(
            s["duration"] for s in fixed if s["faculty"] == f
        )
        model.add(sum(terms) <= remaining)
    model.minimize(sum(costs) + (max_total + 1) * sum(skips))
    deadline = monotonic() + 8
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    best_recovered = None
    search_status = "Time limit reached"
    while len(assignments) < 3 and monotonic() < deadline:
        solver.parameters.max_time_in_seconds = max(0.01, deadline - monotonic())
        status = solver.solve(model)
        search_status = {
            cp_model.OPTIMAL: "Optimal",
            cp_model.FEASIBLE: "Feasible",
            cp_model.INFEASIBLE: "Infeasible",
            cp_model.UNKNOWN: "Time limit reached"
            if monotonic() >= deadline - 0.05
            else "Unknown",
        }.get(status, "Unknown")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        selected = [
            next((v, o) for v, o in group if solver.value(v)) for group in groups
        ]
        model.add(sum(v for v, _ in selected) <= len(selected) - 1)
        changes = [
            {
                "id": s["id"],
                "subject": s["subject"],
                "cohort": s["cohort"],
                "duration": s["duration"],
                "before": assignment(s),
                "after": assignment(o) if o else None,
            }
            for s, (_, o) in zip(affected, selected)
        ]
        if not validate(affected, fixed, changes, resources, outages, settings):
            continue
        recovered = sum(o is not None for _, o in selected)
        if best_recovered is not None and recovered < best_recovered:
            break
        best_recovered = recovered
        delay, rooms, subs, penalty = [
            sum(x)
            for x in zip(
                *[
                    metrics(s, o, resources, settings) if o else (0, 0, 0, 0)
                    for s, (_, o) in zip(affected, selected)
                ]
            )
        ]
        assignments.append(
            {
                "changes": changes,
                "recovered": recovered,
                "unresolved": len(affected) - recovered,
                "students": sum(
                    resources[c]["details"]["size"]
                    for c in {s["cohort"] for s in affected}
                ),
                "delay": delay,
                "rooms": rooms,
                "subs": subs,
                "penalty": penalty,
                "violations": 0,
                "solver": "Optimal" if status == cp_model.OPTIMAL else "Feasible",
                "outcome": "Complete"
                if recovered == len(affected)
                else "Partial"
                if recovered
                else "Unrecoverable",
                "explanation": f"{recovered} of {len(affected)} sessions covered with {delay} student-minutes of delay, {rooms} room changes and {subs} substitutions.",
                "blockers": [
                    {
                        "session": s["id"],
                        "reason": explain_blocker(s, resources, outages),
                    }
                    for s, (_, o) in zip(affected, selected)
                    if o is None
                ],
            }
        )
        if recovered == 0:
            break
    assignments.sort(key=lambda entry: (-entry["recovered"], entry["penalty"]))
    return assignments, assignments[0]["solver"] if assignments else search_status
