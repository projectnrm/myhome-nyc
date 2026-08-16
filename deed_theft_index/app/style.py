"""Shared visual design tokens for the Streamlit app.

Hex values pulled directly from NYC Opportunity Standard's compiled stylesheet
(nycopportunity.github.io/standard/css/documentation.css) — CLAUDE.md Section 8's
named design system reference. The npm package doesn't drop into Streamlit
(Section 8's own integration note), so per that section's instruction these are
hand-picked into a custom CSS block instead. Verified live 2026-08-15; font is
"Rubik" (--nyco-fontFace-primary/secondary in the source stylesheet).

RISK_RAMP is a single-hue sequential scale (the system's primary blue, light to
dark) for the risk_score magnitude on the public heatmap — per the dataviz
skill's color-formula, magnitude gets one hue, never a rainbow, and status colors
(red/green) are reserved for true good/bad states, not a vulnerability score.
Single-hue blue also keeps the public map from visually reading as a red/orange
"danger map" laid over specific neighborhoods — exactly the optics CLAUDE.md's
Bias & Fairness Review (Section 7) is trying to avoid. Values are the design
system's own named light->dark steps (light-3 through blue-d-1), not arbitrary
picks, but the dataviz skill's validate_palette.js needs Node, which wasn't
available in this environment — re-run it (--ordinal) once available to confirm
the ramp checks (monotone lightness, adjacent delta-L, light-end contrast).
"""

FONT_FAMILY = "'Rubik', -apple-system, BlinkMacSystemFont, sans-serif"

# Sequential ramp for risk_score (0-100, low -> high), light to dark, one hue.
RISK_RAMP = ["#e3f1fd", "#53b3fc", "#217ceb", "#004cbe", "#00369f"]

PRIMARY = "#004cbe"
NEUTRAL_BG = "#f0f6fa"
NEUTRAL_BORDER = "#c9e7fc"
NEUTRAL_INK = "#0c264d"
PAGE_BG = "#eef3f8"  # slightly deeper than NEUTRAL_BG so white cards actually pop against it

# st.container(key=...) stamps a stable ".st-key-<key>" class on its wrapper (verified
# live via getComputedStyle/page.content(), not assumed from docs) — every app module
# that wants the white-card-on-tinted-page look (color blocking per the NYC Opportunity
# homepage reference) registers its container key here so the CSS rule below and the
# actual st.container() calls in main.py/public_view.py/self_lookup.py can't drift apart.
CARD_KEYS = [
    "lookup_form_card",
    "factors_card",
    "next_steps_card",
    "additional_steps_card",
    "public_map_card",
    "public_table_card",
    "sche_form_card",
    "sche_autocheck_card",
    "sche_output_card",
    "sche_screening_card",
    "history_form_card",
    "history_summary_card",
    "history_timeline_card",
]
_card_selector = ", ".join(f".st-key-{key}" for key in CARD_KEYS)

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;700&display=swap');

/* Streamlit's own stylesheet sets font-family directly on headings and other
   elements with equal-or-higher specificity than a bare `body`/`[class*="css"]`
   rule, so it silently wins over that unless every selector here is forced —
   verified via getComputedStyle in a live browser check, not assumed. */
html, body, [class*="css"], .stApp, .stApp * {{
    font-family: {FONT_FAMILY} !important;
}}
/* Streamlit's icons (expander arrows, etc.) are ligatures that only render as
   glyphs under the Material Symbols font — the blanket rule above broke them
   into literal text like "keyboard_arrow_down" until this exception was added,
   caught via a live screenshot, not assumed safe. */
[data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded' !important;
}}
/* Fixed height + flex centering (not padding-driven sizing) so this lines up
   exactly with the toggle button beside it — verified pixel heights via
   getComputedStyle before tuning this, not eyeballed: pill was 31.3px against
   a 40px button with mismatched tops, an 8px visible offset. */
.risk-pill {{
    display: inline-flex;
    align-items: center;
    height: 2rem;
    padding: 0 0.85rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    box-sizing: border-box;
}}
.risk-pill-on {{
    background: {PRIMARY};
    color: #fff;
}}
.risk-pill-off {{
    background: {NEUTRAL_BG};
    color: {NEUTRAL_INK};
    border: 1px solid {NEUTRAL_BORDER};
}}

/* Color blocking (per NYC Opportunity homepage reference): tinted page background,
   white "card" sections for each distinct content block, brand-blue hero band for
   the page title. Mirrors the reference's white-nav / blue-hero / light-content-area
   structure, adapted to this app's single-page layout. */
.stApp {{
    background: {PAGE_BG};
}}
{_card_selector} {{
    background: #ffffff;
    border-radius: 0.75rem;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(12, 38, 66, 0.10);
}}
/* A little extra breathing room under the last factor row specifically —
   requested distinct from the shared card padding above (which already applies
   to this card too; this adds to it). */
