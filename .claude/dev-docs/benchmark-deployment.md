# Benchmark déploiement — grille complète (C5 sizing VPS + C6 domaine/accès)

> Référencé par `roadmap/checklist.md` (items C5/C6). Grille exhaustive de ce qu'il faut
> mesurer/décider avant d'ouvrir streaMLytics au public. Inclut en fin de doc les
> **prompts cross-projets** à poser aux IA des projets MT5 / n8n (qui ont les détails
> de ces charges, contrairement à l'IA de ce repo). Créé 2026-06-11.

## 0. Système à dimensionner (contexte)

streaMLytics = SaaS multi-tenant analytics musicale, stack **dockerisée**, isolation par
`artist_id`, 1 URL publique → register/login → chaque artiste voit ses données.

| Composant | Rôle | Port | Profil ressources |
|---|---|---|---|
| **PostgreSQL 17** | `airflow_db` + `spotify_etl` (~78 tables) | 5433→5432 | RAM modérée, **I/O disque (disk-bound sur petit VPS)** |
| **Streamlit dashboard** | UI principale, ~40 vues | 8501 | **RAM = facteur dimensionnant** : chaque session en mémoire ; base ~300-600 Mo (pandas/plotly/xgboost/matplotlib) |
| **Airflow webserver** | UI orchestrateur (admin) | 8080 | ~0,5-1 Go |
| **Airflow scheduler** | ~15 DAGs cron en **LocalExecutor** | — | scheduler ~0,5 Go + **chaque tâche = subprocess** ~200-500 Mo |
| **FastAPI** | REST JWT + webhook Stripe | 8502 | léger ~150 Mo |
| **Reverse proxy** (à ajouter) | TLS/HTTPS (Caddy) | 80/443 | léger |

Particularités structurantes :
- **Streamlit mono-process multi-sessions** : N sessions concurrentes = N×session_state en RAM dans 1 process → la RAM monte avec la concurrence, pas le CPU.
- **Génération PDF** (matplotlib + WeasyPrint) = pics RAM transitoires 200-500 Mo/rapport.
- **Inférence ML** XGBoost chargée en mémoire.
- **LocalExecutor** : tâches DAG sur la même machine que le scheduler (pas de workers distribués).

---

## A. Profil de ressources PAR composant — à MESURER (idle / charge / pic)

1. **RAM** : RSS repos, RSS charge, pic (génération PDF, scoring ML, collecte Meta/YouTube, gros import CSV).
2. **CPU** : moyen + pics (rendu Streamlit, agrégations SQL, parsing CSV, inférence ML).
3. **Disque** : taille DB (croissance/mois/artiste), logs Airflow, modèles ML, `data/raw`+`data/archive`.
4. **Connexions DB** simultanées (Streamlit ~1/vue + tâches Airflow + FastAPI).
5. **Durée de chaque DAG** (Spotify/YouTube/SoundCloud/Instagram/Meta/watchers CSV/ML scoring) → détermine le chevauchement.

**Cible critique** : **Mo de RAM par session Streamlit active** (ouvrir 1/5/10 sessions, mesurer le delta). RAM totale ≈ ce chiffre × concurrence-pic.

---

## B. Hypothèses d'échelle — à DÉCIDER avant de benchmarker

1. Nb d'artistes cibles à **3 / 6 / 12 mois** (10 ? 100 ? 1000 ?).
2. **Concurrence pic** : sur N inscrits, combien simultanément actifs ? (SaaS B2B typique : 5-15 % actifs/jour, fraction concurrente).
3. **Sessions Streamlit concurrentes au pic** = dimensionne la RAM.
4. **Volume données/tenant** (titres, historique streams, campagnes) → taille DB + durée requêtes.
5. **Fréquence collectes** × nb artistes = charge Airflow.

---

## C. Méthodologie de benchmark (outils + protocole)

- **Ressources** : `docker stats` / `ctop` en continu ; Prometheus + cAdvisor pour l'historique.
- **Load test Streamlit** : ⚠️ Streamlit = **WebSockets** (Tornado), pas HTTP → ab/wrk/k6-HTTP ne reproduisent PAS une session. Utiliser **Playwright/Selenium** (N navigateurs headless naviguant réellement) ou **Locust + client WS custom**. Mesurer RAM/CPU du conteneur pendant la montée.
- **Load test FastAPI** : `k6`/`wrk` (vérifier aussi le rate-limit C3 : 120 req/60s global, 10/300s sur `/auth/token`).
- **DB** : `pgbench` (capacité brute) + surtout `pg_stat_statements` + `EXPLAIN ANALYZE` sur les requêtes dashboard chaudes (ROI, KPI, séries temporelles).
- **Airflow** : déclencher tous les DAGs simultanément (= bouton « Lancer TOUTES les collectes ») → RAM/CPU pic + durée.
- **Pic combiné (WORST CASE qui dimensionne)** : collecte Airflow (plusieurs tâches) **+** plusieurs sessions Streamlit **+** une génération PDF **simultanément**. Dimensionner sur ce pic, pas la moyenne.

---

## D. Topologie — décision structurante

Charges à placer : **streaMLytics** (prêt), **n8n** (workflows : génération vidéo, YouTube auto, scraping), **MT5** (trading), + marge.

Points durs :
- ⚠️ **MT5 = Windows-only** → ne tourne pas sur VPS Linux/Docker → **casse le « un seul VPS »**. Décider : VPS Windows séparé / machine dédiée / VM Windows.
- ⚠️ **Génération vidéo** = potentiellement GPU + RAM/CPU lourds → machine dédiée ou rendu serverless GPU à la demande.
- **Scraping** = IP/bande passante + risque bannissement → proxies, parfois isolé.

À décider :
1. 1 VPS Linux mutualisé (streaMLytics + n8n) **vs split**.
2. streaMLytics **seul d'abord** (recommandé : seul prêt+mergé), couches au-dessus ensuite.
3. Tout en Docker sur 1 hôte vs VPS séparés par charge.
4. MT5 : où + coût Windows.
5. Vidéo : CPU/GPU, fréquence, volume.

---

## E. Stockage & I/O
- Taille DB actuelle + **croissance/mois/artiste** (extrapoler à l'échelle cible).
- **Disque NVMe SSD requis** (Postgres I/O-sensible, disk-bound sur petit VPS).
- Volume **logs Airflow** (rotation ?).
- **Backups** : espace `pg_dump` gzippé + rétention (`tools/db_backup.sh` existe) + **copie déportée** (Storage Box / S3).
- Volumes Docker persistés (`postgres_data`, `airflow_logs`) — ne pas perdre au `down -v`.

---

## F. Réseau & bande passante
- **Sortant** : appels API collecteurs (Spotify/YouTube/Meta/SoundCloud/Instagram) + scraping → volume/mois.
- **Entrant** : assets Streamlit (~532 Ko bundle JS au cold-start/session).
- Quota bande passante + coût **overage** de l'hébergeur.
- Latence datacenter vs localisation des artistes.

---

## G. C6 — Domaine + accès public (PRÉREQUIS, pas cosmétique)

HTTPS obligatoire : exigé par **Stripe** (checkout + webhook), cookies d'auth, crédibilité SaaS.
1. **Nom de marque** : dispo + prix `streamlytics.{com,io,app,fr}` (vérifier marques déposées).
2. **Registrar** : Cloudflare (DNS + proxy/CDN gratuit + anti-DDoS, recommandé) vs OVH vs Namecheap — comparer **prix renouvellement** (piège 2e année).
3. **Sous-domaines** : `app.X` (dashboard) + `api.X` (FastAPI/webhook) ? ou racine + chemins ?
4. **TLS** : **Caddy** (Let's Encrypt auto) vs Traefik vs nginx+certbot. Caddy gère aussi cookies Secure/HttpOnly/SameSite + HSTS au edge.
5. **Email pro** (`contact@X`) : requis Stripe + support + emails de vérification (actuellement SMTP Gmail). Google Workspace / Zoho / OVH. Vérifier **délivrabilité SPF/DKIM/DMARC** (sinon vérifications en spam).
6. **CDN/cache** assets statiques (Cloudflare gratuit).

---

## H. Modèle de coût (€/mois) — à construire
VPS Linux streaMLytics + (éventuel) VPS Windows MT5 + (éventuel) machine/GPU vidéo + domaine (~10-50 €/an) + email pro (~5-6 €/mois/boîte) + stockage backup déporté + overage bande passante + outillage. **Budget cible €/mois** = input à fixer (contraint la topologie).

---

## I. Sauvegarde / DR / monitoring
- **Backup** : fréquence `pg_dump` (script + drill restauration validé sur 78 tables) + rétention + **copie déportée**.
- **RTO/RPO** : temps de remontée acceptable + perte de données acceptable.
- **Monitoring** : CPU/RAM/disk/uptime (Netdata / Grafana / UptimeRobot externe) + alerting (DB down, disk plein).
- **Health checks** : déjà en place (postgres `pg_isready`, airflow `/health`).

---

## J. Critères de choix hébergeur
Comparer Hetzner / OVH / Scaleway / Contabo / DigitalOcean / Vultr sur : €/Go RAM, €/vCPU, **NVMe** (taille/IOPS), bande passante incluse + overage, snapshots/backups managés, **localisation UE (RGPD)**, dispo **VPS Windows** (MT5) chez le même fournisseur, scalabilité verticale (upgrade RAM sans réinstall).

---

## K. Seuils de scaling (« quand passer à l'étape suivante »)
- Nb de sessions concurrentes où Streamlit sature → multi-replica derrière le proxy, ou migration React.
- Nb de tenants où Postgres a besoin de plus de RAM / serveur dédié.
- Airflow LocalExecutor saturé → CeleryExecutor + workers.
- FastAPI multi-worker (uvicorn workers) — ⚠️ rate-limit C3 in-memory single-process + **secret JWT à fixer** (pas éphémère) en multi-worker.

---

## L. Inconnues bloquantes à trancher AVANT de benchmarker
1. Échelle cible (3/6/12 mois) + concurrence pic.
2. Budget €/mois infra.
3. MT5 : mutualisé (impossible Linux) ou Windows séparé ?
4. Vidéo : CPU/GPU, fréquence, volume ?
5. n8n/scraping : même hôte ou isolés ?
6. Domaine retenu + registrar + email pro.
7. Région datacenter.

---

## M. Prompts cross-projets (à poser aux IA MT5 / n8n)

> Ces IA connaissent les détails de leurs projets respectifs ; elles doivent renvoyer
> un **profil de ressources** consolidable avec streaMLytics pour décider la topologie.

### Prompt à poser à l'IA du projet **MT5**
```
Je dimensionne l'hébergement d'un setup multi-projets et je dois décider si MT5 partage
une machine ou tourne sur une machine Windows dédiée. Donne-moi le PROFIL DE RESSOURCES
précis de ce projet MT5, en chiffres :
1. OS requis (Windows obligatoire ? quelle version ?) et pourquoi (MT5 terminal, EAs).
2. Nombre de terminaux MT5 / comptes / EAs tournant en parallèle.
3. RAM idle et pic par terminal, et au total.
4. CPU : usage moyen + pics (backtests, optimisations, multi-symboles).
5. Doit-il tourner 24/7 ? sensibilité à la latence vers le broker (VPS proche du broker ?).
6. Disque (historique de ticks, logs) et croissance.
7. Réseau (flux de cotations, ordres) + besoin d'IP fixe.
8. Dépendances annexes (Python/MetaTrader bridge, base de données, n8n, dashboards ?).
9. Contraintes de colocalisation : peut-il cohabiter avec d'autres charges, ou exige-t-il
   une VM/VPS isolé (stabilité, broker, sécurité) ?
10. Coût actuel ou estimé de son hébergement.
Format de sortie : un tableau RAM/CPU/disque/réseau (idle/pic) + une reco « machine dédiée
Windows vs mutualisable », + le budget €/mois.
```

### Prompt à poser à l'IA du projet **n8n** (workflows : génération vidéo, YouTube auto, scraping)
```
Je dimensionne l'hébergement d'un setup multi-projets et je veux savoir si n8n + ses
workflows peuvent partager un VPS Linux avec une app Streamlit/Postgres/Airflow, ou s'ils
exigent des ressources/une machine séparée. Donne-moi le PROFIL DE RESSOURCES précis, en
chiffres :
1. n8n lui-même : RAM/CPU idle et sous charge, mode (main process vs queue mode + workers),
   base de données utilisée (SQLite/Postgres ?), persistance.
2. Workflows de GÉNÉRATION VIDÉO : CPU ou GPU ? RAM/VRAM par rendu, durée par vidéo,
   fréquence/volume (vidéos/jour), outils (ffmpeg, modèles IA, services externes ?).
   → c'est le plus gros levier de sizing : précise si rendu local ou délégué (API/serverless GPU).
3. Workflows YOUTUBE auto : volume d'appels API, stockage temporaire, bande passante upload.
4. Workflows SCRAPING : volume de requêtes, besoin de PROXIES/IP tournantes, risque de
   bannissement → faut-il isoler le scraping sur une IP/VPS séparé ?
5. Pics de charge concurrents (plusieurs workflows en même temps) → worst case RAM/CPU.
6. Disque (fichiers vidéo temporaires, assets) + croissance + nettoyage.
7. Réseau : trafic sortant (scraping/API) + entrant/sortant (upload vidéo) par mois.
8. Dépendances : Postgres dédié ? Redis (queue mode) ? services externes payants ?
9. Contraintes de colocalisation : peut-il cohabiter avec streaMLytics (Postgres/Airflow/
   Streamlit) sur 1 VPS Linux, ou la génération vidéo justifie-t-elle une machine dédiée/GPU ?
10. Coût actuel ou estimé.
Format de sortie : tableau RAM/CPU/GPU/disque/réseau (idle/pic) par catégorie de workflow +
reco « mutualisable avec streaMLytics vs machine dédiée/GPU » + budget €/mois.
```

### Après avoir collecté les deux réponses
Revenir avec : profil MT5 + profil n8n + (l'estimation streaMLytics une fois benchmarkée).
On additionne les pics, on tranche la topologie (1 VPS Linux + 1 box Windows ? + 1 machine
GPU vidéo ?), on chiffre le €/mois total, et on choisit l'hébergeur via la grille § J.
