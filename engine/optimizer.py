from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from ortools.sat.python import cp_model

NORMAL_OV = 60
NORMAL_BIKE = 30
REGULAR_ROUNDS = ("J4", "LANG", "J2", "J1")
PROFILE_ROUND = "PROF"


def is_normal(route: dict[str, Any]) -> bool:
    ov = route.get("ov_minutes")
    bike = route.get("bike_minutes")
    return (ov is not None and ov <= NORMAL_OV) or (bike is not None and bike <= NORMAL_BIKE)


def best_travel_minutes(route: dict[str, Any]) -> int:
    vals = [v for v in (route.get("ov_minutes"), route.get("bike_minutes")) if v is not None]
    return min(vals) if vals else 999


def _route_index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(r["student_id"], r["school_id"]): r for r in payload.get("routes", [])}


def _blocks(payload: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (b["student_id"], b["school_id"])
        for b in payload.get("blocks", [])
        if b.get("active", True)
    }


def _active_schools(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in payload.get("schools", []) if s.get("active", True)]


def _solver(payload: dict[str, Any]) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(payload.get("max_solve_seconds", 30))
    solver.parameters.num_search_workers = int(payload.get("search_workers", 8))
    return solver


def _status_name(status: int) -> str:
    if status == cp_model.OPTIMAL:
        return "optimal"
    if status == cp_model.FEASIBLE:
        return "feasible"
    return "no_solution"


def _normal_reason(route: dict[str, Any]) -> str | None:
    if is_normal(route):
        return None
    return "OV>60_AND_BIKE>30"


def _candidate_scarcity(candidates: dict[str, list[str]]) -> dict[str, int]:
    """Higher score = school is depended on by more inflexible students."""
    scarcity: dict[str, int] = defaultdict(int)
    for school_ids in candidates.values():
        flexibility = max(1, len(school_ids))
        # 100/1, 100/2, 100/3 ... gives scarce dependencies more weight.
        contribution = max(1, 100 // flexibility)
        for school_id in school_ids:
            scarcity[school_id] += contribution
    return scarcity


def _objective_score(
    route: dict[str, Any],
    school_id: str,
    scarcity: dict[str, int],
    max_lower_total: int,
) -> int:
    """Safe lexicographic-style score: placement > normal > travel > reserve preservation."""
    normal_bonus = 100_000 if is_normal(route) else 0
    travel_penalty = best_travel_minutes(route) * 100
    scarcity_penalty = scarcity.get(school_id, 0)
    # This term is set by caller large enough that one extra placement always wins.
    return max_lower_total + normal_bonus - travel_penalty - scarcity_penalty


def solve_regular_round(payload: dict[str, Any]) -> dict[str, Any]:
    round_type = payload["round"]
    if round_type not in REGULAR_ROUNDS:
        raise ValueError(f"Regular round must be one of {REGULAR_ROUNDS}; got {round_type!r}")

    cap_key = {"J1": "capacity_j1", "J2": "capacity_j2", "J4": "capacity_j4", "LANG": "capacity_lang"}[round_type]
    students = [
        s for s in payload.get("students", [])
        if s.get("category") == round_type and s.get("active", True)
    ]
    schools = _active_schools(payload)
    routes = _route_index(payload)
    blocked = _blocks(payload)

    # Optional locked placements from earlier/approved work consume capacity but never move.
    locked_usage: dict[str, int] = defaultdict(int)
    for p in payload.get("locked_placements", []):
        if p.get("round") == round_type and p.get("active", True):
            locked_usage[p["school_id"]] += 1

    candidates: dict[str, list[str]] = defaultdict(list)
    excluded: dict[str, list[dict[str, str]]] = defaultdict(list)
    for st in students:
        sid = st["student_id"]
        for sc in schools:
            scid = sc["school_id"]
            pair = (sid, scid)
            remaining = int(sc.get(cap_key, 0)) - locked_usage[scid]
            if pair in blocked:
                excluded[sid].append({"school_id": scid, "reason": "BLOCKED"})
                continue
            if remaining <= 0:
                excluded[sid].append({"school_id": scid, "reason": "NO_CAPACITY"})
                continue
            if pair not in routes:
                excluded[sid].append({"school_id": scid, "reason": "NO_ROUTE"})
                continue
            candidates[sid].append(scid)

    scarcity = _candidate_scarcity(candidates)
    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    for sid, scids in candidates.items():
        for scid in scids:
            x[(sid, scid)] = model.NewBoolVar(f"x_{sid}_{scid}")

    for st in students:
        sid = st["student_id"]
        vars_ = [x[(sid, scid)] for scid in candidates.get(sid, [])]
        if vars_:
            model.Add(sum(vars_) <= 1)

    for sc in schools:
        scid = sc["school_id"]
        vars_ = [var for (sid, school_id), var in x.items() if school_id == scid]
        remaining = max(0, int(sc.get(cap_key, 0)) - locked_usage[scid])
        if vars_:
            model.Add(sum(vars_) <= remaining)

    # Bound lower-priority effects so +1 placement always dominates every lower-order choice.
    n = max(1, len(students))
    max_lower_total = n * 300_000 + 1
    terms = []
    for (sid, scid), var in x.items():
        terms.append(_objective_score(routes[(sid, scid)], scid, scarcity, max_lower_total) * var)
    model.Maximize(sum(terms))

    solver = _solver(payload)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "no_solution", "round": round_type}

    placements: list[dict[str, Any]] = []
    used: dict[str, int] = defaultdict(int)
    placed_ids: set[str] = set()
    for (sid, scid), var in x.items():
        if solver.Value(var):
            route = routes[(sid, scid)]
            normal = is_normal(route)
            placements.append({
                "student_id": sid,
                "school_id": scid,
                "ov_minutes": route.get("ov_minutes"),
                "bike_minutes": route.get("bike_minutes"),
                "normal_reachability": normal,
                "human_review": not normal,
                "review_reason": _normal_reason(route),
            })
            used[scid] += 1
            placed_ids.add(sid)

    unplaced = _build_unplaced(students, placed_ids, candidates, routes, excluded)
    remaining_capacity, reserves = _remaining_and_reserve(
        schools, cap_key, used, locked_usage, scarcity
    )

    return {
        "engine_version": "0.2",
        "status": _status_name(status),
        "round": round_type,
        "total_students": len(students),
        "placed": len(placements),
        "placement_percentage": round(len(placements) / len(students) * 100, 1) if students else 100.0,
        "placements": sorted(placements, key=lambda p: p["student_id"]),
        "human_review": [p for p in placements if p["human_review"]],
        "unplaced": unplaced,
        "remaining_capacity": remaining_capacity,
        "strategic_reserve_candidates": reserves,
    }


