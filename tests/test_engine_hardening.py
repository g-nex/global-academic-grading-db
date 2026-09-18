"""Hardening: validation, Decimal stability, repeat audit, strict mode."""

from __future__ import annotations

import pytest

from gad.engine import EngineError, GPAEngine, TranscriptCourse
from gad.loader import Catalog
from gad.models import (
    AcademicYear,
    ClassificationBand,
    Country,
    CreditSystem,
    CreditUnit,
    DegreeClassificationRules,
    DegreeLevel,
    FacultyProgram,
    GPAFormula,
    GPAFormulaKind,
    GradeBoundary,
    GradingScheme,
    PassFailRules,
    PassFailTreatment,
    RepeatCourseRules,
    RepeatPolicyKind,
    RoundingMode,
    University,
)


def _scheme(**kwargs) -> GradingScheme:
    defaults = dict(
        scheme_id="hard-synth",
        university=University(slug="h", name="H", country_iso2="XX"),
        country=Country(iso2="XX", name="X"),
        faculty_program=FacultyProgram(slug="all", name="All"),
        degree_level=DegreeLevel.UNDERGRADUATE,
        academic_year=AcademicYear(start=2020, label="2020+", open_ended=True),
        name="H",
        grade_boundaries=[
            GradeBoundary(symbol="A", grade_points=4.0),
            GradeBoundary(symbol="B", grade_points=3.0),
            GradeBoundary(symbol="F", grade_points=0.0, passing=False, counts_toward_credits=False),
            GradeBoundary(symbol="P", grade_points=None, counts_toward_gpa=False, passing=True),
        ],
        credit_system=CreditSystem(unit=CreditUnit.GENERIC_CREDIT),
        gpa_formula=GPAFormula(
            kind=GPAFormulaKind.WEIGHTED_MEAN,
            scale_max=4.0,
            rounding=RoundingMode.HALF_UP,
            decimal_places=2,
            description="w",
            expression="q/c",
        ),
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.LAST_ATTEMPT_ONLY, description="last"
        ),
        pass_fail=PassFailRules(
            treatment=PassFailTreatment.EXCLUDE_FROM_GPA,
            pass_symbols=["P"],
            fail_symbols=[],
            description="p",
        ),
        degree_classification=DegreeClassificationRules(applies=False, description="n"),
        official_sources=[],
        verification_date="2026-09-18",
    )
    defaults.update(kwargs)
    return GradingScheme(**defaults)


def test_negative_credits_excluded_with_warning():
    r = GPAEngine().calculate(
        _scheme(),
        [TranscriptCourse("X", -3, grade="A"), TranscriptCourse("Y", 3, grade="B")],
    )
    assert r.gpa_credits == 3
    assert r.value == 3.0
    assert any("negative" in w for w in r.warnings)


def test_strict_rejects_negative_credits():
    with pytest.raises(EngineError, match="negative"):
        GPAEngine().calculate(
            _scheme(),
            [TranscriptCourse("X", -1, grade="A")],
            strict=True,
        )


def test_empty_code_skipped():
    r = GPAEngine().calculate(
        _scheme(),
        [TranscriptCourse("  ", 3, grade="A"), TranscriptCourse("OK", 3, grade="A")],
    )
    assert r.gpa_credits == 3
    assert any("empty" in w for w in r.warnings)


def test_repeat_code_normalization_case_and_space():
    scheme = _scheme(
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.LAST_ATTEMPT_ONLY, description="last"
        )
    )
    r = GPAEngine().calculate(
        scheme,
        [
            TranscriptCourse("cs 101", 3, grade="F", attempt=1),
            TranscriptCourse("CS 101", 3, grade="A", attempt=2),
        ],
    )
    assert r.gpa_credits == 3
    assert r.value == 4.0
    assert r.extras["courses_dropped"] == 1
    assert any(c.reason == "dropped_by_repeat_policy" for c in r.courses)


