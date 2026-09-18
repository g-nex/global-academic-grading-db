# Relational model & migration

## Two representations, one contract

| Layer | Shape | Role |
|---|---|---|
| **JSON seeds** (`data/schemes/*.json`) | Large aggregate document | Portable source of truth, human-reviewed, git-diffable |
| **Postgres** (`schema/sql/postgres.sql`) | Normalized entities | Scale to thousands of schemes; share identical scales/rules |

The Python engine continues to consume the **aggregate** view (file-backed `Catalog` today; a DB-backed loader can reassemble the same `GradingScheme` object from joins).

## Why normalize?

At nine schemes, duplicating a 4.0 letter scale inside every US record is fine. At thousands, you want:

- one row for “US standard refined letter scale”
- many schemes pointing at it
- a single edit when a shared policy is corrected (with versioning discipline)

## Target entity graph

```
Country
  └── University
        └── FacultyProgram
              └── GradingScheme          ← versioned binding
                    ├── GradeScale
                    │     └── GradeScaleBoundary[]
                    ├── CalculationRule
                    ├── RepeatPolicy
                    ├── PassFailPolicy
                    ├── ClassificationRule
                    │     └── ClassificationBand[]
                    └── Source[] (via scheme_sources)
```

### Reusable components

| Table | Shared when… | Do **not** share when… |
|---|---|---|
| `grade_scales` | Identical symbol → points/percent map | One letter differs (e.g. A+ = 4.0 vs 4.3) |
| `calculation_rules` | Same kind, scale, rounding, expression | Rounding or scale_max differs |
| `repeat_policies` | Same kind + replace_with + description | Institution-specific side conditions |
| `pass_fail_policies` | Same treatment + symbol lists | Symbol sets differ |
| `classification_rules` | Same band set + metric | Different cut-offs or inclusivity |
| `sources` | Same URL + title | — (always dedupe by URL hash) |

Dedup key: stable `content_hash` over the canonical JSON of the component (excluding scheme-local notes).

### Scheme stays the public key

`grading_schemes.scheme_id` remains the external identifier the engine and API use. Changing a shared `grade_scale` affects every scheme that references it — prefer **new scale + new scheme version** over silent in-place mutation of historical records.

## ETL sketch

1. Load each JSON scheme document.
2. Upsert spine: country → university → faculty_program.
3. For each component block, compute `content_hash`; insert if missing, else reuse `id`.
4. Insert `grading_schemes` row with FKs to those components.
5. Upsert `sources` and link via `scheme_sources` with `retrieved` date.
6. Copy `unverified_fields` / `notes` onto the scheme row as JSONB.

No cloud credentials belong in this repository.

## JSON → relational mapping

| JSON path | Relational target |
|---|---|
| `university`, `country` | `universities`, `countries` |
| `faculty_program` | `faculty_programs` |
| `grade_boundaries[]` | `grade_scales` + `grade_scale_boundaries` |
| `gpa_formula` | `calculation_rules` |
| `repeat_course_rules` | `repeat_policies` |
| `pass_fail` | `pass_fail_policies` |
| `degree_classification` | `classification_rules` + `classification_bands` |
| `official_sources[]` | `sources` + `scheme_sources` |
| `scheme_id`, year, degree, credit, provenance | `grading_schemes` columns |

## Migration steps (when a provider is chosen)

1. Apply `schema/sql/postgres.sql`.
2. Run ETL (to be implemented as `gad migrate` once a DSN is provided).
3. Point a DB-backed `Catalog` at the same `scheme_id`s — engine code unchanged.
4. Keep JSON seeds as the reviewable audit trail until the org decides otherwise.
