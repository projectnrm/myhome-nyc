"""Generic Socrata SODA API client — CLAUDE.md Section 9: `requests` against
data.cityofnewyork.us/resource/{id}.json with SoQL $where/$limit/$offset, paginated
to local Parquet. Every dataset-specific module in ingest/ should call fetch_all().
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from deed_theft_index.config import SOCRATA_BASE_URL

load_dotenv()

PAGE_SIZE = 50_000


MAX_RETRIES = 4


def fetch_page(dataset_id: str, where: str | None = None, limit: int = PAGE_SIZE, offset: int = 0) -> list[dict]:
    """Fetch a single page of records from a Socrata dataset.

    Retries transient failures with exponential backoff — pulls against citywide
    datasets run long enough (dozens to thousands of small-batch requests) that a
    single mid-pull blip becomes likely, and without retry it kills the entire
    multi-minute-to-multi-hour job. Originally only covered connection-level
    errors (a live ReadTimeoutError after ~2M rows already fetched proved that
    much), but a live run also died on a plain HTTP 500 with ~99% of a multi-hour
    pull already done — transient 5xx server errors need the same retry, not just
    connection drops, so those are now covered too rather than assumed rare.
    """
    url = SOCRATA_BASE_URL.format(dataset_id=dataset_id)
    params = {"$limit": limit, "$offset": offset}
    if where:
        params["$where"] = where

    headers = {}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=120)
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                backoff = 2**attempt
                print(f"  [retry] HTTP {resp.status_code} on offset={offset}, retrying in {backoff}s (attempt {attempt + 1}/{MAX_RETRIES})", flush=True)
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt == MAX_RETRIES:
                raise
            backoff = 2**attempt
            print(f"  [retry] {type(e).__name__} on offset={offset}, retrying in {backoff}s (attempt {attempt + 1}/{MAX_RETRIES})", flush=True)
            time.sleep(backoff)


def fetch_all(
    dataset_id: str,
    where: str | None = None,
    sleep_between_pages: float = 0.2,
    progress_label: str | None = None,
) -> pd.DataFrame:
    """Paginate through an entire Socrata dataset (optionally filtered) into a DataFrame.

    Without a SOCRATA_APP_TOKEN set, requests throttle hard (CLAUDE.md Section 10) —
    register one before pulling anything at full scale. Prints page-by-page progress
    when progress_label is set — pulls against citywide datasets can run long enough
    that silent, unbuffered-stdout blocking looks indistinguishable from a hang.
    """
    records = []
    offset = 0
    page_num = 0
    while True:
        page = fetch_page(dataset_id, where=where, limit=PAGE_SIZE, offset=offset)
        page_num += 1
        if not page:
            break
        records.extend(page)
        if progress_label:
            print(f"  [{progress_label}] page {page_num}: +{len(page)} rows ({len(records)} total)", flush=True)
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE:
            break
        time.sleep(sleep_between_pages)

    return pd.DataFrame.from_records(records)


def save_parquet(df: pd.DataFrame, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_parquet(out_path, index=False)
