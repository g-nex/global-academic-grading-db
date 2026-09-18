"""Rules-driven calculation coverage against official seed schemes."""

from __future__ import annotations

import pytest

from gad.engine import GPAEngine, TranscriptCourse
from gad.loader import Catalog
from gad.models import RoundingMode


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog.load()


@pytest.fixture
def engine() -> GPAEngine:
    return GPAEngine()


def test_berkeley_weighted_gpa_excludes_pass(catalog, engine):
    scheme = catalog.get("us-berkeley-ug-letter-current")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("HIST", 4, grade="A"),
            TranscriptCourse("MATH", 4, grade="B+"),
            TranscriptCourse("PE", 2, grade="P"),
        ],
    )
    assert result.metric_name == "gpa"
    assert result.gpa_credits == 8
    assert abs(result.value - (4.0 * 4 + 3.3 * 4) / 8) < 1e-9
    assert result.earned_credits == 10


def test_berkeley_fail_counts_in_gpa_not_earned(catalog, engine):
    scheme = catalog.get("us-berkeley-ug-letter-current")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("X", 4, grade="A"),
            TranscriptCourse("Y", 4, grade="F"),
        ],
    )
    assert result.gpa_credits == 8
    assert abs(result.value - (4.0 * 4 + 0.0 * 4) / 8) < 1e-9
    assert result.earned_credits == 4


def test_nus_weighted_gpa_a_plus_equals_a(catalog, engine):
    scheme = catalog.get("sg-nus-ug-gpa-2021-present")
    aplus = engine.calculate(scheme, [TranscriptCourse("X", 4, grade="A+")])
    a = engine.calculate(scheme, [TranscriptCourse("X", 4, grade="A")])
    assert aplus.value == a.value == 5.0


def test_nus_mixed_grades(catalog, engine):
    scheme = catalog.get("sg-nus-ug-gpa-2021-present")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("CS1010", 4, grade="A-"),
            TranscriptCourse("MA1101", 4, grade="B+"),
            TranscriptCourse("GEA1000", 4, grade="S"),
        ],
    )
    assert result.gpa_credits == 8
    assert abs(result.value - (4.5 * 4 + 4.0 * 4) / 8) < 1e-9


def test_delhi_cgpa_ten_point(catalog, engine):
    scheme = catalog.get("in-delhi-ugcf-2022")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("C1", 4, grade="O"),
            TranscriptCourse("C2", 4, grade="A+"),
            TranscriptCourse("C3", 4, grade="B"),
        ],
    )
    assert result.scale_max == 10.0
    expected = (10 * 4 + 9 * 4 + 6 * 4) / 12
    assert abs(result.value - expected) < 1e-9


def test_mcgill_truncates_not_rounds(catalog, engine):
    scheme = catalog.get("ca-mcgill-ug-current")
    assert scheme.gpa_formula.rounding == RoundingMode.TRUNCATE
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("A1", 3, grade="A"),
            TranscriptCourse("B1", 3, grade="B+"),
            TranscriptCourse("C1", 3, grade="A-"),
        ],
    )
    raw = (4.0 * 3 + 3.3 * 3 + 3.7 * 3) / 9
    assert raw > 3.66
    assert result.value == 3.66


def test_mit_rounds_half_up_one_decimal(catalog, engine):
    scheme = catalog.get("us-mit-ug-5pt-current")
    assert scheme.gpa_formula.rounding == RoundingMode.HALF_UP
    assert scheme.gpa_formula.decimal_places == 1
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("A", 12, grade="A"),
            TranscriptCourse("B", 12, grade="B"),
            TranscriptCourse("C", 6, grade="C"),
        ],
    )
    assert result.value == 4.2


def test_mit_half_up_rounds_up_from_5(catalog, engine):
    scheme = catalog.get("us-mit-ug-5pt-current")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("A", 15, grade="A"),
            TranscriptCourse("B", 5, grade="B"),
        ],
    )
    assert result.value == 4.8


def test_melbourne_wam_includes_fails_excludes_cmp(catalog, engine):
    scheme = catalog.get("au-unimelb-ug-wam-current")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("SUB1", 12.5, percent=80, grade="H1"),
            TranscriptCourse("SUB2", 12.5, percent=40, grade="N"),
            TranscriptCourse("SUB3", 12.5, grade="CMP", pass_fail=True),
        ],
    )
    assert result.metric_name == "wam"
    assert abs(result.value - (80 * 12.5 + 40 * 12.5) / 25) < 1e-9


def test_melbourne_wam_all_pass_marks(catalog, engine):
    scheme = catalog.get("au-unimelb-ug-wam-current")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("S1", 12.5, percent=85),
            TranscriptCourse("S2", 12.5, percent=75),
            TranscriptCourse("S3", 25.0, percent=70),
        ],
    )
    expected = (85 * 12.5 + 75 * 12.5 + 70 * 25) / 50
    assert abs(result.value - expected) < 1e-9


def test_oxford_class_upper_second(catalog, engine):
    scheme = catalog.get("uk-oxford-ug-usm-honour-school")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("P1", 1, percent=72),
            TranscriptCourse("P2", 1, percent=64),
        ],
    )
    assert result.metric_name == "wam"
    assert result.value == 68
    assert result.classification == "Upper Second"


def test_oxford_class_first(catalog, engine):
    scheme = catalog.get("uk-oxford-ug-usm-honour-school")
    result = engine.calculate(
        scheme,
        [TranscriptCourse("P1", 1, percent=72), TranscriptCourse("P2", 1, percent=70)],
    )
    assert result.value == 71
    assert result.classification == "First Class"