def test_raw_value_preserved_before_rounding():
    scheme = Catalog.load().get("ca-mcgill-ug-current")
    r = GPAEngine().calculate(
        scheme,
        [
            TranscriptCourse("A1", 3, grade="A"),
            TranscriptCourse("B1", 3, grade="B+"),
            TranscriptCourse("C1", 3, grade="A-"),
        ],
    )
    assert r.value == 3.66
    assert r.raw_value is not None
    assert r.raw_value > 3.66


def test_zero_credit_course_does_not_change_gpa():
    r = GPAEngine().calculate(
        _scheme(),
        [
            TranscriptCourse("A", 3, grade="A"),
            TranscriptCourse("ZERO", 0, grade="F"),
        ],
    )
    assert r.value == 4.0
    assert any("zero credits" in w for w in r.warnings)


def test_attempt_below_one_coerced():
    r = GPAEngine().calculate(
        _scheme(
            repeat_course_rules=RepeatCourseRules(
                kind=RepeatPolicyKind.INCLUDE_ALL_ATTEMPTS, description="all"
            )
        ),
        [TranscriptCourse("X", 3, grade="A", attempt=0)],
    )
    assert r.value == 4.0
    assert any("attempt" in w for w in r.warnings)


def test_max_attempts_warning():
    scheme = _scheme(
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.LAST_ATTEMPT_ONLY,
            description="last",
            max_attempts=2,
        )
    )
    r = GPAEngine().calculate(
        scheme,
        [
            TranscriptCourse("X", 3, grade="F", attempt=1),
            TranscriptCourse("X", 3, grade="B", attempt=2),
            TranscriptCourse("X", 3, grade="A", attempt=3),
        ],
    )
    assert any("max_attempts" in w for w in r.warnings)
    assert r.value == 4.0


def test_classification_no_band_warns():
    scheme = _scheme(
        gpa_formula=GPAFormula(
            kind=GPAFormulaKind.WEIGHTED_MEAN,
            scale_max=4.0,
            rounding=RoundingMode.NONE,
            decimal_places=2,
            description="w",
            expression="q/c",
        ),
        degree_classification=DegreeClassificationRules(
            applies=True,
            description="narrow",
            bands=[ClassificationBand(name="Only high", min_value=3.5, max_value=4.0)],
        ),
    )
    r = GPAEngine().calculate(scheme, [TranscriptCourse("X", 3, grade="B")])
    assert r.classification is None
    assert any("matched no classification band" in w for w in r.warnings)


def test_extra_conditions_surfaced_as_warnings():
    scheme = _scheme(
        degree_classification=DegreeClassificationRules(
            applies=True,
            description="with extras",
            bands=[ClassificationBand(name="Pass", min_value=0, max_value=4)],
            extra_conditions=["Must complete final year project"],
        )
    )
    r = GPAEngine().calculate(scheme, [TranscriptCourse("X", 3, grade="A")])
    assert any("final year project" in w for w in r.warnings)


def test_decimal_accumulation_many_small_courses():
    scheme = _scheme(
        gpa_formula=GPAFormula(
            kind=GPAFormulaKind.WEIGHTED_MEAN,
            scale_max=4.0,
            rounding=RoundingMode.NONE,
            decimal_places=10,
            description="w",
            expression="q/c",
        ),
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.INCLUDE_ALL_ATTEMPTS, description="all"
        ),
    )
    courses = [TranscriptCourse(f"C{i}", 0.1, grade="A") for i in range(100)]
    courses += [TranscriptCourse(f"B{i}", 0.1, grade="B") for i in range(100)]
    r = GPAEngine().calculate(scheme, courses)
    assert abs(r.value - 3.5) < 1e-12


def test_seed_engines_still_pass_smoke():
    cat = Catalog.load()
    eng = GPAEngine()
    for sid in cat.schemes:
        s = cat.get(sid)
        r = eng.calculate(s, [])
        assert r.value is None
        assert r.scheme_id == sid
