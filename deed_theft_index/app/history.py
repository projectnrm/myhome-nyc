"""History of My Home — CLAUDE.md Section 12. A fully public deed timeline for
any address, no login, no scoring — the deliberate opposite framing from the
main scorer for the exact same underlying facts (a $0 deed reads as "typically a
gift or family transfer" here, never a flag). No new ingestion pipeline needed:
pipeline/join.py's `filings_joined` table already carries every document per
BBL (not collapsed to most-recent, unlike `properties`) — this page just queries
it directly by BBL, which *is* the "separate, non-collapsed query path" Section
12 asks for.

Known gap, found during implementation, not guessed around: no lis pendens /
notice-of-pendency code exists anywhere in ACRIS's own Document Control Codes
reference table (confirmed live against 7isb-wh4c, 126 codes, all record_type
'D') — lis pendens are filed through NYS courts, not ACRIS document recording.
Section 12's "active legal notices surface above the timeline" feature is
therefore not buildable from data in scope; said so directly in the UI rather
than showing an always-empty "no active notices" state with false confidence.
"""
from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from deed_theft_index.app.sche_helper import property_type_label
from deed_theft_index.config import DOC_TYPE_NARRATIVE, DOC_TYPE_NEVER_STANDALONE, DUCKDB_PATH
from deed_theft_index.geocode.geoclient import resolve_address

RECENT_YEARS = 10  # matches LONG_TENURE_YEARS_THRESHOLD's concept but is a UI
# disclosure threshold, not a scoring one — kept separate in case they diverge.
BUNDLE_WINDOW_DAYS = 5  # "same-day/nearby-date" per Section 12
PRICE_MATCH_WINDOW_DAYS = 45


def _bundle_and_tier(filings: pd.DataFrame) -> list[dict]:
    """Group filings into narrative entries. A bundle's doc_date is its earliest
    member's date; members within BUNDLE_WINDOW_DAYS of that anchor join the same
    bundle. A bundle is "narrative" tier if any member is (so a deed bundled with
    an administrative filing like RPTT still surfaces by default), and its
    headline sentence is the highest-priority narrative member's template.
    """
    filings = filings.sort_values("document_date").reset_index(drop=True)
    bundles: list[dict] = []
    used = set()

    for i, row in filings.iterrows():
        if i in used:
            continue
        anchor_date = row["document_date"]
        window = filings[
            (filings["document_date"] >= anchor_date)
            & (filings["document_date"] <= anchor_date + pd.Timedelta(days=BUNDLE_WINDOW_DAYS))
            & (~filings.index.isin(used))
        ]
        used.update(window.index)

        doc_types = window["doc_type"].tolist()
        narrative_members = [t for t in doc_types if t in DOC_TYPE_NARRATIVE and t not in DOC_TYPE_NEVER_STANDALONE]
        is_narrative = len(narrative_members) > 0
        headline_type = narrative_members[0] if narrative_members else doc_types[0]

        all_parties: list[str] = []
        for names in window["party_names"]:
            if names is not None:
                all_parties.extend(n for n in names if n not in all_parties)

        # Grantee specifically, not "last name in the bundle" — a deed bundled
        # with a same-day mortgage (the common purchase-money-mortgage case)
        # would otherwise report the lender as the "current owner," since the
        # merged party pool above includes the mortgage's parties too. ACRIS
        # party_type '2' is the grantee on a deed row; only deed rows are
        # considered here, and only that row's own names/types (not the
        # window-merged, deduped pool) so the positions still correspond.
        deed_grantee = None
        for _, deed_row in window[window["is_deed"]].iterrows():
            # DuckDB LIST columns come back from fetchdf() as numpy arrays, not
            # plain Python lists — `if not names:` raises "truth value of an
            # array... is ambiguous", and ndarray has no .index(), so both are
            # coerced to plain lists up front (caught live, not assumed safe).
            names = list(deed_row["party_names"]) if deed_row["party_names"] is not None else []
            types = list(deed_row["party_types"]) if deed_row["party_types"] is not None else []
            if not names:
                continue
            if types and len(types) == len(names) and "2" in types:
                deed_grantee = names[types.index("2")]
            else:
                deed_grantee = names[-1]

        bundles.append({
            "date": anchor_date,
            "doc_types": doc_types,
            "headline": DOC_TYPE_NARRATIVE.get(headline_type, f"{headline_type} recorded."),
            "is_narrative": is_narrative,
            "is_recent": anchor_date >= (pd.Timestamp.today().normalize() - pd.DateOffset(years=RECENT_YEARS)),
            "parties": all_parties,
            "deed_grantee": deed_grantee,
            "is_deed": bool(window["is_deed"].any()),
        })

    return sorted(bundles, key=lambda b: b["date"], reverse=True)


