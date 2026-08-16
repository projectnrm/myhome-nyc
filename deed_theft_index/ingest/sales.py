"""Rolling/Annualized Calendar Sales ingestion — CLAUDE.md Section 4: neighborhood
price context (display-only, never a scored input, Section 7 Bias & Fairness
Review) and, as of Section 12, price-matching for History of My Home.

Bounded by neighborhood blocks (same pattern as ingest/acris.py's Legals pull) —
an unbounded pull hit a live 500 error, most likely the dataset's size/computed
columns at a 50K-row page against the full unfiltered citywide history. Small,
block-scoped requests work fine (verified live), so bound it the same way the
rest of the pipeline already does rather than debug the unbounded case further.
"""
import pandas as pd

from deed_theft_index.config import DATA_RAW_DIR, DATASETS
from deed_theft_index.ingest.socrata import fetch_all, save_parquet

BLOCK_BATCH_SIZE = 800


def _batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _pull_bounded(dataset_key: str, pluto_df: pd.DataFrame, out_name: str) -> None:
    blocks_by_borough = pluto_df.groupby("borocode")["block"].unique().apply(list).to_dict()
    frames = []
    for borocode, blocks in blocks_by_borough.items():
        for batch in _batched(blocks, BLOCK_BATCH_SIZE):
            block_list = ",".join(f"'{b}'" for b in batch)
            where = f"borough = '{borocode}' AND block in ({block_list})"
            frames.append(fetch_all(DATASETS[dataset_key], where=where, progress_label=out_name))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    save_parquet(df, f"{DATA_RAW_DIR}/{out_name}.parquet")


def pull_rolling(pluto_df: pd.DataFrame) -> None:
    _pull_bounded("rolling_calendar_sales", pluto_df, "rolling_calendar_sales")


def pull_annualized(pluto_df: pd.DataFrame) -> None:
    _pull_bounded("annualized_calendar_sales", pluto_df, "annualized_calendar_sales")
