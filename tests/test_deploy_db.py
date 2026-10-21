"""Guards the committed demo database (data/deploy/deed_theft_index.duckdb).

CLAUDE.md Section 8: individual risk factors for real properties must never be
public. These checks fail if anything other than synthetic property-level rows and
the community-district aggregate ever lands in the committed file.
Run with: python -m pytest tests/
"""
from pathlib import Path

import duckdb
import pytest

DEPLOY_DB = Path(__file__).resolve().parent.parent / "data" / "deploy" / "deed_theft_index.duckdb"
ALLOWED_TABLES = {"properties", "filings_joined", "sales_history", "cd_risk_aggregate"}


@pytest.fixture(scope="module")
def con():
    if not DEPLOY_DB.exists():
        pytest.skip("No committed deploy DB.")
    c = duckdb.connect(str(DEPLOY_DB), read_only=True)
    yield c
    c.close()


def test_only_expected_tables(con):
    tables = {t for (t,) in con.execute("SHOW TABLES").fetchall()}
    assert tables <= ALLOWED_TABLES, f"Unexpected tables: {tables - ALLOWED_TABLES}"


def test_properties_are_synthetic(con):
    real = con.execute(
        "SELECT count(*) FROM properties WHERE ownername IS NULL OR ownername NOT LIKE 'DEMO:%'"
    ).fetchone()[0]
    assert real == 0


def test_filings_are_synthetic(con):
    real = con.execute(
        "SELECT count(*) FROM filings_joined WHERE document_id NOT LIKE 'DEMO-%'"
    ).fetchone()[0]
    assert real == 0


def test_aggregate_has_no_property_level_columns(con):
    cols = {c for (c, *_) in con.execute("DESCRIBE cd_risk_aggregate").fetchall()}
    assert cols == {"cd", "avg_risk_score", "n_properties"}


def test_aggregate_cells_are_not_small(con):
    smallest = con.execute("SELECT min(n_properties) FROM cd_risk_aggregate").fetchone()[0]
    assert smallest >= 100
