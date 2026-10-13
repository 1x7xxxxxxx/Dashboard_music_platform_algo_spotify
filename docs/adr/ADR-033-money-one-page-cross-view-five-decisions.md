# ADR-033 — Money in one place, the cross view in five decisions, the algo page in one scroll

- **Status:** Accepted
- **Date:** 2026-10-13
- **Deciders:** the owner (voice notes Y1, Y2, Y3 — `revue/notes-vocales-2026-10-13.md`), R553–R560, code-critic BUILD-MODIFIED (12 findings, folded in below)
- **Supersedes:** ADR-032 §2 (the seven sections) and §3 (« break-even → cross view »)

## Context

The owner reviewed the app and the charts dossier of 2026-10-13 (fiche numbers below).
Three verdicts reshape three pages:

| note | what it says | where it lands today |
|---|---|---|
| Y1 | « consolider tous les graphiques de revenue (même avec source Meta) dans la vue revenue » | money is drawn in THREE pages: the cross view's « 💶 Revenus » (fiche 25), the algo page's « 💰 Budget & ROI » (fiches 50, 51) and « 💶 Mon argent » (tiles, projection, fiche 68, LTV fiche 67) |
| Y2 | one cross view, « architecture cohérente … comparer, traquer avec les mêmes filtres » ; fiches 42+43+29+2+6 « un truc temporel qui regroupe tout » ; 44 « le funnel principal » absorbing 128, 22, 23, 39, 26 ; 27, 30, 32, 34 removed | seven sections, the time series spread over four of them |
| Y3 | « il faut tout me regrouper en un seul endroit … trop de trucs redondants » ; no tables ; DW → Radio → RR | already one scroll (`router.py`), but five named sub-parts that repeat one another, tables in three of them |

ADR-032's registry (one page, `Section(label, render, bar)`, one filter bar) is kept: the
owner's complaint is not the mechanism, it is what the sections hold.

## Decision

1. **Every euro is on the Trésorerie page (`imusician`)** — read top to bottom: import,
   entries (distributor revenue, release costs), the monthly treasury, the break-even
   (fiche 25 — spend red, revenue green, projection DRAWN dotted on a bounded horizon, never
   « 270 ans » in text; it absorbs fiche 51 and the « Mon argent » tiles), revenue against
   Meta spend (fiche 50), what an algo trigger is worth (fiche 68), SACEM. The subscriber
   LTV (fiche 67) is the operator's number: it moves to the admin page. One chart, one
   caller: the copies in the algo page and the cross view are deleted in the same commit.
   Four drawings of the break-even exist today (`revenue_forecast._render_money_chart`,
   `imusician.render_break_even`, `_tab_budget_roi._render_breakeven`, the PDF's
   `pdf_charts` treasury): the three on screen become one; the PDF keeps its own static
   copy (a print layout, out of scope). Fiche 68's numbers (`stream_rate`, `trigger_value`)
   keep ONE caller. The key `revenue_forecast` routes to `imusician` (route, `PAGE_ALIASES`,
   `_sections.ALIAS_SECTION`, `plan_pitch`); the cross view's stored `revenue` section falls
   back to its first section (no URL alias existed). **An admin with no artist chosen sees
   the all-tenant aggregate on this page (R25); fiche 68 and the break-even need ONE
   tenant, so they are shown only for a resolved `artist_id`.**
2. **The cross view has five sections, each answering one decision**, same registry, same bar:
   - 📈 **Chronologie** — ONE calendar figure (fiches 42, 43, 29, 6): streams/day,
     listeners, saves/day and playlist adds/day (7-day mean), Meta budget/day as an area,
     outbound clicks, CPR, Shazam; every series toggled by its legend. Below it, a second
     figure on the AGE axis (fiche 2, 28): two releases overlaid at equal age, with its own
     release picker — the period filter does not apply to an age axis, and the section says
     so (two x-axes never share one figure).
   - 🛤️ **Entonnoir** — ONE funnel, budget → impressions → link clicks → smart-link visits →
     platform clicks → streams → revenue, each step with its rate « of the step before »
     and its unit cost; « compare two campaigns » = two funnels side by side (fiche 26's
     indicators on each) — so this section reads `BAR_FULL` (it needs `second`). The
     stream → revenue step uses the artist's measured €/stream, never a join of monthly
     revenue onto days, and its caption says so.
   - 🎨 **Créas & réglages** — a « best settings » tool: for every lever the artist can set
     (creative, hook, objective, placement, age, country, platform) the best value by CPR,
     as bars; two creatives side by side (fiche 37); the spend Pareto with its CPR line
     (fiche 41); fiche 53 absorbed. Bar `BAR_UNDATED`: breakdown levers (age, country,
     placement) are undated, and a period filter must not apply to half the levers.
   - 🌍 **Audiences** — fiche 31 kept, fiche 45 as a Pareto by €/stream with CPR, fiche 33
     with its small counts legible.
   - 📸 **Instagram** — fiches 18, 19 with Meta spend as an area; engagement defined. The
     section gains a bar (account, period) to scope that spend.
   A folded glossary on the page defines outbound click, frequency, engagement, « % of the
   step before », unit cost.
3. **The algo page stays one scroll and loses its sub-parts' repetition**: the latest release is picked by
   default; horizontal rules separate the readings, in this order — where this track
   stands (fiche 46, absorbing 56 and 57, with the budget left to 100 % DW and Radio at the
   best and mean CPR), which lever would trigger (fiche 47 redrawn, two releases, SHAP order
   DW → Radio → RR with thresholds), what a trigger brings (129 + 48 merged, RR → DW →
   Radio, prediction dotted), what really happened, campaign settings. Tables only under
   `detail()`. Removed: « prochain geste titre par titre », « le vrai pour tout ton
   catalogue », fiche 56 as a separate figure; fiche 49 re-proposed or removed.
4. **Delivery order**: R553 (money) → R554 (the five sections AND their alias renames in
   one commit, so no alias dangles) → R555–R558 (they fill those sections) → R559 → R560
   (both rewrite `PAGE_SECTIONS`, the second on the first's layout).
5. **The dossier follows the code**: a removed or merged fiche leaves `review.yaml` in the
   commit that removes it.

## Consequences

### Positive
- « Is it paying? » has one page; three break-even drawings become one.
- The cross view's sections become decisions (when / where it leaks / what to change /
  who / community), not data sources.
- The algo page reads like the other pages: top to bottom, figures first.

### Negative / Trade-offs
- The algo page already renders everything on each rerun; removing the money section
  REMOVES three fragments from it. Only `_loaders.py` is cached (ttl 60 s): the tracks
  query and the model loads rerun on every pick — measured in R559, not assumed.
- Links to `?page=revenue_forecast` and to the cross view's revenue section now land on
  another page — kept working as aliases.

### Neutral / Operational
- No migration, no plan change: `meta_ads_overview` stays the Free key; `imusician` is Free.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Keep ADR-032's seven sections and only edit the figures | the owner's notes merge figures ACROSS sections (42 + 43 + 29 + 2 + 6): a figure cannot span two sections |
| One page per source (Meta, Hypeddit, Insta) with shared filters in session state | the state R378 left; W13 and Y2 ask for the opposite |
| A « Revenus » section kept in the cross view, the Trésorerie page linking to it | Y1 names the Trésorerie as THE money page; two places is the redundancy Y3 refuses |
| `st.tabs` on the algo page | tabs still hide readings behind a click; Y3 asks for one place |
