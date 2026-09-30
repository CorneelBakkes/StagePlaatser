# Stagepuzzel Engine v0.1

Proof-of-concept placement engine for Pabo stage placements.

## Current scope

- OR-Tools CP-SAT optimizer
- regular rounds: J4, LANG, J2, J1
- hard student-school blocks
- capacity constraints
- OV <= 60 minutes OR bicycle <= 30 minutes counts as normal reachability
- maximizes number of placements first, then normal reachability, then travel time
- reports human-review placements, unplaced students, remaining capacity and strategic reserve candidates
- no personal data required

Profiling (S1/S2, 8 profiles, max 2/student/semester) is the next engine module; it is deliberately separate from regular J4/J2/J1/LANG capacity.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m engine.optimizer data/testdata.json --output output/result.json
pytest -q
```

## GitHub

Create an empty repository and copy the contents of this folder into it. The engine does not depend on GitHub and can later be deployed unchanged behind an Azure Function/API.

## Input/output

The proof-of-concept consumes JSON. Route times are currently supplied as test data. The next engine will generate these through a real routing provider and cache the results.
