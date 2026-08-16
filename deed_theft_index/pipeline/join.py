"""Join pipeline — implements CLAUDE.md Section 5's join sequence over DuckDB,
reading Parquet directly from data/raw/. Two grains: `filings` (one row per ACRIS
Document ID) collapsed to one row per BBL, then joined into `properties` (one row
per BBL, spined on PLUTO) — never the reverse.

Column names below are the standard ACRIS/PLUTO Socrata field names but were not
verified against actually-pulled data in the planning session (CLAUDE.md Section 4/10)
— run `describe select * from read_parquet(...)` in DuckDB against each raw file
before trusting a join, and fix names here if the live schema differs.

The BBL-level collapse deliberately keeps last-deed/last-mortgage/last-satisfaction
dates separately (not just "the single most recent filing") — free_and_clear
(score.py) needs to compare mortgage vs. satisfaction recency, which a single
most-recent-row collapse would silently lose.
"""
import duckdb

from deed_theft_index.config import (
    ACRIS_DEED_DOC_TYPES,
    ACRIS_MORTGAGE_DOC_TYPES,
    ACRIS_SATISFACTION_DOC_TYPES,
    DATA_RAW_DIR,
    DHE_EXEMPTION_CODE,
    DUCKDB_PATH,
    SCHE_EXEMPTION_CODE,
)


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DUCKDB_PATH)


def build_filings(con: duckdb.DuckDBPyConnection) -> None:
    """CLAUDE.md Section 5, steps 1-4: Master + Legals + Parties + References,
    collapsed to one row per BBL on most recent recording date.

    Join-explosion checks to run manually before trusting this: row count of
    master+legals should stay close to len(master) unless blanket filings are
    common in the neighborhood subset; parties should be pre-aggregated to one
    array-of-names row per document_id before joining anything else.
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE legals_with_bbl AS
        SELECT
            document_id,
            borough,
            block,
            lot,
            -- TODO verify: BBL is typically borough(1) + block(5, zero-padded) + lot(4, zero-padded)
            borough || lpad(block, 5, '0') || lpad(lot, 4, '0') AS bbl
        FROM read_parquet('{DATA_RAW_DIR}/acris_legals.parquet');
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE parties_agg AS
        SELECT
            document_id,
            -- Deduping name and party_type as two SEPARATE lists (the earlier
            -- version of this query) silently breaks the positional correspondence
            -- between party_names[i] and party_types[i] — e.g. history.py needs
            -- to find the deed row's grantee (party_type '2') by matching against
            -- its own name, which only works if the two arrays stay paired.
            -- Deduping the (name, party_type) pair as a single struct, then
            -- splitting back into two parallel arrays, keeps that correspondence.
            list(DISTINCT {{'name': name, 'party_type': party_type}}) AS parties
        FROM read_parquet('{DATA_RAW_DIR}/acris_parties.parquet')
        GROUP BY document_id;
    """)

    deed_types = ",".join(f"'{t}'" for t in ACRIS_DEED_DOC_TYPES)
    mortgage_types = ",".join(f"'{t}'" for t in ACRIS_MORTGAGE_DOC_TYPES)
    satisfaction_types = ",".join(f"'{t}'" for t in ACRIS_SATISFACTION_DOC_TYPES)

    con.execute(f"""
        CREATE OR REPLACE TABLE filings_joined AS
        SELECT
            m.document_id,
            m.doc_type,
            -- Socrata returns document_date as a string; cast explicitly or every
            -- downstream date_diff/comparison against current_date fails to bind.
            CAST(m.document_date AS DATE) AS document_date,
            m.document_amt,
            l.bbl,
            list_transform(p.parties, x -> x.name) AS party_names,
            list_transform(p.parties, x -> x.party_type) AS party_types,
            m.doc_type IN ({deed_types}) AS is_deed,
            m.doc_type IN ({mortgage_types}) AS is_mortgage,
            m.doc_type IN ({satisfaction_types}) AS is_satisfaction
        FROM read_parquet('{DATA_RAW_DIR}/acris_master.parquet') m
        JOIN legals_with_bbl l USING (document_id)
        LEFT JOIN parties_agg p USING (document_id);
    """)

    # Step 4: collapse to one row per BBL — but keep last-deed/mortgage/satisfaction
    # dates as separate columns rather than a single "most recent row", since
    # free_and_clear (score.py) needs to compare mortgage vs. satisfaction recency.
    con.execute("""
        CREATE OR REPLACE TABLE filings AS
        SELECT
            bbl,
            max(document_date) AS most_recent_doc_date,
            arg_max(doc_type, document_date) AS most_recent_doc_type,
            arg_max(party_names, document_date) AS most_recent_party_names,
            max(document_date) FILTER (is_deed) AS last_deed_date,
            max(document_date) FILTER (is_mortgage) AS last_mortgage_date,
            max(document_date) FILTER (is_satisfaction) AS last_satisfaction_date
        FROM filings_joined
        GROUP BY bbl;
    """)


