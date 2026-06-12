# Deployment — programme différé (Phase D)

> **Statut : HORS SCOPE actuel** (décision 2026-06-09). On fait tout le reste d'abord
> (features B + robustesse C + benchmark VPS) ; la conteneurisation Docker du dashboard
> et le déploiement Hetzner sont la **toute dernière** étape, suivie du pentest sur l'URL
> déployée. Ce fichier capture les objectifs pour ne rien perdre. Le runbook détaillé
> (Ubuntu, Caddy, SSH, Storage Box) vit dans `.claude/dev-docs/migration-hetzner.md` (363 l).

## Pré-requis (à figer avant Phase D)

- **C5 — Benchmark VPS tranché** ✅ (2026-06-11) → topologie consolidée dans
  `.claude/dev-docs/benchmark-deployment-synthesis.md` : **Box A VPS Linux** (streaMLytics
  Postgres+Airflow+Streamlit+FastAPI **+ n8n orchestrateur + ffmpeg d'assemblage**, `CPX31 8 Go`
  validation → `CPX41 16 Go` à l'échelle) **+ Box B VPS Windows isolée** pour **MT5 (Windows-only)**
  + **génération vidéo déléguée à du GPU serverless pay-per-call** (jamais en local sur Box A)
  + **proxies résidentiels** pour isoler l'IP de scraping. Budget fixe ~35-55 €/mois.
- **Secrets prod prêts** : `APP_BASE_URL` (URL réelle, sinon liens email cassés), SMTP
  (`SMTP_HOST/PORT/USER/PASSWORD`), `FERNET_KEY` (identique app+Airflow), `STRIPE_*`
  (produit Premium 10€ + Payment Link `client_reference_id=artist_id` + webhook). Voir `.env.example`.

## D-1 — Provisioning infra (runbook, décisions figées 2026-06-11 → à exécuter 2026-06-12)

> Toutes les décisions sont **tranchées** (cf. `benchmark-deployment-synthesis.md`). Ce runbook
> est l'ordre d'exécution copier-coller. Coût cible **~13 €/mois tout compris** pour streaMLytics.

**Décisions figées :**

| Poste | Choix | Coût |
|---|---|---|
| **Box A (VPS streaMLytics)** | **Hetzner CAX31** — ARM Ampere, 8 vCPU / 16 Go / 160 Go NVMe | **~12,50 €/mo** |
| Fallback si ARM64 casse | Hetzner CPX31 x86 (4 vCPU / 8 Go) → resize CPX41 16 Go si besoin | ~13,60 / ~25 €/mo |
| **Domaine** | **`streamlytics.fr`** chez **OVH** (`.com` pris/parké ; `.app` libre en alternative) | ~7 €/an |
| **TLS / reverse proxy** | **Caddy** sur Box A — `app.` (Streamlit) + `api.` (FastAPI/Stripe) | 0 € |
| **Email envoi** | **SMTP Gmail actuel** — inchangé | 0 € |
| **Email réception `contact@`** | Boîte gratuite OVH ou Cloudflare Email Routing (forward → Gmail) | 0 € |
| **Backup** | `pg_dump` gzippé → Cloudflare R2 (10 Go gratuits) — `tools/db_backup.sh` | 0 € |
| **Box B (MT5)** | VPS Windows dédié isolé — **VPS broker (souvent gratuit, Windows+RDP prêt)** ou **OVH VPS Windows** (~10-15 €, licence incluse, même provider que le domaine). ⚠️ **PAS Hetzner Cloud** (Linux-only, pas de Windows en un clic). RDP par IP = fonction Windows, marche pareil partout. | ~0-15 €/mo |
| **Vidéo / n8n / scraping** | **POUR PLUS TARD** sur Box A (n8n+ffmpeg) + serverless GPU + proxy | 0 € maintenant |

**⚠️ Bloquant à lever AVANT d'acheter le CAX31 : validation build ARM64.**
- [ ] Builder les 3 Dockerfiles en `linux/arm64` (`docker buildx --platform linux/arm64`) : `Dockerfile` (dashboard — le plus risqué : pandas/numpy/xgboost/scikit-learn/shap/lime/weasyprint), `Dockerfile.airflow` (`apache/airflow:2.8.1-python3.11` est multi-arch), `Dockerfile.api`. Lancé 2026-06-11. **Si tous verts → CAX31 confirmé. Si un wheel manque en aarch64 → bascule CPX31 x86 (même prix).** (Résultat consigné dans DEVLOG#2026-06-11.)

**Runbook d'exécution (ordre) :**
1. [ ] **OVH** : enregistrer `streamlytics.fr` (~7 €/an) + activer la **boîte email gratuite** `contact@streamlytics.fr`.
2. [ ] **Hetzner Cloud** : créer un projet → serveur **CAX31** (ou CPX31 si fallback ARM), image **Ubuntu 24.04**, datacenter **UE (Nuremberg/Falkenstein/Helsinki)** (RGPD + latence UE), clé SSH ajoutée. Noter l'**IP publique**.
3. [ ] **DNS (OVH zone)** : `A app.streamlytics.fr → <IP Box A>`, `A api.streamlytics.fr → <IP Box A>` (et `A streamlytics.fr → <IP>` + redirect racine→`app.` au choix). TTL court le 1er jour.
4. [ ] **Hardening hôte D0** (section ci-dessous) : `ufw` 22/80/443, rotation secrets, `.env` prod, binding loopback Postgres/Airflow.
5. [ ] **Déploiement D1** : `git clone` + `cp docker-compose.example.yml docker-compose.yml` + `.env` rempli + `make migrate` + `docker compose up -d`.
6. [ ] **Caddy** : `Caddyfile` avec `app.streamlytics.fr` → `localhost:8501` (WebSocket OK) et `api.streamlytics.fr` → `localhost:8502` ; Let's Encrypt auto ; headers cookie `Secure/HttpOnly/SameSite` + HSTS.
7. [ ] **Backup** : cron `pg_dump` quotidien → R2 + **drill de restauration** validé (78 tables).
8. [ ] **Box B (MT5)** : provisionner/downsizer le VPS Windows en parallèle (indépendant de streaMLytics).
9. [ ] **Smoke prod** : register/login, isolation `artist_id`, déclencher 1 DAG, upload 1 CSV, export PDF — sur l'URL `https://app.streamlytics.fr`.
10. [ ] **Phase D** (Stripe + pentest) : voir D0/D2.

**Repoussé explicitement (pas demain)** : activation Stripe (Phase D), n8n + génération vidéo (serverless pay-per-call), proxies scraping — tout est documenté dans la synthèse, 0 € tant que non déployé.

## D0 — Sécurité pré-exposition (checklist actionnable, 2026-06-11)

Audit pré-déploiement. Ce qui était **fixable en code est déjà fait** (PR `chore/pre-deploy-optimizations`) ; le reste sont des **actions ops** à exécuter sur le VPS avant d'ouvrir le port 443.

**✅ Déjà corrigé en code :**
- `docker-compose.yml` est **gitignored** (local par environnement). Le durcissement vit donc dans le **template versionné `docker-compose.example.yml`** (`cp docker-compose.example.yml docker-compose.yml` sur le VPS) : plus aucun secret en dur — `${DATABASE_PASSWORD}`, `${AIRFLOW_ADMIN_USERNAME/PASSWORD}` ; Postgres + Airflow bindés sur `127.0.0.1` (plus joignables depuis Internet ; dev local sur `localhost`). ⚠️ L'ancien `docker-compose.yml` **tracké** contenait `Wowow1357911!` → présent dans l'historique git (commits `52c2e19`, `7781b22`, `cf10a97`) même si le fichier est désormais untracké → rotation obligatoire (action ops #1).
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
