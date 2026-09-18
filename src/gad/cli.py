"""CLI: list schemes, resolve hierarchy, calculate GPA, SQLite ETL, serve API."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gad", description="Global academic grading database")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List loaded schemes")
    p_list.add_argument("--country")
    p_list.add_argument("--university")

    p_show = sub.add_parser("show", help="Print one scheme as JSON")
    p_show.add_argument("scheme_id")

    p_calc = sub.add_parser("calc", help="Calculate GPA from a JSON transcript")
    p_calc.add_argument("scheme_id")
    p_calc.add_argument("transcript")

    sub.add_parser("validate", help="Validate seed data")

    p_db = sub.add_parser("db-init", help="Create empty SQLite schema")
    p_db.add_argument("--db", default=None)

    p_load = sub.add_parser("db-load", help="ETL JSON seeds into SQLite")
    p_load.add_argument("--db", default=None)
    p_load.add_argument("--data", default=None)

    p_stats = sub.add_parser("db-stats", help="Show SQLite row counts")
    p_stats.add_argument("--db", default=None)

    p_serve = sub.add_parser("serve", help="Run production API (uvicorn)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--db", default=None)
    p_serve.add_argument("--reload", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "db-init":
        from pathlib import Path
        from gad.db import init_db
        path = init_db(Path(args.db) if args.db else None)
        print(f"initialized {path}")
        return 0

    if args.cmd == "db-load":
        from pathlib import Path
        from gad.db import load_json_into_db
        n = load_json_into_db(
            Path(args.data) if args.data else None,
            Path(args.db) if args.db else None,
            replace=True,
        )
        print(f"loaded {n} schemes into SQLite")
        return 0

    if args.cmd == "db-stats":
        from pathlib import Path
        from gad.db import db_stats
        print(json.dumps(db_stats(Path(args.db) if args.db else None), indent=2))
        return 0

    if args.cmd == "serve":
        import os
        if args.db:
            os.environ["GAD_DB"] = args.db
        else:
            from pathlib import Path
            from gad.db import DEFAULT_DB, load_json_into_db
            if not DEFAULT_DB.exists():
                load_json_into_db(replace=True)
            os.environ.setdefault("GAD_DB", str(DEFAULT_DB))
        try:
            import uvicorn
        except ImportError:
            print("Install API extras: pip install 'gad[api]'", file=sys.stderr)
            return 1
        uvicorn.run("gad.api:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    from gad.engine import GPAEngine, TranscriptCourse
    from gad.loader import Catalog
    from gad.validate import validate_catalog

    catalog = Catalog.load()

    if args.cmd == "list":
        for s in catalog.resolve(university=args.university, country=args.country):
            print(
                f"{s.scheme_id}\t{s.university.name}\t{s.country.iso2}\t"
                f"{s.faculty_program.slug}\t{s.degree_level.value}\t{s.academic_year.label}"
            )
        return 0

    if args.cmd == "show":
        print(catalog.get(args.scheme_id).model_dump_json(indent=2))
        return 0

    if args.cmd == "validate":
        errs = validate_catalog(catalog)
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 1
        print(f"ok: {len(catalog.schemes)} schemes")
        return 0

    if args.cmd == "calc":
        scheme = catalog.get(args.scheme_id)
        raw = json.loads(open(args.transcript, encoding="utf-8").read())
        result = GPAEngine().calculate(scheme, [TranscriptCourse(**row) for row in raw])
        print(
            json.dumps(
                {
                    "scheme_id": result.scheme_id,
                    "metric": result.metric_name,
                    "value": result.value,
                    "raw_value": result.raw_value,
                    "scale": [result.scale_min, result.scale_max],
                    "quality_points": result.quality_points,
                    "gpa_credits": result.gpa_credits,
                    "earned_credits": result.earned_credits,
                    "classification": result.classification,
                    "warnings": result.warnings,
                    "courses": [c.__dict__ for c in result.courses],
                },
                indent=2,
            )
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
