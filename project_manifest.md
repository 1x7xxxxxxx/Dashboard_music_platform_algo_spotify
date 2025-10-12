# MVP Project Tracking Manifest

**Projet**: Streamlit - Agrégation & Analyse de données musicales (MVP)

**But**: Document de suivi des scripts, fonctions, variables, organisation GitHub, objectifs, commentaires, et tâches associées au projet. Fichier pensé pour être maintenu en racine du repo (`docs/` ou `/project_manifest.md`).

---

## Comment utiliser ce document

- Chaque script ou module du projet doit avoir une entrée dans la section **Catalogue des scripts**.
- Pour chaque fonction importante, remplir la sous-section `Fonctions` avec son objectif, ses entrées/sorties, variables globales utilisées et tests associés.
- Mettre à jour `Statut` et `Owner` lors de changements.
- Ce document servira de source pour la génération automatique minimale de docs et pour les revues PR.

---

## Sommaire / Arborescence suggérée du repo

```
/ (repo root)
├─ src/
│  ├─ etl/
│  │  ├─ spotify_api.py
│  │  ├─ spotify_selenium.py
│  │  ├─ hypeddit_scraper.py
│  │  ├─ airflow_dags/
│  │  │  └─ dags.py
│  │  └─ transforms.py
│  ├─ db/
│  │  ├─ postgres.py
│  │  └─ models.py
│  ├─ ml/
│  │  ├─ model.py
│  │  └─ explainability.py
│  ├─ api/
│  │  └─ llm_adapter.py
│  └─ streamlit_app/
│     ├─ pages/
│     └─ ui_components.py
├─ tests/
├─ docker/
├─ infra/
│  ├─ docker-compose.yml
│  └─ airflow/
├─ .github/workflows/ci.yml
├─ README.md
├─ config.yaml
└─ project_manifest.md (this document)
```

---

## Catalogue des scripts (template)

> **Nom fichier**: `chemin/vers/fichier.py`  
> **But / responsabilité**: Description courte et précise.  
> **Entrées**: paramètres d'appel + variables d'environnement requises  
> **Sorties**: fichiers/DB/tables/retours API  
> **Fonctions clés**:
>
> - `fonction_x(param1, param2)` — *Objectif*: ...  
>   - Entrées:  
>   - Sorties:  
>   - Variables globales lues/écrites:  
>   - Exceptions attendues:  
>   - Tests unitaires: référence `tests/test_fichier.py::test_fonction_x`
>
> **Variables importantes**: lister variables globales, noms de tables, colonnes  
> **Schéma DB associé**: table(s) et colonnes impactées  
> **Owner**: @github_user / équipe  
> **Statut**: `idea` / `dev` / `review` / `done`  
> **Commentaires / Notes**: conseils d'implémentation, contraintes (ex: rate limit API)


### Exemple rempli — `src/etl/spotify_api.py`

- **But**: Collecter les métriques journalières Spotify par artiste/release via l'API Web de Spotify (MVP: prioriser endpoint `streams` ou équivalent, requêtes journalières).
- **Entrées**: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `ARTIST_ID`, `RELEASE_ID`, `date` (optionnel)
- **Sorties**: Insert en base `spotify_streams_daily(artist_id, release_id, date, streams, saves, playlist_adds, listeners)`
- **Fonctions clés**:
  - `get_spotify_token()` — *Objectif*: Récupère access token via Client Credentials. Entrées: client_id, secret. Sortie: token (str). Exceptions: échec auth -> raise `AuthError`.
  - `fetch_release_metrics(release_id, date_from, date_to)` — *Objectif*: Récupère métriques agrégées par jour. Entrées: ids, période. Sortie: list[dict] journaliers.
  - `store_metrics_to_db(records: List[dict])` — *Objectif*: Upsert en PostgreSQL. Doit valider via Pydantic le schéma avant insert.
- **Variables importantes**: `SPOTIFY_API_RATE_LIMIT=100` (exemple)
- **Schéma DB associé**: table `spotify_streams_daily` (voir section Schéma DB)
- **Owner**: data_engineer
- **Statut**: dev
- **Tests unitaires**: `tests/test_spotify_api.py` (mock responses + token expired)

---

## Schéma de base de données (essentiel pour MVP)

### Tables principales

1. `artists`  
   - `artist_id` (pk), `name`, `spotify_id`, `apple_id`, `youtube_channel`, `created_at`

2. `releases`  
   - `release_id` (pk), `artist_id` (fk), `title`, `release_date`, `platform_ids` (json), `created_at`

3. `spotify_streams_daily`  
   - `id`, `artist_id` (fk), `release_id` (fk), `date` (date), `streams` (int), `saves` (int), `playlist_adds` (int), `listeners` (int), `source` (text), `last_updated` (timestamptz)

4. `marketing_hypeddit`  
   - `id`, `campaign_id`, `date`, `visits`, `clicks`, `landing_url`, `last_updated`

5. `meta_ads_campaigns`  
   - `id`, `campaign_name`, `date`, `budget_spent`, `conversions`, `clicks`, `cpr`, `last_updated`

