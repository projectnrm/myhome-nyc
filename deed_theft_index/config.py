"""Central config: dataset IDs, scope, and scoring weights — all sourced from CLAUDE.md.

Keep this the single source of truth so ingest/pipeline/app modules never hardcode
a Socrata ID or a point value. If CLAUDE.md's decisions change, update here first.
"""
import os

SOCRATA_BASE_URL = "https://data.cityofnewyork.us/resource/{dataset_id}.json"

# CLAUDE.md Section 4 — Data Sources. IDs marked "verify" were not confirmed in the
# planning session; hit the Socrata discovery API or the portal before relying on them.
DATASETS = {
    "acris_master": "bnx9-e6tj",  # verify: confirm not a community copy
    "acris_legals": "8h5j-fqxa",
    "acris_parties": "636b-3b5g",
    "acris_references": "pwkr-dpni",
    "pluto": "64uk-42ks",
    "property_valuation_assessment": "8y4t-faws",
    "rnopv": "8vgb-zm6e",
    "property_exemption_detail": "muvi-b6kx",
    "tax_lien_sale_lists": "9rz4-mjek",
    "rolling_calendar_sales": "usep-8jbt",
    "annualized_calendar_sales": "w2pb-icbu",
    # 311 is cut for the hackathon (CLAUDE.md Section 3a) — kept for the v2 post-hackathon build.
    "service_requests_311": "erm2-nwe9",  # verify
}

# CLAUDE.md Section 3a — bounded neighborhood set for the hackathon, not full-city.
# Filter via PLUTO community district (cd), not fuzzy neighborhood-name matching.
#
# PLUTO's `cd` field is borough digit (1=Manhattan, 2=Bronx, 3=Brooklyn, 4=Queens,
# 5=Staten Island) + 2-digit community district number, e.g. Brooklyn CD3 = 303.
# Some neighborhoods span multiple CDs — filter on membership in the tuple, not equality.
# Verified against NYC Planning community district profiles (communityprofiles.planning.nyc.gov).
NEIGHBORHOODS = {
    "Bedford-Stuyvesant": (303,),           # Brooklyn CD3
    "Crown Heights": (308, 309),           # Brooklyn CD8 (North) + CD9 (South)
    "East New York": (305,),               # Brooklyn CD5
    "South Bronx": (201, 202, 203, 204),   # Bronx CD1 Mott Haven - CD4 Highbridge/Concourse
    "Harlem": (109, 110, 111),             # Manhattan CD9 West - CD10 Central - CD11 East
    "Southeast Queens": (412, 413),        # Queens CD12 Jamaica + CD13 Queens Village
    "Flatbush": (314,),                    # Brooklyn CD14
    "Upper West Side": (107,),             # Manhattan CD7
    "Astoria": (401,),                     # Queens CD1
    "Jamaica": (412,),                     # Queens CD12 — overlaps Southeast Queens by design
    "Financial District": (101,),          # Manhattan CD1
    "Flushing": (407,),                    # Queens CD7
}

# Flattened, de-duped PLUTO `cd` codes across all bounded neighborhoods — the actual
# SoQL filter value for ingest/pluto.py. Recomputed from NEIGHBORHOODS so the two
# never drift apart.
ALL_COMMUNITY_DISTRICTS = sorted({cd for cds in NEIGHBORHOODS.values() for cd in cds})

# Approximate neighborhood center points (lat, lon) for the public heatmap
# (app/public_view.py) — plotting at neighborhood centroids rather than pulling in
# a full community-district GeoJSON boundary file, which is out of scope for the
# hackathon. Standard, widely-published NYC neighborhood coordinates, not looked
# up per-session.
NEIGHBORHOOD_CENTROIDS = {
    "Bedford-Stuyvesant": (40.6872, -73.9418),
    "Crown Heights": (40.6694, -73.9422),
    "East New York": (40.6660, -73.8807),
    "South Bronx": (40.8115, -73.9264),
    "Harlem": (40.8116, -73.9465),
    "Southeast Queens": (40.6870, -73.7818),
    "Flatbush": (40.6501, -73.9596),
    "Upper West Side": (40.7870, -73.9754),
    "Astoria": (40.7720, -73.9302),
    "Jamaica": (40.7027, -73.7890),
    "Financial District": (40.7075, -74.0113),
    "Flushing": (40.7654, -73.8318),
}

