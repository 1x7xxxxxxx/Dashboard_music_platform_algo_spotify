# Ops mail journal — what streaMLytics mailed, and what it meant

Type: Doc (appended by the assistant at the start of a session; the owner does not read these mails)
Uses: Gmail (Claude session connector) — **only** `from:noreply@streamlytics.fr`; nothing personal is read or kept
Persists in: this file

⚠️ **Two inboxes (measured 2026-09-26).** GitHub-side mails (CI break, security nightly, prod
health) reach the inbox read here. The production nightly mail (`alert_monitor`, now the
R181 recap) goes to `ALERT_EMAIL` on the server — another address, unreadable from here.

Why this exists: the owner does not read the automated mails, and some signals only exist
there. Each session starts by searching `from:noreply@streamlytics.fr newer_than:<since last
entry>`, and each mail is triaged here into one of: **real** (a defect — link its fix),
**expected** (a known state), **false alarm** (the mailer was wrong — link its fix),
**test** (a deliberate probe). A real or false-alarm row without a fix link is open work.

The last-entry date is read by `make night-status`, which says when the journal is stale.

| received (UTC) | subject | verdict | cause | fix / note |
|---|---|---|---|---|
| 2026-09-24 11:45 | Prod — Daily health check a échoué | expected | `api.streamlytics.fr` timed out: the Hetzner box was cut ~10 h for an unpaid invoice | memory `feedback_an_unreachable_server_check_the_account_first` |
| 2026-09-25 14:46 | Prod — Daily health check a échoué | test | `force_red` dispatch proving the red verdict is mailed | — |
| 2026-09-25 21:17–21:52 | Security — Nightly audit a échoué (×5) | expected | gitleaks: real secrets in public history awaiting rotation (R177) + jobs being repaired that evening | R177 closed 2026-09-25 ~23:55 — re-check the 2026-09-26 night |
| 2026-09-26 02:33 → 09:12 | CI a échoué (×4) | real, then false alarm | real: `.test_durations` missing new files, then `gold-coverage.md` stale; false: runs CANCELLED by a newer push counted as red | `14d9827` (cancelled ≠ red), `make test-durations-missing`, generated doc checked in pytest |
| 2026-09-26 10:23 | CI a échoué | real | new test file with no recorded duration (`49fa9e5`) | fixed by the next commit (`9324722`) |
| 2026-09-21 08:00 | [artiste1] Weekly KPI — N/A everywhere | expected | `artiste1` (id 17) is a test account with no data | — |
| 2026-09-26 11:27 | 📋 Récap de la nuit — nuit calme, rien à signaler | test | R181 end-to-end: `airflow tasks test alert_monitor send_consolidated_alert` in prod — delivered, but to `ALERT_EMAIL` = `1x7…@gmail.com`, NOT the inbox read here (`timothe.baudry137@…`) | ⚠️ the nightly mails have ALWAYS gone to another inbox — owner to point `ALERT_EMAIL` (prod `.env`) at the read inbox |
