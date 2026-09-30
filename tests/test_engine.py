import json
from pathlib import Path
import pytest

from engine.optimizer import solve_regular_round, solve_profile_round, solve_replacement

ROOT = Path(__file__).parents[1]


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def test_regular_places_everyone_when_capacity_exists():
    result = solve_regular_round(load("test_regular.json"))
    assert result["placed"] == 6


def test_unique_school_is_protected_by_global_optimization():
    result = solve_regular_round(load("test_regular.json"))
    mapping = {p["student_id"]: p["school_id"] for p in result["placements"]}
    assert mapping["STU-002"] == "SCH-A"


def test_block_is_never_violated():
    result = solve_regular_round(load("test_regular.json"))
    mapping = {p["student_id"]: p["school_id"] for p in result["placements"]}
    assert mapping["STU-004"] != "SCH-C"


def test_bike_30_or_less_counts_as_normal():
    result = solve_regular_round(load("test_regular.json"))
    p = next(p for p in result["placements"] if p["student_id"] == "STU-004")
    assert p["normal_reachability"] is True


def test_bad_route_is_human_review_not_hard_rejection():
    result = solve_regular_round(load("test_regular.json"))
    p = next(p for p in result["placements"] if p["student_id"] == "STU-006")
    assert p["school_id"] == "SCH-D"
    assert p["human_review"] is True
    assert p["review_reason"] == "OV>60_AND_BIKE>30"


def test_profile_capacity_and_blocking():
    result = solve_profile_round(load("test_profiles.json"))
    assert result["placed"] == 4
    p3 = [p for p in result["placements"] if p["student_id"] == "STU-P03"]
    assert len(p3) == 1
    assert p3[0]["school_id"] == "SCH-Z"


def test_max_two_profiles_per_semester():
    data = load("test_profiles.json")
    data["student_profiles"].append({"student_id":"STU-P01","semester":"S1","profile_id":"PROF-03","active":True})
    with pytest.raises(ValueError):
        solve_profile_round(data)


def test_replacement_does_not_move_other_students():
    data = load("test_regular.json")
    data["current_placements"] = [
        {"student_id":"STU-002","school_id":"SCH-A","active":True},
        {"student_id":"STU-003","school_id":"SCH-B","active":True}
    ]
    result = solve_replacement(data, "STU-001")
    assert result["mode"] == "replacement"
    if result["placements"]:
        assert result["placements"][0]["school_id"] != "SCH-A"
