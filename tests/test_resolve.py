"""Hierarchy resolution: university, country, faculty, degree, year."""

from gad.loader import Catalog


def test_resolve_by_university_slug():
    hits = Catalog.load().resolve(university="mit")
    assert len(hits) == 1
    assert hits[0].scheme_id == "us-mit-ug-5pt-current"


def test_resolve_by_country_iso():
    hits = Catalog.load().resolve(country="CA")
    ids = {s.scheme_id for s in hits}
    assert "ca-mcgill-ug-current" in ids
    assert "ca-toronto-ug-refined-letter" in ids
    assert all(s.country.iso2 == "CA" for s in hits)


def test_resolve_by_country_name():
    hits = Catalog.load().resolve(country="singapore")
    assert len(hits) == 1
    assert hits[0].university.slug == "nus"


def test_resolve_by_degree_level():
    hits = Catalog.load().resolve(degree_level="undergraduate")
    assert len(hits) >= 7
    assert all(s.degree_level.value == "undergraduate" for s in hits)


def test_resolve_by_year_open_ended():
    hits = Catalog.load().resolve(university="mit", year=2026)
    assert len(hits) == 1


def test_resolve_year_before_scheme_start_empty():
    hits = Catalog.load().resolve(university="mit", year=1960)
    assert hits == []


def test_resolve_oxford_year_window():
    hits = Catalog.load().resolve(university="oxford", year=2025)
    assert any(s.scheme_id == "uk-oxford-ug-usm-honour-school" for s in hits)


def test_resolve_faculty_filter():
    hits = Catalog.load().resolve(university="delhi", faculty="ugcf")
    assert len(hits) == 1
    assert hits[0].faculty_program.slug == "ugcf-2022"


def test_resolve_no_match():
    assert Catalog.load().resolve(university="nonexistent-uni-xyz") == []


def test_get_unknown_raises():
    import pytest

    with pytest.raises(KeyError):
        Catalog.load().get("does-not-exist")
