import json
from pathlib import Path
from engine.optimizer import solve_round

DATA = Path(__file__).parents[1] / "data" / "testdata.json"


def payload():
    return json.loads(DATA.read_text())


def test_places_all_five_and_protects_unique_school():
    result = solve_round(payload())
    assert result["placed"] == 5
    mapping = {p["student_id"]: p["school_id"] for p in result["placements"]}
    # STU-002 has only SCH-A; global optimization must preserve it.
    assert mapping["STU-002"] == "SCH-A"


def test_block_is_hard():
    result = solve_round(payload())
    mapping = {p["student_id"]: p["school_id"] for p in result["placements"]}
    assert mapping["STU-004"] != "SCH-C"


def test_bike_under_30_is_normal():
    result = solve_round(payload())
    p = next(p for p in result["placements"] if p["student_id"] == "STU-004")
    if p["school_id"] == "SCH-B":
        assert p["bike_minutes"] == 24
        assert p["normal_reachability"] is True
