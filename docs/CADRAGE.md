# CADRAGE — streamlytics

<!-- cadrage : posé par le master du parc (fleet_apply, T383). Les blocs cadrage:auto sont réécrits
     à chaque apply ; tout le reste s'écrit à la main dans ce dépôt et est gardé. Le master signale
     chaque « à compléter » restant (avis cadrage-incomplete). -->

## 1. Besoin

<!-- cadrage:auto:besoin -->
> README.md : Tous droits réservés — voir [LICENSE](LICENSE). Le code est visible, aucune réutilisation n'est accordée.
<!-- /cadrage:auto:besoin -->

- Problème : un artiste indépendant dépense en publicité Meta sans savoir si ses titres en tirent des écoutes ni s'ils entrent en playlist algorithmique — ses chiffres sont éparpillés entre Spotify for Artists, Meta Ads, Instagram, Hypeddit et Shazam, aucun ne les croise (ADR-025).
- Pour qui : des artistes indépendants qui financent eux-mêmes leur promotion — un locataire par artiste, isolé des autres (multi-tenant, règle 7) ; aujourd'hui un artiste propriétaire et quelques bêta-testeurs invités (`runbook-artist-test-session.md`).
- Critère de succès : l'activation — un artiste invité reçoit ses propres données collectées sans geste de l'administrateur (ADR-028, métrique d'activation `src/utils/activation.py`, R149) ; tant qu'elle n'est pas résolue, ni le prix (plat, ADR-028) ni l'échelle (ADR-030) ne bougent.

## 2. Objectifs et risques

### Objectifs

<!-- cadrage:auto:objectifs -->
| id | objectif | P | Mesuré par |
|---|---|---|---|
| O1 | An artist never sees another artist's rows | P1 | `3 gardes d'isolation des locataires verts (rc = 0)` |
| O2 | The figures an artist reads are right — no silent loss at collection, no S4A total row | P2 | `gardes collecteur-lève et ligne Total filtrée verts (rc = 0)` |
| O3 | Every requirement has its probe | P2 | `0 domaine orphelin (arch_benchmark --coverage --check)` |
| O4 | Nothing ships on a red suite | P2 | `0 ligne FAILED ou ERROR dans .pytest-last.log` |
<!-- /cadrage:auto:objectifs -->

### Analyse de risques

<!-- cadrage:auto:risques -->
Aucun fait de risque détecté par l'outil.
<!-- /cadrage:auto:risques -->

Probabilité et impact de 1 (faible) à 3 (fort) ; criticité = probabilité × impact. Traitement : réduire, accepter, transférer, éviter ;
résiduel = probabilité × impact une fois la mitigation en place (« réduire » le baisse, « accepter » le garde).

| risque | objectif | composant | probabilité | impact | criticité | mitigation | traitement | résiduel | sonde |
|---|---|---|---|---|---|---|---|---|---|
| Identité de locataire illisible ⇒ données de l'admin montrées à un artiste (2 tests artiste ratés, 2026-08-21) | O1 | dashboard Streamlit (`view_session`) | 2 | 3 | 6 | `view_session()` sans repli sur l'artiste 1 + gardes d'isolation des vues or | réduire | 3 | `.venv/bin/python -m pytest -q tests/test_a_gold_view_is_blind_to_another_tenants_rows.py tests/test_a_tenant_flag_is_applied_everywhere.py` |
| Collecteur qui avale une erreur d'API et finit SUCCESS sur 0 ligne | O2 | collecteurs Python + DAG Airflow | 2 | 2 | 4 | règle 6 (un `except` relève) + hook `collector-audit` au commit + alerte `stale` d'`etl_run_log` | réduire | 2 | `.venv/bin/python -m pytest -q tests/test_the_collector_audit_sees_a_silent_return.py` |
| Ligne « Total » des CSV S4A comptée comme un titre | O2 | PostgreSQL `s4a_song_timeline` | 2 | 2 | 4 | filtre `ARTIST_NAME_FILTER` obligatoire sur chaque requête + garde | réduire | 2 | `.venv/bin/python -m pytest -q tests/test_the_total_row_is_always_filtered_out.py` |
| Serveur unique coupé (impayé Hetzner, ~10 h le 2026-09-24) ⇒ nuits de collecte perdues | O2 | VPS Hetzner CPX32 + docker compose | 1 | 3 | 3 | contrôle de santé externe chaque matin + sauvegarde hors-site chiffrée (R57) | accepter | 3 | `gh run list --workflow prod-health.yml --limit 1` |
| Livraison sur une suite rouge | O4 | GitHub Actions `ci.yml` + porte pre-push (R444) | 2 | 2 | 4 | tampon vert de `make test-changed` exigé au push, CI attendue avant `make roadmap-close` (R268) | réduire | 2 | `make test-verdict` |
| Exigence du catalogue sans preuve rejouable | O3 | `.claude/dev-docs/architecture/requirements.yaml` | 1 | 2 | 2 | `make requirements-report` + `arch_benchmark --coverage --check` | réduire | 1 | `.venv/bin/python tools/dev/arch_benchmark.py --coverage --check` |


## 3. Stack

<!-- cadrage:auto:stack -->
Langages (fichiers versionnés) : py (1542), sql (152), sh (22), js (1).

- `Dockerfile` : python:3.11-slim
- `Dockerfile.airflow` : aucune dépendance déclarée
- `Dockerfile.api` : python:3.11-slim
- `pyproject.toml` : python >=3.11, pandas==2.3.3, numpy==1.26.4, psutil>=5.9.0, xgboost>=2.0.0, scikit-learn>=1.3.0, shap>=0.44.0, lime>=0.2.0, facebook-business==18.0.5, spotipy==2.26.0, google-api-python-client==2.200.0, streamlit==1.66.1 …
- `requirements-api.txt` : pandas==2.3.3, numpy==1.26.4, psutil>=5.9.0, fastapi>=0.110.0, uvicorn[standard]>=0.27.0, python-multipart>=0.0.9, PyJWT>=2.15.0, urllib3>=2.8.0  # transitive (requests); floor so the pip-built images get the fix too (R341), passlib[bcrypt]>=1.7.4, bcrypt>=4.0,<4.1, cryptography>=42.0.0, pyotp>=2.9.0 …
- `requirements-dev.txt` : pytest>=8.0.0, pytest-mock>=3.12.0, pytest-cov>=5.0.0, httpx>=0.27.0, ruff==0.16.7
- `requirements.txt` : pandas==2.3.3, psutil>=5.9.0, numpy==1.26.4, xgboost>=2.0.0, scikit-learn>=1.3.0, shap>=0.44.0, lime>=0.2.0, facebook-business==18.0.5, spotipy==2.26.0, google-api-python-client==2.200.0, streamlit==1.66.1, authlib>=1.3.2 …
<!-- /cadrage:auto:stack -->

Compromis (ATAM, Humble & Farley, *Continuous Delivery* p.262) — « scalable » se prouve par un seuil
d'objectif, jamais par ce tableau :

| attribut | choix | alternative écartée | compromis accepté |
|---|---|---|---|
| performance | Streamlit rendu serveur sur des vues or PostgreSQL | front React sur l'API FastAPI | chaque interaction relance le script de la page ; tenu tant que le temps de rendu mesuré reste sous son seuil (ADR-030) |
| disponibilité | un seul VPS Hetzner, docker compose | plusieurs nœuds ou orchestrateur | une panne du VPS coupe le service (2026-09-24, ~10 h) ; l'échelle attend un déclencheur surveillé (ADR-030) |
| coût | VPS unique + GitHub Actions | services managés (base, conteneurs) | l'exploitation (sauvegarde, mises à jour, jetons) reste au propriétaire |
| maintenabilité | un dépôt Python, une base `spotify_etl` | un service par plateforme | un changement de schéma touche collecte, API et dashboard ensemble |

## 4. Déploiement par priorité

<!-- cadrage:auto:deploiement -->
Pas de roadmap (`docs/roadmap/checklist.md` absent) : la méthode ci-dessous dit d'où viennent les priorités.
<!-- /cadrage:auto:deploiement -->

Méthode : P1 sécurité > P2 intégrité des données > P3 UX > P4 dette (règle 4 de `CLAUDE.md`) ; une ligne de roadmap avant tout code (R196), dans `.claude/dev-docs/roadmap/checklist.md` ; une tâche se ferme par `make roadmap-close` une fois sa CI verte (R268).
