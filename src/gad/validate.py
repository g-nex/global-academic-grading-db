"""Validate seed files against the Pydantic schema and sourcing rules."""

from __future__ import annotations

from gad.loader import Catalog
from gad.models import VerificationStatus

REQUIRED_SCHEME_FIELDS = (
    "grade_boundaries",
    "credit_system",
    "gpa_formula",
    "repeat_course_rules",
    "pass_fail",
    "degree_classification",
    "official_sources",
    "verification_date",
)


def validate_catalog(catalog: Catalog) -> list[str]:
    errors: list[str] = []
    for s in catalog.list():
        if not s.official_sources:
            errors.append(f"{s.scheme_id}: missing official_sources")
        if not s.grade_boundaries:
            errors.append(f"{s.scheme_id}: no grade boundaries")
        if not s.verification_date:
            errors.append(f"{s.scheme_id}: missing verification_date")
        for g in s.grade_boundaries:
            if g.provenance.status == VerificationStatus.UNVERIFIED:
                path = f"grade_boundaries[{g.symbol}]"
                if path not in s.unverified_fields:
                    errors.append(f"{s.scheme_id}: unverified field {path} not listed in unverified_fields")
    return errors
