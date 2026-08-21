# Master Roadmap Checklist — actif

**Roadmap en deux fichiers.** Celui-ci ne porte que ce qui est **ouvert** ; ce qui est livré
ou clos vit dans `.claude/dev-docs/roadmap/archive.md`. Un item passe de l'un à l'autre par
**déplacement** — jamais par duplication ni par effacement.

| Fichier | Contient | Écrit par |
|---|---|---|
| `checklist.md` (ici) | tâches ouvertes, bugs ouverts, état de reprise | `/roadmap-done`, `roadmap-keeper` |
| `archive.md` | briques livrées, bugs clos | `roadmap-keeper` (rotation seule) |

`tests/test_roadmap_two_files.py` échoue si la somme des items des deux fichiers change :
une rotation qui rétrécit le dénominateur améliore le pourcentage sans rien livrer.

Updated by `strategic-plan-architect` background agent.
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

---

## 📋 Tâches ouvertes (index — détail plus bas)

Index concis des tâches **qu'on peut commencer maintenant**. À la complétion d'une tâche :
`/roadmap-done <id>` la coche dans son bloc détaillé ET la retire de ce tableau **vers
`archive.md`** (CLAUDE.md — flux roadmap). État courant : `## 🔖 REPRISE` ci-dessous.

> **Vide au 2026-08-21, et c'est un état, pas un oubli.** Tout ce qui pouvait être fait
> côté ingénierie l'a été ; ce qui est mesuré inutile est parti sous **ADR-007**, ce qui
> attend une donnée sous **ADR-008**, et ce qui attend un geste humain est dans
> `## 🙋 En attente de toi` juste en dessous. Une tâche revient ici le jour où son
> déclencheur se produit.

| id | tâche | prio | statut / déclencheur |
|----|-------|------|----------------------|
| — | *(aucune)* | — | — |

## 🙋 En attente de toi (aucune ne se débloque sans une action humaine)

Elles restent comptées comme ouvertes — rien n'est supprimé — mais elles ne sont pas dans
l'index ci-dessus parce qu'aucune ne peut commencer sans toi. Chacune dit exactement quel
geste elle attend.

| id | tâche | prio | le geste qu'elle attend |
|----|-------|------|--------------------------|
| R13 | **Régénérer le token Meta System User** — panne confirmée, **23 mois** | P2 | **action utilisateur : Meta Business Manager, je ne peux pas m'y connecter.** Mesuré en production le 2026-08-21 : `meta_insights_performance_day` a `MAX(day_date) = 2024-09-30` et **zéro** ligne dans les 7 derniers jours. La sonde de fraîcheur le rapporte désormais à **16 577 h** de retard. **Deux silences corrigés le 2026-08-21, qui sont la vraie leçon** : (1) aucun contrôle planifié ne demandait si les apps **partagées** authentifient encore — `check_central_apps` existait, branché nulle part ; il tourne maintenant chaque nuit, en tête du sujet et du corps de l'e-mail, et ses sondes vivent dans `src/utils/` parce que `tools/` n'est pas importable dans les conteneurs Airflow (constaté au premier vrai run). (2) La fraîcheur lisait `collected_at` : le DAG réécrivait les mêmes lignes de 2024, l'horodatage d'écriture avançait, et **la source paraissait fraîche**. Classe `freshness-measured-on-write-time`. ⚠️ `check_meta()` passe volontairement au vert sur « REST inconclusive » — c'est normal pour un token System User — donc **c'est la fraîcheur qui alerte pour Meta**, pas l'authentification. |
| R20 | Créer le locataire **canari** en prod + le marquer `is_canary` | P2 | **une seule commande, il ne manque que tes identifiants** : `make canary NAME="Canary <toi>" SPOTIFY=<artist id> YOUTUBE=<UC…>` (ajoute `DRY_RUN=1` pour voir sans écrire). `tools/create_canary.py` crée la ligne, pose le flag, écrit les credentials, et **refuse** deux choses : une identité identique à celle de l'admin — un canari qui emprunte la chaîne de l'admin passe au vert pendant que l'isolation qu'il teste est cassée — et une identité qu'un autre locataire réclame déjà (même règle que le formulaire, R30). Idempotent. Ce qui reste à toi, et que personne d'autre ne peut faire : **choisir tes profils publics**, différents de ceux de l'admin. Les deviner serait la règle « une identité ne se devine jamais » violée par l'outil censé la prouver. Sans ce locataire, `make artist-preflight` s'arrête d'emblée — et il nomme désormais la commande. |
| R18 | `.env` ligne 67 malformée — `docker compose` refuse de démarrer en local | P4 | **action utilisateur** : le fichier est deny-listé dans les permissions, je ne peux ni le lire ni le corriger. Erreur : « key cannot contain a space » ; `python-dotenv` se contente d'avertir, seul `docker compose` refuse. Pour voir la clé fautive **sans exposer sa valeur** : `awk 'NR==67{n=index($0,"=");print (n?substr($0,1,n-1):$0)}' .env`. **Passé de P2 à P4 le 2026-08-21** : il ne bloque plus la vérification. Un Postgres jetable suffit et fait tourner l'intégralité de la suite — `docker run -d --name e2e_pg -e POSTGRES_PASSWORD=x -e POSTGRES_DB=spotify_etl -p 5434:5432 postgres:17`, puis `init_db.sql`, puis `PG_CONT=e2e_pg bash tools/migrate.sh`, puis `DATABASE_URL=postgresql://postgres:x@127.0.0.1:5434/spotify_etl python3 -m pytest tests/ -q` → **858 verts / 14 sautés** au lieu de 716/128. Il ne reste que le confort de `make up`. |
| R17 | Ingérer un corpus ergonomie / front-end dans knowledge-rag | P3 | **action utilisateur** : déposer les PDF/EPUB dans `/mnt/c/Users/timot/knowledge/books/ux-frontend/` puis `cd /home/timothe/knowledge-rag && uv run python ingest.py`. Le domaine est créé et vide ; sans lui, les arbitrages d'ergonomie (dont le budget de graphiques) restent non sourcés. |
| R1 | E1 — beta privée avec des proches sur `streamlytics.fr` | P3 | **actionnable maintenant** (funnel + paiement live validés) |

