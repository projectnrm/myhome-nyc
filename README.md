# NYC Deed Theft Risk Index

Hackathon build — see [CLAUDE.md](CLAUDE.md) for full project context, scope, and
methodology. Start there, not here.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in SOCRATA_APP_TOKEN and GEOCLIENT_APP_ID/KEY
```

## Run

```bash
python scripts/ingest.py   # pull raw datasets to data/raw/
python scripts/build.py    # join + score -> data/processed/deed_theft_index.duckdb
streamlit run deed_theft_index/app/main.py
```

## Deploy data (demo only)

A fresh clone has no `data/processed/` database, so the app falls back to the
committed `data/deploy/deed_theft_index.duckdb` and shows a "Demo build" banner.
That file never holds real property-level data, because an address-level list of
vulnerable homes is the target list this project exists to protect
(CLAUDE.md Section 8):

- `properties`, `filings_joined`, `sales_history`: synthetic rows only (owner names
  start with `DEMO:`). Try **1 Centre Street, Manhattan** in any lookup.
- `cd_risk_aggregate`: real scores, averaged by community district (no BBL,
  address, owner, or factor flags; districts under 100 properties are dropped).

Rebuild it after a real scoring run with:

```bash
python scripts/build_deploy_db.py   # reads data/processed/, writes data/deploy/
python -m pytest tests/             # fails if anything real slipped in
```

## Layout

```
deed_theft_index/
  config.py       # dataset IDs, scope, scoring weights (single source of truth)
  ingest/         # Socrata SODA pulls, one module per dataset
  geocode/        # Geoclient address -> BBL resolution (self-lookup only)
  pipeline/       # join.py (Section 5 join sequence), score.py (Section 7 scorecard)
  app/            # Streamlit UI: public heatmap + self-lookup toggle
scripts/
  ingest.py       # CLI: run all ingestion
  build.py        # CLI: run join + score pipeline
```
