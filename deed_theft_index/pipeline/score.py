"""v1 scorecard — CLAUDE.md Section 7. Each feature is a boolean/points column
computed on the `properties` table built by pipeline/join.py; final score is the
weighted sum from config.SCORE_WEIGHTS. Present results as "risk factors present"
with contributing factors listed — never a bare number or a probability (Section 7).

Predicate logic below follows the feature definitions in Section 7 but the exact
column references depend on the live PLUTO/exemption/tax-lien schema — verify
against a pulled sample before trusting scores (see join.py's schema TODOs).
"""
import duckdb

from deed_theft_index.config import LONG_TENURE_YEARS_THRESHOLD, SCORE_WEIGHTS


def add_free_and_clear(con: duckdb.DuckDBPyConnection) -> None:
    """25 pts — most recent mortgage (if any) has since been satisfied, with no
    newer mortgage recorded after that satisfaction; or no mortgage was ever
    recorded within the ACRIS_YEARS_LOOKBACK window (config.py) at all (Section 7).

    Compares last_mortgage_date vs. last_satisfaction_date rather than checking
    only the single most-recent filing — a mortgage followed by its satisfaction
    is exactly the free-and-clear case, but wouldn't be "the most recent doc type"
    if anything else was filed after the satisfaction (e.g. a later, unrelated
    document). NULL last_mortgage_date within the lookback window is treated as
    free-and-clear; it can't distinguish "never had a mortgage" from "mortgage
    predates the window", which is the same caveat CLAUDE.md's Section 7 flags for
    this feature generally (satisfaction filings can lag real-world payoff).
    """
    con.execute("""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS free_and_clear BOOLEAN;
        UPDATE properties
        SET free_and_clear = (
            last_mortgage_date IS NULL
            OR (last_satisfaction_date IS NOT NULL AND last_satisfaction_date > last_mortgage_date)
        );
    """)


def add_senior_disabled_exemption(con: duckdb.DuckDBPyConnection) -> None:
    """20 pts — active SCHE/DHE exemption on file for the current/most recent tax year.

    has_sche/has_dhe come from join.py's build_properties(), joined against
    Property Exemption Detail filtered to SCHE (1015) / DHE (1019) — both
    confirmed live against DOF's Exemption Classification Codes reference.
    """
    con.execute("""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS senior_disabled_exemption BOOLEAN;
        UPDATE properties SET senior_disabled_exemption = (has_sche OR has_dhe);
    """)


def add_long_tenure_no_deed_activity(con: duckdb.DuckDBPyConnection) -> None:
    """20 pts — no deed-type document (not mortgage/satisfaction) recorded against
    the BBL in at least LONG_TENURE_YEARS_THRESHOLD years (default 10, Section 7:
    'to be validated statistically').

    NULL last_deed_date counts as long-tenure: ACRIS ingestion is bounded to
    ACRIS_YEARS_LOOKBACK (config.py, currently 15) years, comfortably wider than
    the 10-year threshold, so "no deed in the pulled window" already implies "no
    deed in at least ACRIS_YEARS_LOOKBACK years" — no need to see further history.
    """
    con.execute(f"""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS long_tenure_no_deed_activity BOOLEAN;
        UPDATE properties
        SET long_tenure_no_deed_activity = (
            last_deed_date IS NULL
            OR date_diff('year', last_deed_date, current_date) >= {LONG_TENURE_YEARS_THRESHOLD}
        );
    """)


def add_individually_owned(con: duckdb.DuckDBPyConnection) -> None:
    """10 pts — owner-occupied 1-3 family home, not LLC/INC/CORP (simple suffix regex,
    no trust-detection edge case per Section 3a cut-list).

    PLUTO owner names commonly carry trailing whitespace/periods (e.g. "SMITH LLC ",
    "JONES CORP."), so trim before matching — an untrimmed match against a name with
    trailing space would silently fail the suffix check and misclassify an LLC as
    individually owned.
    """
    con.execute("""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS individually_owned BOOLEAN;
        UPDATE properties
        SET individually_owned = NOT regexp_matches(trim(upper(ownername)), '(LLC|INC|CORP)\\.?$');
    """)  # TODO: confirm PLUTO's actual owner-name column is `ownername`.


def add_tax_lien_history(con: duckdb.DuckDBPyConnection) -> None:
    """15 pts — BBL appears currently or historically on Tax Lien Sale Lists."""
    # TODO: requires tax_lien_sale_lists joined onto properties (join.py TODO).
    con.execute("""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS tax_lien_history BOOLEAN;
        UPDATE properties SET tax_lien_history = FALSE WHERE tax_lien_history IS NULL;
    """)


FEATURE_FUNCS = {
    "free_and_clear": add_free_and_clear,
    "senior_disabled_exemption": add_senior_disabled_exemption,
    "long_tenure_no_deed_activity": add_long_tenure_no_deed_activity,
    "individually_owned": add_individually_owned,
    "tax_lien_history": add_tax_lien_history,
}


def compute_scores(con: duckdb.DuckDBPyConnection) -> None:
    for func in FEATURE_FUNCS.values():
        func(con)

    weighted_terms = " + ".join(
        f"(CAST({feature} AS INTEGER) * {points})" for feature, points in SCORE_WEIGHTS.items()
        if feature in FEATURE_FUNCS
    )
    con.execute(f"""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS risk_score INTEGER;
        UPDATE properties SET risk_score = {weighted_terms};
    """)
