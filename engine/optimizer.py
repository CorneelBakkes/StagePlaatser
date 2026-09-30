from collections import defaultdict
from ortools.sat.python import cp_model


def is_normal_route(route: dict) -> bool:
    """
    Een route is normaal bereikbaar wanneer:
    - OV <= 60 minuten, of
    - fiets <= 30 minuten.
    """
    ov = route.get("ov")
    bike = route.get("bike")

    ov_ok = ov is not None and ov <= 60
    bike_ok = bike is not None and bike <= 30

    return ov_ok or bike_ok


def travel_score(route: dict) -> int:
    """
    Geeft een eenvoudige reistijdscore terug.
    We gebruiken de beste beschikbare modaliteit.
    """
    values = []

    if route.get("ov") is not None:
        values.append(route["ov"])

    if route.get("bike") is not None:
        values.append(route["bike"])

    return min(values) if values else 999


def solve_round(
    students: list,
    schools: list,
    routes: dict,
    blocks: set,
    category: str,
) -> dict:
    """
    Lost één reguliere plaatsingsronde op.

    Voorbeelden category:
    - J4
    - LANG
    - J2
    - J1

    Er bestaat bewust geen reguliere J3.

    students:
    [
        {"id": "STU-001", "category": "J4"},
        ...
    ]

    schools:
    [
        {
            "id": "SCH-001",
            "capacity": {
                "J4": 2,
                "LANG": 1,
                "J2": 2,
                "J1": 2
            }
        }
    ]

    routes:
    {
        ("STU-001", "SCH-001"): {
            "ov": 42,
            "bike": 35
        }
    }

    blocks:
    {
        ("STU-001", "SCH-004"),
        ...
    }
    """

    round_students = [
        student
        for student in students
        if student["category"] == category
    ]

    feasible = defaultdict(list)

    # Eerst alle mogelijke student-schoolcombinaties bepalen.
    for student in round_students:
        student_id = student["id"]

        for school in schools:
            school_id = school["id"]

            # Hard block: combinatie bestaat voor de solver niet.
            if (student_id, school_id) in blocks:
                continue

            capacity = school.get("capacity", {}).get(category, 0)

            if capacity <= 0:
                continue

            route = routes.get((student_id, school_id))

            if route is None:
                continue

            feasible[student_id].append(school_id)

    model = cp_model.CpModel()

    placement_vars = {}

    # Beslisvariabelen.
    for student in round_students:
        student_id = student["id"]

        for school_id in feasible[student_id]:
            placement_vars[(student_id, school_id)] = model.NewBoolVar(
                f"place_{student_id}_{school_id}"
            )

        student_vars = [
            placement_vars[(student_id, school_id)]
            for school_id in feasible[student_id]
        ]

        # Student maximaal één keer plaatsen.
        if student_vars:
            model.Add(sum(student_vars) <= 1)

    # Capaciteitsbeperkingen per school.
    for school in schools:
        school_id = school["id"]
        capacity = school.get("capacity", {}).get(category, 0)

        school_vars = [
            placement_vars[(student["id"], school_id)]
            for student in round_students
            if (student["id"], school_id) in placement_vars
        ]

        if school_vars:
            model.Add(sum(school_vars) <= capacity)

    objective_terms = []

    for student in round_students:
        student_id = student["id"]
        option_count = len(feasible[student_id])

        # Student met weinig alternatieven krijgt meer bescherming.
        scarcity_bonus = 0

        if option_count > 0:
            scarcity_bonus = 8000 // option_count

        for school_id in feasible[student_id]:
            route = routes[(student_id, school_id)]

            score = 100_000

            # Studenten met weinig alternatieven beschermen.
            score += scarcity_bonus

            # Normaal bereikbare plaatsingen krijgen sterke voorkeur.
            if is_normal_route(route):
                score += 5_000
            else:
                score -= 5_000

            # Kortere reistijd is beter.
            score -= travel_score(route)

            objective_terms.append(
                score * placement_vars[(student_id, school_id)]
            )

    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0

    status = solver.Solve(model)

    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ):
        return {
            "category": category,
            "placements": [],
            "unplaced": [
                student["id"]
                for student in round_students
            ],
            "remaining_capacity": {
                school["id"]: school.get("capacity", {}).get(category, 0)
                for school in schools
            },
        }

    placements = []
    used_capacity = defaultdict(int)

    for student in round_students:
        student_id = student["id"]

        selected_school = None

        for school_id in feasible[student_id]:
            var = placement_vars[(student_id, school_id)]

            if solver.Value(var) == 1:
                selected_school = school_id
                break

        if selected_school is None:
            continue

        route = routes[(student_id, selected_school)]
        normal = is_normal_route(route)

        placements.append(
            {
                "student": student_id,
                "school": selected_school,
                "ov": route.get("ov"),
                "bike": route.get("bike"),
                "normal_reachable": normal,
                "human_review": not normal,
                "review_reason": (
                    None
                    if normal
                    else "OV > 60 minuten en fiets > 30 minuten"
                ),
                "alternative_count": len(feasible[student_id]),
            }
        )

        used_capacity[selected_school] += 1

    placed_ids = {
        placement["student"]
        for placement in placements
    }

    unplaced = [
        student["id"]
        for student in round_students
        if student["id"] not in placed_ids
    ]

    remaining_capacity = {}

    for school in schools:
        school_id = school["id"]
        capacity = school.get("capacity", {}).get(category, 0)

        remaining_capacity[school_id] = max(
            0,
            capacity - used_capacity[school_id],
        )

    return {
        "category": category,
        "placements": placements,
        "unplaced": unplaced,
        "remaining_capacity": remaining_capacity,
    }