# CLAUDE.md Section 3a — 5 of 6 scored features in scope for the hackathon.
# "exemption_lapse" is cut first if time is short (most build-complex, worth least).
SCORED_FEATURES = [
    "free_and_clear",
    "senior_disabled_exemption",
    "long_tenure_no_deed_activity",
    "individually_owned",
    "tax_lien_history",
]
CUT_FEATURES = ["exemption_lapse"]

# CLAUDE.md Section 7 — v1 Weighting (draft, pending fair-housing/civil-rights legal review).
# Two pillars, 0-100 total. Neighborhood appreciation is intentionally NOT a scored input —
# see CLAUDE.md's Bias & Fairness Review before adding any geography-derived feature here.
SCORE_WEIGHTS = {
    "free_and_clear": 25,               # Ownership Vulnerability
    "senior_disabled_exemption": 20,    # Ownership Vulnerability
    "long_tenure_no_deed_activity": 20, # Ownership Vulnerability
    "individually_owned": 10,           # Ownership Vulnerability
    "tax_lien_history": 15,             # Financial Distress
    "exemption_lapse": 10,              # Financial Distress — cut for hackathon, kept for v2
}

# Display copy for the "How Scoring Works" explainer (app/how_scoring_works.py) and
# self-lookup factor list (app/self_lookup.py) — one place so both stay in sync with
# SCORE_WEIGHTS and can't silently drift from CLAUDE.md Section 7's feature defs.
FEATURE_LABELS = {
    "free_and_clear": "No active mortgage on file (free and clear)",
    "senior_disabled_exemption": "Senior/disabled (SCHE/DHE) exemption on file",
    "long_tenure_no_deed_activity": "10+ years since last recorded deed activity",
    "individually_owned": "Individually owned (not LLC/corporate)",
    "tax_lien_history": "Active or historical tax lien",
    "exemption_lapse": "Senior/disabled exemption lapse pattern",
}
FEATURE_RATIONALE = {
    "free_and_clear": "An active mortgage means a lender routinely monitors the title; once paid off, the homeowner becomes the sole line of defense.",
    "senior_disabled_exemption": "Age and disability are the most consistently cited vulnerability characteristics in DA/AG/legal-aid guidance.",
    "long_tenure_no_deed_activity": "Long-held, unchallenged chains of title are where heirs'-property and probate-fraud cases concentrate.",
    "individually_owned": "Keeps the model focused on individual homeowners rather than professionally-managed, LLC-owned properties.",
    "tax_lien_history": "Financial distress is a documented precursor to foreclosure-rescue and predatory-purchase schemes.",
    "exemption_lapse": "A lapsed senior exemption can signal owner death, incapacity, or an unresolved estate — the heirs'-property vector again.",
}
FEATURE_CAVEATS = {
    "free_and_clear": "Satisfaction filings can lag real-world payoff — a data-driven estimate, not a certainty.",
    "senior_disabled_exemption": "Only captures enrolled seniors. “Not on file” means missing data, never “confirmed not a senior.”",
    "long_tenure_no_deed_activity": "Can't distinguish an occupied aging owner from an informally inherited, absentee-owned home — both high-risk, different reasons.",
    "individually_owned": "A legitimate estate-planning trust can pattern-match as LLC-like even though the real beneficiary is an individual.",
    "tax_lien_history": "A binary flag for now — doesn't yet distinguish real distress from a short administrative gap.",
    "exemption_lapse": "Cut from this hackathon build (needs multi-year exemption history); shown here for transparency about what isn't scored yet.",
}