def _match_price(sales: pd.DataFrame, target_date) -> int | None:
    if sales.empty:
        return None
    window = sales[(sales["sale_date"] - target_date).abs() <= pd.Timedelta(days=PRICE_MATCH_WINDOW_DAYS)]
    window = window[window["sale_price"] > 0]
    if window.empty:
        return None
    window = window.copy()
    window["distance"] = (window["sale_date"] - target_date).abs()
    return int(window.sort_values("distance").iloc[0]["sale_price"])


def render() -> None:
    st.subheader("History of My Home")
    st.caption(
        "A plain-language ownership timeline for any NYC property, built from public "
        "records — no score, no login, and available to anyone. This is a different "
        "surface than TitleWatch, the internal staff tool that flags risk factors; "
        "this page just tells the story of who's owned this property and when."
    )

    with st.container(key="history_form_card"):
        with st.form("history_lookup_form"):
            house_number = st.text_input("House number")
            street = st.text_input("Street name")
            borough = st.selectbox("Borough", ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"])
            submitted = st.form_submit_button("Look up this property")

    if submitted:
        try:
            address = resolve_address(house_number, street, borough)
        except KeyError:
            st.error("Geoclient credentials not configured — set GEOCLIENT_PRIMARY_KEY in .env.")
            st.session_state.pop("history_bbl", None)
            return

        bbl = address.get("bbl")
        if not bbl:
            st.warning("Couldn't resolve that address to a property (BBL). Double-check the entry.")
            st.session_state.pop("history_bbl", None)
            return

        st.session_state["history_bbl"] = bbl
        st.session_state.pop("history_show_earlier", None)
        st.session_state.pop("history_show_all", None)

    bbl = st.session_state.get("history_bbl")
    if not bbl:
        return

    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        prop = con.execute("SELECT * FROM properties WHERE bbl = ?", [bbl]).fetchdf()
        filings = con.execute(
            "SELECT * FROM filings_joined WHERE bbl = ? ORDER BY document_date", [bbl]
        ).fetchdf()
        try:
            sales = con.execute("SELECT * FROM sales_history WHERE bbl = ?", [bbl]).fetchdf()
        except duckdb.CatalogException:
            sales = pd.DataFrame(columns=["bbl", "sale_price", "sale_date"])
    except duckdb.CatalogException:
        st.info("No scored data yet — run `python scripts/build.py` after ingestion.")
        return
    finally:
        con.close()

    if filings.empty:
        st.warning(
            "No recorded documents found for this property in the current bounded-"
            "neighborhood pilot data."
        )
        return

    record = prop.iloc[0] if not prop.empty else None
    property_type = property_type_label(record.get("bldgclass")) if record is not None else None

    bundles = _bundle_and_tier(filings)
    deed_bundles = [b for b in bundles if b["is_deed"]]

    # --- Summary card ---
    with st.container(key="history_summary_card"):
        st.markdown("### Summary")
        if deed_bundles:
            latest_deed = deed_bundles[0]
            current_owner = latest_deed["deed_grantee"] or "Unknown"
            tenure_years = (pd.Timestamp.today().normalize() - latest_deed["date"]).days // 365
            st.markdown(f"- **Current owner (most recent deed):** {current_owner}")
            st.markdown(f"- **Owned since:** {latest_deed['date'].strftime('%B %Y')} (~{tenure_years} years)")
            price = _match_price(sales, latest_deed["date"])
            if price:
                st.markdown(f"- **Last sale price:** ${price:,} (matched to a recorded sale near this date)")
            st.markdown(f"- **Ownership changes on record:** {len(deed_bundles)}")
        if property_type:
            st.markdown(f"- **Property type:** {property_type}")
        if property_type == "co-op":
            st.caption(
                "Co-ops aren't fully covered yet — this tool tracks deed records, and "
                "co-op ownership is transferred by stock/proprietary lease, a different "
                "mechanism. Not covered by a separate model yet."
            )

    # Section 12: lis pendens can't be built from data in scope — say so plainly
    # rather than silently omit it or show a false-confidence empty state.
    st.info(
        "Active legal notices (like a pending lawsuit against this property) aren't "
        "available from this data source yet — that information is filed through "
        "NYS courts, not the city property-records system this tool uses."
    )

    # --- Timeline, toggle ladder ---
    with st.container(key="history_timeline_card"):
        st.markdown("### Timeline")

        show_earlier = st.session_state.get("history_show_earlier", False)
        show_all = st.session_state.get("history_show_all", False)

        def _visible(b: dict) -> bool:
            if show_all:
                return True
            if show_earlier:
                return b["is_narrative"]
            return b["is_narrative"] and b["is_recent"]

        visible_bundles = [b for b in bundles if _visible(b)]
        hidden_earlier_count = len([b for b in bundles if b["is_narrative"] and not b["is_recent"]]) if not show_earlier and not show_all else 0
        hidden_admin_count = len([b for b in bundles if not b["is_narrative"]]) if not show_all else 0

        # Plain st.divider() between entries, not a container(key=...) per entry —
        # container keys must be statically registered in style.py's CARD_KEYS to
        # get the card styling, which a per-entry dynamic key (one per date) can't
        # be; entries render as content inside the one already-styled
        # history_timeline_card instead, matching self_lookup.py's factor-row pattern.
        for i, b in enumerate(visible_bundles):
            if i > 0:
                st.divider()
            price = _match_price(sales, b["date"]) if b["is_deed"] else None
            st.markdown(f"**{b['date'].strftime('%B %d, %Y')}**")
            st.markdown(b["headline"])
            if price:
                st.caption(f"Recorded sale price: ${price:,}")
            elif b["is_deed"]:
                st.caption(
                    "No sale price on file for this transfer — this typically "
                    "indicates a gift, inheritance, or family transfer, not "
                    "necessarily anything else."
                )
            if b["parties"]:
                st.caption(", ".join(b["parties"]))
        st.divider()

        oldest_date = bundles[-1]["date"]
        st.caption(
            f"Earliest record in NYC's digital system: {oldest_date.strftime('%B %Y')} — "
            "earlier transfers may exist only in physical records."
        )
        st.caption(
            "Reflects this specific lot's current configuration — lot lines can merge "
            "or subdivide over time, so this is the history of this lot as it exists "
            "today, not necessarily everything that ever happened at this address."
        )
        st.caption("Records current as of the last data pull. Not a substitute for a title search or legal advice.")

        # Explicit stable keys, not auto-generated-from-label — the label text
        # includes a count that changes as the ladder is climbed, and an
        # auto-generated key tied to that changing label risks Streamlit treating
        # each count change as a different widget rather than the same toggle.
        if not show_all:
            col1, col2 = st.columns(2)
            with col1:
                if not show_earlier and hidden_earlier_count:
                    if st.button(f"Show earlier history ({hidden_earlier_count} more)", key="history_btn_earlier"):
                        st.session_state["history_show_earlier"] = True
                        st.rerun()
            with col2:
                if hidden_admin_count or (not show_earlier and hidden_earlier_count):
                    total_hidden = len(bundles) - len(visible_bundles)
                    if st.button(f"Show all recorded documents ({total_hidden} more)", key="history_btn_all"):
                        st.session_state["history_show_all"] = True
                        st.session_state["history_show_earlier"] = True
                        st.rerun()

    # Section 13's discovery path: surface the SCHE/DHE Helper contextually when
    # no exemption is on file, rather than only as a standalone tool.
    if record is not None and not bool(record.get("has_sche")) and not bool(record.get("has_dhe")):
        st.info(
            "Not currently getting a senior or disability property tax exemption on "
            "this property? Use the **SCHE/DHE Enrollment Helper** (see the view "
            "toggle above) to check if you might qualify."
        )
