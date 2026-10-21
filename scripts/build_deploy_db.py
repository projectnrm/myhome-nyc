#!/usr/bin/env python
"""Build the committed demo database at data/deploy/deed_theft_index.duckdb.

Why this exists: the deployed app (e.g. Streamlit Community Cloud) needs a database
in the repo, but a property-level table of real NYC homes with senior-exemption,
free-and-clear, and risk-score flags is exactly the target list CLAUDE.md Section 8
says must never be public. So the committed file holds only:

  - properties, filings_joined, sales_history: SYNTHETIC rows from
    scripts/seed_demo_data.py (owner names prefixed "DEMO:", document IDs "DEMO-").
  - cd_risk_aggregate: REAL scores, aggregated to community district (cd,
    avg_risk_score, n_properties). No BBL, no address, no owner, no factor flags.

Usage:
    python scripts/build.py                 # real scored DB in data/processed/
    python scripts/build_deploy_db.py       # demo DB in data/deploy/
    python scripts/build_deploy_db.py --source path/to/scored.duckdb

The script refuses to write the file if any non-synthetic property-level row would
end up in it (see _check_demo_only), and tests/test_deploy_db.py re-checks the
committed file.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import duckdb
import pandas as pd

import seed_demo_data as seed
from deed_theft_index.config import NEIGHBORHOODS

DEFAULT_SOURCE = ROOT / "data" / "processed" / "deed_theft_index.duckdb"
DEPLOY_PATH = ROOT / "data" / "deploy" / "deed_theft_index.duckdb"

# Community districts with fewer scored properties than this are left out of the
# aggregate, so no published average describes a handful of identifiable homes.
MIN_PROPERTIES_PER_CD = 100


def _real_cd_aggregate(source: Path) -> pd.DataFrame:
    con = duckdb.connect(str(source), read_only=True)
    try:
        cols = {c for (c, *_) in con.execute("DESCRIBE properties").fetchall()}
        # Skip seeded rows if the source was ever seeded (trimmed DBs may lack ownername).
        where = "WHERE ownername IS NULL OR ownername NOT LIKE 'DEMO:%'" if "ownername" in cols else ""
        agg = con.execute(f"""
            SELECT cd, avg(risk_score) AS avg_risk_score, count(*) AS n_properties
            FROM properties
            {where}
            GROUP BY cd
            ORDER BY cd
        """).fetchdf()
    finally:
        con.close()
    return agg[agg["n_properties"] >= MIN_PROPERTIES_PER_CD].reset_index(drop=True)


def _synthetic_tables() -> dict:
    rows = [seed._high_risk_row(seed.KNOWN_TEST_BBL, 101)]
    bbl_counter = 1
    for cds in NEIGHBORHOODS.values():
        for _ in range(25):
            cd = seed.random.choice(cds)
            rows.append(seed._random_row(f"{cd:03d}{bbl_counter:07d}", cd))
            bbl_counter += 1
    return {
        "properties": pd.DataFrame(rows),
        "filings_joined": seed._seed_filings_joined(),
        "sales_history": seed._seed_sales_history(),
    }


def _check_demo_only(tables: dict) -> None:
    props = tables["properties"]
    bad = props[~props["ownername"].astype(str).str.startswith("DEMO:")]
    if not bad.empty:
        raise SystemExit(f"Refusing to build: {len(bad)} non-synthetic property rows.")
    filings = tables["filings_joined"]
    if not filings["document_id"].astype(str).str.startswith("DEMO-").all():
        raise SystemExit("Refusing to build: non-synthetic filings rows.")
    if set(tables["cd_risk_aggregate"].columns) != {"cd", "avg_risk_score", "n_properties"}:
        raise SystemExit("Refusing to build: aggregate table carries extra columns.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="Scored DuckDB to aggregate real cd-level scores from.")
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(f"No scored database at {args.source}; run scripts/build.py first.")

    tables = _synthetic_tables()
    tables["cd_risk_aggregate"] = _real_cd_aggregate(args.source)
    _check_demo_only(tables)

    DEPLOY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEPLOY_PATH.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    for name, df in tables.items():
        con.register("df_src", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df_src")
        con.unregister("df_src")
    con.close()
    tmp.replace(DEPLOY_PATH)

    agg = tables["cd_risk_aggregate"]
    print(f"Wrote {DEPLOY_PATH.relative_to(ROOT)}: {len(tables['properties'])} synthetic properties, "
          f"{len(agg)} community districts aggregated from {int(agg['n_properties'].sum()):,} real scores.")


if __name__ == "__main__":
    main()
