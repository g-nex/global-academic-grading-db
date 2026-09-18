-- SQLite production target (local / single-node).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS countries (
    iso2 TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS universities (
    slug TEXT PRIMARY KEY, name TEXT NOT NULL,
    country_iso2 TEXT NOT NULL REFERENCES countries (iso2), homepage TEXT
);
CREATE TABLE IF NOT EXISTS faculty_programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_slug TEXT NOT NULL REFERENCES universities (slug),
    slug TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
    UNIQUE (university_slug, slug)
);
CREATE TABLE IF NOT EXISTS grade_scales (
    id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL, content_hash TEXT NOT NULL, notes TEXT
);
CREATE TABLE IF NOT EXISTS grade_scale_boundaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_scale_id INTEGER NOT NULL REFERENCES grade_scales (id) ON DELETE CASCADE,
    symbol TEXT NOT NULL, label TEXT, grade_points REAL,
    min_percent REAL, max_percent REAL,
    passing INTEGER NOT NULL DEFAULT 1,
    counts_toward_gpa INTEGER NOT NULL DEFAULT 1,
    counts_toward_credits INTEGER NOT NULL DEFAULT 1,
    notes TEXT, verification_status TEXT NOT NULL DEFAULT 'verified',
    UNIQUE (grade_scale_id, symbol)
);
CREATE TABLE IF NOT EXISTS calculation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    kind TEXT NOT NULL, scale_max REAL NOT NULL, scale_min REAL NOT NULL DEFAULT 0,
    rounding TEXT NOT NULL, decimal_places INTEGER NOT NULL DEFAULT 2,
    expression TEXT NOT NULL, description TEXT NOT NULL, content_hash TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified', notes TEXT
);
CREATE TABLE IF NOT EXISTS repeat_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
    replace_with TEXT NOT NULL DEFAULT 'last', description TEXT NOT NULL,
    max_attempts INTEGER, content_hash TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified', notes TEXT
);
CREATE TABLE IF NOT EXISTS pass_fail_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE, treatment TEXT NOT NULL,
    pass_symbols TEXT NOT NULL DEFAULT '[]', fail_symbols TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL, content_hash TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified', notes TEXT
);
CREATE TABLE IF NOT EXISTS classification_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    applies INTEGER NOT NULL, description TEXT NOT NULL,
    extra_conditions TEXT NOT NULL DEFAULT '[]', content_hash TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'verified', notes TEXT
);
CREATE TABLE IF NOT EXISTS classification_bands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classification_rule_id INTEGER NOT NULL REFERENCES classification_rules (id) ON DELETE CASCADE,
    name TEXT NOT NULL, min_value REAL NOT NULL, max_value REAL NOT NULL, metric TEXT NOT NULL,
    min_inclusive INTEGER NOT NULL DEFAULT 1, max_inclusive INTEGER NOT NULL DEFAULT 1, notes TEXT
);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL,
    source_class TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE, notes TEXT
);
CREATE TABLE IF NOT EXISTS grading_schemes (
    scheme_id TEXT PRIMARY KEY,
    university_slug TEXT NOT NULL REFERENCES universities (slug),
    country_iso2 TEXT NOT NULL REFERENCES countries (iso2),
    faculty_program_id INTEGER NOT NULL REFERENCES faculty_programs (id),
    degree_level TEXT NOT NULL, year_start INTEGER NOT NULL, year_end INTEGER,
    year_label TEXT NOT NULL, open_ended INTEGER NOT NULL DEFAULT 0, name TEXT NOT NULL,
    grade_scale_id INTEGER NOT NULL REFERENCES grade_scales (id),
    calculation_rule_id INTEGER NOT NULL REFERENCES calculation_rules (id),
    repeat_policy_id INTEGER NOT NULL REFERENCES repeat_policies (id),
    pass_fail_policy_id INTEGER NOT NULL REFERENCES pass_fail_policies (id),
    classification_rule_id INTEGER NOT NULL REFERENCES classification_rules (id),
    credit_unit TEXT NOT NULL, typical_load REAL, credit_notes TEXT,
    verification_date TEXT NOT NULL,
    unverified_fields TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '[]',
    document_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scheme_sources (
    scheme_id TEXT NOT NULL REFERENCES grading_schemes (scheme_id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources (id),
    retrieved TEXT NOT NULL,
    PRIMARY KEY (scheme_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_schemes_country ON grading_schemes (country_iso2);
CREATE INDEX IF NOT EXISTS idx_schemes_university ON grading_schemes (university_slug);
