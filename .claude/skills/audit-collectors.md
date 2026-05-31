---
rex:
  - date: 2026-05-15
    issue: "Skill listed only empty returns (None/[]/{}); missed the return-partial-in-except variant YouTube collector used"
    fix: "Treat ANY non-raising return inside a collector except block as silent-success, including partial/truncated data. youtube_collector get_video_comments/get_playlists now raise"
    ref: "DEVLOG#2026-05-15"
    severity: warn
  - date: 2026-05-28
    issue: "Audit caught only silent RETURNS; meta collector raised nothing but hardcoded results to one action_type, zeroing data"
    fix: "Added Rule 5 (silent correctness): a metric pinned to a fixed action_type/column regardless of objective is corruption. meta collector now maps objective via _OBJECTIVE_RESULT_ACTION"
    ref: "DEVLOG#2026-05-28"
    severity: warn
  - date: 2026-05-29
    issue: "Paused/archived ads' insights silently lost: status filter excluded the ads, FK 'continue' guard discarded them"
    fix: "Audit skip guards too, not only except-returns: a 'continue' fed by an over-narrow API scope loses data. Broadened effective_status per level + clamped backfill to 36mo (Meta #3018)"
    ref: "DEVLOG#2026-05-29"
    severity: warn
  - date: 2026-05-29
    issue: "Broadening collector scope (archived ads) exploded API calls → Meta 80004 account throttle; retry covered only code 17"
    fix: "Retry all throttle codes {4,17,32,80004} w/ exp backoff + fetch_creatives flag to cut per-creative calls. BUC 80004 needs cooldown — re-running harder pins the score, not retry"
    ref: "DEVLOG#2026-05-29"
    severity: warn
  - date: 2026-05-29
    issue: "Derived table went stale: roll-up hook lived in only 1 of 3 write paths (Streamlit), not the DAG/debug batch importers"
    fix: "A post-write refresh hook must be wired into EVERY write path. Added rollup_sales_to_monthly to the iMusician DAG + debug importer (was Streamlit-only); backfilled artist 1"
    ref: "DEVLOG#2026-05-29"
    severity: warn
  - date: 2026-05-29
    issue: "Dual writers (legacy CSV + API) on same Meta tables, incompatible keys → silent 2x inflation ('All' buckets, fr labels)"
    fix: "Rule 8: one canonical writer per table. Archived legacy Meta CSV stack (8 files) + cleaned 'All'/fr rows. Two writers need identical keys or a source col, else silent duplication"
    ref: "DEVLOG#2026-05-29"
    severity: warn
  - date: 2026-05-31
    issue: "ML train/serve skew: scaler + _adj cols inference can't reproduce; probabilities wrong yet scoring exits SUCCESS"
    fix: "Rule 9: train on EXACTLY what inference recomputes. Dropped scaler (XGB-invariant), used raw counts + streams/listeners ratio, fixed ReleasePhaseEarly<35"
    ref: "DEVLOG#2026-05-31"
    severity: crit
  - date: 2026-05-31
    issue: "Model extrapolated outside its N=508 training envelope with no monitoring — silent out-of-distribution outputs"
    fix: "Rule 10: export training feature_stats; check_drift flags |z|>4 inputs, logged per song in the scoring DAG. OOD input = unreliable prediction"
    ref: "DEVLOG#2026-05-31"
    severity: warn
  - date: 2026-05-31
    issue: "Drift detector flagged the imputed-to-0 features (NonAlgoStreams) on 100% of predictions — permanent false alarm"
    fix: "check_drift excludes _IMPUTED_FEATURES (permanently OOD by design, already covered by the imputation caveat); drift now flags only genuine live-feature OOD"
    ref: "DEVLOG#2026-05-31"
    severity: info
---

# Audit: Silent Success Anti-Pattern in Collectors

## What it is
A collector method catches an API error, logs it, then returns empty data (`None`, `[]`, `{}`).
The DAG task receives the empty result, upserts 0 rows, and exits `SUCCESS`.
No alert fires. The dashboard silently shows stale or missing data.

## How to detect

Search every `except` block in `src/collectors/` for these patterns:

```bash
grep -n "return None\|return \[\]\|return {}\|return tracks\|return stats\|return data" src/collectors/*.py
```

Also look for:
- `break` after a non-2xx status code check inside a loop (silently stops pagination)
- `except Exception` that wraps an inner `except ValueError: raise`, preventing re-raise of specific errors

