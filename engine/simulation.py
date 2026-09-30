import json
import random
from pathlib import Path
from html import escape

from engine.optimizer import solve_round, solve_profiles


OUTPUT_DIR = Path("output")


def build_demo(seed: int = 42):
    random.seed(seed)

    categories = (
        ["J4"] * 10
        + ["LANG"] * 5
        + ["PROF"] * 10
        + ["J2"] * 12
        + ["J1"] * 13
    )

    students = [
        {
            "id": f"STU-{i:03}",
            "category": category,
        }
        for i, category in enumerate(categories, start=1)
    ]

    schools = []

    for i in range(1, 13):
        schools.append(
            {
                "id": f"SCH-{i:03}",
                "name": f"Basisschool {i}",
                "capacity": {
                    "J4": random.randint(0, 2),
                    "LANG": random.randint(0, 1),
                    "J2": random.randint(0, 2),
                    "J1": random.randint(0, 2),
                },
            }
        )

    # Zorg dat er in elk geval bruikbare capaciteit is.
    schools[0]["capacity"].update(
        {
            "J4": 2,
            "LANG": 1,
            "J2": 2,
            "J1": 2,
        }
    )

    schools[1]["capacity"].update(
        {
            "J4": 2,
            "LANG": 1,
            "J2": 2,
            "J1": 2,
        }
    )

    routes = {}

    for student in students:
        for school in schools:

            # Een deel van de combinaties bestaat bewust niet.
            if random.random() < 0.08:
                continue

            routes[(student["id"], school["id"])] = {
                "ov": random.randint(25, 85),
                "bike": random.randint(15, 55),
            }

    # Bewust een schaarse student creëren:
    # STU-001 kan alleen naar SCH-001.
    for school in schools:
        if school["id"] != "SCH-001":
            routes.pop(
                ("STU-001", school["id"]),
                None,
            )

    routes[("STU-001", "SCH-001")] = {
        "ov": 48,
        "bike": 39,
    }

    # Enkele harde blokkades.
    blocks = {
        ("STU-002", "SCH-001"),
        ("STU-011", "SCH-002"),
        ("STU-025", "SCH-003"),
        ("STU-040", "SCH-004"),
    }

    profiles = [
        f"PROF-{i:02}"
        for i in range(1, 9)
    ]

    profile_students = [
        student
        for student in students
        if student["category"] == "PROF"
    ]

    profile_requests = []

    for student in profile_students:
        for semester in ("S1", "S2"):

            number_of_profiles = random.choice(
                [1, 2]
            )

            chosen_profiles = random.sample(
                profiles,
                number_of_profiles,
            )

            for profile in chosen_profiles:
                profile_requests.append(
                    {
                        "student": student["id"],
                        "semester": semester,
                        "profile": profile,
                    }
                )

    profile_capacity = {}

    for school in schools:
        for semester in ("S1", "S2"):
            for profile in profiles:

                profile_capacity[
                    (
                        school["id"],
                        semester,
                        profile,
                    )
                ] = (
                    1
                    if random.random() < 0.28
                    else 0
                )

    # Minimaal enige profileringscapaciteit
    # per profiel en semester garanderen.
    for semester in ("S1", "S2"):
        for index, profile in enumerate(profiles):

            school_id = schools[
                index % len(schools)
            ]["id"]

            profile_capacity[
                (
                    school_id,
                    semester,
                    profile,
                )
            ] = 2

    return (
        students,
        schools,
        routes,
        blocks,
        profile_requests,
        profile_capacity,
    )


def run_simulation():
    (
        students,
        schools,
        routes,
        blocks,
        profile_requests,
        profile_capacity,
    ) = build_demo()

    results = {
        "summary": {},
        "rounds": {},
    }

    # Gewenste plaatsingsvolgorde.
    for category in ("J4", "LANG"):

        result = solve_round(
            students=students,
            schools=schools,
            routes=routes,
            blocks=blocks,
            category=category,
        )

        results["rounds"][category] = result

    profile_result = solve_profiles(
        requests=profile_requests,
        profile_capacity=profile_capacity,
        routes=routes,
        blocks=blocks,
    )

    results["rounds"]["PROF"] = profile_result

    for category in ("J2", "J1"):

        result = solve_round(
            students=students,
            schools=schools,
            routes=routes,
            blocks=blocks,
            category=category,
        )

        results["rounds"][category] = result

    regular_categories = (
        "J4",
        "LANG",
        "J2",
        "J1",
    )

    regular_placements = sum(
        len(
            results["rounds"][category][
                "placements"
            ]
        )
        for category in regular_categories
    )

    regular_unplaced = sum(
        len(
            results["rounds"][category][
                "unplaced"
            ]
        )
        for category in regular_categories
    )

    human_review = sum(
        sum(
            1
            for placement in results[
                "rounds"
            ][category]["placements"]
            if placement["human_review"]
        )
        for category in regular_categories
    )

    human_review += sum(
        1
        for placement in profile_result[
            "placements"
        ]
        if placement["human_review"]
    )

    results["summary"] = {
        "students": len(students),
        "schools": len(schools),
        "regular_placements": regular_placements,
        "regular_unplaced": regular_unplaced,
        "profile_requests": len(
            profile_requests
        ),
        "profile_placements": len(
            profile_result["placements"]
        ),
        "profile_unplaced": len(
            profile_result["unplaced"]
        ),
        "human_review": human_review,
    }

    return results


