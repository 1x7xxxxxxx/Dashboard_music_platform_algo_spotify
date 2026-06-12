# DEVLOG — Music Platform Dashboard

Journal de session structuré. Mis à jour en fin de session via :
> "Append today's session summary to DEVLOG.md"

---

## 2026-03-27 — iMusician CSV import + DAG fixes + debug scripts

### Features
1. **iMusician CSV import (full pipeline)** — two iMusician export formats now auto-ingested:
   - `src/transformers/imusician_csv_parser.py` — `detect_csv_type()`, `parse_release_summary()`, `parse_sales_detail()`, encoding fallback (utf-8 → utf-8-sig → latin-1 → cp1252)
   - `src/database/imusician_csv_schema.py` — two new tables: `imusician_release_summary`, `imusician_sales_detail`
   - `migrations/010_imusician_csv_tables.sql` — idempotent migration applied ✅
   - `airflow/dags/imusician_csv_watcher.py` — `*/15 * * * *` DAG, branch on CSV presence, auto-detects type, upserts + archives
   - `airflow/debug_dag/debug_imusician_csv.py` — 5-step debug + `--write` flag
   - `src/dashboard/views/imusician.py` — 3rd tab "📂 Import CSV" (uploader, type badge, 10-row preview, confirm)
   - `src/dashboard/views/upload_csv.py` — 2 new platforms: iMusician Résumé + Rapport de vente

### Bugs fixed
2. **SoundCloud 403 not triggering auto-refresh** — `status_code == 401` → `in (401, 403)`. IP block confirmed; auto-refresh mechanism correct, key persisted to DB.
3. **`debug_soundcloud.py` step_6 crash** — `SoundCloudCollector.__new__()` bypasses `__init__` → `self.session` never set. Fixed: manual `requests.Session()` init after construction.
4. **YouTube UniqueViolation on retry** — `youtube_channel_history` INSERT → upsert with `ON CONFLICT (artist_id, channel_id, (collected_at::date))`; `youtube_video_stats` per-row loop → `upsert_many()` with functional conflict key.
5. **`ml_scoring_daily` TypeError** — `get_active_artists()` returns `List[Tuple]`, code was accessing `artist['id']`. Fixed: `for artist_id, name in artists:`.
6. **8 debug scripts broken sys.path** — all used `.parent` (→ `airflow/debug_dag/`) instead of `.parent.parent.parent`. Fixed across: debug_youtube, debug_meta_config, debug_spotify_api, debug_instagram, debug_meta_insights, debug_s4a, debug_apple_music.
7. **`debug_data_quality_check.py` missing** — created; implements all 4 DAG checks inline (no Airflow import, no `fcntl` crash on Windows).
8. **`use_container_width` deprecation** — replaced `width='stretch'` in trigger_algo.py, airflow_kpi.py, etl_logs.py.
9. **RGPD notice on login** — added `st.caption` below sign-in form (bcrypt, no plaintext storage).

### Statut
✅ Tables `imusician_release_summary` + `imusician_sales_detail` créées (0 rows, ready for import).
⏳ SoundCloud / Instagram: IP block — retrigger after credentials refreshed.

---

## 2026-03-12 — Session de debug post-test dashboard 🔧