## How to fix

### Rule 1 — always re-raise in collector methods
```python
# BAD
except Exception as e:
    logger.error(f"Error: {e}")
    return None          # silent success

# GOOD
except Exception as e:
    logger.error(f"Error: {e}")
    raise                # propagates → DAG task FAILED
```

### Rule 2 — raise on non-200, never break silently
```python
# BAD
if response.status_code != 200:
    print(f"Error {response.status_code}")
    break

# GOOD
if response.status_code == 401:
    raise ValueError("API 401 — token expired. Renew via Dashboard → Credentials.")
if response.status_code != 200:
    raise ValueError(f"API {response.status_code}: {response.text[:200]}")
```

### Rule 3 — specific exceptions must not be swallowed by outer except
```python
# BAD — ValueError raised inside is caught by outer except
try:
    if status == 401:
        raise ValueError("401")
except Exception as e:
    print(e)
    break               # ValueError silently eaten

# GOOD
except ValueError:
    raise
except Exception as e:
    raise RuntimeError(f"Fetch error: {e}") from e
```

### Rule 5 — silent correctness, not just silent success
A collector can raise nothing, write rows, and exit `SUCCESS` while persisting
**semantically wrong** values. Watch for a metric pinned to a single fixed action
type / column regardless of the campaign objective or source variant:

```python
# BAD — results pinned to one action type; engagement campaigns always score 0,
# and the daily upsert overwrites correct CSV-imported values.
results = _count_action(actions, "offsite_conversion.custom")

# GOOD — derive the action type from the campaign objective.
action = _OBJECTIVE_RESULT_ACTION.get(objective, "custom_conversions")
results = _count_action(actions, action)
```

When a collector writes a derived/aggregated metric, confirm the derivation holds
across every objective / source format present in the data — not just the one the
author tested. (Meta `results`, 2026-05-28.)

### Rule 4 — zero-row guard in DAGs (defence in depth)
After processing all artists, check that at least one succeeded:
```python
if artists_with_creds > 0 and successful_fetches == 0:
    raise ValueError("All API calls returned 0 rows — possible credential/network failure.")
```

### Rule 6 — silent loss is not only `except: return`; audit skip-guards too
A `continue` / `if x not in known: skip` inside a fetch loop drops data just as
silently as a swallowed except — and raises nothing. It becomes a bug when the
"known" set is built from an **over-narrow upstream scope**. The data is in the
API response; the guard throws it away.

```python
# BAD — goal_by_ad is built only from ACTIVE/PAUSED ads, so insights for ads of a
# paused/archived campaign (which the API DID return) are silently discarded.
for insight in api_ad_insights:
    if insight["ad_id"] not in goal_by_ad:
        continue            # looks like FK safety; actually scope-induced data loss
```

Audit checklist for any skip-guard:
- What populates the allowlist it checks against? Is that fetch scoped narrower
  than the data being filtered (status filter, date window, page limit)?
- If an item is skipped, is it logged/counted, or does it vanish silently?

Fix the **scope**, not the guard: e.g. broaden the upstream `effective_status`
allowlist so paused/`CAMPAIGN_PAUSED`/archived objects enter the known set.
(Meta ad-level insights, 2026-05-29.)

### Rule 7 — throttle handling must back off on ALL transient codes, and not retry-storm
Retrying only one rate-limit code lets the others hard-fail; conversely, a
bulk backfill that broadens scope can exhaust the account's business-use-case
budget, and **re-running harder pins the throttle score higher**.

- Retry the full transient set, not one code. Meta: `{4, 17, 32, 80004}` (app /
  user / page / ads-management) — exponential backoff, materialise cursors
  *inside* the retry (the SDK raises during `load_next_page`, not the initial call).
- Minimise call volume on backfills: gate optional per-item enrichment (e.g.
  `fetch_creatives=False` skips one API call per creative — data the consuming
  view never displays).
- Business-use-case throttle (80004) decays with idle time; the fix is to wait,
  not to retry-storm. A backfill failing on a 4th aggregate call should ideally
  persist per-chunk so a late throttle doesn't discard earlier successful rows.

(Meta full-history backfill, 2026-05-29.)

### Rule 8 — a derived-table refresh hook must run on EVERY write path
When a table is populated by aggregating another (e.g. `imusician_monthly_revenue`
rolled up from `imusician_sales_detail`), the roll-up hook must fire wherever the
source table is written — not just the path you happened to build it on.

