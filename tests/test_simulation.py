from engine.simulation import build_demo, run_simulation


def test_demo_has_50_students_and_12_schools():
    students, schools, *_ = build_demo()

    assert len(students) == 50
    assert len(schools) == 12


def test_simulation_contains_expected_rounds():
    result = run_simulation()

    assert set(result["rounds"].keys()) == {
        "J4",
        "LANG",
        "PROF",
        "J2",
        "J1",
    }


def test_no_regular_j3():
    result = run_simulation()

    assert "J3" not in result["rounds"]