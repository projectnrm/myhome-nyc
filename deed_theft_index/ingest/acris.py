"""ACRIS ingestion — CLAUDE.md Section 4/5: Master, Legals, Parties, References.

Legals is the required bridge from Document ID to BBL (Master alone has no BBL).

Bounded by BOTH neighborhood geography AND recency — a live run proved either
bound alone is too much data:
  - Date-only (citywide, last 15 years): 5.1M Master rows. Fine to page through
    (single dataset, no batching), but its document_id set is too large to
    batch-filter Legals/Parties/References against (would mean ~10,000+ batched
    requests) — the original design's mistake.
  - Geography-only (our ~8,563 blocks, full history): Legals has NO date field,
    so this pulls *all* history since ACRIS began — Manhattan's 731 blocks alone
    hit 1.79M+ rows and was still climbing when a network timeout killed the run.
    Worse than the date-only citywide pull, not better.

The fix: pull each bound as its own independent, single-dataset paginated call
(no batching, no combinatorial explosion — Socrata handles both of these fine,
they just take real wall-clock time), then INTERSECT the two document_id sets
locally in DuckDB, which is free. Only the resulting (small) intersected ID set
gets used for the batched Parties/References pulls — Master data for those IDs
is already in hand from the date-bounded pull, so it's never re-fetched by ID.

Two more things a real end-to-end run surfaced, both fixed here:

1. **Block-level over-selection.** Legals is bounded by (borough, block), not
   exact BBL — a block can carry many lots, so this pulls every document for
   every lot on a matching block, not just our 233K PLUTO-filtered target
   properties. A live run: Master (date-bounded) came back at 5.1M rows, Legals
   (block-bounded) at 7.2M, and even their intersection was 1.46M documents —
   still far more than our actual property count justifies. Fixed by adding an
   exact-BBL filter (constructed identically on both sides: borough/borocode +
   zero-padded block + zero-padded lot) before intersecting, dropping every
   Legals row for a lot that isn't actually one of our target BBLs.
2. **Batch size too large for the Parties/References URL.** DOCUMENT_ID_BATCH_SIZE
   was 800 — at ~20 chars per quoted document_id, that's a ~16,000-character
   $where clause, and Socrata's endpoint returned "414 Request-URI Too Large" on
   the very first batch of a live run. Dropped to 200 (~4,000 chars), with
   comfortable margin below the observed failure point.

ACRIS Legals' `borough` field is a numeric code ("1".."5") matching PLUTO's
`borocode`, NOT PLUTO's `borough` field (a 2-letter code like "QN") — verified
against a live sample; using the wrong PLUTO column here would silently filter
against nothing. PLUTO must be pulled before this runs (scripts/ingest.py orders
it first) — its (borocode, block) values are what bounds the Legals pull.
"""
from pathlib import Path

import duckdb
import pandas as pd

from deed_theft_index.config import ACRIS_YEARS_LOOKBACK, DATA_RAW_DIR, DATASETS
from deed_theft_index.ingest.socrata import fetch_all, save_parquet

BLOCK_BATCH_SIZE = 800
DOCUMENT_ID_BATCH_SIZE = 200


def _exists(name: str) -> bool:
    return (Path(DATA_RAW_DIR) / f"{name}.parquet").exists()


def _batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _lookback_where() -> str:
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=ACRIS_YEARS_LOOKBACK)
    return f"document_date >= '{cutoff.date().isoformat()}T00:00:00.000'"


def pull_master_recent() -> pd.DataFrame:
    """Citywide, but date-bounded — single paginated pull, no batching. This is
    the ONLY citywide (non-geography-bounded) pull in this module; it's tractable
    because it's one filtered query, not thousands of IN-clause batches.
    """
    df = fetch_all(DATASETS["acris_master"], where=_lookback_where(), progress_label="master (date-bounded)")
    return df


