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

UC Berkeley, MIT, UNC–Chapel Hill, McGill, University of Toronto, Oxford, NUS, University of Melbourne, University of Delhi (UGCF 2022).

Starter spine, not a world census. Add one official JSON file per distinct scheme.

## Licence

MIT. Official source text remains the property of each university.
