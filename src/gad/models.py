"""Pydantic schema for the grading hierarchy.

Logical path (as specified):
  University → Country → Faculty/Program → Degree Level → Academic Year → Grading Scheme

Physical model stores Country as a first-class entity and University.country_iso2
as a foreign key so the graph is relationally normal and migrates cleanly to
Postgres. The logical path is reconstructed by Catalog.resolve().
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class DegreeLevel(str, Enum):
    UNDERGRADUATE = "undergraduate"
    BACHELORS = "bachelors"
    HONOURS = "honours"
    INTEGRATED_MASTERS = "integrated_masters"
    POSTGRADUATE_TAUGHT = "postgraduate_taught"
    MASTERS = "masters"
    DOCTORAL = "doctoral"
    PROFESSIONAL = "professional"
    LAW = "law"
    MEDICINE = "medicine"
    ALL = "all"


class CreditUnit(str, Enum):
    SEMESTER_HOUR = "semester_hour"
    QUARTER_HOUR = "quarter_hour"
    ECTS = "ects"
    UK_CATS = "uk_cats"
    MIT_UNIT = "mit_unit"
    NUS_UNIT = "nus_unit"
    MELBOURNE_CREDIT_POINT = "melbourne_credit_point"
    GENERIC_CREDIT = "generic_credit"
    MODULE = "module"
    NONE = "none"


class GPAFormulaKind(str, Enum):
    WEIGHTED_MEAN = "weighted_mean"
    WAM_PERCENT = "wam_percent"
    UNWEIGHTED_MEAN = "unweighted_mean"
    CUSTOM = "custom"


class RoundingMode(str, Enum):
    NONE = "none"
    HALF_UP = "half_up"
    HALF_EVEN = "half_even"
    TRUNCATE = "truncate"
    SYMMETRIC_NEAREST = "symmetric_nearest"


class RepeatPolicyKind(str, Enum):
    INCLUDE_ALL_ATTEMPTS = "include_all_attempts"
    LAST_ATTEMPT_ONLY = "last_attempt_only"
    BEST_ATTEMPT_ONLY = "best_attempt_only"
    REPLACE_POINTS_CREDIT_ONCE = "replace_points_credit_once"
    UNKNOWN = "unknown"


class PassFailTreatment(str, Enum):
    EXCLUDE_FROM_GPA = "exclude_from_gpa"
    INCLUDE_FAIL_ONLY = "include_fail_only"
    INCLUDE_BOTH = "include_both"
    CONVERT_TO_LETTER = "convert_to_letter"


class FieldProvenance(BaseModel):
    status: VerificationStatus = VerificationStatus.VERIFIED
    note: str | None = None
    source_url: HttpUrl | None = None


class GradeBoundary(BaseModel):
    symbol: str
    label: str | None = None
    grade_points: float | None = None
    min_percent: float | None = None
    max_percent: float | None = None
    passing: bool = True
    counts_toward_gpa: bool = True
    counts_toward_credits: bool = True
    notes: str | None = None
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class CreditSystem(BaseModel):
    unit: CreditUnit
    typical_full_time_load_per_year: float | None = None
    conversion_notes: str | None = None
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class GPAFormula(BaseModel):
    kind: GPAFormulaKind
    scale_max: float
    scale_min: float = 0.0
    rounding: RoundingMode = RoundingMode.NONE
    decimal_places: int = 2
    description: str
    expression: str
    extras: dict[str, Any] = Field(default_factory=dict)
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class RepeatCourseRules(BaseModel):
    """How repeated course attempts enter the GPA calculation.

    - include_all_attempts: every attempt contributes points and credits.
    - last_attempt_only: only the highest attempt number is kept.
    - best_attempt_only: highest grade points, then percent, then later attempt.
      Institutional side conditions are not modelled.
    - replace_points_credit_once: one credit-bearing result retained;
      replace_with is last (default) or best. Not an average of attempts.
    - unknown: all attempts included; engine emits a warning.
    """

    kind: RepeatPolicyKind
    description: str
    max_attempts: int | None = None
    replace_with: Literal["last", "best"] = "last"
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class PassFailRules(BaseModel):
    treatment: PassFailTreatment
    pass_symbols: list[str] = Field(default_factory=list)
    fail_symbols: list[str] = Field(default_factory=list)
    description: str
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class ClassificationBand(BaseModel):
    """One award class interval. Prefer non-overlapping ranges in seed data.
    On overlap, engine sorts by min_value descending so the higher class wins.
    """

    name: str
    min_value: float
    max_value: float
    metric: Literal["gpa", "percent", "wam", "usm", "cgpa", "other"] = "gpa"
    min_inclusive: bool = True
    max_inclusive: bool = True
    notes: str | None = None

    def contains(self, value: float) -> bool:
        lo_ok = value >= self.min_value if self.min_inclusive else value > self.min_value
        hi_ok = value <= self.max_value if self.max_inclusive else value < self.max_value
        return lo_ok and hi_ok


class DegreeClassificationRules(BaseModel):
    applies: bool
    description: str
    bands: list[ClassificationBand] = Field(default_factory=list)
    extra_conditions: list[str] = Field(default_factory=list)
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class OfficialSource(BaseModel):
    title: str
    url: HttpUrl
    source_class: Literal[
        "academic_regulations",
        "student_handbook",
        "registrar",
        "examination_regulations",
        "transcript_legend",
        "degree_classification",
        "programme_handbook",
    ]
    retrieved: str
    notes: str | None = None


class Country(BaseModel):
    iso2: str
    name: str


class University(BaseModel):
    slug: str
    name: str
    country_iso2: str
    homepage: HttpUrl | None = None


class FacultyProgram(BaseModel):
    slug: str
    name: str
    kind: Literal["university_wide", "faculty", "school", "program"] = "university_wide"


class AcademicYear(BaseModel):
    start: int
    end: int | None = None
    label: str
    open_ended: bool = False


class GradingScheme(BaseModel):
    scheme_id: str
    university: University
    country: Country
    faculty_program: FacultyProgram
    degree_level: DegreeLevel
    academic_year: AcademicYear
    name: str
    grade_boundaries: list[GradeBoundary]
    credit_system: CreditSystem
    gpa_formula: GPAFormula
    repeat_course_rules: RepeatCourseRules
    pass_fail: PassFailRules
    degree_classification: DegreeClassificationRules
    official_sources: list[OfficialSource]
    verification_date: str
    unverified_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("scheme_id")
    @classmethod
    def slugish(cls, v: str) -> str:
        if not v or " " in v:
            raise ValueError("scheme_id must be a non-empty slug without spaces")
        return v

    def symbols(self) -> dict[str, GradeBoundary]:
        return {g.symbol.upper(): g for g in self.grade_boundaries}

    def lookup_grade(self, symbol: str) -> GradeBoundary | None:
        return self.symbols().get(symbol.strip().upper())

    def grade_from_percent(self, percent: float) -> GradeBoundary | None:
        hits = [
            g
            for g in self.grade_boundaries
            if g.min_percent is not None
            and g.max_percent is not None
            and g.min_percent <= percent <= g.max_percent
        ]
        return hits[0] if hits else None
