#!/usr/bin/env python
"""DEV-ONLY: populate data/processed/deed_theft_index.duckdb with synthetic
`properties` rows so the Streamlit app (deed_theft_index/app/) can be visually
verified while NYC Open Data is unreachable (e.g. scheduled maintenance).

Not part of the real pipeline (scripts/ingest.py + scripts/build.py) — every
owner name here is prefixed "DEMO:" so seeded rows are never mistaken for real
scored properties. Re-run scripts/build.py against real data to replace this.
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pandas as pd

from deed_theft_index.config import DUCKDB_PATH, NEIGHBORHOODS, SCORE_WEIGHTS, SCORED_FEATURES

random.seed(0)

BLDG_CLASSES = ["A1", "A2", "B1", "B2", "R4", "C0", "C1"]  # 1-3 family / condo / co-op mix

# 1 Centre Street, Manhattan resolves to this BBL via the live Geoclient v2 API
# (verified 2026-08-15) — seeded explicitly so self-lookup can be tested end-to-end
# with a real, resolvable address instead of only synthetic BBLs.
KNOWN_TEST_BBL = "1001210001"


def _random_extras() -> dict:
    """bldgclass/last_deed_date/has_sche/has_dhe — added for the SCHE/DHE Helper
    (Part A/B) and History of My Home (Part C); the original seed predates both.
    has_sche/has_dhe loosely track senior_disabled_exemption so seeded rows stay
    internally consistent rather than contradicting the main scorer's own flag.
    """
    years_owned = random.choice([0, 1, 3, 8, 15, 25])
    last_deed_date = date.today() - timedelta(days=365 * years_owned + random.randint(0, 300))
    return {
        "bldgclass": random.choice(BLDG_CLASSES),
        "last_deed_date": last_deed_date,
    }


def _random_row(bbl: str, cd: int) -> dict:
    features = {f: random.random() < 0.45 for f in SCORED_FEATURES}
    score = sum(SCORE_WEIGHTS[f] for f, v in features.items() if v)
    has_exemption = features["senior_disabled_exemption"]
    return {
        "bbl": bbl,
        "ownername": f"DEMO: OWNER {bbl}",
        "cd": cd,
        "risk_score": score,
        "has_sche": has_exemption and random.random() < 0.8,
        "has_dhe": has_exemption and random.random() >= 0.8,
        **_random_extras(),
        **features,
    }


def _high_risk_row(bbl: str, cd: int) -> dict:
    """All main-scorer factors present — deterministic (not random) so the known
    test BBL reliably demonstrates the full pill list and the High-tier guidance
    panel. has_sche/has_dhe both False (not enrolled) so the same real,
    Geoclient-resolvable address also exercises the SCHE Helper's screening flow,
    not just the already-enrolled state.
    """
    features = {f: True for f in SCORED_FEATURES}
    score = sum(SCORE_WEIGHTS[f] for f in SCORED_FEATURES)
    return {
        "bbl": bbl,
        "ownername": f"DEMO: OWNER {bbl}",
        "cd": cd,
        "risk_score": score,
        "bldgclass": "A1",
        "last_deed_date": date.today() - timedelta(days=365 * 15),
        "has_sche": False,
        "has_dhe": False,
        **features,
    }


def _seed_filings_joined() -> pd.DataFrame:
    """A realistic multi-document history for KNOWN_TEST_BBL, covering every UI
    case History of My Home (Part C) needs to demonstrate: an old deed (thin-
    history disclosure), a same-day deed+mortgage (bundling), a satisfaction, a
    recent Transfer on Death Deed (the heirs'-property narrative case, within the
    "recent" window so it's visible by default), an administrative-tier doc
    bundled near a deed (RPTT), and a standalone administrative doc (UCC1) —
    exercising both toggle-ladder steps ("show earlier history" / "show all
    recorded documents"), not just the default view.
    """
    rows = [
        {"document_id": "DEMO-1998-01", "doc_type": "DEED", "document_date": date(1998, 5, 1), "document_amt": 0,
         "party_names": ["ESTATE OF SMITH ROBERT", "SMITH JOHN"], "party_types": ["1", "2"]},
        {"document_id": "DEMO-2011-01", "doc_type": "DEED", "document_date": date(2011, 1, 15), "document_amt": 500000,
         "party_names": ["SMITH JOHN", "DOE JANE"], "party_types": ["1", "2"]},
        {"document_id": "DEMO-2011-02", "doc_type": "MTGE", "document_date": date(2011, 1, 15), "document_amt": 400000,
         "party_names": ["DOE JANE", "ABC BANK"], "party_types": ["1", "2"]},
        {"document_id": "DEMO-2011-03", "doc_type": "RPTT", "document_date": date(2011, 1, 20), "document_amt": 0,
         "party_names": ["SMITH JOHN", "DOE JANE"], "party_types": ["1", "2"]},
        {"document_id": "DEMO-2016-01", "doc_type": "SAT", "document_date": date(2016, 6, 1), "document_amt": 0,
         "party_names": ["DOE JANE", "ABC BANK"], "party_types": ["1", "2"]},
        {"document_id": "DEMO-2020-01", "doc_type": "UCC1", "document_date": date(2020, 2, 1), "document_amt": 0,
         "party_names": ["DOE JANE", "XYZ EQUIPMENT CO"], "party_types": ["1", "2"]},
        {"document_id": "DEMO-2023-01", "doc_type": "TODD", "document_date": date(2023, 9, 1), "document_amt": 0,
         "party_names": ["DOE JANE", "DOE MICHAEL"], "party_types": ["1", "2"]},
    ]
    for r in rows:
        r["bbl"] = KNOWN_TEST_BBL
        r["is_deed"] = r["doc_type"] in ("DEED", "DEEDO")
        r["is_mortgage"] = r["doc_type"] in ("MTGE", "AGMT")
        r["is_satisfaction"] = r["doc_type"] in ("SAT", "SATM")
    return pd.DataFrame(rows)


def _seed_sales_history() -> pd.DataFrame:
    """One confidently-matchable sale (same BBL/date as the 2011 deed above) so
    History of My Home's price-matching path is demonstrable — the ACRIS deed
    itself carries no reliable price, by design (CLAUDE.md Section 12). Table
    name/shape matches what join.py's build_sales_history() produces from real
    Rolling/Annualized Sales data, so history.py's query works against either.
    """
    return pd.DataFrame([
        {"bbl": KNOWN_TEST_BBL, "sale_price": 500000, "sale_date": date(2011, 1, 15)},
    ])


def main() -> None:
    rows = [_high_risk_row(KNOWN_TEST_BBL, 101)]
    bbl_counter = 1
    for name, cds in NEIGHBORHOODS.items():
        for _ in range(25):
            cd = random.choice(cds)
            bbl = f"{cd:03d}{bbl_counter:07d}"
            rows.append(_random_row(bbl, cd))
            bbl_counter += 1

    df = pd.DataFrame(rows)
    con = duckdb.connect(DUCKDB_PATH)
    con.execute("DROP TABLE IF EXISTS properties;")
    con.execute("CREATE TABLE properties AS SELECT * FROM df")

    filings_df = _seed_filings_joined()
    con.execute("DROP TABLE IF EXISTS filings_joined;")
    con.execute("CREATE TABLE filings_joined AS SELECT * FROM filings_df")

    sales_df = _seed_sales_history()
    con.execute("DROP TABLE IF EXISTS sales_history;")
    con.execute("CREATE TABLE sales_history AS SELECT * FROM sales_df")

    con.close()
    print(f"Seeded {len(df)} DEMO: properties, {len(filings_df)} filings_joined rows, "
          f"{len(sales_df)} sales_history row into {DUCKDB_PATH}")


if __name__ == "__main__":
    main()
