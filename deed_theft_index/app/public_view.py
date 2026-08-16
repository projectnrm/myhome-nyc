"""Public aggregate view — CLAUDE.md Section 8: block/census-tract heatmap only,
never individual addresses or map pins. This boundary is enforced visually here,
not just by policy, so don't add an address-level layer to this view.
"""
import html as html_lib

import duckdb
import pandas as pd
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

from deed_theft_index.app.style import NEUTRAL_BORDER, NEUTRAL_INK, PRIMARY, risk_color
from deed_theft_index.config import (
    DUCKDB_PATH,
    FEATURE_SHORT_LABELS,
    NEIGHBORHOOD_CENTROIDS,
    NEIGHBORHOODS,
    SCORE_WEIGHTS,
    SCORED_FEATURES,
)

# Built from the same source-of-truth used by "How scoring works" (config.py),
# not hand-typed, so this can't silently drift from what score.py actually computes.
_MAX_POSSIBLE_SCORE = sum(SCORE_WEIGHTS[f] for f in SCORED_FEATURES)
_FACTOR_LIST = ", ".join(FEATURE_SHORT_LABELS[f].lower() for f in SCORED_FEATURES)
SCORE_TOOLTIP_TEXT = (
    f"Average of each property's weighted risk score (0-{_MAX_POSSIBLE_SCORE}) across the "
    f"neighborhood, based on {len(SCORED_FEATURES)} factors: {_FACTOR_LIST}. Not a probability "
    f"of theft — see “How scoring works” above for details."
)


