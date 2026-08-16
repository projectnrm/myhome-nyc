"""SCHE/DHE Enrollment Helper — CLAUDE.md Section 13. A screening tool, not an
eligibility determination; unlike the main scorer and History of My Home, this
page collects a few self-reported answers (age bracket, primary-residence status,
income bracket) that don't exist in any public dataset. Section 13's privacy
guardrail is the whole point of this file: those answers live in
`st.session_state` only, computed and discarded client-side — nothing here ever
writes them to DuckDB or disk. If a future edit adds a database write for
self-reported answers, that's the one thing this page was specifically designed
never to do.

Follows self_lookup.py's established address-lookup pattern (form ->
resolve_address -> DuckDB query -> session-state-persisted BBL so results survive
reruns from the form's own widget interactions).
"""
from __future__ import annotations

import duckdb
import streamlit as st

from deed_theft_index.config import DUCKDB_PATH
from deed_theft_index.geocode.geoclient import resolve_address

# CLAUDE.md Section 13: same simple-prefix simplification already used for
# individually_owned in score.py (Section 3a: "no trust-detection edge case") —
# A/B = 1-3 family, R = condo, C = co-op. Imprecise at the edges (C also covers
# larger walkup apartment buildings), not a legal determination either way.
FAMILY_PREFIXES = ("A", "B")
CONDO_PREFIX = "R"
COOP_PREFIX = "C"

OWNERSHIP_MONTHS_REQUIRED = 12


def property_type_label(bldg_class: str) -> str | None:
    """Shared with app/history.py (its co-op scope-gap messaging needs the same
    classification) — not private to this module despite living here first."""
    if not bldg_class:
        return None
    prefix = bldg_class[0]
    if prefix in FAMILY_PREFIXES:
        return "1-3 family home"
    if prefix == CONDO_PREFIX:
        return "condo"
    if prefix == COOP_PREFIX:
        return "co-op"
    return None


