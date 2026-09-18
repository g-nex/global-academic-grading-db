-- Normalized Postgres target for thousands of schemes.
--
-- JSON under data/schemes/ remains the portable *document* source of truth.
-- This DDL is the relational *projection*: shared rule objects are first-class
-- so identical grade scales / formulas / policies are stored once and reused.
--
-- Logical spine:
--   Country → University → FacultyProgram → GradingScheme (version)
-- Scheme version points at reusable:
--   GradeScale, CalculationRule, RepeatPolicy, PassFailPolicy, ClassificationRule
-- Sources are independently stored and linked via scheme_sources.

CREATE TABLE countries (
    iso2          CHAR(2) PRIMARY KEY,
    name          TEXT NOT NULL
);

CREATE TABLE universities (
    slug          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    country_iso2  CHAR(2) NOT NULL REFERENCES countries (iso2),
    homepage      TEXT
);

CREATE TABLE faculty_programs (
    id              BIGSERIAL PRIMARY KEY,
    university_slug TEXT NOT NULL REFERENCES universities (slug),
    slug            TEXT NOT NULL,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL
                    CHECK (kind IN ('university_wide','faculty','school','program')),
    UNIQUE (university_slug, slug)
);

CREATE TABLE grade_scales (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE grade_scale_boundaries (
    id                    BIGSERIAL PRIMARY KEY,
    grade_scale_id        BIGINT NOT NULL REFERENCES grade_scales (id) ON DELETE CASCADE,
    symbol                TEXT NOT NULL,
    label                 TEXT,
    grade_points          DOUBLE PRECISION,
    min_percent           DOUBLE PRECISION,
    max_percent           DOUBLE PRECISION,
    passing               BOOLEAN NOT NULL DEFAULT TRUE,
    counts_toward_gpa     BOOLEAN NOT NULL DEFAULT TRUE,
    counts_toward_credits BOOLEAN NOT NULL DEFAULT TRUE,
    notes                 TEXT,
    verification_status   TEXT NOT NULL DEFAULT 'verified',
    UNIQUE (grade_scale_id, symbol)
);

CREATE TABLE calculation_rules (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL
                    CHECK (kind IN ('weighted_mean','wam_percent','unweighted_mean','custom')),
    scale_max       DOUBLE PRECISION NOT NULL,
    scale_min       DOUBLE PRECISION NOT NULL DEFAULT 0,
    rounding        TEXT NOT NULL,
    decimal_places  INTEGER NOT NULL DEFAULT 2,
    expression      TEXT NOT NULL,
    description     TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified',
    notes           TEXT
);

CREATE TABLE repeat_policies (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    kind            TEXT NOT NULL
                    CHECK (kind IN (
                        'include_all_attempts',
                        'last_attempt_only',
                        'best_attempt_only',
                        'replace_points_credit_once',
                        'unknown'
                    )),
    replace_with    TEXT NOT NULL DEFAULT 'last'
                    CHECK (replace_with IN ('last','best')),
    description     TEXT NOT NULL,
    max_attempts    INTEGER,
    content_hash    TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified',
    notes           TEXT
);

CREATE TABLE pass_fail_policies (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    treatment       TEXT NOT NULL
                    CHECK (treatment IN (
                        'exclude_from_gpa',
                        'include_fail_only',
                        'include_both',
                        'convert_to_letter'
                    )),
    pass_symbols    JSONB NOT NULL DEFAULT '[]'::jsonb,
    fail_symbols    JSONB NOT NULL DEFAULT '[]'::jsonb,
    description     TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified',
    notes           TEXT
);

CREATE TABLE classification_rules (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    applies         BOOLEAN NOT NULL,
    description     TEXT NOT NULL,
    extra_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_hash    TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified',
    notes           TEXT
);

CREATE TABLE classification_bands (
    id                      BIGSERIAL PRIMARY KEY,
    classification_rule_id  BIGINT NOT NULL REFERENCES classification_rules (id) ON DELETE CASCADE,
    name                    TEXT NOT NULL,
    min_value               DOUBLE PRECISION NOT NULL,
    max_value               DOUBLE PRECISION NOT NULL,
    metric                  TEXT NOT NULL,
    min_inclusive           BOOLEAN NOT NULL DEFAULT TRUE,
    max_inclusive           BOOLEAN NOT NULL DEFAULT TRUE,
    notes                   TEXT
);

CREATE TABLE sources (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    source_class    TEXT NOT NULL,
    content_hash    TEXT NOT NULL UNIQUE,
    notes           TEXT
);

CREATE TABLE grading_schemes (
    scheme_id               TEXT PRIMARY KEY,
    university_slug         TEXT NOT NULL REFERENCES universities (slug),
    country_iso2            CHAR(2) NOT NULL REFERENCES countries (iso2),
    faculty_program_id      BIGINT NOT NULL REFERENCES faculty_programs (id),
    degree_level            TEXT NOT NULL,
    year_start              INTEGER NOT NULL,
    year_end                INTEGER,
    year_label              TEXT NOT NULL,
    open_ended              BOOLEAN NOT NULL DEFAULT FALSE,
    name                    TEXT NOT NULL,

    grade_scale_id          BIGINT NOT NULL REFERENCES grade_scales (id),
    calculation_rule_id     BIGINT NOT NULL REFERENCES calculation_rules (id),
    repeat_policy_id        BIGINT NOT NULL REFERENCES repeat_policies (id),
    pass_fail_policy_id     BIGINT NOT NULL REFERENCES pass_fail_policies (id),
    classification_rule_id  BIGINT NOT NULL REFERENCES classification_rules (id),

    credit_unit             TEXT NOT NULL,
    typical_load            DOUBLE PRECISION,
    credit_notes            TEXT,

    verification_date       DATE NOT NULL,
    unverified_fields       JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes                   JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE scheme_sources (
    scheme_id       TEXT NOT NULL REFERENCES grading_schemes (scheme_id) ON DELETE CASCADE,
    source_id       BIGINT NOT NULL REFERENCES sources (id),
    retrieved       DATE NOT NULL,
    PRIMARY KEY (scheme_id, source_id)
);

CREATE INDEX idx_schemes_country ON grading_schemes (country_iso2);
CREATE INDEX idx_schemes_university ON grading_schemes (university_slug);
CREATE INDEX idx_schemes_level_year ON grading_schemes (degree_level, year_start);
CREATE INDEX idx_schemes_grade_scale ON grading_schemes (grade_scale_id);
CREATE INDEX idx_schemes_calc_rule ON grading_schemes (calculation_rule_id);
CREATE INDEX idx_grade_scale_hash ON grade_scales (content_hash);
CREATE INDEX idx_calc_rule_hash ON calculation_rules (content_hash);
CREATE INDEX idx_repeat_hash ON repeat_policies (content_hash);
