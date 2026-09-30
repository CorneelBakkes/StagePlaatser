# StagePlaatser Engine v0.2

Proof-of-concept voor de dNP-stageplaatsingspuzzel met Python + Google OR-Tools CP-SAT.

## Wat v0.2 kan

- Reguliere rondes: **J4, LANG, J2, J1** (geen reguliere J3).
- Globale optimalisatie: maximaal aantal studenten plaatsen vóór reistijdoptimalisatie.
- Harde student-schoolblokkades.
- Schoolcapaciteit per reguliere ronde.
- OV <= 60 minuten **of** fiets <= 30 minuten = normale bereikbaarheid.
- Slechtere bereikbaarheid wordt niet hard afgekeurd, maar gemarkeerd voor Human Review.
- Strategische schaarste wordt meegewogen bij gelijkwaardige oplossingen.
- Profileringsronde per semester (S1/S2), met capaciteit per school + profilering.
- Maximaal 2 profileringen per student per semester.
- Herplaatsing van één student zonder andere bestaande plaatsingen te verschuiven.
- JSON in / JSON uit; daardoor later geschikt voor Azure Function, SharePoint of Power Apps.

## Installeren

Python 3.11 of 3.12 aanbevolen.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

## Tests uitvoeren

```bash
pytest -q
```

## Reguliere test draaien

```bash
python -m engine.optimizer data/test_regular.json --output output/regular_result.json
```

## Profileringstest draaien

```bash
python -m engine.optimizer data/test_profiles.json --output output/profile_result.json
```

## Belangrijke ontwerpregels

- Een blokkade is hard en kan nooit door de optimizer worden genegeerd.
- Een route boven 60 minuten OV en boven 30 minuten fiets blijft technisch mogelijk, maar vraagt Human Review.
- Plaatsingsaantal heeft hogere prioriteit dan reistijd. Een student kan dus bewust iets verder reizen zodat een andere student niet onplaatsbaar wordt.
- Profilering gebruikt aanvullende capaciteit en staat los van J1/J2/J4/LANG.
- Namen, e-mailadressen en redenen van blokkades horen niet in de engine-input.

## Nog niet in v0.2

- Echte OV/fiets-route-API.
- Aankomsttijd 08:00/08:15 uit dienstregelingen.
- SharePoint/Forms/Power Automate-koppeling.
- Azure Function wrapper.
- Productie-authenticatie en auditlogging.
