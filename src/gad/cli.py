"""CLI: list schemes, resolve hierarchy, calculate GPA."""
from __future__ import annotations
import argparse, json, sys
from gad.engine import GPAEngine, TranscriptCourse
from gad.loader import Catalog
from gad.validate import validate_catalog

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="gad", description="Global academic grading database")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list"); p_list.add_argument("--country"); p_list.add_argument("--university")
    p_show = sub.add_parser("show"); p_show.add_argument("scheme_id")
    p_calc = sub.add_parser("calc"); p_calc.add_argument("scheme_id"); p_calc.add_argument("transcript")
    sub.add_parser("validate")
    args = parser.parse_args(argv)
    catalog = Catalog.load()
    if args.cmd == "list":
        for s in catalog.resolve(university=args.university, country=args.country):
            print(f"{s.scheme_id}\t{s.university.name}\t{s.country.iso2}\t{s.faculty_program.slug}\t{s.degree_level.value}\t{s.academic_year.label}")
        return 0
    if args.cmd == "show":
        print(catalog.get(args.scheme_id).model_dump_json(indent=2)); return 0
    if args.cmd == "validate":
        errs = validate_catalog(catalog)
        if errs:
            print("\n".join(errs), file=sys.stderr); return 1
        print(f"ok: {len(catalog.schemes)} schemes"); return 0
    if args.cmd == "calc":
        scheme = catalog.get(args.scheme_id)
        raw = json.loads(open(args.transcript, encoding="utf-8").read())
        result = GPAEngine().calculate(scheme, [TranscriptCourse(**row) for row in raw])
        print(json.dumps({"scheme_id": result.scheme_id, "metric": result.metric_name, "value": result.value, "scale": [result.scale_min, result.scale_max], "quality_points": result.quality_points, "gpa_credits": result.gpa_credits, "earned_credits": result.earned_credits, "classification": result.classification, "warnings": result.warnings, "courses": [c.__dict__ for c in result.courses]}, indent=2))
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
