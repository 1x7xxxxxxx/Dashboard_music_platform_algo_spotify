# Deployment — programme différé (Phase D)

> **Statut : HORS SCOPE actuel** (décision 2026-06-09). On fait tout le reste d'abord
> (features B + robustesse C + benchmark VPS) ; la conteneurisation Docker du dashboard
> et le déploiement Hetzner sont la **toute dernière** étape, suivie du pentest sur l'URL
> déployée. Ce fichier capture les objectifs pour ne rien perdre. Le runbook détaillé
> (Ubuntu, Caddy, SSH, Storage Box) vit dans `.claude/dev-docs/migration-hetzner.md` (363 l).

## Pré-requis (à figer avant Phase D)

- **C5 — Benchmark VPS tranché** : topologie choisie pour les 4 charges — streaMLytics
  (Postgres + Airflow + Streamlit + FastAPI), n8n (stack Docker actuelle + workflows futurs :
  génération vidéo lourde, intégration YouTube auto, scraping leboncoin), **MT5 (Windows-only)**,
  + marge. Reco probable : **1 VPS Linux** (streaMLytics + n8n) + **MT5 sur box Windows séparée** ;
  la génération vidéo peut justifier un sizing supérieur ou du rendu à la demande.
- **Secrets prod prêts** : `APP_BASE_URL` (URL réelle, sinon liens email cassés), SMTP
  (`SMTP_HOST/PORT/USER/PASSWORD`), `FERNET_KEY` (identique app+Airflow), `STRIPE_*`
  (produit Premium 10€ + Payment Link `client_reference_id=artist_id` + webhook). Voir `.env.example`.

## D0 — Sécurité pré-exposition (checklist actionnable, 2026-06-11)

Audit pré-déploiement. Ce qui était **fixable en code est déjà fait** (PR `chore/pre-deploy-optimizations`) ; le reste sont des **actions ops** à exécuter sur le VPS avant d'ouvrir le port 443.

**✅ Déjà corrigé en code :**
- `docker-compose.yml` : plus aucun secret en dur — `${DATABASE_PASSWORD}`, `${AIRFLOW_ADMIN_USERNAME/PASSWORD}` (3 occurrences du mot de passe supprimées). Postgres + Airflow bindés sur `127.0.0.1` (plus joignables depuis Internet ; le dev local reste sur `localhost`).
- `src/api/auth.py` : plus de secret JWT public en dur — secret aléatoire éphémère si `API_SECRET_KEY` absente.
- `src/api/main.py` : `/docs` + `/redoc` désactivés par défaut (`API_ENABLE_DOCS=1` pour les réactiver) ; origines CORS pilotées par `CORS_ORIGINS`.
- `src/api/routers/stripe_webhook.py` : refus (503) des webhooks non signés sauf `STRIPE_ALLOW_UNSIGNED=1` (dev).

**🔧 Actions ops AVANT exposition (non automatisables) :**
1. **Rotation mot de passe Postgres** — `Wowow1357911!` est dans l'historique git → le changer pour de bon (nouveau mot de passe DB + `ALTER USER postgres PASSWORD …`), puis poser `DATABASE_PASSWORD`/`DB_PASSWORD` dans le `.env` du VPS. Idem mot de passe admin Airflow (`AIRFLOW_ADMIN_PASSWORD` distinct et aléatoire) + username (`AIRFLOW_ADMIN_USERNAME` ≠ `1x7xxxxxxx`).
   - **Rotation des creds `config/config.yaml`** (gitignored mais *live*, jamais commités mais possiblement partagés via fichiers locaux) : surtout le **token d'accès Meta** et le **mot de passe d'application Gmail/SMTP** — les régénérer côté Meta/Google par hygiène, et reposer les valeurs côté VPS.
2. **`API_SECRET_KEY`** posée (`openssl rand -hex 32`) dans l'env prod — sinon tokens cassés en multi-worker.
3. **`CORS_ORIGINS=https://<domaine>`** + **`APP_BASE_URL=https://<domaine>`** (liens email en clair/cassés sinon). **`API_ENABLE_DOCS`** laissé vide. **`STRIPE_WEBHOOK_SECRET`** posé (sinon webhook en 503, voulu).
4. **Firewall hôte (ufw)** : autoriser uniquement `22, 80, 443` en entrée ; `deny 5433, 8080, 8501, 8502`. Le binding loopback est une défense ; le firewall en est la seconde.
5. **Airflow UI** : jamais en direct → tunnel SSH (`ssh -L 8080:127.0.0.1:8080`) ou reverse-proxy authentifié séparé.
6. **Cookie session Streamlit** : `Secure`+`HttpOnly`+`SameSite` posés au niveau du reverse proxy (Caddy) ; HSTS au edge ; raccourcir `cookie.expiry_days` (30 → 1-7).

(P3 hygiène, non bloquant : `SPOTIFY_ARTIST_IDS` / `META_AD_ACCOUNT_ID` encore en dur dans `docker-compose.yml` — IDs publics, env-ref optionnel ; liens localhost dans `useful_links.py` à piloter par env.)

## D1 — Conteneurisation + déploiement

1. **Conteneuriser le dashboard Streamlit** : ajouter un service `dashboard` au
   `docker-compose.yml` (un `Dockerfile` racine existe ; FastAPI a `Dockerfile.api`). Aujourd'hui
   le dashboard tourne sur l'hôte (`streamlit run`) — Airflow + Postgres sont déjà conteneurisés
   et **les DAGs tournent déjà dans le conteneur `airflow_scheduler`** (rien à changer côté DAGs).
2. **Volumes persistés** : `postgres_data` / `airflow_logs` aujourd'hui en volumes nommés non
   sauvegardés → bind-mount ou volume managé + **éviter `docker compose down -v`**.
3. **HTTPS** : Caddy + Let's Encrypt en reverse proxy (auto-renew).
4. **Env prod** : injecter les secrets ci-dessus (jamais en clair dans compose).
5. **CD** : activer le job dans `.github/workflows/cd-release.yml` (aujourd'hui `if: false`) —
   `docker compose pull && up -d` via SSH.
6. **Backup (C2)** : cron `pg_dump` quotidien → Storage Box + **drill de restauration** vérifié.

## D2 — Test cyber (sur l'URL déployée)

Checklist pentest, contre l'environnement déployé (pas WSL2 local) :
- **Bruteforce** : vérifier lockout (5 essais/15 min) + rate-limit.
- **Phishing** : hygiène liens/domaines (les emails passent par `APP_BASE_URL`).
- **MITM** : HTTPS/HSTS via Caddy.
- **RCE** : SQL paramétré + allowlist + validation des uploads CSV.
- **DoS** : rate-limit API (C3) + limites Caddy.
- Outil : **chrome-devtools MCP** contre l'URL Linux (Lighthouse, console, réseau) — la limite
  WSL2 locale ne s'applique pas côté serveur.

## Déjà en place (ne pas refaire)

- 14 DAGs auto-schedulés (cron) ; CI complète (`ci.yml` : ruff + pytest + manifest).
- Auth durcie : bcrypt, lockout, TOTP, Fernet, allowlist SQL.
- Sécurité restante (code, en C3) : rate-limit API FastAPI, timeout session, headers.
