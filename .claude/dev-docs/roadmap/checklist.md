# Master Roadmap Checklist

Single source of truth for all bricks and open bugs.
Updated by `strategic-plan-architect` background agent.
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

---

## 🔖 REPRISE — état au 2026-06-13 (à lire EN PREMIER au `/resume`)

**streaMLytics est EN PRODUCTION et lançable.** (détail : `[[project_production_deploy]]`, DEVLOG suites 7→14)

- 🌐 **Live** : https://streamlytics.fr (HTTPS Let's Encrypt · Hetzner **CPX32** Nuremberg `167.233.92.1` · `ssh root@167.233.92.1` via clé WSL `~/.ssh/id_ed25519` · code à `/opt/streamlytics`). Durci (ufw 22/80/443, fail2ban, SSH key-only), backup cron `pg_dump` 3h, postgres `restart: unless-stopped`.
- 💳 **Stripe** : **mode LIVE PROUVÉ end-to-end (2026-06-13)** — KYC validé, 4 env vars live sur le serveur, vrai paiement carte → webhook → `tier=premium` + annulation OK. Portail client actif. (détail : `[[project_stripe_state]]`)
- 👤 **Funnel d'inscription** : **COMPLET et validé en prod** (Brevo → inbox, login par **email** OU username, vérif instantanée, welcome + **2 PDF guide FR/EN** en PJ). Pré-requis **E1 validés**.
- ⚙️ **DAGs** : tous **activés** (étaient en pause par défaut !) → collecte quotidienne par artiste (Meta 5h/Spotify 7h/YT 8h/SC 9h/IG 10h/ML 11h UTC ; CSV watchers 15 min). Si Airflow recréé → ré-`unpause`.
- 🔌 **API REST** : **fonctionnelle en prod** (auth DB `saas_users`, lockout partagé, 2FA refusé, tenant-scoped). `POST /auth/token` → JWT.
- ⚙️ Déploiement = sur le serveur `cd /opt/streamlytics && git pull --ff-only origin main && docker compose up -d --build dashboard` (ou `api`). Compte test QA supprimé.

