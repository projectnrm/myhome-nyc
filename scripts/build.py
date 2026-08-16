#!/usr/bin/env python
"""Run the join pipeline + v1 scorecard against pulled raw data — CLAUDE.md
Sections 5 and 7. Re-run manually before each demo; no scheduler for the hackathon.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deed_theft_index.config import DUCKDB_PATH
from deed_theft_index.pipeline import join, score


def main() -> None:
    print("Running join pipeline (ACRIS -> filings -> properties)...")
    join.run()

    print("Computing v1 scorecard...")
    con = join.get_connection()
    score.compute_scores(con)
    con.close()

    print("Done. Scored `properties` table written to", DUCKDB_PATH)


if __name__ == "__main__":
    main()
