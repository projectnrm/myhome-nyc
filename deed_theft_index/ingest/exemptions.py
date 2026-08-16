"""Property Exemption Detail ingestion — CLAUDE.md Section 4: SCHE/DHE senior/
disabled exemption flags. Pull most recent year only for the hackathon scorecard
(Section 3a); multi-year pull is needed later for the exemption-lapse feature (v2/cut).

The docstring above already stated "most recent year only," but the code never
actually filtered by year — a live check found ~500K rows *per year*, several
years present (`year` is DOF's fiscal year; 2027 is current as of this build).
Pulling unfiltered would mean several million rows for a value only one year of
which is used. Fixed here: discover the max year via a lightweight SoQL
aggregate query first, then filter the real pull to it — not hardcoded, since
"most recent" changes every fiscal year.
"""
import os

import requests

from deed_theft_index.config import DATA_RAW_DIR, DATASETS, SOCRATA_BASE_URL
from deed_theft_index.ingest.socrata import fetch_all, save_parquet


def _most_recent_year() -> str:
    url = SOCRATA_BASE_URL.format(dataset_id=DATASETS["property_exemption_detail"])
    headers = {}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    resp = requests.get(url, params={"$select": "max(year) as max_year"}, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()[0]["max_year"]


def pull() -> None:
    year = _most_recent_year()
    df = fetch_all(
        DATASETS["property_exemption_detail"],
        where=f"year = '{year}'",
        progress_label=f"exemptions (year={year})",
    )
    save_parquet(df, f"{DATA_RAW_DIR}/property_exemption_detail.parquet")
