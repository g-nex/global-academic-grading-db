"""Synthetic schemes for classification boundaries and repeat-policy edges."""

from __future__ import annotations

from gad.engine import GPAEngine, TranscriptCourse
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
from gad.validate import _bands_overlap, validate_catalog


def _base_scheme(**kwargs) -> GradingScheme:
    defaults = dict(
        scheme_id="synthetic-edge",
        university=University(slug="synth", name="Synth U", country_iso2="XX"),
        country=Country(iso2="XX", name="Testland"),
        faculty_program=FacultyProgram(slug="all", name="All"),
        degree_level=DegreeLevel.UNDERGRADUATE,
        academic_year=AcademicYear(start=2020, label="2020+", open_ended=True),
        name="Synthetic",
        grade_boundaries=[
            GradeBoundary(symbol="A", grade_points=4.0),
            GradeBoundary(symbol="B", grade_points=3.0),
            GradeBoundary(symbol="C", grade_points=2.0),
            GradeBoundary(symbol="F", grade_points=0.0, passing=False, counts_toward_credits=False),
        ],
        credit_system=CreditSystem(unit=CreditUnit.GENERIC_CREDIT),
        gpa_formula=GPAFormula(
            kind=GPAFormulaKind.WEIGHTED_MEAN,
            scale_max=4.0,
            rounding=RoundingMode.NONE,
            decimal_places=2,
            description="test",
            expression="sum(gp*c)/sum(c)",
        ),
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.INCLUDE_ALL_ATTEMPTS, description="default"
        ),
        pass_fail=PassFailRules(treatment=PassFailTreatment.EXCLUDE_FROM_GPA, description="none"),
        degree_classification=DegreeClassificationRules(applies=False, description="n/a"),
        official_sources=[],
        verification_date="2026-09-18",
    )
    defaults.update(kwargs)
    return GradingScheme(**defaults)


def _wam_scheme(**kwargs) -> GradingScheme:
    return _base_scheme(
        grade_boundaries=[
            GradeBoundary(
                symbol="MARK",
                grade_points=None,
                min_percent=0,
                max_percent=100,
                passing=True,
                counts_toward_gpa=True,
                counts_toward_credits=True,
            ),
        ],
        gpa_formula=GPAFormula(
            kind=GPAFormulaKind.WAM_PERCENT,
            scale_max=100,
            rounding=RoundingMode.NONE,
            decimal_places=0,
            description="wam",
            expression="avg",
        ),
        **kwargs,
    )


def test_overlapping_bands_prefer_higher_class():
    scheme = _wam_scheme(
        degree_classification=DegreeClassificationRules(
            applies=True,
            description="deliberately overlapping",
            bands=[
                ClassificationBand(name="Upper Second", min_value=60, max_value=70),
                ClassificationBand(name="First Class", min_value=70, max_value=100),
            ],
        ),
    )
    result = GPAEngine().calculate(scheme, [TranscriptCourse("P1", 1, percent=70)])
    assert result.value == 70
    assert result.classification == "First Class"


def test_exclusive_upper_bound_avoids_shared_edge():
    scheme = _wam_scheme(
        degree_classification=DegreeClassificationRules(
            applies=True,
            description="half-open style",
            bands=[
                ClassificationBand(name="Upper Second", min_value=60, max_value=70, max_inclusive=False),
                ClassificationBand(name="First Class", min_value=70, max_value=100),
            ],
        ),
    )
    engine = GPAEngine()
    assert engine.calculate(scheme, [TranscriptCourse("P", 1, percent=69)]).classification == "Upper Second"
    assert engine.calculate(scheme, [TranscriptCourse("P", 1, percent=70)]).classification == "First Class"


def test_replace_points_credit_once_defaults_to_last():
    scheme = _base_scheme(
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.REPLACE_POINTS_CREDIT_ONCE,
            description="credits once; last replaces",
            replace_with="last",
        )
    )
    result = GPAEngine().calculate(
        scheme,
        [
            TranscriptCourse("CHEM", 3, grade="A", attempt=1),
            TranscriptCourse("CHEM", 3, grade="B", attempt=2),
        ],
    )
    assert result.gpa_credits == 3
    assert result.value == 3.0


def test_replace_points_credit_once_can_use_best():
    scheme = _base_scheme(
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.REPLACE_POINTS_CREDIT_ONCE,
            description="credits once; best replaces",
            replace_with="best",
        )
    )
    result = GPAEngine().calculate(
        scheme,
        [
            TranscriptCourse("CHEM", 3, grade="A", attempt=1),
            TranscriptCourse("CHEM", 3, grade="B", attempt=2),
        ],
    )
    assert result.gpa_credits == 3
    assert result.value == 4.0


def test_best_attempt_tie_break_prefers_later_attempt():
    scheme = _base_scheme(
        repeat_course_rules=RepeatCourseRules(
            kind=RepeatPolicyKind.BEST_ATTEMPT_ONLY, description="best by points"
        )
    )
    result = GPAEngine().calculate(
        scheme,
        [
            TranscriptCourse("X", 3, grade="B", attempt=1),
            TranscriptCourse("X", 3, grade="B", attempt=2),
        ],
    )
    assert result.gpa_credits == 3
    assert result.value == 3.0


def test_bands_overlap_helper():
    assert _bands_overlap(60, 70, True, True, 70, 100, True, True) is True
    assert _bands_overlap(60, 69, True, True, 70, 100, True, True) is False
    assert _bands_overlap(60, 70, True, False, 70, 100, True, True) is False


def test_seed_catalog_still_valid():
    assert validate_catalog(Catalog.load()) == []
