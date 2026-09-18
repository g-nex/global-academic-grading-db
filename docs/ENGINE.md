# Engine semantics

The calculator is driven only by fields on the matched `GradingScheme`. This
document records intentional behaviour for the edge cases that matter once
many institutions are in the catalog.

## Classification bands

Each band has `min_value`, `max_value`, `min_inclusive`, `max_inclusive`
(defaults: both inclusive).

Matching order: bands sorted by **`min_value` descending**. First match wins.

That means if two bands both contain the same boundary (bad seed data), the
**higher** class is returned. Prefer non-overlapping ranges in seeds, e.g.:

| Class | Range |
|---|---|
| First | 70–100 |
| Upper Second | 60–69 |
| Lower Second | 50–59 |

not 70–100 and 60–70. `gad validate` reports overlaps as errors.

## Repeat policies

| `kind` | Calculation behaviour |
|---|---|
| `include_all_attempts` | Every attempt enters the GPA/WAM sum. |
| `last_attempt_only` | Keep only the highest `attempt` number. |
| `best_attempt_only` | Keep the attempt with highest grade points, then percent, then later attempt. Side conditions are **not** automated. |
| `replace_points_credit_once` | **One** credit-bearing result is kept. `replace_with` is `last` (default) or `best`. Prior attempts are dropped (not averaged). |
| `unknown` | All attempts included; warning emitted. |

## Pass / fail

Controlled by `pass_fail.treatment` and per-boundary `counts_toward_gpa` /
`counts_toward_credits`. WAM schemes require a numeric `percent` and non–pass/fail
courses for inclusion in the mark average.

## Hardening behaviour

| Input | Default | `strict=True` |
|---|---|---|
| Empty course code | Warning, skip | `EngineError` |
| Negative credits | Warning, skip | `EngineError` |
| Zero credits | Warning, include (zero weight) | same |
| `attempt < 1` | Warning, coerce to 1 | `EngineError` |
| Percent outside 0–100 | Warning | `EngineError` |
| Unknown grade | Warning, exclude from GPA | same |

Additional guarantees:

- Quality points accumulated with `Decimal` (less float drift).
- Course codes normalized (case + whitespace) when grouping repeats.
- Dropped repeat attempts appear on `CalculationResult.courses` with
  `reason="dropped_by_repeat_policy"` and `selected=False`.
- `extras["raw_value"]` / `result.raw_value` holds the metric **before** rounding.
- Values outside `[scale_min, scale_max]` produce a warning.
- Unmatched classification bands and `extra_conditions` produce warnings
  (conditions are not auto-evaluated).
- `custom` formula kind falls back to weighted mean with a warning.