# Self-lookup pill text (present, absent) per factor — deliberately NOT a uniform
# "On file"/"Not on file" for every row. That framing is only semantically correct
# for the two factors that are genuinely a record-presence question, where absence
# is ambiguous (a real absence vs. a data gap — see FEATURE_CAVEATS above, esp. the
# SCHE-enrollment-gap point, which is exactly why those two keep the neutral
# "Not on file" wording). The other three are computed classifications from data
# already in hand (not "did we find a record"), so they get more specific, definite
# language instead — "On file" read as a mismatched metaphor for e.g. tenure length.
FEATURE_PILL_TEXT = {
    "free_and_clear": ("Free and clear", "Active mortgage"),
    "senior_disabled_exemption": ("Enrolled", "Not on file"),
    "long_tenure_no_deed_activity": ("No activity in 10+ yrs", "Recent deed activity"),
    "individually_owned": ("Individually owned", "LLC / corporate"),
    "tax_lien_history": ("Lien on file", "Not on file"),
}

# Short, neutral topic labels for the self-lookup accordion headers (app/self_lookup.py,
# one per factor as its own collapsed-by-default st.expander, mirroring nyc.gov/deedfraud's
# own FAQ accordion pattern). Deliberately distinct from FEATURE_LABELS above: those are
# full descriptive sentences already phrased toward the "present" state (e.g. "No active
# mortgage on file (free and clear)"), which reads redundant stacked next to a
# FEATURE_PILL_TEXT status pill in a header. These are just the topic, status goes in the pill.
FEATURE_SHORT_LABELS = {
    "free_and_clear": "Mortgage status",
    "senior_disabled_exemption": "Senior/disabled exemption",
    "long_tenure_no_deed_activity": "Deed activity",
    "individually_owned": "Ownership type",
    "tax_lien_history": "Tax lien history",
}

# Plain-English explanations, shared by self-lookup (app/self_lookup.py) and "How
# Scoring Works" (app/how_scoring_works.py) — written for a general audience,
# including seniors who are one of the groups this tool is meant to help. Second
# person, no jargon ("documented risk factors," "the model," "data-driven
# estimate"), one short warm paragraph combining what FEATURE_RATIONALE/CAVEATS
# say separately and technically. FEATURE_RATIONALE/FEATURE_CAVEATS above are kept
# around as the source-of-truth methodological notes these are written from, and
# for the one cut feature (exemption_lapse) that has no plain-English version yet.
FEATURE_PLAIN_EXPLANATION = {
    "free_and_clear": (
        "When you have a mortgage, your bank keeps a close eye on your home's "
        "paperwork as part of protecting their loan. Once that mortgage is paid "
        "off, no one is automatically watching for you anymore — which is part "
        "of why homes that are fully paid off are often targeted. (Records can "
        "take a little while to update after a payoff, so this isn't always "
        "perfectly current.)"
    ),
    "senior_disabled_exemption": (
        "Older adults and people with disabilities are common targets for "
        "property scams, sometimes because they're more isolated or it's harder "
        "to keep up with paperwork. If you have a senior or disability property "
        "tax break on file, it's worth taking extra precautions. And if you "
        "don't see one here, that doesn't necessarily mean you're in the clear — "
        "plenty of people who qualify never signed up for it."
    ),
    "long_tenure_no_deed_activity": (
        "If no new paperwork has been filed on this property in over 10 years, "
        "it may have been passed down in the family without going through a "
        "will or the courts. That can leave a confusing paper trail, which "
        "makes it easier for someone to slip in a fake document without anyone "
        "noticing. This matters whether you've lived there all along or "
        "inherited it from a relative."
    ),
    "individually_owned": (
        "This home is owned by a person, not a business. Businesses often have "
        "staff or lawyers looking out for their properties — as an individual "
        "owner, keeping an eye on your home's paperwork is mostly up to you (or "
        "someone you trust)."
    ),
    "tax_lien_history": (
        "A tax lien means there are unpaid property taxes on record. People who "
        "are behind on payments are sometimes targeted by scammers offering a "
        "quick fix — be very cautious of anyone who contacts you out of the "
        "blue promising to help with a lien or stop a foreclosure."
    ),
}

