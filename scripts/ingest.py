#!/usr/bin/env python
"""Pull all raw datasets to data/raw/ as Parquet — CLAUDE.md Section 9.
Requires SOCRATA_APP_TOKEN in .env (see .env.example) or ingestion throttles hard.

Resumable: each step is skipped if its output Parquet already exists on disk,
so a rerun after an interruption (sleep, a killed process, a flaky connection)
only fetches what's actually missing rather than re-pulling everything from
scratch. Delete the relevant file(s) in data/raw/ to force a re-pull of that
step specifically.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from deed_theft_index.config import DATA_RAW_DIR
from deed_theft_index.ingest import acris, exemptions, pluto, sales, tax_liens


def _exists(name: str) -> bool:
    return (Path(DATA_RAW_DIR) / f"{name}.parquet").exists()


def main() -> None:
    # PLUTO must run first — ACRIS's Legals pull is bounded to PLUTO's already-filtered
    # (borocode, block) pairs, not citywide (see ingest/acris.py's module docstring for why).
    # pluto_df is needed in memory below even when the pull itself is skipped.
    if _exists("pluto"):
        print("PLUTO already pulled — reading from disk...")
        pluto_df = pd.read_parquet(f"{DATA_RAW_DIR}/pluto.parquet")
    else:
        print("Pulling PLUTO...")
        pluto_df = pluto.pull()

    print("Pulling ACRIS (legals bounded by neighborhood blocks, then master/parties/references)...")
    acris.pull_all(pluto_df)

    if _exists("property_exemption_detail"):
        print("Property Exemption Detail already pulled — skipping.")
    else:
        print("Pulling Property Exemption Detail...")
        exemptions.pull()

    if _exists("tax_lien_sale_lists"):
        print("Tax Lien Sale Lists already pulled — skipping.")
    else:
        print("Pulling Tax Lien Sale Lists...")
        tax_liens.pull()

    if _exists("rolling_calendar_sales") and _exists("annualized_calendar_sales"):
        print("Rolling/Annualized Calendar Sales already pulled — skipping.")
    else:
        print("Pulling Rolling/Annualized Calendar Sales (History of My Home price-matching, Section 12)...")
        sales.pull_rolling(pluto_df)
        sales.pull_annualized(pluto_df)

    print("Done. Raw Parquet files written to data/raw/.")


if __name__ == "__main__":
    main()
