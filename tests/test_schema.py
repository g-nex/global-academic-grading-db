"""Seed integrity: load, required fields, sources, hierarchy consistency."""

from gad.loader import Catalog
from gad.validate import validate_catalog


EXPECTED_SCHEME_IDS = {
    "us-berkeley-ug-letter-current",
    "us-mit-ug-5pt-current",
    "us-unc-chapel-hill-ug",
    "ca-mcgill-ug-current",
    "ca-toronto-ug-refined-letter",
    "uk-oxford-ug-usm-honour-school",
    "sg-nus-ug-gpa-2021-present",
    "au-unimelb-ug-wam-current",
    "in-delhi-ugcf-2022",
}


def test_seed_loads_all_nine_schemes():
    catalog = Catalog.load()
    assert set(catalog.schemes.keys()) == EXPECTED_SCHEME_IDS


def test_validate_catalog_clean():
    assert validate_catalog(Catalog.load()) == []


def test_required_scheme_fields_present():
    for s in Catalog.load().list():
        assert s.official_sources, s.scheme_id
        assert s.verification_date, s.scheme_id
        assert s.grade_boundaries, s.scheme_id
        assert s.gpa_formula.expression, s.scheme_id
        assert s.gpa_formula.description, s.scheme_id
        assert s.credit_system.unit, s.scheme_id
        assert s.repeat_course_rules.kind, s.scheme_id
        assert s.pass_fail.treatment, s.scheme_id
        assert s.country.iso2 == s.university.country_iso2, s.scheme_id


def test_every_scheme_has_official_url_and_verification_date():
    for s in Catalog.load().list():
        assert s.verification_date == "2026-09-18" or s.verification_date
        for src in s.official_sources:
            assert str(src.url).startswith("http")
            assert src.retrieved
            assert src.source_class


def test_unverified_fields_listed_when_repeat_unknown():
    for s in Catalog.load().list():
        if s.repeat_course_rules.kind.value == "unknown":
            assert any("repeat" in f for f in s.unverified_fields), s.scheme_id
