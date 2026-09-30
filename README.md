# StagePlaatser Engine v0.3

Werkende proof-of-concept voor de dNP-stageplaatsingspuzzel met Python + Google OR-Tools CP-SAT.

## Nieuw in v0.3

Naast de v0.2-engine bevat deze versie een **zichtbare fictieve simulatie**:

- 50 fictieve studenten;
- 12 fictieve scholen;
- rondevolgorde **J4 -> Langstudeerders -> Profilering S1/S2 -> J2 -> J1**;
- geen reguliere Jaar 3;
- 8 profileringen;
- maximaal 2 profileringen per student per semester;
- harde student-schoolblokkades;
- fictieve OV- en fietstijden;
- OV <= 60 minuten of fiets <= 30 minuten = normaal bereikbaar;
- slechtere bereikbaarheid blijft mogelijk, maar gaat naar **Human Review**;
- globale optimalisatie in plaats van greedy dichtstbijzijnde-schoollogica;
- strategische schaarste/reservecapaciteit zichtbaar in de output;
- resterende capaciteit en niet-geplaatste studenten;
- JSON-output, leesbaar tekstverslag én statisch HTML-dashboard;
- herplaatsingsfunctie uit v0.2 blijft aanwezig.

Alle studenten, scholen, blokkades en reistijden in de simulatie zijn fictief.

## Installeren

```bash
pip install -r requirements.txt
```

## Tests

Gebruik in GitHub Codespaces bij voorkeur:

```bash
python -m pytest -q
```

Door `pytest.ini` hoort ook dit nu te werken:

```bash
pytest -q
```

## De fictieve simulatie draaien

```bash
python -m engine.simulation
```

Daarna staan ook deze bestanden klaar:

```text
output/simulation.json
output/simulation.txt
output/simulation.html
output/simulation.html
```

Een andere vaste seed gebruiken:

```bash
python -m engine.simulation --seed 12345
```

## Een losse reguliere ronde oplossen

```bash
python -m engine.optimizer data/test_regular.json --output output/regular_result.json
```

## Een losse profileringsronde oplossen

```bash
python -m engine.optimizer data/test_profiles.json --output output/profile_result.json
```

## Belangrijke ontwerpregels

1. Plaats zo veel mogelijk studenten.
2. Geef normale bereikbaarheid voorrang.
3. Beperk reistijd daarna zo veel mogelijk.
4. Houd rekening met schaarste, zodat een flexibele student niet onnodig de enige optie van een inflexibele student inneemt.
5. Een actieve blokkade is absoluut: die combinatie wordt nooit voorgesteld.
6. Een route buiten de normale OV/fietsgrens is geen automatische afwijzing; deze wordt gemarkeerd voor Human Review.
7. Profilering heeft aanvullende capaciteit en staat los van reguliere capaciteit.
8. Namen, e-mailadressen en interne redenen voor blokkades horen niet in de optimizer-input.

## Nog niet productie-klaar

- echte OV/fiets-route-API;
- aankomsttijd 08:00/08:15 uit actuele dienstregelingen;
- SharePoint/Forms/Power Automate-koppeling;
- Azure Function wrapper;
- authenticatie, autorisaties en volledig auditlog;
- definitieve menselijke goedkeuringsworkflow.
