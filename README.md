# Global Academic Grading Database

Public database of **institution-specific** academic grading schemes plus a
rules-driven GPA / WAM engine, SQLite store, and production HTTP API.

Schemes are taken from official university pages (regulations, registrar,
examination conventions, transcript legends). Fields the official page does
not state are listed in `unverified_fields`.

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

### Production API + SQLite

```bash
pip install -e ".[api]"
gad db-load                    # ETL JSON → data/gad.sqlite3
gad db-stats
gad serve --host 0.0.0.0 --port 8000
```

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + scheme count |
| `GET /stats` | SQLite row counts |
| `GET /schemes` | Filter by country, university, degree_level, year |
| `GET /schemes/{id}` | Full scheme document |
| `POST /calculate` | GPA/WAM/classification for a transcript |
| `POST /admin/reload` | Re-ETL JSON into SQLite |

## Seed coverage (verification date 2026-09-18)

**14 schemes** across **6 countries** — research spine, not a world census.

See [docs/COVERAGE.md](docs/COVERAGE.md).

## Licence

MIT.