.st-key-factors_card {{
    padding-bottom: 2rem;
}}
/* Full-bleed band, not contained to the page's padded content column (verified
   live: Streamlit's block-container carries 80px left/right padding at this
   viewport, which the shared card padding above respects on purpose — this is
   the one section deliberately breaking out of it). Classic "100vw + negative
   50vw margin" full-bleed trick, so it works regardless of the container's
   actual padding value rather than hardcoding a match to it. Inner content
   keeps its own padding so the title text isn't flush against the browser edge. */
.hero-band {{
    background: {PRIMARY};
    width: 100vw;
    position: relative;
    left: 50%;
    right: 50%;
    margin-left: -50vw;
    margin-right: -50vw;
    margin-bottom: 1rem;
}}
.hero-band-inner {{
    padding: 1.5rem 2rem;
    max-width: 1600px;
    margin: 0 auto;
}}
.hero-band h1, .hero-band p {{
    color: #ffffff !important;
}}
.hero-band p {{
    opacity: 0.9;
    margin-top: 0.25rem;
}}
.hero-band-inner {{
    display: flex;
    align-items: center;
    gap: 1.25rem;
}}
.hero-logo {{
    /* Matched to the h1's line-height (not its smaller font-size) so the mark
       reads as part of the same lockup rather than a small icon beside big
       text — the source SVG's viewBox was also cropped to its real artwork
       bounds first (it shipped with ~74% dead padding baked in, which made
       any height setting here look tiny regardless of the value). */
    height: 3.3rem;
    width: auto;
    flex-shrink: 0;
    /* Source mark is a dark/neutral wordmark, not pre-colored white — this
       recolors it to solid white so it reads correctly against the blue
       hero band without needing a separate light-mode asset. */
    filter: brightness(0) invert(1);
}}
.hero-title-group h1 {{
    margin: 0;
}}
.hero-logo-fallback {{
    font-size: 2rem;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
}}

/* Primary nav — NYC Opportunity homepage reference: a plain horizontal row of
   text links, not a control (no radio dots/borders). Built from st.button()
   (type="primary" for the active item, "secondary" for the rest) rather than
   st.radio, specifically so each item can be restyled as a link instead of a
   form control — verified live that Streamlit stamps kind="primary"/
   "secondary" on the underlying <button>, which is what these selectors key
   off of, scoped to nav_bar so it doesn't affect buttons elsewhere. */
.st-key-nav_bar {{
    background: transparent;
    box-shadow: none;
    padding: 0;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid {NEUTRAL_BORDER};
}}
.st-key-nav_bar div[data-testid="stHorizontalBlock"] {{
    gap: 0.5rem;
}}
.st-key-nav_bar button {{
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0.75rem 0.25rem !important;
    font-weight: 500 !important;
    color: #5a6b7d !important;
    width: 100%;
}}
.st-key-nav_bar button:hover {{
    color: {PRIMARY} !important;
    background: transparent !important;
}}
.st-key-nav_bar button[kind="primary"] {{
    color: {PRIMARY} !important;
    font-weight: 700 !important;
    border-bottom: 3px solid {PRIMARY} !important;
}}

/* Color-blocked card header — same brand-blue band used on the hero, scaled
   down to a card's top edge. Negative margins bleed the band to the card's
   own padded edges (st.container(key=...) cards get 1.25rem/1.5rem padding
   from CARD_KEYS above) and only the top corners keep the card's radius. */
.card-header-band {{
    background: {PRIMARY};
    color: #fff !important;
    margin: -1.25rem -1.5rem 1.25rem -1.5rem;
    padding: 0.85rem 1.5rem;
    border-radius: 0.75rem 0.75rem 0 0;
    font-weight: 700;
    font-size: 1.05rem;
}}
/* Factor-row toggle buttons (self_lookup.py) — a plain chevron, not a bordered
   button, since they're inline with a label + pill and shouldn't look like a
   separate call-to-action. Height/padding matched to .risk-pill's 2rem exactly
   (Streamlit's own button default was 40px vs. the pill's 31px — an 8px visible
   misalignment, measured, not guessed) so the two sit flush on the same row.
   Scoped to factors_card so it only affects these, not buttons elsewhere. */
.st-key-factors_card button {{
    background: transparent !important;
    border: none !important;
    color: {PRIMARY} !important;
    box-shadow: none !important;
    height: 2rem !important;
    min-height: 2rem !important;
    padding: 0 0.5rem !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
.st-key-factors_card button:hover {{
    background: {NEUTRAL_BG} !important;
}}
/* Streamlit's default hr margin (32px) reads as loose/inconsistent against the
   tighter 2rem row content beside it — tightened to a uniform 0.75rem, scoped
   to this card so the rest of the app's dividers (if any) are unaffected. */
.st-key-factors_card hr {{
    margin: 0.75rem 0 !important;
}}
</style>
"""


def risk_color(score: float, max_score: int = 100) -> list:
    """Map a 0-100 risk_score to an [r, g, b] triple from RISK_RAMP, for pydeck."""
    steps = len(RISK_RAMP)
    idx = min(max(int((score / max_score) * steps), 0), steps - 1) if max_score else 0
    hex_color = RISK_RAMP[idx].lstrip("#")
    return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]
