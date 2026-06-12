# ADR-005 — Topologie de déploiement : split 2 boxes + VPS ARM, vidéo serverless

- **Status:** Accepted (décisions figées 2026-06-11 ; provisioning prévu 2026-06-12)
- **Date:** 2026-06-11
- **Deciders:** @1x7xxxxxxx
- **Supersedes:** —
- **Related:** `.claude/dev-docs/benchmark-deployment-synthesis.md` (livrable C5/C6), `.claude/dev-docs/benchmark-deployment.md` (grille de mesure), `.claude/dev-docs/deployment.md` (runbook D-1/D0/D1/D2), roadmap `checklist.md` items **C5/C6/D** ; ADR-003 (React différé → Streamlit reste, ce qui fixe le profil RAM)

## Context

streaMLytics (SaaS multi-tenant dockerisé : Postgres + Airflow + Streamlit + FastAPI) doit
être ouvert au public. Il partage l'écosystème de l'utilisateur avec **2 autres projets** :
**MT5** (trading algorithmique, terminal Windows + EAs) et **n8n** (workflows : génération
vidéo IA, publication réseaux sociaux, YouTube auto, scraping Leboncoin/reels). Question
posée (items C5/C6) : **un seul VPS mutualisé, ou un split ? quel sizing ? quel domaine ?**
Contraintes exprimées : cible **10-50 artistes** à 3-6 mois, **« le moins cher possible »**,
**génération vidéo = pour plus tard**, utilisateur **français**.

Les profils de ressources des 3 charges ont été collectés (IA MT5 + IA n8n) et consolidés
avec le profil streaMLytics dans `benchmark-deployment-synthesis.md`.

## Decision

**Split en 2 machines + délégation de la vidéo + isolation de l'IP de scraping :**

1. **Box A — VPS Linux always-on = Hetzner CAX31** (ARM Ampere, 8 vCPU / 16 Go / 160 Go NVMe,
   ~12,50 €/mo) : streaMLytics **maintenant** ; n8n (orchestrateur) + ffmpeg d'assemblage
   **plus tard sur la même box** (16 Go absorbe les deux). Fallback **CPX31 x86** (même prix)
   si un wheel ne build pas en `linux/arm64`.
2. **Box B — VPS Windows dédié et isolé** : MT5 live 24/7 (~10-20 €/mo ou VPS broker gratuit).
   **Jamais mutualisé** avec Box A.
3. **Génération vidéo IA = GPU serverless pay-per-call** (fal.ai/Replicate, modèles open
   LTX-Video/Wan/CogVideoX). **Aucun GPU acheté ni loué 24/7.** ffmpeg d'assemblage sur Box A.
4. **Scraping = proxy résidentiel** (isole l'IP, pas la machine).
5. **Domaine `streamlytics.fr` chez OVH** ; **TLS Caddy** ; **envoi email = SMTP Gmail
   inchangé** ; `contact@` = boîte gratuite ; **backup `pg_dump` → Cloudflare R2 gratuit**.

Budget streaMLytics ≈ **13 €/mois tout compris**.

## Consequences

### Positive
- **Coût minimal** : ARM (CAX31) = meilleur €/Go ; email/backup à 0 € ; ~13 €/mo total.
- **Marge intégrée** : 16 Go couvre streaMLytics 10-50 tenants **et** le pic combiné n8n+ffmpeg
  futur (~8-10 Go worst case) → pas de seconde box pour n8n, pas de surcoût « au cas où ».
- **Resize vertical Hetzner** (~2 min, même disque) → on monte en CAX41 32 Go seulement quand
  la mesure réelle (Mo/session Streamlit × concurrence) l'exige. La « différence de budget
  streaMLytics-seul vs +n8n-d'emblée » est **≈ 0 € maintenant**.
- **Isolation du trading** : un OOM de la vidéo ne peut pas tuer le terminal MT5 live ;
  les creds broker vivent hors de la surface web.

### Negative / Trade-offs
- **Risque ARM64** : les images Docker doivent builder en aarch64 (dérisqué par un build
  `buildx` préalable ; fallback x86 au même prix si échec). Train/serve reste identique.
- **Postgres partagé streaMLytics ↔ n8n** (plus tard) couple les domaines de panne → base
  `n8n_db` séparée, instance dédiée si cloisonnement requis.
- **CPU contention** : ffmpeg (2-4 cœurs en spike) vs collecte Airflow → planifier les renders
  hors fenêtres de collecte + n8n queue concurrency=1 + `nice`/`cpulimit`.
- **`.fr` au lieu de `.com`** : `.com` était pris/parké ; `.fr` signale une cible FR (moins
  « international ») — acceptable, `.app` reste disponible en backup.
- **Email d'envoi sur Gmail perso** : plafond ~500 mails/j + délivrabilité moindre → bascule
  `noreply@streamlytics.fr` + SPF/DKIM/DMARC à prévoir **au scale**, pas au lancement.

### Neutral / Operational
- Le **vrai risque du volet vidéo n'est pas l'infra** mais bans/shadowban + monétisation +
  angle créatif (souligné par l'IA n8n). Décision GPU dédié repoussée de 2 mois, à trancher
  avec des chiffres réels (break-even ≈ 50-100 vidéos/jour soutenues).
- Publication réseaux + webhooks exigent du 24/7 → n8n vit sur Box A (always-on), pas sur le
  PC perso (non-24/7, dev/test uniquement). n8n = 1 seule instance → tout s'éteint avec l'hôte.

## Alternatives rejected

| Option | Pourquoi rejetée |
|--------|--------------|
| **1 seul VPS pour tout** | MT5 = Windows-only (Linux casse), et son live 24/7 ne doit pas cohabiter avec les rafales vidéo/scraping. |
| **VPS x86 (CPX) par défaut** | ARM CAX31 donne 16 Go pour ~12,50 € (vs 8 Go en CPX31 même prix). x86 gardé en **fallback** si ARM64 échoue au build. |
| **GPU dédié / loué 24/7** | ~250-400 €/mo gaspillés à ~10 vidéos/jour ; break-even ≈ 50-100/jour. |
| **Rendu vidéo IA local sur Box A** | Impossible sans GPU (VPS CPU) — une génération prendrait des heures. Le GPU vit ailleurs (serverless / PC). |
| **2ᵉ VPS pour le scraping** | Inutile : seul l'**IP** doit être isolée → proxy résidentiel suffit. |
| **Box GPU dédiée pour n8n vidéo** | Sur-dimensionné pour un volume sporadique ; serverless pay-per-call est moins cher. |
| **Email pro payant (Workspace) dès le lancement** | Non requis par Stripe ; SMTP Gmail (envoi) + forward gratuit (réception) couvrent la phase validation. |
| **Windows MT5 sur Hetzner Cloud** | Hetzner Cloud = Linux-only, pas de Windows en un clic. ISO custom = BYO-licence + non supporté. |
| **WinBoat / dockur-windows (Windows-en-conteneur) sur Hetzner** | Exige la **virtualisation imbriquée (nested KVM)** que Hetzner Cloud n'expose pas (seul le bare-metal dédié ~40 €+ l'a). Sur ARM (CAX) = émulation x86 inutilisable (MT5 est x86). Et un terminal live 24/7 dans une VM QEMU imbriquée = fragilité inacceptable + casse l'isolation MT5↔streaMLytics. Réservé au PC Linux perso (qui a le KVM) pour des apps ponctuelles. |
| **Domaine `.com` via broker** | Pris/parké depuis 2017 → rachat incertain et cher ; `.fr` libre et le moins cher. |
