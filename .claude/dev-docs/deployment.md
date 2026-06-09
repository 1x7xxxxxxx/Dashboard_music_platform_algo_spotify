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
