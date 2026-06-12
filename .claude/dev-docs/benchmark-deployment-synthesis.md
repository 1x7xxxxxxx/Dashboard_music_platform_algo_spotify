# Benchmark déploiement — SYNTHÈSE consolidée (streaMLytics + n8n/vidéo + MT5)

> Réponses cross-projets collectées le **2026-06-11**. Ce fichier **consolide** les trois
> profils de ressources et **tranche la topologie + le budget**. Il est le livrable des items
> **C5** (sizing VPS) et **C6** (domaine/accès) de `roadmap/checklist.md`, et alimente
> `deployment.md` (Phase D). La grille de mesure brute reste dans `benchmark-deployment.md` ;
> les profils détaillés MT5 / n8n viennent des IA de ces projets (citées telles quelles ci-dessous).

---

## 0. TL;DR — le verdict en 5 lignes

1. **Box A — 1 VPS Linux always-on** : streaMLytics (Postgres + Airflow + Streamlit + FastAPI + Caddy) **+** n8n **orchestrateur** (workflows scraping / YouTube / créatives / assemblage ffmpeg). Mutualisables **à une condition** : la **génération vidéo IA est déléguée** (serverless GPU à l'usage), **jamais rendue en local** sur ce VPS CPU.
2. **Box B — 1 VPS Windows dédié et isolé** : MT5 live 24/7. **Ne jamais mutualiser** (OS incompatible + stabilité du live + isolation des creds broker).
3. **GPU vidéo** : **aucun GPU acheté ni loué 24/7**. En phase de validation (~10 vidéos/jour, 2 mois), **pay-per-call sur modèles open hébergés** (fal.ai / Replicate : LTX-Video, Wan, CogVideoX). Coût marginal négligeable.
4. **Le seul vrai besoin d'isolation du stack Linux n'est pas le CPU, c'est l'IP de scraping** → **proxies résidentiels**, pas un 2ᵉ VPS.
5. **Budget infra fixe always-on ≈ 50-55 €/mois** (Box A + Box B + domaine + email + backup) ; **+ ~50-75 €/mois de proxies** + **vidéo gen variable ~30-90 €/mois** en phase test. Le poste qui décide du succès n'est PAS l'infra — c'est **bans/shadowban + monétisation**.

---

## 1. Topologie cible (schéma)

```
                          INTERNET (port 443)
                                 │
                      ┌──────────┴───────────┐
                      │   Caddy (TLS auto)    │  app.X → Streamlit | api.X → FastAPI/Stripe
                      └──────────┬───────────┘
   ┌─────────────────────────────┴──────────────────────────────────────┐
   │  BOX A — VPS Linux always-on (Hetzner CPX31→CPX41)                   │
   │                                                                      │
   │  streaMLytics (Docker)            n8n (Docker)                       │
   │   • PostgreSQL 17                  • n8n main (+ Redis/worker si       │
   │     (airflow_db + spotify_etl)       queue mode)                      │
   │   • Airflow web + scheduler        • workflows : scraping(proxy),     │
   │     (LocalExecutor, ~15 DAGs)        YouTube auto, créatives,         │
   │   • Streamlit (~40 vues)             ASMR/absurde → ffmpeg ASSEMBLAGE │
   │   • FastAPI (JWT + webhook Stripe)   • publication réseaux (24/7)     │
   └──────────────┬──────────────────────────────┬────────────────────────┘
                  │ délègue le rendu              │ scrape via
                  ▼                               ▼
        GPU SERVERLESS (pay-per-call)     PROXIES RÉSIDENTIELS
        fal.ai / Replicate / Runway       (isole l'IP, pas la machine)

   ┌──────────────────────────────────────────────────────────────────────┐
   │  BOX B — VPS Windows dédié ISOLÉ (~10-20 €/mo, ou VPS broker gratuit)  │
   │   • MT5 terminal live 24/7 + EAs (stratégie H1)                        │
   │   • creds broker isolés du web — aucune autre charge                   │
   └──────────────────────────────────────────────────────────────────────┘

   PC perso (NON 24/7) : dev/test, backtests MT5 à la demande,
                         (option) instance n8n batch lourd
```

**Pourquoi 2 boxes et pas 1 ni 3 :**
- **MT5 hors Box A** : Windows-only (airflow/n8n/ffmpeg sont Linux-natifs) **+** un OOM de l'assemblage vidéo ne doit jamais pouvoir tuer un terminal de trading live **+** surface d'attaque (n8n expose des webhooks ; les creds broker doivent vivre ailleurs).
- **n8n DANS Box A** (pas une 3ᵉ box) : sans le rendu GPU local, n8n n'est qu'un orchestrateur léger (appels HTTP + ffmpeg CPU) → il tient dans la marge du VPS streaMLytics.
- **Pas de box GPU** : à ~10 vidéos/jour, le serverless à la seconde est ~50-100× moins cher qu'un GPU 24/7 (break-even ≈ 50-100 vidéos/jour soutenues).

---

## 2. Profil de ressources consolidé (idle / pic)

### Box A — charges Linux mutualisées

| Composant | RAM idle | RAM pic | CPU pic | GPU | Disque | Réseau/mois |
|---|---|---|---|---|---|---|
| **streaMLytics — Postgres 17** | ~50-150 Mo | 150-300 Mo (+ buffers) | <0,5 cœur | — | DB + WAL (croît /tenant) ; **NVMe requis (disk-bound)** | — |
| **streaMLytics — Streamlit** | 300-600 Mo | **+N×session_state** (RAM = fct concurrence) | 0,5-1 cœur/rendu | — | — | bundle JS ~532 Ko/session |
| **streaMLytics — Airflow web** | ~0,5-1 Go | idem | <0,5 cœur | — | logs (rotation) | — |
| **streaMLytics — Airflow scheduler** | ~0,5 Go | **+ subprocess/tâche 200-500 Mo** (LocalExecutor) | 1-2 cœurs en collecte | — | logs DAG | appels API collecteurs |
| **streaMLytics — FastAPI** | ~150 Mo | ~250 Mo | <0,5 cœur | — | — | léger |
| **streaMLytics — génération PDF** | — | +200-500 Mo transitoire | 1 cœur | — | — | — |
| **n8n main** | 150-250 Mo | 400-700 Mo | 0,5-1 cœur | — | volume `n8n_data` ~1 Go | API JSON (faible) |
| **n8n Postgres (n8n_db)** | 50 Mo | 150-300 Mo | <0,5 cœur | — | <1 Go (pruning 72 h) | — |
| **n8n Redis** (si queue mode) | 10 Mo | 50-100 Mo | négligeable | — | — | — |
| **n8n — digest news (UC1)** | — | +200-400 Mo transitoire | 0,5 cœur | — | ~0 | qq Mo |
| **n8n — scraping (LBC/reels)** | — | +150-300 Mo | 0,5-1 cœur | — | <500 Mo | 1-5 Go (**via proxy**) |
| **n8n — créatives marketing** | — | +200 Mo | 0,5 cœur | **délégué** | 100-500 Mo/job | dépend volume |
| **n8n — vidéo : assemblage ffmpeg** | — | **+0,8-2 Go** | **2-4 cœurs (le spike)** | **délégué** | 50-500 Mo/job | download gen + **upload massif** |
| **n8n — génération vidéo IA** | — | — | — | **EXTERNE serverless** | — | download résultats |

**Worst case concurrent Box A** (cron digest **+** 1 render ffmpeg **+** 1 scrape **+** collecte Airflow **+** 1 session dashboard, simultanés) :
≈ **8-10 Go RAM** et **4-6 cœurs en burst**. **C'est ce pic qui dimensionne Box A.**
> En phase validation, streaMLytics n'a **qu'1 tenant** → sa concurrence Streamlit est ~nulle, donc le pic réel est dominé par ffmpeg+Airflow → **8 Go tient (juste)**, **16 Go confortable**.

### Box B — MT5 (Windows, isolé)

| Ressource | Idle | Pic | Notes |
|---|---|---|---|
| RAM (process MT5) | 0,6-1 Go | 1,5-2 Go | base ~500 Mo + 30-80 Mo/chart-EA |
| **RAM (avec Windows)** | **2,5-3 Go** | **3,5-4 Go** | Windows Server GUI mange ~1,5-2 Go → **4 Go mini, 8 Go confort** |
| CPU | <2 % d'1 vCPU | pics brefs 10-20 % sur 1 cœur | stratégie **H1 = 1 décision/heure**, aucune pression CPU → **2 vCPU suffisent** |
| Disque | install 0,5-1 Go | +1-5 Go/an (ticks+logs) | **50-60 Go SSD** = années de marge |
| Réseau | qq kbps | dizaines de kbps en rafale | qq Go/mois ; ordres négligeables |
| IP fixe | — | — | **non nécessaire** (connexion sortante broker) |
| Latence broker | — | — | **non-critique** (H1 ≠ HFT, 50-150 ms OK) → la « VPS haute fréquence » actuelle est **surdimensionnée** |

---

## 3. Le levier #1 du sizing vidéo : rendu local vs délégué (90 % de la décision)

Les deux projets vidéo (absurde/UC5 + ASMR auto-publish) se découpent en **3 étages** :

| Étage | Quoi | Où | Coût ressource |
|---|---|---|---|
| **Génération** (text→video, image→video) | Runway, Kling, Seedance, fal.ai, Replicate | **API externe (GPU serverless)** | **~0 local** — n8n appelle, poll, télécharge |
| **Assemblage** (concat, sous-titres, audio ASMR en boucle, watermark, vertical) | ffmpeg | **Local CPU (Box A)** | 1-2 cœurs, ~0,5-1 Go RAM, **1-3 min/clip** |
| **Publication** | YouTube/TikTok/Insta/FB API | Local, I/O réseau | négligeable CPU, **upload-bound** |

**Le piège corrigé par l'IA n8n** : le blocage n'est **pas** « API vs pas d'API ». On *peut* télécharger un modèle open (LTX-Video, Wan 2.2, CogVideoX, HunyuanVideo, SVD, AnimateDiff) et le tourner sans coût marginal — **mais seulement sur un GPU NVIDIA avec assez de VRAM**. Sur un VPS CPU (Hetzner sans GPU), une génération prendrait des heures ou ne démarrerait pas.

**VRAM requise par modèle open** (le vrai critère si rendu local un jour) :

| Modèle | VRAM (full / quantisé) | Vitesse | Note |
|---|---|---|---|
| **LTX-Video** | ~12 Go | très rapide | le plus accessible (démarre sur RTX 3060 12 Go) |
| Wan 2.1/2.2 1.3B | ~8-12 Go | rapide | bon rapport qualité/VRAM |
| Wan 2.2 14B | 24 Go+ (quantisé ~16 Go) | lent | qualité supérieure |
| CogVideoX-5B | 16-24 Go | moyen | — |
| HunyuanVideo | 45 Go+ full / ~13-16 Go quantisé | lent | top qualité open, lourd |
| Stable Video Diffusion | 16-20 Go | moyen | image→video |
| AnimateDiff | 8-12 Go | rapide | animation courte |

**Arbre de décision GPU :**
- **Tu as déjà un GPU NVIDIA ≥12 Go sur une box allumable** → ComfyUI en Docker, coût marginal ~0 (élec). Mais **cette box n'est PAS Box A** (le VPS CPU) — c'est ton PC / un nœud GPU. n8n l'appelle via webhook/HTTP.
- **Pas de GPU + tu louerais 24/7** → ~250-400 €/mois (RTX 4090 cloud) → **rentable seulement si tu satures le GPU plusieurs h/jour**. À ~10/jour = gaspillage.
- **Pas de GPU + volume sporadique** (← **ton cas**) → **GPU serverless à la seconde** (fal.ai / Replicate / RunPod) : même modèle open, tu paies seulement le calcul. **Choix retenu pour la validation.**

> **Correction clé** : la reco n'est pas « API produit fermée obligatoire ». C'est « **le GPU ne se mutualise pas avec streaMLytics sur un VPS CPU** ; le rendu vidéo local impose un GPU qui vit ailleurs ». Pour la phase test, **pay-per-call sur modèle open** (pas l'API premium chère) est l'optimum coût.

---

## 4. Quels workflows tolèrent un PC perso non-24/7 ?

**Critère = type de TRIGGER, pas le use case.** Un workflow tolère un PC qui dort s'il est **cron/batch + sans webhook entrant + sans heure critique**.

| Workflow / étape | Trigger | PC éteint OK ? | Pourquoi |
|---|---|---|---|
| UC1 digest news | cron quotidien | ✅ | hourly catch-up + `staticData` guard (commit `0d8d7de`) = rattrape au prochain boot |
| UC2 scraping Leboncoin | cron/poll | ✅ | rate un run = scrape au suivant ; ⚠️ **via proxy**, pas l'IP maison |
| UC3 scraping reels + vision | batch | ✅ | pipeline d'analyse, zéro temps réel ; lourd → mieux sur le PC |
| UC4 créatives marketing | on-demand/batch | ✅ | génération à la demande |
| UC5/ASMR — gen vidéo + assemblage ffmpeg | batch | ✅ | appelle serverless, télécharge, assemble ; ffmpeg CPU mieux sur PC que sur VPS payant |
| **Publication au pic d'audience** (18 h…) | horaire critique | ❌ | PC endormi à l'heure du post = créneau raté (levier de revenu) |
| **Tout webhook entrant** (callback gen, OAuth refresh, bot) | inbound | ❌ | endpoint mort quand le PC dort (REX `N8N_WEBHOOK_URL`) |
| **Notif d'erreur fiable** | — | ❌ | hôte off = l'error-workflow ne notifie personne |

**Le piège n8n = une seule instance** : si n8n vit sur le PC, **tout** s'éteint avec le PC — publication comprise. On ne peut pas répartir des workflows d'une même instance entre PC et VPS. Deux options :
- **Reco (validation)** — **une seule instance n8n sur Box A (always-on)**. Gen déléguée (léger), ffmpeg d'assemblage sur Box A (OK à ~10/jour), scraping via proxy. **Le PC n'est pas dans l'archi de prod** (dev/test seulement). Publication fiable, webhooks vivants.
- **Variante éco** — **deux instances** : PC = batch lourd (digest, scraping, vision, gen+assemblage) ; Box A = **uniquement** scheduler de publication + webhooks + error-notif. Économise du CPU VPS mais coûte en complexité (2 `N8N_ENCRYPTION_KEY`, coordination inter-instances). À n'adopter que si le ffmpeg du VPS devient un goulot — **improbable à 10 vidéos/jour**.

---

## 5. Réponses point-par-point (n8n)

1. **n8n** : Postgres (pas SQLite). **Main process** suffit jusqu'à ≥2 workflows longs concurrents ; au-delà **queue mode** (Redis + 1-2 workers) per règle `n8n-workflow.md`. Persistance = Postgres + volume `n8n_data` (clé de chiffrement, binaires).
2. **Vidéo** : CPU pour l'**assemblage ffmpeg uniquement** ; **GPU délégué**. ~0,5-1 Go RAM, 1-3 min/clip 1080p local. Règle d'or : **ne jamais rendre l'IA en local sur Box A**.
3. **YouTube auto** : limité par **les quotas API**, pas le CPU. YouTube Data API = **10 000 unités/jour** par défaut, **1 upload = 1 600 unités** → **~6 uploads/jour/compte** sans hausse de quota.
4. **Scraping** : Leboncoin (**DataDome**) + TikTok/Insta agressifs anti-bot → **proxies résidentiels rotatifs** ou API de scraping (Apify/Bright Data). Risque ban de l'IP du VPS → **on isole l'IP, pas la machine**. Volume faible → pas de pression CPU.
5. **Pics concurrents** : worst case ~4 Go / 4-5 cœurs. **Queue mode + limite de concurrence** des workers borne ça.
6. **Disque** : vidéo temp 50-500 Mo/job → **nœud cleanup obligatoire** (rm après publication confirmée) + **~20-50 Go scratch**. Logs n8n prunés à 72 h.
7. **Réseau** : sortant scraping modeste (qq Go/mois) ; **vidéo upload-lourd** — ex. 10 vidéos/j × 4 plateformes × 100 Mo ≈ **120 Go/mois egress** + download gen. La plupart des VPS incluent plusieurs To → OK.
8. **Dépendances** : Postgres (cohabitation possible avec celui de streaMLytics en **base/schéma séparé**, ou instance dédiée pour cloisonner) ; Redis si queue mode ; **payants externes = le vrai poste de coût** (API vidéo, proxies).
9. **Colocalisation** : **OUI** avec streaMLytics si gen vidéo déléguée. Airflow (~1,5-3 Go) + Streamlit (~0,3-0,5 Go) + Postgres ≈ **3-5 Go déjà** ; n8n + spikes ffmpeg ajoutent ~2-3 Go transitoires → **tient sur 16 Go avec marge ; 8 Go juste sous pic concurrent**. Pas de GPU local.
10. **Coût** : cf. § 7.

---

## 6. Réponses point-par-point (MT5)

- **OS** : **Windows obligatoire** (terminal MT5 + EAs natifs). Linux = WINE non fiable pour du live.
- **Parallélisme** : 1 compte = 1 terminal (plusieurs charts). Profil ci-dessus = terminal live seul.
- **RAM** : process 0,6-2 Go ; **avec Windows 2,5-4 Go** → **4 Go mini, 8 Go confort**.
- **CPU** : ~négligeable en live (H1) ; **2 vCPU suffisent**. Backtests/optims = ailleurs (PC perso / MQL5 Cloud).
- **24/7** : **oui** (live). **Latence broker non-critique** sur H1 → pas besoin de colocation broker.
- **Disque** : 50-60 Go SSD. **Réseau** : qq Go/mois, **pas d'IP fixe**.
- **Dépendances** : aucune lourde (pas de DB/n8n/dashboard côté MT5 dans ce profil).
- **Colocalisation** : **NON** → **VPS Windows dédié isolé** (OS + stabilité live + sécurité creds broker).
- **Coût** : **~10-20 €/mois** (2 vCPU/4 Go/50-60 Go) ; **VPS broker souvent gratuit** sous condition de volume/dépôt ; backtests sur PC perso (0 €). **La « VPS haute fréquence » actuelle est surdimensionnée → downsize = économie.**

---

## 7. Budget consolidé €/mois

### Décisions FIGÉES 2026-06-11 (choix concrets retenus)

> Cible retenue = **10-50 artistes à 3-6 mois** ; priorité = **le moins cher possible** ;
> **streaMLytics seul d'abord** (n8n/vidéo en couche plus tard sur la même box).

| Poste | Choix retenu | Coût/mois |
|---|---|---|
| **Box A — VPS** | **Hetzner CAX31** (ARM Ampere, 8 vCPU / **16 Go** / 160 Go NVMe) — meilleur €/Go, 16 Go couvre streaMLytics 10-50 *et* le pic combiné n8n+ffmpeg futur | **~12,50 €** |
| ↳ fallback ARM64 | **CPX31 x86** (4 vCPU / 8 Go) si un wheel manque en aarch64 — même prix, resize CPX41 16 Go ~25 € au besoin | ~13,60 € |
| **Domaine** | **`streamlytics.fr`** chez **OVH** (`.com` pris/parké ; `.app` libre en alternative). Resize vertical Hetzner CAX31→CAX41 32 Go (~24,50 €) seulement >50 tenants | ~0,60 € (~7 €/an) |
| **Email envoi** | **SMTP Gmail actuel — inchangé** (vérif/alertes/digest/Stripe). Bascule `noreply@streamlytics.fr`+SPF/DKIM/DMARC = sujet de scale | **0 €** |
| **Email `contact@`** | boîte gratuite **OVH** ou Cloudflare Email Routing (forward → Gmail) | **0 €** |
| **Backup** | `pg_dump` gzippé → Cloudflare **R2 (10 Go gratuits)** (`tools/db_backup.sh`) | **0 €** |
| **TLS** | **Caddy** sur Box A (`app.`/`api.streamlytics.fr`) | 0 € |
| **TOTAL always-on streaMLytics** | | **~13 €/mois** |

> **Note « différence de budget entre les 2 options »** (streaMLytics seul vs +n8n d'emblée) : **≈ 0 € maintenant** — 16 Go (CAX31) couvre les deux scénarios, et Hetzner **resize à la verticale en ~2 min** (même disque). On ne paie le cran 32 Go que quand n8n/vidéo arrivent réellement ET que la charge le justifie. Provisionner « les deux d'emblée » = payer du 32 Go pour une charge vidéo inexistante → inutile.

### Phase validation vidéo (2 mois, ~10 vidéos/jour — POUR PLUS TARD)

| Poste | Spec / choix | Coût |
|---|---|---|
| **Box A — VPS Linux** (déjà payé ci-dessus, +n8n+ffmpeg) | CAX31 16 Go (resize CAX41 32 Go si ffmpeg lourd) | inclus / +12 € si resize |
| **Box B — VPS Windows MT5** (live) | 2 vCPU / 4 Go / 50-60 Go — **VPS broker (souvent gratuit, Windows+RDP prêt)** ou **OVH VPS Windows** (~10-15 €, licence incluse). ⚠️ **PAS Hetzner Cloud** (Linux-only, pas de Windows). RDP par IP = fonction Windows, identique partout. | **~0-15 €/mois** |
| **Génération vidéo** (open serverless, pay-per-call) | LTX-Video/Wan via fal.ai ~0,10-0,30 $/vidéo × ~300/mois | **~30-90 €/mois (variable)** |
| ⚠️ variante premium (si qualité open insuffisante) | Runway/Kling ~1-3 $/vidéo × 300/mois | ~300-900 €/mois ⚠️ |
| **Proxies scraping** (si multi-comptes publication dès le départ) | résidentiel petit plan / Apify pay-per-use | **~50-75 €/mois** |
| **Domaine** | `streamlytics.{com,io,app}` (Cloudflare registrar) | ~1 €/mois (10-15 €/an) |
| **Email pro** (`contact@X`, requis Stripe + délivrabilité) | Zoho / Google Workspace / OVH | ~5-6 €/mois |
| **Backup déporté** | Hetzner Storage Box (`pg_dump` gzippé) | ~3-4 €/mois |
| Redis (queue mode) | conteneur sur Box A | inclus |
| **GPU dédié / loué 24/7** | RTX 4090 cloud | **0 € — À NE PAS PRENDRE** |

**Total infra fixe always-on** (Box A + Box B + domaine + email + backup) ≈ **35-55 €/mois**.
**Total opérationnel phase test** ≈ **~90-210 € sur 2 mois côté infra+gen** + **~50-75 €/mois de proxies** si publication multi-comptes immédiate.

### Passage à l'échelle (post-validation)
- **streaMLytics monte en tenants** → Box A : **CPX31 8 Go → CPX41 16 Go (~27 €/mois)** dès que la concurrence Streamlit pèse (RAM = N × session_state). Seuil = mesurer Mo/session puis `RAM ≈ Mo/session × concurrence-pic`.
- **Vidéo > 50-100/jour soutenus** → réévaluer **GPU serverless batché (~30-60 €/mois)** ou **GPU dédié (~250-400 €/mois)** — décision à 2 mois **avec des chiffres réels**, pas une hypothèse.

---

## 8. Risques & garde-fous (le sizing infra est la partie FACILE)

> L'IA n8n est explicite : **90 % des projets de ce type meurent ailleurs que sur l'infra.**

| Risque | Impact | Garde-fou |
|---|---|---|
| **Bans / shadowban plateformes** | 10 vidéos IA/jour depuis la même IP/compte = drapeau anti-spam | comptes séparés + **pacing humain** + **proxies résidentiels** (~50 €/mois récurrents — plus cher que la gen) |
| **Monétisation lente** | YouTube Partner = 1 000 abonnés + 4 000 h ; TikTok RPM faible sur IA générique | l'argent vient de **l'angle** (affiliation, promo de ton son/produit), pas de la vue brute |
| **Quota upload YouTube** | 1 600 unités/upload, 10 000/jour → ~6 uploads/jour/compte | multi-comptes ou demande de hausse de quota |
| **Saturation qualité** | 10 vidéos absurdes génériques/jour = proba virale faible | **l'angle > le volume** (« fausse influenceuse qui réagit à mon son » ≫ « vidéo random ») |
| **ffmpeg vs collecte Airflow (CPU)** sur Box A 4 cœurs | un render concurrent d'une collecte « Lancer TOUTES » peut saturer | **n8n queue concurrency=1** + planifier les renders **hors fenêtres de collecte** + `nice`/`cpulimit` sur ffmpeg |
| **Disque vidéo non nettoyé** | scratch explose | **nœud cleanup obligatoire** post-publication confirmée + ~20-50 Go réservés |
| **Postgres partagé streaMLytics ↔ n8n** | couplage des domaines de panne (backup/restore, connexions) | **base `n8n_db` séparée** dans la même instance pour la validation ; **instance dédiée** si cloisonnement requis plus tard |
| **n8n webhooks sur le même hôte que le SaaS** | surface d'attaque accrue | n8n derrière Caddy **authentifié**, sous-domaine distinct, endpoints webhook restreints |
| **OOM vidéo tue le trading** | perte de position live | **MT5 sur Box B isolée** (raison structurante du split) |
| **Secret Postgres dans l'historique git** (`Wowow1357911!`) | exposition | **rotation obligatoire** avant exposition (cf. `deployment.md` D0 action #1) |

---

## 9. C6 — Domaine + accès public (PRÉREQUIS, pas cosmétique)

HTTPS exigé par **Stripe** (checkout + webhook) + cookies d'auth + crédibilité. Sans domaine = `http://IP:8501` (inviable).

- **Modèle d'accès déjà construit** : 1 URL publique → register/login → isolation par `artist_id` → chaque artiste voit ses données, connecte ses creds, upload ses CSV ; DAGs paramétrés par artiste. **Il manque juste** : domaine + TLS + reverse proxy + port 443 ouvert.
- **Nom de marque** : vérifier dispo + marque déposée `streamlytics.{com,io,app,fr}`.
- **Registrar** : **Cloudflare** (DNS + proxy/CDN gratuit + anti-DDoS) — comparer **prix de renouvellement** (piège 2e année).
- **Sous-domaines** : `app.X` (Streamlit) + `api.X` (FastAPI/webhook Stripe).
- **TLS** : **Caddy** (Let's Encrypt auto, zéro config) en reverse proxy ; gère aussi cookies `Secure/HttpOnly/SameSite` + HSTS au edge.
- **Email pro** (`contact@X`) : requis Stripe + support + vérifications. **Délivrabilité SPF/DKIM/DMARC** (sinon spam).

---

## 10. Plan d'action (ordre d'exécution)

1. **[décision]** Acter la topologie **Box A (Linux) + Box B (Windows) + serverless GPU + proxies** (ce doc). ✅ tranché.
2. **[Box B]** Provisionner / **downsizer** le VPS Windows MT5 vers 2 vCPU/4 Go (ou basculer sur VPS broker gratuit). Économie immédiate.
3. **[domaine]** Réserver `streamlytics.X` chez Cloudflare + email pro + SPF/DKIM/DMARC.
4. **[Box A]** Provisionner Hetzner **CPX31 (8 Go)** pour la validation ; Caddy + sous-domaines `app.`/`api.`.
5. **[secrets]** Exécuter la checklist **D0** de `deployment.md` (rotation Postgres, `API_SECRET_KEY`, `CORS_ORIGINS`, `APP_BASE_URL`, ufw 22/80/443, Airflow en tunnel).
6. **[n8n]** Déployer **1 instance n8n sur Box A** (Postgres `n8n_db` séparé) ; gen vidéo en pay-per-call (fal.ai/LTX-Video) ; **nœud cleanup** ; **queue mode** dès 2 workflows longs concurrents.
7. **[proxies]** Brancher un proxy résidentiel pour le scraping (isole l'IP).
8. **[mesure]** Sous charge réelle : `docker stats` Box A pendant pic combiné (collecte + render + scrape) → valider 8 Go, sinon **upgrade CPX41 16 Go**. Mesurer **Mo/session Streamlit** pour le seuil de scaling tenants.
9. **[Phase D]** Activer Stripe (Payment Link + env vars + webhook déployé) + pentest sur l'URL.
10. **[revue 2 mois]** Décider GPU dédié vs serverless batché vs arrêt — **avec coût réel/vidéo + taux de monétisation en main**.

---

## 11. Décisions tranchées (résumé pour la roadmap)

| Question (C5/C6) | Décision |
|---|---|
| 1 VPS mutualisé vs split | **Split** : Box A Linux (streaMLytics + n8n) + Box B Windows (MT5) |
| MT5 où | **VPS Windows dédié isolé** ~10-20 €/mo (ou broker gratuit), **downsize** de l'actuel surdimensionné |
| Génération vidéo CPU/GPU | **GPU délégué serverless pay-per-call** (open : fal.ai/LTX-Video) ; **assemblage ffmpeg local** Box A ; **aucun GPU acheté/loué** |
| Scraping isolé ? | **Proxy résidentiel** (isole l'IP), pas un 2ᵉ VPS ; ~50-75 €/mo |
| n8n même hôte ? | **Oui, Box A**, 1 instance ; queue mode si concurrence ; PC perso = dev/test seulement |
| Sizing Box A | **Hetzner CAX31 ARM 16 Go (~12,50 €)** — cible 10-50 tenants ; resize CAX41 32 Go (~24,50 €) >50 tenants. Fallback x86 **CPX31** si ARM64 casse |
| Prérequis CAX31 | **build `linux/arm64` des 3 Dockerfiles validé** (lancé 2026-06-11) ; sinon CPX31 x86 même prix |
| Échelle / RAM | **RAM = fct concurrence Streamlit** (N × session_state) → mesurer Mo/session avant resize 16→32 Go |
| Domaine | **`streamlytics.fr` chez OVH** (~7 €/an ; `.com` pris/parké, `.app` libre en backup) |
| TLS / email | **Caddy** (`app.`/`api.streamlytics.fr`) ; **envoi = SMTP Gmail inchangé** ; `contact@` = boîte OVH/Cloudflare gratuite |
| Budget streaMLytics | **~13 €/mois tout compris** (CAX31 + domaine + email/backup gratuits) ; Box B MT5 + proxies + gen vidéo = à part/plus tard |
| Le vrai risque | **Pas l'infra** → bans/shadowban + monétisation + angle créatif |