def pull_legals_bounded(pluto_df: pd.DataFrame) -> pd.DataFrame:
    """Geography-bounded, full history (Legals has no date field to filter on) —
    single paginated pull per block-batch, no document-id batching. Over-selects
    at the lot level (every lot on a matching block, not just our exact BBLs) and
    across all history; both get trimmed by the intersection in pull_all().
    """
    blocks_by_borough = pluto_df.groupby("borocode")["block"].unique().apply(list).to_dict()

    frames = []
    for borocode, blocks in blocks_by_borough.items():
        for batch in _batched(blocks, BLOCK_BATCH_SIZE):
            block_list = ",".join(f"'{b}'" for b in batch)
            where = f"borough = '{borocode}' AND block in ({block_list})"
            frames.append(fetch_all(DATASETS["acris_legals"], where=where, progress_label=f"legals boro={borocode}"))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _pull_by_document_ids(dataset_key: str, document_ids: list, out_name: str) -> None:
    ids = sorted(set(document_ids))
    frames = []
    for batch in _batched(ids, DOCUMENT_ID_BATCH_SIZE):
        quoted = ",".join(f"'{doc_id}'" for doc_id in batch)
        frames.append(fetch_all(DATASETS[dataset_key], where=f"document_id in ({quoted})", progress_label=out_name))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    save_parquet(df, f"{DATA_RAW_DIR}/{out_name}.parquet")


def pull_all(pluto_df: pd.DataFrame) -> None:
    # Master/Legals are saved already-intersected (see below) — if both are on
    # disk from a prior run, their document_id set IS the intersected_ids list,
    # so it can be read straight back off disk instead of re-pulling and
    # re-intersecting two full citywide/geography-bounded datasets over the network.
    if _exists("acris_master") and _exists("acris_legals"):
        print("  ACRIS Master/Legals already pulled and intersected — reading document IDs from disk...", flush=True)
        intersected_ids = pd.read_parquet(
            f"{DATA_RAW_DIR}/acris_master.parquet", columns=["document_id"]
        )["document_id"].tolist()
    else:
        print("  Pulling ACRIS Master (date-bounded, citywide)...", flush=True)
        master_df = pull_master_recent()

        print("  Pulling ACRIS Legals (geography-bounded, full history)...", flush=True)
        legals_df = pull_legals_bounded(pluto_df)

        print(
            f"  Filtering {len(legals_df)} block-bounded Legals rows down to exact BBL "
            f"matches against {len(pluto_df)} target properties, then intersecting with "
            f"{len(master_df)} recent docs...",
            flush=True,
        )
        con = duckdb.connect()
        intersected_ids = con.execute("""
            SELECT DISTINCT m.document_id
            FROM master_df m
            JOIN (
                SELECT document_id, borough || lpad(block, 5, '0') || lpad(lot, 4, '0') AS bbl
                FROM legals_df
            ) l USING (document_id)
            JOIN (
                SELECT DISTINCT borocode || lpad(block, 5, '0') || lpad(lot, 4, '0') AS bbl
                FROM pluto_df
            ) p ON p.bbl = l.bbl
        """).fetchdf()["document_id"].tolist()
        con.close()
        print(f"  {len(intersected_ids)} documents are recent, in-neighborhood, and exact-BBL matched.", flush=True)

        master_df[master_df["document_id"].isin(intersected_ids)].to_parquet(f"{DATA_RAW_DIR}/acris_master.parquet", index=False)
        legals_df[legals_df["document_id"].isin(intersected_ids)].to_parquet(f"{DATA_RAW_DIR}/acris_legals.parquet", index=False)

    if _exists("acris_parties"):
        print("  ACRIS Parties already pulled — skipping.", flush=True)
    else:
        print("  Pulling ACRIS Parties for the intersected document IDs...", flush=True)
        _pull_by_document_ids("acris_parties", intersected_ids, "acris_parties")

    if _exists("acris_references"):
        print("  ACRIS References already pulled — skipping.", flush=True)
    else:
        print("  Pulling ACRIS References for the intersected document IDs...", flush=True)
        _pull_by_document_ids("acris_references", intersected_ids, "acris_references")
