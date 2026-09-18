"""GPA / WAM / classification engine driven entirely by stored scheme rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Any

from gad.models import (
    GPAFormulaKind,
    GradingScheme,
    PassFailTreatment,
    RepeatPolicyKind,
    RoundingMode,
)


@dataclass
class TranscriptCourse:
    code: str
    credits: float
    grade: str | None = None
    percent: float | None = None
    attempt: int = 1
    term: str | None = None
    pass_fail: bool = False


@dataclass
class CourseResult:
    code: str
    credits: float
    symbol: str | None
    grade_points: float | None
    included_in_gpa: bool
    included_in_credits: bool
    reason: str


@dataclass
class CalculationResult:
    scheme_id: str
    metric_name: str
    value: float | None
    scale_max: float
    scale_min: float
    quality_points: float
    gpa_credits: float
    earned_credits: float
    classification: str | None
    courses: list[CourseResult]
    warnings: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptInput:
    scheme_id: str
    courses: list[TranscriptCourse]


class GPAEngine:
    def calculate(self, scheme: GradingScheme, courses: list[TranscriptCourse]) -> CalculationResult:
        warnings: list[str] = []
        selected = self._apply_repeats(scheme, courses, warnings)
        resolved: list[CourseResult] = [self._resolve_course(scheme, c, warnings) for c in selected]

        quality = 0.0
        gpa_credits = 0.0
        earned = 0.0
        marks_num = 0.0
        marks_den = 0.0

        for course, result in zip(selected, resolved, strict=True):
            if result.included_in_credits:
                earned += result.credits
            if result.included_in_gpa and result.grade_points is not None:
                quality += result.grade_points * result.credits
                gpa_credits += result.credits
            if (
                scheme.gpa_formula.kind == GPAFormulaKind.WAM_PERCENT
                and result.included_in_gpa
                and course.percent is not None
            ):
                marks_num += course.percent * course.credits
                marks_den += course.credits

        formula = scheme.gpa_formula
        raw: float | None
        metric = "gpa"

        if formula.kind == GPAFormulaKind.WAM_PERCENT:
            metric = "wam"
            raw = (marks_num / marks_den) if marks_den else None
        elif formula.kind == GPAFormulaKind.UNWEIGHTED_MEAN:
            pts = [r.grade_points for r in resolved if r.included_in_gpa and r.grade_points is not None]
            raw = (sum(pts) / len(pts)) if pts else None
        else:
            raw = (quality / gpa_credits) if gpa_credits else None

        value = self._round(raw, formula.rounding, formula.decimal_places) if raw is not None else None
        classification = self._classify(scheme, value) if value is not None else None

        if scheme.repeat_course_rules.kind == RepeatPolicyKind.UNKNOWN:
            warnings.append("repeat_course_rules.kind is unknown; all attempts included")

        return CalculationResult(
            scheme_id=scheme.scheme_id,
            metric_name=metric,
            value=value,
            scale_max=formula.scale_max,
            scale_min=formula.scale_min,
            quality_points=quality,
            gpa_credits=gpa_credits,
            earned_credits=earned,
            classification=classification,
            courses=resolved,
            warnings=warnings,
        )

    def _apply_repeats(self, scheme: GradingScheme, courses: list[TranscriptCourse], warnings: list[str]) -> list[TranscriptCourse]:
        kind = scheme.repeat_course_rules.kind
        if kind in (RepeatPolicyKind.INCLUDE_ALL_ATTEMPTS, RepeatPolicyKind.UNKNOWN):
            return list(courses)
        by_code: dict[str, list[TranscriptCourse]] = {}
        for c in courses:
            by_code.setdefault(c.code, []).append(c)
        out: list[TranscriptCourse] = []
        for code, attempts in by_code.items():
            attempts_sorted = sorted(attempts, key=lambda x: x.attempt)
            if kind == RepeatPolicyKind.LAST_ATTEMPT_ONLY:
                out.append(attempts_sorted[-1])
            elif kind == RepeatPolicyKind.BEST_ATTEMPT_ONLY:
                def score(c: TranscriptCourse) -> float:
                    b = scheme.lookup_grade(c.grade or "")
                    if b and b.grade_points is not None:
                        return b.grade_points
                    return c.percent or -1.0
                out.append(max(attempts_sorted, key=score))
            elif kind == RepeatPolicyKind.REPLACE_POINTS_CREDIT_ONCE:
                out.append(attempts_sorted[-1])
            else:
                out.extend(attempts_sorted)
        return out

    def _resolve_course(self, scheme: GradingScheme, course: TranscriptCourse, warnings: list[str]) -> CourseResult:
        symbol = course.grade
        boundary = scheme.lookup_grade(symbol) if symbol else None
        if boundary is None and course.percent is not None:
            boundary = scheme.grade_from_percent(course.percent)
            if boundary:
                symbol = boundary.symbol
        if boundary is None:
            warnings.append(f"{course.code}: grade {course.grade!r} / percent {course.percent!r} not in scheme")
            return CourseResult(code=course.code, credits=course.credits, symbol=symbol, grade_points=None, included_in_gpa=False, included_in_credits=False, reason="unrecognized_grade")
        pf = course.pass_fail or (symbol or "").upper() in {s.upper() for s in scheme.pass_fail.pass_symbols + scheme.pass_fail.fail_symbols}
        included_gpa = boundary.counts_toward_gpa
        included_credits = boundary.counts_toward_credits
        if pf:
            treat = scheme.pass_fail.treatment
            if treat == PassFailTreatment.EXCLUDE_FROM_GPA:
                included_gpa = False
            elif treat == PassFailTreatment.INCLUDE_FAIL_ONLY:
                included_gpa = not boundary.passing
            elif treat == PassFailTreatment.INCLUDE_BOTH:
                included_gpa = True
        if scheme.gpa_formula.kind == GPAFormulaKind.WAM_PERCENT:
            included_gpa = course.percent is not None and not course.pass_fail
        return CourseResult(code=course.code, credits=course.credits, symbol=boundary.symbol, grade_points=boundary.grade_points, included_in_gpa=included_gpa, included_in_credits=included_credits and boundary.passing, reason="ok" if boundary.passing else "fail")

    def _round(self, value: float, mode: RoundingMode, places: int) -> float:
        q = Decimal("1").scaleb(-places)
        d = Decimal(str(value))
        if mode == RoundingMode.NONE:
            return float(d)
        if mode == RoundingMode.TRUNCATE:
            return float(d.quantize(q, rounding=ROUND_DOWN))
        if mode == RoundingMode.HALF_EVEN:
            return float(d.quantize(q, rounding=ROUND_HALF_EVEN))
        if mode in (RoundingMode.HALF_UP, RoundingMode.SYMMETRIC_NEAREST):
            return float(d.quantize(q, rounding=ROUND_HALF_UP))
        return float(d)

    def _classify(self, scheme: GradingScheme, value: float) -> str | None:
        rules = scheme.degree_classification
        if not rules.applies or not rules.bands:
            return None
        for band in rules.bands:
            if band.min_value <= value <= band.max_value:
                return band.name
        return None