def build_text_report(results: dict) -> str:
    summary = results["summary"]

    lines = []

    lines.append(
        "STAGEPLAATSER v0.3 SIMULATIE"
    )
    lines.append("=" * 42)
    lines.append(
        f"Studenten:               "
        f"{summary['students']}"
    )
    lines.append(
        f"Scholen:                 "
        f"{summary['schools']}"
    )
    lines.append(
        f"Regulier geplaatst:      "
        f"{summary['regular_placements']}"
    )
    lines.append(
        f"Regulier niet geplaatst: "
        f"{summary['regular_unplaced']}"
    )
    lines.append(
        f"Profileringsverzoeken:   "
        f"{summary['profile_requests']}"
    )
    lines.append(
        f"Profilering geplaatst:   "
        f"{summary['profile_placements']}"
    )
    lines.append(
        f"Profilering niet geplaatst: "
        f"{summary['profile_unplaced']}"
    )
    lines.append(
        f"Human Review:            "
        f"{summary['human_review']}"
    )

    for category in (
        "J4",
        "LANG",
        "PROF",
        "J2",
        "J1",
    ):
        result = results["rounds"][category]

        lines.append("")
        lines.append(category)
        lines.append("-" * 42)

        for placement in result["placements"]:

            if category == "PROF":
                lines.append(
                    f"{placement['student']} "
                    f"-> {placement['school']} | "
                    f"{placement['semester']} "
                    f"{placement['profile']} | "
                    f"OV {placement['ov']} | "
                    f"fiets {placement['bike']} | "
                    f"{'REVIEW' if placement['human_review'] else 'OK'}"
                )

            else:
                lines.append(
                    f"{placement['student']} "
                    f"-> {placement['school']} | "
                    f"OV {placement['ov']} | "
                    f"fiets {placement['bike']} | "
                    f"alternatieven "
                    f"{placement['alternative_count']} | "
                    f"{'REVIEW' if placement['human_review'] else 'OK'}"
                )

        if result["unplaced"]:
            lines.append("")
            lines.append(
                f"Niet geplaatst: "
                f"{result['unplaced']}"
            )

    return "\n".join(lines)


def build_html(results: dict) -> str:
    summary = results["summary"]

    rows = []

    for category in (
        "J4",
        "LANG",
        "PROF",
        "J2",
        "J1",
    ):
        for placement in results[
            "rounds"
        ][category]["placements"]:

            rows.append(
                "<tr>"
                f"<td>{escape(category)}</td>"
                f"<td>{escape(placement['student'])}</td>"
                f"<td>{escape(placement['school'])}</td>"
                f"<td>{placement.get('ov', '')}</td>"
                f"<td>{placement.get('bike', '')}</td>"
                f"<td>"
                f"{'Human Review' if placement.get('human_review') else 'OK'}"
                f"</td>"
                "</tr>"
            )

    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>StagePlaatser v0.3</title>
<style>
body {{
    font-family: Arial, sans-serif;
    max-width: 1200px;
    margin: 30px auto;
    padding: 0 20px;
}}

.cards {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
}}

.card {{
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 16px;
}}

.number {{
    font-size: 28px;
    font-weight: bold;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 25px;
}}

th, td {{
    border-bottom: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}}
</style>
</head>
<body>

<h1>StagePlaatser v0.3</h1>
<p>Proof of concept met fictieve gegevens.</p>

<div class="cards">

<div class="card">
<div class="number">
{summary['students']}
</div>
studenten
</div>

<div class="card">
<div class="number">
{summary['schools']}
</div>
scholen
</div>

<div class="card">
<div class="number">
{summary['regular_placements']}
</div>
regulier geplaatst
</div>

<div class="card">
<div class="number">
{summary['profile_placements']}
</div>
profileringsplaatsen
</div>

<div class="card">
<div class="number">
{summary['human_review']}
</div>
Human Review
</div>

</div>

<table>

<thead>
<tr>
<th>Ronde</th>
<th>Student</th>
<th>School</th>
<th>OV</th>
<th>Fiets</th>
<th>Status</th>
</tr>
</thead>

<tbody>
{''.join(rows)}
</tbody>

</table>

</body>
</html>
"""


def main():
    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    results = run_simulation()

    json_path = (
        OUTPUT_DIR / "simulation.json"
    )

    text_path = (
        OUTPUT_DIR / "simulation.txt"
    )

    html_path = (
        OUTPUT_DIR / "simulation.html"
    )

    json_path.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_text_report(
        results
    )

    text_path.write_text(
        report,
        encoding="utf-8",
    )

    html_path.write_text(
        build_html(results),
        encoding="utf-8",
    )

    print(report)

    print("")
    print("Bestanden geschreven:")
    print(
        "  output/simulation.json"
    )
    print(
        "  output/simulation.txt"
    )
    print(
        "  output/simulation.html"
    )


if __name__ == "__main__":
    main()