""""How Scoring Works" explainer — CLAUDE.md Section 7: presents the scorecard as
"risk factors present" with contributing factors listed, never a bare number or a
probability of theft, and surfaces the caveats/bias notes Section 7's Bias &
Fairness Review explicitly says must not be hidden from the UI (esp. the
SCHE-enrollment-gap and neighborhood-appreciation-exclusion points).

Copy is the same plain-English voice as self_lookup.py's factor rows (config.
FEATURE_PLAIN_EXPLANATION) rather than the more clinical FEATURE_RATIONALE/
FEATURE_CAVEATS pairing this used originally — this page is public-facing and
read by the same general audience (including seniors) self-lookup is written
for, so there's no real reason for it to read more technically just because
it's the "under the hood" page. FEATURE_RATIONALE/FEATURE_CAVEATS remain the
methodological source-of-truth those explanations are written from, and are
still used for exemption_lapse below, the one cut feature with no plain-English
version yet.
"""
import streamlit as st

from deed_theft_index.config import (
    CUT_FEATURES,
    FEATURE_CAVEATS,
    FEATURE_LABELS,
    FEATURE_PLAIN_EXPLANATION,
    SCORE_WEIGHTS,
    SCORED_FEATURES,
)


def render() -> None:
    st.markdown(
        "This is a **vulnerability index**, not a fraud-detection tool — there's no "
        "list of confirmed deed theft cases anywhere to check our guesses against. "
        "Instead, every property earns points for a handful of documented risk "
        "factors — things prosecutors and legal-aid groups actually see show up "
        "again and again in real cases. A high score means several of those factors "
        "are present on this property, not a prediction that something bad is "
        "about to happen."
    )

    max_possible = sum(SCORE_WEIGHTS[f] for f in SCORED_FEATURES)
    st.markdown(f"**What we check** (out of {max_possible} possible points):")

    for feature in SCORED_FEATURES:
        points = SCORE_WEIGHTS[feature]
        st.markdown(f"**{FEATURE_LABELS[feature]} — {points} pts**")
        st.caption(FEATURE_PLAIN_EXPLANATION[feature])

    if CUT_FEATURES:
        st.markdown("**Not part of the score yet:**")
        for feature in CUT_FEATURES:
            st.markdown(f"- {FEATURE_LABELS[feature]} ({SCORE_WEIGHTS[feature]} pts if added)")
            st.caption(FEATURE_CAVEATS[feature])

    st.markdown("**What we leave out on purpose:**")
    st.markdown(
        "- **We never score how fast home prices are rising in your neighborhood**, "
        "even though it's a real warning sign. The problem is that deed theft is "
        "already concentrated in historically Black neighborhoods where prices are "
        "climbing fastest — so scoring that in would mean every home in those areas "
        "gets bumped up, regardless of that specific owner's actual situation. That's "
        "not a risk score anymore, that's just a map of where Black homeowners live, "
        "which is exactly the kind of thing fair housing law exists to prevent. We "
        "show it for context, never as something that raises your score."
    )
    st.markdown(
        "- **Not seeing a risk factor here doesn't mean you're safe.** A senior or "
        "disability tax break, for instance, only shows up if someone's actually "
        "enrolled in it — and we know plenty of people who qualify never sign up. So "
        "someone eligible-but-not-enrolled looks identical to someone the factor "
        "just doesn't apply to. That's why you'll see \"Not on file\" instead of a "
        "checkmark or an X — a checkmark would wrongly imply we'd confirmed you're "
        "in the clear."
    )
