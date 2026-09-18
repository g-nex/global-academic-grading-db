"""SQLite production store: init schema, ETL from JSON seeds, Catalog.from_db."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

from gad.loader import Catalog, DEFAULT_DATA
from gad.models import GradingScheme

DEFAULT_DB = Path(os.environ.get("GAD_DB", Path(__file__).resolve().parents[2] / "data" / "gad.sqlite3"))
SCHEMA_SQL = Path(__file__).resolve().parents[2] / "schema" / "sql" / "sqlite.sql"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or DEFAULT_DB
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(sql)
        conn.commit()
    return path


def _hash(obj: object) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def load_json_into_db(
    data_root: Path | None = None,
    db_path: Path | None = None,
    *,
    replace: bool = True,
) -> int:
    catalog = Catalog.load(data_root or DEFAULT_DATA)
    path = init_db(db_path) if replace or not (db_path or DEFAULT_DB).exists() else (db_path or DEFAULT_DB)
    conn = connect(path)
    if replace:
        for table in (
            "scheme_sources", "grading_schemes", "classification_bands", "grade_scale_boundaries",
            "sources", "classification_rules", "pass_fail_policies", "repeat_policies",
            "calculation_rules", "grade_scales", "faculty_programs", "universities", "countries",
        ):
            conn.execute(f"DELETE FROM {table}")
    for s in catalog.list():
        _upsert_scheme(conn, s)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM grading_schemes").fetchone()[0]
    conn.close()
    return int(n)


def _upsert_scheme(conn: sqlite3.Connection, s: GradingScheme) -> None:
    conn.execute("INSERT OR REPLACE INTO countries (iso2, name) VALUES (?, ?)", (s.country.iso2, s.country.name))
    conn.execute(
        "INSERT OR REPLACE INTO universities (slug, name, country_iso2, homepage) VALUES (?, ?, ?, ?)",
        (s.university.slug, s.university.name, s.university.country_iso2,
         str(s.university.homepage) if s.university.homepage else None),
    )
    conn.execute(
        """INSERT INTO faculty_programs (university_slug, slug, name, kind) VALUES (?, ?, ?, ?)
        ON CONFLICT (university_slug, slug) DO UPDATE SET name=excluded.name, kind=excluded.kind""",
        (s.university.slug, s.faculty_program.slug, s.faculty_program.name, s.faculty_program.kind),
    )
    fp_id = conn.execute(
        "SELECT id FROM faculty_programs WHERE university_slug=? AND slug=?",
        (s.university.slug, s.faculty_program.slug),
    ).fetchone()[0]

    boundaries = [b.model_dump(mode="json") for b in s.grade_boundaries]
    gs_hash = _hash(boundaries)
    gs_slug = f"scale-{gs_hash[:12]}"
    conn.execute(
        "INSERT INTO grade_scales (slug, name, content_hash) VALUES (?, ?, ?) ON CONFLICT(slug) DO UPDATE SET content_hash=excluded.content_hash",
        (gs_slug, f"Scale for {s.scheme_id}", gs_hash),
    )
    gs_id = conn.execute("SELECT id FROM grade_scales WHERE slug=?", (gs_slug,)).fetchone()[0]
    conn.execute("DELETE FROM grade_scale_boundaries WHERE grade_scale_id=?", (gs_id,))
    for b in s.grade_boundaries:
        conn.execute(
            """INSERT INTO grade_scale_boundaries (
                grade_scale_id, symbol, label, grade_points, min_percent, max_percent,
                passing, counts_toward_gpa, counts_toward_credits, notes, verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (gs_id, b.symbol, b.label, b.grade_points, b.min_percent, b.max_percent,
             int(b.passing), int(b.counts_toward_gpa), int(b.counts_toward_credits),
             b.notes, b.provenance.status.value),
        )

    calc = s.gpa_formula.model_dump(mode="json")
    calc_hash = _hash(calc)
    calc_slug = f"calc-{calc_hash[:12]}"
    conn.execute(
        """INSERT INTO calculation_rules (
            slug, name, kind, scale_max, scale_min, rounding, decimal_places,
            expression, description, content_hash, verification_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET content_hash=excluded.content_hash""",
        (calc_slug, f"Calc {s.scheme_id}", s.gpa_formula.kind.value, s.gpa_formula.scale_max,
         s.gpa_formula.scale_min, s.gpa_formula.rounding.value, s.gpa_formula.decimal_places,
         s.gpa_formula.expression, s.gpa_formula.description, calc_hash,
         s.gpa_formula.provenance.status.value),
    )
    calc_id = conn.execute("SELECT id FROM calculation_rules WHERE slug=?", (calc_slug,)).fetchone()[0]

    rep = s.repeat_course_rules.model_dump(mode="json")
    rep_hash = _hash(rep)
    rep_slug = f"rep-{rep_hash[:12]}"
    conn.execute(
        """INSERT INTO repeat_policies (slug, kind, replace_with, description, max_attempts, content_hash, verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(slug) DO UPDATE SET content_hash=excluded.content_hash""",
        (rep_slug, s.repeat_course_rules.kind.value, s.repeat_course_rules.replace_with,
         s.repeat_course_rules.description, s.repeat_course_rules.max_attempts, rep_hash,
         s.repeat_course_rules.provenance.status.value),
    )
    rep_id = conn.execute("SELECT id FROM repeat_policies WHERE slug=?", (rep_slug,)).fetchone()[0]

    pf = s.pass_fail.model_dump(mode="json")
    pf_hash = _hash(pf)
    pf_slug = f"pf-{pf_hash[:12]}"
    conn.execute(
        """INSERT INTO pass_fail_policies (slug, treatment, pass_symbols, fail_symbols, description, content_hash, verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(slug) DO UPDATE SET content_hash=excluded.content_hash""",
        (pf_slug, s.pass_fail.treatment.value, json.dumps(s.pass_fail.pass_symbols),
         json.dumps(s.pass_fail.fail_symbols), s.pass_fail.description, pf_hash,
         s.pass_fail.provenance.status.value),
    )
    pf_id = conn.execute("SELECT id FROM pass_fail_policies WHERE slug=?", (pf_slug,)).fetchone()[0]

    cl = s.degree_classification.model_dump(mode="json")
    cl_hash = _hash(cl)
    cl_slug = f"cl-{cl_hash[:12]}"
    conn.execute(
        """INSERT INTO classification_rules (slug, name, applies, description, extra_conditions, content_hash, verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(slug) DO UPDATE SET content_hash=excluded.content_hash""",
        (cl_slug, f"Class {s.scheme_id}", int(s.degree_classification.applies),
         s.degree_classification.description, json.dumps(s.degree_classification.extra_conditions),
         cl_hash, s.degree_classification.provenance.status.value),
    )
    cl_id = conn.execute("SELECT id FROM classification_rules WHERE slug=?", (cl_slug,)).fetchone()[0]
    conn.execute("DELETE FROM classification_bands WHERE classification_rule_id=?", (cl_id,))
    for band in s.degree_classification.bands:
        conn.execute(
            """INSERT INTO classification_bands (
                classification_rule_id, name, min_value, max_value, metric, min_inclusive, max_inclusive, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (cl_id, band.name, band.min_value, band.max_value, band.metric,
             int(band.min_inclusive), int(band.max_inclusive), band.notes),
        )

    doc = s.model_dump_json()
    conn.execute(
        """INSERT OR REPLACE INTO grading_schemes (
            scheme_id, university_slug, country_iso2, faculty_program_id, degree_level,
            year_start, year_end, year_label, open_ended, name,
            grade_scale_id, calculation_rule_id, repeat_policy_id, pass_fail_policy_id,
            classification_rule_id, credit_unit, typical_load, credit_notes,
            verification_date, unverified_fields, notes, document_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (s.scheme_id, s.university.slug, s.country.iso2, fp_id, s.degree_level.value,
         s.academic_year.start, s.academic_year.end, s.academic_year.label,
         int(s.academic_year.open_ended), s.name, gs_id, calc_id, rep_id, pf_id, cl_id,
         s.credit_system.unit.value, s.credit_system.typical_full_time_load_per_year,
         s.credit_system.conversion_notes, s.verification_date,
         json.dumps(s.unverified_fields), json.dumps(s.notes), doc),
    )

    for src in s.official_sources:
        sh = _hash({"url": str(src.url), "title": src.title})
        conn.execute(
            """INSERT INTO sources (title, url, source_class, content_hash, notes)
            VALUES (?, ?, ?, ?, ?) ON CONFLICT(content_hash) DO UPDATE SET title=excluded.title""",
            (src.title, str(src.url), src.source_class, sh, src.notes),
        )
        sid = conn.execute("SELECT id FROM sources WHERE content_hash=?", (sh,)).fetchone()[0]
        conn.execute(
            "INSERT OR REPLACE INTO scheme_sources (scheme_id, source_id, retrieved) VALUES (?, ?, ?)",
            (s.scheme_id, sid, src.retrieved),
        )


def catalog_from_db(db_path: Path | None = None) -> Catalog:
    conn = connect(db_path)
    rows = conn.execute("SELECT document_json FROM grading_schemes ORDER BY scheme_id").fetchall()
    conn.close()
    return Catalog([GradingScheme.model_validate_json(r["document_json"]) for r in rows])


def db_stats(db_path: Path | None = None) -> dict:
    conn = connect(db_path)
    stats = {
        "path": str(db_path or DEFAULT_DB),
        "schemes": conn.execute("SELECT COUNT(*) FROM grading_schemes").fetchone()[0],
        "universities": conn.execute("SELECT COUNT(*) FROM universities").fetchone()[0],
        "countries": conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0],
        "grade_scales": conn.execute("SELECT COUNT(*) FROM grade_scales").fetchone()[0],
        "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
    }
    conn.close()
    return stats
