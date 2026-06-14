# Prod health monitoring — 3 surfaces

Daily guarantee the live app is healthy. Each check lives where it can both *observe*
the thing and *alert* independently of it. Built 2026-06-14 (after the Cloudflare
edge incident proved internal-only checks miss edge regressions).

## Surface 1 — External (GitHub Actions, 06:00 UTC)
- `tests/test_prod_health.py` — pytest, runs only when `RUN_PROD_HEALTH=1` (skipped in
  normal CI so a push never hits prod). Probes the public endpoints **through Cloudflare**.
  - **A (no secrets):** dashboard 200 · `api/health` 200 · `/webhooks/stripe`≠403 (Stripe
    edge-block guard) · `/auth/token`≠403 · TLS cert > 14d · HTTPS redirect · security
    headers · `/openapi.json`+`/docs`→404.
  - **B (authenticated):** logs in as the `healthcheck` service account (GitHub secrets
    `HEALTHCHECK_USER` / `HEALTHCHECK_PASSWORD`) → asserts **no 500** on `/kpis`,
    `/youtube/videos`, `/streams/summary`, `/ml/predictions`. Catches prod-only schema
    drift the CI (canonical schema) structurally cannot. Skips if the secrets are absent.
- `.github/workflows/prod-health.yml` — `cron: 0 6 * * *` + `workflow_dispatch`. Red run
  → GitHub emails the owner.
- Run locally: `RUN_PROD_HEALTH=1 HEALTHCHECK_USER=… HEALTHCHECK_PASSWORD=… pytest tests/test_prod_health.py -v`
- `healthcheck` account: role=artist, verified, no 2FA, its own empty tenant (artist_id=10
  on prod). Created by DB INSERT (pgcrypto). Rotate: `UPDATE saas_users SET password_hash=
  crypt('<new>', gen_salt('bf')) WHERE username='healthcheck'` + `gh secret set HEALTHCHECK_PASSWORD`.

## Surface 2 — Internal DB (alert_monitor DAG, 23:00 UTC)
Two tasks added to the existing consolidated-alert DAG (one Brevo email, no new channel):
- `check_billing_sync` — Stripe subscriptions stuck (`past_due`/`incomplete`/`unpaid`) or
  `active` but `current_period_end` lapsed > 3 days (missed webhook).
- `check_row_anomalies` — daily-insert SPIKE: latest day > 10× trailing-7d avg (floor 100
  rows). Freshness already covers the no-data direction. Tables: `ANOMALY_TABLES` allowlist.

## Surface 3 — Internal host (tools/infra_health_cron.sh, 05:00 UTC)
Mirrors `schema_drift_cron.sh`; alerts via Brevo (`tools/notify_schema_drift.py`). Checks:
- **Backup freshness** — newest `backups/spotify_etl_*.sql.gz` < 25h old AND non-empty
  (would have caught the 2026-06-14 silent backup failure).
- **Disk** — `/` used% < 85.
- **Container liveness** — postgres / airflow_scheduler / dashboard / api all `running`
  (a DAG can't watch its own scheduler).
Cron: `0 5 * * * /opt/streamlytics/tools/infra_health_cron.sh >> /var/log/streamlytics-infra-health.log 2>&1`.
Test failure path: `BACKUP_MAX_AGE_H=0 tools/infra_health_cron.sh` (sends a real Brevo email).

## Deploy hygiene (root cause of a found incident)
`api`/`dashboard` images **COPY `src/` at build time** → a `git pull` without
`--build` leaves stale code running (this is how `/youtube/videos` 500'd in prod while
the checkout had the fix). Always deploy code with
`docker compose up -d --build <service>`. Surface 1B is the durable guard for the API.
