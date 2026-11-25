"""Maximize the number of covered sessions, then minimize configured disruption."""

from time import monotonic
from datetime import date
from ortools.sat.python import cp_model
from .validation import assignment, compatible, eligible, validate, workload
from .graph import cohort_members, cohort_size, overlaps, unique_students


def explain_blocker(s, resources, outages):
    day_outages = outages.get(s["day"], ()) if isinstance(outages, dict) else outages
    room_type = "Classroom" if s["kind"] == "Lecture" else "Laboratory"
    rooms = [
        r
        for r in resources.values()
        if r["kind"] == room_type
        and r["details"]["capacity"] >= cohort_size(s["cohort"], resources)
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
            for blocked, a, b in day_outages
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
        and (r["id"] == s["faculty"] or settings.get("allow_substitution", False))
    ]
    rooms = [
        r["id"] for r in resources.values() if r["kind"] in ("Laboratory", "Classroom")
    ]
    days = (
        [s["day"]]
        if s["protected"]
        else [s["day"], *(d for d in settings.get("recovery_days", ()) if d > s["day"])]
    )
    slots = (
        (day, start)
        for day in days
        for start in (
            [s["start"]]
            if s["protected"]
            else range(s["start"] if day == s["day"] else 480, 1081 - s["duration"], 30)
        )
    )
    for day, t in slots:
        for f in faculty:
            for r in rooms:
                opt = {**s, "day": day, "start": t, "faculty": f, "room": r}
                if (
                    eligible(s, opt, resources, outages, settings)
                    and all(
                        compatible(opt, other, resources, settings["travel_minutes"])
                        for other in fixed
                    )
                    and workload([*fixed, opt], resources)
                ):
                    yield opt


def metrics(original, opt, resources, settings):
    days = (date.fromisoformat(opt["day"]) - date.fromisoformat(original["day"])).days
    delay = abs(days * 1440 + opt["start"] - original["start"]) * cohort_size(
        original["cohort"], resources
    )
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


def swap_alternatives(affected, fixed, resources, outages, settings):
    """Try an exchange within one section while preserving both instructors."""
    if len(affected) != 1 or affected[0]["protected"]:
        return []
    original = affected[0]
    alternatives = []
    for partner in fixed:
        if (
            partner["protected"]
            or partner["day"] != original["day"]
            or partner["dept"] != original["dept"]
            or partner["cohort"] != original["cohort"]
            or partner["duration"] != original["duration"]
            or partner["start"] <= original["start"]
        ):
            continue
        first = {**original, "start": partner["start"], "room": partner["room"]}
        second = {**partner, "start": original["start"], "room": original["room"]}
        changes = [
            {
                **{
                    key: before[key]
                    for key in ("id", "day", "subject", "cohort", "duration")
                },
                "before": assignment(before),
                "after": assignment(after),
            }
            for before, after in ((original, first), (partner, second))
        ]
        unused = [s for s in fixed if s["id"] != partner["id"]]
        if not validate(
            [original, partner], unused, changes, resources, outages, settings
        ):
            continue
        delay, rooms, subs, penalty = (
            first_cost + second_cost
            for first_cost, second_cost in zip(
                metrics(original, first, resources, settings),
                metrics(partner, second, resources, settings),
            )
        )
        alternatives.append(
            {
                "changes": changes,
                "recovered": 1,
                "unresolved": 0,
                "swap": partner["id"],
                "students": cohort_size(original["cohort"], resources),
                "delay": delay,
                "rooms": rooms,
                "subs": subs,
                "penalty": penalty,
                "violations": 0,
                "solver": "Feasible",
                "outcome": "Complete",
                "explanation": "The two subjects exchange class slots. Both retain their assigned instructor.",
                "blockers": [],
            }
        )
    return alternatives


def solve(affected, fixed, resources, outages, settings):
    if not affected:
        return [], "No affected sessions"
    model = cp_model.CpModel()
    groups, assignments, intervals, loads = [], [], {}, {}
    costs, skips = [], []
    max_total = 0
    pruned = False
    for original in affected:
        group = []
        penalties = []
        options = list(candidates(original, fixed, resources, outages, settings))
        if len(settings.get("recovery_days", ())) > 1:
            by_day = {}
            for option in options:
                by_day.setdefault(option["day"], []).append(option)
            options = []
            for daily in by_day.values():
                daily.sort(
                    key=lambda option: metrics(original, option, resources, settings)[3]
                )
                pruned = pruned or len(daily) > 72
                options.extend(daily[:72])
        options.sort(
            key=lambda option: metrics(original, option, resources, settings)[3]
        )
        for option in options:
            pick = model.new_bool_var("")
            interval = model.new_optional_fixed_size_interval_var(
                option["start"], option["duration"], pick, ""
            )
            for key in ("faculty", "room"):
                intervals.setdefault((option["day"], option[key]), []).append(interval)
            for batch in cohort_members(option["cohort"], resources):
                intervals.setdefault((option["day"], batch), []).append(interval)
            loads.setdefault((option["faculty"], option["day"]), []).append(
                option["duration"] * pick
            )
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
    for (f, day), terms in loads.items():
        remaining = resources[f]["details"]["limit"] - sum(
            s["duration"] for s in fixed if s["faculty"] == f and s["day"] == day
        )
        model.add(sum(terms) <= remaining)
    model.minimize(sum(costs) + (max_total + 1) * sum(skips))
    # Give the solver a constraint-checked incumbent before searching the multi-day model.
    greedy = []
    occupied = list(fixed)
    for group in groups:
        selected = next(
            (
                (pick, option)
                for pick, option in group
                if option
                and all(
                    compatible(option, other, resources, settings["travel_minutes"])
                    for other in occupied
                )
                and workload([*occupied, option], resources)
            ),
            group[-1],
        )
        greedy.append(selected)
        if selected[1]:
            occupied.append(selected[1])
        for pick, _ in group:
            model.add_hint(pick, int(pick is selected[0]))
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
        fallback = not assignments and status not in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        )
        if not fallback and status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        selected = (
            greedy
            if fallback
            else [next((v, o) for v, o in group if solver.value(v)) for group in groups]
        )
        model.add(sum(v for v, _ in selected) <= len(selected) - 1)
        model.clear_hints()
        changes = [
            {
                "id": s["id"],
                "subject": s["subject"],
                "cohort": s["cohort"],
                "duration": s["duration"],
                "before": assignment(s),
                "day": s["day"],
                "after": {
                    **assignment(o),
                    **({"day": o["day"]} if s["day"] != o["day"] else {}),
                }
                if o
                else None,
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
                "students": unique_students({s["cohort"] for s in affected}, resources),
                "delay": delay,
                "rooms": rooms,
                "subs": subs,
                "penalty": penalty,
                "violations": 0,
                "solver": "Optimal"
                if status == cp_model.OPTIMAL and not pruned
                else "Feasible",
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
        if recovered == 0 or fallback:
            break
    assignments.sort(key=lambda entry: (-entry["recovered"], entry["penalty"]))
    return assignments, assignments[0]["solver"] if assignments else search_status