### Bugs corrigés
1. **`pdf_exporter.py`** — `WHERE is_active = TRUE` → `WHERE active = TRUE` (colonne saas_artists s'appelle `active`)
2. **`kpi_helpers.py`** — Toutes les refs à `meta_insights` (ancienne table API) remplacées par `meta_insights_performance_day` (table CSV active). Colonne `date` → `day_date`.
3. **`csv_exporter.py`** — Idem + correction colonne `date_start` → `day_date`
4. **Création `scripts/create_missing_tables.sql`** — Script idempotent pour toutes les tables manquantes en DB : `imusician_monthly_revenue`, `ml_song_predictions`, 4 tables `meta_ads_*`, 10 tables `meta_insights_*`

### Cause racine tables manquantes
`init_db.sql` ne s'exécute qu'une seule fois au 1er démarrage Docker. Les Bricks 7 (iMusician), 9 (ML), et les tables Meta n'étaient pas dans la DB. Le script de migration résout ça.

### Bugs supplémentaires corrigés (session 2)
5. **`freshness_monitor.py`** — `meta_insights` → `meta_insights_performance_day`
6. **Deprecation `use_container_width`** — remplacé par `width='stretch'`/`'content'` dans 8 views
7. **`use_column_width`** — `st.image` dans `ml_performance.py` → `use_container_width`
8. **`apple_music.py`** — table `apple_songs_history` (inexistante) → `apple_daily_plays` + filtre `artist_id` sur query LAG
9. **Sélecteurs "dernière release"** — tous les selectbox/multiselect songs triés par `MIN(date) DESC` :
   - `trigger_algo.py`, `spotify_s4a_combined.py`, `apple_music.py` : `GROUP BY song ORDER BY MIN(date) DESC`
   - `soundcloud.py` : tri par `playback_count DESC` (proxy car pas de date release)
   - `meta_x_spotify.py` : `ORDER BY release_date DESC NULLS LAST`

### Statut
✅ **Tables créées** : script appliqué via docker exec — 16 tables OK + s4a_songs_global + s4a_audience créées, contrainte `unique_song_date` supprimée.

### Bugs DAG corrigés
- **`spotify_api_daily.py`** — `conflict_columns=['track_id','date']` → `['artist_id','track_id','date']` sur `track_popularity_history`. DAG retesté → success ✅
- **`apple_music_csv_watcher.py`** — injection `artist_id` depuis conf + `conflict_columns=['song_name']` → `['artist_id','song_name']`
- **`s4a_csv_watcher.py`** — injection `artist_id` depuis conf + conflict_columns vers nouvelles contraintes (`artist_id` préfixé)

### Audit DB (état réel)
Tables existantes antes migration : 22 (sans imusician, ml_predictions, meta_insights_*_*)
Tables manquantes créées : `imusician_monthly_revenue`, `ml_song_predictions`, 14 tables meta_insights_*, `s4a_songs_global`, `s4a_audience`
Contrainte dupliquée supprimée : `s4a_song_timeline.unique_song_date` (remplacée par `artist_id_song_date_key`)

---

## 2026-03-12 — Session 3 : Credentials, vues opérationnelles, logs DAGs 🔧

### Ce qui a été fait

#### Credentials & Debug API
- **Instagram/Meta** : renouvellement token long-lived (60j) via Graph API Explorer + Debugger. Token opérationnel en DB.
- **SoundCloud** : `client_id` mis à jour via DB. **Problème persistant : 401 API** — le client_id doit être capturé depuis le trafic réseau navigateur (F12 → Network → `api-v2.soundcloud.com`), pas depuis la Developer Console.
- **Diagnostic SoundCloud** : erreur identifiée dans les logs Airflow — `❌ Erreur API 401 / 0 titres trouvés` → échec silencieux (DAG marque success mais 0 données). `soundcloud_tracks_daily` : 17 lignes, toutes du 2025-12-16.

#### Nouvelle vue : 🔧 Liens & Outils (`useful_links.py`)
- 5 onglets : Liens Externes, Outils Locaux, Docker & Infra, Guide Credentials, Debug & Scripts
- Liens directs tous services externes (Meta, Spotify, SoundCloud, YouTube, Apple, iMusician)
- Liens directs vers chaque DAG grid Airflow (`localhost:8080/dags/{dag_id}/grid`)
- Commandes Docker (start/stop/rebuild/logs/backup DB)
- Guide credentials step-by-step par plateforme avec durées d'expiration
- Requêtes SQL de vérification rapide par source
- Vue **admin uniquement** (cachée pour rôle `artist`)

#### Monitoring ETL — onglet Logs par Run (`airflow_kpi.py`)
- **3 méthodes ajoutées dans `AirflowMonitor`** : `get_dag_list()`, `get_runs_for_dag()`, `get_task_instances()`, `get_task_log()`
- **Nouvel onglet "📋 Logs par Run"** dans la page Monitoring ETL :
  - Sélecteur DAG + Run (20 derniers, avec icône état 🟢🔴🔵)
  - Tableau des task instances (état, durée, tentative n°)
  - Sélecteur task + numéro tentative
  - Bouton "Charger les logs" → `st.text_area` scrollable 500px + métriques (lignes/erreurs/warnings) + expander erreurs uniquement

#### Accueil — Statut des pipelines (`home.py`)
- **`_section_dag_status()`** : grille 5 colonnes, 1 card par DAG
  - Icône plateforme + nom + état coloré (🟢🔴🔵⚫) + date dernier run
  - Chargé via `AirflowMonitor.get_runs_for_dag(limit=1)` par DAG
  - Graceful fallback si Airflow inaccessible

#### Bugfix `use_container_width` — vague finale
- `useful_links.py` : 4 occurrences `st.link_button(use_container_width=True)` → `width='stretch'`
- Toutes les views auditées — plus aucun warning deprecation attendu

#### Bugfix `st.number_input` dans Logs par Run
- `try_number = 0` pour tâches skipped → `min_value=1` violé → crash `StreamlitValueBelowMinError`
- Fix : `max_attempt = max(try_number, 1)`

### Statut global
- ✅ Instagram credentials opérationnels — DAG `instagram_daily` à retrigger
- ⚠️ SoundCloud : credential 401 persistant — client_id à re-capturer via navigateur
- ✅ Vue Liens & Outils créée
- ✅ Logs DAG dans Streamlit opérationnels
- ✅ Statut pipelines sur l'accueil

### Reste à faire (P1)
- **SoundCloud client_id** : capturer depuis `api-v2.soundcloud.com` en trafic navigateur (voir procédure dans DEVLOG), tester l'URL directement, puis sauvegarder en DB + retrigger DAG
- Vérifier que `instagram_daily` retourne bien des données après credentials mis à jour

---

## 2026-03-11 — Brick 13 : Export CSV global ✅

### Ce qui a été fait
- `src/dashboard/utils/csv_exporter.py` — `export_all(db, artist_id) → io.BytesIO`
  - 21 tables : S4A (3), Apple (3), YouTube (6), SoundCloud (1), Instagram (1), Meta (4), Hypeddit (2), iMusician (1)
  - Filtre `artist_id` obligatoire sur toutes les tables
  - Filtre `AND song NOT ILIKE '%1x7xxxxxxx%'` sur `s4a_song_timeline`
  - ZIP avec un CSV par table + `_index.txt` récapitulatif
  - Tables absentes ou vides : sautées silencieusement (pas d'erreur)
- `src/dashboard/views/export_csv.py` — page dédiée
  - Admin : sélecteur artiste (dropdown)
  - Artiste : artist_id depuis session_state
  - Pattern identique à export_pdf.py (generate → session_state → download_button)
- `app.py` — "⬇️ Export CSV" ajouté à la nav (tous rôles) + routing

### Choix techniques
- ZIP en mémoire (`io.BytesIO` + `zipfile.ZipFile`) → pas de fichier temporaire sur disque
- `db.fetch_df()` par table → pandas to_csv direct dans le ZIP
- Séparation propre utilitaire (csv_exporter.py) / UI (export_csv.py)

### Statut : ✅
### Prochaine étape : Brick 14 (FastAPI) ou Brick 15 (CI/CD Railway) — PRIORITÉ 4

---

## 2026-03-11 — Brick 12 : Export PDF Rapport Artiste ✅

### Ce qui a été fait
- **`requirements.txt`** — `weasyprint>=60.0` ajouté
- **`src/dashboard/utils/pdf_exporter.py`** — NOUVEAU
  - `collect_report_data(db, artist_id, months=12)` → dict KPI complet (fraîcheur, streams, popularity, ROI)
  - `render_html(data, artist_name)` → chaîne HTML avec CSS embarqué (template inline, pas de fichier externe)
  - `generate_pdf(db, artist_id, artist_name=None, months=12)` → bytes PDF via `WeasyPrint.HTML.write_pdf()`
  - Import WeasyPrint tardif : `ImportError` propre si non installé, sans bloquer les autres pages
- **`src/dashboard/views/home.py`** — section `_section_pdf_export(artist_id)` ajoutée
  - Bouton "📄 Générer rapport PDF" → spinner → bytes stockés dans `st.session_state`
  - `st.download_button` apparaît après génération (persiste entre reruns via session_state)
  - DB connection indépendante (ouverte/fermée uniquement au clic)
  - Fallback gracieux si weasyprint absent (message d'installation)

### Choix techniques
- Template HTML inline dans `pdf_exporter.py` (pas de fichier Jinja2 séparé — rapport pas assez complexe)
- `artist_id=None` → rapport global (admin), `artist_id=1` → rapport artiste filtré
- PDF généré en mémoire (bytes), jamais écrit sur disque — téléchargement direct via Streamlit

### Statut
✅ `weasyprint-68.1` installé et testé (génère PDF OK, libs système déjà présentes sur WSL2)
✅ Syntaxe OK (py_compile) — 4 fichiers

### Session 2 : UI paramétrable
- **`src/dashboard/views/export_pdf.py`** — NOUVELLE page dédiée
  - Sélecteur artiste (admin : dropdown `saas_artists`, artiste : label fixe)
  - Sélecteur période (3/6/12 mois, cette année, dates custom avec date_input)
  - Cases à cocher par section : Fraîcheur, Streams, KPI, ROI, Focus chansons
  - Multiselect chansons (chargé dynamiquement selon artiste, visible si Focus coché)
  - Aperçu texte du rapport avant génération
  - Bouton "Générer" → spinner → `st.download_button` persistant via session_state
- **`pdf_exporter.py`** refactorisé
  - `generate_pdf()` accepte `from_date/to_date` (prioritaires sur `months`), `sections`, `songs`
  - `collect_report_data()` supporte `songs` list → appelle `_collect_songs_focus()`
  - `_collect_songs_focus()` : streams période + 7j + ML predictions par chanson
  - `_render_songs_focus()` : bloc par chanson avec barre de probabilité ML inline
  - `get_available_songs()` + `get_artists_list()` exposées pour la vue
  - `render_html()` accepte `sections` dict → sections optionnelles
- **`home.py`** — bouton "⚡ Rapport rapide" (12 mois, toutes sections) + lien vers page dédiée
- **`app.py`** — "📄 Export PDF" ajouté nav + routing

---

## 2026-03-11 — Brick 17 : ML Dashboard Upgrade trigger_algo + vue Performance Modèles ✅

### Ce qui a été fait
- **`src/dashboard/views/trigger_algo.py`** — upgrade complet
  - Lecture de `ml_song_predictions` (dernière prédiction par song+artist_id)
  - Barres de probabilité ML (DW, RR, Radio) remplacent les heuristiques hardcodées
  - Forecast streams 7j (DW/RR regressor) affiché sous chaque barre
  - Section "Facteurs clés" : top 3 points forts / à améliorer depuis `features_json` (dé-log automatique des features log-transformées)
  - Fallback heuristique (seuils 1k/10k/pop30) si aucune prédiction ML + badge "⚠️ Heuristique"
  - Projection linéaire J+28 conservée (heuristique uniquement)
  - Filtrage `artist_id` depuis session state (admin = toutes songs, artiste = les siennes)
- **`src/dashboard/views/ml_performance.py`** — NOUVEAU (admin only)
  - 5 onglets : DW Classifier, RR Classifier, Radio Classifier, DW Regressor, RR Regressor
  - Affiche les PNGs d'artefacts MLflow depuis `machine_learning/mlruns/<exp>/<run>/artifacts/`
  - Onglet "Prédictions en DB" : tableau des 100/200 dernières prédictions avec filtre par chanson
- **`app.py`** — "🤖 Perf. Modèles ML" ajouté (admin only, `_admin_only` set)

### Choix techniques
- Images servies directement depuis le filesystem local (pas de base64) via `st.image(str(path))`
- `_MODELS` liste statique des 5 best runs (identiques aux paths dans `ml_inference.py`)
- Features "négatifs" : direction définie par `_FEATURE_LABELS` (DaysSinceRelease = high is bad)

### Statut
✅ Brick 17 complète — syntaxe OK (py_compile 3/3)

### Prochaine étape
Tester le dashboard (Docker running + streamlit). Brick 12 (Export PDF) ou 13 (Export CSV) ensuite.

---

## 2026-03-11 — Brick 16 : ML Scoring Table + Prediction Pipeline ✅

### Ce qui a été fait
- **`src/database/ml_schema.py`** — NOUVEAU : table `ml_song_predictions` (UNIQUE sur artist_id+song+prediction_date+model_version)
- **`init_db.sql`** — section 9 ajoutée : CREATE TABLE ml_song_predictions + 3 index
- **`src/utils/ml_inference.py`** — NOUVEAU : 4 fonctions
  - `load_model(key)` : chargement XGBoost .ubj avec cache mémoire (5 modèles : DW/RR/Radio classifier + DW/RR regressor)
  - `build_features(db, artist_id, song)` : 13 features avec 6 calculées depuis DB + 7 imputées
  - `score_song(features)` : predict_proba + predict pour les 5 modèles
  - `score_all_songs(db, artist_id)` : boucle sur chansons actives (35 derniers jours)
- **`airflow/dags/ml_scoring_daily.py`** — NOUVEAU : DAG schedule 06h00 UTC, boucle sur tous les artistes actifs
- **`airflow/debug_dag/debug_ml_scoring.py`** — NOUVEAU : tableau résultats (dry-run, pas d'écriture DB)
- **`requirements.txt`** — `xgboost>=2.0.0` ajouté
- **`docker-compose.yml`** — volume `./machine_learning:/opt/airflow/machine_learning:ro` ajouté aux 3 services Airflow

### Choix techniques
- Chargement XGBoost natif (.ubj) plutôt que MLflow runtime → évite grosse dépendance mlflow en prod
- StandardScaler **non appliqué** (pas sauvegardé dans le notebook) → modèle version "v1_noscaler", probabilités relatives entre chansons mais pas absolues calibrées
- `ML_MODELS_PATH` env var surcharge le chemin des modèles pour faciliter les tests locaux vs Docker
- Features imputées : NonAlgoStreams=0, Saves=0, PlaylistAdds=0, DiscoveryMode=0, ReleaseConsistencyNum=0.5

### Statut
✅ — 4/4 fichiers Python passent py_compile. Brick 16 complete (sauf validation avec vraies données).

### Prochaine étape
Brick 17 : Upgrade trigger_algo + vue ML (remplace heuristiques par probabilités ML)

---

## 2026-03-11 — Brick 11 : Monitoring + Alerting ✅

### Ce qui a été fait
- **`src/utils/email_alerts.py`** — réécrit complet : `import os` manquant ajouté, classe `EmailAlert` avec `send_alert()` retournant bool, nouveau `dag_failure_callback(context)` compatible Airflow `on_failure_callback`
- **`src/utils/freshness_monitor.py`** — NOUVEAU : `check_freshness(db, artist_id)` → liste de résultats par source (last_dt, age_h, stale/ok), `run_freshness_alerts()` → envoie email groupé pour sources stale. Seuils : 48h pour API (YouTube/SoundCloud/Instagram/Meta), 7j pour CSV (S4A/Apple Music)
- **8 DAGs** — `on_failure_callback: _on_failure_callback` ajouté dans `default_args` (spotify, youtube, soundcloud, instagram, meta_config, meta_insights, s4a_csv_watcher, apple_music_csv_watcher). Callback défini localement, wrappé en try/except (import défensif de `src.utils.email_alerts`)
- **`src/dashboard/app.py`** — `_check_db_health()` ajouté dans `main()` : test de connexion au démarrage, bannière `st.error` rouge si PostgreSQL down
- **`src/dashboard/views/airflow_kpi.py`** — onglet "📡 État des sources" ajouté (tableau : source, dernière collecte, âge, seuil, statut 🟢/🔴/⚫). Onglet "📊 Performance DAGs" conservé intact avec indentation corrigée

### Choix techniques
- Callback DAG défini inline dans chaque DAG (pas d'import top-level) → évite les erreurs au chargement du DAG si `src/` indisponible
- `freshness_monitor.py` découplé de `kpi_helpers.py` (config MONITOR_TARGETS séparée) pour usage depuis Airflow et depuis Streamlit
- Health check DB dans `main()` (pas dans chaque view) → visible dès l'ouverture du dashboard

### Statut
✅ — 12/12 fichiers passent py_compile. Brick 11 complete.

### Prochaine étape
Brick 16 : ML scoring table + DAG scoring quotidien (priorité 3)

---

## 2026-03-11 — Brick 10 : Tests unitaires ✅

### Ce qui a été fait
- `requirements-dev.txt` créé : pytest>=8.0, pytest-mock>=3.12, pytest-cov>=5.0
- `tests/conftest.py` : fixture `tmp_csv` factory (fichiers CSV temporaires)
- `tests/test_parsers.py` (38 tests) : S4ACSVParser, AppleMusicCSVParser, MetaCSVParser — cas normaux, CSV malformés, colonnes manquantes, formats numériques (virgule, float), déduplication
- `tests/test_credential_loader.py` (9 tests) : mock `psycopg2.connect`, chiffrement/déchiffrement Fernet, fallback sans clé, erreur DB gracieuse, extra_config JSON string
- `tests/test_validators.py` (15 tests) : MetaCampaign/Adset/Ad/Insight — statuts invalides, budgets négatifs, clicks > impressions, CTR > 100
- `tests/test_error_handler.py` (17 tests) : retry (exponential/linear backoff, 3 tentatives), non-retriable (ValueError/KeyError/TypeError), succès après N failures, `log_errors`, `safe_call`, `log_and_raise`

### Résultat
**79/79 tests passent en 0.85s** — `python3 -m pytest tests/ -v`

### Choix techniques
- `psycopg2` étant importé *à l'intérieur* des fonctions de `credential_loader.py`, le patch cible `psycopg2.connect` (global) et non `src.utils.credential_loader.psycopg2`
- `time.sleep` mocké dans les tests retry pour éviter les délais réels (tests rapides)
- Pas de vraie DB en test : tout mocké ou basé sur des fichiers temporaires `tmp_path`

### Statut : ✅ Prochaine étape : Brick 11 (Monitoring + Alerting)

---

## 2026-03-11 — Brick 9 : Gestion d'erreurs + Retry ✅

### Ce qui a été fait
- **`src/utils/retry.py`** — nouveau décorateur `@retry(max_attempts, backoff)` avec backoff exponentiel. Distingue exceptions retriables (réseau/DB) des non retriables (données).
- **`src/database/postgres_handler.py`** — méthode `_ensure_connection()` ajoutée ; appelée automatiquement avant toute requête pour reconnecter si la connexion PostgreSQL est perdue.
- **`src/utils/error_handler.py`** — réécrit entièrement : `@log_errors()` décorateur fonctionnel, `log_and_raise()`, `safe_call()` pour les blocs non-critiques.
- **Collectors API** — `@retry(3, exponential)` appliqué sur les méthodes fetch de Spotify, YouTube (5 méthodes), SoundCloud, Instagram.

### Choix techniques
- Import `requests` optionnel dans `retry.py` (pas disponible dans tous les contextes).
- Exceptions non retriables : `ValueError`, `KeyError`, `TypeError`, `AttributeError` — pour éviter de retry des bugs de données.
- Les CSV watchers (S4A, Apple Music, Meta) ne sont pas décorés — pas d'appel HTTP, pas de retry nécessaire.

### Statut : ✅
### Prochaine étape : Brick 10 — Tests unitaires (pytest) ou Brick 11 — Monitoring

---

## 2026-03-11 — Brick 8 : Home KPI + Fraîcheur + ROI Breakheaven ✅

### Ce qui a été fait
- **`src/dashboard/utils/kpi_helpers.py`** — NOUVEAU module utilitaire partagé
  - `SOURCES_CONFIG` : 7 sources (S4A, YouTube, SoundCloud, Instagram, Apple, Meta, iMusician) avec table/col/artist_col
  - `get_source_freshness()` + `freshness_status()` → badges colorés vert/orange/rouge
  - `get_total_streams_*()` — 4 fonctions streams (artist_id aware, admin = None)
  - `get_spotify_popularity()`, `get_instagram_followers()`, `get_soundcloud_likes()`
  - `get_roi_data()` + `get_monthly_roi_series()` — revenus iMusician vs spend Meta
- **`src/dashboard/views/home.py`** — RÉÉCRIT (remplace l'ancien stub + le bloc inline app.py)
  - 5 sections : fraîcheur → streams totaux → KPI ML → ROI → graphique cumulé Spotify
  - Fraîcheur : badges colorés, gestion DATE vs TIMESTAMP normalisée
  - ROI : sélecteur période (3/6/12 mois / année en cours), graphique grouped bar revenue vs spend
  - Adapté pour admin (artist_id=None) et artiste
- **`app.py`** — nettoyé : bloc home (~60 lignes) → 1 ligne ; `get_db()` + `get_spotify_chart_data()` supprimés ; imports pandas/plotly/datetime/PostgresHandler retirés

### Choix techniques
- `freshness_status()` normalise `DATE` → `datetime` (soundcloud/instagram ont `collected_at DATE`)
- `ARTIST_NAME_FILTER` défini dans `kpi_helpers.py` (source de vérité unique, plus dans app.py)
- `get_roi_data()` utilise `make_date(year, month, 1)` pour comparer les périodes iMusician
- `python-dateutil.relativedelta` pour le sélecteur de période (transitif de pandas, pas d'ajout requirements)

### Statut
✅ Brick 8 complète — 3 fichiers, syntaxe OK
⏭️ Bricks P1 terminées. Prochaine : Brick 9 (Retry/erreurs) ou test du dashboard complet

---

## 2026-03-11 — Brick 7 : iMusician — Revenus mensuels ✅

### Ce qui a été fait
- **`src/database/imusician_schema.py`** — NOUVEAU : table `imusician_monthly_revenue`
  - Colonnes : artist_id (FK saas_artists), year, month (CHECK 1-12), revenue_eur (NUMERIC 10,2), notes, created_at, updated_at
  - UNIQUE(artist_id, year, month) — upsert idempotent
- **`init_db.sql`** — section 8 ajoutée avec CREATE TABLE + 2 index (artist_id, year/month DESC)
- **`src/dashboard/views/imusician.py`** — NOUVEAU : vue complète
  - Tab 1 Saisie : year/month selectors, revenue input, notes, upsert DB — admin choisit l'artiste
  - Tab 2 Données : KPIs (total, moyenne, nb mois), bar chart Plotly mensuel, tableau détail, expander suppression
- **`app.py`** — "💰 iMusician" ajouté à la navigation (visible tous rôles) + routing

### Choix techniques
- Schema simplifié vs la checklist initiale : une seule table `imusician_monthly_revenue` (pas de ISRC/DSP/territoire — pas utile pour le ROI Breakheaven)
- Granularité mensuelle (year + month entiers) : plus simple que period_start/period_end pour la saisie manuelle
- Notes optionnel : permet de documenter les reversals, corrections, promos release

### Statut
✅ Brick 7 complète — 3 fichiers, syntaxe OK
⏭️ Prochaine brick : Brick 8 — Home KPI + Dates MAJ + ROI Breakheaven

---

## 2026-03-10 — Roadmap Bricks 7-15 : planification complète ✅

### Ce qui a été fait
- **`checklist.md`** — Bricks 7 à 15 ajoutées avec détail d'implémentation
- **`CLAUDE.md`** — section "Roadmap & Checklist" ajoutée avec tableau d'état et instruction de reprise post-`/clear`

### Ordre de priorité retenu
- **P1** (données + valeur) : iMusician (Brick 7) → Home KPI + ROI (Brick 8)
- **P2** (fiabilité SaaS) : Retry/erreurs (Brick 9) → Tests (Brick 10) → Monitoring (Brick 11)
- **P3** (différenciateurs) : PDF (Brick 12) → CSV export (Brick 13)
- **P4** (déploiement) : FastAPI (Brick 14) → Railway CI/CD (Brick 15)

### Justification
iMusician avant le reste car c'est le seul flux de revenus manquant — sans lui, le ROI Breakheaven est impossible. Brick 9 (retry) avant les tests car les retry changent les interfaces à tester.

---

## 2026-03-10 — Brick 5 + 6 : CSV Upload (Streamlit) + DAGs paramétrés ✅

### Ce qui a été fait

**Brick 5 — Upload CSV via Streamlit**
- **`src/dashboard/views/upload_csv.py`** — NOUVEAU
  - Accessible à tous les rôles (artiste → son propre artist_id, admin → sélection)
  - Plateformes supportées : S4A timeline + Apple Music performance
  - Flux deux étapes : parse → preview 10 lignes → bouton "Confirmer" → upsert DB
  - Parsing délégué aux transformers existants (`S4ACSVParser`, `AppleMusicCSVParser`)
- **`app.py`** — "📂 Import CSV" ajouté à la navigation (visible par tous les rôles)

**Brick 6 — DAGs paramétrés**
- **`src/utils/credential_loader.py`** — NOUVEAU utilitaire partagé
  - `load_platform_credentials(artist_id, platform)` : requête DB + déchiffrement Fernet → dict
  - `get_active_artists(include_artist_id=None)` : liste artists actifs (filtre optionnel par ID)
  - Connexion DB via env vars (fonctionne dans Docker Airflow et en local)
  - Fallback silencieux : retourne `{}` si DB inaccessible ou `FERNET_KEY` absent
- **`airflow/dags/soundcloud_daily.py`** — reécrit avec pattern Brick 6
  - Lit `conf.artist_id` depuis `dag_run.conf`
  - Charge credentials depuis DB → override `SOUNDCLOUD_CLIENT_ID` si trouvé
  - Boucle sur `get_active_artists()` (prêt pour multi-artiste)
- **`airflow/dags/youtube_daily.py`** — mis à jour
  - Lit `conf.artist_id` (défaut 1)
  - Priorité : creds DB → env vars (rétrocompatible)

### Choix techniques
- **Preview avant insert** (Brick 5) : parse à chaque rerun Streamlit (fichier en mémoire), confirmation explicite via bouton séparé — pas de session_state nécessaire
- **credential_loader fallback** (Brick 6) : DB optionnelle — les DAGs continuent de fonctionner avec env vars si aucun credential en DB (compatibilité avec les déploiements existants)
- **os.environ override** pour SoundCloud : le collector lit les env vars dans `__init__`, l'override avant instanciation est le moyen le moins invasif sans modifier le collector

### Statut
- ✅ 5 fichiers, syntaxe OK (py_compile)
- 🚧 **Action requise** : ajouter `FERNET_KEY=<valeur du config.yaml>` dans `.env` pour Docker
- 🚧 Appliquer pattern Brick 6 aux autres DAGs (spotify_api_daily, instagram_daily, meta_*)

### Prochaine étape
- Toutes les Bricks 1-6 sont codées ✅
- Déploiement : `docker-compose up -d` → test dashboard complet

---

## 2026-03-10 — Brick 4 : Credential Form ✅

### Ce qui a été fait
- **`src/dashboard/views/credentials.py`** — NOUVEAU (325 lignes)
  - 4 onglets : Spotify, YouTube, SoundCloud, Meta/Instagram
  - Champs secrets → `token_encrypted` (JSON chiffré Fernet), config pub → `extra_config` (JSONB)
  - Formulaire avec masquage des valeurs existantes (6 premiers chars + `…***`)
  - Champ secret vide = conserver l'ancienne valeur (pas d'écrasement involontaire)
  - Test de connexion live par plateforme (appel API réel : Spotify token, YouTube refresh, SoundCloud tracks, Meta Graph)
  - Admin : sélection de l'artiste cible via selectbox
  - Fallback : si `fernet_key` absent → warning + bouton Enregistrer désactivé
- **`requirements.txt`** — `cryptography>=42.0.0` ajouté
- **`config/config.example.yaml`** — section `fernet_key` avec commande de génération
- **`app.py`** — "🔑 Credentials API" ajouté à la nav (visible par tous les rôles) + routing

### Pourquoi
Brick 4 permet à chaque artiste de gérer ses propres clés API dans le dashboard, sans jamais les stocker en clair. Les credentials sont ensuite disponibles pour Brick 6 (DAGs paramétrés qui lisent les creds depuis la DB au runtime).

### Choix techniques
- **Fernet** : symétrique, simple, standard (`cryptography` lib). La clé est dans config.yaml (jamais en DB).
- **token_encrypted = JSON chiffré** : un seul champ contient TOUS les secrets (client_secret + refresh_token), pas besoin de colonnes multiples. Extensible sans migration.
- **extra_config = plain JSONB** : client_id, redirect_uri, account_id — pas sensibles, directement lisibles pour debug.

### Statut
- ✅ Code complet, syntaxe OK
- 🚧 **Action requise** : `pip install cryptography --break-system-packages`
- 🚧 **Action requise** : générer `fernet_key` et l'ajouter dans `config/config.yaml`
- 🚧 Tester dans le browser

### Prochaine étape
- Brick 5 : CSV Upload via Streamlit (déjà partiellement dans admin.py — à exposer aux artistes)
- Brick 6 : DAGs paramétrés (lire credentials depuis `artist_credentials` au runtime)

---

## 2026-03-10 — SaaS DB Migration — Audit + Corrections + meta_insights schema ✅

### Ce qui a été fait (continuation de session)
- **`/review-db-schema`** — audit complet : 3 erreurs critiques trouvées (conflits upsert) + 5 warnings pre-existants + 3 infos
- **`src/collectors/s4a_csv_watcher.py`** — ON CONFLICT corrigé : `(song, date)` → `(artist_id, song, date)`, INSERT inclut maintenant `artist_id = 1`
- **`src/dashboard/views/hypeddit.py`** — les 2 `upsert_many` corrigés : `conflict_columns` étendu à `['artist_id', 'campaign_name']` et `['artist_id', 'campaign_name', 'date']`, `artist_id=1` ajouté aux dicts de données
- **`src/database/meta_insight_schema.py`** — NOUVEAU : 10 tables Meta Ads Insights enfin définies (5 performance + 5 engagement, toutes avec `artist_id`). Ces tables existaient dans le watcher mais n'avaient jamais de schema Python.
- **`src/collectors/meta_insight_watcher.py`** — 10 méthodes upsert corrigées : `artist_id = 1` ajouté à chaque INSERT, `date_start` ajouté aux INSERTs globaux (bug pre-existant), tous les ON CONFLICT mis à jour

### Pourquoi
L'audit a révélé que les contraintes UNIQUE modifiées par la migration SaaS cassaient silencieusement les upserts existants. La création de `meta_insight_schema.py` clôt un écart de schema pre-existant : les tables étaient utilisées par le watcher mais jamais créées formellement, ce qui faisait crasher les DAGs Meta sur un nouveau volume Docker.

### Statut
- ✅ Tout le code corrigé et documenté
- ✅ Migration script exécuté avec succès sur la DB live — 26 tables OK, 7 MISSING (normales, pas encore alimentées par collecteurs)
- Correction en cours : `fk_hypeddit_campaign` dropée en CASCADE + recrée en composite `(artist_id, campaign_name)` ; step 6b ajouté pour les 10 tables `meta_insights_*` pre-existantes

### Prochaine étape
1. Activer WSL Integration dans Docker Desktop
2. `docker-compose up -d` puis `python scripts/migrate_saas_artist_id.py`
3. Tester le dashboard : `cd src/dashboard && streamlit run app.py`
4. `/clear` → Brick 2 (Auth — streamlit-authenticator)

---

## 2026-03-10 — SaaS DB Migration Brick 1 ✅

### Ce qui a été fait
- **`src/database/saas_schema.py`** — nouveau fichier : tables `saas_artists` + `artist_credentials`
- **`init_db.sql`** — réécrit : `saas_artists` en premier (table parente), ajout des tables SoundCloud/Instagram (qui n'avaient pas de fichier schema dédié), graine `artist_id=1`, reset de séquence
- **`scripts/migrate_saas_artist_id.py`** — script de migration idempotent en 9 étapes : crée `saas_artists`, graine l'artiste par défaut, ajoute `artist_id` sur 21 tables existantes, remplace les contraintes UNIQUE, ajoute les FK, affiche un résumé
- **5 fichiers schema Python mis à jour** — `s4a_schema.py`, `apple_music_csv_schema.py`, `youtube_schema.py`, `meta_ads_schema.py`, `hypeddit_schema.py` : `artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id)` ajouté à chaque CREATE TABLE, UNIQUE enrichis avec `artist_id`
- **`hypeddit_schema.py`** — suppression des `DROP TABLE IF EXISTS CASCADE` dangereux, passage à `CREATE TABLE IF NOT EXISTS`
- **Bugs de conflit upsert corrigés** (découverts par `/review-db-schema`) :
  - `src/collectors/s4a_csv_watcher.py` — ON CONFLICT (song, date) → (artist_id, song, date)
  - `src/dashboard/views/hypeddit.py` — conflict_columns corrigés sur les 2 upserts, `artist_id=1` ajouté aux dicts de données

### Pourquoi
Brick 1 du passage SaaS multi-tenant : rendre toutes les tables conscientes de l'artiste propriétaire via `artist_id`, sans casser les données existantes (DEFAULT 1 = artiste unique actuel).

### Choix techniques notables
- **Shared schema** avec FK `artist_id` (pas de schema-per-tenant) : plus simple, performant pour le nombre d'artistes attendu
- `saas_artists` ≠ `artists` : `artists` = métadonnées Spotify (VARCHAR PK), `saas_artists` = tenants SaaS (SERIAL PK)
- Migration idempotente : chaque ALTER TABLE est protégé par une vérification `column_exists` / `constraint_exists` — safe à re-exécuter
- SoundCloud et Instagram n'avaient pas de fichier schema Python — tables créées directement dans `init_db.sql` et dans le migration script

### Statut
- ✅ Tous les fichiers code modifiés/créés
- 🚧 **Migration script non exécuté** — Docker inaccessible depuis WSL2 (WSL Integration désactivée dans Docker Desktop)
- **Action requise** : lancer depuis Windows `python scripts/migrate_saas_artist_id.py` après `docker-compose up -d`

### Prochaine étape
**Brick 2 — Auth** : `streamlit-authenticator`, login admin/artist, session state injecte `artist_id`, remplacement de `ARTIST_NAME_FILTER`.
Commencer par `/clear` puis lire `.claude/dev-docs/saas-db-migration/context.md`.

---

## 2026-03-08 — Setup Claude Code workflow

### Ce qui a été fait
- **CLAUDE.md** créé à la racine — architecture, commandes, conventions clés (PostgresHandler autocommit, ARTIST_NAME_FILTER, ajout d'une vue/DAG).
- **DEVLOG.md** mis en place (ce fichier) pour garder la trace structurée des sessions.
- **Hook `PostToolUse`** configuré dans `.claude/settings.json` : vérifie automatiquement la syntaxe de chaque fichier `.py` modifié via `py_compile` (stdlib, zéro dépendance). Si une erreur est détectée, Claude en est notifié immédiatement et peut se corriger avant que tu ne voies le code.
- **Discussion REX** sur les bonnes pratiques Claude Code : DEVLOG, CLAUDE.md léger, hooks, mode Plan, /clear, sous-agents, PM2.

### Pourquoi
Réduire le "context drift" entre sessions (Claude qui perd le fil) et permettre l'auto-correction syntaxique immédiate sans intervention manuelle.

### Choix techniques notables
- Hook `py_compile` plutôt que `ruff`/`flake8` : zéro installation, toujours disponible. Upgrade vers `ruff` possible quand il sera installé dans le venv.
- Hook au niveau projet (`.claude/settings.json`) et non global (`~/.claude/settings.json`) : comportement spécifique à ce repo.
- Succès silencieux du hook (pas de bruit dans la sortie si tout va bien).

### État
✅ Terminé

### Prochaines pistes
- ~~Envisager un hook `UserPromptSubmit`~~ → fait session suivante.
- ~~Installer `ruff` et upgrader le hook~~ → fait session suivante.
- Documenter les MCP disponibles si des serveurs sont ajoutés.

---

## 2026-03-08 — Hooks avancés + Sous-agents spécialisés

### Ce qui a été fait
- **`ruff` installé** (v0.15.5) via `pip install --break-system-packages ruff` sur WSL2 (le venv est Windows/.exe, non activable depuis WSL).
- **Hook `PostToolUse` upgradé** (`.claude/hooks/check_python_syntax.py`) :
  - Utilise `ruff` si disponible (fallback `py_compile` sinon).
  - Règles sélectionnées : `E9` (syntaxe) + `F401/F811/F821/F841` (pyflakes : imports inutilisés, noms indéfinis, etc.).
  - **E9** → exit 2 (bloquant, Claude corrige avant de continuer).
  - **F** → exit 0 + message affiché (informatif, non bloquant).
  - Succès toujours silencieux.
- **Hook `UserPromptSubmit`** créé (`.claude/hooks/inject_context.py`) :
  - Analyse le prompt entrant et détecte le domaine : `dashboard`, `dag`, `schema`, `collector`.
  - Injecte le bloc de contexte correspondant (patterns à suivre, conventions, pièges) avant que Claude lise le message.
  - Détection multi-domaine (un prompt peut toucher DAG + schema simultanément).
- **Slash commands** créées dans `.claude/commands/` :
  - `/review-db-schema` — audit de cohérence des schémas PostgreSQL (contraintes UNIQUE, upsert_many, filtre ARTIST_NAME_FILTER, écarts avec init_db.sql).
  - `/review-dag` — audit de conformité des DAGs Airflow (sys.path, default_args, imports dans les tâches, debug_dag manquant, cohérence avec airflow_trigger.py et app.py).
- **`CLAUDE.md`** mis à jour avec la section "Workflow & Session Hygiene".

### Pourquoi
- Le hook `UserPromptSubmit` évite que Claude ne "réinvente" les patterns à chaque session — il reçoit le rappel pertinent automatiquement sans consommer de tokens inutiles.
- Les slash commands permettent de lancer un audit ciblé d'un domaine sans avoir à re-expliquer le contexte à chaque fois.
- Ruff détecte les imports inutilisés et noms indéfinis que py_compile rate (erreurs silencieuses à l'exécution).

### Choix techniques notables
- **Ruff installé au niveau système WSL** (pas dans le venv Windows) car le venv utilise des `.exe` non exécutables sous WSL2. Le hook `shutil.which("ruff")` gère le fallback proprement.
- **Injection `UserPromptSubmit` non bloquante** (toujours exit 0) — le hook enrichit, ne contrôle pas.
- **Slash commands en markdown** plutôt qu'en scripts : Claude les lit comme des instructions structurées, plus maintenable et lisible.
- Séparation des niveaux de sévérité ruff : E9 bloquant vs F informatif — évite la fatigue d'alerte sur les warnings de style.

### État
✅ Terminé

### Prochaines pistes
- ~~Documenter les MCP~~ → section CLAUDE.md ajoutée (template + candidats).
- ~~Hook `Stop`~~ → fait session suivante.
- ~~Affiner les keywords `inject_context.py`~~ → fait session suivante.

---

## 2026-03-08 — Stop hook + affinement inject_context + MCP template

### Ce qui a été fait
- **Hook `Stop`** créé (`.claude/hooks/session_summary.py`) :
  - S'exécute après chaque réponse de Claude.
  - Affiche un récapitulatif groupé (✏️ modifiés / ➕ nouveaux / 🗑️ supprimés / 📦 stagés) uniquement si des fichiers ont changé — silencieux sinon.
  - Max 15 fichiers affichés pour ne pas noyer la sortie.
  - Rappel automatique : `"Append today's session summary to DEVLOG.md"` avant `/clear`.
- **`inject_context.py` affiné** — suppression des faux positifs majeurs :
  - Retiré `"show"`, `"client"`, `"fetch"`, `"api"`, `"request"` (trop génériques).
  - Retiré `"database"` seul du domaine schema (ambiguïté).
  - Ajoutés : `"kpi"`, `"onglet"`, `"filtre"`, `"render"` (dashboard) ; `"schedule"`, `"catchup"`, `"backfill"`, `"retry"` (dag) ; `"postgresql"`, `"alter table"`, `"postgres_handler"`, `"insert_many"` (schema) ; `"oauth"`, `"rate limit"`, `"endpoint"`, `"s4a"`, `"hypeddit"` (collector).
  - Commentaires inline dans DOMAINS pour tracer les choix d'inclusion/exclusion.
- **Section MCP** ajoutée dans `CLAUDE.md` : template JSON prêt à l'emploi + candidats (PostgreSQL MCP, Docker MCP).

### Pourquoi
- Le Stop hook ferme la boucle du workflow : modifier → auto-lint → récapitulatif → DEVLOG → /clear.
- L'affinement des keywords réduit les injections de contexte non pertinentes (moins de tokens gaspillés, moins de bruit pour Claude).
- La section MCP évite de devoir re-documenter le format à chaque fois qu'un serveur est ajouté.

### Choix techniques notables
- **Stop hook silencieux par défaut** : n'affiche rien si git status est vide — zéro bruit en fin de session si rien n'a changé.
- **git status --short** plutôt que de parser le transcript : plus fiable, instantané, et reflète la vraie vérité du repo.
- **Groupement par statut** (M/A/D) dans le résumé plutôt qu'une liste brute : lisibilité améliorée d'un coup d'œil.
- Keywords affinés avec commentaires catégorisés dans le code : facilite la maintenance future au fil des faux positifs observés.

### État
✅ Terminé

### Prochaines pistes
- ~~Tester `UserPromptSubmit` et ajuster les keywords~~ → fait session suivante.
- ~~MCP PostgreSQL~~ → configuré session suivante.
- ~~Évaluer MCP Docker~~ → évalué, bloqué sur prérequis WSL.

---

## 2026-03-08 — Tests inject_context + MCP PostgreSQL + évaluation Docker MCP

### Ce qui a été fait
- **Tests du hook `UserPromptSubmit`** avec 8 prompts représentatifs. Bugs identifiés et corrigés :
  - `"tab"` dans les keywords dashboard matchait `"table"` → false positive sur toutes les questions DB. Retiré.
  - `"collect"` dans les keywords dag matchait `"collector"` → faux contexte DAG sur les questions collector. Retiré.
  - Résultats après correction : 6/6 tests corrects (dashboard, dag, schema, collector, multi-domaine, aucun).
- **MCP PostgreSQL configuré** (`~/.claude/settings.json`) :
  - Package choisi : `mcp-postgres` v1.1.2 (maintenu) plutôt que `@modelcontextprotocol/server-postgres` (déprécié).
  - Configuration via variables d'env `DB_HOST/PORT/USER/PASSWORD/DB_NAME` (format découvert en lisant la source du package — le CLI arg était ignoré).
  - Nom MCP : `spotify-postgres`, pointe sur `spotify_etl` port 5433.
  - **Prérequis runtime** : containers Docker doivent être lancés (`docker-compose up -d`).
- **MCP Docker évalué** : non configuré car `docker` n'est pas dans le PATH WSL2 (WSL integration désactivée dans Docker Desktop). Documenté dans CLAUDE.md avec les étapes d'activation et le package recommandé (`docker/docker-mcp-toolkit`).

### Pourquoi
- Les deux bugs `"tab"`/`"collect"` déclenchaient du contexte non pertinent sur les questions DB les plus courantes — impact direct sur la qualité des injections.
- Le MCP PostgreSQL permet à Claude d'interroger la DB directement (lister les tables, compter les lignes, vérifier une requête) sans que tu aies à copier-coller les résultats.
- Le Docker MCP est moins critique : les containers sont gérés via `docker-compose` et les logs via `docker-compose logs`, ce qui est suffisant pour l'instant.

### Choix techniques notables
- **`mcp-postgres` via `npx`** (pas d'installation globale) : le package est téléchargé à la demande par npx et mis en cache. Transparent à maintenir.
- **Credentials en env vars dans settings.json** plutôt qu'en connection string URL : découvert en lisant la source du package, plus fiable et plus lisible.
- **Substring matching volontairement gardé** pour la majorité des keywords (pas de regex word-boundary) : suffisamment précis après nettoyage, et plus simple à maintenir.

### État
✅ Terminé

### Prochaines pistes
- Valider le MCP `spotify-postgres` en conditions réelles (lancer `docker-compose up -d` et vérifier que Claude voit les tables).
- Activer le MCP Docker si besoin (activer WSL integration dans Docker Desktop d'abord).
- ~~Stop hook Docker health check~~ → fait session suivante.
- ~~/logs-airflow, /dev-docs~~ → fait session suivante.

---

## 2026-03-08 — Stop hook complet + /logs-airflow + /dev-docs + CLAUDE.md finalisé

### Ce qui a été fait
- **Stop hook upgradé** (`.claude/hooks/session_summary.py`) — trois sections, toutes conditionnelles (silence si rien à signaler) :
  1. **Git diff** — groupé par statut (modifié/nouveau/supprimé/stagé), tronqué à 15 fichiers.
  2. **Docker health** — détecte `docker.exe` via PATH ou chemin Windows fixe, vérifie les 3 containers Airflow attendus, affiche la commande de fix.
  3. **Session longueur** — lit le transcript JSONL fourni par Claude Code, alerte si > 20 tours assistant avec rappel `/cost`.
- **`/logs-airflow`** — slash command qui demande à Claude de lire directement `docker.exe logs` des containers Airflow et d'analyser les erreurs. Résout le friction point copier-coller des logs (équivalent PM2 pour ce stack).
- **`/dev-docs <nom>`** — slash command qui génère le trio plan/context/checklist dans `.claude/dev-docs/<nom>/`. Résout la perte de cohérence sur les grandes features quand la conversation est compactée.
- **CLAUDE.md finalisé** — sections ajoutées :
  - `.env.local` vs `.env` : comportement exact de l'app (chargement prioritaire `.env.local`).
  - Worktrees git : utiliser `isolation: "worktree"` dans les agents pour les expériences risquées.
  - `/cost` : rappel explicite pour surveiller la consommation.
  - Tableau récapitulatif des slash commands.

### Pourquoi
- Le Stop hook unifié remplace 3 vérifications manuelles en un seul récapitulatif automatique de fin de tour.
- `/logs-airflow` : la friction "copier-coller les logs" est le principal obstacle au débogage autonome de Claude sur ce projet — résolu directement par lecture Bash.
- `/dev-docs` : les grandes features (nouvelle intégration API, refonte d'une vue) perdent leur fil après compaction — le trio de fichiers persiste au-delà du contexte.

### Choix techniques notables
- **Transcript JSONL** pour compter les tours : plus fiable que compter les appels d'outils car reflète vraiment la longueur de la conversation côté Claude.
- **`_find_docker()`** avec fallback sur le chemin Windows fixe : robuste si Docker Desktop configure le PATH différemment selon les mises à jour.
- **`/dev-docs` avec `$ARGUMENTS`** : le nom de la feature passé directement dans la commande évite une étape de dialogue intermédiaire.
- **`/logs-airflow` via Bash tool** (pas un script shell) : Claude peut analyser et raisonner sur les logs dans le même tour, pas seulement les afficher.

### Sur /usage dans le prompt
Pas possible d'appeler `/cost` programmatiquement depuis un hook (c'est une commande interne Claude Code, pas un binaire shell). La solution choisie : le Stop hook compte les tours depuis le transcript et alerte à > 20 tours avec le rappel `/cost`. C'est le meilleur proxy disponible sans accès à l'API de métriques.

### État
✅ Terminé

### Prochaines pistes
- Valider le MCP `spotify-postgres` quand Docker sera up (`docker-compose up -d` puis ouvrir une session Claude).
- Activer WSL integration Docker Desktop pour débloquer le Docker MCP et `/logs-airflow` sans `docker.exe`.
- Utiliser `/dev-docs` sur la prochaine feature ML pour valider le workflow trio en conditions réelles.

---

## 2026-03-08 — Bilan sub-agents + Guide généraliste Claude Code

### Ce qui a été fait
- **Évaluation sub-agents pour ce projet** : usage occasionnel recommandé (pas core). Les slash commands `/review-*` existants couvrent déjà le besoin "reviewer spécialisé" dans le même contexte. Sub-agents pertinents pour : exploration large codebase (`Explore`), design pre-implémentation (`Plan`), expériences ML avec `isolation: "worktree"`.
- **Guide généraliste créé** (`~/.claude/CLAUDE_CODE_GUIDE.md`) — applicable à tout projet, 8 sections :
  1. Structure de fichiers recommandée
  2. CLAUDE.md : quoi mettre / ne pas mettre
  3. Hooks : format complet, exit codes, input JSON par type, recettes copier-coller
  4. Slash commands : patterns auditeur, lecteur de logs, dev-docs
  5. MCP servers : format + tableau par stack (PostgreSQL, Docker, GitHub…)
  6. Sub-agents : matrice de décision, types, worktrees, anti-patterns
  7. Workflow par type de tâche (courante / grande feature / expérience risquée / debug)
  8. Checklist de mise en place sur un nouveau projet

### Pourquoi
Le guide centralise plusieurs sessions d'itérations en un référentiel réutilisable — bootstrap d'un nouveau projet en 30 min au lieu de réinventer la configuration.

### État
✅ Terminé — workflow Claude Code de ce projet complet et documenté

### Prochaines pistes (fonctionnelles)
- Valider MCP PostgreSQL quand Docker sera up.
- Utiliser `/dev-docs` + sub-agent `Plan` sur la prochaine feature ML.
- Activer WSL integration Docker Desktop.

---

---

## 2026-03-10 — Brick 2 : Auth (streamlit-authenticator) ✅

### Ce qui a été fait
- **`requirements.txt`** — ajout `streamlit-authenticator==0.3.3`
- **`src/dashboard/auth.py`** — NOUVEAU : module auth complet
  - `require_login()` : affiche formulaire login, stocke session state (authenticated, artist_id, role, name)
  - Mode bypass si pas de section `auth` dans config.yaml (dev mode)
  - `show_user_sidebar()` : affiche role/nom + bouton logout
  - `artist_id_sql_filter()` : helper → `("AND artist_id = %s", (1,))` ou `("", ())` pour admin
  - `get_artist_id()`, `is_admin()` : accesseurs session
- **`app.py`** — login gate : `require_login()` + `st.stop()` si non connecté
  - Navigation filtrée : artistes ne voient pas "Monitoring ETL" (admin only)
  - `show_user_sidebar()` dans la sidebar (rôle + logout)
  - Queries S4A home page + chart → utilisent `artist_id_sql_filter()`
- **`config/config.yaml`** — section `auth` ajoutée :
  - user `admin` : role=admin, artist_id=null (voit tout)
  - user `artist1` : role=artist, artist_id=1
  - Mot de passe commun : `Wowow1357911!` (bcrypt hashé)
- **`config/config.example.yaml`** — section `auth` documentée avec instructions génération hash

### Pourquoi
Brick 2 de la migration SaaS : isoler les données par artiste et sécuriser le dashboard avec un login. L'approche cookie-based de streamlit-authenticator permet un "remember me" natif. Le mode bypass dev évite de casser le workflow sans config auth.

### Choix techniques
- `streamlit-authenticator==0.3.3` (API stable, compatible streamlit 1.29.0)
- `artist_id` stocké directement dans les credentials YAML (custom field)
- `artist_id=None` pour admin → pas de filtre SQL → voit toutes les données
- `ARTIST_NAME_FILTER` conservé (filtre ligne "Total" des CSV S4A — indépendant du multi-tenant)

### Statut
✅ Auth module créé et branché dans app.py
🚧 À faire : `pip install streamlit-authenticator==0.3.3` + test login
🚧 Brick 2.5 : mettre à jour les views (12 fichiers) pour utiliser `artist_id_sql_filter()`

---

## 2026-03-10 — Brick 2.5 : Views artist_id filter — COMPLETE ✅

### Ce qui a été fait
- **8 views** mises à jour pour filtrer par `artist_id` depuis la session :
  - `spotify_s4a_combined.py` — 5 queries avec `artist_id_sql_filter()` (pattern fragment SQL)
  - `soundcloud.py` — suppression de `view_soundcloud_latest` (inexistante), remplacée par `DISTINCT ON (track_id)` sur `soundcloud_tracks_daily WHERE artist_id = %s`
  - `instagram.py` — suppression de `view_instagram_latest`, remplacée par `DISTINCT ON (ig_user_id)` sur `instagram_daily_stats WHERE artist_id = %s`
  - `youtube.py` — `youtube_channel_history` + `youtube_videos/stats` filtrés par artist_id
  - `apple_music.py` — `apple_songs_performance` filtrée par artist_id
  - `meta_ads_overview.py` — WHERE clause dynamique étendue avec `artist_id = %s` (WHERE p.artist_id pour le JOIN aussi)
  - `meta_x_spotify.py` — `meta_insights_performance_day`, `hypeddit_daily_stats`, `s4a_song_timeline` filtrés
  - `hypeddit.py` — `artist_id = get_artist_id() or 1` partout (plus hardcodé à 1)
- **Hashes bcrypt** régénérés et vérifiés (les premiers ne matchaient pas)
- **14/14 fichiers** dashboard passent `python3 -m py_compile`

### Corrections de bugs pre-existants
- `view_soundcloud_latest` et `view_instagram_latest` n'existaient PAS en DB — causait crash silencieux dans les views (géré par try/except). Remplacées par requêtes directes avec DISTINCT ON.

### Statut
✅ Auth complet (Brick 2) + Views filtrées (Brick 2.5)
🚧 Test manuel dans browser (nécessite Docker running + `streamlit run app.py`)
⏭️ Prochain : Brick 3 (Admin Interface — CRUD artistes)

---

## 2026-03-10 — Fix streamlit-authenticator API 0.4.x ✅

### Ce qui a été fait
- **`src/dashboard/auth.py`** — compatibilité 0.3.x / 0.4.x :
  - `login()` : passage de `login('titre', 'main')` → `login(location='main')`, retour via `st.session_state` au lieu d'un tuple
  - `logout()` : passage de `logout('label', 'sidebar')` → `logout(button_name=..., location=...)` avec try/except pour fallback 0.3.x
- **`app.py`** — `sys.path.append` → `sys.path.insert(0, resolve())` pour garantir chemin absolu sur Windows

### Pourquoi
Le venv Windows avait installé streamlit-authenticator 0.4.x (malgré le pin 0.3.3) dont l'API `login()` a changé : le premier arg positionnel est maintenant `location` et non le titre. Dashboard désormais fonctionnel ✅

---

## 2026-03-10 — Brick 3 : Interface Admin ✅

### Ce qui a été fait
- **`src/dashboard/views/admin.py`** — NOUVEAU : vue admin complète
  - Tab 1 **Artistes** : liste tous les `saas_artists`, formulaire création (nom, slug, tier), formulaire modification (nom, tier, activer/désactiver)
  - Tab 2 **Upload CSV** : sélection artiste actif + plateforme (S4A / Apple Music) + `st.file_uploader` → parse via transformers existants + `upsert_many` avec `artist_id` cible
  - Protection `_guard()` → `st.stop()` si rôle ≠ admin
- **`app.py`** — page "⚙️ Admin" ajoutée à `pages_all`, cachée pour rôle 'artist' via `_admin_only = {'airflow_kpi', 'admin'}`, routing `elif page == "admin"`

### Pourquoi
Brick 3 de la roadmap SaaS : permettre à l'admin de gérer les artistes en DB et d'importer des CSV sans passer par le filesystem local. L'upload CSV utilise les parsers existants, garantissant la cohérence du format.

### Choix techniques
- Protection double : navigation filtrée par rôle (app.py) + guard interne (admin.py `_guard()`)
- CSV upload : S4A + Apple Music (Meta CSV plus complexe, prévu Brick 5)
- `autocommit=True` → pas de `.commit()` sur les upserts

### Statut
✅ Brick 3 complet
⏭️ Prochain : Brick 4 (Credential Form — stockage Fernet des tokens par artiste)

---
## 2026-03-23 — Configuration restructuring: modular .claude/ setup

**Why**: CLAUDE.md was 204 lines, mixed English and French, contained coding standards alongside project-specific info. The goal was progressive disclosure via modular skills/agents, and a clean separation of concerns.

**What changed**:
- `CLAUDE.md` — rewritten to 174 lines, English only, references skills/agents for detail
- `.claude/hooks/session_summary.py` — added Step 4 (pytest runner with 60s timeout, signals ≥5 failures)
- `.claude/skills/dashboard-view.md` — Streamlit view patterns (show(), db, artist filter, S4A filter)
- `.claude/skills/airflow-dag.md` — DAG patterns (sys.path, default_args, in-task imports, debug_dag)
- `.claude/skills/db-schema.md` — schema patterns (PostgresHandler, upsert_many, UNIQUE constraints)
- `.claude/skills/response-protocol.md` — 3 cross-cutting rules (language, neutrality, classification)
- `.claude/agents/strategic-plan-architect.md` — background agent for docs (architecture, retro, checklist, DEVLOG)
- `.claude/agents/code-architecture-reviewer.md` — cold audit agent
- `.claude/agents/build-error-resolver.md` — pytest failure diagnosis agent
- `.claude/agents/web-research-specialist.md` — web research with ≤500-word output
- `.claude/hooks/hook.md` — hook documentation (events, exit codes, add-hook guide)
- `.claude/commands/review-architecture.md` — new slash command
- `.claude/commands/run-tests.md` — new slash command
- `.claude/scripts/run_tests.sh` — bash test runner
- `.claude/scripts/check_env.py` — environment checker
- `.claude/dev-docs/architecture.md` — initial Mermaid diagrams (macro + micro + classification map)
- `.claude/dev-docs/retro.md` — retrospective log (initial entries)
- `.claude/dev-docs/roadmap/checklist.md` — master checklist (consolidated from saas-db-migration)
- `.claude/CLAUDE_CODE_GUIDE.md` → archived to `.claude/dev-docs/archive/`

**Technical choices**:
- Skills inject on keyword detection via existing inject_context.py (no settings.json change needed)
- session_summary.py extended (not replaced) to preserve git/Docker logic
- pytest step guarded by `stop_hook_active` flag to prevent infinite Stop hook loop
- CLAUDE_CODE_GUIDE.md archived (not deleted) in case of missed pattern migration

**Tests**: 79 passed ✅ (verified via session_summary.py hook)
**Status**: ✅ Restructuring complete. All 3 existing hooks remain operational.
**Next**: Address P1 bugs (SoundCloud/Instagram credentials, meta_campaigns ALTER TABLE)

---

## 2026-03-26 — PDF, export Excel, UX sidebar, bugfixes

### Bugs corrigés
1. **`billing.py`** — `st.secrets.get()` crashait (`StreamlitSecretNotFoundError`) même avec guard `hasattr`. Remplacé par `os.getenv()` pour `STRIPE_CHECKOUT_URL` et `STRIPE_PORTAL_URL`.
2. **`.env`** — `SMTP_HOST` contenait l'adresse email au lieu de `smtp.gmail.com`. `SMTP_PORT=587` était sur la même ligne (jamais parsé). Corrigé → alertes email DAG fonctionnelles.
3. **`data_wrapped.py`** — Non-admin voyait `"Artiste 1"` au lieu du vrai nom. Admin ne voyait pas les artistes inactifs. Corrigés : query non-admin charge le nom depuis `saas_artists` ; query admin retire le filtre `active = TRUE`.

### Migration WeasyPrint → xhtml2pdf
- WeasyPrint nécessite GTK3/Pango/Cairo (indisponibles nativement sur Windows).
- Remplacé par `xhtml2pdf>=0.2.11` (pure Python). `requirements.txt` mis à jour.

### SoundCloud DAG — diagnostic IP block
- Confirmé 403 (IP bloquée) via logs Airflow. Le code actuel raise `ValueError` → tâche FAILED correctement.
- L'ancienne run (2026-03-24) montrait un silent success (bug corrigé dans commit `3d73c0a`).

### PDF export — 6 nouvelles sections
Ajoutées dans `pdf_exporter.py` : Spotify S4A top songs, YouTube, Instagram, Meta Ads, SoundCloud tracks, Apple Music. Chacune avec `_collect_xxx` + `_render_xxx`. `_collect_s4a_top_songs` accepte `songs_filter`. UI `export_pdf.py` : sélecteur S4A indépendant + case "Toutes".

### Export CSV — format Excel
- Ajout `export_excel()` dans `csv_exporter.py` (openpyxl, un onglet par table).
- `export_csv.py` : radio ZIP / Excel (.xlsx), bouton téléchargement unifié.

### Sidebar — bouton collecte en haut
- `show_data_collection_panel()` appelé avant `show_navigation_menu()` dans `main()`.
- Séparateur `---` déplacé après le bouton.

### SoundCloud view — tri par dernière release
- Ajout subquery `MIN(collected_at) AS first_seen` par track.
- Multiselect trié par `first_seen DESC`, défaut `[:1]` (dernière release uniquement).

**Fichiers modifiés** : `app.py`, `billing.py`, `data_wrapped.py`, `soundcloud.py`, `export_csv.py`, `export_pdf.py`, `csv_exporter.py`, `pdf_exporter.py`, `requirements.txt`, `.env`

## 2026-05-14 — Brick 32 : Live Activity widget ✅

### What changed
- **Migration 026** — new `active_sessions(artist_id PK FK → saas_artists, last_heartbeat TIMESTAMPTZ)` table with index on `last_heartbeat DESC`. Identity stays in `saas_artists`; activity is decoupled.
- **`live_pulse.py`** (`src/dashboard/utils/`) — three helpers : `bump_heartbeat(db, artist_id)` (fire-and-forget UPSERT, swallows `psycopg2.Error`), `get_live_pulse(db, ttl_minutes=5) -> (live, registered)` (single round-trip), and `get_registered_count_public()` decorated `@st.cache_data(ttl=600)` for the anonymous landing widget.
- **`auth.py`** — `_maybe_bump_heartbeat()` fired from `require_login()` short-circuit. Throttled at 60 s via `st.session_state['_last_heartbeat_at']`. Admins (`artist_id = None`) skipped.
- **`home.py`** — `_section_live_pulse(db)` rendering 2 `st.metric` ("🟢 Active right now" / "👥 Total registered") inserted between `_section_dag_status()` and `_section_freshness()`.
- **`register.py`** — `st.metric("Live Activity", f"{n:,} artistes utilisent streaMLytics")` at the top of `show()`. Count-only — zero PII.
- **`postgres_handler.py`** — `'active_sessions'` added to `_ALLOWED_TABLES`. **`saas_schema.py`** — entry added to `SAAS_SCHEMA` dict so fresh installs include it.

### Decisions
- TTL = 5 min (roadmap default — accepted).
- Throttle = 60 s (5 heartbeats / TTL window — enough redundancy without spam).
- Public widget on `register.py` only — not duplicated on `home.py` (auth users already see the admin pulse).
- SEO name = "Live Activity" (search intent clear; preuve sociale primaire, SEO secondaire vu les limites de Streamlit).

### Tests
- `tests/test_live_pulse.py` — 7 tests passent : upsert SQL shape + params, `psycopg2.Error` swallowed, non-DB exceptions propagated, count tuple, empty fallback, cutoff freshness, default TTL = 5 min.
- Full test suite : **183 passed** (test_api.py skipped — pré-existant `ModuleNotFoundError: fastapi`).

### Verification restante (manuelle, à faire avec Docker up)
1. `Get-Content migrations/026_active_sessions.sql | docker exec -i <pg> psql -U postgres -d spotify_etl`
2. Ouvrir 2 sessions incognito → 2 logins distincts → `home.py` doit afficher "Active right now: 2".
3. Visiter `?page=register` sans auth → "X artistes utilisent streaMLytics".

**Fichiers modifiés** : `migrations/026_active_sessions.sql` (nouveau), `src/database/saas_schema.py`, `src/database/postgres_handler.py`, `src/dashboard/utils/live_pulse.py` (nouveau), `src/dashboard/auth.py`, `src/dashboard/views/home.py`, `src/dashboard/views/register.py`, `tests/test_live_pulse.py` (nouveau), `.claude/dev-docs/roadmap/checklist.md`.

## 2026-05-14 — Phase B : Fondations + cherry-pick msdr ✅

### What changed
Revue de la référence Airbus `msdr_predictive_maintenance` contre streaMLytics. Adoption de 3 patterns qui apportent un gain clair, rejet motivé de 7 patterns qui seraient du cargo-culting sur un SaaS CRUD non-safety-critical.

### Adopté
- **`Makefile`** (nouveau, 10 cibles) : `make up/down/logs/test/lint/migrate/dashboard/sync/clean`. Standardise les commandes, baisse le coût d'onboarding.
- **`pyproject.toml`** + **`uv.lock`** (nouveaux) : migration de `requirements.txt` → `pyproject.toml` avec dev extras. `uv lock` résout 231 packages en 3.4s. `requirements.txt` conservé pour le Dockerfile/CI actuel (legacy parallel).
- **CI/CD split** : `.github/workflows/ci.yml` épuré (lint+test only), nouveau `cd-release.yml` (Railway + Hetzner — `if: false` jusqu'à refresh secrets), nouveau `security-nightly.yml` (cron 03:00 UTC, `pip-audit --strict` + `gitleaks`).
- **`docs/checklists_ml/`** (nouveau) : import des 10 checklists ML baseline (9 HTML + `unified_ml_checklist.md` 172 KB) depuis `claude_code_deployment_baseline`.
- **`docs/adr/ADR-002-no-alembic-no-repository-pattern.md`** (nouveau) : ADR documentant les non-choix.

### Rejeté (motivé dans ADR-002)
- Alembic (26 migrations SQL plates marchent, rollback jamais utilisé)
- Repository pattern (`PostgresHandler` direct + `_ALLOWED_TABLES` allowlist suffisent)
- Domain/services DDD layer (over-engineered pour un CRUD SaaS)
- Observability stack Prometheus/Grafana/OTel (pas d'astreinte, pas de SLO)
- `infra/` dir (3 Dockerfiles + 1 compose.yml à la racine = lisibilité OK)
- Streaming Redis/MQTT/FSM (pas de temps réel, batch suffit)
- DR scripts (criticité ne le justifie pas)

### Tests
- `make test` : **183/183 verts** (suite globale hors `test_api.py` pré-cassé).
- `uv lock` : résolution OK, 231 packages.
- `make help` : 10 cibles listées correctement.

### Differé Phase C (à confirmer plus tard)
- `mypy.ini` soft sur les nouveaux fichiers seulement (pas strict sur ~30K LOC).
- Adaptation des checklists ML au scope streamlytics (retirer les sections hardware industriel).
- Verif manuelle Brick 32 (toujours en attente côté user).

**Fichiers ajoutés** : `Makefile`, `pyproject.toml`, `uv.lock`, `docs/checklists_ml/*` (10), `docs/adr/ADR-002-no-alembic-no-repository-pattern.md`, `.github/workflows/cd-release.yml`, `.github/workflows/security-nightly.yml`.
**Fichiers modifiés** : `.github/workflows/ci.yml` (extraction deploys), `.claude/dev-docs/ROADMAP.md` (table ADR à jour).

## 2026-05-14 — Phase D : Graphify regen + tooling doc + ML checklist filter + refactor audit ✅

### What changed
Suite à Phase B, audit complémentaire couvrant 4 axes : (1) état réel de
graphify et RTK (les deux étaient déjà actifs, simplement non-documentés
côté projet), (2) filtrage de la checklist ML 172 KB au scope streamlytics,
(3) audit du refactor dashboard (rapport prioritisé, pas de code).

### Livraisons
- **Graphify** : `graphify update .` régénère le graph local (1532 nodes,
  3106 edges, 94 communities — couvre Brick 32 + Phase B). `graphify-out/`
  reste gitignored, regen = step opérationnel sans commit.
- **`CLAUDE.md` — section "Tooling auxiliaire"** : commit `docs(tooling)`.
  Documente RTK (user-level proxy, 95.6% efficiency observée) et graphify
  (commands de refresh). Aucun code ajouté, juste de la doc onboarding.
- **`docs/checklists_ml/RELEVANT_FOR_STREAMLYTICS.md`** : commit
  `docs(checklists)`. Filtre les 13 sections de `unified_ml_checklist.md` :
  ~60% applicables, ~40% rejetées (RL, time-series indus, Prometheus,
  Kubernetes, DR — cohérent ADR-002). Soulève 3 questions P3 :
  drift detection §9.3, MLflow registry §9.1b, retraining strategy §9.4.
- **`.claude/dev-docs/refactor-audit-dashboard.md`** : commit `docs(refactor)`.
  Rapport prioritisé des 7 pain points de `src/dashboard/` (14 257 lignes
  totales) avec effort / risque / ROI par item. Top recommandations :
  (1) context manager `project_db()` (1h, faible risque, 34 fichiers
  simplifiés), (2) `trigger_algo.py` package split (4-6h, ROI élevé).
  Pas de refactor effectif — user choisit dans une brique ultérieure.

### Constats clés
- Graphify et RTK étaient **déjà intégrés** au niveau infra (`.mcp.json`,
  hook PreToolUse, RTK user-level) mais absents de `CLAUDE.md`. Gap doc
  comblé.
- `src/dashboard/views/` médiane 250 lignes (OK), 95e percentile 608 lignes,
  pire offender 1209 (`trigger_algo.py`). Split de cet offender est *pré-fait*
  par l'auteur original (5 `_show_tab_*` distincts) — l'effort se réduit à
  déplacer en sous-fichiers.
- 34 vues ouvrent une connexion DB manuellement avec un `try/finally:
  db.close()` ; un context manager retirerait ~170 lignes de boilerplate.

### Tests + non-régression
- `make test` : 183/183 verts (inchangé).
- `make lint` : mêmes 7 findings pré-existants (kpi_helpers + home + register),
  rien de nouveau introduit par Phase D (qui est full-doc).

### Hors scope, différé
- Refactor effectif des pain points listés : user décide après lecture du
  rapport. Trigger naturel = "next time you touch that view".
- mypy.ini soft (toujours différé depuis Phase B).
- Verif manuelle Brick 32 (toujours en attente côté user).
- Push des commits sur `origin/main` (user décide quand).

**Fichiers ajoutés** : `docs/checklists_ml/RELEVANT_FOR_STREAMLYTICS.md`, `.claude/dev-docs/refactor-audit-dashboard.md`.
**Fichiers modifiés** : `CLAUDE.md` (section "Tooling auxiliaire"), `DEVLOG.md` (cette entrée).

## 2026-05-14 — CLAUDE.md rework + cytoscape graph viewer ✅

### What changed
Audit du `CLAUDE.md` post-Phase-D : 5 bugs détectés (double section "Cross-Cutting Rules", PowerShell-only migration, pas de mention `make`/`uv`/`pyproject.toml`, pas de pointeurs vers `dev-docs/architecture/*`). 4 edits ciblés appliqués. Le 5e (mention `make logs`) est couvert par la nouvelle table "Development tooling".

Côté graphify, le user demandait un viewer HTML. Confirmation que la CLI graphify n'en produit pas (sortie native = `graph.json` + `GRAPH_REPORT.md` md). Implémentation d'un viewer maison `tools/graph_viewer.html` (cytoscape.js via CDN, ~250 lignes standalone). Servable via `make graph-viewer`.

### Livraisons
- **`CLAUDE.md`** :
  - Consolidation de la double "Cross-Cutting Rules" (la 1re était un wrapper inutile)
  - Nouvelle section "Running Migrations" recommandant `make migrate` (WSL/bash) et conservant PowerShell pour Windows-native
  - Nouvelle table "Development tooling" (Makefile + pyproject.toml + uv.lock + ruff.toml)
  - Nouvelle table "Reference docs (dev-docs/)" listant 10 pointeurs vers `dev-docs/architecture/`, `docs/adr/`, `docs/checklists_ml/`, `refactor-audit-dashboard.md`
  - Mise à jour de la section graphify pour mentionner `make graph-refresh` et `make graph-viewer`
- **`tools/graph_viewer.html`** (nouveau, 254 lignes) :
  - cytoscape.js + fcose layout via CDN unpkg
  - Click sur noeud → panneau latéral avec source_file, location, community, degree, voisins (cliquables)
  - Regex search sur labels (dim/highlight)
  - Switcher de layout (fcose / cose / circle / concentric / grid / breadthfirst)
  - Coloration par community (palette 20 couleurs cyclique)
  - Distinction edges EXTRACTED (plain) vs INFERRED (dashed, opacity 0.35)
- **`Makefile`** :
  - `make graph-refresh` — wrapper de `graphify update .`
  - `make graph-viewer` — lance `python3 -m http.server 8765` puis indique l'URL du viewer

### Vérification
- `make help` : 12 cibles listées (avant : 10).
- `make graph-refresh` : OK (~3s, mise à jour graph.json + GRAPH_REPORT.md).
- Viewer : ouvert localement, charge bien le graph (1532 noeuds, 3106 edges, 94 communities).
- Tests inchangés (Phase post-doc, pas de code applicatif touché).

### Hors scope
- Filtre par community dans le viewer (palette est cyclique → community 0 et 20 ont la même couleur ; négligeable pour usage actuel).
- Export PNG/SVG du graph rendu (cytoscape supporte mais pas implémenté ici).
- Embed du graph.json dans le HTML (pour permettre `file://` direct sans serveur) — gros fichier (1.7 MB) qui alourdirait inutilement le viewer.

**Fichiers modifiés** : `CLAUDE.md`, `Makefile`, `DEVLOG.md`.
**Fichiers ajoutés** : `tools/graph_viewer.html`.

## 2026-05-14 — Switch from cytoscape viewer to native graphify HTML ✅

### What changed
Le viewer cytoscape `tools/graph_viewer.html` (introduit dans le commit précédent) nécessitait `make graph-viewer` → `python3 -m http.server` parce que Chrome bloque `fetch()` sur `file://`. Le user a signalé que dans son projet de référence msdr, il n'y a **pas** besoin de serveur — le HTML s'ouvre directement.

Investigation : graphify expose `to_html()` dans `graphify.export` (alias `generate_html`) qui produit un HTML autonome avec vis-network bundled inline. La CLI ne l'expose pas en command direct, mais msdr a un script `tools/dev/graphify_render_html.py` qui l'appelle. Solution : porter ce script.

### Livraisons
- **`tools/dev/graphify_render_html.py`** (nouveau, 53 lignes) — copie quasi-littérale du script msdr. Charge `graph.json`, reconstruit NetworkX `G` + communities, appelle `ex.to_html()`. Lift le cap `MAX_NODES_FOR_VIZ` à 100k pour future-proof.
- **`Makefile`** :
  - Retiré : `make graph-refresh`, `make graph-viewer`
  - Ajouté : `make graph-update` (= `graphify update .`), `make graph-html` (= script render), `make graph` (les deux en un)
- **`tools/graph_viewer.html`** : **supprimé** (cytoscape viewer obsolete vs natif vis-network)
- **`CLAUDE.md`** : section graphify mise à jour pour pointer vers le HTML autonome, plus aucune mention de serveur HTTP

### Vérification
- `python3 tools/dev/graphify_render_html.py` : OK, produit `graphify-out/graph.html` (1.3 MB, 1532 nodes / 3106 edges / 94 communities).
- `make help` : 13 cibles, plus de `graph-viewer`, ajout de `graph-update` / `graph-html` / `graph`.
- `tools/` : `dev/` (nouveau dossier avec le script), `tools/graph_viewer.html` supprimé.
- `graphify-out/graph.html` : ouvrable direct en `file://`, vis-network inline, pas de serveur requis.

### Rationale
Mon viewer cytoscape avait des features sympas (regex search, 6 layouts switchables) mais introduisait du code maison à maintenir et obligeait à un workflow `make graph-viewer` + ouvrir URL. Le natif graphify (vis-network) est :
- (a) maintenu upstream — pas de drift à gérer si graphify update son format
- (b) **autonome** — `file://` marche, zero friction d'usage
- (c) consistent avec le pattern msdr (le user a déjà cet usage en muscle memory)

Trade-off accepté : on perd les features cytoscape spécifiques (multi-layout switcher, regex search), mais on gagne en simplicité d'usage et alignement avec la baseline msdr.

**Fichiers ajoutés** : `tools/dev/graphify_render_html.py`.
**Fichiers supprimés** : `tools/graph_viewer.html`.
**Fichiers modifiés** : `Makefile`, `CLAUDE.md`, `DEVLOG.md`.

---

## 2026-05-14 — Repo cleanup + security hardening + supply chain ✅

### Why
Session de consolidation : nettoyage du repo accumulé sur plusieurs sprints + un audit en 3 axes (`src/`, roadmap unicité, config layer) a révélé des P1/P2 non traités malgré 32 bricks livrées. Objectif : remettre le repo en état canonique avant de commencer Phase 2 du SaaS (cf. `ROADMAP.md` brick 33+).

### What changed — 13 commits

**Clean repo (3 commits)** — `a4fa11e` → `418fad5`
- Nouveau dossier `.archive/` (gitignored) pour fichiers obsolètes ; ~22 fichiers déplacés (skills inutilisés, dev-docs stubs, security-reviewer agent doublon, retro.md/system-audit.md datés, archive/meta_api_v1/ legacy v1, brick-snapshots template).
- CLAUDE.md aligné avec l'état réel : retrait des références ROADMAP.md (stub vide) et `/audit-collectors` (slash command inexistant), ajout meta-ads-credential-guide + refactor-audit-mlops dans le tableau "Reference docs", description agent `strategic-plan-architect` mise à jour pour pointer REX blocks (rules/rex-format.md) plutôt que `retro.md`.

**P2 intégrité données (1 commit)** — `a0f86de`
- `src/collectors/instagram_api_collector.py:97-98` et `:196-224` : `except Exception` warn-only remplacé par `logger.error` + `raise` (CLAUDE.md rule #6). Avant : SQL fail dans `save_to_db` retournait silencieusement et `run()` indiquait succès — données non collectées sans alerte. Token persist DB fail idem.
- Dédup `requirements.txt` : retiré 3 doublons (python-dotenv, pandas, psycopg2-binary aux lignes 62-64).
- `print()` → `logger.{info,warning,error}()` dans 4 collectors (28 sites, emojis strippés).
- `datetime.now()` → `datetime.now(timezone.utc)` dans 13 sites `collected_at` (rule python.md). Les 3 sites filename strftime laissés (cosmétiques).

**Runtime cohérent (1 commit)** — `52db15f`
- `Dockerfile.airflow` : base image `apache/airflow:2.8.1-python3.10` → `python3.11`. Aligne avec `pyproject.toml requires-python = ">=3.11"`.
- Rebuild + smoke test : 15 DAGs chargent sans erreur, sklearn 1.8.0 / xgboost 3.2.0 / shap 0.49.1 résolvent.

**P1 sécurité — SQL allowlist (2 commits)** — `d41a842` + `997dcde`
- `src/dashboard/views/{db_health,admin,airflow_kpi}.py` : appels explicites `validate_table()` / `validate_columns()` avant chaque f-string SQL qui interpole un identifiant (rule #8). Avant : allowlist implicite via constantes (`_DATASETS`, `_GDPR_PLATFORM_TABLES`, `_INSERTION_TARGETS`) — défense-en-profondeur incomplète.
- db_health : validation hors try/except (dataset doit être allowlisté, sinon scream loud). admin GDPR : validation dans try/except (tables non-allowlistées tombent en `-1`, sémantique identique à "table missing"). airflow_kpi : tous targets allowlistés.
- Promotion `_validate_table` → `validate_table` (et idem pour `_validate_columns`) en API publique : 6 sites internes postgres_handler + 3 sites externes + 1 commentaire test renommés. Évite la convention "import du privé".

**Supply chain (2 commits)** — `6c323c9` + `e6513b4`
- `.github/dependabot.yml` : pip hebdo (minor/patch groupés, security séparé, majors ignorés), github-actions mensuel, docker mensuel (auto-discovers Dockerfile + .airflow + .api). Boucle "CVE détecté → PR de fix" fermée (pip-audit dans security-nightly.yml restait observationnel).
- `.github/workflows/ci.yml` : `setup-python` + `pip install -r requirements*.txt` → `astral-sh/setup-uv@v4` + `uv sync --frozen --extra dev`. CI lit désormais `uv.lock` (231 packages pinned). Sans ce changement, les PRs Dependabot qui bumpaient `uv.lock` n'auraient eu aucun effet sur CI.

### Décisions explicites de non-faire

- **Phase B1 (helper `get_table_freshness()`)** : audit avait surcompté à "12+ sites". Réelle dédup possible = 1-2 sites (les autres sont des strings de doc dans `useful_links.py` rendus en UI pour copier-coller psql, OU des GROUP BY subqueries différentes). Abstraction prématurée écartée.
- **Phase C #1 (kpi_helpers.py consolider 6 `get_total_*`)** : agrégations toutes différentes (SUM(daily_max), DISTINCT ON, view_count last value). Branching `if artist_id is not None` ne peut pas être éliminé sans f-string SQL (interdit par rule #8). Pas de helper paramétré propre.
- **Phase C #2 (meta_ads_api_collector split)** : fichier 753L mais déjà bien structuré (section headers, helpers groupés en tête, classe orchestrée). Split en 4 sous-modules = boilerplate (re-exports, passage état) sans gain net.

### Out-of-scope reportés

- `.env.railway.example` incomplet (Railway CI désactivé `if: false`).
- Phase C #9 `credentials.py` 853L (vrai candidat split par plateforme, demande validation UI manuelle).
- `check_roadmap_update.py` orphan refs (BRICKS.md, DEPLOYMENT.md inexistants, hook exit 0 toujours).
- pytest sans `--cov` (gap d'observabilité, pas un bug).
- `docker-compose.yml` credentials hardcodés (fichier gitignored, pattern à revoir).

### Tests
- `pytest tests/ -q --ignore=tests/test_api.py` → **193 passed** après chaque commit.
- `test_api.py` reste cassé sur `ModuleNotFoundError: jose` (préexistant, env-only — `python-jose` pas installé localement, mais OK en CI).
- Smoke Airflow : `docker exec airflow_scheduler airflow dags list-import-errors` → No data found.

### Graphify
- Refresh : 1581 nodes / 3150 edges / 114 communities (vs 1500/94 ce matin).

**Fichiers modifiés/ajoutés** : `.archive/` (gitignored, 22 fichiers), `.gitignore`, `CLAUDE.md`, `.claude/dev-docs/architecture.md`, `.claude/skills/response-protocol.md`, `.claude/agents/strategic-plan-architect.md`, `Dockerfile.airflow`, `.github/dependabot.yml` (nouveau), `.github/workflows/ci.yml`, `requirements.txt`, `src/collectors/{instagram_api,meta_csv_watcher,meta_insight_watcher,s4a_csv_watcher,meta_ads_api,soundcloud_api,spotify_api,youtube}.py`, `src/dashboard/views/{db_health,admin,airflow_kpi}.py`, `src/database/postgres_handler.py`, `tests/test_postgres_handler.py`.

---

## 2026-05-14 (suite) — Phase E wrap-up : REX promotion + hook fix + env + coverage ✅

### What changed — 4 commits

**REX promotion (`a3b13d9`)** — 2 drafts validés et injectés :
- `strategic-plan-architect.md` : ref Mermaid pointait vers stub archivé → corrigée vers `architecture.md`
- `response-protocol.md` : deliverable retro.md contredisait `rex-format.md` → remplacé par per-tool REX block
- Validator `python3 .claude/scripts/validate_rex.py` → 42 tools OK / 0 errors

**Hook orphan fix (`bcfe774`)** — `check_roadmap_update.py` était un **no-op silencieux** :
- `_INCLUDE = "src/Application"` ne matchait jamais ce repo (code dans `src/`)
- `_TRACKER_PATHS` pointait vers `ROADMAP.md` (archivé), `BRICKS.md` + `DEPLOYMENT.md` (inexistants)
- Fix : `_INCLUDE = "src" + os.sep` avec excludes (`.claude/hooks`, `.claude/scripts`, `airflow/debug_dag`, `tests/`), trackers = `roadmap/checklist.md` + `DEVLOG.md`. Reminder écrit sur stderr (où Claude Code remonte les hooks), emoji stripped.

**Env templates (`66f807d`)** — double bug :
- `.gitignore` règle `.env.*` swallowait `.env.example` ET `.env.railway.example` → jamais trackés, invisibles au clone. Ajout `!.env.example` + `!.env.railway.example`.
- `.env.railway.example` manquait les vars Stripe (Brick 21) : `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_CHECKOUT_URL`, `STRIPE_PORTAL_URL` lues par `src/api/routers/stripe_webhook.py` + `billing.py`. L'audit avait flaggé SPOTIFY/META/YOUTUBE comme manquants, mais ces clés sont collector-side (Airflow local, pas Railway) — footer "Not required on Railway" ajouté pour bloquer les faux fix futurs.

**Pytest coverage (`7376aae`)** — observabilité tests :
- `pyproject.toml` : `[tool.coverage.run]` (branch coverage, source=src/, omit migrations/tests/__pycache__/api.main), `[tool.coverage.report]` (show_missing, exclude TYPE_CHECKING/__main__/NotImplementedError).
- `ci.yml` : pytest gagne `--cov=src --cov-report=xml --cov-report=term-missing`, upload coverage.xml en artifact 7 jours.
- **Pas de `fail_under`** : mesure d'abord, gate plus tard (éviter les seuils arbitraires sans baseline).

### Skip explicite — Phase C #9 credentials.py (après lecture honnête)

L'audit avait proposé "split par plateforme". Lecture du code révèle structure différente :
- 244L helpers techniques (crypto, DB, mask) — shared
- 90L `_test_*` (4 plateformes, ~25L chacun) — petits hooks data
- 150L `_guide_*` (4 markdown guides) — text content
- 250L **renderer générique paramétré** (`_render_platform_tab`, `_handle_save`) — UN codepath pour 7 plateformes
- Reste : orchestrator `show()`, KPI, save handler

**Pas d'UI par-plateforme à splitter**. Il y a UNE UI générique + 4 data-hooks. Splitter par plateforme = boilerplate (imports croisés) sans gain ; splitter par concern = 6 fichiers pour 1, downgrade de navigation. Le fichier est bien factorisé tel quel.

C'est le 3e item Phase C rejeté après analyse (avec C#1 kpi_helpers et C#2 meta_ads_api_collector). Pattern observé : l'audit générique "fichier > 400L = split" ne survit pas à la lecture du code dans ce repo. Les vrais wins ont été ailleurs (P1 SQL allowlist, P2 silent success, supply chain).

### Restant légitimement TODO

- Hardcoded credentials dans `docker-compose.yml` (gitignored, mais pattern à revoir si on Compose-ifie autre chose)
- Phase C autres items (#3-#8, #10) : aucun n'a été lu en détail aujourd'hui, mais le pattern Phase C #1/#2/#9 suggère que la majorité ne mérite pas un split. À ré-évaluer un par un si besoin futur.

---

## 2026-05-31 (suite) — Source unique = roadmap/checklist.md : config repointée + RR/RADIO calibration export + make migrate

### Why
Audit roadmap/déploiement demandé. Découvert que `/resume`, `/sprint`, `/adr`, le hook `session_summary.py` et l'agent `strategic-plan-architect` lisaient `.claude/dev-docs/ROADMAP.md` + `.claude/dev-docs/work-in-progress/` — **deux chemins inexistants dans ce repo** (résidus d'un template d'autre projet). `/resume` ne ressortait donc rien. Pas de `deployment.md` non plus. La vraie source unique est `.claude/dev-docs/roadmap/checklist.md`.

### What changed
- **Source unique = `checklist.md`.** Repointé : `.claude/commands/{resume,sprint,adr}.md` (réécrits pour lire checklist.md + `docs/adr/`), `.claude/hooks/session_summary.py` (`_DELIVERABLES` + snapshot resume + reminders), `.claude/agents/strategic-plan-architect.md`, `.claude/rules/rex-format.md`, `.claude/commands/dev-docs.md`, `.claude/skills/verification.md`. REX colocalisé ajouté (resume/sprint/adr/session_summary) — `validate_rex.py` : 48 tools OK, 0 erreur. `check_roadmap_update.py` était déjà correct ; `pre_compact.py`/`session_summary.py` gèrent l'absence de `work-in-progress/` sans crash (smoke rc=0). Au passage, fix de 8 E741 préexistants (`l` → `line`) dans session_summary.py pour passer pre-commit.
- **`make migrate` appliqué** — Postgres up ; migrations 036 (radio_streams_forecast_7d) + 037 (pi_forecast_7d) + 038 (s4a_song_saves_daily) confirmées présentes. Lève le "RUNTIME STEP PENDING".
- **`machine_learning/export_calibration_bands.py`** (nouveau) — bandes de calibration RR/RADIO depuis les classifieurs sauvegardés (load-only, pas de retrain). NON câblé dans `ALGO_CALIBRATION_BANDS` : mismatch score brut (consumer `calibration_note`) vs Platt-calibré (export) à réconcilier d'abord.

### Tests
`python3 -m pytest tests/ -q` → **285 passed, 1 skipped**. `session_summary.py` AST OK + ruff clean après fix E741. `validate_rex.py` clean (48 tools). `checklist.md` inchangée (md5 == HEAD).

---

## 2026-05-31 (suite 2) — Backlog "tout ce qu'on peut faire" : tracks multi-tenant, perf batch, render-smoke harness, Discovery Mode

### Why
Après `/resume`, balayage de tous les items checklist actionnables **sans dépendance live** (DAG re-trigger, artefacts ML, capture S4A Phase-2 = exclus). Priorité P2 → P3 → P4, chaque lot vérifié (ruff + pytest) avant le suivant.

### What changed

**P2 — `tracks` → multi-tenant (fuite cross-tenant fermée).** `migrations/039_tracks_multi_tenant.sql` : `saas_artists.spotify_artist_id` (pont) + `tracks.saas_artist_id` FK + index, **auto-bridge idempotent non-ambigu** (1 seul tenant actif ⊗ 1 seul `artist_id` distinct → lien auto ; no-op dès qu'un 2e tenant existe). Appliqué au live (saas id=1 ← `7sbfafbLjNZGZJZjZ3xoPB`, 11 tracks). Writer `spotify_api_daily.collect_spotify_top_tracks` résout + stampe `saas_artist_id` (warn si non-ponté). 4 readers filtrés par tenant : `spotify_s4a_combined` ×3, `trigger_algo` ×2 (branche admin laissée non-filtrée), `meta_x_spotify` ×1 ; admin (None) = pas de filtre. `init_db.sql` MAJ. Varchar `tracks.artist_id` legacy conservé (drop dans un cycle ultérieur). `audit-tracks-legacy.md` marqué RESOLVED.

**P3 perf.** (1) `@st.cache_data(ttl=60)` sur 8 getters read-only de `kpi_helpers.py` — handle DB passé en `_db` (underscore → exclu de la clé de cache, clé = artist_id ; aucun caller Airflow → décorateur sûr). (2) **N+1 Airflow** : nouveau `AirflowMonitor.get_all_dags_last_state()` = 1 POST batch `~/dagRuns/list` (vs ~15 appels), fallback per-DAG si endpoint indispo ; 3 callers repointés (`airflow_kpi`, `home`, `credentials/_core`). Non smoke-testé live (webserver Airflow down) — le fallback garantit la correction. (3) `@st.fragment` sur `home._section_pdf_export` + `airflow_kpi._section_insertion_test` (rerun isolé). (4) Downsampling >500 pts du cumulatif S4A (`spotify_s4a_combined`, dernier point conservé). (5) `SELECT *` → littéral dans le CTE `apple_music` ; `data_wrapped` gardé générique **par design** (`.to_dict()` + colonnes dynamiques, cf. DEVLOG#2026-05-29). **Lazy imports DÉ-PRIORISÉ** (pas bloqué) : `app.py` charge déjà les vues lazy par page → déplacer `import plotly` dans `show()` gagne ≈0, et le bundle JS domine le cold start.

**P3 ML — `DaysSinceRelease`.** `ml_inference.build_features` résout la date de sortie **par chanson** depuis `track_release_reference` (match sur `normalize_track_title`), fallback timeline `MIN(date)` uniquement sans match (le backfill one-shot donnait la même first-appearance à tous les titres). Vérifié end-to-end.

**NOUVEAU — harnais render-smoke.** `tests/test_views_render_smoke.py` : `AppTest`-exécute les `show()` des **36 vues** (session admin, DB live), assert "aucune exception". Comble le trou "zéro couverture render" (classe de régression qui passait au vert, cf. WAVE 3). Skip module si Postgres injoignable (CI sans DB). 36 pass en ~13 s. C'est ce harnais qui a dé-risqué les `@st.fragment` ci-dessus.

**Phase-2 ML — Discovery Mode (un-impute feature).** `migrations/040_s4a_song_discovery_mode.sql` (table calquée sur `s4a_song_playlist_adds`, opt-in daté par chanson) + `init_db.sql` + `_ALLOWED_TABLES`. `build_features` source `IsThisSongOptedIntoSpotifyDiscoveryMode` depuis la dernière saisie (défaut 0.0). `trigger_algo` : metric "🔭 Discovery Mode" + formulaire opt-in manuel. Gardé dans `_IMPUTED_FEATURES` (exclu du drift — flag binaire, z-score sans sens). End-to-end vérifié (feature 0→1 à l'opt-in). Reste imputés : `NonAlgoStreams28Days`, `HowManySongsDoYouHaveInRadioRightNow` (Phase-2).

**REX.** `/rex-promote` : 4 entrées injectées (`strategic-plan-architect`, `dev-docs`, `rex-format`, `verification`) reconstruites depuis le diff `2d7a84f` (repoint ROADMAP.md→checklist.md) ; 4 drafts droppés (doublons — adr/resume/sprint/session_summary avaient déjà une entrée 2026-05-31). Validator : 48 tools OK.

### Tests
`python3 -m pytest tests/ -q` → **321 passed, 1 skipped** (285 + 36 render-smoke). `ruff check src/ tests/` clean. Migrations 039 + 040 appliquées au live + vérifiées (backfill, feature flip). `validate_rex.py` → 48 tools, 0 erreur.

### Reste à faire (bloqué / hors-scope headless)
- **Live infra** : confirmation re-trigger DAG Meta/SoundCloud, backfill Meta Ads (Airflow webserver down).
- **Artefacts/data externes** : courbe calibration RR, re-seed benchmark, items Phase-2 capture/retrain.
- **À scoper, pas à bricoler à l'aveugle** : Meta per-chunk insight persistence + rename-guard `campaign_name` (collecteur throttle-sensible, compte de test throttlé).
- **Faible valeur** : pagination admin/etl_logs (gain ~nul à la taille actuelle).

---

## 2026-06-01 — Meta Ads full_history backfill réussi (P2 fermé) — live ops via Airflow MCP

### Why
Session live : Airflow webserver de nouveau up. L'utilisateur a lancé la collecte complète ("Lancer TOUTES") puis demandé de finir le backfill Meta Ads (item P2 ouvert depuis 2026-03-30, bloqué sur le throttle BUC `code 80004`).

### What changed
- **Backfill Meta Ads terminé — item P2 fermé.** Diagnostic live (logs DAG via `docker exec` + Airflow MCP read-only) : le `code 80004` n'était PAS un blocage de fond mais un artefact de quota épuisé — plusieurs runs Meta lancés coup sur coup (scheduled + 2 daily manuels via le bouton + un full_history) ont saturé l'ad-account ; le full_history a wall-throttlé ~26 min sur le fetch per-creative, puis a été tué. **Fix qui marche** : arrêt de toute activité Meta → cooldown ~60 min → UN seul run `full_history` solo sur quota reposé → succès en ~4 min, **zéro throttle** : 34 campaigns, 69 adsets, 144 ads, 144 creatives, **13139 lignes d'insights sur 23 tables** (dont tous les breakdowns ad/adset × country/placement/age, vides jusque-là). `meta_insights_performance_day` couvre 2023-08-24 → 2024-09-29 (231 lignes / 205 jours) = durée de vie complète des campagnes ; ne dépasse pas 2024-09-30 car l'ad-account n'a aucune dépense depuis (le daily ne trouve rien de plus récent) — le critère "past 2024-09-30" de la checklist était une hypothèse erronée.
- **Règle opérationnelle confirmée** : `max_active_runs=1` (déjà en place sur les 13 DAGs) + UN run solo sur quota reposé = la façon fiable de lancer un full_history Meta. Ne jamais enchaîner des runs Meta concurrents/back-to-back. Le bouton "Lancer TOUTES" re-queue un run Meta à chaque clic → tenu en file par le cap (vérifié live : run redondant annulé via PATCH state=failed sur le dagRun + la task pour bloquer l'auto-retry).
- **Note non-régressée** : le gap "Meta per-chunk insight persistence" reste ouvert (un throttle sur un appel agrégat tardif jette tout le run) — séparé, candidat hardening.

### Tests
Pas de changement de code (ops live uniquement). Vérif DB : `SELECT MIN/MAX(day_date), COUNT(*) FROM meta_insights_performance_day WHERE artist_id=1` → 2023-08-24 / 2024-09-29 / 231. Log DAG : `success`, return code 0, 0× `80004` sur le run final.

---

## 2026-06-01 (suite) — Backlog actionnable : Meta per-chunk persistence + rename-guard, 2 render-crash fixes, R2 closé

### Why
Après le backfill Meta, l'utilisateur a demandé de traiter **tout le bucket "actionnable maintenant"** de la roadmap (code pur, zéro dépendance externe). Au passage, le harnais render-smoke a détecté 2 crashs introduits par les données live du jour.

### What changed
- **P2 — Meta per-chunk insight persistence** (`meta_ads_api_collector.py`). `run()` jetait tout le run sur un throttle tardif (fetch complet en mémoire → un seul `_upsert_all` final). Désormais : config (campaigns/adsets/ads/creatives) upsertée **en amont** via `_upsert_config`, puis `_fetch_all_insights` persiste **chaque chunk mensuel + chaque breakdown dès qu'il est récupéré** via `persist_cb` (`_persist_insights`). `_upsert_all` supprimé → scindé en `_upsert_config` + `_insight_upsert_maps` (source unique des maps colonnes/clés) + `_persist_insights`. Un throttle tardif conserve désormais tous les mois déjà fetchés.
- **P2 — rename-guard `campaign_name`** (`meta_ads_api_collector.py`). `_prune_renamed_campaigns()` supprime les lignes campaign-grain dont le `campaign_name` n'est plus renvoyé par l'API (grains ad/adset keyés par id = immunisés). Gardé : fetch vide = no-op (jamais de mass-delete) ; `validate_table()` (rule #8) ; DELETE artist-scopé + `campaign_name <> ALL(%s)` paramétré ; `_CAMPAIGN_GRAIN_TABLES` frozenset (10 tables).
- **Tests** : `tests/test_meta_ads_collector.py` +6 (20→26) — trimming colonnes, **preuve de durabilité** (throttle au chunk 2 → chunk 1 persisté), prune (no-op vide + 10 DELETE scopés). Blast radius nul (helpers d'extraction pure intacts ; `_upsert_all`/`_fetch_all_insights` n'étaient appelés que par `run()`).
- **2 render-crash fixes** (data-driven, indépendants du refactor — prouvé par `git stash`). `airflow_kpi.py` : `df_runs` start/end_date = ISO strings tz-mixtes → `pd.to_datetime`/`px.timeline` "Cannot mix tz-aware with tz-naive" ; normalisés en naive-UTC une fois (`utc=True` + `tz_localize(None)`). `soundcloud.py` : un NULL dans likes/reposts/comment rendait la colonne object → `(_eng/_pc*100).round(1)` "Expected numeric dtype, got object" ; coercition `pd.to_numeric(errors='coerce')` + `.where(_pc!=0)` (même pattern que le fix `revenue_forecast`).
- **R2 (refactor-program) closé** — `kpi_helpers.py` déjà ruff-clean sous la config autoritaire (`E501` ignoré pour les SQL ; F401/F541 de l'audit déjà nettoyés par le sweep de mai). Verify-and-close, zéro edit fabriqué. Trackers `refactor-program.md` + `refactor-audit-dashboard.md` (#4) marqués DONE.

### Tests
`python3 -m pytest tests/ -q` → **325 passed** (dont les 2 vues réparées repassent au render-smoke, +6 meta). `ruff check src/ tests/` clean.

---

## 2026-06-01 (suite 2) — Refactor program R2/R4/R5/R6 (move-only, séparé en commits)

### Why
Sur demande explicite « tout faire » du bucket actionnable, exécution des refactors R2/R4/R5/R6 du programme — en forçant les triggers (non déclenchés) mais en respectant les garde-fous : un commit/PR par item, zéro changement de comportement, vérifié par render-smoke + pytest.

### What changed
- **R2 (kpi_helpers)** — clos *verify-and-close* : déjà ruff-clean sous la config autoritaire (E501 ignoré pour SQL ; F401/F541 de l'audit nettoyés depuis). Zéro edit fabriqué.
- **R4 (trigger_algo → package)** — le monolithe avait **doublé** (2279 l, 6 tabs, ~40 fns). Scindé en package : `router.py` (show() slim), un `_tab_*.py` par onglet, `_common.py` = **les 47 helpers/loaders/constantes partagés** (module unique → pas de cycle inter-tabs ; vérifié : les 6 tab-fns ne sont appelées que par show(), seul `show` est importé dehors). Généré via script AST calculant les imports exacts par module. `pytest` 325 inchangé, render-smoke[trigger_algo] vert, `show` résolu depuis `router`.
- **R5 (pdf_exporter)** — rejeté le mega `_render_section` esquissé (les 6 renderers diffèrent trop pour être byte-identiques) ; extrait 3 primitives exactes (`_html_table`/`_kpi_card`/`_kpi_grid`) utilisées par 7 renderers. **Filet snapshot** : `tests/test_pdf_exporter.py` compare `render_html` à un golden (`tests/fixtures/pdf_report_golden.html`, freshness_status monkeypatché) → **byte-identique** avant/après. pdf_exporter avait 0 test, maintenant 2. Hooks whitespace exclus sur `tests/fixtures/` pour préserver le golden.
- **R6 (revenue_forecast)** — math déterministe extraite vers `utils/revenue_forecast.py` : 3 loaders DB (déplacés, ré-aliasés → call-sites inchangés) + `project_mrr`/`ltv_global`/`ltv_scenarios`. `tests/test_revenue_forecast.py` (+8). Le tab de 285 l `_tab_artist_forecast` garde sa math interleaved (extraction profonde plus risquée sans golden → passe future, son propre trigger). Vue 628→586 l.
- Trackers `refactor-program.md` + `refactor-audit-dashboard.md` (#1/#4/#5/#6) marqués DONE avec notes as-built (déviations documentées, Rule #2).

### Tests
`python3 -m pytest tests/ -q` → **335 passed, 1 skipped** (325 + 8 R6 + 2 R5). `ruff check src/ tests/` clean. 5 commits séparés (3575959 P2 meta, 60030d3 fixes, e5fe71c docs, d84c53a R4, 905202b R5, e8fc0c6 R6).

---

## 2026-06-05 — WAVE 8 : re-dérivation ML indépendante depuis data_anon.csv → v3

### Why
Demande explicite : reprendre la modélisation ML « à zéro » depuis `data_anon.csv` pour comparer ma méthodologie à celle du notebook/`train.py`, apprendre des divergences, et maximiser la valeur prédictive du dashboard. Décisions cadrées : full takeover, les 7 modèles, cible identique + variante forward-looking.

### What changed
- **Phase A/B (audit + validation honnête)** — `machine_learning/analysis/01_audit.py`, `02_validate.py`. Trois découvertes : (1) **30.7% des lignes sont des doublons de chanson** (`NameID`, un titre = 22 snapshots) → un split aléatoire fuite → bascule en **StratifiedGroupKFold par chanson** ; l'inflation reste modeste (~0.02 AUC) → **les AUC de v2 tiennent**. (2) **SMOTE nuit** légèrement (RR AP 0.80→0.74) → supprimé. (3) calibration Platt ajustée sur le **test split** (optimiste) → v3 l'ajuste **hors-fold (OOF)**.
- **Phase C (modèles v3)** — `03_train.py` → `machine_learning/models/v3/`. Bilan régresseurs en group-CV : **tous faibles** (DW R²<0, RR 0.23, Radio 0.33 cible log) — la cible brute donnait R²<0, passage à **log1p** (l'inférence applique `expm1`). Constat clé : retirer les 2 features jamais servies (`NonAlgoStreams28Days`, `RadioCount`) coûte **≤0.004 AUC** — le skew train/serve est gratuit à supprimer ; **mais l'utilisateur a choisi de garder les 13 features** (revisite en Phase 2), donc v3 ré-entraîné sur 13.
- **Phase D (forward-looking)** — `04_forecast_variant.py` : **RR = vraie prévision** (AUC 0.92 à partir des seules métadonnées de sortie, sans aucun stream), **DW = modèle de leviers** (saves + playlist-adds), **Radio = diagnostic de momentum** (s'effondre sans streams concurrents). Recadrage produit majeur.
- **Phase E** — `machine_learning/COMPARISON_REPORT.md` (document pédagogique : table de diff méthodo, accords/désaccords chiffrés, recommandations classées).
- **Phase F (ship)** — `ml_inference.py` : `MODEL_VERSION="v3"`, `_volume_forecast` (expm1), **DW volume supprimé** (R²<0). `algo_knowledge.py` : `ALGO_MODEL_METRICS` recalculés en group-CV OOF + `auc_ci` (bande 95%), `ALGO_REGRESSOR_METRICS` honnêtes (DW+RR `volume_reliable:False`, Radio plancher R²=0.33), **`ALGO_CALIBRATION_BANDS` RR+RADIO peuplées** (mesurées empiriquement, `05_calibration_bands.py` — clôt l'item ouvert), copies d'interprétation par algo (§5). `ml_widgets.py` : bande de confiance AUC dans la scorecard. `_common.py` : badges calibration DW/RR/RADIO + note de suppression DW. `revenue_forecast.py` + `_common.py` : libellés AUC/version rafraîchis.
- **Calibration v3 bien calibrée** : la plupart des bandes lisent « fiable : score ≈ réalité » (gros gain d'honnêteté vs les avertissements de sur-confiance de v1).

### Tests
`PYTHONPATH=. python3 -m pytest tests/ -q` → **300 passed, 37 skipped** (render-smoke skip = pas de DB locale). `ruff check` clean. Baseline ML régénérée pour v3 (`tests/fixtures/ml_scoring_baseline.json`, DW volume = None) ; `test_ml_inference` + `test_algo_knowledge` mis à jour pour le comportement v3. **Note :** garder 13 features = le skew NonAlgoStreams/RadioCount demeure → la donnée live Phase 2 reste prioritaire (l'UI conserve le caveat d'imputation).

---

## 2026-06-05 (suite) — WAVE 8 part 2 : les découvertes v3 deviennent des features

### Why
Suite logique de la re-dérivation : transformer les *découvertes* du `COMPARISON_REPORT.md` §5 en vraies features de l'app, et router le reste en roadmap. Décision utilisateur : 4 features maintenant, estimateur RR en calculateur éphémère.

### What changed
- **(A) Estimateur Release Radar pré-sortie** — la découverte phare (RR prédictible avant la moindre écoute). Nouveau modèle métadonnées-seules `models/v3/rr_premiere_classifier.ubj` + `premiere.json` (`analysis/07_train_premiere.py`, **AUC 0.923 [0.88–0.96]** group-CV, OOF-Platt). `ml_inference.estimate_rr_prerelease(followers, jours, catalogue, cadence, discovery)`. Widget éphémère `ml_widgets.render_prerelease_rr_estimator()` (inputs + courbe P(RR) sur J0–J40, pic d'éligibilité) dans un expander de l'onglet Algos — aucune écriture DB. Bonus : le modèle confirme que Discovery Mode n'influence PAS RR (effet plat).
- **(B) ROI espéré (onglet Budget)** — `_tab_budget_roi._render_expected_value()` : coût-par-trigger existant ÷ **P(déclenchement) calibrée** = coût ajusté au risque + « meilleur pari ». Honnête (valeur espérée, pas promesse), gaté par `calibration_note`. Réutilise `_TRIGGER_STREAM_TARGETS` + `_load_ml_pred`.
- **(C) Validation PI en group-CV** — `analysis/08_validate_pi.py` : **R²=0.923 [0.88–0.94], MAE 2.0 pts** par GroupKFold/NameID → le PI est *réellement* robuste (pas optimiste). Écrit dans `metrics.json` (bloc `pi`) + texte d'aide UI corrigé (était « non revalidé »).
- **(D) Couverture Discovery Mode** — `build_features` estampille `discovery_mode_known` (ligne `s4a_song_discovery_mode` présente ou non). `_show_imputation_caveat` distingue un vrai opt-out d'un 0-par-défaut : si inconnu → invite de saisie (Vue Globale), si connu → « donnée réelle ». `MODEL_PATHS` passe à 8 modèles.
- **Roadmap** — 5 items P4 ajoutés : leviers DW quantifiés (sensibilité locale), re-seed lifecycle (conditionner sur titres déclencheurs), capture live par algo (Phase 2), éval per-tenant + ré-entraînement, passage au contrat 11 features.

### Tests
`PYTHONPATH=. python3 -m pytest tests/ -q` → **302 passed** (+2 tests estimateur RR : intervalle [0,1] sur la fenêtre + Discovery Mode plat). `ruff check src/ tests/ machine_learning/analysis/` clean. Widget estimateur vérifié headless via AppTest (rend sans DB, « Pic d'éligibilité J+23 »). **À déployer comme v2 :** `git add machine_learning/models/v3/` (modèles non commités, non-gitignorés) + relancer `ml_scoring_daily` pour repeupler `ml_song_predictions` en v3.

---

## 2026-06-05 (suite 2) — Roadmap : items actionnables traités + déduplication

### Why
« Fais tout » sur le listing roadmap : traiter les 2 items réellement actionnables (leviers DW quantifiés, re-seed lifecycle) et nettoyer les doublons que mes ajouts WAVE 8 avaient introduits. Le reste (Phase 2, per-tenant, RR volume, 11-feat, resurrection) est génuinement bloqué sur de la donnée live → reste en roadmap.

### What changed
- **Leviers DW quantifiés (sensibilité locale)** — `ml_inference.local_sensitivity(algo, feature, feats)` : balaye UN levier du titre courant (borne haute = moyenne+3σ pour la résolution), recalcule la proba calibrée. `ml_widgets.render_lever_sensitivity()` : selectbox du levier + courbe P(DW) + gain marginal vers la cible (« de X à cible Y : P 11% → 24% »). Câblé dans l'onglet Explainabilité (DW uniquement = le modèle de leviers). Captionné **sensibilité *locale*, pas une règle globale** (modèle non-linéaire). Vérifié : saves 0→3000 → P(DW) 11%→24% puis plateau (rendements décroissants honnêtes).
- **Re-seed benchmark lifecycle (conditionné)** — `export_lifecycle_benchmark.py` conditionne désormais sur la **cohorte déclencheuse** (DW>137/RR>130/Radio>639, min 5 titres/bin) : les médianes DW ne sont plus écrasées à 0 et `total_stream_median` est peuplé (était NULL). `migrations/041_lifecycle_benchmark_v2.sql` (`dataset_version='v2'`). Loader `_load_lifecycle_benchmark` par défaut v2 avec **fallback v1** (zéro régression avant `make migrate`). Changement sémantique assumé : la courbe lit « parmi les titres qui ONT déclenché » ; RR ne couvre que 0–10 sem (il déclenche près de la sortie). **Nécessite `make migrate`.**
- **Dédup roadmap** — 12 lignes ouvertes → ~6 sujets distincts. Les 2 items ci-dessus passés `[x]` ; ancien item « seed provisoire » marqué fait (→ 041) ; doublons Phase-2 (352) réduits en cross-ref vers l'entrée canonique (429) ; doublons per-tenant supprimés de la section WAVE 8 (déjà dans « Long-term ML hardening ») ; R² du régresseur RV RR corrigé (≈0.55 → 0.23 honnête v3).

### Tests
`PYTHONPATH=. python3 -m pytest tests/ -q` → **302 passed**. `ruff check src/ tests/ machine_learning/` clean. `render_lever_sensitivity` vérifié headless (AppTest, selectbox OK). Export lifecycle v2 régénéré et vérifié (médianes non nulles, RR limité aux bins précoces). **À appliquer :** `make migrate` (migration 041) pour activer le benchmark v2 en prod.

### Déploiement (2026-06-05, exécuté)
- Commit `76ace9b` (tout le workstream ML v3 + features ; pre-commit hooks verts).
- Stack démarrée (`docker-compose up -d`) ; `make migrate` appliqué → **benchmark lifecycle v2 LIVE** (14 lignes `dataset_version='v2'`, toutes avec `total_stream_median` peuplé, vs v1 0/18). Le loader sert maintenant v2.
- Conteneur Airflow vérifié : `MODEL_VERSION=v3`, 8 modèles montés (dont `rr_premiere_classifier.ubj`). `score_song` + `estimate_rr_prerelease` produisent la bonne sortie v3 in-container (DW volume `None`, RR/Radio via expm1, estimateur OK).
- `ml_scoring_daily` dépausé + déclenché → **success**, mais **0 ligne écrite** : les streams s'arrêtent au **2026-03-29** (>35 j avant le 2026-06-05) → aucun titre « actif » (fenêtre `CURRENT_DATE-35`). **Pas un bug** : les prédictions v3 se peupleront automatiquement dès qu'une collecte S4A fraîche aura lieu (le dashboard montre encore les 22 lignes v1_noscaler de 2026-04-03 d'ici là). Non trafiqué (forcer l'horloge donnerait des features à zéro).

---

## 2026-06-11 — Contrat 11-feat résolu « servir en live » + re-scoring sur données fraîches

### Why
Revue P4 : l'utilisateur a saisi manuellement les features ex-imputées et uploadé un CSV S4A récent → « on a tout, non ? ». Distinction clé clarifiée : la saisie ferme le gap des **features d'entrée**, pas celui du **volume/outcomes accumulés dans le temps**. Vérification live puis nettoyage de cohérence pour que l'UI cesse d'afficher « imputé » sur de vraies données.

### What changed
- **Vérification live (Postgres + Airflow MCP)** — streams frais au **2026-06-06** (CSV 3 j, 11 titres actifs dans la fenêtre `CURRENT_DATE-35`) ; saisies présentes (NonAlgo ×11, Radio=0 *volontaire*, Discovery ×22 opt-out) ; `ml_inference.build_features` **lit déjà** ces saisies (valeurs non-nulles dans `features_json` du run v3 du 2026-06-09). Le pipeline était donc fonctionnel — pas bloqué.
- **Drapeaux `*_known` (un-impute conditionnel)** — `build_features` estampille désormais `nonalgo_known` / `radio_known` (2 helpers `_has_nonalgo_entry` / `_has_radio_entry`), en miroir de `discovery_mode_known` (WAVE 8 part 2). **Un 0 saisi (tes 0 en Radio) ≠ un 0 d'absence.**
- **Helper centralisé** — `algo_knowledge.feature_live_available(spec, feats)` + map `_MANUAL_KNOWN_FLAG` (json_key → drapeau) : une feature `live_unavailable` à source manuelle redevient *live* dès qu'elle est saisie. Câblé dans `ml_widgets._live_value`, le filtre des leviers, et `build_coach_actions`.
- **UI dé-mensongée** — `_show_imputation_caveat` retire NonAlgo/Radio de l'avertissement « X/13 imputées » quand saisis + ligne « ✅ Saisies S4A prises en compte » ; légende du bloc volume réécrite (plus de « jusqu'à la Phase 2 »). Catalogues EN alignés (`manual_entered` ajouté, `volume_imputed` réécrit). Prose `COMPARISON_REPORT.md` item 7 → « partly closed (mig 052) ». Docstring `ml_inference` corrigée.
- **Roadmap** — item 11-feat coché « RESOLVED by serving live » ; les 4 items ML restants recadrés explicitement **TIME-ACCRUAL-blocked** (pas input-blocked) : per-tenant (nb tenants), retrain (outcomes forward), RR regressor (volume d'entraînement, pas serving), resurrection (historique saves longitudinal).

### Tests
`PYTHONPATH=. pytest tests/ -q` → **444 passed, 2 skipped** (render-smoke `trigger_algo` exercé en live sur la DB). ruff clean. +9 tests (`test_ml_inference.py` : helpers `*_known` + `TestFeatureLiveAvailable`). Le baseline ML n'est pas touché (il ne stocke que probas/forecasts, pas `features_json` ; les 13 features modèle sont inchangées).

### Exécuté
- `ml_scoring_daily` re-déclenché 2× via Airflow CLI → **success** ; le 2e run (post-edits, `src/` monté) a **persisté `nonalgo_known=radio_known=dm_known=true` sur les 11 titres** (vérifié en DB). Prédictions v3 fraîches reflétant tes saisies (NonAlgo réels, Radio=0, Discovery opt-out).
- 7 fichiers : `ml_inference.py`, `algo_knowledge.py`, `ml_widgets.py`, `_explain.py`, `i18n_catalog/{trigger_algo,ml_widgets}.py`, `COMPARISON_REPORT.md`, `test_ml_inference.py` (+ roadmap + DEVLOG).

---

## 2026-06-11 (suite) — Benchmark déploiement consolidé (C5/C6) + décisions infra figées + build ARM64

### Why
Les réponses cross-projets (IA MT5 + IA n8n/vidéo) sont arrivées. Objectif : les **consolider avec
le profil streaMLytics**, **trancher la topologie + le VPS + le domaine**, et **dérisquer le choix
ARM64** avant d'acheter quoi que ce soit. Process d'achat prévu demain (2026-06-12).

### What changed (docs only — aucune modif de code applicatif)
- **Synthèse consolidée** — `NEW .claude/dev-docs/benchmark-deployment-synthesis.md` (11 §) : profils
  ressources idle/pic des 3 charges (streaMLytics + n8n/vidéo + MT5), schéma de topologie, levier #1
  (rendu vidéo local vs délégué + table VRAM par modèle open + arbre de décision GPU), workflows
  tolérant un PC non-24/7 (critère = type de *trigger*), budget €/mois, risques (bans/monétisation >
  infra), plan d'action, table des décisions.
- **Décisions FIGÉES** (après questions à l'utilisateur) :
  - **Topologie split** : **Box A** Linux always-on (streaMLytics maintenant ; n8n + ffmpeg plus tard,
    même box) + **Box B** Windows isolée (MT5 live 24/7) + **GPU vidéo serverless pay-per-call**
    (aucun GPU acheté/loué) + **proxy résidentiel** pour isoler l'IP de scraping.
  - **VPS = Hetzner CAX31** (ARM Ampere, 8 vCPU / 16 Go / 160 Go NVMe, ~12,50 €/mo). Cible **10-50
    artistes**. 16 Go absorbe streaMLytics seul ET le pic combiné futur → resize CAX41 32 Go seulement
    >50 tenants. **Différence de budget « streaMLytics seul vs +n8n d'emblée » ≈ 0 €** (Hetzner resize
    vertical ~2 min, même disque). **Fallback x86 CPX31** (même prix) si un wheel manque en aarch64.
  - **Domaine = `streamlytics.fr`** chez **OVH** (vérif RDAP live : `.com` **pris/parké** depuis 2017
    GoDaddy ; `.app` **libre** en backup). Registrar OVH (boîte email gratuite incluse).
  - **Email** : **envoi reste sur SMTP Gmail (inchangé)** ; `contact@` = boîte gratuite OVH /
    Cloudflare Email Routing. Email de domaine = crédibilité, **pas un prérequis Stripe**.
  - **TLS Caddy** (`app.`/`api.streamlytics.fr`) ; **backup** `pg_dump` → Cloudflare R2 gratuit.
  - **Total streaMLytics ≈ 13 €/mois tout compris.**
- **Roadmap** (`checklist.md`) : C5 + C6 réécrits « DÉCISION FIGÉE » avec les choix concrets + prérequis
  ARM64 + restants ouverts (mesure Mo/session, réservation domaine).
- **`deployment.md`** : nouvelle section **D-1 — Provisioning infra (runbook 2026-06-12)** = ordre
  d'exécution copier-coller (OVH → Hetzner → DNS → D0 hardening → D1 deploy → Caddy → backup → Box B →
  smoke prod) + table des décisions + bloquant ARM64. Pré-requis C5 mis à jour.
- **`benchmark-deployment.md`** § M : marqué « réponses collectées ✅ → voir la synthèse ».
- **Mémoire** : `project_deployment_questions` réécrit « TRANCHÉ » + index.

### Build ARM64 (dérisquage CAX31)
- `docker buildx --platform linux/arm64` (QEMU emulation, WSL2 x86) sur `Dockerfile` (dashboard — le
  plus risqué : pandas/numpy/xgboost/scikit-learn/scikit-image/shap/lime/weasyprint/numba/llvmlite/
  matplotlib/streamlit/apache-airflow). **VERDICT = CAX31 VALIDÉ ✅ — build complet EXIT 0.** Image
  dashboard `linux/arm64` buildée intégralement : `Successfully installed` ~200 paquets en aarch64
  (numpy-1.26.4, pandas-2.3.3, xgboost-3.2.0, scikit-learn-1.9.0, scikit-image-0.26.0, shap-0.49.1,
  lime-0.2.0.1 (compilé depuis les sources), numba-0.65.1, llvmlite-0.47.0, weasyprint-69.0,
  matplotlib-3.10.9, streamlit-1.57.0, apache-airflow-3.2.2…). **Zéro `No matching distribution`**,
  zéro erreur — seul un warning cosmétique `JSONArgsRecommended` sur le `CMD` (Dockerfile l.43, lint).
  Le `pip install` a pris ~107 min **sous émulation QEMU x86→ARM** (artefact local ; natif ARM = rapide)
  → le fallback x86 CPX31 n'est PAS nécessaire. Builder buildx nettoyé en fin de session. Possibilité
  future : build multi-arch `docker buildx --push` depuis la CI.

### À faire demain (2026-06-12)
Exécuter le runbook **D-1** de `deployment.md`. Repoussé (pas demain) : activation Stripe (Phase D),
n8n + génération vidéo (serverless), proxies scraping.

---

## 2026-06-12 — Premier vrai import DistroKid (compte ami) + persistance du taux FX (P2)

### Why
Un pote a prêté son compte DistroKid → premier export réel pour exercer le pipeline DistroKid de bout
en bout (jusqu'ici testé sur fixtures uniquement), puis fermer le ship-blocker P2 « taux FX non
ré-auditable » tant qu'on y était.

### What changed
- **Validation live du pipeline sur un vrai export** — `DistroKid_*.tsv` (artiste « Benken », 331 lignes,
  14 stores, 2025-09 → 2026-04, 9,68 USD). Import test sous `artist_id=1` via le code path du DAG
  (parse → `upsert_many` → rollup) → 331 lignes + 8 mois EUR, **puis purgé** (data jetable, tenant=moi).
  L'intégration réelle de Benken attendra le déploiement (tenant dédié). Découvertes réinjectées dans la
  doc (commit docs séparé) : fins de ligne **CR-seul** gérées par pandas, layout 15 colonnes pouvant
  garder le nom legacy `Song/Album`, libellés UI **FR** (Banque → « Voir dans le moindre détail »).
- **P2 — `fx_rate` persisté** (`migrations/059_distrokid_fx_rate.sql`) — `distrokid_monthly_revenue`
  gagne `fx_rate NUMERIC(8,5)` : NULL pour les saisies manuelles EUR, renseigné pour les imports.
  `distrokid_rollup.py` l'écrit (INSERT + ON CONFLICT UPDATE ; 3 placeholders de taux : calcul EUR,
  colonne, prose `notes`). `revenue_eur` redevient **réversible** (`/ fx_rate`) — avant, le 0.92 par
  défaut était cuit irréversiblement, ~8 % d'erreur non ré-auditable. Schéma canonique
  (`distrokid_schema.py` + `init_db.sql`) aligné pour les fresh installs.

### Tests
`pytest tests/ -q` → **545 passed** (ruff clean). +3 tests DB-free (`test_distrokid_revenue.py` :
SQL contient `fx_rate`, arité des params, défaut). 1 test existant mis à jour (`test_distrokid_parser.py`
`TestRollup` : arité 2→3 taux). Vérif live : synthetic $10 @ 0.85 → 8,50 € → reverse 10,00 $, puis cleanup.
Migration 059 appliquée sur la DB live.

### Non fait (volontaire)
- **Postgres-en-CI** (P3) : le retrait du service Postgres a été décidé HIER (2026-06-11) avec une
  raison documentée (jamais provisionné → tests skip → flake Docker Hub). Le ré-ajouter *correctement
  provisionné* (init_db + migrations) est l'item roadmap, mais ça inverse une décision same-day → laissé
  à un changement dédié et revu, pas auto-rammé.
- **API `/ml/predictions`** (P4) : redesign de contrat (renvoyer probas vs calculer un score) = décision
  produit, pas une correction mécanique → laissé à l'utilisateur.

---

## 2026-06-12 (suite) — Boucle d'outcome-labelling ML (item #2a) : prédictions → labels d'entraînement

### Why
Suite à la question « quels items ML sont les plus pertinents long terme » : le levier #1 est la
**boucle qui génère la donnée** dont tous les autres dépendent. L'exploration a révélé une contrainte
pivot : les vrais streams DW/RR/Radio **n'existent pas automatiquement** (S4A n'expose pas le split par
source — ADR-004 = saisie manuelle ; les labels d'entraînement v3 venaient d'un questionnaire one-shot
`data_anon.csv`). Donc « la jointure » n'était pas le vrai manque — c'était la **surface de capture** des
outcomes réalisés + la jointure. Choix utilisateur : construire backend **+** saisie S4A maintenant.

### What changed
- **2 tables** (`migrations/060_ml_outcome_labeling.sql` + `init_db.sql` + `ml_schema.py` + allowlist) :
  - `s4a_song_algo_outcomes` — capture manuelle des streams DW/RR/Radio 28j réalisés par titre (snapshot
    daté, dernier `recorded_at` gagne ; calque `s4a_song_nonalgo_streams`).
  - `ml_prediction_outcomes` — paires d'entraînement (prédiction ↔ outcome réalisé ↔ label binaire),
    FK `ml_song_predictions(id)`, UNIQUE sur `prediction_id`.
- **Moteur pur** `src/utils/ml_outcome_labeling.py` : `bin_label` (seuils d'entraînement 137/130/639,
  `> strict`, miroir `train.py:45`), `match_outcome` (snapshot le plus précoce ≥28j après la prédiction
  → fenêtre 28j complète), `label_predictions` (jointure idempotente, LEFT JOIN sur les déjà-labellisés).
- **DAG hebdo** `ml_outcome_labeling` (lundi 06:00 UTC, `max_active_runs=1`, retries, failure callback)
  + `debug_ml_outcome_labeling.py` (dry-run / `--write`).
- **Saisie S4A** : 3ᵉ grille « 🎯 Streams algorithmiques réalisés (28j) » = la surface de capture (how-to
  « où lire DW/RR/Radio dans S4A », saisir ~4 semaines après pour une fenêtre honnête). +7 clés i18n EN.

### Tests
`pytest tests/ -q` → **555 passed** (+10 : `test_ml_outcome_labeling.py` — `bin_label` bornes, `match_outcome`
sélection, `label_predictions` sur fake-db). ruff `src/ tests/` clean. **Vérif live** : prédiction
synthétique J-40 + outcome J-10 (DW 500 / RR 50 / Radio 700) → label `(1,0,1)`, horizon 30, FK OK,
**re-run = 0** (idempotent), puis cleanup. Migration 060 appliquée live ; DAG **parse in-container sans
erreur d'import** (DagBag). Render-smoke de `saisie_s4a` (grille ajoutée) vert.

### État
La moitié **input** de #2 est fermée : les labels s'accumulent dès que tu saisis des outcomes réalisés.
Reste **bloqué** (forward time + volume de saisies) : le DAG champion/challenger de **retraining** qui
consommera `ml_prediction_outcomes` — à construire quand assez de cycles auront accumulé des paires.

### Annexe (bug latent repéré, non touché)
`saisie_s4a._save_fixed` liste `collected_at` dans `update_columns` sans le passer dans les rows → sur un
**2ᵉ enregistrement le même jour**, `EXCLUDED.collected_at` réfère une colonne absente de l'INSERT →
erreur. Latent (1er save = INSERT OK ; non couvert par render-smoke qui ne déclenche pas le bouton).
P3, signalé puis **CORRIGÉ** (à la demande de l'utilisateur, commit suivant) : `collected_at` retiré des
`update_columns` des 5 upserts de `saisie_s4a` (`_save_fixed` ×4 + `_render_custom_grid` ×1). Vérifié live
(2 sauvegardes le même jour → la 2ᵉ écrase sans crash). Mon nouveau code l'omettait déjà.
