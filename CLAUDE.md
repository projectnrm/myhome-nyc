# NYC Deed Theft Risk Index — Project Context

> **This is CLAUDE.md.** Claude Code loads this automatically at the start of every session in this repo — it's the *why* behind the product and data decisions, not just a spec. Update it as decisions change; treat it as living project memory.

> **Starting a build session?** Read Section 3a (MVP Cut-List) and Section 9 (Hackathon Stack) first — those are the action-critical sections for what to actually build this weekend, and Section 3a now includes History of My Home and the SCHE/DHE Helper as in-scope (see Sections 12–13 for full design detail on each). Section 8's internal-SSO risk-access architecture and Section 14's other product ideas remain post-hackathon exploration, not build targets. Everything else is supporting context: reference it as needed rather than reading linearly.

---

## 1. Project Summary

A public-facing web app that scores/ranks NYC residential properties by estimated **vulnerability to deed theft** (not confirmed fraud — no such labeled dataset exists), using NYC Open Data. The goal is prevention and outreach, not detection of fraud that has already occurred (that's the job of the city's existing Mayor's Office of Deed Theft Prevention and the ACRIS Recorded Document Notification / NRD alert program, which this project complements rather than duplicates).

**Hackathon scope note:** this is a 2-day build. v1 targets the core NYC Open Data pipeline (Sections 4–7) plus Geoclient from Section 11. Census ACS, HUD/USPS vacancy data, and OpenCorporates are real, well-researched enhancements but are **not** part of the hackathon build — they're demo talking points for "where this goes next," not implementation targets. Don't let their access/cost complications block anything in the 48-hour window.

## 2. Goals / Non-Goals

**Goals**
- Build a transparent, explainable risk score per property (BBL) using public data.
- Surface the score in a way that helps homeowners, heirs, and advocates take protective action.
- Optionally flag newly recorded deeds that show transaction-level fraud red flags.

**Non-Goals**
- Not a fraud-detection tool with statistical guarantees — there's no ground-truth label set of confirmed deed theft cases at scale, so scores are a **vulnerability index**, not a calibrated probability.
- Not a replacement for the city's NRD alert system — point users toward it.
- Not a public, scrapable, address-ranked "most vulnerable homes" leaderboard — see Section 6 (dual-use risk).

## 3. Key Constraint: No Labeled Ground Truth

Confirmed deed theft cases live in DA prosecutions, AG referrals, and legal-aid casework (e.g. Build Up Justice NYC) — not in any open dataset. This rules out standard supervised fraud-probability modeling. Two model types instead:

1. **v1 — Weighted risk scorecard** (property-level, uses only public data, fully explainable). Ship this first.
2. **v2 — Transaction anomaly scoring** (deed-level, flags unusual *new* filings independent of any "theft" label). Build after v1, as a second surface.

## 3a. MVP Cut-List (Hackathon)

**In scope:**
- Bounded neighborhood set, not full city: the ~10-15 neighborhoods already used in the mockup (Bedford-Stuyvesant, Crown Heights, East New York, South Bronx, Harlem, Southeast Queens, Flatbush, Upper West Side, Astoria, Jamaica, Financial District, Flushing), spanning all five boroughs. Filter via PLUTO community district, not fuzzy neighborhood-name matching.
- 5 of the 6 scored features: free-and-clear, senior/disabled exemption, 10+ year tenure, individually-owned (simple LLC/INC/CORP suffix regex, no trust-detection edge case), tax lien history.
- Core pipeline: ACRIS Master + Legals + Parties + References, PLUTO, Property Exemption Detail (most recent year only), Tax Lien Sale Lists.
- Geoclient for self-lookup address resolution only.
- Public heatmap + self-lookup UI exactly as mocked, including UI-pattern-only gating.
- Explicit "co-ops not covered yet" messaging — resolves the co-op scope gap without a second model.
- **History of My Home (Section 12) — promoted to in-scope.** Reuses the same ACRIS ingestion above; the only pipeline difference is querying full history per BBL instead of the collapsed-most-recent view. Needs Rolling Sales (see below) for price matching. Net-new build: plain-language doc-type mapping, same-day record bundling, the toggle-ladder timeline UI.
- **SCHE/DHE Enrollment Helper (Section 13) — promoted to in-scope, the cheaper of the two additions.** Auto-check reuses PLUTO, ACRIS tenure logic, and Property Exemption Detail — all already in scope above for the main scorer. Net-new build: the 3-question self-report form and output logic, no persistence layer needed since answers were never meant to be stored. **Simplification for the hackathon:** skip computing a real next-renewal date (would need the same multi-year Property Exemption Detail pull already cut below as the main scorer's exemption-lapse feature) — state the 24-month renewal cadence generically instead.
- **Rolling/Annualized Sales — now in scope, but only for History of My Home's price matching.** Its other originally-scoped use, neighborhood-pressure scoring context, remains cut below; this is a narrower, different use of the same dataset.
- **Build order if time gets tight:** main scorer + heatmap first (the anchor deliverable — already built and working as of this session), then SCHE/DHE Helper (cheapest add), then History of My Home.

**Cut (demo talking points, not build tasks):**
- Exemption non-renewal/lapse pattern (6th scored feature) — most build-complex of the six, worth only 10/100 points. First cut if time is short; ties directly to the probate/heirs'-property fairness story, good to narrate even if unbuilt.
- 311 ingestion — never made it into the actual scored formula (Section 7), only ever a corroborating signal. Cutting it removes a data source and the hardest geocoding step for zero loss to the score. Worth naming explicitly at the demo: 311's illegal-conversion/vacancy complaints were also functioning as an unofficial stand-in for a real vacancy signal, so cutting 311 alongside the access-gated HUD/USPS data (Section 11) means the hackathon build has no vacancy signal at all, not a reduced one. A deliberate, defensible cut — but a cut worth naming, not one that just quietly disappeared.
- Census ACS neighborhood context — already scoped as display-only, never-scored (Section 7 bias review), still cut.
- Rolling Sales as *scoring* context (neighborhood-pressure pillar) — still cut; only its use for History of My Home's price matching is in scope now (see above).
- v2 anomaly detection, HUD vacancy data, OpenCorporates — already deferred.
- Internal-SSO risk lookup (Section 8), real self-lookup authentication, bulk-export protections, fair-housing legal review — genuine future-work items, not hackathon tasks. The hackathon risk lookup stays UI-pattern-gated per Section 9, not real internal auth.

## 4. Data Sources

All datasets below are on the NYC Open Data portal (Socrata / `data.cityofnewyork.us`) unless noted. IDs marked "verify" were not confirmed in this session — search the portal or hit the Socrata discovery API before building the ingestion pipeline, since dataset ownership/IDs occasionally change (some ACRIS tables have community-duplicated copies alongside the official NYC OpenData–owned ones — prefer the one owned by "NYC OpenData", not a member-created copy).

| Dataset | Provider | Socrata ID | Join Key | Purpose |
|---|---|---|---|---|
| ACRIS – Real Property Master | DOF | `bnx9-e6tj` (official; confirm not a community copy) | Document ID, BBL | Every recorded deed/mortgage/satisfaction; core of both v1 and v2 |
| ACRIS – Real Property Legals | DOF | `8h5j-fqxa` (confirmed) | Document ID, BBL | Links documents to specific lots |
| ACRIS – Real Property Parties | DOF | `636b-3b5g` (confirmed) | Document ID | Grantor/grantee names — needed for owner-match checks |
| ACRIS – Real Property References | DOF | `pwkr-dpni` | Document ID | Cross-references between related filings (e.g. deed → new mortgage chains) |
| PLUTO / MapPLUTO | DCP | `64uk-42ks` | BBL | Baseline owner name, building class, ownership type |
| Property Valuation & Assessment Data (Tax Classes 1,2,3,4) | DOF | `8y4t-faws` | BBL | Assessed value, mailing address (more current than the older `yjxr-fw8i` version) |
| Revised Notice of Property Value (RNOPV) | DOF | `8vgb-zm6e` | BBL | Owner mailing address for mismatch detection |
| Property Exemption Detail (incl. SCHE/DHE) | DOF | `muvi-b6kx` | BBL | Senior/disabled homeowner exemption flags — vulnerability proxy |
| Tax Lien Sale Lists | DOF | `9rz4-mjek` | BBL | Financial distress signal |
| NYC Citywide Rolling Calendar Sales | DOF | `usep-8jbt` | BBL, neighborhood | Recent sales — neighborhood price-pressure baseline |
| NYC Citywide Annualized Calendar Sales | DOF | `w2pb-icbu` | BBL, neighborhood | Multi-year price appreciation trend |
| 311 Service Requests (2010–present) | DOITT | commonly cited as `erm2-nwe9` — verify | BBL/address | **Cut for hackathon (Section 3a)** — kept here for the post-hackathon v2 build |

**External, non-Open-Data references** (not to be scraped/joined automatically without review):
- NY Dept. of State business entity search — for identifying newly formed LLC grantees.
- NYC ACRIS document images — for manual review of flagged filings, not bulk ingestion.

## 5. Join Strategy

Two grains: **`properties`** (one row per BBL, spined on PLUTO) and **`filings`** (one row per ACRIS Document ID). Don't collapse these into a single table — join `filings` (collapsed to one row per BBL via a window function on recording date) into `properties`, never the reverse.

**Join sequence:**
1. ACRIS Master + Legals (Document ID → BBL). Legals is the required bridge — Master alone has no BBL. **Join-explosion risk:** a document can reference multiple BBLs (blanket filings); check row counts before/after rather than assuming 1:1.
2. ACRIS Master + Parties (Document ID). Multiple grantors/grantees per document — aggregate to one row per document (array of names, or filter to primary party-type codes) before joining anything else.
3. ACRIS Master + References (Document ID ↔ related Document ID). Self-referencing join for detecting deed→mortgage chains (Section 6's equity-stripping pattern). Watch directionality to avoid double-counting.
4. Collapse the joined `filings` view to one row per BBL (window function, most recent recording date) *before* joining into PLUTO.
5. PLUTO + Property Exemption Detail (BBL). Multiple exemption line items per BBL per year — filter to SCHE/DHE codes, take most recent year.
6. PLUTO + Tax Lien Sale Lists, Rolling/Annualized Sales (BBL). Watch field-format inconsistency across DOF datasets — some use one padded BBL string, others separate borough/block/lot columns with different padding/types. A frequent silent join-failure source.
7. **Deferred post-hackathon (Section 3a):** 311 doesn't reliably carry BBL (usually address or lat/long) — geocode to BBL via NYC Geoclient before joining, when 311 gets reintroduced for v2.

**Grain caveat:** PLUTO has one row per tax lot *except* condominiums, which collapse to one row per condo complex, not per unit — a real coverage gap, document it rather than discover it later.

## 6. Feature Groups (v1 Scorecard)

**Ownership vulnerability**
- Senior (SCHE) / disabled (DHE) exemption present
- Long ownership tenure with no recent ACRIS deed activity (computed from Master table)
- Free-and-clear status (mortgage satisfaction recorded, no subsequent new mortgage)
- Owner-occupied 1–3 family home vs. LLC-owned (PLUTO building class + owner name)

**Financial distress**
- Present/historical entry in Tax Lien Sale Lists
- Exemption lapse pattern (e.g. SCHE stops renewing — can indicate owner death or incapacity)

**Neighborhood pressure**
- Recent price appreciation (Rolling/Annualized Sales) relative to citywide baseline
- Density of recent legitimate sales nearby, as a "normal transfer" baseline for v2

**Transaction-level red flags** (feed v2, or bump v1 score if a new filing appears on a scored property)
- $0 / nominal consideration on a deed
- Quitclaim deed where a warranty/bargain-and-sale deed would be typical
- New deed followed within days/weeks by a new mortgage on the same BBL (equity-stripping pattern)
- Grantee is a newly formed LLC (requires the external DOS join, treat as optional/manual-review feature, not automated)

## 7. Scoring Methodology

### v1 Weighting (draft — pending fair-housing/civil-rights legal review, see below)

Two scored pillars, 0–100 total. **Neighborhood price appreciation is intentionally NOT a scored input** — see Bias & Fairness Review.

| Feature | Pillar | Points | Rationale |
|---|---|---|---|
| Free-and-clear (no active mortgage) | Ownership Vulnerability | 25 | Strongest documented driver — no lender monitoring the title |
| Senior/disabled exemption on file (SCHE/DHE) | Ownership Vulnerability | 20 | Most consistently cited targeting pattern in DA/AG guidance |
| Long tenure, no ACRIS deed activity in 10+ yrs | Ownership Vulnerability | 20 | Generational-ownership pattern, correlates with free-and-clear |
| Owner-occupied, individually owned (not LLC) | Ownership Vulnerability | 10 | Keeps the model targeted at individual homeowners, not landlords |
| Active/historical tax lien | Financial Distress | 15 | Documented driver of foreclosure-rescue and equity-theft schemes |
| Exemption non-renewal/lapse pattern | Financial Distress | 10 | Proxy for possible owner death, incapacity, or unresolved probate |

### Feature Definitions

**Free-and-clear, no active mortgage (25 pts).** Computed by checking whether the most recent ACRIS filing against a BBL is a mortgage satisfaction/discharge with no subsequent new mortgage recorded, or a deed with no mortgage ever recorded. Weighted highest because an active mortgage means a lender routinely monitors the title as part of loan servicing; once paid off, that institutional monitoring disappears and the homeowner becomes the sole line of defense — the pattern DOF and legal-aid guidance cite for why free-and-clear homes are disproportionately targeted. *Caveat:* satisfaction filings can lag real-world payoff, so treat as a data-driven estimate, not a certainty.

**Senior/disabled exemption on file — SCHE/DHE (20 pts).** Checks for an active exemption on the BBL in DOF's Property Exemption Detail data for the current or most recent tax year. Weighted heavily because age and disability are the most consistently cited vulnerability characteristics in DA/AG/legal-aid guidance — social isolation, susceptibility to undue influence, reduced capacity to monitor records. *Caveat:* only captures enrolled seniors; DOF's own audits show administrative gaps, so an eligible-but-unenrolled senior scores as if this factor doesn't apply — frame as "known senior/disabled homeowner," never "confirmed not a senior."

**Long tenure, no ACRIS deed activity in 10+ years (20 pts).** Years since the most recent deed-type document (not mortgage, not satisfaction) was recorded against a BBL; 10-year threshold to be validated statistically once real data is pulled. Weighted heavily because long-held properties are more likely free-and-clear and equity-rich, and this pattern captures heirs' property — owner died, no probate filed, chain of title murky enough that a forged deed can go unchallenged. *Caveat:* can't distinguish "still occupied by aging original owner" from "informally inherited by absentee heirs" — both high-risk, different reasons; consider splitting once a mailing-address-distance signal exists.

**Owner-occupied, individually owned, not an LLC (10 pts).** Derived from PLUTO owner-name pattern-matching plus residential building class. Lowest weight in this pillar because it's a scope filter, not a strong risk differentiator — LLC-owned properties are professionally managed and monitored, so this keeps the model focused on the right population. *Caveat:* a legitimate estate-planning trust can pattern-match as "LLC-like" while the actual beneficiary is an individual who needs protecting — likely needs manual review for edge cases.

**Active or historical tax lien (15 pts).** BBL appears, currently or in recent years, on DOF's Tax Lien Sale Lists. Weighted meaningfully because financial distress is a documented precursor to foreclosure-rescue and predatory-purchase schemes, both of which start from exactly this situation. *Caveat:* doesn't distinguish real distress from a short-term/administrative gap — ideally weight by recency and duration rather than as a flat binary.

**Exemption non-renewal or lapse pattern (10 pts).** Detected by comparing SCHE/DHE status for the same BBL across consecutive available years (SCHE requires renewal roughly every 24 months). Weighted as a moderate signal because a lapse is one of the few public-data proxies for owner death, incapacity, or an unresolved estate — the heirs'-property/probate-fraud vector again. *Caveat:* can just mean missed paperwork by a still-capable owner — should trigger a lighter-touch response (reminder mailer), not be read as near-certain evidence of death or incapacity.

Worked example: 82-year-old SCHE-enrolled owner, free-and-clear, owned since the 1990s, individually owned → 25+20+20+10 = **75/100, "elevated"** — structural factors alone carry the signal without geography as an input.

Present as "risk factors present" with the contributing factors listed. **Revised 2026-08-16:** the numeric point total is now also shown on self-lookup, framed as "X of Y possible points" — a magnitude, never a percentage or a probability of theft. The original all-or-nothing "never show a number" stance assumed any number would read as a calibrated probability; showing it explicitly captioned as a points total (not a percentage) was judged an acceptable way to answer "how bad is it" without crossing into implying a real probability, given there's still no ground-truth dataset to calibrate one against.

### Bias & Fairness Review (v1)

- **Neighborhood appreciation excluded from scoring.** It's the feature most likely to function as a proxy for race and historic redlining patterns — deed theft concentrates in historically Black homeownership neighborhoods (Central Brooklyn, Southeast Queens, parts of the Bronx) precisely because those areas are appreciating fastest. Scoring it in would (a) dilute individual-level signal, since every property in the neighborhood gets bumped regardless of the specific owner's actual risk factors, and (b) turn the public aggregate view into what is functionally a map of historically Black homeownership — a serious Fair Housing Act exposure for a tool touching housing, independent of intent. Keep it as **contextual information shown alongside a score**, never as a scoring input and never as the sole driver of what appears "hot" on the public view.
- **SCHE-enrollment gap is a real blind spot.** DOF's own audits have found administration issues with the SCHE program; enrollment requires paperwork and awareness the eligible-but-unenrolled senior may not have. The unenrolled may be the *most* vulnerable (least financial literacy, language barriers, no advocate) and will score as if the senior factor doesn't apply. **Document explicitly: absence of SCHE is missing data, not evidence of lower risk** — do not let the UI imply otherwise. (Section 13's SCHE/DHE Enrollment Helper is the concrete fix for this gap — it closes it with a screening tool, not just a UI caveat.)
- **Population/scope gap:** this scorecard only covers BBL-level deed properties. Co-ops are a different fraud mechanism (stock/proprietary lease fraud, not deed fraud) and need a separate model — don't silently exclude them; say so in the product.
- **Downstream misuse risk reinforces the Section 8 no-bulk-export decision.** Even a bias-checked score could be scraped and used *against* the homeowners it's meant to protect (e.g., an investor treating "high vulnerability" as "likely to sell cheap soon").
- **Do not self-certify this.** Given the tool is public, housing-adjacent, and geographically patterned, an internal methodology review is necessary but not sufficient — get an actual fair-housing/civil-rights legal review before public launch.

### v2 (later)

Anomaly scoring on new ACRIS filings (e.g. isolation forest or a simple rules-plus-statistics approach) scored against the "normal transfer" baseline from Section 6. Keep this separate from the v1 property score — different unit of analysis (transaction vs. property).

## 8. Public-Facing Product Design — Dual-Use Risk

**The core tension:** an address-level, publicly rankable "highest risk" list is also a target list for the exact bad actors this app is trying to stop (e.g., "elderly, free-and-clear, tax-delinquent homes in [neighborhood]").

**Design resolution:**
- Public view: aggregate to **block or census-tract level** (heatmap), not individual addresses.
- Individual-level score: gated behind a **self-lookup** flow — the owner (or someone acting on their behalf) enters their own address and receives their own score plus concrete next steps (register for the city's NRD alert program, check ACRIS annually, contact the Mayor's Office of Deed Theft Prevention).
- No bulk export or API access to individual scores without rate-limiting/verification.
- Precedent: NYC's own MODA illegal-conversion fire-risk model was used internally by the inspection task force, not published as a public ranked list — same logic applies here.

### Self-Lookup Verification (Theoretical Design — SUPERSEDED, see below)

*Kept for historical record of the exploration; no longer reflects the current design.* Property ownership records are inherently public, so any verification scheme built from property facts (BBL, assessed value, exemption ID) is answerable by anyone willing to do the same public-records research the tool itself does — structurally circular, not a real gate. Two mechanisms that actually work, because they reach outside the public record:
1. **Mail-based confirmation** — mirror DOF's own NRD program: mail a one-time code to the property's mailing address on file, entered online to unlock. Proves postal access, not just knowledge. Reuses a trust bar the city already established.
2. **Government ID matching** (e.g. Login.gov, ID.me, Persona) against the ACRIS-recorded owner/grantee name — stronger, but heavier friction. Also runs into a real problem this design never solved: it verifies *who someone is*, not *whether they should see this property's data* — a second matching step against the ACRIS-recorded name is still needed, and that reopens the exact-name-mismatch problem (maiden names, trusts, heirs not yet of record). Also excludes anyone without a current government ID — disproportionately the elderly and heirs this tool is meant to protect.
3. **Institutional mediation** — a legal-aid caseworker or outreach worker looks it up on behalf of someone they're already working with in person, sidestepping automated verification via an existing human trust relationship.

**Formerly recommended approach — tiered disclosure, not a single gate:** no verification → aggregate view only; light friction (email, rate limiting) → summary count only; real verification (mailed code) → full breakdown. Superseded entirely by the decision below.

### Architecture Decision: Individual Risk Lookup is Internal-SSO-Only (Post-Hackathon)

**Individual-level risk-factor data has no public path at all — not gated, not tiered, simply not exposed publicly.** Access is restricted to authenticated city staff via SSO, scoped to whichever specific outreach team actually does this work (e.g. the Mayor's Office of Deed Theft Prevention, or a specific DOF unit) — not agency-wide DOF access. Least-privilege: broader access is more misuse surface for no real benefit.

This resolves the verification problem above by making it moot rather than solving it: staff SSO authenticates a *professional role* authorized to look up any address for outreach purposes, not a claim of ownership over one specific property. No ACRIS-name-matching step is needed, no ID.me integration, no equity concern about excluding people without a driver's license — all of that was specific to proving "you are this property's owner," which this design no longer attempts.

**The safeguard this puts all its weight on:** every staff lookup must be logged — who, when, which property, tied to an outreach-contact record — since staff SSO alone doesn't prevent an employee from looking up someone unrelated to their casework (an ex, a neighbor). This is not a nice-to-have; with no other gate on individual data, this logging is the actual control.

**Stated design principle:** House history (Section 12) is public, for anyone, always. The risk index is internal-only, staff-authenticated, and feeds directly into outreach — it is never public, and there is no path for it to become one.

### UI Design Notes (from mockup)

- Single app, toggled between "public view" and "self-lookup" — not separate pages. Faster to build and keeps the boundary between the two explicit in the UI itself.
- Public view shows neighborhood-name cells only, never addresses or map pins — the Section 8 boundary enforced visually, not just in policy.
- Self-lookup headline reads "X of N risk factors on file" (N = 5 in the hackathon build, per Section 3a's cut list). **Revised 2026-08-16:** the point total is now shown alongside it, as "X of Y possible points" — see Section 7's revision note. Still never shown as a percentage.
- Factor list uses neutral "Not on file" pills, deliberately not checkmark/x iconography — a checkmark next to an absent senior exemption would visually imply "confirmed not vulnerable," the exact SCHE-enrollment-gap misread flagged in Section 7.
- Results panel always pairs with the three concrete next steps (NRD alert registration, annual ACRIS check, Mayor's Office of Deed Theft Prevention contact) — never shown as a bare number on its own.
- **Note:** this mockup predates the internal-SSO decision above and models a public self-lookup flow. See Section 12 for the current branched-UI design (house history public to everyone, risk factors visible only to authenticated staff). For the hackathon itself, the existing self-lookup UI (address in, factors out, no real auth) stays as the technical stand-in — see Section 3a's cut list.

### NYC Design System Reference

- **NYC Opportunity Standard** (`npm install @nycopportunity/standard`, nycopportunity.github.io/standard) — current, actively maintained, WCAG AA, mobile-first, built for exactly this kind of citizen-facing service tool (ACCESS NYC heritage). Best philosophical fit.
- **NYC Core Framework** (`github.com/CityOfNewYork/nyc-core-framework`) — older, broader, Bootstrap 4-based, open source, more general city-website styling.
- **Skip:** "NYC Digital Design System" (`@nycds/core`) — install docs require Azure DevOps personal-access-token auth, likely an internal-only registry, not available externally.
- **Integration note for the hackathon stack:** both real options are npm/vanilla-CSS packages that don't drop cleanly into Streamlit. Don't install the package — hand-pick the Opportunity Standard's color palette and typography scale into a custom CSS block via `st.markdown(unsafe_allow_html=True)` instead. Full package integration becomes straightforward if the FastAPI+Leaflet upgrade path (Section 9) gets used instead.

## 9. Architecture

### Hackathon stack (decided, build this)

- **Language:** Python end-to-end (ingestion, joins, scoring, frontend) — one language, minimal context-switching for a small team.
- **Ingestion:** `requests` against the Socrata SODA API (`data.cityofnewyork.us/resource/{id}.json`) using the confirmed IDs in Section 4, with SoQL `$where`/`$limit`/`$offset`. Register a free NYC Open Data app token immediately — unauthenticated calls throttle hard. Pull to local Parquet files.
- **Storage/joins: DuckDB**, not Postgres. Queries Parquet/CSV directly, no server, and well-suited to the window-function aggregation Section 5's join logic needs. SQLite is an acceptable fallback if the team prefers it, at a performance cost on the aggregation-heavy joins.
- **Scoring:** a single Python script running the join pipeline + Section 7 scorecard, re-run manually before the demo. No scheduler, no queue.
- **Geocoding:** direct `requests` calls to Geoclient, results cached locally.
- **Frontend: Streamlit** — `pydeck`/`st.map` for the aggregate heatmap, form widgets for self-lookup, History of My Home, and the SCHE/DHE Helper. The self-lookup "gating" from Section 8 is a UI pattern only for the demo (address input box), not real identity verification — that gap is itself worth naming explicitly to judges. For the SCHE Helper, Streamlit's session state (not a database write) naturally satisfies Section 13's "never persisted" privacy requirement — worth confirming whoever builds it doesn't add a write path that isn't needed. Upgrade path if a frontend-capable teammate is available: FastAPI + Leaflet for more visual polish.
- **Deployment:** local, on the laptop, for the demo. Streamlit Community Cloud as an optional stretch for a shareable link.
- **Explicitly skip:** hosted Postgres, Airflow/cron, real auth, microservices, full-city ingestion — all solve problems this build doesn't have in 48 hours.

### Post-hackathon / production considerations

- **Refresh cadence:** ACRIS updates roughly daily; DOF valuation/exemption data updates annually/periodically — a real pipeline needs to handle mixed cadences per source rather than a single refresh schedule.
- **Real auth for self-lookup:** the hackathon UI pattern needs to become an actual verification step before any public launch (see Section 8) — though per Section 8's internal-SSO decision, this now means staff SSO, not a public verification flow.
- **Scheduled ingestion, hosted storage, and a real deployment target** replace the local/manual hackathon setup once this moves past a demo.

## 10. Open Decisions (resolve before or during build)

- [x] Draft v1 weighting scheme complete (see Section 7) — points and pillars grounded in documented targeting patterns, not arbitrary numbers.
- [ ] Get a fair-housing/civil-rights legal review of the v1 scoring methodology before any public launch — internal QA is not sufficient given the housing-adjacent, geographically-patterned nature of the tool.
- [x] SCHE-enrollment gap UI messaging resolved: "not on file" neutral pill, not a checkmark/x (see Section 8 UI Design Notes); Section 13's Enrollment Helper is the further, active fix.
- [x] Co-op scope gap resolved: explicit "not covered yet" messaging for the hackathon (see Section 3a), not a separate model.
- [x] v2 (transaction anomaly scoring) resolved: out of scope for the hackathon (see Section 3a), phase-two feature.
- [x] 311 geocoding resolved: 311 ingestion cut entirely for the hackathon (see Section 3a) — Geoclient is only needed for self-lookup addresses.
- [ ] Verify the "TBD" Socrata dataset IDs above and confirm current update cadence for each.
- [ ] Register a free NYC Open Data app token before ingestion starts — avoids throttling on day one.
- [x] Geoclient API key registered and verified live against the v2 `/search` endpoint (see Section 11 for the corrected v2 endpoint shape — v1 is retired).
- [ ] Confirm team size/skills to decide Streamlit vs. FastAPI+Leaflet for the frontend.
- [ ] Prep the "future enhancements" talking points (HUD vacancy data, OpenCorporates) for the demo — not build tasks, just have the reasoning ready to explain.
- [x] Self-lookup verification method (mail-based/tiered disclosure) superseded by the internal-SSO architecture decision (see Section 8) — not built for the hackathon either way, real implementation is a post-launch task.
- [x] Build History of My Home (Section 12) — net-new: plain-language doc-type mapping, same-day bundling, toggle-ladder timeline UI, full-history ACRIS query path. Built and live-verified (`app/history.py`); lis-pendens gap documented above.
- [x] Build SCHE/DHE Enrollment Helper (Section 13) — net-new: 3-question self-report form, output-state logic, no persistence. Built and live-verified (`app/sche_helper.py`).

## 11. Complementary External Data Sources (Non-NYC-Open-Data)

### Build for the hackathon:

- **NYC Geoclient API (DoITT).** v1 (`api.nyc.gov/geoclient/v1/`, app_id/app_key query params) is retired — use **v2**: base URL `api.nyc.gov/geoclient/v2/search` (no `/geo/` path segment), a single `input` query param taking an unparsed location string (e.g. `input=1 centre st manhattan`), auth via `Ocp-Apim-Subscription-Key` header set to your Primary key. Response is `results[0].response` when `results[0].status == "EXACT_MATCH"`; BBL is `response.bbl`. Register at the NYC API Developer Portal (api-portal.nyc.gov) and subscribe to the Geoclient product specifically — an account alone doesn't grant access, and it may need portal-side approval before the key activates. Free, no meaningful volume restriction. Use to resolve self-lookup addresses to BBL — this, not Google, for the core geocoding need. (311 geocoding is deferred, see Section 3a.) Verified live 2026-08-15.

### Future enhancements — demo talking points, not built for the hackathon:

- **US Census Bureau ACS.** Free API key at `api.census.gov/data/key_signup.html`. Latest vintage: 2020–2024 5-year estimates (released Jan 29, 2026), available down to census tract/block group. No meaningful cost or access barrier — cut for the hackathon purely for time (Section 3a), not for any access reason. Tract-level context for the public aggregate view only, never a scored input — same proxy-variable reasoning as excluding neighborhood appreciation in Section 7.
- **HUD/USPS quarterly vacancy data (by census tract).** Vacancy is a real, independent risk signal (deed thieves target unoccupied homes, especially post-mortem), but access is gated to registered government entities and nonprofits, not self-serve — would need a partnership (e.g. with Build Up Justice NYC, already referenced in Section 15) to pursue post-hackathon.
- **OpenCorporates.** Would strengthen the "newly formed LLC grantee" transaction feature, but the free tier (~50 requests/day) isn't viable at pipeline scale and the paid tier is real money. Worth applying for their free public-benefit access program after the hackathon, once there's a working demo to point to in the application.

### Display-only:
- **Google Maps/Places API** — map tiles, address autocomplete, and reverse-geocoding a user-typed address before handing it to Geoclient for the authoritative BBL. Not a data source for the model itself.

**Considered and not recommended:**
- **USPS National Change of Address (NCOA)** — a useful signal in principle, but access-restricted to CASS-certified commercial vendors, not public data.
- **Commercial skip-trace / data-broker services** — reintroduces the individual-level bulk-lookup misuse risk Section 8 was designed to avoid.
- **Street View-based visual occupancy signals** — real surveillance flavor for marginal benefit over vacancy/311 signals already in scope.
- **NYS Surrogate's/probate court records** — the most direct possible signal for the heirs'-property vector, but not available as bulk open data, only case-by-case lookup. Aspirational, not an ingestion target.

## 12. History of My Home (In Scope — see Section 3a)

A separate, fully public feature: a plain-language ownership/deed timeline for any address, built on the same ACRIS/PLUTO/Geoclient pipeline already in place, no scoring or login involved.

**Core design line — neutral facts only, no risk framing.** Presents the same underlying facts as Section 7's scorecard (free-and-clear status, tenure length) but as neutral history, never as flagged or weighted signals. This is what keeps it safe to be fully public: everything shown is already visible in ACRIS's own (much clunkier) interface today — this tool improves legibility of existing public information, it doesn't create new exposure.

**Data pipeline — reuses existing tables, one real difference from the scoring build:** Geoclient resolves address → BBL, same as elsewhere. ACRIS Master + Legals + Parties, same three tables — but needs **every record for the BBL, full history**, not the collapsed-to-most-recent-only view Section 5's join logic builds for scoring. Whoever builds this needs a separate query path, not a reuse of the collapsed view.

**Price:** ACRIS deed records don't reliably carry consideration. Match against Rolling Sales by BBL + date window; show price only on a confident match, never a guess.

**Content design decisions:**
- **Bundle same-day/nearby-date records** (a deed + its purchase-money mortgage) into one narrative entry rather than presenting raw ACRIS rows separately.
- **Document-type tiering:** narrative tier with custom plain-language sentences (deed, mortgage, satisfaction, assignment, lis pendens) vs. suppressed-by-default administrative tier (UCC filings, boilerplate), revealed via toggle.
- **$0/nominal sale price gets neutral framing, not a red flag** — "typically indicates a gift, inheritance, or family transfer" — the deliberate opposite of Section 7's treatment of the same underlying fact, because the audience and stakes are different (someone reading their own home's history vs. a risk-scoring input).
- **Active legal notices (lis pendens) surface out of chronological order**, above the timeline, as a "currently true status" line — a present fact, not historical, so it doesn't wait in the date-ordered list. Shown unconditionally, same for every visitor regardless of the internal-SSO risk-access decision in Section 8.
  - **Implementation gap, found while building (2026-08-16):** not buildable from data currently in scope. Checked live against ACRIS's own "Document Control Codes" reference table (`7isb-wh4c`, all 126 codes, `record_type = 'D'`) — no lis pendens / notice-of-pendency code exists anywhere in it. Lis pendens are filed through NYS courts, not ACRIS document recording, so no dataset already in this pipeline carries them. `app/history.py` says this plainly in the UI ("Active legal notices... aren't available from this data source yet") instead of showing a fabricated always-empty "no active notices" state. Revisit if a NYS court-records feed is ever added as a new source.
- **Thin-history disclosure:** oldest entry reads "Earliest record in NYC's digital system — earlier transfers may exist only in physical records," not a silent stop.
- **BBL-identity disclosure:** lot lines merge/subdivide over time — frame as "history of this current lot configuration," not "this address across all time."
- **Freshness disclosure:** "Records current as of [ingestion date]," given ACRIS's roughly-daily update cadence.
- **Toggle ladder, not independent toggles:** "Show earlier history" and "Show all recorded documents" are ordered, not parallel — the second is a strict superset of the first (always implies full time depth too), avoiding the dead combination of "recent window + administrative filings." Each button shows a count of what it reveals; both disappear once used. Same-day grouping keeps applying even to newly revealed administrative-tier records.
- **Summary card:** current owner + tenure (reuses the same most-recent-deed logic as Section 7's tenure feature), last sale price/date if confidently matched, "X ownership changes since [year]" stat.
- **Co-ops:** same scope gap as the main tool, same "not covered yet" messaging — not a separate model.
- **Disclaimer:** "Reflects NYC's public property records; may not include every historical filing and isn't a substitute for a title search or legal advice."

### Branched "Look Up My Property" UI

Single search entry point, single result page — house history and the internal risk view live on the same UI, differentiated by authentication state, not separate tools:
- **Public/unauthenticated:** house history timeline + summary card + active-notice line, always. Where the risk panel would appear for staff, an **informational-only** card instead: "Risk assessment is available to authorized city staff." No login button, no CTA — there's no public login path to invite, per Section 8's internal-SSO-only decision.
- **Authenticated staff (SSO):** everything public users see, plus the full risk-factor panel from Section 7/8 in the same position.

Mockup reference: two-persona toggle ("Public" / "Staff (internal)") demonstrates both states; the public-state card copy was deliberately corrected from an earlier draft that invited a public "Log in" action, since that implied a public path that doesn't exist.

## 13. SCHE/DHE Enrollment Helper (In Scope — see Section 3a)

A third public feature, distinct from the other two in one important way: it's unambiguously beneficial with no bias or dual-use tension to design around, and it directly closes a limitation flagged since Section 7 — the SCHE-enrollment gap ("absence of SCHE is missing data, not evidence of lower risk") — rather than just working around it in scoring.

**Confirmed current SCHE/DHE eligibility criteria** (verify against DOF before launch, since income thresholds adjust periodically):
- SCHE: owner(s) 65+. DHE: owner(s) under 65 with a qualifying disability. Mutually exclusive — DOF applies SCHE if a homeowner qualifies for both.
- Property: 1-3 family home, condo, or co-op.
- Combined household income (all owners, all sources) ≤ $58,399/year — sliding scale, ≤$50,000 gets the full 50% assessed-value reduction, up to $58,399 gets a minimum 5%.
- Primary residence, with narrow exceptions (divorce, separation, abandonment, nursing-home stays).
- Owned 12+ consecutive months before applying, unless transferring SCHE from a prior residence.
- Application deadline March 15, for the following July 1 billing period. Renews every 24 months.
- Bonus fact worth surfacing in the UI: SCHE recipients automatically also get Enhanced STAR, no separate action needed.

**Auto-checked from the pipeline vs. self-reported — deliberately minimized ask:**
- **Auto-checked:** property type (PLUTO building class), ownership duration 12+ months (same ACRIS deed-history logic as Section 7's tenure feature and Section 12's summary card), whether SCHE/DHE is *currently* on file (Property Exemption Detail).
- **Self-reported only, appropriately** (none of this belongs in any public dataset): age/disability status, primary-residence status, income bracket — brackets, not an exact figure, to minimize sensitivity of what's collected.

**Privacy guardrail — the one that matters most here:** self-reported answers must never be stored tied to the address. Unlike Section 12, which is safe to be fully public because everything it shows is already public record, "this address + self-reported age/income/enrollment status" would be a *new* sensitive record that doesn't exist in any public dataset today. Stateless client-side computation only, not persisted — stated directly in the UI ("Your answers aren't saved or linked to this address"), not just documented internally.

**Output states, same neutral/non-determinative register as the rest of the project:**
1. Already on file — confirmation + estimated next renewal date (24-month cadence).
2. Not on file, self-reported answers suggest eligible — "you may be eligible for [SCHE/DHE] and it's not currently on file — apply by March 15" + link.
3. Not on file, answers suggest not currently eligible (not primary residence, or income over the limit) — neutral, never a flat rejection: "may not currently qualify based on what you told us — DOF is the authoritative source, and rules can change."
4. Always shown: "This is a screening tool, not an eligibility determination — NYC DOF makes the final decision."

**Discovery path — surfaced contextually, not just standalone:** shown directly on the House of My Home page (Section 12) whenever the auto-check finds no SCHE/DHE on file: "Not currently getting a senior or disability exemption on this property. Check if you might qualify." Reaches people at the moment it's relevant rather than requiring them to find a separate tool.

**UI design decisions:**
- The first screening question — 65+ vs. under-65-with-a-disability — gives both paths equal visual weight (two buttons, same row), so DHE isn't a footnote to SCHE in the actual flow even though the tool is publicly branded around the more commonly searched "SCHE" name.
- Auto-checked facts render as confirmed context before the self-report form appears, so the person is only asked for the three things that genuinely can't be known any other way.

## 14. Other Public-Facing Ideas Surfaced (Not Developed)

Brainstormed while scoping History of My Home; kept as institutional memory, not designed further:
- **Corporate vs. individual ownership, aggregate by neighborhood** — reuses the OpenCorporates integration (Section 11) and the individually-owned pattern-matching logic (Section 7), aggregate-only by design.
- **"Before you sign" price sanity-check** — compares a specific offer against recent comparable sales (Rolling Sales), protects the person doing the lookup about their own situation rather than classifying them for someone else.
- **Tenant-ownership-transparency** — adjacent domain (who owns my building), established civic-tech precedent (JustFix.nyc), same ownership-resolution pipeline. Not deed theft, a different problem — noted for awareness, not pursued here.

## 15. Related City Resources (link out to, don't duplicate)

- ACRIS Recorded Document Notification Program (NRD alerts): `a836-acrissds.nyc.gov/NRD`
- Mayor's Office of Deed Theft Prevention: `nyc.gov/deedfraud`
- Build Up Justice NYC (legal aid partner, case pattern reference): `buj.org`
