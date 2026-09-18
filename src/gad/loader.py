"""Load and index grading schemes from data/schemes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gad.models import GradingScheme

DEFAULT_DATA = Path(os.environ.get("GAD_DATA", Path(__file__).resolve().parents[2] / "data" / "schemes"))


class Catalog:
    def __init__(self, schemes: list[GradingScheme]):
        self.schemes = {s.scheme_id: s for s in schemes}

    @classmethod
    def load(cls, root: Path | None = None) -> "Catalog":
        root = root or DEFAULT_DATA
        schemes: list[GradingScheme] = []
        if not root.exists():
            raise FileNotFoundError(root)
        for path in sorted(root.glob("*.json")):
            if path.name.startswith("_"):
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload if isinstance(payload, list) else [payload]
            for rec in records:
                schemes.append(GradingScheme.model_validate(rec))
        return cls(schemes)

    def get(self, scheme_id: str) -> GradingScheme:
        return self.schemes[scheme_id]

    def list(self) -> list[GradingScheme]:
        return list(self.schemes.values())

    def resolve(
        self,
        university: str | None = None,
        country: str | None = None,
        faculty: str | None = None,
        degree_level: str | None = None,
        year: int | None = None,
    ) -> list[GradingScheme]:
        out = self.list()
        if university:
            u = university.lower()
            out = [s for s in out if u in s.university.slug or u in s.university.name.lower()]
        if country:
            c = country.lower()
            out = [s for s in out if c in s.country.iso2.lower() or c in s.country.name.lower()]
        if faculty:
            f = faculty.lower()
            out = [s for s in out if f in s.faculty_program.slug or f in s.faculty_program.name.lower()]
        if degree_level:
            out = [s for s in out if s.degree_level.value == degree_level]
        if year is not None:
            out = [
                s
                for s in out
                if s.academic_year.start <= year
                and (s.academic_year.open_ended or (s.academic_year.end or s.academic_year.start) >= year)
            ]
        return out
