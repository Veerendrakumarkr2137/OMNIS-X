from .graph import overlaps


def assignment(s):
    return {k: s[k] for k in ("faculty", "room", "start")}


def compatible(a, b, resources, travel):
    a_end, b_end = a["start"] + a["duration"], b["start"] + b["duration"]
    shared_person = a["faculty"] == b["faculty"] or a["cohort"] == b["cohort"]
    if (shared_person or a["room"] == b["room"]) and overlaps(
        a["start"], a_end, b["start"], b_end
    ):
        return False
    if (
        travel
        and shared_person
        and resources[a["room"]]["details"]["building"]
        != resources[b["room"]]["details"]["building"]
    ):
        return a_end + travel <= b["start"] or b_end + travel <= a["start"]
    return True


def eligible(original, s, resources, outages):
    f, r = resources[s["faculty"]], resources[s["room"]]
    start, end = s["start"], s["start"] + s["duration"]
    if (
        f["kind"] != "Faculty"
        or f["dept"] != s["dept"]
        or s["subject"] not in f["details"]["subjects"]
    ):
        return False
    if r["kind"] != ("Classroom" if s["kind"] == "Lecture" else "Laboratory"):
        return False
    if r["details"]["capacity"] < resources[s["cohort"]]["details"]["size"] or not set(
        s["needs"]
    ).issubset(r["details"]["equipment"]):
        return False
    if (
        not 480 <= start < end <= 1080
        or s["duration"] != original["duration"]
        or (original["protected"] and start != original["start"])
    ):
        return False
    lo, hi = f["details"]["available"]
    return (
        lo <= start
        and end <= hi
        and all(
            not ({s["faculty"], s["room"]} & blocked and overlaps(start, end, a, b))
            for blocked, a, b in outages
        )
    )


def workload(sessions, resources):
    by_faculty = {}
    for s in sessions:
        by_faculty.setdefault(s["faculty"], []).append(
            (s["start"], s["start"] + s["duration"])
        )
    for faculty, slots in by_faculty.items():
        limits = resources[faculty]["details"]
        if sum(end - start for start, end in slots) > limits["limit"]:
            return False
        previous, consecutive = -1, 0
        for start, end in sorted(slots):
            consecutive = end - start + (consecutive if start == previous else 0)
            if consecutive > limits["consecutive"]:
                return False
            previous = end
    return True


def validate(affected, fixed, changes, resources, outages, settings):
    if {c["id"] for c in changes} != {s["id"] for s in affected} or len(changes) != len(
        affected
    ):
        return False
    origins = {s["id"]: s for s in affected}
    chosen = list(fixed)
    for c in changes:
        orig = origins[c["id"]]
        if c["before"] != assignment(orig):
            return False
        if c["after"] is None:
            continue
        if set(c["after"]) != {"faculty", "room", "start"}:
            return False
        scheduled = {**orig, **c["after"]}
        if not eligible(orig, scheduled, resources, outages):
            return False
        if any(
            not compatible(scheduled, other, resources, settings["travel_minutes"])
            for other in chosen
        ):
            return False
        chosen.append(scheduled)
    return workload(chosen, resources)