---

## 🔖 REPRISE — état au 2026-08-21 (à lire EN PREMIER au `/resume`)

**streaMLytics est EN PRODUCTION et lançable.** (détail : `[[project_production_deploy]]`, DEVLOG suites 7→14)

- 🌐 **Live** : https://streamlytics.fr (HTTPS Let's Encrypt · Hetzner **CPX32** Nuremberg `167.233.92.1` · `ssh root@167.233.92.1` via clé WSL `~/.ssh/id_ed25519` · code à `/opt/streamlytics`). Durci (ufw 22/80/443, fail2ban, SSH key-only), backup cron `pg_dump` 3h, postgres `restart: unless-stopped`.
- 💳 **Stripe** : **mode LIVE PROUVÉ end-to-end (2026-06-13)** — KYC validé, 4 env vars live sur le serveur, vrai paiement carte → webhook → `tier=premium` + annulation OK. Portail client actif. (détail : `[[project_stripe_state]]`)
- 👤 **Funnel d'inscription** : **COMPLET et validé en prod** (Brevo → inbox, login par **email** OU username, vérif instantanée, welcome + **2 PDF guide FR/EN** en PJ). Pré-requis **E1 validés**.
- ⚙️ **DAGs** : tous **activés** (étaient en pause par défaut !) → collecte quotidienne par artiste (Meta 5h/Spotify 7h/YT 8h/SC 9h/IG 10h/ML 11h UTC ; CSV watchers 15 min). Si Airflow recréé → ré-`unpause`.
- 🔌 **API REST** : **fonctionnelle en prod** (auth DB `saas_users`, lockout partagé, 2FA refusé, tenant-scoped). `POST /auth/token` → JWT.
- ⚙️ Déploiement = sur le serveur `cd /opt/streamlytics && git pull --ff-only origin main && docker compose up -d --build dashboard` (ou `api`). Compte test QA supprimé.

**▶️ Où on en est (MAJ 2026-08-21) — la file d'ingénierie est vide.**

Prod à jour (`prod == canonique`, 917 colonnes / 91 tables, code déployé == `origin/main`),
**900 tests verts**, `ruff check .` propre sur tout le dépôt, les cinq gardes bloquants de CI
passent. L'index `## 📋 Tâches ouvertes` ci-dessus **ne contient rien**, et c'est un état :
ce qui était mesuré inutile est sorti sous **ADR-007**, ce qui attend une donnée sous
**ADR-008**, et les cinq items restants sont dans `## 🙋 En attente de toi` parce qu'aucun
ne peut commencer sans un geste humain.

**Ce qui t'attend, dans l'ordre où ça débloque le plus :**
1. **R13 — régénérer le token Meta System User.** Meta et Instagram ne collectent plus.
   `make artist-preflight ARTIST=12` le remonte de lui-même. Débloque aussi la partie
   CAPI de R2 le jour où elle revient.
2. **R20 — créer le locataire canari en prod** avec **tes** identifiants publics, différents
   de ceux de l'admin, puis `UPDATE saas_artists SET is_canary = TRUE WHERE id = <id>;`.
   Sans lui `make artist-preflight` s'arrête d'emblée — c'est le filet avant toute session
   avec un artiste réel.
3. **R18 — `.env` ligne 67.** `awk 'NR==67{n=index($0,"=");print (n?substr($0,1,n-1):$0)}' .env`
   n'affiche que le **nom** de la clé, jamais sa valeur. Confort seulement : un Postgres
   jetable fait déjà tourner toute la suite (voir la fiche R18).
4. **R17 — déposer les PDF/EPUB d'ergonomie** dans `knowledge/books/ux-frontend/` puis
   `cd /home/timothe/knowledge-rag && uv run python ingest.py`.
5. **R1 — ouvrir la bêta privée** à des proches sur `streamlytics.fr`. Le funnel et le
   paiement sont prouvés en live ; R2 (landing + pixel + CAPI) démarre avec la première
   campagne, pas avant — voir ADR-008.

