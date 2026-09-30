from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ortools.sat.python import cp_model

NORMAL_OV = 60
NORMAL_BIKE = 30


def is_normal(route: dict[str, Any]) -> bool:
    ov = route.get("ov_minutes")
    bike = route.get("bike_minutes")
    return (ov is not None and ov <= NORMAL_OV) or (bike is not None and bike <= NORMAL_BIKE)


def travel_cost(route: dict[str, Any]) -> int:
    """Cost of the best usable mode; lower is better."""
    vals = []
    ov = route.get("ov_minutes")
    bike = route.get("bike_minutes")
    if ov is not None:
        vals.append(ov)
    if bike is not None:
        vals.append(bike)
    return min(vals) if vals else 999


def solve_round(payload: dict[str, Any]) -> dict[str, Any]:
    round_type = payload["round"]
    students = [s for s in payload["students"] if s["category"] == round_type and s.get("active", True)]
    schools = [s for s in payload["schools"] if s.get("active", True)]
    blocked = {(b["student_id"], b["school_id"]) for b in payload.get("blocks", []) if b.get("active", True)}
    routes = {(r["student_id"], r["school_id"]): r for r in payload.get("routes", [])}

    cap_key = {"J1": "capacity_j1", "J2": "capacity_j2", "J4": "capacity_j4", "LANG": "capacity_lang"}[round_type]

    candidates: dict[str, list[str]] = defaultdict(list)
    for st in students:
        for sc in schools:
            pair = (st["student_id"], sc["school_id"])
            if pair in blocked or int(sc.get(cap_key, 0)) <= 0 or pair not in routes:
                continue
            candidates[st["student_id"]].append(sc["school_id"])

    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    for sid, school_ids in candidates.items():
        for scid in school_ids:
            x[(sid, scid)] = model.NewBoolVar(f"x_{sid}_{scid}")

    # Every student gets at most one placement.
    for st in students:
        vars_ = [x[(st["student_id"], scid)] for scid in candidates.get(st["student_id"], [])]
        if vars_:
            model.Add(sum(vars_) <= 1)

    # School capacity.
    for sc in schools:
        vars_ = [var for (sid, scid), var in x.items() if scid == sc["school_id"]]
        if vars_:
            model.Add(sum(vars_) <= int(sc.get(cap_key, 0)))

    # Lexicographic-like weighted objective:
    # 1) place as many as possible; 2) normal reachability; 3) lower travel time.
    objective_terms = []
    for (sid, scid), var in x.items():
        route = routes[(sid, scid)]
        score = 1_000_000
        if is_normal(route):
            score += 10_000
        score -= travel_cost(route) * 10
        objective_terms.append(score * var)
    model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(payload.get("max_solve_seconds", 15))
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "no_solution", "round": round_type}

    placements = []
    used = defaultdict(int)
    placed_ids = set()
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
                "review_reason": None if normal else "OV>60_AND_BIKE>30",
            })
            used[scid] += 1
            placed_ids.add(sid)

    unplaced = []
    for st in students:
        sid = st["student_id"]
        if sid in placed_ids:
            continue
        alts = []
        for scid in candidates.get(sid, []):
            r = routes[(sid, scid)]
            alts.append({
                "school_id": scid,
                "ov_minutes": r.get("ov_minutes"),
                "bike_minutes": r.get("bike_minutes"),
                "normal_reachability": is_normal(r),
            })
        alts.sort(key=lambda a: (not a["normal_reachability"], min(a.get("ov_minutes") or 999, a.get("bike_minutes") or 999)))
        unplaced.append({"student_id": sid, "alternatives": alts[:3]})

    remaining = []
    scarcity = []
    for sc in schools:
        scid = sc["school_id"]
        capacity = int(sc.get(cap_key, 0))
        rem = capacity - used[scid]
        remaining.append({"school_id": scid, "remaining": rem, "capacity": capacity})
        dependent = sum(1 for sid, ids in candidates.items() if scid in ids and len(ids) <= 2)
        if rem > 0 and dependent > 0:
            scarcity.append({"school_id": scid, "remaining": rem, "hard_to_place_dependents": dependent})

    return {
        "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
        "round": round_type,
        "total_students": len(students),
        "placed": len(placements),
        "placement_percentage": round((len(placements) / len(students) * 100), 1) if students else 100.0,
        "placements": sorted(placements, key=lambda p: p["student_id"]),
        "human_review": [p for p in placements if p["human_review"]],
        "unplaced": unplaced,
        "remaining_capacity": remaining,
        "strategic_reserve_candidates": sorted(scarcity, key=lambda z: -z["hard_to_place_dependents"]),
    }


def solve_file(input_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    result = solve_round(data)
    if output_path:
        Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", default="output/result.json")
    args = parser.parse_args()
    result = solve_file(args.input, args.output)
    print(json.dumps(result, indent=2))