**▶️ Prochaines actions, dans l'ordre (MAJ suite 19c — Cloudflare ACTIF + durci) :**
1. **✅ Cloudflare — ACTIF, PROXIFIE & DURCI (complet)** (détail `[[project_security_cloudflare]]`). Fait : zone active, NS Cloudflare, **SSL Full(strict)**, zone settings (min TLS 1.2 / Always HTTPS / Brotli / TLS 1.3), **rate-limit `/auth/token`** (10/10s), **firewall origine verrouillé** (ufw → IP CF only, vérifié), **Bot Fight Mode** ON, **cert Origin CF 15 ans** posé sur Caddy (plus de risque renouvellement, vérifié 2 edges). **RESTE (non bloquant)** : 🔑 **révoquer le token** `streamlytics-hardening` ; (optionnel) ré-activer DNSSEC via CF. ⚠️ vérifs prod **toujours via `curl --resolve host:443:<edge-CF-IP>`** (cache DNS local peut pointer l'IP origine firewallée → faux « down »).
2. **✅ Red-team — COMPLET** (réseau + app + dashboard). Couvert & clean : MITM/TLS (CVE suite), brute-force, SQLi, deps (0 CVE), **isolation tenant/IDOR (prouvé live)**, priv-esc, JWT, CORS, secrets, XSS (escaping tient), **replay webhook Stripe** (signature + handlers idempotents + tolérance 5 min), upload path-traversal (filename = détection seulement), app-DoS (cap 50 Mo + bornes `le=1000` + Cloudflare). **Trouvé+fixé+déployé** : `/kpis` & `/youtube/videos` schema-drift 500 (suite 18/19b) ; **CSV/Excel formula injection sur export (CWE-1236, suite 20)** → `defang_formulas()` sur les 3 chemins d'export + test. Mineur restant : XSRF/cookies Streamlit = défaut framework (P4). Compte test `redteam_qa` **supprimé (clôturé suite 20)**. Classes cataloguées : `api-router-schema-drift`, `csv-formula-injection` (`error-classes.md`).
3. **Ouvrir E1** — inviter 2-3 proches sur `streamlytics.fr` (tout le funnel + paiement live sont validés).
4. *(optionnel)* Stripe : prix doublon **confirmé supprimé via API** (1 prix actif). *(i18n emails ✅ s16 ; env-first 11 `*_schema.py` ✅ s15 ; **`/kpis` 500 fixé+déployé ✅ s18**.)*

*Session 2026-06-13 (suites 12→14) : Stripe live prouvé ; 4 bugs corrigés (nav login-bounce #46, date période #47, fuite fraîcheur Spotify #48, « Aucun DAG trouvé »/AirflowMonitor env-first #53) ; audit isolation tenant (#49 : `require_artist_scope` + P3) ; `/ml/predictions` réparé & P4 fermée (#50) ; cadence freshness #51 ; **Postgres-en-CI #52 (P3 fermée, render-smoke 39 vues en CI)** ; pentest A-D (#54 `/openapi.json` fermé) ; DAGs activés ; **API REST fonctionnelle en prod #56** ; analyse d'impact config/prod = classe « config.yaml absent » entièrement contenue sur le chemin runtime.*

---

## 📋 Tâches ouvertes (index — détail plus bas)

Tableau concis de TOUTES les tâches encore ouvertes (`- [ ]`). À la complétion d'une
tâche : `/roadmap-done <id>` la coche dans son bloc détaillé ET la retire de ce tableau
vers `## Completed` (CLAUDE.md — flux roadmap). Une seule source : ce fichier.

| id | tâche | prio | statut / déclencheur |
|----|-------|------|----------------------|
| R1 | E1 — beta privée avec des proches sur `streamlytics.fr` | P3 | **actionnable maintenant** (funnel + paiement live validés) |
| R2 | E2 — landing marketing + pixel Meta + CAPI server-side | P3 | après R1 |
| R3 | 2 collectors `return None` (instagram `:294`, youtube `:45`) — escalader en `raise` ou documenter skip légitime | P2/P3 | skip par-item, PAS le pattern dangereux ; à trancher |
| R4 | More training data + évaluation per-tenant (ML) | P3 | BLOQUÉ : 1 seul tenant live, volume de labels |
| R5 | Retraining automatique sur outcomes live (ML) | P3 | BLOQUÉ : outcomes forward s'accumulent dans le temps |
| R6 | RR volume regressor (R²=0.23) | P3 | BLOQUÉ : volume d'entraînement, pas features |
| R7 | Resurrection tuning (`detect_saves_resurrection`) | P3 | BLOQUÉ : besoin d'une série temporelle de saves |
| R8 | Caching `@st.cache_data(ttl=300)` sur 4 vues lourdes | P4 | DIFFÉRÉ — déclencheur : trafic concurrent / re-renders |
| R9 | Migration `view_session()` (16 vues legacy `get_db_connection()`) | P4 | DIFFÉRÉ — déclencheur : ≥50 artistes / leak connexion |
| R10 | Splitter god-functions (+171 fonctions >40 l.) | P4 | DIFFÉRÉ — **au fil de l'eau**, jamais en sweep dédié |
| R11 | Lazy imports (plotly/sklearn/shap → dans les fonctions) | P4 | DIFFÉRÉ — déclencheur : latence par-vue ressentie |
| R12 | Index composite `s4a_song_timeline(artist_id, song, date)` | P4 | DIFFÉRÉ — déclencheur : ~10× le volume (≈140k l.) |

*Décidé/clos mais checkbox encore cochable dans le détail (pas des tâches actives) :
C5 (benchmark VPS) + C6 (domaine) **DÉCISIONS FIGÉES** → `benchmark-deployment-synthesis.md` ;
D (déploiement + pentest) **FAIT** (prod live + red-team complet). Cocher via `/roadmap-done` au prochain passage.*

---

## Open Bugs

### 🔍 Audit 2026-06-13 — deep multi-dimension (suite 19)

Audit profond post-red-team (perf · correctness · supply-chain · tests · tech-debt), **vérifié en live contre le schéma + données prod**. **Bilan : 1 vrai bug prod + 1 gap de test systémique ; le reste = tech-debt P4 basse urgence. Aucun nouveau risque sécurité/critique.**

**P3 — CORRIGÉ (suite 19b, déployé + vérifié live) :**
- [x] **`/youtube/videos` API cassé (HTTP 500) — schema drift, MÊME CLASSE que `/kpis`** — sélectionnait `views/likes/comments/title` sur `youtube_video_stats` (vraies colonnes `view_count/like_count/comment_count`, pas de `title`). **FIXÉ** : requête sur `youtube_videos` (catalogue par-vidéo : title + view_count/like_count/comment_count). Mergé PR #62, déployé, `/youtube/videos` = **200** confirmé live. *(8 routers audités, youtube était le dernier cassé.)*
- [x] **Gap de test systémique = cause racine `/kpis` + `/youtube`** — les 2 bugs avaient échappé aux tests (routers testés **DB mockée**). **FIXÉ** : `tests/test_api_db_smoke.py` — smoke-test **DB-gated** (comme `test_views_render_smoke`) qui exécute chaque endpoint data contre le vrai schéma (token admin+tenant forgé) et assert no-500 → attrape toute la classe en CI. Aurait fait échouer /kpis ET /youtube.

**P3/P4 — correctness borderline :**
- [ ] **2 collectors `return None`** — `instagram_api_collector.py:294` (insights code-100 non-supporté, skip 1 média) et `youtube_collector.py:45` (chaîne introuvable). Skips **par-item**, PAS le pattern dangereux « swallow → 0 rows → DAG SUCCESS ». Décider : escalader en `raise` (rule #6 stricte) ou documenter comme skip légitime. Effort S · confiance MED.

**P4 — tech-debt / opportunités (basse urgence) :**
- [ ] **Caching** — 4 vues requêtent la DB sans `@st.cache_data` (`spotify_s4a_combined`, `meta_ads_overview`, `export_pdf/csv`, `usage_analytics`). Bénéfice **modeste** à l'échelle actuelle (requêtes <1ms mesurées) ; vrai levier LCP = cache Cloudflare (en cours). Effort M.
- [ ] **`view_session()` migration** — 16 vues encore en `get_db_connection()` legacy (valide mais non-conforme rule #9). Tech-debt, **pas un leak**. Effort M.
- [ ] **171 fonctions >40 lignes** (règle projet) — surtout des `show()` Streamlit (jusqu'à 502 l. `meta_ads_overview`). Lisibilité. Effort L. (cf. `refactor-audit-dashboard.md`)

**Mesuré & ÉCARTÉ (FP / non pertinent — ne pas re-auditer) :**
- Index `s4a_song_timeline(artist_id, song, date)` → **prématuré** : EXPLAIN ANALYZE = **0.4ms** sur 13794 lignes via l'index `(artist_id,date)` existant. Revisiter à ~10× volume.
- `API_SECRET_KEY` → **SET (64 chars) en prod** : JWT stables au restart, non-issue.
- Sweep schema-drift : 132 candidats bruts → **tous FP sauf le router youtube** (alias `col AS x`, vars f-string `{filt}/{frag}`, fonctions SQL, littéraux, commentaires FR, ON CONFLICT/EXCLUDED).
- Deps `uv.lock` **0 CVE** ; imports morts **0** (ruff F401) ; data-integrity (filtre 1x7 / scoping tenant / clés upsert) **clean** ; secrets git history **0**.

### 🚀 Base d'optimisation différée (P4 — déclencheur : ÉCHELLE, pas maintenant)

**FAIT (gratuit, via Cloudflare, ROI élevé, zéro risque)** : cache edge du bundle JS Streamlit (`cf-cache-status: HIT` → attaque le LCP 5.7s), **HTTP/3 + Early Hints + 0-RTT**, Brotli, min TLS 1.2. → *Le vrai levier perf (livraison) est en place.*

**DIFFÉRÉ — à réévaluer à ≥ ~50 artistes actifs / trafic multi-tenant concurrent réel.** Sur la prod actuelle (mono-tenant sain, requêtes <1ms), ces items sont **faible ROI + risque de régression** → on ne refactore pas pour des micro-gains. Cataloguées dans `error-classes.md` (`view-session-adoption`, etc.) + visibles dans graphify (god-nodes).

- [ ] **Caching `@st.cache_data(ttl=300)` sur les 4 vues lourdes** (`spotify_s4a_combined`, `meta_ads_overview`, `export_pdf/csv`, `usage_analytics`). *Gain* : évite la re-requête à chaque rerun Streamlit. *Risque* : cacher la donnée pure (pas `db`/connexion → unhashable), staleness TTL. *Déclencheur* : trafic concurrent / re-renders fréquents ressentis. Effort M.
- [ ] **Migration `view_session()` (16 vues legacy `get_db_connection()`)** — classe `view-session-adoption`. *Gain* : robustesse connexions (graphify : `get_db_connection` = 57 edges). *Risque* : refactor mécanique 16 fichiers = régression. *Déclencheur* : ≥50 artistes / si un leak de connexion apparaît. Effort M.
- [ ] **Splitter les god-functions** (`collect_report_data()` = 69 edges, + 171 fonctions >40 l. règle projet). *Gain* : lisibilité/maintenabilité, **pas perf**. *Risque* : élevé si fait en masse. *Déclencheur* : **au fil de l'eau** quand on touche déjà le fichier (jamais en sweep dédié). Effort L.
- [ ] **Lazy imports** (plotly/sklearn/shap en tête de vue → différer dans les fonctions). *Gain* : cold-start par vue. *Risque* : faible mais large. *Déclencheur* : si latence par-vue ressentie. Effort M.
- [ ] **Index composite `s4a_song_timeline(artist_id, song, date)`** — **prématuré aujourd'hui** (mesuré 0.4ms / 13794 lignes). *Déclencheur* : **~10× le volume de données** (≈140k lignes) ou EXPLAIN qui régresse. Effort S.

### P1 — Blocking (data missing or crash)

- [x] **SoundCloud + Instagram DAGs** — fixed 2026-03-30.
  SoundCloud: infinite pagination loop (manual offset ignored `next_href`) → cursor-based pagination + `max_pages=200` cap.
  Instagram: Meta API v18.0 deprecated Sept 2025 → centralized to `META_GRAPH_BASE_URL` (v24.0) via `src/utils/meta_config.py`; fresh personal token with ~56 days validity entered via Credentials page.
- [x] **`meta_campaigns` schema incomplete** — DB has 5 columns, `meta_ads_schema.py` expects 11.
  Fix: applied in `migrations/002_schema_fixes.sql`.
- [x] **DAG health audit** — completed 2026-03-23. Summary:
  | DAG | Schedule | Last run | State | Note |
  |-----|----------|----------|-------|------|
  | apple_music_csv_watcher | 15min | 2026-03-23 | ✅ success | No CSVs to process |
  | data_quality_check | daily 22h | 2026-03-21 | ⚠️ partial | `check_meta_ads_freshness` fails → empty meta_campaigns |
  | instagram_daily | daily 10h | 2025-12-11 | ❌ all failed | Expired credentials (P1) |
  | meta_csv_watcher_config | 5min | 2025-12-08 | ✅ last was ok | Not collecting (no new CSV files in watch dir) |
  | meta_insights_watcher | 5min | 2025-12-09 | ✅ last was ok | Same — idle since Dec 2025 |
  | ml_scoring_daily | daily 6h | — | ❌ paused | `dbname` bug fixed; unpause via UI |
  | s4a_csv_watcher | manual only | 2025-11-23 | ✅ success | schedule_interval=None, manual trigger needed |
  | soundcloud_daily | daily 9h | 2025-12-11 | ❌ all failed | Expired credentials (P1) |
  | spotify_api_daily | manual only | 2025-11-23 | ✅ success | schedule_interval=None, manual trigger needed |
  | youtube_daily | manual only | 2025-11-30 | ✅ success | schedule_interval=None, manual trigger needed |

### P2 — Data Integrity

- [x] **`meta_insights` UNIQUE(ad_id, date)** — missing `artist_id` → collision risk between artists.
  Fix: applied in `migrations/002_schema_fixes.sql`; DAG and view queries already filter by `artist_id`.
- [x] **`apple_songs_history` no `artist_id`** — data shared across all artists.
  Fix: migration in `migrations/002_schema_fixes.sql`; table added to `apple_music_csv_schema.py`; DAG and view queries updated.
- [x] **`meta_x_spotify.py` autocommit bypass** — lines 38–44 use `db.conn.cursor()` + `db.conn.commit()`.
  Fix: replace with `db.execute_query()` calls.
- [x] **`s4a_song_timeline` null artist_id** — rows created before migration may have `artist_id IS NULL`.
  Fix: applied in `migrations/002_schema_fixes.sql`.
- [x] **`ml_scoring_daily` DAG paused** — ML scoring not running automatically.
  Fix: `dbname` → `database` typo in DAG fixed. 16 `.ubj` model files confirmed present. Unpause via Airflow UI (http://localhost:8080).
- [x] **CSV import — validation before upsert** — `upload_csv.py` watcher inserts files without feedback or `artist_id` check.
  Fix: add pre-upsert validation step: row count, expected column names, detected/prompted `artist_id`; surface result in UI before writing to DB.
- [x] **PostgreSQL schema coherence audit** — completed 2026-03-23. 5 errors fixed:
  - `hypeddit.py`, `soundcloud_api_collector.py`, `instagram_api_collector.py`, `meta_csv_watcher.py`, `meta_insight_watcher.py` — all `db.conn.commit()/rollback()` calls removed (ProgrammingError with autocommit=True).
  - `hypeddit_schema.py` — 5 indexes missing IF NOT EXISTS, fixed.
  - `spotify_s4a_combined.py` — freshness query now filtered by artist_id.
  - `pdf_exporter.py` — 4 song-level queries now include 1x7 filter.
  Remaining warnings (non-blocking): youtube_channel_history/video_stats no UNIQUE, bootstrap gap (24 tables not in init_db.sql), provide_context deprecation in data_quality_check.
- [x] **Release-date filter standardized across all views** — filter by earliest release date (`MIN(date)`) is implemented on S4A/Apple/SoundCloud/Meta but missing on YouTube and inconsistent elsewhere.
  Fix: apply the same `track`/`song` release-date filter in all views; extends the YouTube-specific item (moved from P3).

### P3 — UX / Features

- [x] **SHAP/LIME explanations + marketing levers** — `trigger_algo.py` shows raw feature JSON but no SHAP values. Extend: display SHAP feature importances for the most recent track with marketing interpretation labels ("Increase saves", "Boost week-1 streams", etc.).
- [x] **`data_quality_check` DAG** — last run Dec 2025, status unknown. Verify if failing or just not scheduled.
- [x] **User onboarding doc (PDF)** — extend to a printable PDF checklist: run Docker, launch Streamlit, connect credentials, trigger a DAG, upload a CSV, read KPIs. Deliverable: PDF exportable from the app or standalone file.
- [x] **DAG run log dashboard** — dedicated view listing last run per DAG: status, duration, rows inserted, email alert on failure. Distinct from existing failure-callback emails (Brick 11).
- [x] **Budget tracker in trigger_algo** — in `trigger_algo.py`, show estimated cost per playlist submission (Groover/Fluence rates) and remaining budget from a value stored in DB or entered by user.
- [x] **Rename "iMusician" → "Distributeur" in UI** — update nav menu labels, page titles, and UI strings in `imusician.py` / `imusician_schema.py`. Do not rename DB tables or files (would be a regression).
- [x] **View optimization audit** — review all views for N+1 queries, deprecated `use_container_width` calls, unused columns, unnecessary re-renders.
  Action: run `/review-architecture`.

### P4 — Tech Debt

- [x] **`PostgresHandler` accept `DATABASE_URL`** — prerequisite for Railway deployment (Brick 15).
- [x] **`.github/workflows/ci.yml`** — ruff + pytest in CI (~20 lines).
- [x] **Tests for `csv_exporter.py`** — mock `db.fetch_df`, verify ZIP contains correct files.
- [x] **Export CSV: table selection** — allow checking/unchecking sources before ZIP download.
- [x] **Remove stale SQL views** — `view_soundcloud_latest`, `view_instagram_latest` replaced by DISTINCT ON in Python. DROP applied in `migrations/002_schema_fixes.sql`.
- [x] **`use_container_width` audit** — check `meta_ads_overview.py`, `instagram.py`, `youtube.py`, `hypeddit.py`, `spotify_s4a_combined.py`.

### P2 — Data Integrity (new)

- [x] **Multi-tenancy — artist_id propagation in all collectors** (Brick 20)
  Collectors hardcode `artist_id = 1` in INSERT statements. DAGs don't iterate all active artists.
  Fix: add `artist_id` param to `SoundCloudCollector`, `InstagramCollector`, `MetaAdsWatcher`, `MetaCSVWatcher`; update DAGs to loop via `get_active_artists()`; scope DELETE queries by `artist_id`.
  Files: `soundcloud_api_collector.py`, `instagram_api_collector.py`, `meta_insight_watcher.py`, `meta_csv_watcher.py`, `soundcloud_daily.py` (already OK), `instagram_daily.py`, `youtube_daily.py`, `spotify_api_daily.py`, `meta_insights_dag.py`, `meta_config_dag.py`.

### P3 — UX / Features (new)

- [x] **Scheduled email reports** — `airflow/dags/weekly_digest.py`, every Monday 08:00 UTC. One HTML email per active artist: S4A streams delta, top song, Meta spend/CTR, Instagram delta, SoundCloud delta, ML top prediction. Requires SMTP_USER/SMTP_PASSWORD/ALERT_EMAIL env vars.
- [x] **Stripe integration** (Brick 21) — `subscription_plans` + `artist_subscriptions` tables in `stripe_schema.py` + `migrations/004_stripe_billing.sql`; `POST /webhooks/stripe` in `src/api/routers/stripe_webhook.py` (handles checkout.session.completed, subscription.updated/deleted, invoice.payment_failed); `get_artist_plan()` + `require_plan()` in `auth.py`; billing page `views/billing.py` (current plan, MRR admin view, plan comparison, upgrade links). Requires STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_CHECKOUT_URL, STRIPE_PORTAL_URL env vars.
- [x] **PDF report expansion** — `pdf_exporter.py` extended with 6 new sections: S4A top songs, YouTube, Instagram, Meta Ads, SoundCloud tracks, Apple Music. `songs_filter` parameter added to `_collect_s4a_top_songs`, `collect_report_data`, `generate_pdf`. `export_pdf.py` adds S4A song selector with "Toutes" checkbox.
- [x] **Excel export** — `csv_exporter.py` gains `export_excel()` (openpyxl, multi-sheet). `export_csv.py` adds format selector (ZIP vs Excel).
- [x] **SoundCloud track selector UX** — track list sorted by `first_seen DESC`; defaults to the latest release (`[:1]`).
- [x] **Data Wrapped multi-tenant fix** — admin query no longer filters `active=TRUE`; non-admin loads real artist name from DB instead of hardcoded value.
- [x] **Data Wrapped gains → percentages** — `artist_wrapped` 4 `*_gain` columns (INTEGER/BIGINT) renamed to `*_gain_pct` and widened to `DECIMAL(7,2)` via idempotent `migrations/033_wrapped_gains_pct.sql` (guarded RENAME + TYPE widening). `data_wrapped.py` form inputs now signed `%` `number_input`s (`_fmt_pct` helper, `_bar_gain_chart` `fmt_fn` param, "(%)" titles, "△ X %" rename_map); `wrapped_schema.py` canonical CREATE TABLE updated for fresh installs.
- [x] **Data Wrapped "top" metric → super-fans + combined chart** — the old `top_artist_name` (VARCHAR) + `top_artist_fan_pct` (DECIMAL) modelled a *similar artist*; replaced by the artist's OWN super-fans `top_fans_count INTEGER` + `top_fans_rank INTEGER` (fans who ranked the artist in their top N) via idempotent `migrations/034_wrapped_top_fans.sql` (ADD IF NOT EXISTS + DROP IF EXISTS; applied to live DB, artist_id=1/2024 row preserved + backfilled to 11/rank 5). `wrapped_schema.py` updated. `data_wrapped.py`: 4 absolute line charts merged into one `_multi_line_chart` with per-tab linear/log `st.toggle`; 4 gain % bars regrouped under "Gains annuels (%)"; new "Super-fans" line+table replaces "Top artiste similaire"; `_load_row_for_year` refactored to `fetch_df().iloc[0].to_dict()` (robust to DROP/ADD column reordering). ref: DEVLOG#2026-05-29.
- [x] **Billing page env fix** — `billing.py` replaced `st.secrets` with `os.getenv` for STRIPE_CHECKOUT_URL and STRIPE_PORTAL_URL (fixes crash when Streamlit secrets file absent).
- [x] **WeasyPrint → xhtml2pdf migration** — `pdf_exporter.py` and `requirements.txt` switched from WeasyPrint to `xhtml2pdf>=0.2.11` (eliminates system-level GTK/Pango dependency).
- [x] **SMTP config fix** — `.env` corrected: SMTP_HOST was set to an email address (now `smtp.gmail.com`); SMTP_PORT moved to its own line.

### P4 — Tech Debt (new)

- [x] **CSV upload audit log** — `csv_upload_log` table (migration 025): filename, artist_id, platform, row_count, status, error_message, imported_at. Logged after every upsert in `upload_csv.py`; audit failure never blocks UI.

- [x] **`init_db.sql` bootstrap gap** — 26 missing tables appended (S4A, Meta Ads, Meta Insights ×10, YouTube ×6, Apple Music ×4, Hypeddit ×2). Fresh install is now self-contained.
- [x] **YouTube UNIQUE constraints** — `UNIQUE(artist_id, channel_id, collected_at::date)` and `UNIQUE(artist_id, video_id, collected_at::date)` added to `youtube_schema.py` + `migrations/003_youtube_unique.sql`.
- [x] **`provide_context` deprecation** — removed `provide_context=True` from all 4 `PythonOperator` instances in `data_quality_check.py`. Functions already accept `**context`.

### P3 — UX / Features (new, 2026-03-27)

- [x] **Meta Ads credential onboarding guide** — step-by-step guide with screenshots for each artist to configure Meta credentials in the dashboard.
  Spec: (1) generate a long-lived User Access Token from Business Manager → System Users (not a personal token); (2) token must have `ads_read` + `ads_management` scopes; (3) account_id = numeric ID from `/me/adaccounts` (no `act_` prefix — the dashboard adds it); (4) artists do NOT create their own app — they use ETL_DASHBOARD_SPOTIFY as OAuth client; (5) link ad account to the app in Business Manager → App Settings → Business Assets.
  Deliverable: dedicated doc in `.claude/dev-docs/` + in-app help tooltip on Credentials page.

### P2 — Data Integrity (new, 2026-03-27)

- [x] **Instagram System User token — activation** — code-side ready (DAG `meta_token_refresh` skip `expires_at=NULL`, collector ne touche plus à `os.environ`). Activation par tenant = acte opérationnel décrit dans `.claude/dev-docs/meta-ads-credential-guide.md` ; suivi par artiste, pas par roadmap.
- [x] **Instagram + Meta System User token migration** (Brick 24) — migrate from personal 60-day tokens (expired Dec 2025) to System User tokens (never expire).
  Changes: `meta_token_refresh.py` skips artists with `expires_at=NULL` instead of attempting `fb_exchange_token` (which fails on System User tokens); `instagram_daily.py` precheck error message updated; `_guide_meta()` extended with Instagram scopes (`instagram_basic`, `instagram_manage_insights`, `pages_show_list`); `meta-ads-credential-guide.md` updated with token refresh behavior table.
  Note: Spotify/YouTube/meta_token_refresh DAGs were already scheduled in previous bricks — no schedule changes needed.

### P1 — Security (new, 2026-03-27)

- [x] **`get_artist_id()` default was `1` instead of `None`** — session non-hydratée queryait silencieusement l'artiste 1. Fix: `auth.py` default → `None`.
- [x] **`get_artist_id() or 1` dans 9 vues** — isolation tenant cassée pour les admins (None coercé sur artiste 1). Fix: guard explicite `if artist_id is None: if not is_admin(): st.stop()` dans `apple_music.py`, `instagram.py`, `soundcloud.py`, `youtube.py`, `meta_ads_overview.py`, `meta_cpr_optimizer.py`, `meta_creatives.py`, `meta_x_spotify.py`, `hypeddit.py`.
- [x] **f-string SQL avec `where_clause` interpolé — `meta_ads_overview.py`** — fragment WHERE interpolé dans 5 requêtes via f-string. Fix: suppression de la variable `where_clause`; chaque requête construite explicitement avec `_campaign_in`.
- [x] **f-string SQL avec identifiants table/colonne — `freshness_monitor.py` + `kpi_helpers.py`** — noms de table et colonne interpolés sans validation. Fix: allowlists `_ALLOWED_TABLES` / `_ALLOWED_COLS` validées avant interpolation.
- [x] **Secrets réels dans `config/config.yaml`** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.

### P1 — Security (2026-03-28 — full OWASP + RGPD hardening)

- [x] **CRITICAL-02: SQL injection in `postgres_handler.py`** — `insert_many()` / `upsert_many()` used f-string table/column interpolation. Fix: `_ALLOWED_TABLES` frozenset + `_VALID_IDENTIFIER_RE`; all queries rewritten with `psycopg2.sql` composition.
- [x] **CRITICAL-03: SQL injection via `artist_id_sql_filter()` table alias** — alias not validated. Fix: `_ALIAS_RE = re.compile(r'^[a-z_][a-z0-9_]*$')` in `auth.py`.
- [x] **CRITICAL-04: Campaign filter IDOR in `meta_ads_overview.py`** — user-supplied campaign IDs not validated against DB. Fix: allowlist check against fetched campaign list.
- [x] **CRITICAL-05: Fernet key on disk** — `credentials.py` read FERNET_KEY only from config.yaml. Fix: `os.getenv('FERNET_KEY')` first, config.yaml as local-dev fallback.
- [x] **CRITICAL-06: Token written to `os.environ` in `instagram_api_collector.py`** — exposed to all child processes. Fix: removed the assignment entirely.
- [x] **HIGH-01: No brute-force protection** — unlimited login attempts. Fix: `failed_login_attempts` + `locked_until` in DB (migration 017); 5 failures → 15-min lockout.
- [x] **HIGH-02: Email enumeration on unverified login** — error message revealed whether email existed. Fix: generic message; email looked up only on "Resend" button click.
- [x] **HIGH-04: Weak password policy** — minimum 8 chars only. Fix: 10 chars + 1 letter + 1 digit enforced in both `auth.py` and `register.py`.
- [x] **HIGH-05: Hardcoded `'admin'` default in AirflowTrigger** — unauthenticated DAG triggering possible. Fix: `RuntimeError` raised if `AIRFLOW_PASSWORD` is falsy.
- [x] **HIGH-06/07: Stored XSS via `unsafe_allow_html`** — DB values interpolated unescaped in `etl_logs.py` and `home.py`. Fix: `html.escape()` on all interpolated values.
- [x] **MEDIUM-01: Session fixation** — session state not cleared on login. Fix: `st.session_state.clear()` before `_hydrate_session()`.
- [x] **MEDIUM-02: Plan gate bypass** — `require_plan()` returned `False` instead of stopping. Fix: `st.stop()` after error.
- [x] **MEDIUM-05: TOCTOU on single-use promo codes** — concurrent registrations could exhaust code without guard. Fix: atomic `UPDATE ... WHERE uses_count < max_uses RETURNING id`.
- [x] **INFO-01: Email verification tokens never expire** — link valid indefinitely. Fix: 48h expiry check in `_verify_email()`; expired token cleared from DB.
- [x] **INFO-02: Secret key names logged at INFO level** — `credential_loader.py` logged key name in update messages. Fix: `logger.debug()` with key name removed.
- [x] **INFO-04: SSRF via open redirects in outbound requests** — 5 `requests` calls in `credentials.py` without `allow_redirects=False`. Fix: `allow_redirects=False` on all 5.
- [x] **INFO-06: No upload size cap** — Streamlit allowed arbitrarily large file uploads. Fix: `.streamlit/config.toml` with `maxUploadSize = 50`.
- [x] **RGPD Art. 5(1)(f): Marketing export not audited** — no record of admin personal data access. Fix: `admin_audit_log` write on download button click in `admin.py`.
- [x] **CRITICAL-01: Credential rotation** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.
- [x] **Task #11: Update all dev-docs with security session** — DEVLOG.md, retro.md, checklist.md updated to reflect the full 2026-03-28 security hardening session (Brick 25: OWASP + RGPD). All implemented items documented.

### P2 — Data Integrity (new, 2026-03-27 — audit)

- [x] **Collecteurs silencieux — `instagram_api_collector.py` + `soundcloud_api_collector.py`** — `except Exception → self.db = None` permettait un run complet à 0 lignes avec DAG SUCCESS. Fix: suppression du try/except autour de `PostgresHandler.__init__`; échec DB = exception levée.
- [x] **`spotify_api.py` `search_artist()` retournait `None`** — au lieu de `raise` sur API error ou artiste introuvable. Fix: `ValueError` si aucun artiste trouvé, `raise` dans le bloc `except`.
- [x] **Validation email trop permissive dans `register.py`** — `'@' not in email` acceptait `a@`, `@b`, `@@`. Fix: `re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email)`.

### P3 — Performance (new, 2026-03-27 — audit)

- [x] **`get_artist_plan()` ouvrait 2–3 connexions DB par render** — fallback `db2` ouvert séparément. Fix: 1 seule requête avec LEFT JOIN `saas_artists ↔ artist_subscriptions ↔ subscription_plans`; promo + subscription + tier résolus en 1 round-trip. (`auth.py`)
- [x] **`get_source_freshness()` — 7 requêtes séquentielles** — 1 `SELECT MAX()` par source à chaque chargement de la home. Fix: remplacé par 1 `UNION ALL` query. (`kpi_helpers.py`)
- [x] **Index composites manquants** — `migration/016_performance_indexes.sql` ajoute 4 index : `s4a_song_timeline(artist_id, date DESC)`, `soundcloud_tracks_daily(artist_id, track_id, collected_at DESC)`, `meta_insights_performance_day(artist_id, day_date DESC)`, `track_popularity_history(artist_id, date DESC)`.

### P2 — Data Integrity (new, 2026-03-30)

- [x] **Meta Ads DAG first-run backfill** — DONE 2026-06-01. Token blocker resolved 2026-05-31 (expired personal token `code 190` → valid System User token, `type=SYSTEM_USER`/`expires_at=0`, `expires_at` NULL in DB). Rate-limit blocker resolved 2026-06-01: the `code 80004` BUC throttle was purely a concurrency/quota-exhaustion artefact (multiple runs hammering the same ad-account — confirmed live: an over-eager session fired scheduled + 2 daily manual + a full_history run, and the full_history run wall-throttled on the per-creative content fetch for ~26 min, then was killed). **Fix that worked:** stopped all Meta activity, let the account quota cool ~60 min, triggered ONE solo `full_history` run on a rested quota → completed in ~4 min with **zero throttle**: 34 campaigns, 69 adsets, 144 ads, 144 creatives, **13139 insight rows across 23 tables** (incl. all previously-empty ad/adset × country/placement/age breakdowns). `meta_insights_performance_day` now spans 2023-08-24 → 2024-09-29 (231 rows / 205 days) = the campaigns' full lifetime; it does NOT advance past 2024-09-30 because the account has had no spend since then (the daily run finds nothing newer), so the original "past 2024-09-30" criterion was an incorrect assumption. **Operational rule confirmed:** `max_active_runs=1` + a single solo run on a rested quota is the reliable way to run full_history; never fire concurrent/back-to-back Meta runs. The "Meta per-chunk insight persistence" gap (a late throttle discards the whole run) remains open below as a separate hardening item. ref: DEVLOG#2026-06-01.
- [x] **SoundCloud DAG cursor pagination — confirm** — CONFIRMED live 2026-05-31. `soundcloud_daily` scheduled run succeeded in ~2 s (precheck 1.9 s + collect 1.8 s) → no hang (the old infinite-pagination loop is gone). `soundcloud_tracks_daily` has **0 duplicate** `(track_id, collected_at::date)` rows → cursor `next_href` followed correctly. 197 rows, fresh (collected 2026-05-31 20:42).
- [x] **Instagram System User token — migration** — same as line 110 (code path complete). Per-artist migration is operational, not a code task. See guide.

### P2/P3 — Live-ops hardening (2026-05-31, from the Meta credential session)

- [x] **DAG concurrency cap — `max_active_runs=1` fleet-wide** (P2). Root cause of the Meta throttle storm: the dashboard auto-triggers a collector DAG on every credential save (`_render.py`), and 8 DAGs had NO `max_active_runs` → rapid re-saves spawned 5 concurrent `meta_ads_api_daily` runs hammering the same ad-account → instant Meta BUC `80004`. Fix: `max_active_runs=1` added to all 8 uncapped DAGs (meta_ads_api_daily, instagram_daily, soundcloud_daily, spotify_api_daily, youtube_daily, meta_token_refresh, ml_scoring_daily, weekly_digest). **All 13 DAGs now capped.** Encoded the rule in `.claude/skills/airflow-dag.md` (template + checklist + REX). Generalization audited: the only 2 DAG-trigger sites (`app.py` "Lancer TOUTES" button, `_render.py` save) are now both safe; the button triggers 7 *distinct* DAGs (no single-account concurrency).
- [x] **Meta System User token → false 60-day expiry** (P3). `_fetch_meta_token_expiry` returned `None` for never-expiring System User tokens (debug_token `expires_at=0`), conflating "never expires" with "couldn't determine" → the save left a stale/false expiry + a misleading warning (manual `expires_at=NULL` was needed). Fix: new `META_TOKEN_NEVER_EXPIRES` sentinel (also keyed on `type=='SYSTEM_USER'`); `_handle_save` now sets `expires_at=NULL` for it; the exchange/renew path defaults `expires_in` to 0 (not 60 days) and sets NULL when the token never expires. Generalization: expiry logic is 100% `platform='meta'` (Instagram shares the Meta token) — no other platform affected.

### P1 — Security (new, 2026-03-30)

- [x] **Credential rotation** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.

### Decisions / closed (2026-03-27)

- ❌ **iMusician API** — no public API exists on any iMusician plan (confirmed 2026-03-27), including AMPLIFY Pro. CSV-only. `imusician_csv_watcher` DAG is the final architecture for this source. Contact iMusician support if an enterprise/white-label API becomes available.
- ❌ **Apple Music API** — Apple Music for Artists has no public analytics API. MusicKit covers catalog/playback only. CSV export remains the only option.

---

## Brick Status

| # | Topic | Status | Priority |
|---|---|---|---|
| 1 | DB migration SaaS (artist_id + saas_artists table) | ✅ | — |
| 2 | Auth Streamlit (authenticator + artist_id in session) | ✅ | — |
| 2.5 | SQL filters by artist (artist_id in all queries) | ✅ | — |
| 3 | Admin interface (CRUD artists + CSV upload) | ✅ | — |
| 4 | API credential form (Fernet encryption) | ✅ | — |
| 5 | CSV import via Streamlit with preview + validation | ✅ | — |
| 6 | Parameterized DAGs (credentials from DB) | ✅ | — |
| 7 | iMusician — manual monthly revenue entry + viz | ✅ | — |
| 8 | Home KPI + source freshness + ROI Breakheaven | ✅ | — |
| 9 | Error handling + retry on all collectors | ✅ | P2 |
| 10 | Unit tests (pytest, 79 tests) | ✅ | P2 |
| 11 | Monitoring + alerting (DAG callbacks + freshness) | ✅ | P2 |
| 12 | PDF report export (WeasyPrint) | ✅ | P3 |
| 13 | CSV global export (ZIP per artist) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT auth) | ✅ | P4 |
| 15 | CI/CD Railway deployment | ✅ | P4 |
| 16 | ML — ml_song_predictions table + daily scoring DAG | ✅ | P3 |
| 17 | ML — trigger_algo upgrade + model performance view | ✅ | P3 |
| 18 | Data Wrapped — annual artist performance report (PDF/HTML) | ✅ | P3 |
| 19 | Security audit — SQL injection, Fernet key exposure, auth bypass, SSRF | ✅ | P3 |
| 20 | Multi-tenancy — artist_id propagation in all collectors + DAG iteration | ✅ | P2 |
| 21 | Stripe integration — subscription plans, webhook, billing page | ✅ | P3 |
| 22 | iMusician CSV import — parser, watcher DAG, Distributeur tab, Upload CSV page | ✅ | P2 |
| 23 | Meta Ads API collector — direct pull (facebook_business SDK), daily DAG, CSV data-quality fixes | ✅ | P2 |
| 24 | Instagram + Meta System User token migration — non-expiring tokens, DAG + guide updates | ✅ | P2 |
| 25 | Security hardening — OWASP Top 10 + RGPD: SQL injection (postgres_handler), brute-force lockout, session fixation, SSRF, XSS, weak password policy, Fernet key env, promo TOCTOU, token expiry, upload cap, audit log | ✅ | P1 |
| 26 | Rate limiting — session-based sliding window (10 attempts / 5 min) on login + TOTP challenge | ✅ | P1 |
| 27 | GDPR Art. 17 erasure — cascading DELETE across 34 tables, 2-step admin confirmation, gdpr_erasure_log audit trail | ✅ | P2 |
| 28 | TOTP 2FA — pyotp + qrcode enrollment in account.py, challenge step in login flow, disable-with-password | ✅ | P1 |
| 29 | Onboarding tracker — "Getting started" progress on home page (credentials, S4A CSV, Apple Music CSV, first data collection); shows green "configuration terminée" recap when complete (no longer auto-hidden — revised 2026-05-28) | ✅ | P3 |
| 30 | Alerting dashboard — circuit breakers, freshness warnings, DAG failures, locked accounts, billing alerts | ✅ | P2 |
| 31 | S4A dashboard view audit — per-track KPIs (listeners, saves) from s4a_songs_global; dual-window (28d/12m) support; DB health view; playlist placement manual entry; s4a_audience saves/playlist_adds columns | ✅ | P3 |

---

### P3 — UX / Features (new, 2026-03-31)

- [x] **S4A per-track KPIs fix** — Listeners and Saves in trigger_algo `_show_tab_global()` were sourced from `s4a_audience` (artist-level → same value for all tracks). Rebound to `s4a_songs_global` per-track snapshot with automatic `time_window` selection (≤35 days → `28d`, else `12m`).
- [x] **s4a_songs_global dual-window** — migration 023 adds `time_window TEXT DEFAULT '12m'` + UNIQUE `(artist_id, song, time_window)`. Parser detects `28d` from filename tokens `28day/28d/28j`, else `12m`. `ml_inference.py` queries now filter `AND time_window = '12m'`.
- [x] **s4a_audience saves + playlist_adds** — migration 020 adds columns. Parser maps `'playlist adds'` (with space) and `'saves'` from audience CSV.
- [x] **Playlist placement manual entry** — migration 021 `s4a_song_playlists` (per-song playlist registry, unused for now). Migration 022 `s4a_song_playlist_adds(artist_id, song, period_start, period_end, count)` — stores manual count from S4A UI (not in CSV exports). `trigger_algo.py` Vue Globale shows count + update form.
- [x] **DB health view** (`src/dashboard/views/db_health.py`) — 11 datasets, freshness table + horizontal bar chart (thresholds 14j/30j), 52-week heatmap, cumulative growth chart, batch sizes chart.
- [x] **Styled dataframe NoneType crash** — `display.style.format(na_rep="—")` added as first call in Score /20 benchmark; `fillna(0)` on all numeric columns before styling.
- [x] **Upload CSV multi-file auto-detection** — `_detect_platform(filename, columns)` priority-ordered detection; `accept_multiple_files=True`; per-file preview + 4-KPI import result.
- [x] **upsert_many row count fix** — was returning `cursor.rowcount` (last batch only = 1); now returns `len(data)` post-dedup.

### P2 — Data Integrity (new, 2026-03-31)

- [x] **s4a_audience playlist_adds / saves still 0** — confirmed: `playlist_adds` is not present in `s4a_songs_global` CSV (neither 28d nor 12m format). Only source is `s4a_audience` daily timeline CSV (artist-level delta) which records 0 for this artist — genuine data. Saves ARE in songs_global CSV and import correctly. playlist_adds entry via manual form (`s4a_song_playlist_adds`) is the intended workflow.

### P2 — Data Integrity (new, 2026-05-14)

- [x] **Migrate `tracks` table to multi-tenant** — DONE 2026-05-31. `migrations/039_tracks_multi_tenant.sql` adds `saas_artists.spotify_artist_id` (bridge) + `tracks.saas_artist_id` (FK to `saas_artists.id`) + `idx_tracks_saas_artist`; idempotent unambiguous auto-bridge backfilled the single tenant (saas id=1 ← `7sbfafbLjNZGZJZjZ3xoPB`, 11 tracks). Applied to live DB. Writer `spotify_api_daily.collect_spotify_top_tracks` resolves + stamps `saas_artist_id` per Spotify id (warns if unbridged). All 4 readers now filter by `saas_artist_id` (`spotify_s4a_combined` ×3, `trigger_algo` ×2 incl. admin-unfiltered branch, `meta_x_spotify` ×1); admin (None) = no filter. `init_db.sql` updated for fresh installs. Legacy varchar `tracks.artist_id` kept (drop in a later cycle). See `.claude/dev-docs/audit-tracks-legacy.md`.

### P1 — Security hardening (closed, 2026-05-14)

- [x] **Explicit SQL allowlist guards** — `db_health.py`, `admin.py`, `airflow_kpi.py` had f-string SQL with implicit allowlist (via constant lookup). Now call `validate_table()` / `validate_columns()` explicitly before each f-string per CLAUDE.md rule #8. Promoted both validators from private (`_validate_*`) to public API in postgres_handler. Commits `d41a842`, `997dcde`.

### P2 — Data integrity (closed, 2026-05-14)

- [x] **Instagram collector silent success** — `_refresh_access_token` and `save_to_db` swallowed exceptions and reported success. Both now `logger.error` + `raise`. Commit `a0f86de`.
- [x] **`requirements.txt` duplicates** — python-dotenv, pandas, psycopg2-binary listed twice (rows 62-64 vs canonical block). Removed dupes. Commit `a0f86de`.

### P2 — Data integrity (closed, 2026-05-15)

- [x] **YouTube collector silent success** — `get_video_comments()` and `get_playlists()` did `return [partial]` inside `except` → a truncated fetch could mark a DAG SUCCESS. Both now `raise` (CLAUDE.md rule #6). YouTube collector now fully silent-success-compliant; `audit-collectors.md` status table corrected, `error-classes.md` `collector-silent-success` History appended. Commit `3b63984`.

### P3 — Infra / supply chain (closed, 2026-05-14)

- [x] **Airflow base image → Python 3.11** — was 3.10, mismatched `pyproject.toml requires-python = ">=3.11"`. Smoke-validated (15 DAGs load, sklearn/xgboost/shap import). Commit `52db15f`.
- [x] **Dependabot config** — pip weekly (groups), github-actions monthly, docker monthly. Closes the loop with `security-nightly.yml` pip-audit (detection → automated fix PR). Commit `6c323c9`.
- [x] **CI on `uv sync --frozen`** — was `pip install -r requirements*.txt` which ignored uv.lock; CI and local devs could install different transitive deps. Now CI reads uv.lock (231 packages pinned). Necessary for Dependabot to be effective. Commit `e6513b4`.
- [x] **Repo cleanup → `.archive/`** — ~22 obsolete files (unused skills, dev-docs stubs, archived agent doublons, dated retro/audit snapshots, legacy v1 collectors) moved to gitignored `.archive/`. CLAUDE.md aligned. Commits `a4fa11e`, `d60e570`, `418fad5`.
- [x] **Collectors style sweep** — 28 `print()` → `logger.*()` and 13 `datetime.now()` → `datetime.now(timezone.utc)` (filename strftime exempt). Commit `a0f86de`.
- [x] **REX promotion** — 2 drafts (`strategic-plan-architect`, `response-protocol`) validated and injected per `rules/rex-format.md`. Validator 42 tools OK. Commit `a3b13d9`.
- [x] **`check_roadmap_update.py` hook** — was no-op (`_INCLUDE='src/Application'` mismatched repo, tracker paths pointed to non-existent files). Fixed to `_INCLUDE='src'` with proper excludes, trackers = `roadmap/checklist.md` + `DEVLOG.md`. Commit `bcfe774`.
- [x] **`.env*.example` templates trackable** — `.gitignore` rule `.env.*` was swallowing the example onboarding files; added `!.env.example` + `!.env.railway.example` exceptions. Also added missing Stripe vars (Brick 21) to Railway example. Commit `66f807d`.
- [x] **pytest coverage** — added `[tool.coverage]` config in `pyproject.toml`, `--cov=src --cov-report=xml` in CI, coverage.xml uploaded as 7-day artifact. No `fail_under` (measure first). Commit `7376aae`.

### P3 — UX / Features (new, 2026-04-12)

- [x] **Live user counter + registered users widget** (Brick 32) — display on the app (home page or landing) the number of currently active sessions and total registered artists. ✅ 2026-05-14
  Sub-tasks:
  - [x] Active sessions: `active_sessions` table (heartbeat updated on each page load, TTL = 5 min). Migration 026.
  - [x] Registered users: `SELECT COUNT(*) FROM saas_artists WHERE active = TRUE`.
  - [x] SEO name: **Live Activity** chosen. Visible copy on landing: "X artistes utilisent streaMLytics".
  - [x] Read-only widget (counts only, no PII). Admin pulse on `home.py`, public trust signal on `register.py`.
  Priority: P3. Decision: added `active_sessions` heartbeat table with 60s session_state throttle (≤1 INSERT/min/session).

---

### P3 — Performance dashboard (long-term, 2026-05-14 audit)

Audit statique + live Lighthouse (page login publique) effectués 2026-05-14. Voir aussi `docs/adr/ADR-003-react-rewrite-deferred.md` pour l'option architecturale long-terme.

**Mesures Lighthouse réelles (login page, headless desktop)** :

| Métrique | Valeur | Score | Cible |
|---|---|---|---|
| Performance | 69/100 | — | ≥90 |
| FCP (First Contentful Paint) | 3.7 s | 29 | <1.8 s |
| **LCP (Largest Contentful Paint)** | **5.7 s** | 16 | <2.5 s |
| TTI (Time To Interactive) | 5.7 s | 68 | <3.8 s |
| CLS (Cumulative Layout Shift) | 0.066 | 97 | <0.1 ✅ |
| TBT (Total Blocking Time) | 80 ms | 99 | <200 ms ✅ |
| Speed Index | 3.7 s | 85 | <3.4 s |

**Network breakdown** : 25 requêtes, 818 KiB total, **bundle JS Streamlit = 532 KiB** (`index.Drusyo5m.js`), 12 fichiers JS (550 KiB cumulé), **324 KiB de JS unused** sur la page login.

**Conclusion live vs static** : le bottleneck #1 du *cold start* est le **bundle JS Streamlit** (pas Python). Les optimisations Python (cache, lazy imports) restent valides mais n'améliorent que les *renders subséquents*, pas le cold start. Cela renforce légèrement l'argument React (Next.js + code splitting → ~100-150 KiB initial bundle vs 532 KiB) mais ne change pas la décision ADR-003.

- [x] **N+1 Airflow DAG monitoring** (HIGH) — DONE 2026-05-31. New `AirflowMonitor.get_all_dags_last_state()` collapses the per-DAG `get_runs_for_dag` loop into ONE POST to the `~/dagRuns/list` batch endpoint (latest run per DAG, sorted-desc first-wins), with a per-DAG fallback if the batch endpoint is unavailable. Repointed all 3 callers: `airflow_kpi.py::_section_last_runs`, `home.py::_section_dag_status`, `credentials/_core.py::_fetch_dag_last_states`. Not live-smoke-tested (Airflow webserver was down this session) — fallback guarantees correctness. **Gain ~2-3 s/render.**
- [x] **`@st.cache_data(ttl=60)` sur 5 KPI helpers** (HIGH) — DONE 2026-05-31. 8 read-only getters in `kpi_helpers.py` wrapped: `get_source_freshness`, `get_total_streams_s4a`, `get_total_views_youtube`, `get_total_plays_soundcloud`, `get_total_plays_apple`, `get_spotify_popularity`, `get_instagram_followers`, `get_soundcloud_likes`. DB handle passed as `_db` (underscore → excluded from cache key; entries keyed on artist_id). No Airflow caller, so the Streamlit-cache decorator is safe. **Gain ~500-1000 ms.**
- [x] **View render-smoke test harness** (NEW 2026-05-31) — `tests/test_views_render_smoke.py`: `AppTest`-runs all 36 dashboard views' `show()` under an admin session against the live DB, asserting no uncaught exception (catches mis-scoped lazy-import `NameError`, broken `@st.fragment`, render-time SQL typos — the class of regression that previously shipped green, cf. WAVE 3 "failed-Edit dead code passed tests+ruff"). Module-skips when Postgres is unreachable (CI has no DB on 5433). 36 pass in ~13 s. Closes the "zero view-render coverage" gap. ([[project_no_view_render_tests]])
- ❌ **CANCELLED 2026-06-01 — Lazy imports plotly + pandas dans 19 vues** (MEDIUM). Re-analysis showed ≈0 gain: `app.py` already lazy-loads view modules per page (`elif page=="x": from views.x import show; show()`), and the module-import + `show()` call are coupled, so deferring `import plotly` into `show()` saves nothing — plotly still loads on the first chart render. Cold start is dominated by the 532 KiB JS bundle ("irréductible sans changer de framework"), which masks any Python-side ms. 26-file churn for no user-visible gain. Revisit only if a non-charting view is ever added.
- [x] **`@st.fragment` sur widgets isolés** (MEDIUM) — DONE 2026-05-31. `home.py::_section_pdf_export` (PDF "Rapport rapide" button + download) and `airflow_kpi.py::_section_insertion_test` (Today/7d/30d window selector → per-table COUNT loop) decorated with `@st.fragment`: interacting with them re-runs only that section, not the whole heavy page. Both self-contained (state via `st.session_state`), verified by the new render-smoke harness. **Gain ~300-500 ms par interaction.**
- [x] **Plotly area chart sampling** (LOW-MEDIUM) — DONE 2026-05-31. Added >500-row downsampling to the cumulative S4A area chart (`spotify_s4a_combined.py`; the `home.py:167` reference was stale — that chart moved here). Every-Nth-point on a monotonic cumulative series, with the last point always kept so the total is never understated. **Gain ~100-300 ms réseau lent.**
- [x] **Pagination admin + ETL logs** (HIGH si tables >1000 rows) — RESOLVED 2026-05-31. Re-scoped to the real concern (silent truncation, not perf): `etl_logs.py` already caps at `LIMIT 200` but hid older runs silently — added an honest "Affichage des 200 runs les plus récents sur N au total" caption (one extra `COUNT(*)`, only when truncating). `admin.py` tables (artists/users/opt-in) are bounded by tenant count — no growth risk, no pagination needed. The only daily-growing table is `etl_run_log`, now handled. Verified by render-smoke. **Gain: honesty, not ms.**
- [x] **`SELECT *` → colonnes explicites** (LOW) — RESOLVED 2026-05-31. `apple_music.py` `SELECT * FROM daily_diff` (a CTE, columns already explicit) made literal. `data_wrapped.py` ×2 (`SELECT * FROM artist_wrapped`) deliberately KEPT generic: consumed via `.to_dict()` + dynamic `df[['year', col]]` + `.get(col)`; DEVLOG#2026-05-29 made this robust to DROP/ADD column reordering (migrations 033/034) — explicit projection would re-introduce that fragility and break dynamic column access. Wontfix-by-design.
- [x] **Disable Streamlit telemetry + headless mode** — `.streamlit/config.toml` updated 2026-05-14 : `[browser] gatherUsageStats = false` (skip data.streamlit.io + fivetran calls) + `[server] headless = true` (skip auto-open browser, fixes WSL2 `gio` error + ready for Hetzner headless VPS).

**Estimated total** : ~2 jours de dev → -50 % temps de render moyen (de ~2-3s à ~1-1.5s) sur les pages internes. **Le cold start (LCP 5.7s) restera dominé par le bundle JS Streamlit (532 KiB) — irréductible sans changer de framework.**

### P4 — Refactor program (2026-05-15)

- [x] **Dashboard refactor program** — sequenced queue R1–R6 (one file/PR, trigger-gated) — DONE 2026-06-01. Tracker: `.claude/dev-docs/roadmap/refactor-program.md` (created `c30d004`, spec: `refactor-audit-dashboard.md`). R1 `credentials.py`→package ✅ (`acf8b6f`, 2026-05-15). R2 `kpi_helpers.py` ruff ✅ (already clean under authoritative config). R4 `trigger_algo.py` (grown to 2279 l / 6 tabs) → package ✅ (`d84c53a`). R5 `pdf_exporter.py` HTML primitives + snapshot net ✅ (`905202b`). R6 `revenue_forecast.py` calc→tested util ✅ (`e8fc0c6`, +8 tests). R3 = `view-session-adoption` — partial **by design** (helper ships; migration stays opt-in per view, no big-bang). 335 pytest pass. Guardrails honored: one-file commits, no FastAPI/React, no service layers (ADR-002), never split <400 l.

### P2 — Data integrity (new, 2026-05-28)

- [x] **Meta Ads `results` hardcoded to one action_type** — `meta_ads_api_collector.py` counted only `offsite_conversion.custom`. All 15 test-account campaigns are `OUTCOME_ENGAGEMENT` (0 custom conversions) → `results` written `0` daily, and the daily upsert overwrote correct CSV-imported values. Fix: `_OBJECTIVE_RESULT_ACTION` map (`OUTCOME_ENGAGEMENT→post_engagement`, `OUTCOME_TRAFFIC→link_click`, `OUTCOME_LEADS/SALES→offsite_conversion.custom`, `OUTCOME_APP_PROMOTION→app_install`; unknown/NULL/awareness → fallback `custom_conversions`). Objective propagated from `meta_campaigns` into `_extract_perf` via `objective_by_name` across all 4 `_call_insights` calls + the `insights_only` DB query. `tests/test_meta_ads_collector.py` adds `TestExtractPerfObjective` (6 tests). **Requires a `full_history` Meta DAG re-collection to backfill historical `results`.**
  Decision recorded: dashboard "Résultats" = Meta's native result per campaign objective (user-confirmed), not Spotify-only conversions.

### P3 — UX / Features (new, 2026-05-28)

- [x] **Onboarding tracker revision** (`home.py`) — replaced the "Enable 2FA" step with "Upload an Apple Music CSV" (checks `apple_songs_performance` rows); reordered so "Run your first data collection" comes after the two upload steps; removed auto-hide-when-complete — now renders a green "configuration terminée" recap with all steps checked.
- [x] **Mapping page relocation** (`app.py`) — moved `meta_mapping` out of "Publicité Meta Ads" into the "Données" section, directly under "Import CSV"; relabeled "🔗 Mapping Spotify × Meta Ads (nom de campagne)".
- [x] **`meta_x_spotify.py` cleanup** — removed the redundant inline "Gérer les associations" mapping expander (duplicate of `meta_mapping.py` AND broken: its INSERT omitted the now-NOT-NULL `artist_id`). View now only reads mappings and points to the dedicated Mapping page. Removed the "Streams Cumulés" series (trace + cumsum + yaxis8 + table column). CPR now reads the real `cpr` column (fallback to `spend/results` only where `cpr` null but `results>0`). Forced number format "13 385" (separators + `tickformat=",d"`) instead of Plotly's "13.385k".
- [x] **Upload CSV doc expander** (`upload_csv.py`) — documents the 6 recognized CSV types (S4A timeline/songs/audience, Apple Music, iMusician summary/sales) + info note to run the mapping after launching collection from the home page.

### P2 — Data integrity (new, 2026-05-29)

- [x] **Meta Ads paused/archived ad-level insights silently lost** — `meta_ads_api_collector.py` fetched all 3 levels with `effective_status: ['ACTIVE','PAUSED']`; a PAUSED campaign propagates `CAMPAIGN_PAUSED`/`ADSET_PAUSED` to its ads, excluding them from `meta_ads`, so `_build_goal_maps` lacked them and `_fetch_ad_insights` dropped the ad-level insights the API returned via `if ad_id not in goal_by_ad: continue`. Campaign spend present, per-creative breakdown missing (Créatives view). Fix: per-level allowlists `_CAMPAIGN_STATUSES`/`_ADSET_STATUSES`/`_AD_STATUSES` (incl. CAMPAIGN_PAUSED, ADSET_PAUSED, ARCHIVED, IN_PROCESS, WITH_ISSUES). `meta_creatives.py` advisory corrected to instruct a FULL full-history collection + note Meta's ~37-month retention. `audit-collectors.md` gained Rule 6 (silent loss via skip-guards fed by over-narrow scope) + 2 REX entries. **Backfill of the 4 paused campaigns not yet succeeded (account throttled at session end).**
- [x] **Meta Ads throttle robustness** — `_meta_list` retried only code 17; the placement-breakdown insights call hard-failed on code 4 and the per-creative fetch stormed code 80004 (ads-management BUC). Fix: generic `_meta_retry()` retrying `_META_THROTTLE_CODES = {4,17,32,80004}` with 60→120→240s exp backoff (4 attempts), cursor materialised inside the retry; `_meta_list` + per-creative `api_get` delegate to it. New `run(fetch_creatives=False)` skips the per-creative content fetch (dominant rate-limit driver, not shown by the view); `debug_meta_ads_api.py` gains `--skip-creatives` + routes the step-3 probe through `_meta_list`. `audit-collectors.md` Rule 7. **Known limitation:** a throttle on a late aggregate call discards all already-fetched insights of the run (no per-chunk persistence) — future-brick candidate.
- [x] **Meta Ads backfill date clamp** — including ARCHIVED campaigns pulled an aberrant start_time → backfill `since=1970-01-01` → Meta error #3018 (start beyond 37 months). Fix: `_META_INSIGHTS_RETENTION_MONTHS = 36`, `history_start` clamped to `today − 36 months` in `_fetch_all_insights`.
- [x] **Meta Ads per-chunk insight persistence** — DONE 2026-06-01. `run()` now upserts config tables (campaigns/adsets/ads/creatives) up front via `_upsert_config`, then `_fetch_all_insights` persists each monthly daily-chunk and each breakdown as it is fetched through a `persist_cb` (`_persist_insights`); the old all-or-nothing end-of-run `_upsert_all` is gone (split into `_upsert_config` + `_insight_upsert_maps` single-source column/key config + `_persist_insights`). A late throttle now keeps every already-fetched month/breakdown instead of discarding the whole run. `tests/test_meta_ads_collector.py` +6 (column trimming, late-throttle-keeps-earlier-chunk durability proof, prune behaviour); 26 meta tests pass. ref: DEVLOG#2026-06-01.
- [x] **Revenue forecast NULL-probability crash (P1)** — `ml_song_predictions.dw/rr/radio_probability` can be NULL (a model that fails to score writes None, `ml_inference.py:204-237`), making the pandas Series object-dtype so `(ml_df[col]*100).round(1)` raised `TypeError: Expected numeric dtype, got object` at `revenue_forecast.py:505`. The `ml_df.empty` guard didn't cover "non-empty but all-NULL". Fix: `pd.to_numeric(ml_df[col], errors='coerce')` + `.map(lambda v: f"{v}%" if pd.notna(v) else "—")` (lines 504-506), reusing the safe pattern from `ml_performance.py:93-99`.
- [x] **iMusician derived-table staleness — roll-up wired into all 3 import paths** — `imusician_monthly_revenue` is DERIVED from `imusician_sales_detail` via `rollup_sales_to_monthly` (`src/utils/imusician_rollup.py`), but the roll-up hook lived only in the Streamlit path. The user's full 2023-01→2026-01 export (~212€, 4326 rows) had been imported by the watcher DAG with no roll-up → monthly_revenue stuck at 13 months / 11.56€ while sales_detail held 211.87€ (dashboard ~5% of real revenue, no error). Fix: added the roll-up to `imusician_csv_watcher.py::process_csv_files` (per dag_run.conf artist_id) and `debug_imusician_csv.py::step_5_real_upsert` (per distinct artist_id), both best-effort/non-blocking. One-time backfill for artist 1 → monthly_revenue now 37 months, 2023-01→2026-01, 211.90€ (all `source='import'`). REX + Rule 8 added to `audit-collectors.md`.

### P2 — Data integrity (new, 2026-05-29 — Meta double-count + single-writer)

- [x] **Meta campaign-grain breakdowns double-counted spend (~2×)** — `meta_insights_performance_country/placement/age` showed ~2× the real spend. Root cause: a DUAL WRITER — the one-time Dec-2025 legacy Meta CSV stack wrote the same tables as the API collector with incompatible conventions (an aggregate `country='All'`/`placement='All'` total row doubling country/age, and French placement labels `Reels Instagram` vs API snake_case `instagram_reels` → distinct conflict keys, both kept). Same legacy import that earlier produced the `cg:`/`a:` prefixed-ID duplicates. Fix (DEFINITIVE): (1) cleaned spurious rows (DELETE `'All'` buckets + non-snake_case placement rows across the 6 campaign breakdown tables, all artists) → all grains reconcile to ~3088€ (= day total); (2) patched `meta_insight_csv_parser` to skip aggregate/total rows (defense); (3) ARCHIVED the entire legacy Meta CSV stack — 8 files → `archive/legacy_meta_csv/` (DAGs `meta_config_dag`/`meta_insights_dag`, watchers `meta_csv_watcher`/`meta_insight_watcher`, parsers, debug scripts) + README; removed `TestMetaCSVParser` from `tests/test_parsers.py`; repointed ALL dashboard/alerting refs (app.py sync, home.py, useful_links.py, airflow_kpi.py, credentials/_core.py, alert_root_cause.py, alert_monitor.py + debug) to the canonical `meta_ads_api_daily`; added `archive/` to `.dockerignore`. RESULT: Meta tables now have exactly ONE writer → double-count cannot recur. `audit-collectors.md` gained Rule 8 "one canonical writer per table" + dual-writer REX. ref: DEVLOG#2026-05-29.
- [x] **Meta campaign-grain breakdowns keyed by `campaign_name`** — DONE 2026-06-01. New `_prune_renamed_campaigns()` (called in `run()` after `_upsert_config`, non-insights_only only) deletes campaign-grain insight rows whose `campaign_name` is no longer returned by the API (ad/adset grains key by id, immune). Guarded: empty/failed fetch is a no-op (never a mass delete); table names validated via `validate_table()` against the allowlist (rule #8); DELETEs artist-scoped, `campaign_name <> ALL(%s)` parameterized. `_CAMPAIGN_GRAIN_TABLES` frozenset = the 10 affected tables. Test coverage in `tests/test_meta_ads_collector.py`. ref: DEVLOG#2026-06-01.

### P3 — UX / Features (new, 2026-05-29 — Road to Algorithms overhaul)

- [x] **WAVE 1 — lifecycle & benchmark tab** (`trigger_algo.py`) — 6th tab "📉 Cycle de vie & Benchmark" (cohort lifecycle/standardization band charts P25/median/P75 by song age-in-weeks, live track age overlaid). New GLOBAL read-only table `algo_lifecycle_benchmark` (`src/database/benchmark_schema.py`, `migrations/035`, `init_db.sql`) — non-tenant, NOT in `_ALLOWED_TABLES`, seeded PROVISIONAL (18 qualitative rows, `total_stream_median` NULL). Threshold-honesty rework: `ELBOW_THRESHOLDS_28D` ({DW:137,RR:130,RADIO:639}) vs `HEURISTIC_GOALS` (Radio fallback); dynamic-imputation caveat (6/13 features imputed → probabilities indicative); `show()` migrated to `view_session()`. Offline `machine_learning/export_lifecycle_benchmark.py` computes real standardization ratios from `data_anon.csv` (path to replace the seed). ref: DEVLOG#2026-05-29.
- [x] **WAVE 2 — algo knowledge layer + shared ML widgets** — `src/dashboard/utils/algo_knowledge.py` (PURE, algo-keyed: `ALGO_FEATURE_ZONES`/`ALGO_CALIBRATION_BANDS`/`ALGO_MODEL_METRICS` + helpers; only Discover Weekly populated, RR/Radio plug in later; `tests/test_algo_knowledge.py`, 8 tests). `src/dashboard/utils/ml_widgets.py` (Streamlit/Plotly render: classification scorecard shared by `trigger_algo` Modèle tab AND admin `ml_performance.py`; feature decision gauges + next-best-lever + fake-buzz guard + calibration badge in the Explainabilité tab). `ml_performance.py` gained a "Scorecard classification" tab. 247 pytest pass (239+8), ruff clean, AppTest render smoke OK. ref: DEVLOG#2026-05-29.
- [x] **WAVE 3 — Radio algorithm support + Prescriptive Coach** — `algo_knowledge.py`: `RADIO_FEATURE_ZONES` (9 features; `DaysSinceRelease` INVERTED vs DW honeymoon→flat-negative; velocity stricter 1.5 vs DW 1.2; catalog sweet-spot 10–20), `ALGO_MODEL_METRICS["RADIO"]` (AUC 0.941, TN47/FP7/FN7/TP41, n=102, real lift vs 0.529 baseline — NO calibration bands, honest), `ALGO_LABELS`, `populated_algos()`, `build_coach_actions()` (ranked prescriptive to-do list, velocity-smooth first), NEW `velocity_penalty_threshold(algo)` single-source helper. `ml_widgets.py`: `render_next_best_lever → render_coach` (ranked list + Discovery-Mode prompt for Radio). `trigger_algo.py`: stacked all-algos rendering (loop `populated_algos`) in Explainabilité + Modèle tabs; NEW `_show_velocity_budget_advice` budget cross-link (velocity-too-high → ~30% spend cut) routed through `ak.velocity_penalty_threshold` (no hardcoded 1.2/1.5). `tests/test_algo_knowledge.py` +12 (Radio zone shapes, inverted age, coach ranking/exclusions, threshold single-source contract). 258 pytest pass (1 skip), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 3 fix — failed-Edit dead code passed tests+ruff** — a mid-session Edit error left `_show_velocity_budget_advice` defined-but-never-called; pytest green + ruff clean (F-rules don't flag unused module-level functions) hid that the whole Coach+budget feature was non-functional until the call site was wired in a follow-up. REX added to `check_python_syntax.py` (after an Edit errors, verify wiring landed). ref: DEVLOG#2026-05-30.
- [x] **WAVE 3 fix — velocity cutoff single-source** — `_show_velocity_budget_advice` originally hardcoded the velocity cutoff (1.2/1.5), duplicating the zone logic in `algo_knowledge`. Fixed via `velocity_penalty_threshold()`; gate + displayed numbers both routed through it. REX added to `dashboard-view.md`. ref: DEVLOG#2026-05-30.
- [x] **WAVE 4 — Release Radar (RR) populated** — RR was the reserved-but-empty algo slot (already wired in ALGO_LABELS, `populated_algos()` order, palette, `rr_classifier` model path). `algo_knowledge.py`: `RR_FEATURE_ZONES` (6 features), `"RR"` registered in `ALGO_FEATURE_ZONES` (order DW/RR/RADIO) + `ALGO_MODEL_METRICS["RR"]` — UI lights up automatically with ZERO view-code changes (trigger_algo Algos/Modèle tabs, ml_performance scorecard grid). Zones sourced from offline SHAP zoom ARTIFACTS (`mlruns/4/.../5_SHAP_Zoom_*_RR.png`), not prose: `DaysSinceRelease` is a firing WINDOW (dip 0–7d, sweet 7–40d, then closes) not an on/off cliff; `ReleaseConsistencyNum` is feature #4 (absent from notes, rewards spaced releases); `DiscoveryMode` dead-flat. Scorecard pixel-verified vs `1_Dashboard_Performances_RR.png` (confusion {TN76,FP6,FN4,TP16}, AUC 0.961, AP 0.88, lift_top10 5.1). `PlaylistAddsLast28Days` marked `divergent + actionable:False` (negative SHAP = chronological song-age confound, NOT a causal lever — shown in gauges with warning, excluded from coach). NO RR calibration bands (no artifact exists; `test_rr_has_no_calibration_bands` documents the gap). `ml_widgets.py`: `divergent` gauge message made data-driven (was hardcoded wrong "bornée à ≤1.0") + per-spec `divergent_note` caption. `ml_performance.py`: scorecard loop routed through `ak.populated_algos()` (DRY, removed 3rd hardcoded tuple). `tests/test_algo_knowledge.py` +9 (9 RR tests + 1 cross-algo coherence guard). 267 pytest pass (258→+9), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 5 — volume (regressor) decision layer** — distinct from the classification/entry story: answers "once a song triggers, how much volume?". `algo_knowledge.py`: `ALGO_VOLUME_ZONES` (DW only, regressor-SHAP-derived — raw fuel StreamsLast7Days/NonAlgoStreams28Days drives volume, saves/playlist-adds flagged `volume_flat`: "quality buys the ticket, volume writes the cheque"), `ALGO_REGRESSOR_METRICS`, `FORECAST_FLOOR_DISCLAIMER`, `volume_scaling_threshold(algo)`, and registry-aware `_spec`/`zone_for_value`/`decode_feature_value` (one machinery serves both zone sets via `registry=`). `ml_widgets.py`: `render_floor_forecast`/`floor_forecast_text` (reframes `*_streams_forecast_7d` as a conservative FLOOR), `render_regressor_badge` (hungry/conservative), `render_volume_gauges`, `render_shap_narrative` (NL SHAP autopsy); `_render_one_gauge`/`_live_value` registry-threaded. `trigger_algo.py`: floor wording in `_display_prob_bar`, volume gauges in coach loop, regressor SHAP autopsy in Explainabilité, static organic budget-scaling section (≥6000 organic/28j, labelled "cible, pas écart live"). `revenue_forecast.py`: floor column labels "(plancher ≥)" + caption. Tier B (zones + scaling target) runs in rule+static-target mode and auto-upgrades at Phase 2 (NonAlgoStreams28Days_log/DiscoveryMode/RadioCount still imputed to 0.0). `tests/test_algo_knowledge.py` +`TestVolumeZones`/`TestVolumeScalingThreshold`/`TestRegressorNote` (broken placeholder completed). 280 pytest pass (267→+), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 6 — Radio volume regressor wired + knowledge encoded** — the Radio regressor (MLflow exp 6, run `16155f62`) existed as trained artifacts but was unwired in 5 places; all closed. **Pipeline (P2):** `ml_inference.MODEL_PATHS["radio_regressor"]` + `score_song` now computes `radio_streams_forecast_7d` (capped ≥0); `ml_scoring_daily` update_cols + `ml_song_predictions.radio_streams_forecast_7d INTEGER` (init_db.sql, create_missing_tables.sql, idempotent `migrations/036_ml_radio_streams_forecast.sql` — **needs `make migrate` on live DB**); `ml_performance._MODELS` registers exp 6 (17 PNG artifacts now visible). **Knowledge (P3):** `algo_knowledge.RADIO_VOLUME_ZONES` (StreamsLast7Days amplifier + the FIRST non-flat catalogue lever `HowManySongsDoYouHaveInRadioRightNow` = superstar effect; DiscoveryMode/Saves/PlaylistAdds/ListenersStreamRatio `volume_flat`), `ALGO_REGRESSOR_METRICS["RADIO"]` (R²=0.63 + viral-cap framing: +400k outlier under-predicted → floor not ceiling), `radio_discovery_recovery_note()` (margin-recovery: turn Discovery Mode off past cruising velocity to reclaim 30% royalties). **View (P4):** radio forecast in `_display_prob_bar`, Radio SHAP volume autopsy expander, recovery note in coach loop, 3rd "Radio forecast" column in Actual-vs-Predicted, `revenue_forecast.py` floor column. **Long-term fix:** RadioCount marked `live_unavailable` (imputed-0 → pedagogic expander, not a fake live "0 titres" gauge — the imputed-0 anti-pattern); `render_volume_gauges` pedagogic caption made algo-generic (was DW/NonAlgoStreams-hardcoded). `tests/test_ml_inference.py` (6-model + key contract + regenerated frozen baseline), `test_algo_knowledge.py` +3 RADIO tests. 283 pytest pass (280→+3), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 7 — Release Radar volume regressor SUPPRESSED (R²=0.32, product-protective)** — opposite of WAVE 6: the RR volume regressor (exp 7) scores R²=0.32 (SHAP = flat line at zero broken by 2-3 viral outliers; followers/recent-streams/saves/playlist-adds all flat — RR volume is notification-CTR noise, not algorithmic). Per the user's data-science verdict, the forecast must NOT reach users (false financial promise) — RR ships **classification-only** (AUC 0.96). **Knowledge (P3):** `ALGO_REGRESSOR_METRICS["RR"]` with `volume_reliable: False` + `r2: 0.32` + `suppressed_note` + interpretation; new single-source helpers `volume_forecast_reliable(algo)` (default True, explicit-False gate — no `if algo=="RR"` hardcoding) and `volume_suppressed_note(algo)`. **Gate the 2 user surfaces (P3):** `trigger_algo._show_ml_section` passes `None` as the RR forecast + shows the "abonnés notifiés, volume non prédictible" caption; `revenue_forecast.py` drops the `rr_streams_forecast_7d` floor column when unreliable + updated caption. **Diagnostics kept honest (P4):** the Modèle-tab RR Actual-vs-Predicted scatter + admin `ml_performance` exp 7 artifacts stay, now captioned "R²=0.32 — diagnostic, PAS une prévision". **No pipeline change:** `rr_streams_forecast_7d` still computed/persisted (diagnostics read it); only display is gated. `tests/test_algo_knowledge.py`: `regressor_note("RR")` now non-None + `test_volume_forecast_reliability_gate` + `test_volume_suppressed_note`. 285 pytest pass (283→+2), ruff clean. ref: DEVLOG#2026-05-31.
- [x] **RR (+ RADIO) calibration bands** — DONE 2026-06-05 (WAVE 8 — independent re-derivation). Instead of a notebook PNG, the bands are measured empirically from v3 out-of-fold group-CV calibrated probabilities (`machine_learning/analysis/05_calibration_bands.py`): per-bin observed positive rate → `ALGO_CALIBRATION_BANDS["RR"]` and `["RADIO"]` now populated. v3's OOF-Platt calibration is well-behaved, so most bands read "fiable : score ≈ réalité" (a big honesty upgrade over v1's over-confidence warnings). `test_rr_has_calibration_bands` / `test_radio_has_calibration_bands` updated.
- [x] **Replace provisional `algo_lifecycle_benchmark` seed with real export** — DONE 2026-06-05. Re-seeded from `data_anon.csv` via the conditioned export (`migrations/041_lifecycle_benchmark_v2.sql`, `dataset_version='v2'`): conditions on the triggering cohort so DW medians are no longer crushed to 0 and `total_stream_median` is populated. Loader prefers v2 (falls back to v1). **Needs `make migrate`.** See WAVE 8 follow-ups below.
- [x] **Phase 2 — live per-algorithm stream capture from S4A** → **CLOSED AS MANUAL (2026-06-10, ADR-004)** — see canonical entry "Phase-2 data acquisition" in Long-term ML hardening below. S4A has no source-split export; auto-capture rejected, manual entry shipped (mig 052). Extra context specific to this view: `s4a_song_timeline` is total-streams only, so per-tenant *live* lifecycle curves (vs the static v2 cohort) need the per-algo split; the volume layer's imputed-0 features (`NonAlgoStreams28Days`, `DiscoveryMode`, `RadioCount`) and the Radio superstar lever auto-upgrade from rule/static-target mode to live deltas once Phase 2 lands. (Surfaced 2026-05-29.)
- [x] **`ListenersStreamRatio28Days_adj` inverted + clamped (P2) — FIXED** — `ml_inference.build_features` now computes `streams/listeners` unclamped (was `min(listeners/streams, 1.0)`), matching the SHAP 2.2–4 sweet-spot; `divergent` flag removed from `algo_knowledge`. (2026-05-29.)
- [x] **Recover imputed DW features** — Saves (`s4a_songs_global.saves`, 28d window), PlaylistAdds (`s4a_song_playlist_adds`), ReleaseConsistency (median weeks between real release dates in `track_release_reference`, NOT the all-identical backfilled timeline first-appearance) now computed live; `_IMPUTED_FEATURES` reduced to the 3 genuinely sourceless (NonAlgoStreams28Days → Phase 2, RadioRightNow, DiscoveryMode). REX in `dashboard-view.md`. (2026-05-29.)
- [x] **`DaysSinceRelease` uses backfilled timeline MIN(date)** — FIXED 2026-05-31. `ml_inference.build_features` now resolves the per-song release date from `track_release_reference` (matched on `normalize_track_title(song)` → `match_key`), falling back to the timeline `MIN(date)` only when no reference row matches. `ReleasePhaseEarly` follows automatically (derived from `days_since`). Note: stored `ml_song_predictions.features_json` keep the stale value until the next `ml_scoring_daily` re-score (live trigger_algo render is correct immediately).

### P3 — ML re-derivation (WAVE 8, 2026-06-05 — independent rebuild from data_anon.csv → v3)

- [x] **Independent ML re-derivation + v3 pipeline** — full-takeover rebuild from `data_anon.csv` as a methodology comparison vs `train.py`/v2. Reproducible scripts `machine_learning/analysis/{01_audit,02_validate,03_train,04_forecast_variant,05_calibration_bands,06_scorecard_metrics}.py` + reports (`audit.md`, `validation.md`, `modeling.md`, `forecast.md`, **`COMPARISON_REPORT.md`**). **Findings:** (1) 30.7% of rows are repeat songs (one has 22 snapshots) → validation switched to **StratifiedGroupKFold by `NameID`**; the leakage inflation is modest (~0.02 AUC), so v2's AUCs hold up. (2) **SMOTE mildly hurts** (RR AP 0.80→0.74) → dropped. (3) Calibration was fit on the test split → v3 fits **Platt on out-of-fold** predictions. (4) **All volume regressors are weak** under honest CV (DW R²<0, RR 0.23, Radio 0.33 with log target) → DW + RR volume suppressed, Radio = floor only; regressors switched to **log1p target** (inference applies `expm1`). (5) Per-algo framing: **RR = true forecast** (AUC 0.92 from release-day metadata alone), **DW = lever model** (saves + playlist-adds), **Radio = momentum diagnostic** (collapses without concurrent streams). **Shipped:** `models/v3/` (13-feature contract KEPT per user — feature-drop deferred to Phase 2), `ml_inference.MODEL_VERSION="v3"` + expm1 + DW-volume suppression, `algo_knowledge` refreshed (group-CV scorecard metrics + `auc_ci`, honest regressor metrics, **RR+RADIO calibration bands**, per-algo interpretation copy), `ml_widgets` scorecard CI band, `_common` DW/RR/RADIO calibration badges. Tests re-baselined (`test_ml_inference` v3, `test_algo_knowledge` v3). 300 pytest pass, ruff clean. **Note:** keeping 13 features means the NonAlgoStreams28Days/RadioCount train/serve skew remains → Phase-2 live data stays a priority (UI keeps the imputation caveat). ref: DEVLOG#2026-06-05.
- [x] **Discoveries → app features (WAVE 8 part 2)** — 2026-06-05. Four features shipped from `COMPARISON_REPORT.md` §5: (A) **Pre-release RR estimator** — new metadata-only RR model `models/v3/rr_premiere_classifier.ubj` + `premiere.json` (AUC 0.923 [0.88–0.96] group-CV, `analysis/07_train_premiere.py`); `ml_inference.estimate_rr_prerelease()`; ephemeral what-if widget `ml_widgets.render_prerelease_rr_estimator()` (inputs + RR-odds curve over J0–J40) in the Algos tab. (B) **Expected-value ROI** — `_tab_budget_roi._render_expected_value()` = cost-per-trigger ÷ calibrated P(trigger) = honest risk-adjusted cost + best-bet pick. (C) **PI group-CV validation** — `analysis/08_validate_pi.py`: R²=0.923 [0.88–0.94], MAE 2.0 pts → PI is genuinely robust (not optimistic); UI help text + `metrics.json pi` block updated. (D) **DiscoveryMode coverage** — `build_features` stamps `discovery_mode_known`; `_show_imputation_caveat` distinguishes a real opt-out from a missing-data 0 and prompts entry. `MODEL_PATHS` now 8 models. 302 pytest pass, ruff clean. ref: DEVLOG#2026-06-05.

### P4 — ML follow-ups (WAVE 8, 2026-06-05)

- [x] **Quantified DW levers (local sensitivity)** — DONE 2026-06-05. `ml_inference.local_sensitivity()` sweeps one lever of the current song and recomputes the calibrated probability (upper bound = mean+3σ for resolution); `ml_widgets.render_lever_sensitivity()` plots the per-song curve + the marginal gain to target, wired into the Explainability tab for DW (the lever model). Honest *local* partial dependence — explicitly captioned "not a global rule" (XGBoost is non-linear).
- [x] **Lifecycle benchmark re-seed (conditioned)** — DONE 2026-06-05; **supersedes the provisional-seed item above**. `export_lifecycle_benchmark.py` now conditions on the TRIGGERING cohort (clears the elbow: DW>137 / RR>130 / Radio>639, min 5 songs/bin) → meaningful medians + populated `total_stream_median` (was NULL). `migrations/041_lifecycle_benchmark_v2.sql` seeds `dataset_version='v2'`; the loader prefers v2 and falls back to v1 (no regression pre-migrate). **Needs `make migrate` to go live.** Semantic shift: the curve now reads "among songs that DID trigger"; RR spans only 0–10 wk (fires near release).
- [x] **11-feature contract — RESOLVED by serving live, not dropping (2026-06-11).** The skew fix had two doors (drop the 2 features, or serve them); migration 052 already opened the *serve* door (manual S4A entry → `s4a_song_nonalgo_streams` / `s4a_artist_radio_count`, read by `ml_inference.build_features`). This session closed the loop end-to-end: `build_features` now stamps `nonalgo_known` / `radio_known` (mirroring `discovery_mode_known`); a centralized `algo_knowledge.feature_live_available(spec, feats)` un-imputes a manual-source feature once entered; `_show_imputation_caveat`, the gauges (`ml_widgets._live_value`), the lever filter and `build_coach_actions` all respect it. **A genuine entered 0 (e.g. 0 songs in Radio) now counts as real data, not imputation** → the "X/13 imputed" warning fires only when truly unfilled. Skew gone for filled tenants; keeping 13 features is correct. Verified live: `ml_scoring_daily` re-run persisted `*_known=true` on all 11 active songs. 444 tests pass. ref: DEVLOG#2026-06-11.

*(Phase-2 live per-algorithm capture and per-tenant evaluation + live-outcome retraining are tracked once in "Long-term ML hardening (roadmap)" below — not duplicated here.)*

### P3 — UX / Features (new, 2026-05-29 — Meta analytics expansion)

- [x] **Creative analytics charts** (`meta_creatives.py`) — reorganised into 6 tabs (Classement/Comparaison/Funnel/Évolution/Fatigue/Activité): #1 bubble scatter (spend×CPR, size=impressions, color=CTR), #2 ad-fatigue dual-axis (frequency↗ vs CTR↘), #3 funnel (impressions→clics→résultats, go.Funnel), #4 efficiency bars (CTR/CPM/CPC), #5 weekly density heatmap, #6 cumulative spend area; plus a per-creative multi-metric timeline (one Y-axis/metric + legend toggle, weekly down-sampling >120d, derived CPR). All from `meta_insights` (ad grain). New "🎯 Ciblage vs Performance" (#9) section in `meta_ads_overview.py` (meta_adsets targeting × CPR via `pareto_spend_cpr`). ref: DEVLOG#2026-05-29.
- [x] **Multi-grain breakdowns (ad & adset grain)** — collector `meta_ads_api_collector.py`: `_build_goal_maps` returns `goal_by_adset`; new `_fetch_breakdown(level, id_field, breakdown, goal_by_entity)` helper (reuses `_extract_perf/_extract_eng` + FK guard, +6 API calls/run); `_fetch_all_insights` +12 keys, `_upsert_all` +12 DRY entries. 12 NEW tables `meta_insights_{performance,engagement}_{ad,adset}_{country,placement,age}` (migration 032, registered in `_ALLOWED_TABLES`, documented in `meta_insight_schema.py`) — lifetime aggregates (no date col) → filtered by entity, not period. NEW view `meta_breakdowns.py` ("🌍 Breakdowns Meta", app.py nav+routing): campaign→adset→creative cascade, dimension × metric-family selectors, choropleth (new `dashboard/utils/geo.py` ISO-2→ISO-3 pycountry wrapper) + Pareto (new shared `dashboard/utils/charts.py::pareto_spend_cpr`). `dashboard-view.md` Pitfalls #7 (aggregate tables no date) + #8 (choropleth ISO-2→ISO-3). ref: DEVLOG#2026-05-29.
- [x] **Recency-ordered entity filters** — entity selectboxes now list most-recent-first via SQL `ORDER BY <recency> DESC NULLS LAST` (never Python `sorted()`): meta_breakdowns cascade (start_time/created_time), meta_creatives (campaign/timeline/fatigue/funnel), meta_x_spotify (MAX(day_date)), meta_mapping `_load_campaigns` (start_time), ml_performance (days_since_release). Deliberate non-recency: export_pdf (streams DESC), meta_mapping `_load_tracks` (no date col). `dashboard-view.md` Pitfall #9 + REX. ref: DEVLOG#2026-05-29.

### P3 — UX / Features (new, 2026-05-28 — multi-view UX pass)

- [x] **Apple Music song filter → single-select** (`apple_music.py`) — `multi=False` in `EntitySpec`, defaults to latest release.
- [x] **YouTube subscriber axis legibility** (`youtube.py`) — removed `fill='tozeroy'`, added tight computed y-range + SI `tickformat` so daily evolution is visible.
- [x] **Hypeddit single-page layout** (`hypeddit.py`) — merged the 3 `st.tabs` (Saisie/Stats/Historique) into one scrolling page (stats + history first, manual entry last). New helpers `_render_global_stats` / `_render_history` / `_render_entry_form`.
- [x] **Distributeur tab cleanup** (`imusician.py`) — removed the "Saisie" and in-view "Import CSV" tabs (redundant with the Import CSV page); kept Données + ROI; dropped dead `_upsert_revenue`.
- [x] **App-level credential status** (`credentials/_core.py` + `_render.py`) — new `app_level_configured()`: Spotify/YouTube show "Configuré (clé plateforme)" when keys exist in env/config.yaml even without an `artist_credentials` row (mirrors the collectors' DB-then-env fallback).
- [x] **Billing 3-tier rework** (`billing.py` + `stripe_schema.py`) — 3 columns (Free/Basic/Premium); removed the comparison dataframe; ungreyed the upgrade CTA (enabled button + contact message when `STRIPE_CHECKOUT_URL` unset). `PLAN_FEATURES['basic']` now includes `revenue_forecast` (ML access moved into Basic); `ALWAYS_ACCESSIBLE` now includes `process_guide`.
- [x] **Guide de démarrage page** (`process_guide.py`, NEW) — "📋 Guide de démarrage" view with downloadable PDF (WeasyPrint, HTML fallback). `app.py` nav: Données section reordered Guide → Credentials → Import CSV → Mapping → Santé (Credentials moved out of the account section).
- [x] **Welcome trial + plan-change audit** (`register.py`, `verification_email.py`, `src/utils/plan_history.py` NEW, `migrations/029`) — every new signup auto-grants a 30-day premium trial (`WELCOME_TRIAL_DAYS`) via `promo_plan` precedence; new `send_welcome_email()` recaps first actions; new append-only `subscription_plan_history` table (migration 029, idempotent backfill) with `log_plan_change()` write hooks in `register.py` (welcome_trial/promo), `admin.py` (admin_edit), `api/routers/stripe_webhook.py` (stripe_webhook). Migration 029 applied to local DB.
- [x] **Admin plan-evolution + users views** (`alerts.py`) — plan-evolution stacked-area chart (from `subscription_plan_history`) + users table (email + signup date + effective plan).

### Standing ops — incident-driven (no code action)

These are not roadmap bricks; they are operational standing instructions kept here for visibility.

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, Railway env vars. Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".

---

## Completed

All bricks (1–19) fully implemented. Session implementation notes were archived in `saas-db-migration/checklist.md` (deleted 2026-03-23 — no longer needed).

---

## ML decision layer (2026-05-31, WAVE 8)

- [x] **Scaler-free retrain + PI model** — `machine_learning/train.py`, models in `models/v2_noscaler/`; `pi_forecast_7d` column (migration 037). ✅ 2026-05-31
- [x] **B2 "Portes par PI"** — per-song positioning on the PI→trigger curves (`threshold_tables.json`). ✅ 2026-05-31
- [x] **Verdict banner 🔴🟠🟢** — consolidated kill/optimize/scale on argmax of the 3 probs. ✅ 2026-05-31
- [x] **Budget pacing calculator** — spread budget over the eval window to avoid the velocity spike. ✅ 2026-05-31
- [x] **Snowball radar** — catalogue scan (radio_probability ≥0.5) bypassing the imputed-0 radio-count feature. ✅ 2026-05-31
- [x] **Resurrection data foundation** — `s4a_song_saves_daily` table + daily writer (migration 038). ✅ 2026-05-31
- [x] **Resurrection alert (activation)** — `detect_saves_resurrection` wired into the `alert_monitor` consolidated email as a green "opportunities" section. Dormant until ~2 weeks of saves history accrue. ✅ 2026-05-31
- [x] **Probability calibration (Platt)** — sigmoid calibrator per classifier (`calibration.json`), applied in `score_song`; verdict bands now real probabilities. ✅ 2026-05-31
- [x] **Drift detection foundation** — training `feature_stats` exported; `ml_inference.check_drift` flags out-of-distribution inputs, logged per song in the scoring DAG. ✅ 2026-05-31
- [x] **Empirical threshold reconciliation** — `derive_thresholds.py` computes success-rate knees from data; recalibrated 5 DW zones in algo_knowledge (velocity no longer penalises 1.2-2.0; saves 50→165; organic→3900; adds→175; followers bonus→2650). ✅ 2026-05-31
- [x] **Phase strategy + Discovery Mode protocol + variable hierarchy** — `_show_phase_strategy`, `_show_discovery_mode_protocol`, `_show_feature_importance` (gain-ranked) in trigger_algo. ✅ 2026-05-31
- [x] **ML KPI gaps** — LIME local explanation (`_show_lime_explanation` + lime_background.json + `lime` dep), Meta-lever scoring on real Meta perf (`_show_meta_lever_scoring`), calibrated budget-to-trigger (`_TRIGGER_STREAM_TARGETS`), PI-driven breakeven (`_show_pi_breakeven`). 6/7 requested graphs already existed. ✅ 2026-05-31
- [x] **PI line + 28d gate** — Popularity Index added to the main algos chart; `_GATE_28D` + `_show_28d_gate` (28d streams/listeners vs validated per-algo thresholds, DW 9200/4100). ✅ 2026-05-31
- [x] **Drift surface + alerting** — `_show_drift_status` (OOD features per track, Explainabilité tab) + `check_drift_anomalies` task in alert_monitor (systemic drift >50% of predictions → email). `check_drift` now excludes the imputed features (permanently OOD by design). ✅ 2026-05-31

## Long-term ML hardening (roadmap)

- [x] **Phase-2 data acquisition — CLOSED AS MANUAL (2026-06-10, ADR-004).** The 2 ex-imputed features are now sourced from manual entry: `NonAlgoStreams28Days` → `s4a_song_nonalgo_streams`, `HowManySongsDoYouHaveInRadioRightNow` → `s4a_artist_radio_count` (migration 052), captured in the Saisie S4A form, read by `ml_inference.build_features` (default 0 when no entry). **Automatic capture rejected:** the artist confirmed S4A shows the source split on-screen only (no CSV export → parser+watcher impossible), and scraping the authed S4A UI is ToS-violating + per-tenant-credential-heavy + fragile (see ADR-004). **Reopen only if** Spotify exposes the split via a CSV export or official API → then a cheap DistroKid-style parser+watcher. 416 tests pass.
- [x] **Discovery Mode manual input** — DONE 2026-05-31. `migrations/040_s4a_song_discovery_mode.sql` (table mirrors `s4a_song_playlist_adds`: per-song dated opt-in, latest `recorded_at` wins) + `init_db.sql` + `_ALLOWED_TABLES`. `ml_inference.build_features` sources `IsThisSongOptedIntoSpotifyDiscoveryMode` from the latest manual entry (default 0.0). `trigger_algo` gains a "🔭 Discovery Mode" metric + manual opt-in form (after Ajouts playlist). Kept in `_IMPUTED_FEATURES` (drift-excluded) — bounded binary flag, z-score drift is meaningless. End-to-end verified (feature flips 0→1 on opt-in); render-smoke + 321 pytest green. Marginal SHAP weight (rank 13) but un-imputes one of the 3 sourceless features with zero external API.
> **Framing (2026-06-11): input-feature data is DONE — these 4 are TIME-ACCRUAL-blocked, not input-blocked.**
> Manual S4A entry (mig 052) + fresh stream CSVs closed the *input-feature* gap: a single prediction now has all 13 real features. What remains needs data that **accumulates over time / across tenants** and cannot be backfilled by entering today's values: more labelled rows, several tenants, forward trigger-outcomes, a long saves history. Do **not** re-scope these as "blocked on data entry" — the entry is done.

- [ ] **More training data + per-tenant evaluation** — model trained on N=508 / 102 test (single anonymised set). **Blocker = tenant count + label volume, not features:** still one live tenant; entering your own data does not create cross-tenant generalisation evidence. Accumulate live labelled data across artists before trusting absolute probabilities.
- [ ] **Automated retraining on live outcomes** — `data_anon.csv` is a one-time snapshot. **Blocker = forward outcomes accruing in time:** needs `ml_song_predictions` to gather real trigger results (score → submit to playlists → observe DW/RR/Radio weeks later).
  - [x] **Outcome-labelling loop — BUILT 2026-06-12** (the "next concrete sub-step"). `migrations/060_ml_outcome_labeling.sql`: `s4a_song_algo_outcomes` (manual capture of realized DW/RR/Radio 28d streams per song — S4A has no source-split export, ADR-004) + `ml_prediction_outcomes` (training-ready labelled pairs). Pure engine `src/utils/ml_outcome_labeling.py` (`bin_label` with training thresholds 137/130/639, `match_outcome` = earliest snapshot ≥28d post-prediction, `label_predictions` idempotent join). Weekly DAG `ml_outcome_labeling` (Mon 06:00 UTC) + debug. Saisie S4A view extended with a realized-outcome grid (the capture surface). 10 tests, end-to-end verified live (labels (1,0,1) + idempotent re-run), DAG parses in-container. **Labels now accrue whenever you enter realized outcomes** — closes the input half.
    - [x] **Windowed capture + chart 2026-06-12** — `migrations/061`: `s4a_song_algo_outcomes` made window-aware (`time_window` 7d/28d/custom + `period_start/end`; columns renamed `dw_streams`/`rr_streams`/`radio_streams`). Saisie S4A grid now captures 7j+28j + a custom-period section. New Road-to-Algo tab "📈 Streams algos générés" (`_tab_algo_streams.py`): stacked bar = cumulative total + per-playlist (DW/RR/Radio) contribution, with a 7d/28d/custom selector + KPI cards. **The labelling engine still reads ONLY `time_window='28d'`** (model horizon) — 7d/custom are tracking-only. Verified live: labelling ignores 7d/custom decoys, uses 28d. The reframed need (per user): not predicting *when* algos trigger, but measuring *how many streams* they generate once triggered.
  - [ ] **Champion/challenger retraining DAG** — consume accumulated `ml_prediction_outcomes` pairs to retrain + compare vs the live model. Still genuinely blocked: needs enough labelled cycles to have accumulated (forward time + entries). Build once `ml_prediction_outcomes` has a meaningful row count.
- [ ] **RR volume regressor** — suppressed (R²=0.23 group-CV on the log target, notification-CTR noise — v3 honest figure, was misreported ≈0.55). **Phase-2 features have now landed (mig 052) but did NOT lift this:** R²=0.23 is measured on the training set, which already contained both features — serving them live changes serving, not the fit. Revisit needs more/better training *volume* (ties to the two items above); stays classification-only meanwhile.
- [ ] **Resurrection tuning** — thresholds in `detect_saves_resurrection` (min_age 180d, 2x baseline, min_spark 50) are heuristic; recalibrate once a real **saves time-series** exists (an old song's saves spiking months later) — a longitudinal history, not a snapshot.

---

## P3 — Product usage tracking (spec'd 2026-06-09, Option A — homegrown)

Goal: know what end-users (artists) actually do in the app (pages visited, features
used, drop-offs, dead features). **Decision: build a lightweight server-side event log
in Postgres rather than PostHog** — Streamlit's rerun/DOM model makes PostHog's JS
autocapture/session-replay unusable (see Deferred § below); a homegrown table reuses the
DB + auth + admin-view stack already in place, with zero third-party egress / RGPD cost.

- [x] **`usage_events` table + tracking hook + admin view** — SHIPPED 2026-06-09
  (`migrations/045_usage_events.sql`, `src/dashboard/utils/usage_tracker.py` fail-silent
  `track()`/`track_page_view()`, `views/usage_analytics.py` admin view). Spec below kept for
  reference.
- [x] (spec) **`usage_events` table + tracking hook + admin view** — original spec:
  - **Schema** (`migrations/045_usage_events.sql` + `init_db.sql` + add to `_ALLOWED_TABLES`):
    `usage_events(id BIGSERIAL PK, artist_id INT, role TEXT, session_id TEXT, event TEXT NOT NULL,
    page TEXT, ts TIMESTAMPTZ DEFAULT now(), meta JSONB)`. Indexes on `(ts)`, `(artist_id, ts)`,
    `(event)`. Use UTC-aware `ts` (rules/python.md). Retention: prune > N months via a tiny
    step in an existing daily DAG (or a `DELETE` in `data_quality_check`).
  - **Writer** (`src/dashboard/utils/usage_tracker.py`, NEW): `track(event, page=None, meta=None)`
    → single INSERT via `PostgresHandler.execute_query` (autocommit). **Fail-silent** (try/except,
    never raise — telemetry must NOT break or slow a page; this is the deliberate inverse of the
    collector "must raise" rule). `distinct_id = artist_id` from `get_artist_id()`; `session_id`
    from a `st.session_state['_session_id']` set once (uuid4).
  - **Page-view hook**: in `app.py::main()`, right after `page = show_navigation_menu(role)`
    (line ~313, the single routing choke-point), call `track('page_view', page=page)` **only when
    the page changed** vs `st.session_state['_last_tracked_page']` — Streamlit reruns on every
    widget interaction, so logging every rerun would massively inflate counts.
  - **Key action events** (explicit `track()` calls): `pdf_generate`, `csv_export`,
    `dag_trigger`, `login`, plus `error` (wrap nothing new — just call where errors are already
    caught). Keep the taxonomy small and stable.
  - **Admin view** (`views/usage_analytics.py`, admin-only — add to `_NAV_SECTIONS` admin section
    + `_ADMIN_ONLY` + routing): top pages (bar), events/day (line), active artists, least-used
    pages ("dead features"), simple funnel (login→page→action). Reuse `kpi_helpers`/`charts.py`
    patterns; gate behind `is_admin()`.
  - **RGPD**: first-party, no egress. The app already has a cookie notice
    (`_show_cookie_notice`) + a `?page=privacy` policy — extend the policy text to mention
    in-app usage analytics. No new consent vendor needed for first-party functional analytics,
    but confirm wording.
  - **Verification**: migrate; click around → rows land; rerun a page (widget interaction) →
    NO duplicate page_view; admin view renders; render-smoke + a small unit test on
    `usage_tracker.track` (fail-silent on bad DB). Effort ≈ ½–1 j.

## Pré-déploiement program (2026-06-09)

Ordered A→B→C→D. **Deployment (Docker containerization + Hetzner) is the LAST phase** and is
parked in `.claude/dev-docs/deployment.md` (out of current scope per user). Pricing is now
**2 tiers** free(0€)/premium(10€) — basic retired (migrations 047/048).

- [x] **A — Validations & gate** : 375 tests verts ; tiers free/premium validés + alignés
  (code+DB+billing/upgrade) ; vue admin **📊 Supervision** (business + fraîcheur données) ;
  leak Export-PDF des sections premium corrigé (`PREMIUM_SECTIONS`).
- [x] **B1 — Mapping cross-plateforme + suggestions** (LIVRÉ 2026-06-09 ; **consolidé 2026-06-11**) :
  `migrations/049_track_platform_link.sql`, moteur pur `src/utils/track_mapping_suggest.py`
  (+15 tests), vue `views/track_mapping.py` — 3 onglets : suggestions par plateforme
  (S4A/Spotify/Apple/SC/YT, accept/reject + bulk), **Meta campagnes** (title-sim + date-proximity,
  écrit `campaign_track_mapping` en `_`-form), vue unifiée. Validé sur données réelles.
  **2026-06-11** : fusion `track_mapping` + mapping Meta en **une seule vue `meta_mapping` à 2 onglets**
  (« 🎵 Titres & couverture » + « 📣 Campagnes Meta »), grille couverture ✅ verte, bug confiance
  « toujours 0 % » corrigé (ProgressColumn ×100 à l'affichage, DB reste [0,1]), campagnes 0 € pré-cochées
  Rejeter (tombstone `campaign_mapping_rejected`, mig 054). Vue splitée en package `meta_mapping/`
  (`_common`/`_tracks`/`_campaigns`/`__init__`, move-only). Garde-fou i18n orphelins (`test_i18n_orphans.py`).
- [x] **B1bis — SACEM + revenu consolidé** (2026-06-11) : parser `sacem_parser.py` (xlsx relevé de compte),
  table `sacem_statement` (mig 055), import xlsx + how-to ; royalties brutes (`repartition`) dans le ROI +
  trace SACEM distincte sur le graphe prévision revenus. **VIEW `v_artist_monthly_revenue`** (mig 056) consolide
  iMusician+DistroKid+SACEM (fin du copier-coller UNION sur ~6 sites ; VIEW read-only hors `_ALLOWED_TABLES`).
  Dépense « Hypeddit » fantôme (budget Meta mal interprété) retirée de tous les points ROI → `total_spend = meta_spend`.
- [x] **B2 — DistroKid** (phases 1+2 livrées 2026-06-10) :
  **Phase 1 — saisie manuelle** : table `distrokid_monthly_revenue` (migration 050,
  `distrokid_schema.py`) ; vue Distributeur partagée (`imusician.py`) — sélecteur
  iMusician/DistroKid/Tous (chart empilé), formulaire de saisie mensuelle EUR
  (défaut = mois précédent), suppression distributor-aware ; ROI Breakheaven somme
  les 2 sources (`kpi_helpers` UNION ALL ×4) ; +5 tests (`test_distrokid_revenue.py`).
  **Phase 2 — import « bank details »** : parser `src/transformers/distrokid_parser.py`
  (TSV **ou** CSV sniffé, fallback latin-1, schéma 15 col post-juillet-2025 + legacy
  `Song/Album`, dédup pré-upsert) ; table `distrokid_sales_detail` USD NUMERIC(14,10)
  (migration 051, `distrokid_csv_schema.py`) ; rollup USD→EUR `distrokid_rollup.py`
  (taux `DISTROKID_USD_EUR_RATE` défaut 0.92, modifiable par import, préserve les
  saisies manuelles) ; intégration Upload CSV (uploader accepte `.tsv`, lecture headers
  robuste encodage+délimiteur, champ taux, hook rollup) ; DAG `distrokid_csv_watcher`
  (15 min, max_active_runs=1, watch `data/raw/distrokid/`) + `debug_distrokid_csv.py` ;
  guide in-app (`csv_guides.py`). Fixture réelle `tests/fixtures/distrokid_bank_sample.csv`
  (BetterKid) ; +17 tests parser. **Validé end-to-end live** : 22 lignes → 4 mois EUR,
  idempotent, DAG chargé sans import error. Format : `dev-docs/distrokid-export-format.md`.
  ⚠️ Reste à confirmer sur TON premier export réel (le sample BetterKid fait foi pour le
  schéma, pas pour l'extension/zip exacts).
- [x] **B3 — Refactor ciblé** (2026-06-09) : vues mapping (`track_mapping`, `meta_mapping`) migrées vers `view_session()` (rule #7). Reste : adoption `view_session()` sur les vues legacy au fil des touches (audit #2).
- [x] **C1 — Alerting erreurs app** (2026-06-09) : `src/dashboard/utils/error_alert.py` (`notify_app_error`, fail-silent, rate-limité, re-raise des signaux st.stop/st.rerun) ; dispatch des vues extrait en `_render_page()` + guard try/except dans `app.py` ; +4 tests.
- [x] **C2 — Backup DB** (2026-06-09) : `tools/db_backup.sh` (pg_dump→gzip + rétention) + `tools/db_restore_test.sh` (drill restauration) + `make backup` / `make backup-test`. Drill validé (78 tables restaurées). Cron VPS = Phase D.
- [x] **C3 — Hardening sécurité (code)** (2026-06-10) : (1) rate-limit FastAPI —
  `src/api/security.py` (NEW), fenêtre glissante en mémoire par IP (120 req/60s global,
  10/300s sur `POST /auth/token`), 429 + Retry-After, `/health` exempt, IP via 1er hop
  X-Forwarded-For derrière proxy ; (2) security headers middleware (nosniff, X-Frame-Options
  DENY, Referrer-Policy, HSTS, Permissions-Policy, CSP `default-src 'none'` sauf /docs+/redoc,
  Cache-Control no-store) — headers outermost donc présents aussi sur les 429 ; (3) timeout
  d'inactivité session Streamlit — `auth.py::_session_idle_expired` dans `require_login()`
  (défaut 60 min, `SESSION_IDLE_TIMEOUT_MINUTES`), session clear + notice à la reconnexion.
  Env vars documentées dans `.env.example`. +14 tests (`test_api_security.py`, TestClient
  sans DB). Limiteur in-memory single-process assumé (ADR-002 : pas de Redis/slowapi) —
  re-évaluer si l'API passe multi-worker en phase D.
- [x] **C4 — i18n EN/FR** (infra 2026-06-09 ; **couverture complète 2026-06-10**) :
  `src/dashboard/utils/i18n.py` (`t()` helper, FR source + fallback), **toggle sidebar**
  (`language_selector`), **navigation entièrement traduite**, +5 tests (garde-fou nav).
  **Couverture totale** : catalogues EN par vue sous `i18n_catalog/` (~47 modules, ~2150 clés,
  auto-mergés par `_load_catalogs()`) — **toutes les vues** (login/inscription, compte, billing,
  admin/ops, packages `trigger_algo/` + `credentials/`, `ml_widgets`, guides CSV). Vérifié :
  410 tests verts, render-smoke live sur les 37 vues, ruff clean, 0 clé sans EN. Commits
  `a672725` + `cde230c`. FR conservé par design : prose `csv_guides.py` (partagé PDF) +
  constantes de labels au niveau module (résolution langue au runtime).
- [ ] **C5 — Benchmark VPS (sizing + topologie)** — **DÉCISION FIGÉE le 2026-06-11** → `.claude/dev-docs/benchmark-deployment-synthesis.md`. Topologie **split** + **VPS choisi** :
  - **Box A — Hetzner CAX31 (ARM Ampere, 8 vCPU / 16 Go / 160 Go NVMe, ~12,50 €/mo)** : streaMLytics (Postgres + Airflow + Streamlit + FastAPI + Caddy) **maintenant**, n8n + ffmpeg d'assemblage **plus tard sur la même box** (16 Go absorbe les deux : streaMLytics 10-50 tenants seul ET le pic combiné ~8-10 Go). Resize vertical Hetzner (~2 min reboot, même disque) vers **CAX41 32 Go (~24,50 €/mo)** seulement au-delà de ~50 tenants ou vidéo lourde/concurrente. **Cible retenue : 10-50 artistes à 3-6 mois.**
    ✅ **PRÉREQUIS ARM64 VALIDÉ (2026-06-11)** : `docker buildx --platform linux/arm64` du `Dockerfile` dashboard → **chaque dépendance résout un wheel aarch64** (numpy/pandas/xgboost/scikit-learn/scikit-image/shap/lime/weasyprint/numba/llvmlite/streamlit/airflow), **zéro `No matching distribution`**, `lime` compilé depuis les sources OK. Le fallback x86 CPX31 **n'est pas nécessaire**. (Fin du build local lente sous émulation QEMU = artefact, pas un problème ; natif ARM = rapide.) Détail : DEVLOG#2026-06-11.
  - **Box B — VPS Windows dédié ISOLÉ** : MT5 live 24/7 (2 vCPU / 4 Go / 50-60 Go, ~10-20 €/mo, ou **VPS broker gratuit**). Downsize de l'actuel surdimensionné (H1 ≠ HFT). Jamais mutualisé (OS + stabilité live + isolation creds broker).
  - **Vidéo (POUR PLUS TARD)** : GPU **serverless pay-per-call** (fal.ai/Replicate, modèles open LTX-Video/Wan) + ffmpeg local + nœud cleanup. **Aucun GPU acheté/loué.** 0 € tant que non déployé.
  - **Scraping** : **proxy résidentiel** (~50-75 €/mo) pour isoler l'IP — pas un 2ᵉ VPS.
  - **Budget always-on streaMLytics = ~13 €/mo tout compris** (CAX31 ~12,50 + domaine ~0,60 + email/backup gratuits). **Restant ouvert** : mesure réelle Mo/session Streamlit sous charge (seuil de resize 16→32 Go). Questions initiales (archivées) :
  1. **Échelle streaMLytics** : nb d'artistes cible à 3 / 6 / 12 mois ? (10 / 100 / 1000 ?) — pilote la RAM (Streamlit garde chaque session en mémoire).
  2. **MT5 / vidéo / scraping / n8n sur le MÊME VPS, ou séparés** (juste mutualisés pour le coût) ?
     ⚠️ **MT5 = Windows-only** → ne tourne PAS sur un VPS Linux/Docker → soit VPS Windows séparé, soit machine dédiée → **casse le « un seul VPS »**.
  3. **Génération vidéo** : rendu GPU ou CPU ? quelle fréquence/volume ? (change radicalement le sizing).
  4. **Budget €/mois** visé pour l'infra ?
  **Reco** : sizer **streaMLytics seul d'abord** (le seul prêt+mergé : postgres + airflow web/scheduler + dashboard Streamlit + API FastAPI + reverse proxy), MT5/vidéo/scraping en couche au-dessus une fois la mutualisation décidée.
  **→ GRILLE EXHAUSTIVE : `.claude/dev-docs/benchmark-deployment.md`** — profil ressources par composant (RAM/CPU/disk/réseau, idle/pic), hypothèses d'échelle, méthodo de load-test (⚠️ Streamlit = WebSockets, pas HTTP), topologie, stockage/I/O, coût, backup/DR/monitoring, critères hébergeur, seuils de scaling, **+ les 2 prompts cross-projets à poser aux IA MT5 / n8n** (§ M) pour récupérer leurs profils ressources et trancher la topologie.
  **Livrable** (→ `dev-docs/deployment.md`) : topologie (1 VPS Linux vs split Linux/Windows), sizing vCPU/RAM/disk par composant, reco hébergeur, estimation €/mois.
- [ ] **C6 — Benchmark nom de domaine + accès public (NEW 2026-06-10)** — **DÉCISION FIGÉE le 2026-06-11** → `benchmark-deployment-synthesis.md` § 9. Vérif RDAP live 2026-06-11 :
  - **Domaine retenu : `streamlytics.fr`** (libre ✅ ; cible FR assumée ; le moins cher ~7 €/an). `streamlytics.com` = **pris** (enregistré 2017 GoDaddy, **parké/site mort**) → écarté ; `streamlytics.app` = libre (alternative HTTPS-forcé si besoin). Option : prendre `.fr` + `.app` (~20 €/an) et rediriger l'un vers l'autre.
  - **Registrar : OVH** (français, le moins cher pour `.fr`, **boîte email gratuite incluse** pour `contact@`). Cloudflare ne vend PAS le `.fr` (mais sa DNS gratuite reste utilisable plus tard pour CDN/anti-DDoS).
  - **TLS : Caddy** sur la Box A (Let's Encrypt auto). Sous-domaines `app.streamlytics.fr` (Streamlit) + `api.streamlytics.fr` (FastAPI / webhook Stripe).
  - **Email** : **2 flux distincts** — (1) **ENVOI** (vérif compte, alertes, digest, Stripe) reste sur le **SMTP Gmail actuel**, rien à changer ; (2) **RÉCEPTION** `contact@streamlytics.fr` = **boîte gratuite OVH** ou **Cloudflare Email Routing** (forward gratuit → Gmail). **Email de domaine = crédibilité, PAS un prérequis Stripe** (Stripe accepte un email quelconque). Bascule expéditeur → `noreply@streamlytics.fr` + SPF/DKIM/DMARC = sujet de **scale**, pas de lancement.
  - **Backup** : `pg_dump` gzippé → **Cloudflare R2 (10 Go gratuits)** ou Hetzner Storage Box (`tools/db_backup.sh` existe).
  - **Restant ouvert** : réservation effective `streamlytics.fr` chez OVH + plan DNS (A `app`/`api` → IP Box A). Questions initiales (archivées) :
  Un domaine est un **PRÉREQUIS**, pas cosmétique : HTTPS exigé par **Stripe** (checkout + webhook) + cookies d'auth + crédibilité SaaS. Sans lui = `http://IP:8501` (inviable).
  1. **Nom de marque** : `streamlytics.{com,io,app,fr}` ? → vérifier dispos + prix (je peux checker).
  2. **Registrar** : Cloudflare (DNS + proxy/CDN gratuit, recommandé) / OVH / Namecheap ?
  3. **Sous-domaines** : `app.X` (dashboard Streamlit) + `api.X` (FastAPI / webhook Stripe) ?
  4. **TLS** : **Caddy** recommandé (Let's Encrypt auto, zéro config) en reverse proxy.
  5. **Email pro** (`contact@X`) pour Stripe + support artistes ?
  6. **Délivrabilité email** (SPF/DKIM/DMARC) pour que les emails de vérification ne finissent pas en spam.
  **Modèle d'accès (déjà construit)** : 1 URL publique → register/login → isolation par `artist_id` → chaque artiste voit ses données, connecte ses credentials, upload ses CSV ; DAGs paramétrés par artiste. Il manque juste : domaine + TLS + reverse proxy + port 443 ouvert.
  **→ Détail complet : `.claude/dev-docs/benchmark-deployment.md` § G** (domaine/registrar/sous-domaines/TLS/email/CDN).
  **Livrable** (→ `dev-docs/deployment.md`) : reco domaine + plan DNS + reverse proxy (Caddy) + schéma d'accès multi-tenant.
- [ ] **D — Déploiement + pentest** (DERNIER, séquencé 2026-06-12) : runbook copier-coller dans
  `deployment.md`. Légende : 🤖 code (moi, PR) · 🧑 ops (toi) · 🤝 sur le VPS. On coche au fil de l'eau.
  - **Phase 0 — Prep code (🤖)** :
    - [x] **0.1** services `dashboard` (Streamlit:8501) + `api` (FastAPI:8502) ajoutés à
      `docker-compose.example.yml` (DATABASE_URL, loopback bind, mount `machine_learning`/`data`).
      Le dashboard tournait sur l'hôte → désormais conteneurisable. ref: DEVLOG#2026-06-12 (suite 6).
    - [x] **0.2** `deploy/Caddyfile` — `app.`→8501 (WebSocket), `api.`→8502, TLS Let's Encrypt auto,
      HSTS + headers sécurité, apex/www → `app.`.
    - [x] **0.3** backup + restore drill validés live (`tools/db_backup.sh` → 516K ; `db_restore_test.sh`
      → 92 tables / 13794 rows / DB jetable droppée).
  - [x] **Phase 1 — Provisioning infra (🧑)** — DONE 2026-06-12. OVH `streamlytics.fr` (compte Particulier)
    + email Zimbra inclus · Hetzner **CPX32** (x86 AMD, 4 vCPU/8 Go, ~16,79 €/mo — **ARM CAX en rupture UE**,
    fallback x86 documenté pris) Ubuntu 24.04 Nuremberg, IP **167.233.92.1** · DNS A `app`/`api`/racine.
    ⚠️ racine a un **doublon** `A 213.186.33.5` (parking OVH) à supprimer. **Gate 1** ✅ (`app`/`api` résolvent).
  - [x] **Phase 2 — Hardening D0 (🤝)** — DONE 2026-06-12. MAJ système, Docker 29.5 + Compose v5.1,
    `ufw` (22/80/443 only, reste deny), `fail2ban`. `.env` prod : mdp Postgres + admin Airflow (`sladmin`)
    rotés, `API_SECRET_KEY` généré, FERNET_KEY **réutilisée** (déchiffrement creds), URLs `https://`,
    perms 600. Postgres/Airflow/Streamlit/API en loopback (compose + ufw). **Gate 2** ✅.
  - [x] **Phase 3 — Déploiement D1 (🤝)** — DONE 2026-06-12. Clone via `GITHUB_TOKEN` (purgé du remote) ;
    **migration données** (dump local → restore : 13 794 lignes S4A, 92 tables, 0 erreur) ; `docker compose
    up -d --build` (5 conteneurs) ; **Caddy v2.11** + cert **Let's Encrypt** auto. **Smoke ✅** : `https://
    app.streamlytics.fr` HTTP 200 + login + données visibles ; `https://api.../health` ok ; HTTP→HTTPS 308.
    ⚠️ **2ᵉ bug fresh-install `init_db.sql`** trouvé (FK `hypeddit_daily_stats`→`hypeddit_campaigns(campaign_name)`
    sans UNIQUE matching) → contourné en provisionnant depuis le dump (mount `init_db.sql` retiré du compose
    serveur). À corriger dans le repo (même classe que le bug youtube ; lié au blocker Postgres-en-CI).
    **Gate 3** ✅ → 🎉 **app live**.
  - [x] **Phase 4 — Activation Stripe (🤝)** — DONE 2026-06-12 (**mode TEST**). Produit Premium 10€/mo +
    Payment Link + webhook (4 events) créés **via l'API Stripe** (clé test). `STRIPE_SECRET_KEY` +
    `WEBHOOK_SECRET` + `CHECKOUT_URL` posés dans le `.env` prod. **Webhook vérifié end-to-end** (événement
    `checkout.session.completed` signé → 200 → `artist_subscriptions` provisionné + `tier=premium`, puis
    nettoyé). **2 bugs corrigés** : billing ne passait pas `client_reference_id` (PR #32) ; le handler 500ait
    car `stripe.Event` (StripeObject) n'a pas `.get()` → parse en dict après vérif signature (PR #33).
    **Restant** : `STRIPE_PORTAL_URL` (portail client, optionnel) ; passage **mode LIVE** = activation complète
    du compte Stripe (KYC + SIRET 939874392 + IBAN) puis recréer produit/link/webhook en live + clés `sk_live`.
    **Gate 4** ✅ (provisioning prouvé en test).
  - [x] **Phase 5 — Pentest D2 (🤝)** — **COMPLET 2026-06-13** (pentest live mené par sondes externes ; Gate 5 entièrement levé, A→G ✅).
    ✅ **A. Recon** : seuls 22/80/443 ouverts ; 5433/5432/8080/8501/8502 **filtrés** depuis l'extérieur.
    ✅ **B. Transport** : HTTP→HTTPS 308 · HSTS (1 an + includeSubDomains) · X-Frame DENY · nosniff ·
    Referrer-Policy · **TLS 1.0 refusé / TLS 1.3 OK**. ✅ **C. Surface** : `/docs`+`/redoc` 404 ; `/.env`,
    `/config.yaml`, `/.git/config` → **faux positif** (catch-all SPA Streamlit en `text/html`, aucun secret).
    **FINDING corrigé** : `/openapi.json` était servi (carte API complète) → gé sur `API_ENABLE_DOCS`, **404**
    désormais (PR #54). ✅ **D. Auth** : tous les endpoints API → 401 sans token, token forgé → 401, webhook
    Stripe sans signature → 400 (fail-closed). **Note auth API** : `/auth/token` était inerte en prod (503) →
    rendu **fonctionnel** (auth DB `saas_users`, lockout partagé, 2FA refusé — PR #56) ; l'API est donc désormais
    une vraie surface authentifiée (le tenant-scoping `require_artist_scope` PR #49 la protège).
    ✅ **E. Lockout brute-force PROUVÉ en direct (2026-06-13)** via l'API : `POST /auth/token` ×6 mauvais mdp →
    401 ×5 puis **429 (verrouillé)** au 6ᵉ (le 5ᵉ pose le verrou) → compteur reset. Verrou **partagé** dashboard↔API.
    ✅ **F. Scan client-side secrets (2026-06-13, suite 15)** — fait **par HTTP** (le MCP Chrome crashe toujours
    « Target closed » en WSL ; son fix exige un vrai redémarrage de Claude Code, non réalisable in-session).
    Résultats : (1) HTML bootstrap = seul inline `window.prerenderReady = false` (standard Streamlit), aucun secret ;
    (2) les 3 chunks JS principaux (index/src/lib) = bundle framework Streamlit générique, **0 hit** sur les motifs
    `sk_live/sk_test/AKIA/fernet/postgres://…/-----BEGIN/*secret*` (le code Python n'atteint jamais le client) ;
    (3) **source maps NON exposés** : `*.js.map` renvoie 200 mais c'est le **catch-all SPA** (HTML `text/html`
    5381 o, identique pour un `.map` inexistant) → **faux positif, même classe que `/.env`/`/config.yaml`**.
    ✅ **G. Messages console live (2026-06-13, suite 15) — MCP Chrome RÉPARÉ.** Cause racine trouvée : pas les
    args sandbox/pipe mais la **résolution de version Chrome** — par défaut (`channel: stable`, pas
    d'`executablePath`) le MCP tente un Chrome récent qui meurt en WSL (« Target closed »). Fix définitif :
    `--executablePath=…/puppeteer/chrome/linux-131.0.6778.204/…/chrome` (Chrome 131 du cache, prouvé OK) dans
    `.mcp.json` (gitignored). Scan console de la page login : 2 messages, **tous bénins** (`[issue]` form field
    sans id/name ×2 ; `[verbose] [DOM]` password field hors `<form>`) — **aucun secret, aucune erreur sensible**.
    Pas de CSP/Permissions-Policy (limite Streamlit, P4). **Gate 5 entièrement levé.**
    ✅ **H. Batterie offensive active (2026-06-13, suite 17) — MITM/TLS + injection.** Lancée en direct
    (openssl + testssl.sh) contre la prod : **(ports)** seuls 22/80/443 ouverts (5432/5433/8080/8501/8502/3000
    filtrés) ; **(downgrade MITM)** TLS 1.0/1.1 **refusés**, TLS_FALLBACK_SCSV « no fallback possible »,
    seuls TLS 1.2/1.3 + ciphers **AEAD/forward-secrecy** (ECDHE-ECDSA-AES-GCM) ; RC4/3DES/NULL/CBC-SHA1 tous
    **rejetés** ; **(CVE TLS)** Heartbleed/CCS/Ticketbleed/ROBOT/POODLE/CRIME/SWEET32/FREAK/DROWN/LOGJAM/BEAST/
    LUCKY13/Winshock = **not vulnerable** ; reneg sécurisée OK ; cert LE ECDSA valide (SAN match). **Seul flag :
    BREACH** « potentially » (compression gzip HTTP) — exploitabilité faible (Streamlit websocket, pas de secret
    reflété en réponse) + désactiver gzip dégraderait le LCP déjà lent → **accepté P4** comme le no-CSP.
    **(SQLi)** 3 payloads (`' OR '1'='1`, `'--`, `UNION SELECT`) sur `/auth/token` → **401 propre, 0 erreur SQL**
    (requêtes paramétrées tiennent) ; **(surface)** `/.env /.git/config /openapi.json /docs /redoc /actuator` =
    404 ; endpoints protégés = 401, JWT forgé rejeté, webhook sans signature = 400 fail-closed.
    **Non testé (refusé volontairement)** : DoS volumétrique sur la prod (risque service + ToS Hetzner) →
    recommandation = **Cloudflare gratuit** (WAF + anti-DDoS + cache, comble aussi l'absence de WAF). RCE : surface
    nulle (0 `eval/exec/pickle/subprocess/shell` dans `src/`), non fuzzé. Phishing = hors-scope app (social).
  - ~~Phase 6 — Box B MT5~~ — **RETIRÉ 2026-06-13 : hors scope de streaMLytics** (projet trading MT5 séparé, traité ailleurs).

### E — Post-déploiement : beta privée → growth (séquencé, 2026-06-11)

> **Ordre imposé par l'utilisateur** : déployer (D) → **tester l'app avec des proches (beta privée)** →
> **seulement ensuite** landing + marketing payant. On ne lance pas d'acquisition payante sur une app
> non éprouvée. Détail archi : ADR-005 (déploiement) + `deployment.md`.

- [ ] **E1 — Beta privée avec des proches** (P3, AVANT tout marketing) — `streamlytics.fr` déployé mais
  diffusion **restreinte** (lien partagé à la main, pas de pub). Objectif = éprouver le funnel réel
  (register → vérif email → connexion credentials → upload CSV → KPIs → export) sur des comptes tiers
  réels, détecter les frictions d'onboarding et les bugs multi-tenant que le seul tenant `1x7xxxxxxx`
  ne révèle pas. Sortie = liste de frictions corrigées avant E2.
  Leviers déjà en place : compteur « Live Activity » (`register.py`), onboarding tracker (Brick 29).
  ✅ **PRÉ-REQUIS VALIDÉS 2026-06-13** (test beta réel `127bpmin@gmail.com`, plusieurs passes) : D fait (HTTPS
  live) ; **délivrabilité email résolue** → Brevo + domaine authentifié (DKIM/DMARC), `noreply@streamlytics.fr`
  → **boîte de réception** (le Gmail perso tombait en spam) ; funnel **complet et poli** : inscription allégée
  (nom+email+mdp, slug/username auto-cachés), **login email OU username**, vérif instantanée, welcome + **2 PDF
  FR+EN** en PJ. Bugs corrigés : SMTP env-first (#35), page vérif bloquante (#36), expéditeur dédié (#37),
  app-password Gmail, rebrand (#40), guide bilingue (#43). **Reste** : décider le moment d'inviter + i18n du
  *contenu* des emails (anglais, non bloquant).

- [ ] **E2 — Landing page marketing + pixel + CAPI** (P3 growth, APRÈS E1) — promouvoir l'app via
  campagnes (Meta/Google/TikTok). **Contrainte structurante : Streamlit ne peut pas héberger de pixels
  client** (strippe `<script>`, sandbox iframes `components.html`, re-run complet — cf. item PostHog
  différé § « Deferred »). Donc :
  - [ ] **Landing statique SÉPARÉE de l'app** : `streamlytics.fr` (racine + `www`) → landing **statique**
    (reco **Astro/HTML+Tailwind servi par Caddy** sur Box A = 0 €, contrôle total des `<script>` ;
    alternative no-code Framer/Webflow ~10-25 €/mo). `app.streamlytics.fr` = Streamlit (inchangé),
    `api.streamlytics.fr` = FastAPI. **Ne jamais mettre de pixel dans l'app Streamlit.**
  - [ ] **Pixel client sur la LANDING uniquement** : Meta Pixel + GA4 `gtag` + (option) TikTok pixel →
    `PageView`, `ViewContent`, `Lead` (clic CTA « Essai gratuit »). **Bannière de consentement RGPD +
    Consent Mode v2 AVANT chargement** (UE ; processeur tiers à déclarer dans la privacy policy).
  - [ ] **CAPI server-side depuis FastAPI** (obligatoire ici, pas optionnel) pour les conversions
    profondes que le pixel client rate (cross-domain, ad-block, iOS14) : `CompleteRegistration` à
    l'inscription, `Subscribe`/`Purchase` **branchés sur le webhook Stripe existant**
    (`checkout.session.completed`). Réutilise le SDK `facebook-business` déjà dans `requirements.txt`
    (POST `graph.facebook.com/{PIXEL_ID}/events` + `access_token`). Idem GA4 Measurement Protocol.
  - [ ] **Pont d'attribution (stitching)** — GRATUIT grâce aux sous-domaines : le pixel pose `_fbp`/`_fbc`
    (contient `fbclid`) sur le **domaine parent `streamlytics.fr`** → **lisibles par FastAPI sur
    `api.streamlytics.fr`**. Au register : persister `_fbp`/`_fbc` + `UTM`/`fbclid`/`gclid` (passés en
    query string landing→app) + **email hashé SHA-256** + IP + user-agent sur la ligne user. **Dédup
    pixel↔CAPI par `event_id` partagé.** Jamais d'email en clair (Meta exige SHA-256).
  - **Mapping d'événements exact** (quel event à quelle étape) à préciser au moment de l'implémentation.
  - Note : le `usage_events` server-side (first-party) peut rester comme sink interne ; PostHog
    client-side reste différé (Streamlit) — cf. § « Deferred ».

### Pré-déploiement — optimisations & ship-blockers (2026-06-11)

Trois audits multi-agents (sécu/perf, intégrité données, couverture tests) avant l'ouverture
publique. Verdict intégrité = **GO, convergent** (oublis localisés, pas systémique). PR #21
(perf + sécu) + PR #22 (bugs intégrité + tests) **mergées**.

- [x] **Perf DB** : migrations **057** (5 index composites `(artist_id, date)`) + **058** (3 index :
  `etl_run_log(artist_id,status)` page home, `etl_run_log(started_at)`, `instagram_daily_stats`) ;
  fusion du double-scan de `v_artist_monthly_revenue` dans `get_monthly_roi_series`.
- [x] **Perf/RAM dashboard** : cache `get_artist_plan` (+invalidation sur mutation de plan),
  `get_roi_data`/`get_monthly_roi_series`/`_load_scored_tracks` ; libération des blobs export ;
  mémoïsation des modèles ML ; throttle du ping DB ; `meta_token_refresh` 1 connexion réutilisée.
- [x] **Durcissement sécurité (code)** : `docker-compose.example.yml` tracké (secrets en `${VAR}`,
  binding loopback Postgres/Airflow) ; JWT secret éphémère (plus de fallback public) ; `/docs`+`/redoc`
  off par défaut ; CORS env ; webhook Stripe fail-closed. Checklist ops **D0** dans `deployment.md`.
- [x] **Bugs intégrité** : 2 requêtes S4A sans le filtre `1x7xxxxxxx` (Coût/stream ~2× faux) +
  2 requêtes `meta_x_spotify` non scopées par `artist_id` (fuite cross-tenant sur collision de nom) → corrigés.
- [x] **Tests des chemins argent/tenant** (DB-free → tournent en CI) : `test_plan_gating.py`
  (free verrouillé hors premium), `test_tenant_isolation.py` (`artist_id_sql_filter`), `test_revenue_math.py`.
- [x] **Postgres en CI** (P3 infra/test) — **FAIT 2026-06-13.** `ci.yml` a un service `postgres:17`
  **provisionné** (étape « Provision Postgres » : `init_db.sql` + `migrations/*.sql`, fail-loud si `saas_artists`
  absent → pas de skip silencieux) + `DATABASE_URL` sur l'étape tests. Le render-smoke **39 vues** + les tests
  ML DB tournent désormais en CI. Le « bloquant » `\c`/seed s'est avéré **non bloquant** : avec un service dont
  `POSTGRES_DB=spotify_etl` existe déjà, le `\gexec CREATE DATABASE` no-op et `\c` reconnecte ; le seed est en
  `ON CONFLICT DO NOTHING`. Validé localement (Postgres éphémère) : provisioning **0 erreur**, **39/39 vertes**,
  suite complète **555 passed**. `_db_ready()` rendu conscient de `DATABASE_URL` (skippait sinon sur le check
  socket 5433 codé en dur). **2 bugs fresh-install corrigés au passage** : `campaign_track_mapping` absente du
  bootstrap → ajoutée à `init_db.sql` (débloque migrations 011/049 + vue meta_cpr_optimizer) ; `alerts` crashait
  `px.area` sur DataFrame vide → guard empty-state. ref: DEVLOG#2026-06-13.
- [x] **Cohérence env-first des 11 `*_schema.py`** (P3 tech debt) — DONE 2026-06-13 (suite 15). Les 11 schémas
  (`apple_music_csv/app_costs/distrokid_csv/distrokid/hypeddit/imusician_csv/imusician/instagram/stripe/wrapped/
  youtube`) faisaient `config['database']` en **subscript direct sans fallback `DATABASE_URL`** → `KeyError` si
  lancés en prod (pas de config.yaml). Fix : nouvelle factory **`PostgresHandler.from_env_or_config()`**
  (`postgres_handler.py`) = `DATABASE_URL` d'abord, sinon `config.yaml`, sinon `RuntimeError` clair (plus de
  `KeyError`) — sans dépendance Streamlit (contrairement à `get_db_connection()`, couplée au dashboard). Les 11
  `__main__` appellent désormais la factory ; imports `config_loader` morts retirés (ruff vert). Vérifié : path
  DATABASE_URL (parse OK), path config-absent → RuntimeError, 11 modules `py_compile`, suite **519 passed /
  39 skipped**. ref: DEVLOG#2026-06-13 (suite 15).
- [x] **DistroKid — persister le taux FX** (P2 data integrity) — DONE 2026-06-12. `migrations/059_distrokid_fx_rate.sql`
  ajoute `fx_rate NUMERIC(8,5)` (NULL pour les saisies manuelles EUR, renseigné pour les imports) sur
  `distrokid_monthly_revenue` ; `distrokid_rollup.py` l'écrit (INSERT + ON CONFLICT UPDATE, 3 placeholders de taux).
  `revenue_eur` redevient réversible (`revenue_eur / fx_rate`). Le taux reste aussi dans `notes` (affichage humain).
  Schéma canonique (`distrokid_schema.py` + `init_db.sql`) aligné pour les fresh installs. Vérifié live (synthetic
  $10 @ 0.85 → 8,50 € → reverse 10,00 $) + 3 tests DB-free (`test_distrokid_revenue.py`). Migration appliquée live.
  ref: DEVLOG#2026-06-12.
- [x] **API `/ml/predictions` cassé** (P4) — FIXED 2026-06-13. Le endpoint lisait des colonnes inexistantes
  (`score`/`tier`/`predicted_at`) → 500 systématique. Contrat API redessiné : renvoie les vraies probabilités
  `dw/rr/radio_probability` + `prediction_date` (dernière ligne par titre via `DISTINCT ON (song)`), scopé
  tenant par `require_artist_scope` + filtre nom `1x7xxxxxxx`. Plus de KNOWN-BROKEN. ref: DEVLOG#2026-06-13.

### P3 — UX / Features (closed, 2026-06-12 — pre-deploy validation)

- [x] **Admin "Voir comme" toggle + artist plan vision** — `app.py::show_view_as_selector` (radio
  Admin/Premium/Free, admin-only); `get_artist_plan()` reads the session `_view_as` override; effective
  role='artist' when impersonating free/premium (hides `_ADMIN_ONLY`). Previews ACCESS only — data stays
  admin-wide (`get_artist_id()` untouched). Artist sidebar shows a plan badge + 🔒=Premium marker.
  **Root cause of "no free vision": the sole tenant is premium and the owner is admin → no free account
  ever existed** (not a gating bug). ref: DEVLOG#2026-06-12 (suite 5).
- [x] **Billing premium features live** — 3 bullets in ✓ (no "coming soon"): daily auto-download of
  S4A+Apple CSV, CPR budget&streams optimization, video creative generation 60+/campaign + targeting.
  EN+FR catalogs synced. `SERVICE_CONTACT_EMAIL` → `1x7xxxxxxx@gmail.com`. ref: DEVLOG#2026-06-12 (suite 5).
- [x] **E2E outcome chain proven** — synthetic self-cleaning script: saisie upsert (7d+28d) → real
  `label_predictions()` = 1 label (`y_dw/y_rr/y_radio` vs thresholds 137/130/639, horizon 30d) → trigger
  read OK → idempotent (2nd run=0) → 0 residual. Plumbing was already correct; the chain had simply never
  been exercised (`s4a_song_algo_outcomes` was empty). ref: DEVLOG#2026-06-12 (suite 5).

## Deferred — revisit ONLY if migrating to React (ADR-003 reversal)

Items that are currently irrelevant / worked-around **because of Streamlit** and would become
natural (or need redoing) under a React/Next.js front-end. Parked here per user request
(2026-06-09) so a future migration picks them up. ADR-003 currently keeps Streamlit.

> **PARKED — not open backlog.** Listed as plain bullets (no `[ ]`) **on purpose** so `/resume`
> does not recount them as actionable items. They re-activate only on an ADR-003 reversal
> (migration to React/Next.js). Do not treat them as a to-do until then.

- **PostHog full client-side analytics** — autocapture, **session replay**, heatmaps,
  client funnels/retention. Blocked today: Streamlit strips `<script>` and sandboxes
  `components.html` iframes, and re-runs the whole script (no stable DOM / client event model).
  Under React the standard JS snippet drops in → reconsider PostHog (cloud-w/-consent or
  self-host) and likely retire the homegrown event log's *capture* layer (the `usage_events`
  table can remain as a server-side sink). Needs RGPD consent banner for a 3rd-party processor.
- **Interactive / exact-parity report charts (PDF & in-app)** — the PDF export rebuilds
  every chart in **matplotlib→PNG** (`pdf_charts.py`) because `kaleido` (Plotly→image) is absent
  and Streamlit can't headless-render its Plotly figures. Under React, reports could share the
  *same* chart components (client-side render / a proper reporting service), giving interactive
  + pixel-parity charts and removing the matplotlib duplication. ref: export-pdf overhaul
  2026-06-09.
- **Cold-start bundle / perf** — already audited (line ~295): the #1 cold-start bottleneck
  is the **Streamlit JS bundle** (~532 KiB), not Python. React+Next (code-splitting → ~100–150
  KiB initial) is the structural fix. Python-side caching/lazy-import work stays valid for
  subsequent renders only.
- **Rich client interactions** — anything that fought the rerun model (live event hooks,
  drag/drop, fine-grained widget state, real-time updates without full reruns) becomes
  first-class under React; revisit UX patterns that were simplified to fit Streamlit.
