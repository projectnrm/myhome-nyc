"""Tax Lien Sale Lists ingestion — CLAUDE.md Section 4: financial distress signal."""
from deed_theft_index.config import DATA_RAW_DIR, DATASETS
from deed_theft_index.ingest.socrata import fetch_all, save_parquet


def pull() -> None:
    df = fetch_all(DATASETS["tax_lien_sale_lists"])
    save_parquet(df, f"{DATA_RAW_DIR}/tax_lien_sale_lists.parquet")
