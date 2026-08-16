"""NYC Geoclient API (DoITT) — CLAUDE.md Section 11: address -> BBL resolution for
the self-lookup flow only (not used for bulk ingestion; 311 geocoding is deferred
to v2 per Section 3a). Results are cached locally to a JSON file to avoid re-hitting
the API for repeat lookups during the demo.

Geoclient v1 (CLAUDE.md's originally documented api.nyc.gov/geoclient/v1/ with
app_id/app_key params) is retired. Current version is v2, a different shape
entirely: one `/search` endpoint taking a single unparsed `input` location string
(not separate houseNumber/street/borough params), auth via a single subscription
key in the Ocp-Apim-Subscription-Key header. Verified live 2026-08-15 against
https://api.nyc.gov/geoclient/v2/search (note: no `/geo/` path segment, unlike v1).
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.nyc.gov/geoclient/v2/search"
CACHE_PATH = "data/processed/geoclient_cache.json"


def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)


def resolve_address(house_number: str, street: str, borough: str) -> dict:
    """Resolve a street address to Geoclient's response fields (bbl, communityDistrict,
    etc.) for self-lookup. Returns {} if Geoclient found no exact match.

    Raises if GEOCLIENT_PRIMARY_KEY isn't set — register at api-portal.nyc.gov,
    subscribe to the "Geoclient" product (an account alone isn't enough), then
    copy the Primary key from your profile (CLAUDE.md Section 10).
    """
    cache_key = f"{house_number}|{street}|{borough}".upper()
    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]

    subscription_key = os.environ["GEOCLIENT_PRIMARY_KEY"]

    input_str = f"{house_number} {street} {borough}"
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    resp = requests.get(BASE_URL, params={"input": input_str}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    result = results[0]["response"] if results and results[0].get("status") == "EXACT_MATCH" else {}

    cache[cache_key] = result
    _save_cache(cache)
    return result
