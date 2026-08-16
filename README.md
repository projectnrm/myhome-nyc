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
