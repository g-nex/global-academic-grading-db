# Global Academic Grading Database

Public database of **institution-specific** academic grading schemes plus a rules-driven GPA / WAM engine.

Schemes are taken from official university pages (regulations, registrar, examination conventions, transcript legends). Fields the official page does not state are listed in `unverified_fields`.

**Repository:** https://github.com/g-nex/global-academic-grading-db

## Hierarchy

```
University → Country → Faculty/Program → Degree Level → Academic Year → Grading Scheme
```

Every distinct scheme is its own record. See [docs/HIERARCHY.md](docs/HIERARCHY.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
gad validate
gad list
gad show us-mit-ug-5pt-current
gad calc us-berkeley-ug-letter-current examples/transcript-berkeley.json
pytest
```

## Layout

| Path | Role |
|---|---|
| `src/gad/models.py` | Pydantic schema |
| `src/gad/engine.py` | GPA / WAM / classification engine |
| `src/gad/loader.py` | Catalog + hierarchy resolver |
| `src/gad/ingest.py` | Seed write helper |
| `data/schemes/*.json` | Official-source seed records |
| `schema/sql/postgres.sql` | Target relational DDL |
| `docs/` | Hierarchy, sourcing, verification, migration |

## Seed coverage (verification date 2026-09-18)

**9 schemes committed under `data/schemes/`:**

| File | scheme_id | Institution | Country | Metric |
|---|---|---|---|---|
| `us-berkeley-ug-letter.json` | `us-berkeley-ug-letter-current` | UC Berkeley | US | 4.0 GPA |
| `us-mit-ug-5pt.json` | `us-mit-ug-5pt-current` | MIT | US | 5.0 GPA |
| `us-unc-ug.json` | `us-unc-chapel-hill-ug` | UNC–Chapel Hill | US | 4.0 GPA |
| `ca-mcgill-ug.json` | `ca-mcgill-ug-current` | McGill | CA | 4.0 GPA (truncate 2 d.p.) |
| `ca-toronto-ug.json` | `ca-toronto-ug-refined-letter` | University of Toronto | CA | 4.0 GPA + % bands |
| `uk-oxford-ug-usm.json` | `uk-oxford-ug-usm-honour-school` | University of Oxford | GB | USM / honours class |
| `sg-nus-ug-gpa.json` | `sg-nus-ug-gpa-2021-present` | NUS | SG | 5.0 GPA (ex-CAP) |
| `au-unimelb-wam.json` | `au-unimelb-ug-wam-current` | University of Melbourne | AU | WAM |
| `in-du-ugcf-2022.json` | `in-delhi-ugcf-2022` | University of Delhi (UGCF 2022) | IN | 10-point CGPA |

Starter spine, not a world census. Add one official JSON file per distinct scheme; do not collapse faculty- or year-specific variants.

## Licence

MIT. Official source text remains the property of each university.
