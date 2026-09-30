from engine.optimizer import solve_round, re_place_student


def test_global_solver_protects_student_with_one_option():
    students = [
        {"id": "A", "category": "J4"},
        {"id": "B", "category": "J4"},
    ]

    schools = [
        {"id": "X", "capacity": {"J4": 1}},
        {"id": "Y", "capacity": {"J4": 1}},
    ]

    routes = {
        ("A", "X"): {"ov": 20, "bike": 20},
        ("A", "Y"): {"ov": 25, "bike": 25},
        ("B", "X"): {"ov": 30, "bike": 35},
    }

    result = solve_round(
        students=students,
        schools=schools,
        routes=routes,
        blocks=set(),
        category="J4",
    )

    placements = {
        placement["student"]: placement["school"]
        for placement in result["placements"]
    }

    assert placements["B"] == "X"
    assert placements["A"] == "Y"


def test_hard_block_is_never_used():
    students = [
        {"id": "A", "category": "J2"},
    ]

    schools = [
        {"id": "X", "capacity": {"J2": 1}},
        {"id": "Y", "capacity": {"J2": 1}},
    ]

    routes = {
        ("A", "X"): {"ov": 10, "bike": 10},
        ("A", "Y"): {"ov": 20, "bike": 20},
    }

    result = solve_round(
        students=students,
        schools=schools,
        routes=routes,
        blocks={("A", "X")},
        category="J2",
    )

    assert result["placements"][0]["school"] == "Y"


def test_bad_travel_goes_to_human_review():
    students = [
        {"id": "A", "category": "J1"},
    ]

    schools = [
        {"id": "X", "capacity": {"J1": 1}},
    ]

    routes = {
        ("A", "X"): {"ov": 72, "bike": 42},
    }

    result = solve_round(
        students=students,
        schools=schools,
        routes=routes,
        blocks=set(),
        category="J1",
    )

    assert result["placements"][0]["human_review"] is True


def test_replacement_uses_remaining_capacity():
    student = {
        "id": "A",
        "category": "LANG",
    }

    schools = [
        {"id": "X", "capacity": {"LANG": 0}},
        {"id": "Y", "capacity": {"LANG": 1}},
    ]

    routes = {
        ("A", "X"): {"ov": 20, "bike": 20},
        ("A", "Y"): {"ov": 35, "bike": 28},
    }

    result = re_place_student(
        student=student,
        schools=schools,
        routes=routes,
        blocks=set(),
        category="LANG",
    )

    assert result["placements"][0]["school"] == "Y"