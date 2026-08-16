"""TitleWatch — CLAUDE.md Section 8's internal, staff-authenticated risk-factor
lookup (address in, factor breakdown plus next steps out). Module/function names
below still say "self_lookup"/"lookup" rather than "titlewatch" — this was
originally built and named as a public self-lookup flow before Section 8's
internal-SSO-only decision was made; the nav label and in-page copy now reflect
that decision, but a full rename of the module and its internals is cosmetic
and hasn't been done. Headline is "X of N risk factors on file"; the numeric
point total is also shown, but as "X of Y possible points," never a percentage
or likelihood — CLAUDE.md originally specified score-free display entirely
(never a bare number), on the reasoning that there's no labeled ground truth to
calibrate a real probability against; showing the point total is a deliberate
reversal of that call, not an oversight, so the magnitude framing is kept as
the compromise.

Each factor is a row (topic label, status pill right-justified, chevron toggle)
that expands in place to a plain-English explanation — status is visible at a
glance without a click, detail is opt-in. Built with st.columns + a session_state
toggle rather than st.expander, because st.expander's label is plain text only
and can't hold a colored pill; a raw HTML label wouldn't work either — the pill
needs to be right-justified against a toggle button, meaning real Streamlit
widgets in a row, and widgets don't render inside markdown-supplied HTML wrappers
(each st.* call is its own DOM subtree, not nested inside a prior open <div> tag).
The two record-presence factors (senior/disabled exemption, tax lien) keep neutral
"Not on file" pill wording — absence there is ambiguous (real absence vs. a data
gap), so it's never styled as a checkmark/x either, matching Section 7's
SCHE-enrollment-gap caveat.

The gating here is UI-pattern-only for the hackathon demo (Section 9) — there is
no real identity verification. Say so explicitly in the UI; don't let it read as
a real security boundary. Real verification (mailed one-time code) is designed
in Section 8 but is a post-hackathon build item.
"""
import duckdb
import streamlit as st

from deed_theft_index.config import (
    DUCKDB_PATH,
    FEATURE_PILL_TEXT,
    FEATURE_PLAIN_EXPLANATION,
    FEATURE_PROTECTIVE_ACTIONS,
    FEATURE_SHORT_LABELS,
    SCORE_WEIGHTS,
    SCORED_FEATURES,
    risk_tier,
)
from deed_theft_index.geocode.geoclient import resolve_address

NEXT_STEPS = [
    "Register for the city's ACRIS Recorded Document Notification (NRD) alert program.",
    "Check ACRIS annually for any new filings against your property.",
    "Contact the Mayor's Office of Deed Theft Prevention (nyc.gov/deedfraud) with questions.",
]


def _factor_row(feature: str, record) -> None:
    on_file = bool(record.get(feature))
    pill_class = "risk-pill-on" if on_file else "risk-pill-off"
    pill_text = FEATURE_PILL_TEXT[feature][0] if on_file else FEATURE_PILL_TEXT[feature][1]
    state_key = f"factor_open_{feature}"
    is_open = st.session_state.get(state_key, False)

    # Default (top) column alignment, not vertical_alignment="center" — Streamlit
    # computes that centering by estimating each column's content height and
    # applying a margin-top to the shorter ones, but it measured this raw-HTML
    # pill column's content as 16px against the button's real 32px (verified via
    # getComputedStyle on every ancestor), producing a wrong 8px margin-top.
    # Fix: give every column's content the *same* explicit 2rem-tall flex box
    # myself, so they line up under plain top alignment without needing
    # Streamlit's own (here, buggy) height estimate at all.
    label_col, pill_col, toggle_col = st.columns([6, 3, 1])
    with label_col:
        st.markdown(
            f'<div style="display:flex; align-items:center; height:2rem;">'
            f'<b>{FEATURE_SHORT_LABELS[feature]}</b></div>',
            unsafe_allow_html=True,
        )
    with pill_col:
        st.markdown(
            f'<div style="display:flex; align-items:center; justify-content:flex-end; height:2rem;">'
            f'<span class="risk-pill {pill_class}">{pill_text}</span></div>',
            unsafe_allow_html=True,
        )
    with toggle_col:
        if st.button("︿" if is_open else "⌄", key=f"toggle_{feature}"):
            # A button click triggers exactly one script run using its new value —
            # there's no automatic second rerun after that. `is_open` above was
            # already read (stale) before this button was drawn, so without an
            # explicit rerun here the flip never visibly takes effect on this
            # click; verified by reproducing the no-op toggle in a minimal
            # isolated repro before restoring this call, not assumed.
            st.session_state[state_key] = not is_open
            st.rerun()

    if is_open:
        st.markdown(FEATURE_PLAIN_EXPLANATION[feature])


