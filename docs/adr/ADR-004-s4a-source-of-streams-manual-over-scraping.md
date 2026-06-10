# ADR-004 — S4A source-of-streams split: manual entry, automatic capture rejected

- **Status:** Accepted (manual entry shipped; automatic capture rejected)
- **Date:** 2026-06-10
- **Deciders:** @1x7xxxxxxx
- **Supersedes:** —
- **Related:** migration `052_s4a_nonalgo_radio_manual.sql`; `src/dashboard/views/saisie_s4a.py`; `src/utils/ml_inference.py` (`NonAlgoStreams28Days_log`, `HowManySongsDoYouHaveInRadioRightNow`); roadmap § "Phase-2 data acquisition"

## Context

Two ML features in `ml_inference.build_features` were hard-coded to 0 for lack of a
live source:

- `NonAlgoStreams28Days_log` — per-song organic (non-algorithmic) streams over 28d,
  **the #1 volume driver per SHAP**;
- `HowManySongsDoYouHaveInRadioRightNow` — per-artist count of songs currently in Radio.

Both derive from the **"source of streams" breakdown** (organic/search/profile vs
Discover Weekly / Release Radar / Radio / autoplay / editorial). The roadmap framed
"Phase-2 data acquisition" as capturing this split **automatically** from Spotify for
Artists (S4A).

## Investigation

The S4A ingestion is CSV file-drop based (`airflow/dags/s4a_csv_watcher.py` →
`src/transformers/s4a_csv_parser.py`), with three export types — timeline,
audience, songs-all. **None carries a source split** (columns stop at
`streams / listeners / saves / followers / playlist adds`). The Spotify public Web
API (`src/collectors/spotify_api.py`) exposes no analytics. There is no scraping
infrastructure anywhere in the repo.

The artist (data owner) **confirmed (2026-06-10) that S4A shows the source split
on-screen only — there is no CSV/download export for it.**

## Considered alternatives

### Option A — Manual entry (CHOSEN)
A per-tenant manual-entry form in the Saisie S4A view writes
`s4a_song_nonalgo_streams` (per-song 28d) + `s4a_artist_radio_count` (per-artist);
`build_features` reads them, defaulting to 0 when absent. Effort: shipped
(migration 052). ToS-safe, no new infra, no credentials handled, mirrors the
existing manual signals (playlist adds, Discovery Mode).

### Option B — CSV parser + watcher
Mirror the DistroKid pattern (parser + table + watcher branch). **Not viable:** it
requires a downloadable source-split CSV, which S4A does not provide (confirmed).

### Option C — Browser automation / scraping of the S4A UI
A headless authenticated session reading S4A's private GraphQL/REST endpoints.
**Rejected:**
- **Multi-tenant credentials** — each artist's own Spotify SSO login would have to be
  captured and stored; a security liability with no existing pattern.
- **Fragility** — React SPA with rotating, unauthenticated-hostile private endpoints;
  breaks on any Spotify UI change.
- **ToS** — automated S4A access violates Spotify terms; account-ban risk for tenants.
- **Disproportionate** — high-maintenance new subsystem to un-impute one feature.

## Decision

Keep **manual entry** (Option A) as the standing solution. **Do not build automatic
capture** (Option B impossible without an export; Option C rejected on ToS / security
/ fragility grounds). The two features are now sourced from real data when the artist
fills the form, and default to 0 otherwise — reducing train/serve skew without an API.

## Consequences

- `NonAlgoStreams28Days` and RadioCount are tenant-effort-gated: precise only for
  artists who fill the form; 0 otherwise. They stay excluded from drift detection
  (0-heavy, partial coverage).
- The roadmap "Phase-2 data acquisition" item is **closed as manual** — automatic
  capture is parked. **Reopen only if** Spotify later exposes the source split via a
  CSV export or an official API (then Option B becomes a cheap parser+watcher).
- No model retrain: the 13-feature contract is unchanged; only imputation was
  replaced by real data.
