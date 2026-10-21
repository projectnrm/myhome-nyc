"""Streamlit entrypoint — CLAUDE.md Section 8: single app ("MyHome") toggled
between public views (History of My Home, the SCHE/DHE Helper, the Deed Theft
Risk Heatmap) and TitleWatch — the individual risk-factor lookup that Section 8
designates internal/staff-only — not separate pages, so the boundary between
public and internal stays explicit in the UI itself. TitleWatch has no real
auth in this hackathon build (self_lookup.py's own copy says so); the label is
what signals its intended access model, not an enforced gate. Run with:
streamlit run deed_theft_index/app/main.py
"""
import sys
from pathlib import Path

# Streamlit executes this file directly, so the project root (two levels up)
# never lands on sys.path on its own — without this, `deed_theft_index.app...`
# imports below fail with ModuleNotFoundError regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import base64

import streamlit as st

from deed_theft_index.app import history, how_scoring_works, public_view, sche_helper, self_lookup
from deed_theft_index.app.style import CSS
from deed_theft_index.config import DEMO_MODE, DEMO_TEST_ADDRESS

st.set_page_config(page_title="MyHome", page_icon="🏠", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

# NYC wordmark — inlined as a data URI (not a static-file URL) since Streamlit
# has no built-in static-asset route for arbitrary images short of its
# experimental static-serving flag; base64-embedding in the markdown block
# sidesteps that entirely. Falls back to plain "NYC" text if the asset isn't
# in place yet, rather than a broken <img>.
_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "nyc-logo.svg"
if _LOGO_PATH.exists():
    _logo_b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    _logo_html = f'<img class="hero-logo" src="data:image/svg+xml;base64,{_logo_b64}" alt="NYC">'
else:
    _logo_html = '<span class="hero-logo-fallback">NYC</span>'

st.markdown(
    f"""
    <div class="hero-band">
        <div class="hero-band-inner">
            {_logo_html}
            <div class="hero-title-group">
                <h1>MyHome</h1>
                <p>Free tools for NYC homeowners: look up your home's history, check if you
                qualify for property tax savings, and see how deed theft risk looks across
                NYC neighborhoods — all built from public city data.</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if DEMO_MODE:
    st.info(
        "**Demo build.** Property-level records here are synthetic, so no real "
        "homeowner's risk factors are ever published. Try the address "
        f"**{DEMO_TEST_ADDRESS}** in any lookup. The neighborhood heatmap shows real, "
        "aggregated scores from NYC Open Data."
    )

# Custom nav (not st.radio) — a plain horizontal link row per the NYC
# Opportunity homepage reference, not a form control. session_state holds the
# active view directly; each click sets it and reruns, same pattern as every
# other button-driven toggle in this app (self_lookup.py's factor rows,
# history.py's toggle ladder) — st.button's return value is only True on the
# exact run it was clicked, so persisted state is what survives the rerun.
NAV_ITEMS = [
    "History of My Home",
    "SCHE/DHE Enrollment Helper",
    "Deed Theft Risk Heatmap",
    "TitleWatch (internal-only)",
]
if "active_view" not in st.session_state:
    st.session_state["active_view"] = NAV_ITEMS[0]

with st.container(key="nav_bar"):
    nav_cols = st.columns(len(NAV_ITEMS))
    for col, item in zip(nav_cols, NAV_ITEMS):
        with col:
            is_active = st.session_state["active_view"] == item
            if st.button(item, key=f"nav_{item}", type="primary" if is_active else "secondary", width="stretch"):
                st.session_state["active_view"] = item
                st.rerun()

mode = st.session_state["active_view"]

if mode == "History of My Home":
    history.render()
elif mode == "SCHE/DHE Enrollment Helper":
    sche_helper.render()
elif mode == "Deed Theft Risk Heatmap":
    # Scoring only exists on this view (individual scores are TitleWatch-only,
    # never shown alongside the public aggregate map — CLAUDE.md Section 8), so
    # the explainer only makes sense to show here rather than on every tab.
    with st.expander("How scoring works"):
        how_scoring_works.render()
    public_view.render()
else:
    self_lookup.render()
