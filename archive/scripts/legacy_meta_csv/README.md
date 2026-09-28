# Legacy Meta CSV stack — ARCHIVED 2026-05-29

These 8 files implemented Meta Ads ingestion from **manually-exported CSVs**, before
the project migrated to the **Meta Ads API collector**
(`src/collectors/meta_ads_api_collector.py` + DAG `meta_ads_api_daily`).

They are archived (not deleted) because they are **fully superseded and were actively
corrupting data** — two writers on the same tables with incompatible conventions:

| Artifact | Caused by |
|---|---|
| `cg:` campaigns / `a:` ads duplicates | `meta_csv_parser` / `meta_csv_watcher` (config CSV) |
| `country='All'` / `placement='All'` aggregate rows (2× spend) | `meta_insight_csv_parser` total rows |
| French placement labels (`Reels Instagram`) duplicating API `instagram_reels` | `meta_insight_csv_parser` vocabulary |

Since the API collector populates **all** of `meta_campaigns / meta_adsets / meta_ads`
and every `meta_insights_*` table (campaign + ad + adset grain, perf + engagement),
this CSV path is redundant. Keeping it as the only other writer risked silent
double-counting on every re-run (see `.claude/skills/audit-collectors.md` REX 2026-05-29).

## Files
- `meta_config_dag.py` / `meta_csv_watcher.py` / `meta_csv_parser.py` — config (campaigns/adsets/ads)
- `meta_insights_dag.py` / `meta_insight_watcher.py` / `meta_insight_csv_parser.py` — insights/breakdowns
- `debug_meta_config.py` / `debug_meta_insights.py` — local debug runners

## Restore (if ever needed)
`git mv archive/legacy_meta_csv/<file> <original path>`. The DAGs use absolute
`from src.collectors...` imports, so move the collector/transformer back first.
But prefer extending the API collector instead — do **not** re-enable a second writer
to the Meta tables without a `source` column + reconciliation.