def render() -> None:
    st.subheader("TitleWatch")
    st.caption(
        "Individual risk-factor lookup — CLAUDE.md Section 8 designates this internal, "
        "staff-authenticated tooling for outreach teams, not a public feature. This "
        "hackathon build has no real authentication behind it yet; the tab label reflects "
        "the intended access model, not an enforced gate (see project design notes)."
    )

    with st.container(key="lookup_form_card"):
        with st.form("self_lookup_form"):
            house_number = st.text_input("House number")
            street = st.text_input("Street name")
            borough = st.selectbox("Borough", ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"])
            submitted = st.form_submit_button("Look up")

    # `submitted` is True only on the exact script run where the button was
    # clicked — the per-factor toggle buttons below also trigger a script rerun
    # (any widget interaction does), and on THAT rerun `submitted` is False again.
    # Persisting the resolved BBL in session_state, rather than gating the whole
    # results section on the transient `submitted` flag, is what keeps results
    # visible across those toggle-triggered reruns instead of vanishing — a real
    # bug caught by actually clicking a toggle button and watching the results
    # section disappear, not something that would show up from reading the code.
    if submitted:
        try:
            address = resolve_address(house_number, street, borough)
        except KeyError:
            st.error("Geoclient credentials not configured — set GEOCLIENT_PRIMARY_KEY in .env.")
            st.session_state.pop("lookup_bbl", None)
            return

        bbl = address.get("bbl")
        if not bbl:
            st.warning("Couldn't resolve that address to a property (BBL). Double-check the entry.")
            st.session_state.pop("lookup_bbl", None)
            return

        st.session_state["lookup_bbl"] = bbl

    bbl = st.session_state.get("lookup_bbl")
    if not bbl:
        return

    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        row = con.execute("SELECT * FROM properties WHERE bbl = ?", [bbl]).fetchdf()
    except duckdb.CatalogException:
        st.info("No scored data yet — run `python scripts/build.py` after ingestion.")
        return
    finally:
        con.close()

    if row.empty:
        st.warning("This property isn't in the current scored dataset (bounded-neighborhood pilot).")
        return

    record = row.iloc[0]
    present = [f for f in SCORED_FEATURES if bool(record.get(f))]
    max_possible = sum(SCORE_WEIGHTS[f] for f in SCORED_FEATURES)

    with st.container(key="factors_card"):
        st.markdown(f"### {len(present)} of {len(SCORED_FEATURES)} risk factors on file")
        st.markdown(f"**Risk score: {int(record['risk_score'])} of {max_possible} possible points**")
        st.caption(
            "A magnitude of documented risk factors present, not a probability or "
            "likelihood of theft — see \"How scoring works\" above for what each point "
            "means and why some real risk factors aren't captured here."
        )
        st.divider()
        for i, feature in enumerate(SCORED_FEATURES):
            if i > 0:
                st.divider()
            _factor_row(feature, record)

    with st.container(key="next_steps_card"):
        st.markdown("### Next steps")
        for step in NEXT_STEPS:
            st.markdown(f"- {step}")

    # Extra, factor-specific guidance for higher-tier properties — gated on the
    # tier (config.risk_tier, thresholds still placeholder pending real score
    # data) rather than shown for every lookup, and worded as "extra steps worth
    # considering" rather than a "HIGH RISK" label, consistent with Section 7/8's
    # "never a bare score, never implies certainty" framing elsewhere in this UI.
    if risk_tier(record["risk_score"]) == "High":
        present_by_weight = sorted(present, key=lambda f: SCORE_WEIGHTS[f], reverse=True)
        actions = [FEATURE_PROTECTIVE_ACTIONS[f] for f in present_by_weight if f in FEATURE_PROTECTIVE_ACTIONS]
        if actions:
            with st.container(key="additional_steps_card"):
                st.markdown("### Additional steps worth considering")
                st.caption(
                    "Several higher-weight risk factors are on file for this property — "
                    "these steps respond to which specific factors are present, ordered "
                    "by how much each one contributes to the factors above."
                )
                for action in actions:
                    st.markdown(f"- {action}")
