"""GPA / WAM / classification engine driven entirely by stored scheme rules.

Hardening goals
---------------
- Validate inputs early; never silent-corrupt a transcript.
- Accumulate quality points with Decimal to reduce float drift.
- Normalize course codes when grouping repeats (case / whitespace).
- Surface institutional gaps as warnings, not invented policy.
- Keep raw (pre-round) and rounded values available on the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from gad.models import (
    GPAFormulaKind,
    GradingScheme,
    PassFailTreatment,
    RepeatPolicyKind,
    RoundingMode,
)


class EngineError(ValueError):
    """Raised for inputs the engine refuses to calculate."""


@dataclass
class TranscriptCourse:
    code: str
    credits: float
    grade: str | None = None
    percent: float | None = None
    attempt: int = 1
    term: str | None = None
    pass_fail: bool = False

    def normalized_code(self) -> str:
        return " ".join(self.code.split()).casefold()


@dataclass
class CourseResult:
    code: str
    credits: float
    symbol: str | None
    grade_points: float | None
    included_in_gpa: bool
    included_in_credits: bool
    reason: str
    attempt: int = 1
    percent: float | None = None
    selected: bool = True


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

    @property
    def raw_value(self) -> float | None:
        v = self.extras.get("raw_value")
        return float(v) if v is not None else None


@dataclass
class TranscriptInput:
    scheme_id: str
    courses: list[TranscriptCourse]


class GPAEngine:
    """Rules-driven calculator. Stateless — safe to reuse across calls."""

    def calculate(
        self,
        scheme: GradingScheme,
        courses: list[TranscriptCourse],
        *,
        strict: bool = False,
    ) -> CalculationResult:
        warnings: list[str] = []
        validated = self._validate_courses(courses, warnings, strict=strict)
        selected, dropped = self._apply_repeats(scheme, validated, warnings)
        resolved: list[CourseResult] = [
            self._resolve_course(scheme, c, warnings) for c in selected
        ]
        for d in dropped:
            resolved.append(
                CourseResult(
                    code=d.code,
                    credits=d.credits,
                    symbol=d.grade,
                    grade_points=None,
                    included_in_gpa=False,
                    included_in_credits=False,
                    reason="dropped_by_repeat_policy",
                    attempt=d.attempt,
                    percent=d.percent,
                    selected=False,
                )
            )

        quality = Decimal("0")
        gpa_credits = Decimal("0")
        earned = Decimal("0")
        marks_num = Decimal("0")
        marks_den = Decimal("0")

        for course, result in zip(selected, resolved[: len(selected)], strict=True):
            if result.included_in_credits:
                earned += Decimal(str(result.credits))
            if result.included_in_gpa and result.grade_points is not None:
                quality += Decimal(str(result.grade_points)) * Decimal(str(result.credits))
                gpa_credits += Decimal(str(result.credits))
            if (
                scheme.gpa_formula.kind == GPAFormulaKind.WAM_PERCENT
                and result.included_in_gpa
                and course.percent is not None
            ):
                marks_num += Decimal(str(course.percent)) * Decimal(str(course.credits))
                marks_den += Decimal(str(course.credits))

        formula = scheme.gpa_formula
        raw: float | None
        metric = "gpa"

        if formula.kind == GPAFormulaKind.WAM_PERCENT:
            metric = "wam"
            raw = float(marks_num / marks_den) if marks_den else None
        elif formula.kind == GPAFormulaKind.UNWEIGHTED_MEAN:
            pts = [
                Decimal(str(r.grade_points))
                for r in resolved
                if r.selected and r.included_in_gpa and r.grade_points is not None
            ]
            raw = float(sum(pts) / len(pts)) if pts else None
        elif formula.kind == GPAFormulaKind.CUSTOM:
            warnings.append(
                f"gpa_formula.kind is custom ({formula.expression!r}); "
                "engine falls back to weighted mean"
            )
            raw = float(quality / gpa_credits) if gpa_credits else None
        else:
            raw = float(quality / gpa_credits) if gpa_credits else None

        value = (
            self._round(raw, formula.rounding, formula.decimal_places)
            if raw is not None
            else None
        )

        if value is not None:
            if value > formula.scale_max + 1e-9 or value < formula.scale_min - 1e-9:
                warnings.append(
                    f"computed {metric}={value} outside scheme scale "
                    f"[{formula.scale_min}, {formula.scale_max}]"
                )

        classification = self._classify(scheme, value, warnings) if value is not None else None

        if scheme.repeat_course_rules.kind == RepeatPolicyKind.UNKNOWN:
            warnings.append("repeat_course_rules.kind is unknown; all attempts included")

        if scheme.degree_classification.extra_conditions:
            warnings.append(
                "degree_classification.extra_conditions are not evaluated by the engine: "
                + "; ".join(scheme.degree_classification.extra_conditions)
            )

        return CalculationResult(
            scheme_id=scheme.scheme_id,
            metric_name=metric,
            value=value,
            scale_max=formula.scale_max,
            scale_min=formula.scale_min,
            quality_points=float(quality),
            gpa_credits=float(gpa_credits),
            earned_credits=float(earned),
            classification=classification,
            courses=resolved,
            warnings=warnings,
            extras={
                "raw_value": raw,
                "rounding": formula.rounding.value,
                "decimal_places": formula.decimal_places,
                "repeat_kind": scheme.repeat_course_rules.kind.value,
                "courses_input": len(courses),
                "courses_selected": len(selected),
                "courses_dropped": len(dropped),
            },
        )

    def _validate_courses(
        self,
        courses: list[TranscriptCourse],
        warnings: list[str],
        *,
        strict: bool,
    ) -> list[TranscriptCourse]:
        out: list[TranscriptCourse] = []
        for i, c in enumerate(courses):
            label = c.code or f"index={i}"
            if not c.code or not str(c.code).strip():
                msg = f"course {label}: empty course code"
                if strict:
                    raise EngineError(msg)
                warnings.append(msg)
                continue
            if c.credits < 0:
                msg = f"{c.code}: negative credits {c.credits}"
                if strict:
                    raise EngineError(msg)
                warnings.append(msg + "; excluded")
                continue
            if c.credits == 0:
                warnings.append(f"{c.code}: zero credits; included with no weight")
            if c.attempt < 1:
                msg = f"{c.code}: attempt must be >= 1 (got {c.attempt})"
                if strict:
                    raise EngineError(msg)
                warnings.append(msg + "; treating as attempt 1")
                c = TranscriptCourse(
                    code=c.code,
                    credits=c.credits,
                    grade=c.grade,
                    percent=c.percent,
                    attempt=1,
                    term=c.term,
                    pass_fail=c.pass_fail,
                )
            if c.percent is not None and not (0.0 <= c.percent <= 100.0):
                msg = f"{c.code}: percent {c.percent} outside 0–100"
                if strict:
                    raise EngineError(msg)
                warnings.append(msg)
            if c.grade is None and c.percent is None:
                warnings.append(f"{c.code}: no grade and no percent supplied")
            out.append(c)
        return out

    def _attempt_score(
        self, scheme: GradingScheme, course: TranscriptCourse
    ) -> tuple[float, float, int]:
        boundary = scheme.lookup_grade(course.grade or "") if course.grade else None
        if boundary is None and course.percent is not None:
            boundary = scheme.grade_from_percent(course.percent)
        gp = (
            boundary.grade_points
            if boundary and boundary.grade_points is not None
            else float("-inf")
        )
        pct = course.percent if course.percent is not None else float("-inf")
        return (gp, pct, course.attempt)

    def _apply_repeats(
        self,
        scheme: GradingScheme,
        courses: list[TranscriptCourse],
        warnings: list[str],
    ) -> tuple[list[TranscriptCourse], list[TranscriptCourse]]:
        kind = scheme.repeat_course_rules.kind
        if kind in (RepeatPolicyKind.INCLUDE_ALL_ATTEMPTS, RepeatPolicyKind.UNKNOWN):
            return list(courses), []

        by_code: dict[str, list[TranscriptCourse]] = {}
        for c in courses:
            by_code.setdefault(c.normalized_code(), []).append(c)

        max_attempts = scheme.repeat_course_rules.max_attempts
        selected: list[TranscriptCourse] = []
        dropped: list[TranscriptCourse] = []

        for _code_key, attempts in by_code.items():
            attempts_sorted = sorted(attempts, key=lambda x: x.attempt)

            if max_attempts is not None:
                for a in attempts_sorted:
                    if a.attempt > max_attempts:
                        warnings.append(
                            f"{a.code}: attempt {a.attempt} exceeds scheme max_attempts={max_attempts}"
                        )

            if kind == RepeatPolicyKind.LAST_ATTEMPT_ONLY:
                keep = attempts_sorted[-1]
            elif kind == RepeatPolicyKind.BEST_ATTEMPT_ONLY:
                keep = max(attempts_sorted, key=lambda c: self._attempt_score(scheme, c))
            elif kind == RepeatPolicyKind.REPLACE_POINTS_CREDIT_ONCE:
                strategy = scheme.repeat_course_rules.replace_with
                if strategy == "best":
                    keep = max(attempts_sorted, key=lambda c: self._attempt_score(scheme, c))
                else:
                    keep = attempts_sorted[-1]
            else:
                selected.extend(attempts_sorted)
                continue

            selected.append(keep)
            for a in attempts_sorted:
                if a is not keep:
                    dropped.append(a)

        return selected, dropped

    def _resolve_course(
        self,
        scheme: GradingScheme,
        course: TranscriptCourse,
        warnings: list[str],
    ) -> CourseResult:
        symbol = course.grade.strip() if course.grade else None
        boundary = scheme.lookup_grade(symbol) if symbol else None
        if boundary is None and course.percent is not None:
            boundary = scheme.grade_from_percent(course.percent)
            if boundary:
                symbol = boundary.symbol

        if boundary is None:
            warnings.append(
                f"{course.code}: grade {course.grade!r} / percent {course.percent!r} not in scheme"
            )
            return CourseResult(
                code=course.code,
                credits=course.credits,
                symbol=symbol,
                grade_points=None,
                included_in_gpa=False,
                included_in_credits=False,
                reason="unrecognized_grade",
                attempt=course.attempt,
                percent=course.percent,
            )

        pf_symbols = {
            s.upper()
            for s in scheme.pass_fail.pass_symbols + scheme.pass_fail.fail_symbols
        }
        pf = course.pass_fail or (symbol is not None and symbol.upper() in pf_symbols)
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
            if course.percent is None:
                warnings.append(
                    f"{course.code}: WAM scheme requires percent; course excluded from average"
                )
                included_gpa = False
            elif course.pass_fail or pf:
                included_gpa = False
            else:
                included_gpa = True

        reason = "ok"
        if not boundary.passing:
            reason = "fail"
        if pf:
            reason = "pass_fail"
        if not included_gpa and reason == "ok":
            reason = "excluded_from_gpa"

        return CourseResult(
            code=course.code,
            credits=course.credits,
            symbol=boundary.symbol,
            grade_points=boundary.grade_points,
            included_in_gpa=included_gpa,
            included_in_credits=included_credits and boundary.passing,
            reason=reason,
            attempt=course.attempt,
            percent=course.percent,
        )

    def _round(self, value: float, mode: RoundingMode, places: int) -> float:
        if places < 0:
            places = 0
        try:
            q = Decimal("1").scaleb(-places)
            d = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
        if mode == RoundingMode.NONE:
            return float(d)
        if mode == RoundingMode.TRUNCATE:
            if d >= 0:
                return float(d.quantize(q, rounding=ROUND_DOWN))
            return float(-(-d).quantize(q, rounding=ROUND_DOWN))
        if mode == RoundingMode.HALF_EVEN:
            return float(d.quantize(q, rounding=ROUND_HALF_EVEN))
        if mode in (RoundingMode.HALF_UP, RoundingMode.SYMMETRIC_NEAREST):
            return float(d.quantize(q, rounding=ROUND_HALF_UP))
        return float(d)

    def _classify(
        self,
        scheme: GradingScheme,
        value: float,
        warnings: list[str],
    ) -> str | None:
        rules = scheme.degree_classification
        if not rules.applies or not rules.bands:
            return None
        ordered = sorted(rules.bands, key=lambda b: b.min_value, reverse=True)
        for band in ordered:
            if band.contains(value):
                return band.name
        warnings.append(
            f"value {value} matched no classification band "
            f"(scheme has {len(rules.bands)} band(s))"
        )
        return None
