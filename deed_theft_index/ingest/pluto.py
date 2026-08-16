"""PLUTO / MapPLUTO ingestion — CLAUDE.md Section 4: baseline owner name,
building class, ownership type. One row per BBL, except condos (see Section 5
grain caveat: condos collapse to one row per complex, not per unit).

Filtered to the bounded neighborhood set (CLAUDE.md Section 3a) via PLUTO's `cd`
field, per Section 3a: "Filter via PLUTO community district, not fuzzy
neighborhood-name matching." This is the pipeline's actual scope boundary — since
join.py spines `properties` on PLUTO, filtering here bounds everything downstream.
Must run BEFORE ingest/acris.py — its (borocode, block) values are what bounds
the ACRIS pull to our neighborhoods instead of pulling citywide.
"""
import pandas as pd

from deed_theft_index.config import ALL_COMMUNITY_DISTRICTS, DATA_RAW_DIR, DATASETS
from deed_theft_index.ingest.socrata import fetch_all, save_parquet


def pull() -> pd.DataFrame:
    cd_list = ",".join(str(cd) for cd in ALL_COMMUNITY_DISTRICTS)
    df = fetch_all(DATASETS["pluto"], where=f"cd in ({cd_list})", progress_label="pluto")
    save_parquet(df, f"{DATA_RAW_DIR}/pluto.parquet")
    return df