def _searchable_table_html(table: pd.DataFrame) -> str:
    """A self-contained HTML/JS table with instant, per-keystroke client-side
    filtering — st.text_input only commits on Enter/blur (verified live), so a
    truly "as you type" search needs to happen in the browser, not a Streamlit
    rerun. Runs in components.html's sandboxed iframe, which doesn't inherit the
    parent page's CSS, so the handful of tokens used here are duplicated inline
    rather than relying on style.CSS.
    """
    rows_html = []
    for _, row in table.iterrows():
        name = html_lib.escape(str(row["Neighborhood"]))
        name_key = html_lib.escape(str(row["Neighborhood"]).lower())
        score = f'{row["Avg. Risk Score"]:.1f}'
        count = int(row["Properties Scored"])
        rows_html.append(
            f'<tr data-name="{name_key}">'
            f'<td>{name}</td><td class="num">{score}</td><td class="num">{count}</td>'
            f"</tr>"
        )

    # components.html() embeds this in a FIXED-height iframe (the height passed
    # from Python at render time) — filtering rows client-side with display:none
    # shrinks the table correctly, but the iframe itself can't auto-shrink to
    # match (its resize protocol is only wired up for the full custom-component
    # framework, not this simpler static-HTML helper — confirmed live: posting
    # the "streamlit:setFrameHeight" message Streamlit's own components use had
    # no effect here). Rather than leave a large empty gap below a short result
    # set, only the ROW LIST scrolls within a fixed max-height; the search box
    # stays put above it and the outer iframe height stays constant regardless
    # of how many rows match.
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
      <input id="nbhd-search" type="text" placeholder="Start typing a neighborhood name (e.g. &quot;Harlem&quot;)"
        style="width:100%; box-sizing:border-box; padding:0.6rem 0.85rem; margin-bottom:0.75rem;
               border:1px solid {NEUTRAL_BORDER}; border-radius:0.5rem; font-size:0.95rem;
               color:{NEUTRAL_INK}; background:{'#f0f6fa'};">
      <div style="max-height:260px; overflow-y:auto;">
        <table style="width:100%; border-collapse:collapse; font-size:0.9rem; color:{NEUTRAL_INK};">
          <thead>
            <tr style="border-bottom:1px solid {NEUTRAL_BORDER}; text-align:left; color:#5a6b7d;">
              <th style="padding:0.5rem 0.25rem; font-weight:500; position:sticky; top:0; background:#fff;">Neighborhood</th>
              <th style="padding:0.5rem 0.25rem; font-weight:500; position:sticky; top:0; background:#fff;" class="num">
                <span class="tooltip-wrap">Avg. Risk Score <span class="info-icon">&#9432;</span>
                  <span class="tooltip-text">{html_lib.escape(SCORE_TOOLTIP_TEXT)}</span>
                </span>
              </th>
              <th style="padding:0.5rem 0.25rem; font-weight:500; position:sticky; top:0; background:#fff;" class="num">Properties Scored</th>
            </tr>
          </thead>
          <tbody id="nbhd-rows">{"".join(rows_html)}</tbody>
        </table>
        <div id="nbhd-empty" style="display:none; padding:0.75rem 0.25rem; color:#5a6b7d;">
          No neighborhoods match.
        </div>
      </div>
    </div>
    <style>
      td, tr {{ border-bottom: 1px solid {NEUTRAL_BORDER}; }}
      td {{ padding: 0.5rem 0.25rem; }}
      .num {{ text-align: right; }}
      #nbhd-search:focus {{ outline: 2px solid {PRIMARY}; outline-offset: -1px; }}
      /* Tooltip drops DOWNWARD (top:100%), not upward — the header is
         position:sticky inside a div with overflow-y:auto (for the scrolling
         row list), which clips anything positioned above the sticky header's
         own box. Below it stays within the scroll container's visible area.
         Verified live: an upward-opening version was invisible, clipped by
         the parent's overflow. */
      .tooltip-wrap {{ position: relative; cursor: help; }}
      .info-icon {{ color: #5a6b7d; }}
      .tooltip-text {{
        visibility: hidden;
        opacity: 0;
        position: absolute;
        top: 100%;
        right: 0;
        margin-top: 6px;
        background: {NEUTRAL_INK};
        color: #fff;
        padding: 0.6rem 0.75rem;
        border-radius: 0.5rem;
        font-size: 0.75rem;
        font-weight: 400;
        text-align: left;
        line-height: 1.4;
        width: 240px;
        white-space: normal;
        transition: opacity 0.15s ease;
        z-index: 5;
      }}
      .tooltip-wrap:hover .tooltip-text {{ visibility: visible; opacity: 1; }}
    </style>
    <script>
      document.getElementById('nbhd-search').addEventListener('input', function (e) {{
        var q = e.target.value.toLowerCase();
        var rows = document.querySelectorAll('#nbhd-rows tr');
        var anyVisible = false;
        rows.forEach(function (row) {{
          var match = row.getAttribute('data-name').indexOf(q) !== -1;
          row.style.display = match ? '' : 'none';
          if (match) anyVisible = true;
        }});
        document.getElementById('nbhd-empty').style.display = anyVisible ? 'none' : 'block';
      }});
    </script>
    """


def _neighborhood_aggregate(cd_agg: pd.DataFrame) -> pd.DataFrame:
    """Explode CD-level aggregates into neighborhood-level rows, weighted by
    property count. Several neighborhoods span multiple community districts
    (e.g. South Bronx = CD1-4) — a plain mean-of-CDs would misweight those
    relative to single-CD neighborhoods.
    """
    rows = []
    for name, cds in NEIGHBORHOODS.items():
        subset = cd_agg[cd_agg["community_district"].isin(cds)]
        total_n = subset["n_properties"].sum()
        if subset.empty or total_n == 0:
            continue
        weighted_avg = (subset["avg_risk_score"] * subset["n_properties"]).sum() / total_n
        rows.append({"neighborhood": name, "avg_risk_score": weighted_avg, "n_properties": int(total_n)})
    return pd.DataFrame(rows)


def render() -> None:
    st.subheader("Deed Theft Risk Heatmap")
    st.caption(
        "Aggregated by neighborhood — individual property scores are internal, "
        "staff-only data (see TitleWatch), never shown at the address level here."
    )

    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        cd_agg = con.execute("""
            SELECT cd AS community_district, avg(risk_score) AS avg_risk_score, count(*) AS n_properties
            FROM properties
            GROUP BY cd
        """).fetchdf()
    except duckdb.CatalogException:
        st.info("No scored data yet — run `python scripts/build.py` after ingestion.")
        return
    finally:
        con.close()

    agg = _neighborhood_aggregate(cd_agg)
    if agg.empty:
        st.info("No scored properties fall within the bounded neighborhood set yet.")
        return

    agg["lat"] = agg["neighborhood"].map(lambda n: NEIGHBORHOOD_CENTROIDS[n][0])
    agg["lon"] = agg["neighborhood"].map(lambda n: NEIGHBORHOOD_CENTROIDS[n][1])
    agg["color"] = agg["avg_risk_score"].apply(risk_color)
    agg["radius"] = 400 + (agg["avg_risk_score"] / 100) * 900

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=agg,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.75,
    )
    view_state = pdk.ViewState(latitude=40.72, longitude=-73.92, zoom=9.6)
    with st.container(key="public_map_card"):
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{neighborhood}\nAvg. risk score: {avg_risk_score}\nProperties scored: {n_properties}"},
        ))
        st.caption(
            "Darker and larger circles indicate a higher average risk score across the "
            "neighborhood — never any single address."
        )

    with st.container(key="public_table_card"):
        st.markdown('<div class="card-header-band">Search Neighborhoods</div>', unsafe_allow_html=True)
        table = (
            agg[["neighborhood", "avg_risk_score", "n_properties"]]
            .sort_values("avg_risk_score", ascending=False)
            .rename(columns={
                "neighborhood": "Neighborhood",
                "avg_risk_score": "Avg. Risk Score",
                "n_properties": "Properties Scored",
            })
        )
        # Fixed regardless of row count now — the row list scrolls internally
        # (max-height 260px in _searchable_table_html) rather than the iframe
        # growing/shrinking with it, so this height doesn't need to track len(table).
        components.html(_searchable_table_html(table), height=340)
