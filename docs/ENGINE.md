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
| `best_attempt_only` | Keep the attempt with highest grade points, then percent, then later attempt. Side conditions (faculty approval, “best of first two”) are **not** automated — document them on the scheme. |
| `replace_points_credit_once` | **One** credit-bearing result is kept. `replace_with` is `last` (default) or `best`. Prior attempts are dropped from the sum (not averaged). This is the calculation view of “credits once; points come from the replacement attempt”. |
| `unknown` | All attempts included; warning emitted. |

`last_attempt_only` and `replace_points_credit_once` with `replace_with=last`
produce the same **numeric** selection. They remain distinct kinds because the
institutional *rationale* differs and some schools will later need
`replace_with=best` or richer rules without renaming history.

## Pass / fail

Controlled by `pass_fail.treatment` and per-boundary `counts_toward_gpa` /
`counts_toward_credits`. WAM schemes additionally require a numeric `percent`
and non–pass/fail courses for inclusion in the mark average.
