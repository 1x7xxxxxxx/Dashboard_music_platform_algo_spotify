# ADR-032 — The cross view is the whole funnel: one page, a section registry, one filter bar

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** the owner (voice notes W2, W5, W6, W7, W11, W13 — `revue/notes-vocales-2026-10-09.md`), R476, code-critic BUILD-MODIFIED

## Context

The owner's decision (W13): « une vue Spotify + S4A, une Apple Music, une YouTube, une
SoundCloud ; TOUT le reste dans une seule vue croisée … architecture cohérente, simple,
comparer/traquer avec les mêmes filtres ». R378 had already merged the four Meta pages and
Instagram into `meta_ads_overview` as sections, and R399 gave them one filter bar. What was
left:

| reading | where it lived | the owner's note |
|---|---|---|
| « Tout mon funnel » tab, four sub-tabs | the cross view | W2 « c'est flou » — redistribute |
| campaign stats compared (visits, clicks, Meta) | Hypeddit | W5 « on n'arrive pas à voir qui a le mieux performé ni les data Meta → vue croisée » |
| releases at equal age + Meta € | Spotify + S4A | W6 « → vue croisée » |
| Shazam since release + Meta | Apple Music | W7 « → vue croisée » |
| break-even / net revenue | Distributeurs | W11 « → vue croisée, renommée … × Revenus » |

The page dispatched its sections through an `if section == …` ladder, and the filter bar
guessed from the section name what to show.

## Decision

1. **One registry.** `SECTIONS` maps a key to `Section(label, render, bar_uses)`. `render`
   takes `(db, artist_id, bar)` — the tenant is passed explicitly, never re-resolved by a
   section (rule 7). `bar_uses` is the set of filters the section reads (`account`,
   `campaign`, `second`, `period` — `meta_filter_bar.BAR_*`); the bar draws only those,
   and states the others (greyed period, or « this section follows your releases »). A test
   resolves every entry.
2. **Seven sections, in reading order:** the journey of ONE campaign, without its four
   sub-tabs (Insta → Hypeddit → Spotify, Shazam, the listener verdict — W2 « c'est flou »), campaign performance (absorbs « comparer mes campagnes »),
   releases (Hypeddit campaigns + releases at equal age with Meta € per day + Shazam since
   release with Meta), creatives, who saw the ads (absorbs « par pays »), Instagram,
   revenue (the break-even treasury).
3. **A moved chart leaves its origin in the same commit.** Hypeddit keeps entry + history;
   Apple Music loses the Shazam-since-release chart; Distributeurs loses the treasury. The
   Spotify page keeps its releases chart WITHOUT the Meta overlay — the owner called it
   « nickel » (W6) — and the overlaid version is the cross view's: one builder,
   `spotify_s4a_combined.render_release_cohort(…, overlays=…)`, two callers. The Meta €
   per release is read by ONE loader, `load_release_spend`, shared with Apple.
4. **Meta spend is drawn per day** on every release overlay (dashed, right axis), Apple
   included — the same convention as R459, so two charts of one page read the same way.
5. The page key stays `meta_ads_overview` (Free-plan key, no migration). Title « … × Shazam
   × Revenus ». It moves to the END of « Analytics plateformes » (W13 II). Every old route
   stays an alias that opens its section.

## Consequences

- The four platform pages answer « how does this platform do »; the cross view answers
  « what did my money and my campaigns do ». A reading that needs two sources goes here.
- The break-even is no longer on the distributors page: an artist who only enters revenue
  finds it under the cross view's « Revenus » section. Its redesign (scale, W11) is R488.
- Revenue and releases read the account at most: the campaign does not scope them, and the
  bar says so instead of silently ignoring it.

## Rejected

- **`st.tabs` instead of a segmented control** — tabs run every body on each rerun; seven
  sections are several thousand lines of queries.
- **Separate pages per source with shared filters in session state** — that is the state
  R378 left, and W13 asks for the opposite.
