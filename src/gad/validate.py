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


def _bands_overlap(a_min: float, a_max: float, a_min_i: bool, a_max_i: bool,
                   b_min: float, b_max: float, b_min_i: bool, b_max_i: bool) -> bool:
    """True if the two closed/open intervals share any real value."""
    if a_max < b_min:
        return False
    if b_max < a_min:
        return False
    if a_max == b_min:
        return a_max_i and b_min_i
    if b_max == a_min:
        return b_max_i and a_min_i
    return True


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
                    errors.append(
                        f"{s.scheme_id}: unverified field {path} not listed in unverified_fields"
                    )

        bands = s.degree_classification.bands
        for i, a in enumerate(bands):
            if a.min_value > a.max_value:
                errors.append(
                    f"{s.scheme_id}: classification band {a.name!r} has min_value > max_value"
                )
            for b in bands[i + 1 :]:
                if _bands_overlap(
                    a.min_value, a.max_value, a.min_inclusive, a.max_inclusive,
                    b.min_value, b.max_value, b.min_inclusive, b.max_inclusive,
                ):
                    errors.append(
                        f"{s.scheme_id}: overlapping classification bands "
                        f"{a.name!r} [{a.min_value},{a.max_value}] and "
                        f"{b.name!r} [{b.min_value},{b.max_value}] "
                        f"(engine prefers higher min_value at shared edges; still fix seed data)"
                    )
    return errors
