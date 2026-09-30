from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from engine.optimizer import solve_profile_round, solve_regular_round

ROUND_ORDER = ("J4", "LANG", "PROF", "J2", "J1")
PROFILE_IDS = tuple(f"PROF-{i:02d}" for i in range(1, 9))


def build_demo_payload(seed: int = 20260930) -> dict[str, Any]:
    """Build a deterministic fictitious StagePlaatser dataset."""
    rng = random.Random(seed)

    schools = []
    for i in range(1, 13):
        schools.append(
            {
                "school_id": f"SCH-{i:02d}",
                "school_name": f"Oefenschool {i:02d}",
                "active": True,
                "capacity_j4": rng.choice([1, 1, 1, 2]),
                "capacity_lang": rng.choice([0, 1, 1]),
                "capacity_j2": rng.choice([1, 1, 2, 2]),
                "capacity_j1": rng.choice([1, 2, 2, 3]),
            }
        )

    schools[0].update({"capacity_j4": 2, "capacity_lang": 1, "capacity_j2": 1, "capacity_j1": 2})
    schools[1].update({"capacity_j4": 1, "capacity_lang": 1, "capacity_j2": 2, "capacity_j1": 2})
    schools[2].update({"capacity_j4": 1, "capacity_lang": 1, "capacity_j2": 2, "capacity_j1": 2})

    category_counts = (("J4", 10), ("LANG", 5), ("PROF", 10), ("J2", 13), ("J1", 12))
    students = []
    student_no = 1
    for category, count in category_counts:
        for _ in range(count):
            students.append(
                {
                    "student_id": f"STU-{student_no:03d}",
                    "category": category,
                    "active": True,
                }
            )
            student_no += 1

    routes: list[dict[str, Any]] = []
    for st in students:
        sid_num = int(st["student_id"].split("-")[1])
        for sc in schools:
            sc_num = int(sc["school_id"].split("-")[1])
            if (sid_num * 7 + sc_num * 11 + seed) % 20 < 3:
                continue
            base = 18 + ((sid_num * 13 + sc_num * 17) % 58)
            ov = base + ((sid_num + sc_num) % 12)
            bike = 12 + ((sid_num * 9 + sc_num * 5) % 45)
            if (sid_num + sc_num) % 13 == 0:
                ov += 25
                bike += 15
            routes.append(
                {
                    "student_id": st["student_id"],
                    "school_id": sc["school_id"],
                    "ov_minutes": ov,
                    "bike_minutes": bike,
                }
            )

    def upsert_route(student_id: str, school_id: str, ov: int, bike: int) -> None:
        routes[:] = [
            r
            for r in routes
            if not (r["student_id"] == student_id and r["school_id"] == school_id)
        ]
        routes.append(
            {
                "student_id": student_id,
                "school_id": school_id,
                "ov_minutes": ov,
                "bike_minutes": bike,
            }
        )

    # Scarcity example: STU-002 has only one route; STU-001 has alternatives.
    upsert_route("STU-001", "SCH-01", 20, 18)
    upsert_route("STU-001", "SCH-02", 31, 24)
    upsert_route("STU-001", "SCH-03", 38, 29)
    routes[:] = [r for r in routes if r["student_id"] != "STU-002"]
    upsert_route("STU-002", "SCH-01", 33, 27)

    # Human-review example: one difficult J4 student with one route only.
    routes[:] = [r for r in routes if r["student_id"] != "STU-005"]
    upsert_route("STU-005", "SCH-04", 74, 39)

    blocks = [
        {"block_id": "BLK-001", "student_id": "STU-004", "school_id": "SCH-03", "active": True},
        {"block_id": "BLK-002", "student_id": "STU-012", "school_id": "SCH-02", "active": True},
        {"block_id": "BLK-003", "student_id": "STU-019", "school_id": "SCH-08", "active": True},
        {"block_id": "BLK-004", "student_id": "STU-031", "school_id": "SCH-06", "active": True},
        {"block_id": "BLK-005", "student_id": "STU-044", "school_id": "SCH-10", "active": True},
        {"block_id": "BLK-006", "student_id": "STU-049", "school_id": "SCH-11", "active": True},
    ]

    profile_students = [s for s in students if s["category"] == "PROF"]
    student_profiles: list[dict[str, Any]] = []
    for idx, st in enumerate(profile_students):
        semester = "S1" if idx < 6 else "S2"
        first = PROFILE_IDS[(idx * 3) % len(PROFILE_IDS)]
        student_profiles.append(
            {
                "student_id": st["student_id"],
                "semester": semester,
                "profile_id": first,
                "active": True,
            }
        )
        if idx % 3 == 0:
            second = PROFILE_IDS[(idx * 3 + 2) % len(PROFILE_IDS)]
            student_profiles.append(
                {
                    "student_id": st["student_id"],
                    "semester": semester,
                    "profile_id": second,
                    "active": True,
                }
            )

    profile_capacity: list[dict[str, Any]] = []
    for semester in ("S1", "S2"):
        for sc in schools:
            sc_num = int(sc["school_id"].split("-")[1])
            for pidx, pid in enumerate(PROFILE_IDS, start=1):
                if (sc_num + pidx + (0 if semester == "S1" else 3)) % 4 == 0:
                    profile_capacity.append(
                        {
                            "school_id": sc["school_id"],
                            "semester": semester,
                            "profile_id": pid,
                            "capacity": 1 if (sc_num + pidx) % 5 else 2,
                            "active": True,
                        }
                    )

    return {
        "engine_version": "0.3",
        "seed": seed,
        "students": students,
        "schools": schools,
        "routes": routes,
        "blocks": blocks,
        "profiles": [
            {"profile_id": pid, "name": f"Profilering {pid[-2:]}", "active": True}
            for pid in PROFILE_IDS
        ],
        "student_profiles": student_profiles,
        "profile_capacity": profile_capacity,
        "max_solve_seconds": 10,
        "search_workers": 8,
    }