**Historique des grandes étapes (toutes ✅) :**
1. **✅ Cloudflare — ACTIF, PROXIFIE & DURCI (complet)** (détail `[[project_security_cloudflare]]`). Fait : zone active, NS Cloudflare, **SSL Full(strict)**, zone settings (min TLS 1.2 / Always HTTPS / Brotli / TLS 1.3), **rate-limit `/auth/token`** (10/10s), **firewall origine verrouillé** (ufw → IP CF only, vérifié), **Bot Fight Mode** ON, **cert Origin CF 15 ans** posé sur Caddy (plus de risque renouvellement, vérifié 2 edges). **RESTE (non bloquant)** : 🔑 **révoquer le token** `streamlytics-hardening` ; (optionnel) ré-activer DNSSEC via CF. ⚠️ vérifs prod **toujours via `curl --resolve host:443:<edge-CF-IP>`** (cache DNS local peut pointer l'IP origine firewallée → faux « down »).
2. **✅ Red-team — COMPLET** (réseau + app + dashboard). Couvert & clean : MITM/TLS (CVE suite), brute-force, SQLi, deps (0 CVE), **isolation tenant/IDOR (prouvé live)**, priv-esc, JWT, CORS, secrets, XSS (escaping tient), **replay webhook Stripe** (signature + handlers idempotents + tolérance 5 min), upload path-traversal (filename = détection seulement), app-DoS (cap 50 Mo + bornes `le=1000` + Cloudflare). **Trouvé+fixé+déployé** : `/kpis` & `/youtube/videos` schema-drift 500 (suite 18/19b) ; **CSV/Excel formula injection sur export (CWE-1236, suite 20)** → `defang_formulas()` sur les 3 chemins d'export + test. Mineur restant : XSRF/cookies Streamlit = défaut framework (P4). Compte test `redteam_qa` **supprimé (clôturé suite 20)**. Classes cataloguées : `api-router-schema-drift`, `csv-formula-injection` (`error-classes.md`).
3. **✅ E1 OUVERT** — 1er beta externe **Benken** (artist_id=12) onboardé 2026-06-15. A révélé une cascade per-tenant (tous les tests credentials KO, tous les CSV sauf Apple KO) → **diagnostiquée + corrigée + déployée** (voir session ci-dessous). 2e tenant **Cuzebo** (id=11) créé aussi.
4. **Actions restantes de l'époque, désormais reprises ci-dessus** : **R13 régénérer le token Meta** (cassé en prod, Meta/IG ne collecte plus) ; **prep pré-session Benken** (partage compte pub Meta 65390907 + bon channel YouTube + Spotify artist ID) ; **R14 onboarding UX restant** (plan Track 1) ; refaire une session live avec Benken (tout doit marcher du 1er coup pour SoundCloud ✅/Apple ✅/YouTube/Spotify).

*Session 2026-08-21 (conformité baseline + capitalisation) : **la config baseline n'est PAS entièrement déployée — 76,2/100** (`audit_fleet.py`), et une partie de ce qui l'est était écrite **pour un autre projet**. Trouvé et corrigé : `rules/python.md` — une règle **contraignante, chargée à chaque session** — imposait un factory Redis, un « ingestion hot path » nommant 5 modules inexistants, et surtout des placeholders SQL `?` (SQLite/QuestDB) là où tout le dépôt utilise `%s` psycopg2 ; `/review-architecture` lisait deux gabarits **non remplis** et cherchait QuestDB + des révisions Alembic (que l'ADR-002 rejette) ; `code-critic` — pourtant nommé dans une règle impérative, donc réellement invoqué — se présentait comme critique du projet « MSDR Predictive Maintenance » ; `security-reviewer` auditait OPC UA et `INFLUX_TOKEN` dans un SaaS musical, doublon de `security-specialist` qui, lui, est correct → retiré, ses 5 appelants repointés. **Capitalisation** : dette de schéma des classes d'erreur 29 → **25**, les 4 classes soldées étant celles du sujet du jour (`central-app-missing`, `multitenant-mono-test-blindspot`, `prod-compose-drift`, `env-not-wired-to-service`) ; aucune classe neuve incomplète (cliquet). 812 tests verts.*

*Session 2026-08-20 quater (actions long terme de l'audit) : **6 items de l'audit livrés**. (1) `make schema-check` ne comparait que les colonnes — étendu aux **contraintes et index uniques, par définition** ; premier passage : 3 dérives prod inconnues → migrations `066` (deux `UNIQUE (campaign_name, platform, placement)` **aveugles au locataire**, deux artistes homonymes ne pouvaient pas coexister) et `067` (3 FK Meta manquantes, 0 orphelin vérifié) — **appliquées en prod**, drift restant = la seule divergence YouTube attendue. (2) Migration `068` : `DEFAULT` retiré et `NOT NULL` posé sur les colonnes de locataire — l'oubli devient fatal ; 805 tests verts contre une base la portant ; **attend le déploiement**. Deux enseignements : `tracks.saas_artist_id` reste volontairement nullable, et `artist_id` **n'est pas toujours le locataire** (VARCHAR Spotify sur 3 tables) → classe `column-name-is-not-its-meaning`, on raisonne sur le type. (3) Unicité d'identité refusée à l'enregistrement sur les 4 plateformes. (4) Le déclenchement de collecte **rend son résultat** et traduit l'échec en geste. (5) Parcours d'inscription testé. (6) Gate DB factorisé (`tests/db_gate.py`). **805 tests**, ruff clean, audit clean.*

*Session 2026-08-20 ter (exécution en production + audit de refactor) : **diagnostic prod confirmé sur données réelles** — `YOUTUBE_CHANNEL_ID` du scheduler = la chaîne de l'admin, GRiNCH détenait ses 67 vidéos, Cuzebo 4556 lignes de stats, et l'admin n'avait plus **aucune** ligne `youtube_videos` (volée par l'upsert). SoundCloud de GRiNCH : ID valide, **0 titre public** côté API — son symptôme exact, désormais diagnostiqué par le produit. **Fait en prod** : sauvegarde, migration 064, identités admin déclarées comme locataire puis retirées de `.env` **et** de `docker-compose.yml` (les défauts en dur y résistaient), 5304 lignes contaminées supprimées, collecte réelle revérifiée. **Deux pannes prod découvertes au passage, sans rapport avec les tests artiste** : les 4 watchers CSV échouaient **toutes les 15 min depuis le 13/08** (`PermissionError` sur le volume `data/`), et **aucune alerte n'était envoyée** car `SMTP_*` n'était câblé qu'au service `dashboard` — 672 échecs muets. Les deux corrigés et vérifiés. **Erreur commise et corrigée** : la migration 065 appliquée avant son code a cassé la collecte YouTube (revert immédiat) → classe `migration-ahead-of-its-code`. **Audit de refactor** : `.claude/dev-docs/refactor-audit-2026-08.md` (le RAG ne couvre ni le refactor ni le multi-tenant ; un passage de Reis & Housley p.387 s'applique). 776 tests verts.*

*Session 2026-08-20 bis (cause racine des deux échecs de test artiste) : **une seule règle implicite expliquait les deux symptômes** — « identité illisible ⇒ prends celle de l'admin », « locataire inconnu ⇒ écris sous `artist_id=1` ». Six mécanismes trouvés et corrigés : (1) **`track_popularity_history` écrivait l'historique de TOUS les locataires sous l'admin** depuis la migration multi-tenant (payload sans clé `artist_id` + `DEFAULT 1`), tous les jours, sans erreur ; (2) l'identité SoundCloud/YouTube/Meta retombait sur les variables d'env, qui portent celle de l'admin (`docker-compose` la codait même en dur par défaut) ; (3) un champ vidé (`""`) valait absence, donc identité admin — le geste le plus probable en session ; (4) le bouton « Lancer TOUTES les collectes », que l'e-mail d'inscription recommande, n'envoyait aucun `artist_id` : collecte de flotte + CSV du répertoire partagé écrits sous l'admin ; (5) les upserts réattribuaient la propriété d'une ligne (`youtube_videos UNIQUE(video_id)` + `artist_id` en `update_columns`) — reproduit en vrai ; (6) `load_platform_credentials`/`get_active_artists` renvoyaient vide sur **panne DB** comme sur « pas connecté ». Rien n'alertait parce qu'`artist_readiness` lit la DB seule : le voyant affichait ⚪ « À connecter » pendant que le tuyau coulait. **Livré** : garde E2E deux-locataires (`tests/test_e2e_two_tenants.py`, prouvée **7 rouges avant / 9 verts après** sur un vrai Postgres), migration `064`, `tools/tenant_contamination_check.py` (a détecté de vraies lignes contaminées), `make artist-preflight` en 5 étapes, `check_central_apps --require`, runbook `runbook-artist-test-session.md`, 4 classes d'erreur P1. 758 tests verts avec DB.*

*Session 2026-08-20 (retour test bêta Grinch du 12/08) : **4 chantiers, 46 tests ajoutés, 678 verts, ruff clean, `audit_runner --deterministic` clean**. (1) **Tests de connexion honnêtes** — les 4 plateformes validaient l'app partagée de l'admin, jamais l'identifiant du locataire : ✅ vert puis 0 ligne collectée. SoundCloud passait au vert sur 0 titre (le symptôme exact de Grinch), Meta ne regardait jamais `account_id`, YouTube ni Spotify l'identifiant artiste. Classe `connection-test-proves-app-not-tenant`. (2) **macOS** — `Ctrl+U`/`F12` codés en dur sur 7 sites : tokens `{{VIEW_SOURCE}}`… résolus par OS (détection User-Agent + bascule), les deux graphies dans le PDF. Classe `guide-single-os-shortcut`. (3) **Ergonomie d'installation** — l'étape 2 devient une sélection à cocher : ce que chaque plateforme débloque, ce qu'elle coûte en minutes, recommandation **Spotify + Instagram**, sélection reportée sur la page Credentials. Découvert au passage : **Instagram était inconnectable** (`ig_user_id` lu par le DAG et la readiness, absent du formulaire) → champ ajouté, classe `identity-read-but-never-collectable`. (4) **Moins de graphiques** — règle « un graphique primaire par décision », le reste replié dans `secondary_analyses()` : instagram 4→2 à l'ouverture, soundcloud 2→1, spotify 4→3, budget verrouillé par `tests/test_chart_budget.py`. Chaque classe a une signature vue rouge avant / verte après.*

*Session 2026-06-19→20 (Benken onboarding + durcissement) : **8 PR mergées+déployées** (prod `96554a2`, 587 tests verts). (1) **Modèle central-app complété** : admin = 1 app/plateforme, artiste = 1 identifiant ; câblage env dashboard manquant corrigé (cause #1 de l'échec Benken) ; SoundCloud env ajouté. (2) **Isolation per-tenant** sur 10 sites DAG (un tenant cassé ne casse plus toute la flotte) + garde-fou `test_dag_fleet_isolation`. (3) **load_dotenv** gardé (soundcloud+instagram). (4) **Détection CSV** élargie. (5) **UX credentials** : ordre facile→difficile, statuts honnêtes (App prête vs Connecté), guides Spotify/YT réécrits. (6) **Durcissement** : `test_env_contract` (code-lit ⊆ service-déclare), préflights boot dashboard/api, `test_compose_parity`, alerting per-tenant (freshness + escalation consécutive), ADR-006, `tools/{prod_introspect,check_central_apps}`, 6 classes d'erreur. (7) **Boucle fermée readiness per-artiste** : `artist_readiness()` + vue 🚦 Santé onboarding + flag alert_monitor — Benken meta=🔴 (compte non partagé) remonté auto. (8) **Validation au connect** Spotify (résout l'artiste dans le form). ⚠️ Le plan de cette session (« Tracks 1/2/3 ») **n'a jamais été commité** et n'existe nulle part : `git log --all -- .claude/plans/` est vide et le chemin n'est pas gitignoré. C'était un fichier local, perdu. R14 a donc pointé pendant deux mois un périmètre introuvable — trouvé le 2026-08-21 en élargissant `check_config_refs.py` à la roadmap. Le périmètre a été **reconstruit depuis le code** (voir R14) ; les libellés A6/A7/E/F/G du plan d'origine ne sont pas récupérables.*

*Session 2026-06-13 (suites 12→14) : Stripe live prouvé ; 4 bugs corrigés (nav login-bounce #46, date période #47, fuite fraîcheur Spotify #48, « Aucun DAG trouvé »/AirflowMonitor env-first #53) ; audit isolation tenant (#49 : `require_artist_scope` + P3) ; `/ml/predictions` réparé & P4 fermée (#50) ; cadence freshness #51 ; **Postgres-en-CI #52 (P3 fermée, render-smoke 39 vues en CI)** ; pentest A-D (#54 `/openapi.json` fermé) ; DAGs activés ; **API REST fonctionnelle en prod #56** ; analyse d'impact config/prod = classe « config.yaml absent » entièrement contenue sur le chemin runtime.*

---

## Open Bugs

### 🔍 Audit 2026-06-13 — deep multi-dimension (suite 19)

Audit profond post-red-team (perf · correctness · supply-chain · tests · tech-debt), **vérifié en live contre le schéma + données prod**. **Bilan : 1 vrai bug prod + 1 gap de test systémique ; le reste = tech-debt P4 basse urgence. Aucun nouveau risque sécurité/critique.**

**P3 — CORRIGÉ (suite 19b, déployé + vérifié live) :**
- [x] **`/youtube/videos` API cassé (HTTP 500) — schema drift, MÊME CLASSE que `/kpis`** — sélectionnait `views/likes/comments/title` sur `youtube_video_stats` (vraies colonnes `view_count/like_count/comment_count`, pas de `title`). **FIXÉ** : requête sur `youtube_videos` (catalogue par-vidéo : title + view_count/like_count/comment_count). Mergé PR #62, déployé, `/youtube/videos` = **200** confirmé live. *(8 routers audités, youtube était le dernier cassé.)*
- [x] **Gap de test systémique = cause racine `/kpis` + `/youtube`** — les 2 bugs avaient échappé aux tests (routers testés **DB mockée**). **FIXÉ** : `tests/test_api_db_smoke.py` — smoke-test **DB-gated** (comme `test_views_render_smoke`) qui exécute chaque endpoint data contre le vrai schéma (token admin+tenant forgé) et assert no-500 → attrape toute la classe en CI. Aurait fait échouer /kpis ET /youtube.

**P3/P4 — correctness borderline :**
- [x] **2 collectors `return None`** ✅ (2026-06-14) — `youtube_collector.py:45` (chaîne introuvable) **escaladé en `raise ValueError`** (vrai échec → plus de 0-rows-DAG-SUCCESS) + test de non-régression `test_get_channel_stats_raises_on_channel_not_found`. `instagram_api_collector.py:294` (insights code-100, 1 média) **confirmé skip par-item légitime** (l'appelant filtre `None` L322) + commenté explicitement. `_meta_config_fetch.py:168 return []` = 0-créative valide, hors-scope.

**P4 — tech-debt / opportunités (basse urgence) :**
- [ ] **Caching** — 4 vues requêtent la DB sans `@st.cache_data` (`spotify_s4a_combined`, `meta_ads_overview`, `export_pdf/csv`, `usage_analytics`). Bénéfice **modeste** à l'échelle actuelle (requêtes <1ms mesurées) ; vrai levier LCP = cache Cloudflare (en cours). Effort M.
- [ ] **`view_session()` migration** — 16 vues encore en `get_db_connection()` legacy (valide mais non-conforme rule #9). Tech-debt, **pas un leak**. Effort M.
- [ ] **171 fonctions >40 lignes** (règle projet) — surtout des `show()` Streamlit (jusqu'à 502 l. `meta_ads_overview`). Lisibilité. Effort L. (cf. `refactor-audit-dashboard.md`)

**Mesuré & ÉCARTÉ (FP / non pertinent — ne pas re-auditer) :**
- Index `s4a_song_timeline(artist_id, song, date)` → **prématuré** : EXPLAIN ANALYZE = **0.4ms** sur 13794 lignes via l'index `(artist_id,date)` existant. Revisiter à ~10× volume.
- `API_SECRET_KEY` → **SET (64 chars) en prod** : JWT stables au restart, non-issue.
- Sweep schema-drift : 132 candidats bruts → **tous FP sauf le router youtube** (alias `col AS x`, vars f-string `{filt}/{frag}`, fonctions SQL, littéraux, commentaires FR, ON CONFLICT/EXCLUDED).
- Deps `uv.lock` **0 CVE** ; imports morts **0** (ruff F401) ; data-integrity (filtre 1x7 / scoping tenant / clés upsert) **clean** ; secrets git history **0**.

### 🚀 Base d'optimisation différée (P4 — déclencheur : ÉCHELLE, pas maintenant)

**FAIT (gratuit, via Cloudflare, ROI élevé, zéro risque)** : cache edge du bundle JS Streamlit (`cf-cache-status: HIT` → attaque le LCP 5.7s), **HTTP/3 + Early Hints + 0-RTT**, Brotli, min TLS 1.2. → *Le vrai levier perf (livraison) est en place.*

**DIFFÉRÉ — à réévaluer à ≥ ~50 artistes actifs / trafic multi-tenant concurrent réel.** Sur la prod actuelle (mono-tenant sain, requêtes <1ms), ces items sont **faible ROI + risque de régression** → on ne refactore pas pour des micro-gains. Cataloguées dans `error-classes.md` (`view-session-adoption`, etc.) + visibles dans graphify (god-nodes).

- [ ] **Caching `@st.cache_data(ttl=300)` sur les 4 vues lourdes** (`spotify_s4a_combined`, `meta_ads_overview`, `export_pdf/csv`, `usage_analytics`). *Gain* : évite la re-requête à chaque rerun Streamlit. *Risque* : cacher la donnée pure (pas `db`/connexion → unhashable), staleness TTL. *Déclencheur* : trafic concurrent / re-renders fréquents ressentis. Effort M.
- [ ] **Migration `view_session()` (16 vues legacy `get_db_connection()`)** — classe `view-session-adoption`. *Gain* : robustesse connexions (graphify : `get_db_connection` = 57 edges). *Risque* : refactor mécanique 16 fichiers = régression. *Déclencheur* : ≥50 artistes / si un leak de connexion apparaît. Effort M.
- [ ] **Splitter les god-functions** (`collect_report_data()` = 69 edges, + 171 fonctions >40 l. règle projet). *Gain* : lisibilité/maintenabilité, **pas perf**. *Risque* : élevé si fait en masse. *Déclencheur* : **au fil de l'eau** quand on touche déjà le fichier (jamais en sweep dédié). Effort L.
- [ ] **Lazy imports** (plotly/sklearn/shap en tête de vue → différer dans les fonctions). *Gain* : cold-start par vue. *Risque* : faible mais large. *Déclencheur* : si latence par-vue ressentie. Effort M.
- [ ] **Index composite `s4a_song_timeline(artist_id, song, date)`** — **prématuré aujourd'hui** (mesuré 0.4ms / 13794 lignes). *Déclencheur* : **~10× le volume de données** (≈140k lignes) ou EXPLAIN qui régresse. Effort S.

## Brick Status

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.

### Standing ops — incident-driven (no code action)

These are not roadmap bricks; they are operational standing instructions kept here for visibility.

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, Railway env vars. Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".

---

## Long-term ML hardening (roadmap)

- [x] **Phase-2 data acquisition — CLOSED AS MANUAL (2026-06-10, ADR-004).** The 2 ex-imputed features are now sourced from manual entry: `NonAlgoStreams28Days` → `s4a_song_nonalgo_streams`, `HowManySongsDoYouHaveInRadioRightNow` → `s4a_artist_radio_count` (migration 052), captured in the Saisie S4A form, read by `ml_inference.build_features` (default 0 when no entry). **Automatic capture rejected:** the artist confirmed S4A shows the source split on-screen only (no CSV export → parser+watcher impossible), and scraping the authed S4A UI is ToS-violating + per-tenant-credential-heavy + fragile (see ADR-004). **Reopen only if** Spotify exposes the split via a CSV export or official API → then a cheap DistroKid-style parser+watcher. 416 tests pass.
- [x] **Discovery Mode manual input** — DONE 2026-05-31. `migrations/040_s4a_song_discovery_mode.sql` (table mirrors `s4a_song_playlist_adds`: per-song dated opt-in, latest `recorded_at` wins) + `init_db.sql` + `_ALLOWED_TABLES`. `ml_inference.build_features` sources `IsThisSongOptedIntoSpotifyDiscoveryMode` from the latest manual entry (default 0.0). `trigger_algo` gains a "🔭 Discovery Mode" metric + manual opt-in form (after Ajouts playlist). Kept in `_IMPUTED_FEATURES` (drift-excluded) — bounded binary flag, z-score drift is meaningless. End-to-end verified (feature flips 0→1 on opt-in); render-smoke + 321 pytest green. Marginal SHAP weight (rank 13) but un-imputes one of the 3 sourceless features with zero external API.
> **Framing (2026-06-11): input-feature data is DONE — these 4 are TIME-ACCRUAL-blocked, not input-blocked.**
> Manual S4A entry (mig 052) + fresh stream CSVs closed the *input-feature* gap: a single prediction now has all 13 real features. What remains needs data that **accumulates over time / across tenants** and cannot be backfilled by entering today's values: more labelled rows, several tenants, forward trigger-outcomes, a long saves history. Do **not** re-scope these as "blocked on data entry" — the entry is done.

- [ ] **More training data + per-tenant evaluation** — model trained on N=508 / 102 test (single anonymised set). **Blocker = tenant count + label volume, not features:** still one live tenant; entering your own data does not create cross-tenant generalisation evidence. Accumulate live labelled data across artists before trusting absolute probabilities.
- [ ] **Automated retraining on live outcomes** — `data_anon.csv` is a one-time snapshot. **Blocker = forward outcomes accruing in time:** needs `ml_song_predictions` to gather real trigger results (score → submit to playlists → observe DW/RR/Radio weeks later).
  - [x] **Outcome-labelling loop — BUILT 2026-06-12** (the "next concrete sub-step"). `migrations/060_ml_outcome_labeling.sql`: `s4a_song_algo_outcomes` (manual capture of realized DW/RR/Radio 28d streams per song — S4A has no source-split export, ADR-004) + `ml_prediction_outcomes` (training-ready labelled pairs). Pure engine `src/utils/ml_outcome_labeling.py` (`bin_label` with training thresholds 137/130/639, `match_outcome` = earliest snapshot ≥28d post-prediction, `label_predictions` idempotent join). Weekly DAG `ml_outcome_labeling` (Mon 06:00 UTC) + debug. Saisie S4A view extended with a realized-outcome grid (the capture surface). 10 tests, end-to-end verified live (labels (1,0,1) + idempotent re-run), DAG parses in-container. **Labels now accrue whenever you enter realized outcomes** — closes the input half.
    - [x] **Windowed capture + chart 2026-06-12** — `migrations/061`: `s4a_song_algo_outcomes` made window-aware (`time_window` 7d/28d/custom + `period_start/end`; columns renamed `dw_streams`/`rr_streams`/`radio_streams`). Saisie S4A grid now captures 7j+28j + a custom-period section. New Road-to-Algo tab "📈 Streams algos générés" (`_tab_algo_streams.py`): stacked bar = cumulative total + per-playlist (DW/RR/Radio) contribution, with a 7d/28d/custom selector + KPI cards. **The labelling engine still reads ONLY `time_window='28d'`** (model horizon) — 7d/custom are tracking-only. Verified live: labelling ignores 7d/custom decoys, uses 28d. The reframed need (per user): not predicting *when* algos trigger, but measuring *how many streams* they generate once triggered.
  - [ ] **Champion/challenger retraining DAG** — consume accumulated `ml_prediction_outcomes` pairs to retrain + compare vs the live model. Still genuinely blocked: needs enough labelled cycles to have accumulated (forward time + entries). Build once `ml_prediction_outcomes` has a meaningful row count.
- [ ] **RR volume regressor** — suppressed (R²=0.23 group-CV on the log target, notification-CTR noise — v3 honest figure, was misreported ≈0.55). **Phase-2 features have now landed (mig 052) but did NOT lift this:** R²=0.23 is measured on the training set, which already contained both features — serving them live changes serving, not the fit. Revisit needs more/better training *volume* (ties to the two items above); stays classification-only meanwhile.
- [ ] **Resurrection tuning** — thresholds in `detect_saves_resurrection` (min_age 180d, 2x baseline, min_spark 50) are heuristic; recalibrate once a real **saves time-series** exists (an old song's saves spiking months later) — a longitudinal history, not a snapshot.

---

## Pré-déploiement program (2026-06-09)

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.

### E — Post-déploiement : beta privée → growth (séquencé, 2026-06-11)

> **Ordre imposé par l'utilisateur** : déployer (D) → **tester l'app avec des proches (beta privée)** →
> **seulement ensuite** landing + marketing payant. On ne lance pas d'acquisition payante sur une app
> non éprouvée. Détail archi : ADR-005 (déploiement) + `deployment.md`.

- [ ] **E1 — Beta privée avec des proches** (P3, AVANT tout marketing) — `streamlytics.fr` déployé mais
  diffusion **restreinte** (lien partagé à la main, pas de pub). Objectif = éprouver le funnel réel
  (register → vérif email → connexion credentials → upload CSV → KPIs → export) sur des comptes tiers
  réels, détecter les frictions d'onboarding et les bugs multi-tenant que le seul tenant `1x7xxxxxxx`
  ne révèle pas. Sortie = liste de frictions corrigées avant E2.
  Leviers déjà en place : compteur « Live Activity » (`register.py`), onboarding tracker (Brick 29).
  ✅ **PRÉ-REQUIS VALIDÉS 2026-06-13** (test beta réel `127bpmin@gmail.com`, plusieurs passes) : D fait (HTTPS
  live) ; **délivrabilité email résolue** → Brevo + domaine authentifié (DKIM/DMARC), `noreply@streamlytics.fr`
  → **boîte de réception** (le Gmail perso tombait en spam) ; funnel **complet et poli** : inscription allégée
  (nom+email+mdp, slug/username auto-cachés), **login email OU username**, vérif instantanée, welcome + **2 PDF
  FR+EN** en PJ. Bugs corrigés : SMTP env-first (#35), page vérif bloquante (#36), expéditeur dédié (#37),
  app-password Gmail, rebrand (#40), guide bilingue (#43). **Reste** : décider le moment d'inviter + i18n du
  *contenu* des emails (anglais, non bloquant).

- [ ] **E2 — Landing page marketing + pixel + CAPI** (P3 growth, APRÈS E1) — promouvoir l'app via
  campagnes (Meta/Google/TikTok). **Contrainte structurante : Streamlit ne peut pas héberger de pixels
  client** (strippe `<script>`, sandbox iframes `components.html`, re-run complet — cf. item PostHog
  différé § « Deferred »). Donc :
  - [ ] **Landing statique SÉPARÉE de l'app** : `streamlytics.fr` (racine + `www`) → landing **statique**
    (reco **Astro/HTML+Tailwind servi par Caddy** sur Box A = 0 €, contrôle total des `<script>` ;
    alternative no-code Framer/Webflow ~10-25 €/mo). `app.streamlytics.fr` = Streamlit (inchangé),
    `api.streamlytics.fr` = FastAPI. **Ne jamais mettre de pixel dans l'app Streamlit.**
  - [ ] **Pixel client sur la LANDING uniquement** : Meta Pixel + GA4 `gtag` + (option) TikTok pixel →
    `PageView`, `ViewContent`, `Lead` (clic CTA « Essai gratuit »). **Bannière de consentement RGPD +
    Consent Mode v2 AVANT chargement** (UE ; processeur tiers à déclarer dans la privacy policy).
  - [ ] **CAPI server-side depuis FastAPI** (obligatoire ici, pas optionnel) pour les conversions
    profondes que le pixel client rate (cross-domain, ad-block, iOS14) : `CompleteRegistration` à
    l'inscription, `Subscribe`/`Purchase` **branchés sur le webhook Stripe existant**
    (`checkout.session.completed`). Réutilise le SDK `facebook-business` déjà dans `requirements.txt`
    (POST `graph.facebook.com/{PIXEL_ID}/events` + `access_token`). Idem GA4 Measurement Protocol.
  - [ ] **Pont d'attribution (stitching)** — GRATUIT grâce aux sous-domaines : le pixel pose `_fbp`/`_fbc`
    (contient `fbclid`) sur le **domaine parent `streamlytics.fr`** → **lisibles par FastAPI sur
    `api.streamlytics.fr`**. Au register : persister `_fbp`/`_fbc` + `UTM`/`fbclid`/`gclid` (passés en
    query string landing→app) + **email hashé SHA-256** + IP + user-agent sur la ligne user. **Dédup
    pixel↔CAPI par `event_id` partagé.** Jamais d'email en clair (Meta exige SHA-256).
  - **Mapping d'événements exact** (quel event à quelle étape) à préciser au moment de l'implémentation.
  - Note : le `usage_events` server-side (first-party) peut rester comme sink interne ; PostHog
    client-side reste différé (Streamlit) — cf. § « Deferred ».

## Deferred — revisit ONLY if migrating to React (ADR-003 reversal)

Items that are currently irrelevant / worked-around **because of Streamlit** and would become
natural (or need redoing) under a React/Next.js front-end. Parked here per user request
(2026-06-09) so a future migration picks them up. ADR-003 currently keeps Streamlit.

> **PARKED — not open backlog.** Listed as plain bullets (no `[ ]`) **on purpose** so `/resume`
> does not recount them as actionable items. They re-activate only on an ADR-003 reversal
> (migration to React/Next.js). Do not treat them as a to-do until then.

- **PostHog full client-side analytics** — autocapture, **session replay**, heatmaps,
  client funnels/retention. Blocked today: Streamlit strips `<script>` and sandboxes
  `components.html` iframes, and re-runs the whole script (no stable DOM / client event model).
  Under React the standard JS snippet drops in → reconsider PostHog (cloud-w/-consent or
  self-host) and likely retire the homegrown event log's *capture* layer (the `usage_events`
  table can remain as a server-side sink). Needs RGPD consent banner for a 3rd-party processor.
- **Interactive / exact-parity report charts (PDF & in-app)** — the PDF export rebuilds
  every chart in **matplotlib→PNG** (`pdf_charts.py`) because `kaleido` (Plotly→image) is absent
  and Streamlit can't headless-render its Plotly figures. Under React, reports could share the
  *same* chart components (client-side render / a proper reporting service), giving interactive
  + pixel-parity charts and removing the matplotlib duplication. ref: export-pdf overhaul
  2026-06-09.
- **Cold-start bundle / perf** — already audited (line ~295): the #1 cold-start bottleneck
  is the **Streamlit JS bundle** (~532 KiB), not Python. React+Next (code-splitting → ~100–150
  KiB initial) is the structural fix. Python-side caching/lazy-import work stays valid for
  subsequent renders only.
- **Rich client interactions** — anything that fought the rerun model (live event hooks,
  drag/drop, fine-grained widget state, real-time updates without full reruns) becomes
  first-class under React; revisit UX patterns that were simplified to fit Streamlit.