def render() -> None:
    st.subheader("SCHE/DHE Enrollment Helper")
    st.caption(
        "Check whether this property already has a Senior Citizen (SCHE) or "
        "Disabled Homeowner (DHE) property tax exemption on file, and screen for "
        "eligibility if it doesn't."
    )

    with st.container(key="sche_form_card"):
        with st.form("sche_lookup_form"):
            house_number = st.text_input("House number")
            street = st.text_input("Street name")
            borough = st.selectbox("Borough", ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"])
            submitted = st.form_submit_button("Check this property")

    # Same session-state-persisted-BBL pattern as self_lookup.py: `submitted` is
    # only True on the exact run the button was clicked, and the self-report
    # form's own widgets (below) trigger reruns too — gating on session_state
    # instead of the transient flag is what keeps results from vanishing on
    # those reruns.
    if submitted:
        try:
            address = resolve_address(house_number, street, borough)
        except KeyError:
            st.error("Geoclient credentials not configured — set GEOCLIENT_PRIMARY_KEY in .env.")
            st.session_state.pop("sche_bbl", None)
            return

        bbl = address.get("bbl")
        if not bbl:
            st.warning("Couldn't resolve that address to a property (BBL). Double-check the entry.")
            st.session_state.pop("sche_bbl", None)
            return

        st.session_state["sche_bbl"] = bbl

    bbl = st.session_state.get("sche_bbl")
    if not bbl:
        return

    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        # owned_12_plus_months computed in SQL (DuckDB date_diff), matching the
        # date-math pattern score.py already uses — avoids Python-side ambiguity
        # over whether DuckDB hands back a datetime.date or a pandas Timestamp.
        row = con.execute(
            f"""
            SELECT *,
                (last_deed_date IS NULL
                    OR date_diff('month', last_deed_date, current_date) >= {OWNERSHIP_MONTHS_REQUIRED}
                ) AS owned_12_plus_months
            FROM properties WHERE bbl = ?
            """,
            [bbl],
        ).fetchdf()
    except duckdb.CatalogException:
        st.info("No scored data yet — run `python scripts/build.py` after ingestion.")
        return
    finally:
        con.close()

    if row.empty:
        st.warning("This property isn't in the current scored dataset (bounded-neighborhood pilot).")
        return

    record = row.iloc[0]
    has_sche = bool(record.get("has_sche"))
    has_dhe = bool(record.get("has_dhe"))

    with st.container(key="sche_autocheck_card"):
        st.markdown("### What we already know about this property")

        property_type = property_type_label(record.get("bldgclass"))
        owned_12_plus_months = bool(record.get("owned_12_plus_months"))

        st.markdown(f"- **Property type:** {property_type or 'Could not determine from city records'}")
        st.markdown(
            f"- **Ownership length:** "
            f"{'12+ months (meets the minimum to apply)' if owned_12_plus_months else 'Less than 12 months on record'}"
        )
        if has_sche or has_dhe:
            on_file = "SCHE" if has_sche else "DHE"
            st.markdown(f"- **Exemption status:** {on_file} is currently **on file** for this property.")
        else:
            st.markdown(
                "- **Exemption status:** No SCHE or DHE exemption currently on file — "
                "**this doesn't mean you don't qualify**, just that DOF has no record of it "
                "(see the enrollment-gap note in \"How scoring works\")."
            )

    # Already-enrolled: confirmation + a generic renewal reminder, no self-report
    # form needed — CLAUDE.md Section 13's output state 1.
    if has_sche or has_dhe:
        with st.container(key="sche_output_card"):
            exemption_name = "Senior Citizen Homeowner Exemption (SCHE)" if has_sche else "Disabled Homeowner Exemption (DHE)"
            st.success(f"{exemption_name} is on file for this property.")
            st.markdown(
                "SCHE/DHE renews on a **24-month cycle** — if you haven't reconfirmed "
                "recently, check with NYC DOF that your renewal is current. "
                "(This is a generic reminder, not a specific renewal date — that "
                "would need a multi-year exemption history this build doesn't pull.)"
            )
            if has_sche:
                st.caption("Bonus: SCHE recipients automatically also get Enhanced STAR — no separate action needed.")
        return

    # Not on file — run the self-report screening. Session-state only, per the
    # module docstring's privacy guardrail: nothing below this line is ever
    # written to DuckDB or disk.
    with st.container(key="sche_screening_card"):
        st.markdown("### Quick screening")
        st.caption(
            "Three questions — none of this is saved or linked to this address. "
            "It only exists in your browser for this session."
        )

        st.markdown("**Are you 65 or older, or under 65 with a qualifying disability?**")
        age_col, disability_col = st.columns(2)
        with age_col:
            is_65_plus = st.button("65 or older (SCHE)", key="sche_age_65", width="stretch")
        with disability_col:
            is_disabled = st.button("Under 65, disability (DHE)", key="sche_age_disabled", width="stretch")

        if is_65_plus:
            st.session_state["sche_path"] = "SCHE"
        elif is_disabled:
            st.session_state["sche_path"] = "DHE"

        path = st.session_state.get("sche_path")
        if path:
            primary_residence = st.radio("Is this property your primary residence?", ["Yes", "No"], key="sche_primary")
            # Dollar signs escaped (\$) — Streamlit's markdown-aware widgets treat
            # matched pairs of unescaped `$` as inline LaTeX, and the middle option
            # here has two of them ("$50,001 to $58,399"), which rendered as mangled
            # math notation instead of a dollar amount until this was caught live.
            income_bracket = st.radio(
                "What's your household's combined annual income (all owners, all sources)?",
                ["\\$50,000 or less", "\\$50,001 to \\$58,399", "Over \\$58,399"],
                key="sche_income",
            )

            eligible_income = income_bracket != "Over \\$58,399"
            eligible = primary_residence == "Yes" and eligible_income and owned_12_plus_months

            st.divider()
            exemption_name = "SCHE" if path == "SCHE" else "DHE"
            if eligible:
                st.success(
                    f"Based on what you told us, you may be eligible for {exemption_name} and it's "
                    f"not currently on file for this property. Applications are due **March 15** "
                    f"for the following July 1 billing period."
                )
                # Verified live via web search — the URL guessed on the first pass
                # had both the wrong subdomain (www vs. home) and wrong path segment
                # (benefits vs. property), so this got checked, not assumed correct.
                st.link_button("Learn more / apply (NYC DOF)", "https://home.nyc.gov/site/finance/property/landlords-sche.page")
            else:
                st.info(
                    f"Based on what you told us, this property may not currently qualify for "
                    f"{exemption_name} — DOF is the authoritative source, and rules can change, "
                    f"so it's worth checking directly if your situation changes."
                )

        st.caption("This is a screening tool, not an eligibility determination — NYC DOF makes the final decision.")
