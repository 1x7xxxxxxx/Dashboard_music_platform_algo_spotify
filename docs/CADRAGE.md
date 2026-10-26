# CADRAGE — streamlytics

<!-- cadrage : posé par le master du parc (fleet_apply, T383). Les blocs cadrage:auto sont réécrits
     à chaque apply ; tout le reste s'écrit à la main dans ce dépôt et est gardé. Le master signale
     chaque « à compléter » restant (avis cadrage-incomplete). -->

## 1. Besoin

<!-- cadrage:auto:besoin -->
> README.md : Tous droits réservés — voir [LICENSE](LICENSE). Le code est visible, aucune réutilisation n'est accordée.
<!-- /cadrage:auto:besoin -->

- Problème : à compléter
- Pour qui : à compléter
- Critère de succès : à compléter

## 2. Objectifs et risques

### Objectifs

<!-- cadrage:auto:objectifs -->
| id | objectif | P | Mesuré par |
|---|---|---|---|
| O1 | An artist never sees another artist's rows | P1 | à compléter |
| O2 | The figures an artist reads are right — no silent loss at collection, no S4A total row | P2 | à compléter |
| O3 | Every requirement has its probe | P2 | à compléter |
| O4 | Nothing ships on a red suite | P2 | à compléter |
<!-- /cadrage:auto:objectifs -->

### Analyse de risques

<!-- cadrage:auto:risques -->
Aucun fait de risque détecté par l'outil.
<!-- /cadrage:auto:risques -->

Probabilité et impact de 1 (faible) à 3 (fort) ; criticité = probabilité × impact. Traitement : réduire, accepter, transférer, éviter ;
résiduel = probabilité × impact une fois la mitigation en place (« réduire » le baisse, « accepter » le garde).

| risque | objectif | composant | probabilité | impact | criticité | mitigation | traitement | résiduel | sonde |
|---|---|---|---|---|---|---|---|---|---|


## 3. Stack

<!-- cadrage:auto:stack -->
Langages (fichiers versionnés) : py (1538), sql (152), sh (22), js (1).

- `Dockerfile` : python:3.11-slim
- `Dockerfile.airflow` : aucune dépendance déclarée
- `Dockerfile.api` : python:3.11-slim
- `pyproject.toml` : python >=3.11, pandas==2.3.3, numpy==1.26.4, psutil>=5.9.0, xgboost>=2.0.0, scikit-learn>=1.3.0, shap>=0.44.0, lime>=0.2.0, facebook-business==18.0.5, spotipy==2.26.0, google-api-python-client==2.200.0, streamlit==1.63.0 …
- `requirements-api.txt` : pandas==2.3.3, numpy==1.26.4, psutil>=5.9.0, fastapi>=0.110.0, uvicorn[standard]>=0.27.0, python-multipart>=0.0.9, PyJWT>=2.15.0, urllib3>=2.8.0  # transitive (requests); floor so the pip-built images get the fix too (R341), passlib[bcrypt]>=1.7.4, bcrypt>=4.0,<4.1, cryptography>=42.0.0, pyotp>=2.9.0 …
- `requirements-dev.txt` : pytest>=8.0.0, pytest-mock>=3.12.0, pytest-cov>=5.0.0, httpx>=0.27.0, ruff==0.16.7
- `requirements.txt` : pandas==2.3.3, psutil>=5.9.0, numpy==1.26.4, xgboost>=2.0.0, scikit-learn>=1.3.0, shap>=0.44.0, lime>=0.2.0, facebook-business==18.0.5, spotipy==2.26.0, google-api-python-client==2.200.0, streamlit==1.63.0, authlib>=1.3.2 …
<!-- /cadrage:auto:stack -->

Compromis (ATAM, Humble & Farley, *Continuous Delivery* p.262) — « scalable » se prouve par un seuil
d'objectif, jamais par ce tableau :

| attribut | choix | alternative écartée | compromis accepté |
|---|---|---|---|
| performance | à compléter | à compléter | à compléter |
| disponibilité | à compléter | à compléter | à compléter |
| coût | à compléter | à compléter | à compléter |
| maintenabilité | à compléter | à compléter | à compléter |

## 4. Déploiement par priorité

<!-- cadrage:auto:deploiement -->
Pas de roadmap (`docs/roadmap/checklist.md` absent) : la méthode ci-dessous dit d'où viennent les priorités.
<!-- /cadrage:auto:deploiement -->

Méthode : à compléter