LONG_TENURE_YEARS_THRESHOLD = 10  # CLAUDE.md Section 7: "to be validated statistically"

# Risk tier cutoffs for self-lookup's dynamic protective-action guidance
# (app/self_lookup.py) — PLACEHOLDER values, same status as LONG_TENURE_YEARS_THRESHOLD
# above: not calibrated against a real score distribution, since ingestion hasn't run
# yet (NYC Open Data maintenance window as of this build). Revisit once real scores
# exist — e.g. set "High" near the top decile rather than an arbitrary round number.
# Ordered highest-to-lowest; risk_tier() returns the first threshold the score clears.
RISK_TIERS = [
    ("High", 60),
    ("Elevated", 40),
    ("Moderate", 20),
    ("Low", 0),
]


def risk_tier(score: float) -> str:
    for label, minimum in RISK_TIERS:
        if score >= minimum:
            return label
    return RISK_TIERS[-1][0]


# Protective actions per scored feature, shown on self-lookup only for factors
# actually present on the property being looked up, ordered by SCORE_WEIGHTS
# (highest-weight factor first) so guidance responds to *which* factors are
# driving the property's risk, not a generic checklist. Deliberately concrete
# and actionable (not just "be careful") — grounded in the same DA/AG/legal-aid
# guidance FEATURE_RATIONALE already cites. "individually_owned" has no entry:
# per Section 7 it's a scope filter, not an actionable vulnerability on its own.
FEATURE_PROTECTIVE_ACTIONS = {
    "free_and_clear": (
        "No lender is monitoring this title anymore — that's what an active mortgage "
        "would normally do. Registering for the city's NRD alert program is the closest "
        "replacement, and an annual manual ACRIS check matters more here than for a "
        "mortgaged property."
    ),
    "senior_disabled_exemption": (
        "Identify a trusted family member, elder-law attorney, or legal-aid caseworker "
        "(e.g. Build Up Justice NYC) who can help watch for scams or undue-influence "
        "attempts targeting the senior/disabled homeowner."
    ),
    "long_tenure_no_deed_activity": (
        "If this property was informally inherited (no will filed, no probate "
        "completed), an unclear chain of title is exactly what makes a forged deed "
        "hard to challenge — consult a legal-aid probate clinic to formalize ownership."
    ),
    "tax_lien_history": (
        "Financial distress is actively targeted by \"foreclosure rescue\" scams — never "
        "sign over a deed to anyone promising to pay off a lien or stop a foreclosure. "
        "Contact a HUD-approved housing counselor or HPD's foreclosure prevention "
        "program instead."
    ),
}

# ACRIS Master/Legals/Parties/References are citywide, multi-decade datasets with no
# BBL/community-district field to filter on directly (unlike PLUTO) — a full pull is
# far more data than a 2-day hackathon needs. Bound Master by document_date instead;
# comfortably covers LONG_TENURE_YEARS_THRESHOLD (10 yrs) with margin, since all we
# need is "did any deed activity happen in the last N years" for that feature.
ACRIS_YEARS_LOOKBACK = 15

# ACRIS `doc_type` codes by category, used to classify filings for the free-and-clear
# and long-tenure features (Section 7). doc_type holds short DOF codes (e.g. "DEED",
# "MTGE", "SAT"), not full words — a naive ILIKE '%SATISFACTION%' match silently never
# fires. Based on DOF's published Document Control Types reference; NOT yet verified
# against a live pull (NYC Open Data was down for scheduled maintenance during this
# build session) — cross-check against the "ACRIS - Document Control Types" reference
# dataset once available, and correct these tuples if the live codes differ.
ACRIS_DEED_DOC_TYPES = ("DEED", "DEEDO")
ACRIS_MORTGAGE_DOC_TYPES = ("MTGE", "AGMT")
ACRIS_SATISFACTION_DOC_TYPES = ("SAT", "SATM")