def run_demo(seed: int = 20260930) -> dict[str, Any]:
    data = build_demo_payload(seed)
    results: dict[str, Any] = {}

    for round_type in ("J4", "LANG"):
        results[round_type] = solve_regular_round({**data, "round": round_type})

    for semester in ("S1", "S2"):
        results[f"PROF_{semester}"] = solve_profile_round(
            {**data, "round": "PROF", "semester": semester}
        )

    for round_type in ("J2", "J1"):
        results[round_type] = solve_regular_round({**data, "round": round_type})

    return {
        "engine_version": "0.3",
        "simulation": "fictitious_demo",
        "seed": seed,
        "round_order": list(ROUND_ORDER),
        "input_summary": {
            "students": len(data["students"]),
            "schools": len(data["schools"]),
            "routes": len(data["routes"]),
            "hard_blocks": len(data["blocks"]),
            "profile_requirements": len(data["student_profiles"]),
        },
        "summary": _build_summary(data, results),
        "results": results,
        "input": data,
    }


def _build_summary(data: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    regular_keys = ("J4", "LANG", "J2", "J1")
    regular_students = sum(results[k]["total_students"] for k in regular_keys)
    regular_placed = sum(results[k]["placed"] for k in regular_keys)
    regular_review = sum(len(results[k].get("human_review", [])) for k in regular_keys)
    regular_unplaced = sum(len(results[k].get("unplaced", [])) for k in regular_keys)

    profile_keys = ("PROF_S1", "PROF_S2")
    profile_req = sum(results[k]["total_profile_requirements"] for k in profile_keys)
    profile_placed = sum(results[k]["placed"] for k in profile_keys)
    profile_review = sum(len(results[k].get("human_review", [])) for k in profile_keys)
    profile_unplaced = sum(len(results[k].get("unplaced", [])) for k in profile_keys)

    categories = Counter(s["category"] for s in data["students"])
    return {
        "student_categories": dict(categories),
        "regular_students": regular_students,
        "regular_placed": regular_placed,
        "regular_placement_percentage": round(regular_placed / regular_students * 100, 1)
        if regular_students
        else 100.0,
        "regular_human_review": regular_review,
        "regular_unplaced": regular_unplaced,
        "profile_requirements": profile_req,
        "profile_placed": profile_placed,
        "profile_placement_percentage": round(profile_placed / profile_req * 100, 1)
        if profile_req
        else 100.0,
        "profile_human_review": profile_review,
        "profile_unplaced": profile_unplaced,
    }


def render_report(simulation: dict[str, Any]) -> str:
    s = simulation["summary"]
    lines = [
        "STAGEPLAATSER ENGINE v0.3 - FICTIEVE SIMULATIE",
        "=" * 55,
        f"Studenten: {simulation['input_summary']['students']}",
        f"Scholen:   {simulation['input_summary']['schools']}",
        f"Blokkades: {simulation['input_summary']['hard_blocks']}",
        f"Seed:      {simulation['seed']}",
        "",
        "VOLGORDE: J4 -> Langstudeerders -> Profilering S1/S2 -> J2 -> J1",
        "",
    ]

    display_order = (
        ("J4", "JAAR 4"),
        ("LANG", "LANGSTUDEERDERS"),
        ("PROF_S1", "PROFILERING S1"),
        ("PROF_S2", "PROFILERING S2"),
        ("J2", "JAAR 2"),
        ("J1", "JAAR 1"),
    )
    for key, label in display_order:
        result = simulation["results"][key]
        total_key = "total_profile_requirements" if key.startswith("PROF") else "total_students"
        lines.extend(
            [
                label,
                "-" * len(label),
                f"Te plaatsen:       {result[total_key]}",
                f"Geplaatst:         {result['placed']}",
                f"Plaatsingsgraad:   {result['placement_percentage']}%",
                f"Human Review:      {len(result.get('human_review', []))}",
                f"Niet geplaatst:    {len(result.get('unplaced', []))}",
            ]
        )

        for placement in result.get("placements", [])[:5]:
            profile = f" | {placement['profile_id']}" if placement.get("profile_id") else ""
            review = " | REVIEW" if placement.get("human_review") else ""
            lines.append(
                f"  {placement['student_id']} -> {placement['school_id']}{profile} | "
                f"OV {placement.get('ov_minutes')} min | fiets {placement.get('bike_minutes')} min{review}"
            )
        if len(result.get("placements", [])) > 5:
            lines.append(f"  ... plus {len(result['placements']) - 5} andere plaatsingen")

        for unplaced in result.get("unplaced", [])[:3]:
            profile = f" ({unplaced.get('profile_id')})" if unplaced.get("profile_id") else ""
            lines.append(
                f"  REVIEW: {unplaced['student_id']}{profile} -> geen definitieve plaatsing"
            )

        if not key.startswith("PROF"):
            reserves = result.get("strategic_reserve_candidates", [])[:3]
            if reserves:
                lines.append("  Strategische reservecapaciteit:")
                for item in reserves:
                    lines.append(
                        f"    {item['school_id']}: {item['remaining']} plek(ken) | "
                        f"schaarstescore {item['scarcity_score']}"
                    )
        lines.append("")

    lines.extend(
        [
            "TOTAAL",
            "------",
            f"Regulier geplaatst: {s['regular_placed']}/{s['regular_students']} "
            f"({s['regular_placement_percentage']}%)",
            f"Regulier Human Review: {s['regular_human_review']}",
            f"Regulier niet geplaatst: {s['regular_unplaced']}",
            f"Profilering geplaatst: {s['profile_placed']}/{s['profile_requirements']} "
            f"({s['profile_placement_percentage']}%)",
            f"Profilering Human Review: {s['profile_human_review']}",
            f"Profilering niet geplaatst: {s['profile_unplaced']}",
            "",
            "Let op: alle data en reistijden in deze demo zijn fictief.",
        ]
    )
    return "\n".join(lines)


def render_html(simulation: dict[str, Any]) -> str:
    s = simulation["summary"]
    cards = [
        ("Studenten", simulation["input_summary"]["students"]),
        ("Scholen", simulation["input_summary"]["schools"]),
        ("Regulier geplaatst", f"{s['regular_placed']}/{s['regular_students']}"),
        ("Regulier review", s["regular_human_review"]),
        ("Profilering geplaatst", f"{s['profile_placed']}/{s['profile_requirements']}"),
        ("Profilering review", s["profile_human_review"]),
    ]
    card_html = "".join(
        f'<div class="card"><b>{label}</b><span>{value}</span></div>' for label, value in cards
    )

    sections = []
    display_order = (
        ("J4", "Jaar 4"),
        ("LANG", "Langstudeerders"),
        ("PROF_S1", "Profilering S1"),
        ("PROF_S2", "Profilering S2"),
        ("J2", "Jaar 2"),
        ("J1", "Jaar 1"),
    )
    for key, label in display_order:
        result = simulation["results"][key]
        rows = []
        for placement in result.get("placements", []):
            state = "Human Review" if placement.get("human_review") else "Normaal"
            profile = placement.get("profile_id", "-")
            rows.append(
                "<tr>"
                f"<td>{placement['student_id']}</td>"
                f"<td>{placement['school_id']}</td>"
                f"<td>{profile}</td>"
                f"<td>{placement.get('ov_minutes', '-')}</td>"
                f"<td>{placement.get('bike_minutes', '-')}</td>"
                f"<td>{state}</td>"
                "</tr>"
            )
        for unplaced in result.get("unplaced", []):
            rows.append(
                "<tr class='warn'>"
                f"<td>{unplaced['student_id']}</td>"
                "<td>-</td>"
                f"<td>{unplaced.get('profile_id', '-')}</td>"
                "<td>-</td><td>-</td><td>Niet geplaatst</td></tr>"
            )
        total_key = "total_profile_requirements" if key.startswith("PROF") else "total_students"
        sections.append(
            f"<section><h2>{label}</h2>"
            f"<p>{result['placed']} van {result[total_key]} geplaatst &middot; "
            f"{len(result.get('human_review', []))} Human Review &middot; "
            f"{len(result.get('unplaced', []))} niet geplaatst</p>"
            "<table><thead><tr><th>Student</th><th>School</th><th>Profilering</th>"
            "<th>OV min</th><th>Fiets min</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )

    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>StagePlaatser v0.3 simulatie</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}
header{{background:#111827;color:white;padding:24px}}
main{{max-width:1200px;margin:auto;padding:24px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}}
.card{{background:white;border-radius:10px;padding:16px;box-shadow:0 1px 4px #0002}}
.card b{{display:block;font-size:13px;color:#6b7280}}
.card span{{font-size:26px;font-weight:700}}
section{{background:white;padding:18px;margin:18px 0;border-radius:10px;box-shadow:0 1px 4px #0002;overflow:auto}}
table{{border-collapse:collapse;width:100%;min-width:720px}}
th,td{{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left}}
th{{font-size:12px;text-transform:uppercase;color:#6b7280}}
.warn{{background:#fff7ed}}
.note{{color:#6b7280;font-size:13px}}
</style>
</head>
<body>
<header><h1>StagePlaatser Engine v0.3</h1><div>Fictieve simulatie - seed {simulation['seed']}</div></header>
<main>
<div class="cards">{card_html}</div>
<p class="note">Volgorde: J4 &rarr; Langstudeerders &rarr; Profilering S1/S2 &rarr; J2 &rarr; J1. Alle gegevens en reistijden zijn fictief.</p>
{''.join(sections)}
</main>
</body>
</html>"""


def write_demo(
    output_path: str | Path,
    report_path: str | Path | None = None,
    html_path: str | Path | None = None,
    seed: int = 20260930,
) -> dict[str, Any]:
    simulation = run_demo(seed)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(simulation, indent=2, ensure_ascii=False), encoding="utf-8")
    if report_path:
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(render_report(simulation) + "\n", encoding="utf-8")
    if html_path:
        html = Path(html_path)
        html.parent.mkdir(parents=True, exist_ok=True)
        html.write_text(render_html(simulation), encoding="utf-8")
    return simulation


def main() -> None:
    parser = argparse.ArgumentParser(description="StagePlaatser Engine v0.3 fictieve simulatie")
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--output", default="output/simulation.json")
    parser.add_argument("--report", default="output/simulation.txt")
    parser.add_argument("--html", default="output/simulation.html")
    args = parser.parse_args()

    simulation = write_demo(args.output, args.report, args.html, args.seed)
    print(render_report(simulation))
    print(f"\nJSON opgeslagen: {args.output}")
    print(f"Rapport opgeslagen: {args.report}")
    print(f"Dashboard opgeslagen: {args.html}")


if __name__ == "__main__":
    main()
