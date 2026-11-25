from datetime import date
from .graph import cohort_members, cohort_size, overlaps


def assignment(s):
    return {k: s[k] for k in ("faculty", "room", "start")}


def compatible(a, b, resources, travel):
    if a["day"] != b["day"]:
        return True
    a_end, b_end = a["start"] + a["duration"], b["start"] + b["duration"]
    shared_person = a["faculty"] == b["faculty"] or bool(
        cohort_members(a["cohort"], resources) & cohort_members(b["cohort"], resources)
    )
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


def eligible(original, s, resources, outages, settings=None):
    f, r = resources[s["faculty"]], resources[s["room"]]
    start, end = s["start"], s["start"] + s["duration"]
    if (
        f["kind"] != "Faculty"
        or (
            f["dept"] != s["dept"]
            and not (
                s["faculty"] == original["faculty"]
                and s["day"]
                < f["details"].get("former_departments", {}).get(s["dept"], "")
            )
        )
        or s["subject"] not in f["details"]["subjects"]
        or (
            s["faculty"] != original["faculty"]
            and settings is not None
            and not settings.get("allow_substitution", False)
        )
    ):
        return False
    if r["kind"] != ("Classroom" if s["kind"] == "Lecture" else "Laboratory"):
        return False
    if r["details"]["capacity"] < cohort_size(s["cohort"], resources) or not set(
        s["needs"]
    ).issubset(r["details"]["equipment"]):
        return False
    if (
        not 480 <= start < end <= 1080
        or s["duration"] != original["duration"]
        or (
            original["protected"]
            and (start != original["start"] or s["day"] != original["day"])
        )
    ):
        return False
    lo, hi = f["details"]["available"]
    if settings and settings.get("teaching_windows"):
        windows = settings["teaching_windows"]
        saturday_end = settings.get("saturday_end")
        if (
            saturday_end
            and date.fromisoformat(s["day"]).weekday() == 5
            and end > saturday_end
        ):
            return False
        if not any(a <= start and end <= b for a, b in windows):
            return False
    return (
        lo <= start
        and end <= hi
        and all(
            not (
                (
                    {s["faculty"], s["room"], s["id"]}
                    | cohort_members(s["cohort"], resources)
                )
                & blocked
                and overlaps(start, end, a, b)
            )
            for blocked, a, b in (
                outages.get(s["day"], ()) if isinstance(outages, dict) else outages
            )
        )
    )


def workload(sessions, resources):
    by_faculty = {}
    for s in sessions:
        by_faculty.setdefault((s["faculty"], s["day"]), []).append(
            (s["start"], s["start"] + s["duration"])
        )
    for (faculty, _), slots in by_faculty.items():
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
        if set(c["after"]) not in (
            {"faculty", "room", "start"},
            {"faculty", "room", "start", "day"},
        ):
            return False
        scheduled = {**orig, **c["after"]}
        if scheduled["day"] != orig["day"] and scheduled["day"] not in settings.get(
            "recovery_days", ()
        ):
            return False
        if not eligible(orig, scheduled, resources, outages, settings):
            return False
        if any(
            not compatible(scheduled, other, resources, settings["travel_minutes"])
            for other in chosen
        ):
            return False
        chosen.append(scheduled)
    return workload(chosen, resources)