6. `etl_runs`  
   - `id`, `dag_id`, `run_date`, `status` (`success`/`failed`), `duration_seconds`, `invalid_records_pct`, `anomalies_pct`, `last_alert_delay_seconds`

7. `ml_predictions`  
   - `id`, `release_id`, `date`, `pred_trigger_rr` (float), `pred_trigger_dw` (float), `explainability` (json, SHAP summary), `model_version`

> Indexez `date` et `(artist_id, release_id, date)` pour des lectures rapides.

---

## Conventions de nommage et variables importantes

- Modules: `snake_case` (ex: `spotify_api.py`)  
- Fonctions: `snake_case`  
- Classes: `PascalCase`  
- Tables SQL: `snake_case_plural` (ex: `spotify_streams_daily`)  
- Environment variables: `UPPER_SNAKE_CASE`  

Variables de config (dans `config.yaml`):

```yaml
spotify:
  client_id: ""
  client_secret: ""
  rate_limit: 100
postgres:
  host: localhost
  port: 5432
  user: app_user
  db: music_insights
alerts:
  smtp_server: ""
  from: "alerts@example.com"
  to: ["you@example.com"]
airflow:
  dags_folder: ./infra/airflow/dags
```

---

## Airflow & ETL

- DAGs: écrire un DAG principal `daily_ingest` qui orchestre les tâches:  
  1. `start`  
  2. `spotify_fetch` (parallel: par artiste)  
  3. `hypeddit_fetch`  
  4. `transform_validate` (Pydantic validation + rules)  
  5. `store_db`  
  6. `ml_predict` (optionnel: post-ingest)  
  7. `notify` (si erreurs/anomalies)

- Chaque tâche doit explicitement logger le nombre d'enregistrements traités, durée, et éventuelles erreurs.
- Exposer métriques Prometheus (ou exporter minimal) pour le dashboard ETL.

---

## ML — MVP

- `src/ml/model.py`: modèle simple (ex: Logistic Regression ou LightGBM avec features agrégées sur 7/30/90 jours).
- `explainability.py`: wrapper SHAP pour produire un résumé agrégé (top features) stocké dans `ml_predictions.explainability`.
- Pipeline: features builder -> train/test split (time-based) -> train -> persist model (versionné) -> inference batch quotidien -> store predictions

---

## Monitoring & Alerting

- Alerts par email (SMTP) dans un premier temps, basé sur règles:
  - échec DAG complet ou > 50% tasks failed
  - chute de streams > 50% vs jour précédent ou vs same-day last-week
  - % invalid records > 5%
- Logs: centraliser dans fichiers rotatifs + possibilité d'envoyer erreurs critiques à Sentry.

---

## CI / CD

- GitHub Actions:
  - `ci.yml`: tests unitaires (pytest), linters (black, flake8, pylint), static type check (mypy)
  - `cd.yml`: build docker image + push (optionnel) + déploy Streamlit app (Heroku / DigitalOcean / VPS / Docker Compose)
- Pre-commit hooks: black, isort, flake8, mypy

---

## Tests & Qualité

- Tests unitaires par module dans `tests/`.
- Fixtures pour responses API (vcrpy ou requests-mock).
- Coverage cible initiale: 70%.

---

## Sections à remplir / Priorités (Roadmap MVP)

1. **ETL Spotify (critique)**: endpoints, stockage streaming par jour, Selenium pour CSV artistes (4), webscraping Hypeddit.
2. **DB & Docker**: docker-compose + Postgres local + migrations (alembic).
3. **Airflow DAGs**: daily_ingest
4. **Validation**: Pydantic models + règles métier (streams>0, date format)
5. **Monitoring**: ETL metrics, alerts email
6. **ML simple**: baseline model + SHAP
7. **Streamlit**: Dashboard KPI bloc 1..5 (simpler UI pour MVP)

---

## Template d'entrée (pour chaque nouveau script à ajouter dans ce document)

```
- Nom fichier:
  - But:
  - Entrées:
  - Sorties:
  - Fonctions:
    - name(args): purpose, inputs, outputs, exceptions, tests
  - Variables:
  - Schéma DB:
  - Owner:
  - Statut:
  - Notes:
```

---

## Checklist de revue PR (à inclure dans CONTRIBUTING.md)

- [ ] Tests ajoutés/ok
- [ ] Linter ok (black, flake8)
- [ ] Type checks mypy passed
- [ ] Docstrings PEP257 présents pour nouvelles fonctions/classes
- [ ] Ajout au `project_manifest.md` si nouveau module/variable importante

---

## Remarques finales / Conseils d'implémentation

- Prioriser la résilience réseau: backoff exponentiel, limites de taux respectées.
- Toujours valider les données via Pydantic avant insertion DB.
- Versionner le schéma DB et les modèles ML.
- Loggez les identifiants d'artist/release dans les logs au niveau debug, mais ne stockez jamais de secrets en clair.

---

*Document généré automatiquement — merci de le compléter et le maintenir à jour.*

