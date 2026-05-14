# ML Checklist — Scope filtered for streamlytics

> Filtered subset of `unified_ml_checklist.md` (13 sections, 172 KB), keeping
> only what applies to a multi-tenant CRUD SaaS dashboard. Industrial / hardware
> / RL sections are deferred or rejected (cf. `docs/adr/ADR-002`).
>
> **How to use** : before starting a new ML-flavored brick, skim the relevant
> rows. For non-ML work (UI/DB/views/credentials), ignore this file entirely.

## Applicable sections

| § | Section | Streamlytics relevance |
|---|---|------------------------|
| 1 | Architecture & Use Case Matrix | ✅ Reference when picking algorithms in `machine_learning/ml_scoring_daily.py` |
| 2 | Data Preparation & EDA | ✅ Applies to S4A CSV ingestion + DataFrame validation in `src/transformers/` |
| 9.0 | ETL Pipeline | ✅ Direct map to Airflow DAGs in `airflow/dags/` |
| 9.0b | Data Pipeline Orchestration | ✅ Same — Airflow scheduler, retry policy, failure callbacks |
| 9.1 | Model Packaging | ⚠️ Partial — `machine_learning/` has file-based artifacts, no formal registry yet |
| 9.3 | Drift Detection | ⚠️ Open — no drift monitoring on scoring inputs today |
| 9.4 | Retraining Strategy | ⚠️ Manual trigger only via `views/trigger_algo.py`, no automated retrain |
| 9.5b | Model Validation Gates | ⚠️ Add gates in a future `ml-promotion.yml` if introduced |
| 10.1 | App Security | ✅ Already partially addressed (bcrypt, TOTP, SQL allowlist, rate limits) |
| 11 | Software Engineering — Architecture | ✅ Reference for future ADRs |
| 12 | Software Engineering — Data & Tests | ✅ Match against `tests/` patterns (mocked PostgresHandler) |
| 13 | Dev Env & Tooling | ✅ Reference for Makefile, venv, pre-commit, uv (Phase B already applied parts) |

## Sections deferred or rejected

| § | Section | Status |
|---|---|--------|
| 3 | Feature Engineering | ⏸️ Becomes relevant if/when the scoring pipeline grows custom features |
| 4 | Modeling & Optimization | ⏸️ Same |
| 5 | Evaluation & Interpretation (XAI) | ⏸️ Same |
| 6 | Dimensionality Reduction / Clustering | ⏸️ Same |
| 7 | Time Series & Deep Learning | ❌ streamlytics does no TS forecasting |
| 8 | Reinforcement Learning | ❌ Out of scope |
| 9.5c | Prometheus + Grafana | ❌ Rejected by ADR-002 |
| 9.6 | IPC Industrial Deployment | ❌ Not an industrial product |
| 9.11 | Disaster Recovery | ❌ Rejected by ADR-002 |
| 9.12 | Kubernetes | ❌ Hetzner VPS + Railway are enough |
| 10.2 | ML Fairness | ⏸️ No demographic-sensitive scoring yet |
| 10.3 | Adversarial Threats | ⏸️ No formal adversarial threat model yet |

## Open questions raised by the applicable rows (P3 backlog candidates)

→ **Detailed analysis** : `.claude/dev-docs/refactor-audit-mlops.md` walks
through 6 MLOps items with effort / risk / trigger conditions, after reading
the actual project ML code (5 XGBoost models, MLflow tracking already
in place, hardcoded `MODEL_PATHS` in `src/utils/ml_inference.py`).

TL;DR from that audit :

1. **Tests de non-régression ML** (rank 1, 1–2 h) — fixture-based pytest assertions on `score_all_songs()` output. Catches silent model swaps. Trigger : next time you touch a model or `FEATURE_COLUMNS`.
2. **Add `model_version` to `ml_song_predictions`** (rank 2, 30 min) — propagates `MODEL_VERSION` constant into the row so historical predictions are comparable across model bumps. Trigger : same as #1.
3. **§9.1b MLflow Registry** (rank 3, 2 h) — currently file-path-pinned in `MODEL_PATHS`. Registry adds value only when concurrent training runs or A/B testing emerge.
4. **§9.3 Drift detection** (rank 4, 4–6 h) — defer until a weird prediction triggers a "why ?" investigation. PSI per feature, weekly cron.
5. **§9.4 Automated retraining** (rank 6) — defer indefinitely while cadence < 1×/month.

The decisions here are NOT "yes do them" — they are "here is when each becomes
worth doing".

## What is NOT a checklist gap (deliberate)

Three "missing" items below are deliberate and reflect the ADR-002 trade-offs.
Don't reopen them without a new decision :

- No Prometheus + Grafana → tail `docker-compose logs` and email alerts.
- No automated DR rehearsal → Postgres volume backups are operator-driven.
- No domain/services/repository layers → `PostgresHandler` direct + `_ALLOWED_TABLES`.
