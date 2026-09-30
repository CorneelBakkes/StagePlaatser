import json
from pathlib import Path

from engine.simulation import build_demo_payload, render_report, run_demo, write_demo


def test_demo_has_50_students_and_no_regular_j3():
    data = build_demo_payload()
    assert len(data["students"]) == 50
    assert all(s["category"] != "J3" for s in data["students"])
    assert {s["category"] for s in data["students"]} == {"J4", "LANG", "PROF", "J2", "J1"}


def test_demo_has_12_schools_and_eight_profiles():
    data = build_demo_payload()
    assert len(data["schools"]) == 12
    assert len(data["profiles"]) == 8


def test_profile_max_two_per_student_per_semester():
    data = build_demo_payload()
    counts = {}
    for row in data["student_profiles"]:
        key = (row["student_id"], row["semester"])
        counts[key] = counts.get(key, 0) + 1
    assert counts
    assert max(counts.values()) <= 2


def test_simulation_runs_all_rounds_in_agreed_order():
    result = run_demo()
    assert result["round_order"] == ["J4", "LANG", "PROF", "J2", "J1"]
    assert set(result["results"]) == {"J4", "LANG", "PROF_S1", "PROF_S2", "J2", "J1"}


def test_hard_blocks_are_never_used():
    result = run_demo()
    blocked = {
        (b["student_id"], b["school_id"])
        for b in result["input"]["blocks"]
        if b.get("active", True)
    }
    all_placements = []
    for round_result in result["results"].values():
        all_placements.extend(round_result.get("placements", []))
    assert not any((p["student_id"], p["school_id"]) in blocked for p in all_placements)


def test_forced_difficult_student_is_human_review():
    result = run_demo()
    placement = next(
        p for p in result["results"]["J4"]["placements"] if p["student_id"] == "STU-005"
    )
    assert placement["school_id"] == "SCH-04"
    assert placement["human_review"] is True


def test_report_is_human_readable():
    report = render_report(run_demo())
    assert "STAGEPLAATSER ENGINE v0.3" in report
    assert "JAAR 4" in report
    assert "PROFILERING S1" in report
    assert "TOTAAL" in report


def test_write_demo_creates_json_text_and_html(tmp_path: Path):
    json_path = tmp_path / "sim.json"
    txt_path = tmp_path / "sim.txt"
    html_path = tmp_path / "sim.html"
    write_demo(json_path, txt_path, html_path)
    assert json_path.exists()
    assert txt_path.exists()
    assert html_path.exists()
    assert "StagePlaatser Engine v0.3" in html_path.read_text(encoding="utf-8")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["engine_version"] == "0.3"
