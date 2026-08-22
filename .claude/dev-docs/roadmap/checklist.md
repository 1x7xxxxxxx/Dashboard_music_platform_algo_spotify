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

> **Vide au 2026-08-22 (séance du jour).** Les neuf entrées ouvertes par la nuit du
> 21→22 — R23 à R31 — sont closes et archivées, **et R22 aussi** : le test d'intrusion
> réseau se fait depuis n'importe quelle machine hors du VPS, celle-ci comprise, et le
> fuzzing contre une instance locale du même code. Il ne reste qu'une entrée, dans
> `## 🙋 En attente de toi` juste en dessous, et elle se décompose en trois gestes dont
> aucun n'est du code : déployer (je peux, sur ton feu vert), donner au canari les trois
> identités qui lui manquent (SoundCloud/Meta/Instagram — ce sont TES comptes), inviter
> des gens. Ce qui a été **décidé** plutôt que fait
> porte son ADR : **ADR-007** (mesuré inutile), **ADR-008** (attend une donnée),
> **ADR-009** (deux registres s'accordent au lieu de dériver, ex-R31).
> Une tâche revient ici le jour où son déclencheur se produit.

| id | tâche | prio | statut / déclencheur |
|----|-------|------|----------------------|
| — | *(aucune)* | — | — |

## 🙋 En attente de toi (aucune ne se débloque sans une action humaine)

Elles restent comptées comme ouvertes — rien n'est supprimé — mais elles ne sont pas dans
l'index ci-dessus parce qu'aucune ne peut commencer sans toi. Chacune dit exactement quel
geste elle attend.

📋 **Procédures pas à pas, avec leur vérification :
`.claude/dev-docs/runbook-actions-utilisateur.md`** — classées par ce qu'elles
débloquent, chacune avec la commande qui prouve que c'est fait. `tests/test_roadmap_index_is_honest.py`
échoue si une ligne d'ici n'a pas sa section là-bas.

| id | tâche | prio | le geste qu'elle attend |
|----|-------|------|--------------------------|
| R1 | E1 — beta privée avec des proches sur `streamlytics.fr` | P3 | **trois gestes, tous à toi.** (a) déployer la séance du 2026-08-22 : `make deploy` puis `make migrate-prod` (la **072** est nouvelle ; `make sync-check` la nomme aujourd'hui comme seule dérive) — je peux le faire sur ton feu vert. (b) **compléter le filet** : la préflight du canari prod (`artist_id=14`) est verte pour **Spotify et YouTube seulement** — mesuré le 2026-08-22, pas « de bout en bout » comme cette ligne l'a affirmé jusqu'ici. SoundCloud, Meta et Instagram n'ont **aucune identité** sur le canari, donc rien ne les prouve — et ce sont exactement les deux plateformes qui ont cassé chez Benken (Meta) et GRiNCH (Instagram). Il faut TES identifiants : user id SoundCloud, ad account Meta, IG Business Account. (c) inviter les gens. Runbook §5. |

## 🔖 REPRISE — état au 2026-08-22 (à lire EN PREMIER au `/resume`)

**▶️ L'index actionnable est vide, et R22 est close.** R23→R31 livrées, gardées et
archivées dans la même séance ; le pentest n'a plus aucun volet ouvert. Il ne reste
qu'**une** entrée sur toute la roadmap : R1, ouvrir la bêta — et c'est la seule qu'aucune
machine ne peut faire à ta place, parce qu'elle consiste à inviter des gens.

**R22 close, et son ⅔ manquant n'attendait personne.** Je l'avais classé « en attente de
toi » sur un raisonnement faux : le test d'intrusion réseau demande une machine *hors du
VPS*, et celle-ci en est une. Ce que ça a donné —

- **Scan de l'origine (167.233.92.1), 33 ports** : seul **22** répond. Postgres 5433,
  Airflow 8080, Streamlit 8501 fermés, et même 80/443 injoignables en direct. Les noms
  d'hôte résolvent sur Cloudflare, donc ils n'ont **pas** été scannés — c'est
  l'infrastructure d'un tiers.
- **TLS des trois noms** : aucun protocole obsolète accepté, ni Heartbleed, ni CCS
  injection, ni ROBOT, certificats valides 5/5 magasins (expirent le 2026-11-09).
- **Un écart réel** : le dashboard renvoyait 4 en-têtes de sécurité, l'API 6 — les deux
  de plus viennent du middleware FastAPI, pas de Caddy, donc l'écart était invisible
  depuis le dépôt. `deploy/Caddyfile` corrigé. ⚠️ **non validé par un binaire Caddy** ici.
- **Fuzzing** : un vrai 500. `GET /streams/timeline?song=a%00b` — un octet NUL atteint
  psycopg2 et lève une `ValueError` que personne ne rattrape. Fermé à la frontière,
  gardé, re-fuzzé sur **4 graines / 1730 cas / zéro 5xx**.

**⚠️ Ce qui n'est PAS fait : rien de tout ça n'est déployé.** Le travail est dans
l'arbre local, non commité. `prod == canonique` décrit l'état d'AVANT cette séance.
Avant de déployer : `make migrate-prod` (la **072** est nouvelle), puis `make deploy`,
puis `make sync-check`.

**Avant de conclure quoi que ce soit :**
```
docker start postgres_spotify_airflow && python3 -m pytest tests/ -q
```
~160 tests exigent une base et **skippent en silence** sans elle. Toute la séance a
tourné avec la base : **1312 verts, 0 rouge**, ruff propre, `audit_runner
--deterministic` clean, `make config-check` clean.

**Ce que la séance du 2026-08-22 (jour) a livré :**

- **R23 — la page d'inscription n'est plus un oracle.** Réponse identique que l'adresse
  existe ou non (avec un e-mail « ce compte existe déjà » au vrai propriétaire, sinon on
  ment à l'honnête) ; codes promo validés APRÈS création ; budget par IP ; message
  d'erreur générique portant une référence d'incident.
- **R24 — une révocation révoque.** `active`/`role`/`artist_id` relus en base (30 s côté
  dashboard, chaque requête côté API) et `saas_users.token_version` (migration **072**)
  porté par le JWT. Les deux surfaces échouent en sens INVERSE sur une panne de base :
  dashboard ouvert, API fermée — délibéré, argumenté dans le code.
- **R25 — la règle #7 rétablie, sur 9 vues et pas 4.** Le balayage a trouvé
  `artist_id_sql_filter()`, par où ~30 vues atteignent la base. `tenant_scope()` porte la
  désambiguïsation une fois.
- **R26 — le second facteur coûte quelque chose.** Le compteur de compte n'est plus remis
  à 0 par le mot de passe quand un code est encore dû, un code faux compte, et le budget
  est par IP (un nouvel onglet ne le rembourse plus).
- **R27 — le détecteur de contamination dérive du schéma.** Il connaissait 8 tables sur
  ~70 et aucune entrée Spotify. Il a immédiatement trouvé `youtube_channel_history`.
- **R28 — dette de schéma soldée** : 76 → 81 classes, **100 %** portent `root_cause` et
  `long_term_fix`. Le contrôle CI passe de *advisory* à **bloquant**, comme son propre
  commentaire le demandait.
- **R29 — le budget de graphiques compte enfin ce que Few compte** : ce qui est dans le
  coup d'œil, pas ce qui est dans le fichier. `data_wrapped` passe de 9 à **1** — il était
  signalé à tort.
- **R30 — les 9 constats BAS traités**, dont une clé Fernet valide retirée du CI (générée
  par run), `src/utils/http_logger.py` **supprimé** (zéro importateur), et le logout qui
  laissait `totp_secret` en session.
- **R31 → ADR-009** : décision enregistrée plutôt que dette. Le garde d'accord a reçu son
  plancher de non-vacuité.
- **Cinq classes d'erreur capitalisées**, chacune avec une signature vue rouge sur le
  défaut et verte après.

**Ce que la séance a appris, et qui vaut plus que les correctifs** : trois fois sur
neuf, la portée du garde était une **liste écrite à la main** — les 8 tables du détecteur
de contamination, les 10 verbes français du garde de roadmap, les 6 clés de session du
logout. C'est la classe `guard-scope-is-a-hand-written-list`, et elle était déjà nommée
dans le REPRISE d'hier. Une liste ne signale jamais ce qu'elle ne couvre pas.

**Un défaut trouvé en lisant ce fichier** : `checklist.md` portait un bloc mort de
~70 lignes (un index périmé disant « aucune », une table « en attente » sans R22, un
doublon de R21) sous un titre cassé, `## 🔖 REPRISE\` ci-dessous.`. Un `/resume` qui
tombait dessus lisait « aucune tâche ouverte ». Retiré.

## 🔖 Historique — état au 2026-08-21

**streaMLytics est EN PRODUCTION et lançable.** (détail : `[[project_production_deploy]]`, DEVLOG suites 7→14)

- 🌐 **Live** : https://streamlytics.fr (HTTPS Let's Encrypt · Hetzner **CPX32** Nuremberg `167.233.92.1` · `ssh root@167.233.92.1` via clé WSL `~/.ssh/id_ed25519` · code à `/opt/streamlytics`). Durci (ufw 22/80/443, fail2ban, SSH key-only), backup cron `pg_dump` 3h, postgres `restart: unless-stopped`.
- 💳 **Stripe** : **mode LIVE PROUVÉ end-to-end (2026-06-13)** — KYC validé, 4 env vars live sur le serveur, vrai paiement carte → webhook → `tier=premium` + annulation OK. Portail client actif. (détail : `[[project_stripe_state]]`)
- 👤 **Funnel d'inscription** : **COMPLET et validé en prod** (Brevo → inbox, login par **email** OU username, vérif instantanée, welcome + **2 PDF guide FR/EN** en PJ). Pré-requis **E1 validés**.
- ⚙️ **DAGs** : tous **activés** (étaient en pause par défaut !) → collecte quotidienne par artiste (Meta 5h/Spotify 7h/YT 8h/SC 9h/IG 10h/ML 11h UTC ; CSV watchers 15 min). Si Airflow recréé → ré-`unpause`.
- 🔌 **API REST** : **fonctionnelle en prod** (auth DB `saas_users`, lockout partagé, 2FA refusé, tenant-scoped). `POST /auth/token` → JWT.
- ⚙️ Déploiement = sur le serveur `cd /opt/streamlytics && git pull --ff-only origin main && docker compose up -d --build dashboard` (ou `api`). Compte test QA supprimé.

**▶️ Séance du 2026-08-22 (nuit) — pourquoi « les credentials ne marchaient pas » : rien n'était en panne.**

Deux sessions artiste avaient échoué là-dessus. En cherchant ce qui restait après tous
les correctifs par symptôme, la réponse est plus simple et pire : **les deux
plateformes que l'onboarding recommande en premier échouaient sous les yeux de
l'artiste**, sans qu'aucune infrastructure ne soit en panne.

| # | ce qui se passait | mesuré |
|---|---|---|
| 1 | **La matrice Spotify lisait la table CSV.** Test de connexion vert nommant l'artiste, DAG qui collecte, écran 🔴 « Connecté — aucune donnée » jusqu'à un import CSV. | Spotify était jugée sur **quatre tables** selon l'écran. Vérifié en prod après correctif : le canari a **0 ligne CSV, 10 lignes API**, et readiness dit `ok`. |
| 2 | **Enregistrer un identifiant Instagram déclenchait `meta_ads_api_daily`**, jamais `instagram_daily` — aucune première collecte. L'entrée `'instagram'` de la carte était inatteignable par construction. | Le fichier se lisait comme si la fonctionnalité existait. |
| 3 | **L'onglet Meta mentait à chaque sauvegarde** : « ⚠️ Le renouvellement automatique ne fonctionnera pas », pour tout artiste, parce qu'il lisait trois champs que le formulaire ne déclare pas. Bouton de rafraîchissement idem. | Retiré, pas réparé : sous ADR-006 le token est central et n'expire pas. |
| 4 | **Instagram était exemptée de tout** : pas d'unicité d'identité (deux locataires pouvaient revendiquer le même compte en silence), pas de test de connexion, absente du canari et de l'alerte. | La même carte existait en **six exemplaires**, dont deux amputés. |
| 5 | **Un garde vert tenait le trou en place** : un test affirmait l'égalité entre les deux copies fausses, et les tests d'unicité se paramétraient sur la copie amputée — une entrée manquante y **retire des cas** au lieu d'en faire tomber un. | Vérifié par contraste : Instagram retiré, les paramétrés restent verts (8), seul le cliquet littéral tombe. |
| 6 | **Une sonde en panne s'affichait « Connecté — aucune donnée »** — `freshness_monitor` posait un champ `error` pour ça, personne ne le lisait. | Statut `BROKEN` ⚠️ qui ne demande **rien** à l'artiste. |
| 7 | **L'inscrit qui abandonne n'existait pour personne.** `readiness_red_flags` ne remontait que `NO_DATA` ; un locataire sans identité n'en produit aucune. | Première exécution en prod : **11 locataires bloqués** détectés. |
| 8 | **Le moniteur nocturne ne pouvait pas voir la cause littérale de Benken** : les sondes renvoient `True` sur env absent, et seul un humain tapant `--require` le voyait. | `central-app-missing` passe reported/manual → **guarded/deterministic**. |
| 9 | **Le portail go/no-go n'avait aucun test ni horaire.** Le runbook s'ouvre sur « on n'invite personne tant que `make artist-preflight` n'est pas vert ». | 9 tests + `check_canary_preflight` chaque nuit, scopé aux plateformes que le canari déclare. Exécuté en prod : **0 problème**. |

**Deux régressions à moi, trouvées en production et non en relecture.** Faire dériver
les cibles du watchdog m'a fait rendre la table `artists`, où `artist_id` est
l'identifiant Spotify VARCHAR — `operator does not exist: character varying = integer`,
soit la classe `column-name-is-not-its-meaning` que ce dépôt documente déjà. Et exiger
des lignes dans **toutes** les tables d'une plateforme rapportait le canari muet alors
qu'il collecte : `watchdog-becomes-the-noise` failli recréé. Les deux corrigées et
gardées. Ce qui a tenu : le contrat conservateur — la sonde a dit « could not run »
plutôt que « tout va bien ».

**Ce que ça dit des trois bêta-testeurs** : Benken et GRiNCH n'ont **jamais déclaré de
Spotify**, Cuzebo n'a rien du tout. Ils ont abandonné devant les écrans ci-dessus. Le
correctif ne les récupère pas tout seul — il empêche le prochain de vivre la même chose.

**Déployé et vérifié en production** (`prod == canonique`, 920 col / 92 tables,
71 migrations, code déployé == `origin/main`). 1220 tests verts contre une vraie base.

Classes : `same-platform-judged-on-different-tables`, `map-key-unreachable-by-construction`,
`guard-derived-from-the-thing-it-guards`, `broken-probe-rendered-as-user-fault`,
`row-existence-read-as-connection`, `gate-with-no-test-of-its-own`.

⚠️ **Un angle mort assumé** : les tests gardés par la base skippent en silence sans
Postgres sur 5433. J'ai développé les quatre vagues dedans, et la base a trouvé un vrai
défaut au premier lancement. Lancer la suite avec base avant de conclure.

**▶️ Séance du 2026-08-22 (suite) — R13 est clos, et il n'a jamais fallu régénérer.**

Trois séances avaient conclu qu'un token Meta était mort et qu'il fallait Business
Manager. Interrogé avec les credentials d'application corrects, il répond **valide** :
`SYSTEM_USER`, `expires_at=0`, 43 scopes — en local, en production, et dans
`artist_credentials`. La roadmap réclamait un geste humain pour un token qui marchait.

| # | livré | mesuré |
|---|---|---|
| 1 | **La correction du 2026-08-21 était allée dans le fichier qui perd** | `.env` était corrigé ; `.env.local`, qui **gagne** par construction, portait encore l'ID de compte publicitaire dans `META_APP_ID` et le token avec le `E` parasite. Tout Meta était cassé en local *sur une configuration réputée corrigée*. Les trois clés dupliquées retirées de `.env.local` — un seul fichier les possède. Classe `config-corrected-in-the-file-that-loses`. |
| 2 | **La sonde ne pouvait pas voir ce défaut** | `tools/check_central_apps.py` n'appelait jamais `load_project_env()` : depuis un shell nu, `⚠️ env not set` sur les quatre plateformes et **exit 0**. Frère manqué d'`env-resolved-against-cwd` — sa signature cherche la *mauvaise forme*, ici c'était l'*absence*. Câblée : **exit 1** nommant `1 extra character ('E')`, puis **exit 0** après nettoyage. Garde dérivé des outils que la doc fait lancer, donc un outil neuf est couvert le jour où il est documenté. |
| 3 | **L'ordre des fichiers d'env était recopié ailleurs** | `tools/notify_schema_drift.py` n'importe volontairement pas le paquet applicatif (un import cassé ne doit pas pouvoir museler l'alerte de dérive) — il relisait donc `.env` seul. Aligné sur `ENV_FILES` et **épinglé** dessus par test : un ordre recopié dérive. |
| 4 | **Pourquoi Meta ne renvoie rien, et pourquoi ce n'est pas une panne** | Vérifié sur l'API **et** en base de prod : **34 campagnes, 0 ACTIVE** (19 archivées, 15 en pause), `amount_spent=0`, 0 insight sur 90 j. Les insights n'existent que pendant qu'une publicité tourne. C'est exactement la condition que la séance précédente a rendue ⏸️ au lieu d'une fausse alerte — la suppression se déclenchera donc en prod (34 > 0 connues, 0 active), et un locataire dont aucune campagne n'est connue reste alerté. |

**Ce qui reste sur Meta ne dépend ni de moi ni de toi** : le compte publicitaire de
Benken (`act_65390907`) n'est toujours pas partagé — `(#200) Ad account owner has NOT
granted ads_management or ads_read permission`. Geste de Benken, pas correction de code.

⚠️ **Non déployé.** Le code de ces deux séances est sur `origin/main` mais pas en prod.
Déploiement : `cd /opt/streamlytics && git pull --ff-only origin main && docker compose up -d --build dashboard`.

**▶️ Séance du 2026-08-22 (reprise après crash machine) — la suppression d'alerte
écrite la veille était devenue un feu vert.**

Le travail interrompu par le redémarrage était complet côté décision et **muet côté
lecteur** : `check_freshness` répond à une question avec un seul booléen, et poser
`stale=False` pour une source légitimement silencieuse la fait rendre comme saine
partout. Un rouge qui part chaque nuit finit par être lu comme du bruit ; un vert
n'est jamais questionné — la deuxième panne est la pire des deux.

| # | livré | mesuré |
|---|---|---|
| 1 | **Le silence attendu de Meta Ads ne déclenche plus d'alerte** | Aucune campagne ACTIVE (19 archivées + 15 en pause, `amount_spent=0`, zéro insight en 90 j) ⇒ aucune ligne d'insight ne PEUT exister. Sans ça, `16 577 h stale` partait chaque nuit pour un pipeline correct. La sonde est volontairement conservatrice : sonde en échec, zéro campagne connue ou règle inconnue ⇒ **on garde l'alerte**. Supprimer sur une supposition retire le seul signal qu'une vraie panne produirait. |
| 2 | **Quatre surfaces lisaient `not stale` comme « tout va bien »** | Le tableau des sources (🟢 OK à côté d'une ligne du 2024-09-30) ; `platform_status`, donc la matrice d'onboarding, `readiness_red_flags` **et** `artist_preflight` ; le pied « ✅ Sources OK » de l'e-mail nocturne ; et `debug_alert_monitor` (`✅ OK (16577h)`) — la quatrième trouvée en **balayant la classe**, pas en regardant le bug, et la pire des quatre : c'est ce qu'on lance quand on soupçonne déjà quelque chose. La raison mesurée voyage désormais avec le drapeau et chaque surface a un troisième état ⏸️ qui l'imprime. |
| 3 | **Six gardes, chacun vu ROUGE par mutation** | Retirer la branche `QUIET`, la branche de la vue, la légende de la raison, le filtre du pied d'e-mail, la clé du saut XCom, la branche du script de debug — chacune fait tomber le test correspondant, puis vert après restauration. La vue est testée par **exécution réelle** (le tableau rendu est inspecté), pas par sous-chaîne. |
| 4 | **L'index du catalogue d'erreurs avait cessé de lister** | Trouvé en ajoutant une classe, pas en le cherchant : **63 entrées, 51 lignes d'index**, et les douze manquantes étaient les douze plus récentes — quatre écrites le jour même. Une omission qui ne contredit rien : l'index ne prétend jamais être complet, donc son incomplétude est silencieuse dans la seule direction qui compte (on réécrit la classe sous un autre nom). Lignes **régénérées depuis les entrées**, garde dans les deux sens, et `/capitalise` nomme désormais l'index dans ce qu'il écrit. |

Classes : `suppressed-alert-renders-as-health` (P2), `catalogue-index-omits-its-own-entries` (P3).
Constat annexe non traité (hors périmètre, à décider) : `freshness_monitor.run_freshness_alerts`
n'a **aucun appelant** dans tout le dépôt — l'alerte de fraîcheur réellement envoyée est
celle d'`alert_monitor`. Code mort ou câblage oublié : les deux se corrigent différemment,
et aucune des deux corrections n'appartenait à cette séance.

**▶️ Séance du 2026-08-21 (nuit) — R20 livré en prod, et trois lacunes de plus.**

| # | livré | mesuré |
|---|---|---|
| 4 | **Le canari a un lecteur** (`check_canary_health` dans `alert_monitor`) | Un canari que personne ne lit est de la décoration. Il rapporte, par plateforme déclarée, si des lignes atterrissent encore sous lui (seuil 36 h). L'**absence** de canari est elle-même un constat. Exécuté en prod : `Canary 14 (Canary prod): 0 problem(s)`. |
| 5 | **`central_apps_broken` n'envoyait aucun e-mail** | Il alimentait le corps ET le sujet, mais **pas `has_issues`** — donc une app partagée tombée, seule, ne produisait rien. Masqué par coïncidence (Meta cassé *et* périmé). Le garde balaie la classe : tout `xcom_pull` de `send_consolidated_alert` doit figurer dans la décision d'envoi. |
| 6 | **`make sync-check` voit les migrations non appliquées** | Impossible à demander avant le registre. Ferme `migration-ahead-of-its-code` par le côté qui manquait : du code déployé avant sa migration. Vérifie aussi que `tools/` reste monté — le compose de prod étant gitignoré, ce montage **ne voyage pas** avec `git pull`. Vu rouge sur une migration factice, vert après. |
| 7 | **Un token Meta mal collé se voit tout de suite** | `check_meta()` valide la forme avant le réseau. Vérifié contre le vrai token de prod : il nomme le caractère en trop. |
| 8 | **Le canari n'inondera pas la boîte mail** | Vérifié quelques heures après l'avoir créé : les deux contrôles d'onboarding l'auraient signalé chaque nuit (« 3 credentials manquants », « connecté sans données ») pour un état **normal**. `exclude_canaries=True` là seulement — le défaut reste `False`, sinon les collecteurs cesseraient de collecter POUR lui. Troisième fois que ce dépôt paie la taxe du loup. |

**▶️ Les trois optimisations proposées ont été livrées le 2026-08-21 (soir).**

| # | livré | mesuré |
|---|---|---|
| 1 | **Registre de migrations** (`schema_migrations` + `tools/migrate.sh`, migration 071) | 70 fichiers rejoués à chaque exécution → **0**. Un fichier édité après coup passe de invisible à détecté au `checksum`. ⚠️ Son installation a **cassé** `s4a_song_playlist_adds` (clé primaire + 2 colonnes) en rendant 024 rejouable seule ; réparé, gardé, et consigné comme classe `unguarded-drop-replayed-alone`. |
| 2 | **`make schema-check-local`** | La dérive que ni la CI ni une base jetable ne peuvent voir. Empreinte extraite dans `tools/dev/schema_fingerprint.sql` — elle était **dupliquée** dans le Makefile. Résultat après réparation : **local == canonique, 920 col / 92 tables**. |
| 3 | **Suite contre ≥2 locataires** | Mesuré : une base canonique fraîche contient **exactement 1** locataire, et c'est contre ça que la CI a toujours tourné. La CI sème désormais `ci-canary` ; le garde tombe en dessous de deux. |

**▶️ Séance du 2026-08-21 (soir) — le canari a trouvé trois défauts en une heure.**

Créé en local, il a fait exactement ce pour quoi il existe : révéler ce qu'un dépôt
mono-locataire ne peut pas voir. Dans l'ordre où ils sont tombés :

| classe | gravité | ce qui se passait |
|---|---|---|
| `env-resolved-against-cwd` | P2 | `make artist-preflight` annonçait « credential NOT configured » pour des credentials présents, simplement pas chargés dans ce shell. Et `app.py`, lancé de la façon documentée (`cd src/dashboard`), ne chargeait **rien** — `load_dotenv` renvoyait `False` sans un mot. |
| `identity-mirrored-but-written-once` | P1 | l'identité Spotify vit dans **deux** tables ; le formulaire écrivait les deux, `create_canary.py` une seule. Le canari affichait « Connecté — Daft Punk ✅ » partout et collectait zéro ligne. Le locataire dont le seul rôle est d'attraper un faux vert **était** le faux vert. |
| `api-partial-date-into-date-column` | P2 | Spotify renvoie `release_date` à précision variable (`2013`, `2013-05`, `2013-05-21`) ; la colonne est `DATE`. Un seul album à date approximative faisait perdre à l'artiste **tous** ses top tracks du run. Latent depuis des années : le catalogue de l'admin n'a que des dates complètes. |

Les trois ont un correctif, une signature vue rouge sur le défaut puis verte, et un test
vérifié par mutation. Deux gardes ont dû être réécrits : le premier testait une
**sous-chaîne** que la ligne d'`import` satisfaisait à elle seule — vert alors que l'appel
avait disparu. Réécrit sur l'AST, il tombe.

Un piège d'outillage consigné au passage : vérifier une signature **à la main** dans ce
shell est trompeur — `grep` y est une fonction (le wrapper RTK) qui renvoie 0 dès que la
sortie est redirigée. Passer par `audit_runner.py` ou `command grep`.

**▶️ Où on en est (MAJ 2026-08-21, nuit) — la file d'ingénierie est vide.**

Prod à jour (`prod == canonique`, 920 colonnes / 92 tables, code déployé == `origin/main`,
registre de migrations **71/71**), **940 tests verts hors base** (159 gated DB), `ruff` propre, audit
déterministe propre, canari de production surveillé. L'index `## 📋 Tâches ouvertes` est
à **0**, et les trois items de `## 🙋 En attente de toi` demandent chacun un geste que
seul un humain peut poser — détail juste en dessous.

**Ce qui t'attend — deux choses, et aucune n'est du code.**

L'index actif est à **0**. Les deux items ci-dessous ne se débloquent que par un geste
que tu es seul à pouvoir faire — un fichier, une invitation. Chacun a été **réduit** au
plus petit geste possible.

> **R13 est clos le 2026-08-22, et il ne demandait plus rien.** Le token Meta stocké
> était déjà **valide** — `debug_token` le confirme `SYSTEM_USER`, `expires_at=0`,
> 43 scopes, sur la bonne application. Ce qui restait cassé était `.env.local`, qui
> **gagne** sur `.env` et portait encore l'ID de compte publicitaire et le token mal
> collé. Détail et classe : `config-corrected-in-the-file-that-loses`.

1. ~~**R17 — déposer les PDF/EPUB d'ergonomie**~~ — **fait le 2026-08-21, l'ingestion
   tourne.** Dix ouvrages déposés, 1 indexé, 9 en cours. La lecture « le corpus renvoie
   du bruit, il n'a rien » était juste sur le symptôme et fausse sur la cause : neuf
   livres étaient déjà sur le disque, jamais ingérés, et rien ne distinguait « domaine
   vide » de « ingestion pas lancée ». Un contrôle de couverture donne désormais la
   différence. La décision que R17 bloquait reste **mesurée**
   (`make chart-budget` : 22 vues, 83 graphiques, médiane 3, `trigger_algo` à 15) ; le
   corpus servira à trancher le **seuil** une fois les 10 livres indexés.
2. **R1 — ouvrir la bêta privée** sur `streamlytics.fr`. Son prérequis dur est tombé :
   le canari de production existe et `artist_preflight` y est vert de bout en bout,
   contamination comprise. Le filet qui manquait aux deux sessions bêta précédentes est
   en place. R2 (landing + pixel + CAPI) démarre avec la première campagne, pas avant —
   ADR-008.

**Historique des grandes étapes (toutes ✅) :**
1. **✅ Cloudflare — ACTIF, PROXIFIE & DURCI (complet)** (détail `[[project_security_cloudflare]]`). Fait : zone active, NS Cloudflare, **SSL Full(strict)**, zone settings (min TLS 1.2 / Always HTTPS / Brotli / TLS 1.3), **rate-limit `/auth/token`** (10/10s), **firewall origine verrouillé** (ufw → IP CF only, vérifié), **Bot Fight Mode** ON, **cert Origin CF 15 ans** posé sur Caddy (plus de risque renouvellement, vérifié 2 edges). **RESTE (non bloquant)** : 🔑 **révoquer le token** `streamlytics-hardening` ; (optionnel) ré-activer DNSSEC via CF. ⚠️ vérifs prod **toujours via `curl --resolve host:443:<edge-CF-IP>`** (cache DNS local peut pointer l'IP origine firewallée → faux « down »).
2. **✅ Red-team — COMPLET** (réseau + app + dashboard). Couvert & clean : MITM/TLS (CVE suite), brute-force, SQLi, deps (0 CVE), **isolation tenant/IDOR (prouvé live)**, priv-esc, JWT, CORS, secrets, XSS (escaping tient), **replay webhook Stripe** (signature + handlers idempotents + tolérance 5 min), upload path-traversal (filename = détection seulement), app-DoS (cap 50 Mo + bornes `le=1000` + Cloudflare). **Trouvé+fixé+déployé** : `/kpis` & `/youtube/videos` schema-drift 500 (suite 18/19b) ; **CSV/Excel formula injection sur export (CWE-1236, suite 20)** → `defang_formulas()` sur les 3 chemins d'export + test. Mineur restant : XSRF/cookies Streamlit = défaut framework (P4). Compte test `redteam_qa` **supprimé (clôturé suite 20)**. Classes cataloguées : `api-router-schema-drift`, `csv-formula-injection` (`error-classes.md`).
3. **✅ E1 OUVERT** — 1er beta externe **Benken** (artist_id=12) onboardé 2026-06-15. A révélé une cascade per-tenant (tous les tests credentials KO, tous les CSV sauf Apple KO) → **diagnostiquée + corrigée + déployée** (voir session ci-dessous). 2e tenant **Cuzebo** (id=11) créé aussi.
4. **Actions restantes de l'époque, désormais reprises ci-dessus** : ~~**R13 régénérer le token Meta**~~ (clos 2026-08-22 : le token était valide ; c'est `.env.local` qui masquait la correction) ; **prep pré-session Benken** (partage compte pub Meta 65390907 + bon channel YouTube + Spotify artist ID) ; **R14 onboarding UX restant** (plan Track 1) ; refaire une session live avec Benken (tout doit marcher du 1er coup pour SoundCloud ✅/Apple ✅/YouTube/Spotify).

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
