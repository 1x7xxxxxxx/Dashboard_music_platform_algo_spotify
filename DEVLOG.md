# DEVLOG — Music Platform Dashboard

Journal de session structuré. Mis à jour en fin de session via :
> "Append today's session summary to DEVLOG.md"

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