def build_properties(con: duckdb.DuckDBPyConnection) -> None:
    """CLAUDE.md Section 5, steps 5-6: PLUTO + Exemption Detail + Tax Liens + Sales,
    spined on BBL. Watch field-format inconsistency across DOF datasets — some use
    a single padded BBL string, others separate borough/block/lot columns.

    PLUTO's own `bbl` field is NOT used directly — a live pull showed it formatted
    as "1000360030.00000000" (float-style, trailing zeros) while the ACRIS-derived
    bbl in `legals_with_bbl` is "1000360030" (clean, zero-padded string). Joining
    on those directly would silently match zero rows. Reconstructed here from
    PLUTO's `borocode`/`block`/`lot` with the identical padding scheme instead, so
    both sides of the join are guaranteed to agree. Also casts `cd` to INTEGER —
    PLUTO returns it as a string, and app/public_view.py compares it against
    config.NEIGHBORHOODS' int tuples.

    Property Exemption Detail's `parid` field is, by contrast, already a clean
    10-digit BBL string (verified live) — no reconstruction needed on that side.
    Filtered to SCHE (1015) / DHE (1019) specifically, both confirmed live against
    the "Exemption Classification Codes" reference dataset, not guessed.
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE exemptions_latest AS
        SELECT
            parid AS bbl,
            bool_or(exmp_code = '{SCHE_EXEMPTION_CODE}') AS has_sche,
            bool_or(exmp_code = '{DHE_EXEMPTION_CODE}') AS has_dhe
        FROM read_parquet('{DATA_RAW_DIR}/property_exemption_detail.parquet')
        GROUP BY parid;
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE properties AS
        SELECT
            pluto.borocode || lpad(pluto.block, 5, '0') || lpad(pluto.lot, 4, '0') AS bbl,
            pluto.* EXCLUDE (bbl, cd),
            CAST(pluto.cd AS INTEGER) AS cd,
            filings.most_recent_doc_type,
            filings.most_recent_doc_date,
            filings.most_recent_party_names,
            filings.last_deed_date,
            filings.last_mortgage_date,
            filings.last_satisfaction_date,
            coalesce(ex.has_sche, FALSE) AS has_sche,
            coalesce(ex.has_dhe, FALSE) AS has_dhe
        FROM read_parquet('{DATA_RAW_DIR}/pluto.parquet') pluto
        LEFT JOIN filings
            ON filings.bbl = pluto.borocode || lpad(pluto.block, 5, '0') || lpad(pluto.lot, 4, '0')
        LEFT JOIN exemptions_latest ex
            ON ex.bbl = pluto.borocode || lpad(pluto.block, 5, '0') || lpad(pluto.lot, 4, '0');
    """)

    # TODO: join tax_lien_sale_lists.parquet onto `properties` once its actual
    # BBL/borough-block-lot column names are confirmed from a pulled sample
    # (CLAUDE.md Section 4 "verify" flag) — property_exemption_detail's join is
    # done above (parid = clean BBL, no reconstruction needed there).


def build_sales_history(con: duckdb.DuckDBPyConnection) -> None:
    """History of My Home's price-matching source (CLAUDE.md Section 12) —
    combined Rolling + Annualized Calendar Sales, BBL-constructed the same way as
    ACRIS Legals (borough/block/lot, confirmed live to share that shape). A
    property can appear in both source files across years; kept as separate rows
    here (not deduped/collapsed) since history.py matches by exact date against a
    specific deed, not "most recent sale."
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE sales_history AS
        SELECT
            borough || lpad(block, 5, '0') || lpad(lot, 4, '0') AS bbl,
            TRY_CAST(sale_price AS BIGINT) AS sale_price,
            CAST(sale_date AS DATE) AS sale_date
        FROM read_parquet('{DATA_RAW_DIR}/rolling_calendar_sales.parquet')
        UNION ALL
        SELECT
            borough || lpad(block, 5, '0') || lpad(lot, 4, '0') AS bbl,
            TRY_CAST(sale_price AS BIGINT) AS sale_price,
            CAST(sale_date AS DATE) AS sale_date
        FROM read_parquet('{DATA_RAW_DIR}/annualized_calendar_sales.parquet');
    """)


def run() -> None:
    con = get_connection()
    build_filings(con)
    build_properties(con)
    build_sales_history(con)
    con.close()
