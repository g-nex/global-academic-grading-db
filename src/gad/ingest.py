"""Seed-data ingest helpers."""

from __future__ import annotations

import json
from pathlib import Path

from gad.models import GradingScheme

SOURCE_PRIORITY = [
    "academic_regulations",
    "student_handbook",
    "registrar",
    "examination_regulations",
    "transcript_legend",
    "degree_classification",
    "programme_handbook",
]


def write_scheme(scheme: GradingScheme, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{scheme.scheme_id}.json"
    path.write_text(scheme.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_json_file(path: Path) -> GradingScheme:
    return GradingScheme.model_validate(json.loads(path.read_text(encoding="utf-8")))