def test_oxford_class_fail(catalog, engine):
    scheme = catalog.get("uk-oxford-ug-usm-honour-school")
    result = engine.calculate(
        scheme,
        [TranscriptCourse("P1", 1, percent=20), TranscriptCourse("P2", 1, percent=25)],
    )
    assert result.classification == "Fail"


def test_melbourne_subject_band_from_wam(catalog, engine):
    scheme = catalog.get("au-unimelb-ug-wam-current")
    result = engine.calculate(scheme, [TranscriptCourse("S1", 12.5, percent=82)])
    assert result.classification == "H1"


def test_mcgill_graduation_floor_band(catalog, engine):
    scheme = catalog.get("ca-mcgill-ug-current")
    result = engine.calculate(scheme, [TranscriptCourse("X", 3, grade="C")])
    assert result.value == 2.0
    assert result.classification == "Eligible for graduation (minimum CGPA)"


def test_toronto_percent_to_letter(catalog):
    scheme = catalog.get("ca-toronto-ug-refined-letter")
    assert scheme.grade_from_percent(92).symbol == "A+"
    assert scheme.grade_from_percent(87).symbol == "A"
    assert scheme.grade_from_percent(71).symbol == "B-"
    assert scheme.grade_from_percent(50).symbol == "D-"
    assert scheme.grade_from_percent(49).symbol == "F"


def test_mcgill_percent_to_letter(catalog):
    scheme = catalog.get("ca-mcgill-ug-current")
    assert scheme.grade_from_percent(90).symbol == "A"
    assert scheme.grade_from_percent(52).symbol == "D"
    assert scheme.grade_from_percent(40).symbol == "F"


def test_oxford_percent_to_class_symbol(catalog):
    scheme = catalog.get("uk-oxford-ug-usm-honour-school")
    assert scheme.grade_from_percent(75).symbol == "FIRST"
    assert scheme.grade_from_percent(65).symbol == "2.1"
    assert scheme.grade_from_percent(35).symbol == "PASS"


def test_engine_uses_percent_when_grade_missing(catalog, engine):
    scheme = catalog.get("ca-toronto-ug-refined-letter")
    result = engine.calculate(scheme, [TranscriptCourse("ENG", 1.0, percent=88)])
    assert result.courses[0].symbol == "A"
    assert result.value == 4.0


def test_mit_include_all_attempts(catalog, engine):
    scheme = catalog.get("us-mit-ug-5pt-current")
    assert scheme.repeat_course_rules.kind.value == "include_all_attempts"
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("8.01", 12, grade="C", attempt=1),
            TranscriptCourse("8.01", 12, grade="A", attempt=2),
            TranscriptCourse("8.02", 12, grade="B", attempt=1),
        ],
    )
    assert result.gpa_credits == 36
    assert result.value == 4.0


def test_delhi_last_attempt_only(catalog, engine):
    scheme = catalog.get("in-delhi-ugcf-2022")
    assert scheme.repeat_course_rules.kind.value == "last_attempt_only"
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("MATH", 4, grade="F", attempt=1),
            TranscriptCourse("MATH", 4, grade="A+", attempt=2),
            TranscriptCourse("ENG", 4, grade="B", attempt=1),
        ],
    )
    assert result.gpa_credits == 8
    expected = (9 * 4 + 6 * 4) / 8
    assert abs(result.value - expected) < 1e-9


def test_mcgill_replace_points_credit_once_uses_last(catalog, engine):
    scheme = catalog.get("ca-mcgill-ug-current")
    assert scheme.repeat_course_rules.kind.value == "replace_points_credit_once"
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("CHEM", 3, grade="D", attempt=1),
            TranscriptCourse("CHEM", 3, grade="B", attempt=2),
        ],
    )
    assert result.gpa_credits == 3
    assert result.value == 3.0


def test_berkeley_p_excluded_from_gpa(catalog, engine):
    scheme = catalog.get("us-berkeley-ug-letter-current")
    result = engine.calculate(scheme, [TranscriptCourse("PE", 2, grade="P")])
    assert result.gpa_credits == 0
    assert result.earned_credits == 2


def test_berkeley_np_no_gpa_no_credit(catalog, engine):
    scheme = catalog.get("us-berkeley-ug-letter-current")
    result = engine.calculate(scheme, [TranscriptCourse("X", 3, grade="NP")])
    assert result.gpa_credits == 0
    assert result.earned_credits == 0


def test_nus_s_u_excluded(catalog, engine):
    scheme = catalog.get("sg-nus-ug-gpa-2021-present")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("A", 4, grade="A"),
            TranscriptCourse("B", 4, grade="S"),
            TranscriptCourse("C", 4, grade="U"),
        ],
    )
    assert result.gpa_credits == 4
    assert result.value == 5.0


def test_unknown_grade_warns_and_skips(catalog, engine):
    scheme = catalog.get("us-berkeley-ug-letter-current")
    result = engine.calculate(
        scheme,
        [
            TranscriptCourse("OK", 4, grade="A"),
            TranscriptCourse("BAD", 4, grade="ZZZ"),
        ],
    )
    assert result.gpa_credits == 4
    assert result.value == 4.0
    assert any("ZZZ" in w or "BAD" in w or "unrecognized" in w.lower() for w in result.warnings)
    bad = next(c for c in result.courses if c.code == "BAD")
    assert bad.included_in_gpa is False


def test_empty_transcript_returns_none(catalog, engine):
    scheme = catalog.get("us-mit-ug-5pt-current")
    result = engine.calculate(scheme, [])
    assert result.value is None
    assert result.gpa_credits == 0


def test_grade_lookup_is_case_insensitive(catalog, engine):
    scheme = catalog.get("us-berkeley-ug-letter-current")
    result = engine.calculate(scheme, [TranscriptCourse("X", 4, grade=" a- ")])
    assert result.value == 3.7
