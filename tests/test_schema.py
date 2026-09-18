from gad.loader import Catalog
from gad.validate import validate_catalog

def test_seed_loads_and_validates():
    catalog = Catalog.load()
    assert len(catalog.schemes) >= 1
    assert validate_catalog(catalog) == []