def solve_profiles(
    requests: list,
    profile_capacity: dict,
    routes: dict,
    blocks: set,
) -> dict:
    """
    Lost profileringsplaatsingen op.

    requests:
    [
        {
            "student": "STU-021",
            "semester": "S1",
            "profile": "PROF-01"
        }
    ]

    profile_capacity:
    {
        ("SCH-001", "S1", "PROF-01"): 2
    }

    Een student kan maximaal twee profileringen
    per semester toegewezen krijgen.
    """

    model = cp_model.CpModel()

    placement_vars = {}

    # Mogelijke combinaties opbouwen.
    for request_index, request in enumerate(requests):
        student_id = request["student"]
        semester = request["semester"]
        profile = request["profile"]

        for (
            school_id,
            capacity_semester,
            capacity_profile,
        ), capacity in profile_capacity.items():

            if capacity_semester != semester:
                continue

            if capacity_profile != profile:
                continue

            if capacity <= 0:
                continue

            if (student_id, school_id) in blocks:
                continue

            if (student_id, school_id) not in routes:
                continue

            placement_vars[(request_index, school_id)] = model.NewBoolVar(
                f"profile_{request_index}_{school_id}"
            )

    # Elk profielverzoek maximaal één keer plaatsen.
    for request_index, _request in enumerate(requests):
        request_vars = [
            var
            for (idx, _school_id), var in placement_vars.items()
            if idx == request_index
        ]

        if request_vars:
            model.Add(sum(request_vars) <= 1)

    # Maximaal twee profileringsplaatsingen
    # per student per semester.
    student_semester_requests = defaultdict(list)

    for request_index, request in enumerate(requests):
        key = (
            request["student"],
            request["semester"],
        )

        student_semester_requests[key].append(request_index)

    for request_indices in student_semester_requests.values():

        vars_for_student_semester = [
            var
            for (request_index, _school_id), var in placement_vars.items()
            if request_index in request_indices
        ]

        if vars_for_student_semester:
            model.Add(
                sum(vars_for_student_semester) <= 2
            )

    # Capaciteit per school + semester + profiel.
    for (
        school_id,
        semester,
        profile,
    ), capacity in profile_capacity.items():

        capacity_vars = []

        for request_index, request in enumerate(requests):

            if request["semester"] != semester:
                continue

            if request["profile"] != profile:
                continue

            key = (request_index, school_id)

            if key in placement_vars:
                capacity_vars.append(
                    placement_vars[key]
                )

        if capacity_vars:
            model.Add(
                sum(capacity_vars) <= capacity
            )

    objective_terms = []

    for (
        request_index,
        school_id,
    ), var in placement_vars.items():

        request = requests[request_index]
        student_id = request["student"]

        route = routes[(student_id, school_id)]

        score = 100_000

        if is_normal_route(route):
            score += 5_000
        else:
            score -= 5_000

        score -= travel_score(route)

        objective_terms.append(score * var)

    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0

    status = solver.Solve(model)

    placements = []

    if status in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ):
        for (
            request_index,
            school_id,
        ), var in placement_vars.items():

            if solver.Value(var) != 1:
                continue

            request = requests[request_index]
            student_id = request["student"]

            route = routes[(student_id, school_id)]
            normal = is_normal_route(route)

            placements.append(
                {
                    "student": student_id,
                    "semester": request["semester"],
                    "profile": request["profile"],
                    "school": school_id,
                    "ov": route.get("ov"),
                    "bike": route.get("bike"),
                    "normal_reachable": normal,
                    "human_review": not normal,
                    "review_reason": (
                        None
                        if normal
                        else "OV > 60 minuten en fiets > 30 minuten"
                    ),
                }
            )

    placed_requests = {
        (
            placement["student"],
            placement["semester"],
            placement["profile"],
        )
        for placement in placements
    }

    unplaced = [
        request
        for request in requests
        if (
            request["student"],
            request["semester"],
            request["profile"],
        )
        not in placed_requests
    ]

    return {
        "placements": placements,
        "unplaced": unplaced,
    }


def re_place_student(
    student: dict,
    schools: list,
    routes: dict,
    blocks: set,
    category: str,
) -> dict:
    """
    Herplaatst één student zonder andere plaatsingen
    opnieuw te berekenen.

    De schools-list moet hierbij de actuele
    resterende capaciteit bevatten.
    """
    return solve_round(
        students=[student],
        schools=schools,
        routes=routes,
        blocks=blocks,
        category=category,
    )