def _build_unplaced(
    students: Iterable[dict[str, Any]],
    placed_ids: set[str],
    candidates: dict[str, list[str]],
    routes: dict[tuple[str, str], dict[str, Any]],
    excluded: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    result = []
    for st in students:
        sid = st["student_id"]
        if sid in placed_ids:
            continue
        alts = []
        for scid in candidates.get(sid, []):
            route = routes[(sid, scid)]
            alts.append({
                "school_id": scid,
                "ov_minutes": route.get("ov_minutes"),
                "bike_minutes": route.get("bike_minutes"),
                "normal_reachability": is_normal(route),
            })
        alts.sort(key=lambda a: (not a["normal_reachability"], min(a.get("ov_minutes") or 999, a.get("bike_minutes") or 999)))
        result.append({
            "student_id": sid,
            "review_reason": "NO_VALID_PLACEMENT",
            "alternatives": alts[:3],
            "excluded": excluded.get(sid, [])[:10],
        })
    return result


def _remaining_and_reserve(
    schools: list[dict[str, Any]],
    cap_key: str,
    used: dict[str, int],
    locked_usage: dict[str, int],
    scarcity: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = []
    reserves = []
    for sc in schools:
        scid = sc["school_id"]
        capacity = int(sc.get(cap_key, 0))
        rem = max(0, capacity - locked_usage[scid] - used[scid])
        item = {
            "school_id": scid,
            "capacity": capacity,
            "locked_usage": locked_usage[scid],
            "new_usage": used[scid],
            "remaining": rem,
        }
        remaining.append(item)
        if rem > 0 and scarcity.get(scid, 0) > 0:
            reserves.append({
                "school_id": scid,
                "remaining": rem,
                "scarcity_score": scarcity[scid],
            })
    reserves.sort(key=lambda z: (-z["scarcity_score"], z["school_id"]))
    return remaining, reserves


def solve_profile_round(payload: dict[str, Any]) -> dict[str, Any]:
    """Solve one profiling semester. Each student/profile requirement is a separate placement unit."""
    semester = payload.get("semester")
    if semester not in ("S1", "S2"):
        raise ValueError("Profile round requires semester S1 or S2")

    active_students = {s["student_id"] for s in payload.get("students", []) if s.get("active", True)}
    routes = _route_index(payload)
    blocked = _blocks(payload)
    schools = {s["school_id"]: s for s in _active_schools(payload)}

    requirements = [
        p for p in payload.get("student_profiles", [])
        if p.get("active", True) and p.get("semester") == semester and p.get("student_id") in active_students
    ]
    # Enforce max 2 per student per semester.
    counts: dict[str, int] = defaultdict(int)
    for req in requirements:
        counts[req["student_id"]] += 1
    offenders = [sid for sid, count in counts.items() if count > 2]
    if offenders:
        raise ValueError(f"Max 2 profiles per student per semester exceeded: {offenders}")

    capacities: dict[tuple[str, str], int] = defaultdict(int)
    for pc in payload.get("profile_capacity", []):
        if not pc.get("active", True) or pc.get("semester") != semester:
            continue
        if pc["school_id"] in schools:
            capacities[(pc["school_id"], pc["profile_id"])] += int(pc.get("capacity", 0))

    units: list[dict[str, str]] = []
    for i, req in enumerate(requirements):
        units.append({
            "unit_id": req.get("unit_id") or f'{req["student_id"]}:{semester}:{req["profile_id"]}:{i}',
            "student_id": req["student_id"],
            "profile_id": req["profile_id"],
        })

    candidates: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        sid = unit["student_id"]
        pid = unit["profile_id"]
        for scid in schools:
            if capacities[(scid, pid)] <= 0:
                continue
            if (sid, scid) in blocked or (sid, scid) not in routes:
                continue
            candidates[unit["unit_id"]].append(scid)

    scarcity = _candidate_scarcity(candidates)
    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    for uid, scids in candidates.items():
        for scid in scids:
            x[(uid, scid)] = model.NewBoolVar(f"p_{uid}_{scid}")

    for unit in units:
        uid = unit["unit_id"]
        vars_ = [x[(uid, scid)] for scid in candidates.get(uid, [])]
        if vars_:
            model.Add(sum(vars_) <= 1)

    unit_by_id = {u["unit_id"]: u for u in units}
    for (scid, pid), cap in capacities.items():
        vars_ = [
            var for (uid, school_id), var in x.items()
            if school_id == scid and unit_by_id[uid]["profile_id"] == pid
        ]
        if vars_:
            model.Add(sum(vars_) <= cap)

    n = max(1, len(units))
    max_lower_total = n * 300_000 + 1
    terms = []
    for (uid, scid), var in x.items():
        sid = unit_by_id[uid]["student_id"]
        terms.append(_objective_score(routes[(sid, scid)], scid, scarcity, max_lower_total) * var)
    model.Maximize(sum(terms))

    solver = _solver(payload)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "no_solution", "round": PROFILE_ROUND, "semester": semester}

    placements = []
    placed_units = set()
    used: dict[tuple[str, str], int] = defaultdict(int)
    for (uid, scid), var in x.items():
        if solver.Value(var):
            unit = unit_by_id[uid]
            route = routes[(unit["student_id"], scid)]
            normal = is_normal(route)
            placements.append({
                "unit_id": uid,
                "student_id": unit["student_id"],
                "semester": semester,
                "profile_id": unit["profile_id"],
                "school_id": scid,
                "ov_minutes": route.get("ov_minutes"),
                "bike_minutes": route.get("bike_minutes"),
                "normal_reachability": normal,
                "human_review": not normal,
                "review_reason": _normal_reason(route),
            })
            used[(scid, unit["profile_id"])] += 1
            placed_units.add(uid)

    unplaced = []
    for unit in units:
        if unit["unit_id"] in placed_units:
            continue
        alts = []
        for scid in candidates.get(unit["unit_id"], []):
            r = routes[(unit["student_id"], scid)]
            alts.append({
                "school_id": scid,
                "ov_minutes": r.get("ov_minutes"),
                "bike_minutes": r.get("bike_minutes"),
                "normal_reachability": is_normal(r),
            })
        alts.sort(key=lambda a: (not a["normal_reachability"], best_travel_minutes(a)))
        unplaced.append({**unit, "review_reason": "NO_PROFILE_CAPACITY_OR_ROUTE", "alternatives": alts[:3]})

    remaining = []
    for (scid, pid), cap in sorted(capacities.items()):
        remaining.append({
            "school_id": scid,
            "semester": semester,
            "profile_id": pid,
            "capacity": cap,
            "used": used[(scid, pid)],
            "remaining": cap - used[(scid, pid)],
        })

    return {
        "engine_version": "0.2",
        "status": _status_name(status),
        "round": PROFILE_ROUND,
        "semester": semester,
        "total_profile_requirements": len(units),
        "placed": len(placements),
        "placement_percentage": round(len(placements) / len(units) * 100, 1) if units else 100.0,
        "placements": sorted(placements, key=lambda p: (p["student_id"], p["profile_id"])),
        "human_review": [p for p in placements if p["human_review"]],
        "unplaced": unplaced,
        "remaining_profile_capacity": remaining,
    }


def solve_replacement(payload: dict[str, Any], student_id: str) -> dict[str, Any]:
    """Re-place one student while preserving all other active placements as locked capacity."""
    work = deepcopy(payload)
    round_type = work["round"]
    work["students"] = [s for s in work.get("students", []) if s.get("student_id") == student_id]
    locked = []
    for p in work.get("current_placements", []):
        if p.get("student_id") != student_id and p.get("active", True):
            locked.append({"student_id": p["student_id"], "school_id": p["school_id"], "round": round_type, "active": True})
    work["locked_placements"] = locked
    result = solve_regular_round(work)
    result["mode"] = "replacement"
    result["replacement_student_id"] = student_id
    return result


def solve_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("round") == PROFILE_ROUND:
        return solve_profile_round(payload)
    return solve_regular_round(payload)


def solve_file(input_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    result = solve_payload(data)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="StagePlaatser Engine v0.2")
    parser.add_argument("input", help="JSON input file")
    parser.add_argument("--output", default="output/result.json")
    args = parser.parse_args()
    print(json.dumps(solve_file(args.input, args.output), indent=2))
