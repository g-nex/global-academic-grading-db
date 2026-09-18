"""Production HTTP API (FastAPI).

Run: gad serve --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from gad.db import catalog_from_db, db_stats, load_json_into_db
from gad.engine import GPAEngine, TranscriptCourse
from gad.loader import Catalog

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as e:  # pragma: no cover
    raise SystemExit("Install API extras: pip install 'gad[api]'") from e


class CourseIn(BaseModel):
    code: str
    credits: float
    grade: str | None = None
    percent: float | None = None
    attempt: int = 1
    term: str | None = None
    pass_fail: bool = False


class CalculateRequest(BaseModel):
    scheme_id: str
    courses: list[CourseIn]
    strict: bool = False


class CalculateResponse(BaseModel):
    scheme_id: str
    metric: str
    value: float | None
    raw_value: float | None = None
    scale: list[float]
    quality_points: float
    gpa_credits: float
    earned_credits: float
    classification: str | None
    warnings: list[str]
    courses: list[dict[str, Any]]
    extras: dict[str, Any] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def _catalog() -> Catalog:
    db = os.environ.get("GAD_DB")
    if db and Path(db).exists():
        return catalog_from_db(Path(db))
    default_db = Path(__file__).resolve().parents[2] / "data" / "gad.sqlite3"
    if default_db.exists():
        return catalog_from_db(default_db)
    return Catalog.load()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Global Academic Grading Database",
        description="Official-source grading schemes and rules-driven GPA/WAM engine",
        version="0.2.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("GAD_CORS", "*").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        cat = _catalog()
        return {"status": "ok", "schemes": len(cat.schemes)}

    @app.get("/stats")
    def stats() -> dict[str, Any]:
        db = os.environ.get("GAD_DB")
        path = Path(db) if db else Path(__file__).resolve().parents[2] / "data" / "gad.sqlite3"
        if path.exists():
            return db_stats(path)
        return {"schemes": len(_catalog().schemes), "note": "JSON-only"}

    @app.get("/schemes")
    def list_schemes(
        country: str | None = None,
        university: str | None = None,
        degree_level: str | None = None,
        year: int | None = Query(None),
    ) -> list[dict[str, Any]]:
        rows = _catalog().resolve(country=country, university=university, degree_level=degree_level, year=year)
        return [
            {
                "scheme_id": s.scheme_id,
                "university": s.university.name,
                "country": s.country.iso2,
                "degree_level": s.degree_level.value,
                "year_label": s.academic_year.label,
                "name": s.name,
                "gpa_kind": s.gpa_formula.kind.value,
                "scale_max": s.gpa_formula.scale_max,
                "verification_date": s.verification_date,
                "unverified_fields": s.unverified_fields,
            }
            for s in rows
        ]

    @app.get("/schemes/{scheme_id}")
    def get_scheme(scheme_id: str) -> dict[str, Any]:
        try:
            return _catalog().get(scheme_id).model_dump(mode="json")
        except KeyError as e:
            raise HTTPException(404, f"scheme not found: {scheme_id}") from e

    @app.post("/calculate", response_model=CalculateResponse)
    def calculate(body: CalculateRequest) -> CalculateResponse:
        try:
            scheme = _catalog().get(body.scheme_id)
        except KeyError as e:
            raise HTTPException(404, f"scheme not found: {body.scheme_id}") from e
        courses = [TranscriptCourse(**c.model_dump()) for c in body.courses]
        try:
            result = GPAEngine().calculate(scheme, courses, strict=body.strict)
        except Exception as e:
            raise HTTPException(400, str(e)) from e
        return CalculateResponse(
            scheme_id=result.scheme_id,
            metric=result.metric_name,
            value=result.value,
            raw_value=result.raw_value,
            scale=[result.scale_min, result.scale_max],
            quality_points=result.quality_points,
            gpa_credits=result.gpa_credits,
            earned_credits=result.earned_credits,
            classification=result.classification,
            warnings=result.warnings,
            courses=[c.__dict__ for c in result.courses],
            extras=result.extras,
        )

    @app.post("/admin/reload")
    def reload_from_json() -> dict[str, Any]:
        n = load_json_into_db(replace=True)
        _catalog.cache_clear()
        return {"reloaded": n, "stats": db_stats()}

    return app


app = create_app()
