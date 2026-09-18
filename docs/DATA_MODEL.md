# Data model

## Hierarchy (required)

```
University → Country → Faculty/Program → Degree Level → Academic Year → Grading Scheme
```

In the **JSON document**, Country is nested for readability but is a first-class
entity (`iso2`). University holds `country_iso2`.

In **Postgres**, the same spine is normalized tables; the scheme row is a
*versioned binding* to reusable rule components (see `POSTGRES_MIGRATION.md`).

## GradingScheme aggregate (JSON)

Each seed file is one complete scheme so reviewers can verify it in isolation:

- Grade boundaries (scale)
- Credit system
- GPA / WAM formula
- Repeat-course rules
- Pass/fail treatment
- Degree classification bands
- Official sources + verification date
- `unverified_fields[]` for anything not backed by an official source

## Provenance

`VerificationStatus`: `verified` | `partial` | `unverified` | `not_applicable`

Blocks carry `FieldProvenance` (`status`, `note`, `source_url`). Absence of
evidence must not be stored as a positive claim.

## Multi-scheme institutions

Different faculty, program, degree level, or academic year ⇒ **separate**
`scheme_id`. Never overload one record with mutually exclusive rules.

## Engine view

`GPAEngine` always receives a fully resolved `GradingScheme` aggregate. Whether
that object was loaded from one JSON file or joined from normalized tables is
an implementation detail of `Catalog`.
