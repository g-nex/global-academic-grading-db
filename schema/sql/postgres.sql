-- Postgres target schema. Seed JSON is the source of truth until a provider
-- is chosen; this file is the intended migration shape.

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
    id            BIGSERIAL PRIMARY KEY,
    university_slug TEXT NOT NULL REFERENCES universities (slug),
    slug          TEXT NOT NULL,
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('university_wide','faculty','school','program')),
    UNIQUE (university_slug, slug)
);

CREATE TABLE grading_schemes (
    scheme_id     TEXT PRIMARY KEY,
    university_slug TEXT NOT NULL REFERENCES universities (slug),
    country_iso2  CHAR(2) NOT NULL REFERENCES countries (iso2),
    faculty_program_id BIGINT NOT NULL REFERENCES faculty_programs (id),
    degree_level  TEXT NOT NULL,
    year_start    INTEGER NOT NULL,
    year_end      INTEGER,
    year_label    TEXT NOT NULL,
    open_ended    BOOLEAN NOT NULL DEFAULT FALSE,
    name          TEXT NOT NULL,
    credit_unit   TEXT NOT NULL,
    typical_load  DOUBLE PRECISION,
    gpa_kind      TEXT NOT NULL,
    scale_max     DOUBLE PRECISION NOT NULL,
    scale_min     DOUBLE PRECISION NOT NULL DEFAULT 0,
    rounding      TEXT NOT NULL,
    decimal_places INTEGER NOT NULL DEFAULT 2,
    gpa_expression TEXT NOT NULL,
    gpa_description TEXT NOT NULL,
    repeat_kind   TEXT NOT NULL,
    repeat_description TEXT NOT NULL,
    pass_fail_treatment TEXT NOT NULL,
    classification_applies BOOLEAN NOT NULL,
    classification_description TEXT NOT NULL,
    verification_date DATE NOT NULL,
    unverified_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes         JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE grade_boundaries (
    id            BIGSERIAL PRIMARY KEY,
    scheme_id     TEXT NOT NULL REFERENCES grading_schemes (scheme_id) ON DELETE CASCADE,
    symbol        TEXT NOT NULL,
    label         TEXT,
    grade_points  DOUBLE PRECISION,
    min_percent   DOUBLE PRECISION,
    max_percent   DOUBLE PRECISION,
    passing       BOOLEAN NOT NULL,
    counts_toward_gpa BOOLEAN NOT NULL,
    counts_toward_credits BOOLEAN NOT NULL,
    notes         TEXT,
    verification_status TEXT NOT NULL DEFAULT 'verified',
    UNIQUE (scheme_id, symbol)
);

CREATE TABLE classification_bands (
    id            BIGSERIAL PRIMARY KEY,
    scheme_id     TEXT NOT NULL REFERENCES grading_schemes (scheme_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    min_value     DOUBLE PRECISION NOT NULL,
    max_value     DOUBLE PRECISION NOT NULL,
    metric        TEXT NOT NULL,
    notes         TEXT
);

CREATE TABLE official_sources (
    id            BIGSERIAL PRIMARY KEY,
    scheme_id     TEXT NOT NULL REFERENCES grading_schemes (scheme_id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    source_class  TEXT NOT NULL,
    retrieved     DATE NOT NULL,
    notes         TEXT
);

CREATE INDEX idx_schemes_country ON grading_schemes (country_iso2);
CREATE INDEX idx_schemes_university ON grading_schemes (university_slug);
CREATE INDEX idx_schemes_level_year ON grading_schemes (degree_level, year_start);