iMusician has THREE import paths writing `sales_detail`: the Streamlit uploader
(`upload_csv.py`), the watcher DAG (`imusician_csv_watcher.py`), and the debug
script (`debug_imusician_csv.py`). The roll-up was added only to the Streamlit
path, so a DAG-driven import populated the detail table but left the derived
monthly table stale — the dashboard read ~5% of the real revenue with no error.

Audit checklist:
- Enumerate every writer of the source table (grep the table name, the parser,
  `upsert_many` calls). A view/KPI reads ONE table — confirm all writers refresh it.
- Put the refresh in a shared helper (`src/utils/imusician_rollup.py`) and call it
  from each path, best-effort (never fail the import on a roll-up error).
- Symptom signature: data present in the detail/source table, absent or stale in
  the view, no exception raised.

(iMusician monthly roll-up, 2026-05-29.)

### Rule 8 — one canonical writer per table (or reconcile)
Two collectors writing the same table silently corrupt it when their keys differ.
Meta breakdown tables had a legacy CSV path (`meta_insight_csv_parser`) AND the API
collector both writing `meta_insights_performance_country/placement/age`:
- the CSV emitted an aggregate `country='All'` total row → **+100% spend** on top of
  the real per-country rows (which the API also wrote);
- the CSV used French placement labels (`Reels Instagram`) while the API used
  snake_case (`instagram_reels`) → different conflict keys → both rows kept → double.

`upsert_many` is last-wins on its conflict key, so two writers only reconcile when
they use the **identical** key + label vocabulary. Otherwise rows accumulate and
`SUM()` inflates — with no error and no duplicate-key violation.

Audit checklist:
- For every table a view/KPI sums, `grep` all writers (collectors, transformers,
  watchers, CSV parsers). More than one writer? Verify identical conflict keys AND
  value vocabularies, or add a `source` column + reconciliation.
- Cross-check a grain against a known-good total (e.g. country-sum vs day-sum). A
  clean 2× (or N×) is the signature of an extra aggregate/duplicate writer.
- The durable fix for a redundant legacy writer is to **archive it** (one canonical
  source), not to keep patching both. Precedent: `archive/legacy_meta_csv/` —
  the whole legacy Meta CSV stack, superseded by `meta_ads_api_collector.py`.

(Meta dual-writer 2× inflation, 2026-05-29.)

## Files audited and status (as of 2026-03-25)

| File | Status |
|---|---|
| `src/collectors/spotify_api.py` | ✅ Fixed — get_artist_info, get_artist_top_tracks now raise |
| `src/collectors/youtube_collector.py` | ✅ Fixed — get_channel_stats, get_channel_videos, get_video_stats, get_video_comments, get_playlists now raise (2026-05-15: comments/playlists were missed in the 2026-03-25 pass, caught + fixed) |
| `src/collectors/soundcloud_api_collector.py` | ✅ Fixed — non-200 raises ValueError; outer except re-raises ValueError |
| `src/collectors/instagram_api_collector.py` | ✅ Fixed — 401/400 raise ValueError; generic raises RuntimeError |
| `src/collectors/meta_ads_api_collector.py` | ✅ Silent-correctness fixed (2026-05-28) — `results` now objective-driven via `_OBJECTIVE_RESULT_ACTION` (was hardcoded to `offsite_conversion.custom`, zeroing all engagement campaigns). 2026-05-29: scope-induced data loss fixed (Rule 6 — broadened `effective_status` per level so paused/archived ads' insights are kept) + throttle robustness (Rule 7 — `_meta_retry` over `{4,17,32,80004}`, `fetch_creatives` flag) + 36-month backfill clamp (#3018) |
| `airflow/dags/youtube_daily.py` | ✅ Fixed — zero-row guard after artist loop |
| `airflow/dags/spotify_api_daily.py` | ✅ Fixed — zero-row guard in collect_spotify_artists + collect_spotify_top_tracks |
| `airflow/dags/instagram_daily.py` | ✅ Fixed — precheck task; ig_user_id bug fixed |
| `airflow/dags/soundcloud_daily.py` | ✅ Fixed — precheck task; user_id propagated |

## When to re-run this audit
Run after adding any new collector or DAG. Check every `except` block in `src/collectors/`.