# SCHE/DHE exemption codes — confirmed live against the "Exemption Classification
# Codes" reference dataset (myn9-hwsy): 1015 = "SENIOR CITIZEN HOMEOWNER", 1019 =
# "DISABLED HOMEOWNER". Verified 2026-08-16, not guessed — unlike the ACRIS doc_type
# tuples above, which still need the same live cross-check.
SCHE_EXEMPTION_CODE = "1015"
DHE_EXEMPTION_CODE = "1019"

# Full ACRIS document-type reference, confirmed live against the "ACRIS - Document
# Control Codes" dataset (7isb-wh4c) 2026-08-16 — used by History of My Home
# (app/history.py) to render a plain-language timeline instead of raw doc_type
# codes. Narrative tier gets a human sentence template; everything else (UCC
# filings, tax-lien administrivia, corrections, etc.) falls back to a generic
# administrative-tier label rather than hand-classifying all ~126 known codes.
# {template} is filled with the bundled record's parties/date where relevant.
DOC_TYPE_NARRATIVE = {
    "DEED": "Ownership transferred by deed.",
    "DEEDO": "Ownership transferred by deed.",
    "DEED, LE": "Ownership transferred by deed, with a life estate retained by the seller.",
    "DEED, TS": "Ownership transferred by a timeshare deed.",
    "TODD": "A Transfer on Death Deed was filed, naming a beneficiary to inherit the property automatically.",
    "RTOD": "A previously filed Transfer on Death Deed was revoked.",
    "WILL": "A certified copy of a will was recorded against this property.",
    "MTGE": "A new mortgage was recorded.",
    "CMTG": "A new collateral mortgage was recorded.",
    "SAT": "An existing mortgage was satisfied (paid off).",
    "PSAT": "Part of an existing mortgage was satisfied (paid off).",
    "ASST": "The mortgage was assigned to a new lender — this is a lender-side servicing change, not a change in who owns the home.",
    "M&CON": "Multiple mortgages on the property were consolidated.",
}
# Doc types that ARE narrative-worthy but should only ever appear grouped with a
# same-day deed/mortgage (never as their own timeline entry) — CLAUDE.md Section 12's
# "bundle same-day/nearby-date records" instruction, made explicit rather than left
# to bundling logic alone to infer.
DOC_TYPE_NEVER_STANDALONE = ("RPTT", "RPTT&RET", "RETT")

DATA_RAW_DIR = "data/raw"
DATA_PROCESSED_DIR = "data/processed"

# data/processed/*.duckdb is gitignored (Section 9: "pulled/derived data, not
# committed") — correct for local dev, but it means a fresh clone (e.g. a
# Streamlit Community Cloud deploy) has no database at all. data/deploy/ carries
# one intentional exception: a trimmed, size-capped (<100MB, GitHub's non-LFS
# limit) copy with only the 3 tables the app actually queries (properties,
# filings_joined, sales_history — see the deploy note in README for how it's
# built), committed on purpose. Prefer the full local file when it exists
# (accurate local dev/demo data); fall back to the committed trimmed copy when
# it doesn't (a fresh deploy) — no environment variable or manual config needed
# either way.
_FULL_DUCKDB_PATH = f"{DATA_PROCESSED_DIR}/deed_theft_index.duckdb"
_DEPLOY_DUCKDB_PATH = "data/deploy/deed_theft_index.duckdb"
DUCKDB_PATH = _FULL_DUCKDB_PATH if os.path.exists(_FULL_DUCKDB_PATH) else _DEPLOY_DUCKDB_PATH
