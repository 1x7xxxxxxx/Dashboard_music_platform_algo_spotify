# Master Roadmap Checklist — actif

**Roadmap en deux fichiers.** Celui-ci ne porte que ce qui est **ouvert** ; ce qui est livré
ou clos vit dans `.claude/dev-docs/roadmap/archive.md`. Un item passe de l'un à l'autre par
**déplacement** — jamais par duplication ni par effacement.

| Fichier | Contient | Écrit par |
|---|---|---|
| `checklist.md` (ici) | index des tâches ouvertes, reprise, tâches parquées, consignes | l'inscription d'une tâche (R196), `make roadmap-close` |
| `archive.md` | tâches livrées ou closes, récits, historique de l'actif | `make roadmap-close` (R199), `roadmap-keeper` pour un lot |

**Le cycle d'une action (R196 · R198 · R199)** : (1) une ligne `| Rnnn | … <!-- critic: requis|non — raison --> | P | mesure |`
dans l'index, commitée seule ; (2) le code, commité avec « Rnnn : … » — refusé sinon, avant
l'édition et au commit ; (3) `make roadmap-close ID=Rnnn NOTE="…"`. La discipline est MESURÉE :
`make roadmap-discipline` (R197), chaque nuit et dans le récap du matin.

Ce fichier reste court (R200, 2026-09-26) : la prose d'historique qui l'avait porté à 499
lignes vit dans l'archive, sous « 🗄️ Historique de l'actif ». Plafond gardé par
`tests/test_the_resume_header_is_checked.py`.

Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next open row."*

---


## 📋 Tâches ouvertes (index — détail plus bas)

Index des tâches **qu'on peut commencer maintenant** — chaque ligne décide de son
code-critic. À la livraison : `make roadmap-close ID=Rnnn` (écrit l'archive, retire la ligne).

| id | Tâche | P | Mesuré par |
|---|---|---|---|
| R258 | **Or, une définition par KPI jusqu'au bout** (notes L10, L72, L500-510, L549) : registre étendu à formule, granularité, période et test de qualité par métrique ; identité mécanique argent/or ; plafond brut 66 → descendre (18 figures, 44 tuiles) ; CPC calculé deux fois dans meta_ads_overview → une lecture or <!-- anchor: r258 --> <!-- critic: requis — couche de définition partagée --> | P2 | REQ-GOLD-02/03, REQ-SILVER-01 conformes au benchmark |
| R259 | **Filtres : une seule couche, défaut « dernière sortie »** (notes L90, L98, L103, L511, L549) : `_default_preset` → dernière sortie quand elle existe ; smart_date_range et meta_accounts passent par filters.py ; SoundCloud semaine à un seul point ; mêmes libellés partout <!-- anchor: r259 --> <!-- critic: non — resserrement d'une couche existante --> | P2 | REQ-FILTER-01/02 conformes |
| R260 | **Porte de dessin et formats uniques** (notes L87, L242, L549) : couleurs de plateforme en dur 42 → 0 (PDF compris) ; Pareto par défaut sur les barres par catégorie ; un formateur de nombres/monnaie/% pour tuiles et tableaux + cliquet ; actions en gras, informations en petit <!-- anchor: r260 --> <!-- critic: non — porte existante étendue --> | P3 | REQ-CHART-02/03, REQ-FORMAT-01 conformes |
| R261 | **Un contrat de routage unique** (notes L231, L243, L266, L270, L271, L277, L356) : page d'arrivée décidée à un endroit selon l'état de configuration, même parcours quel que soit l'onglet d'origine ; lien mort vers « Guide de démarrage » dans le mail de bienvenue ; en-tête « Ta mise en route », sélecteur d'OS, identité en haut du menu <!-- anchor: r261 --> <!-- critic: requis — navigation de toute l'app --> | P2 | REQ-UX-02 conforme ; parcours rejoué de bout en bout |
| R262 | **Finance en une vue avec projection** (notes L128, L139, L538, L540) : charges, pub, SACEM, distributeurs, valeur d'un déclenchement sur un graphique, durée restante avant le point mort écrite dessus ; accueil : sources étendues (distributeur, SACEM, Hypeddit, meilleurs paramètres Meta) <!-- anchor: r262 --> <!-- critic: requis — chiffres d'argent --> | P2 | la durée avant point mort lisible sur la figure |
| R263 | **Vue ML simple et aérée** (notes L132) : probabilité par titre d'un coup d'œil, leviers restants en Pareto avec leur équivalent en euros par algorithme, comparaison entre titres, panneaux regroupés, décisions listées <!-- anchor: r263 --> <!-- critic: requis — vue payante --> | P2 | vue relue sur son rendu |
| R264 | **Classes d'erreur génériques, suivies, transposables** (notes L9, L60-65, L72, L165) : une classe générique par famille avant les distinctes ; table en base pour la pertinence et les échecs de chaque classe dans le temps ; processus CLAUDE.md/hooks/agents vérifié ; baseline de déploiement mise à jour ; passe de finalisation avec code-critic (la nuit) <!-- anchor: r264 --> <!-- critic: requis — processus de garde --> | P3 | REQ-ERR-01/03 conformes ; série visible dans Grafana |
| R265 | **Observabilité : santé et échelle dans Grafana** (notes L67-69, L80) : erreurs applicatives par page (« No data »), nombre de logs, CPU/RAM/disque VPS, pool, utilisateurs connectés, lignes et taille de base, API et DAG dans app_error_log, seuils d'alerte ; ce que Grafana montre quitte la vue admin (décidé le 2026-09-27 : Grafana seul, l'admin garde la gestion) <!-- anchor: r265 --> <!-- critic: requis — alertes --> | P3 | REQ-OBS-01, REQ-ERR-02 conformes |
| R266 | **Scalabilité : ingestion et runtime** (notes L72, L169, L549) : fan-out par locataire (tâche par locataire), budget de quota par locataire mesuré, limites mémoire/CPU par conteneur, test de charge (Locust) sur l'instantané avec seuil ADR-007 ; ADR avant le code <!-- anchor: r266 --> <!-- critic: requis — structure des DAGs --> | P2 | REQ-ORCH-01/03, REQ-RUN-02/03 conformes |
| R267 | **Sécurité : nocturne bloquant et pentest** (notes L138, L170, L549) : gitleaks et pip-audit bloquants la nuit, requirements-api.txt audité, session de pentest avec plan d'actions, bilan de la connexion Google <!-- anchor: r267 --> <!-- critic: requis — sécurité --> | P2 | REQ-SEC-02 conforme ; rapport de pentest |
| R268 | **Roadmap et chaîne de dev fiables** (notes L71, L165, L172) : relevé de discipline régénéré chaque nuit, temps de suite depuis une seule source générée, nettoyage de l'obsolète, allègement des livrables (décision), manques de la chaîne commit → CI → push <!-- anchor: r268 --> <!-- critic: non — outillage --> | P3 | REQ-ROAD-03, REQ-TEST-03 conformes |
| R269 | **Redondances de code et graphify** (notes L166, L169) : graphe régénéré et nettoyé des fichiers fantômes, doublons intra et inter-scripts listés et refactorés <!-- anchor: r269 --> <!-- critic: non — refactor mesuré --> | P3 | liste de doublons réduite, graphe sans fantôme |
| R270 | **Onboarding rejouable et CSV expliqués** (notes L5, L7, L157, L258) : marche complète compte → mail → identifiants → première donnée (tiers compris), définition de chaque CSV, verdict vert seulement quand la première donnée arrive (décidé le 2026-09-27), bouton de collecte manuel replié dans l'état <!-- anchor: r270 --> <!-- critic: non — parcours existant --> | P3 | REQ-ONB-01 conforme |
| R271 | **Pages : récap, graphiques et validation** (notes L8, L91, L142, L164, L168, L470) : page récap des graphiques à plus forte valeur, Data Wrapped intégré à la page Spotify & S4A sous la saisie (décidé le 2026-09-27), « Mes sorties à âge égal » avec dépense Meta et Shazams, idées de graphiques par page, validation de chaque vue et de chaque bouton, adaptation mobile <!-- anchor: r271 --> <!-- critic: non — pages --> | P3 | dossier des KPI relu |
| R272 | **Multi-comptes et vue de campagne** (notes L129, L134, L144, L222) : multi-comptes simple sur toutes les plateformes (cas agence Meta), vue qui regroupe les paramètres de campagne et budgets de déclenchement, parrainage : la récompense appliquée par coupon Stripe (décidé le 2026-09-27) <!-- anchor: r272 --> <!-- critic: requis — plans et facturation --> | P2 | un second compte Meta configuré en un geste |
| R273 | **Collecte : Instagram, YouTube, funnel par utilisateur** (notes L92, L107, L531) : engagement Instagram vide, granularité des abonnés YouTube (limite de l'API : répondre), suivi d'un même utilisateur dans le funnel autant que les données le permettent <!-- anchor: r273 --> <!-- critic: non — collecteurs --> | P3 | engagement Instagram rempli sur l'instantané |
| R274 | **Poste de développement** (notes L15, L72, L73, L79) : leviers PC mesurés (WSL, processus Python, conteneurs — n8n le dimanche), ouverture VS Code Remote-WSL par défaut et alias `sl` (geste proposé dans le fil) <!-- anchor: r274 --> <!-- critic: non — hors produit --> | P4 | mesure avant/après |

---

## ⏸️ R116 — ADR-027, en attente de ses courbes (sortie de l'index 2026-09-17)

**Ni livrée ni abandonnée — parquée sur une mesure, pas archivée.** `archive.md` est
strictement passif (`tests/test_roadmap_two_files.py::test_the_archive_holds_nothing_actionable`
refuse tout item non coché qui y atterrit), donc ce bloc reste ici, hors des deux
index. Sortie de l'index actionnable le 2026-09-17 parce que `daily_ops_metrics` ne
porte qu'**une seule ligne** (2026-09-16), `complete = FALSE`, et **tous ses
percentiles de rendu sont `NULL`** — seul `peak_sessions = 8` est renseigné. La
courbe que R116 exige, `streamlytics_rerun_duration_seconds` côté serveur, n'existe
donc pas encore ; le bloc le disait déjà lui-même : « un ADR écrit avant la mesure
serait une rationalisation ». Déclencheur de réouverture, calculable, dans
`### Conditions d'attente` ci-dessous, ligne « Écrire **ADR-027** (répliques et
Redis) » : `SELECT count(*) FROM daily_ops_metrics WHERE complete` doit rendre
**14 jours** à `TRUE` — **2 en production le 2026-09-20**, et le chiffre écrit ici
disait « 0 » parce qu'il avait été relevé sur la base LOCALE. `make reopen-check-prod`
le remesure ; sans `PROD_SSH` le contrôle rend désormais INDÉCIDABLE plutôt qu'un chiffre
qui ne décrit rien. Elle n'attend aucun geste humain, seulement
du trafic — elle ne va donc pas dans « 🙋 En attente de toi » — et pour la même
raison elle sort de l'ancre de reprise en tête de fichier, qui ne porte que ce que
les deux tables d'index de ce fichier listent encore.

- [ ] **R116 — ADR-027, écrit APRÈS les courbes.**

  ⚠️ **Le numéro a changé** : ce bloc annonçait ADR-026, qui est pris depuis le
  2026-09-16 par la décision d'observabilité. Cette décision-ci est **ADR-027**.

  La décision sur les répliques et sur Redis, avec les DEUX courbes mesurées, les
  alternatives refusées et le déclencheur de relecture. Un ADR écrit avant la mesure
  serait une rationalisation — c'est pourquoi il est une tâche à part et qu'il vient en
  dernier.

  **Il a maintenant de quoi être écrit honnêtement, ce qui n'était pas le cas avant :**
  la réplique est arrêtée côté Caddy ET côté scrutation Prometheus, et les trois gestes
  de remise en service sont écrits en UN seul endroit (le bloc au-dessus de
  `reverse_proxy` dans `deploy/Caddyfile`). La courbe qui tranchera est
  `streamlytics_rerun_duration_seconds`, mesurée côté SERVEUR — insensible à la
  saturation du client, qui est ce qui rendait la mesure de R114 ambiguë.

**Ce qui reste écarté, avec sa raison** : Redis (R113 supprime son besoin pour les
caches, l'étape 1 l'a fait pour les limiteurs — s'il reste un besoin après R114, il sera
NOMMÉ, pas supposé) ; Celery/RQ (Airflow tient l'asynchrone, 13 DAGs) ; Loki et les
traces (après Prometheus, et seulement si un incident les réclame) ; Terraform (0 fichier
IaC, vrai manque — déclencheur : une SECONDE machine, ou une reconstruction subie) ;
S3/MinIO (les deux répliques partagent le même bind-mount sur le même hôte — déclencheur :
une seconde MACHINE) ; MLflow (déclencheur : la première décision de réentraîner) ;
dbt, Kafka, OpenSearch, pgvector, K8s, sharding (déclencheurs calculables d'ADR-014 et
ADR-023, relus le 2026-09-11, aucun tiré).

---

## 🔖 REPRISE — état au 2026-09-25 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R258, R259, R260, R261, R262, R263, R264, R265, R266, R267, R268, R269, R270, R271, R272, R273, R274, R275, R255, R256 -->

**État au 2026-09-26** : les tâches ouvertes sont celles de l'index ci-dessus ; R116 et R131
sont parquées (sections ⏸️), leurs déclencheurs évalués par `make reopen-check` chaque nuit.
Le récit des journées précédentes est dans l'archive (« 🗄️ Historique de l'actif »).

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.


#### Mesuré le 2026-09-17 — pourquoi `PYTEST_WORKERS` restera à 2, et ce qui le débloquerait

> ⚠️ **Rectifié le 2026-09-25, par une mesure.** Le raisonnement ci-dessous confond deux
> choses : les résidents sont DÉJÀ hors de `MemAvailable`, la réserve n'a donc à couvrir
> que ce qui peut GROSSIR pendant la suite. Les deux croissances de l'époque ont cessé
> d'être permanentes (n8n le dimanche seulement, modèle knowledge-rag déchargé après
> 10 min) ; la réserve suit désormais ce qui tourne (`tools/dev/pytest_workers.py`) et
> rend **4 workers** : 179–180 s contre 269 s à 2, creux de `MemAvailable` ≥ 4 278 Mo sur
> trois suites complètes alternées. Le texte qui suit reste comme trace de l'ancien calcul.

`PYTEST_DIST` vaut `-n $(PYTEST_WORKERS)`, avec
`workers = (MemAvailable_Mo − 5120) / 700`, borné à `[2, nproc]`. La constante de
réserve avait été écrite le matin même après **deux morts par OOM en une heure**,
sans être confrontée au pic réel. Elle l'a été :

| ce qui a été mesuré | valeur |
|---|---|
| suite complète à `-n 2`, creux de `MemAvailable` | **991 Mo consommés** (3 918 → 2 927) |
| donc par worker | **~495 Mo** — la formule en budgète 700, soit ×1,4 de marge |
| résidents au repos | RAG **1 548** · Airflow+PG **1 686** · serveur VS Code **1 089** · `claude` **449** = **4 772 Mo** |
| RAM totale de la WSL | 9 945 Mo (plafond `.wslconfig`, hôte 15,7 Gio) |

**La réserve de 5 120 Mo n'est donc pas arbitraire : elle vaut à peu près ce que les
résidents pèsent (4 772 Mo mesurés).** Et elle explique l'OOM : à 8 workers,
8 × 495 = 3 960 Mo de suite + 4 772 de résidents = 8 732 Mo sur 9 945. La baisser
rendrait l'OOM, elle ne rendrait pas des workers.

**Le levier est donc les RÉSIDENTS, et il manque 68 Mo.** Le troisième worker demande
`MemAvailable ≥ 7 220`. En libérant le RAG (1 548) et Airflow (1 686) :
3 918 + 3 234 = **7 152 Mo** — à **68 Mo** du seuil. Arrêter en plus un serveur MCP
inutilisé (`chrome-devtools` 89 Mo, `graphify` 90 Mo) ferait basculer.

**Ce qu'on ne fait pas** : courir après ce troisième worker. Le gain attendu est
178 s → ~145 s, soit ~33 s sur une suite qu'on lance quelques fois par jour, contre
l'obligation d'éteindre Airflow — dont on a justement besoin pour que ~160 tests ne
skippent pas. Motif d'ADR-007.

⚠️ Deux mesures de cette séance sont **invalides et ne doivent pas être recitées** :
la somme des `VmHWM` des processus pytest (**194 Mo**, le motif `pgrep` ratait les
workers `execnet`) et les trois bancs mémoire du serveur RAG, dont le dernier rendait
*moins* de mémoire avec préchargement que sans. Seul le creux de `MemAvailable` est
fiable ici.

| Ce qu'on ne fait pas | Ce qui le rouvrirait, calculable |
|---|---|
| Chercher un 3ᵉ worker pytest en baissant la réserve mémoire | `MemAvailable` au repos dépasse durablement **7 220 Mo** SANS éteindre Airflow — c'est-à-dire si le RAG paresseux tient sa promesse (`ps -eo rss` sur `knowledge-rag` après un redémarrage de session) |
| Retirer les **110 index jamais scannés** (5,7 Mo) | une table de faits dépasse **1 M lignes** — l'amplification d'écriture devient réelle. Aujourd'hui : 34 078. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| Sortir **Airflow** de la boîte (il prend 2,3 Go des 7,7) | la RAM des conteneurs dashboard dépasse **2 Go** — ce que R87 rapproche. `docker stats --no-stream` |
| Construire la **couche or** (table de faits agrégée) | un locataire dépasse **100 000 lignes** sur une table de faits, ou un agrégat d'accueil dépasse **200 ms**. Aujourd'hui : 14 694 lignes, 46 ms |
| ClickHouse / Parquet / dbt / Dagster | déclencheurs d'**ADR-014**, relus le 2026-09-11 : aucun n'est tiré (62 Mo contre 50 Go, 34 k lignes contre 10 M) |
| Écrire **ADR-027** (répliques et Redis) | `daily_ops_metrics` porte **14 jours `complete = TRUE`** : `SELECT count(*) FROM daily_ops_metrics WHERE complete` — **aujourd'hui 0**. La table a UNE ligne (2026-09-16), `complete = FALSE`, et **tous ses percentiles de rendu sont `NULL`** ; seul `peak_sessions = 8` est renseigné. La courbe qui doit trancher — `streamlytics_rerun_duration_seconds` côté serveur, et `streamlytics_reruns_in_flight` pour la saturation — n'existe donc pas encore. Le bloc de R116 le disait lui-même : *« un ADR écrit avant la mesure serait une rationalisation »*. Ce n'est pas du travail en retard, c'est du temps et du trafic |
| Fragmenter les **5 vues restantes** de R118 — `imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin` | l'une d'elles dépasse **300 ms de vue** dans l'histogramme SERVEUR : `histogram_quantile(0.5, sum by (page,le) (rate(streamlytics_rerun_duration_seconds_bucket{phase="view"}[1h])))`. Mesuré localement le 2026-09-17 : 20 à 130 ms de rerun à chaud, **dans la même bande que les six déjà fragmentées** (78 à 172 ms) — donc rien ne les distingue, et le bruit local (±60 à 100 %) est plus large que les écarts. Seul le serveur peut trancher, et il lui faut du trafic sur ces pages |

> Les trois sections du 2026-09-10 (audit transverse, R83, les sept tâches livrées
> plus tôt) ont été **déplacées** dans `archive.md` le 2026-09-13 : ce fichier avait
> franchi le plafond de 50 Ko que `/resume` lit à chaque session.

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

---

## ⏸️ R131 — Calibrer les trois seuils de charge (sortie de l'index 2026-09-17)

**Ni livrée ni abandonnée — parquée sur une mesure, pas archivée.** `archive.md` est
strictement passif (`tests/test_roadmap_two_files.py::test_the_archive_holds_nothing_actionable`
refuse tout item non coché qui y atterrit), donc ce bloc reste ici, hors des deux index.

**Pourquoi elle sort de l'index actionnable** : elle demande de dériver trois seuils sur
une distribution, et la distribution n'existe pas. Mesuré le 2026-09-17 :
`daily_ops_metrics` porte **1 ligne en production** (2026-09-17) et 2 en local. Il en
faut 30. Aucun geste ne la débloque — seulement du trafic et du temps —, donc elle ne va
pas non plus dans « 🙋 En attente de toi ».

Écrire les seuils maintenant serait exactement le défaut que la règle interdit : le dépôt
porte déjà **cinq** seuils sans dérivation (disque 85 %, RAM 500 Mo, sauvegarde 25 h,
watchdog 26 h / 48 h), plus le 20 de `scale_check.sh`, posé face à un pic observé de 12
sans que le facteur 1,7 soit justifié.

**Déclencheur de réouverture, calculable** :

```sql
SELECT count(*) FROM daily_ops_metrics WHERE day > now() - interval '30 days';
-- doit rendre 30 — **4 en production le 2026-09-20**
-- ⚠️ À mesurer EN PRODUCTION : `make reopen-check-prod PROD_SSH=…`. Le « 1 » écrit ici
-- venait de la base locale, et l'outil de réouverture faisait la même erreur jusqu'au
-- 2026-09-20 (il annonçait 5).
```

- [ ] **R131 — les trois seuils de charge, dérivés d'une distribution et non d'un instinct.**

| règle différée | ce qu'elle surveillerait | la grandeur qui existe déjà |
|---|---|---|
| `SessionsHigh` | la charge utilisateur | `streamlytics_sessions_1m`, `daily_ops_metrics.peak_sessions` |
| `ErrorRateHigh` | une pointe d'erreurs | `streamlytics_app_errors_total`, `errors_by_page` |
| `LogErrorBurst` | une pointe de journaux ERROR | `streamlytics_log_records_total{level="ERROR"}` |

⚠️ Les quatre alertes livrées le 2026-09-17 ne portent **aucun** seuil — `absent()`,
`up == 0`, `read_ok == 0`. Elles couvrent le silence des instruments, pas la charge. Les
deux questions sont distinctes et la seconde attend ses données.

---

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
| R275 | Faire tester l'app à deux artistes bêta (message vocal) et rapporter leurs retours (notes L173) | P2 | ton envoi — runbook § 35 |
| R255 | Saisir le **coût de distribution** de chaque titre (fiche 62) | P3 | ta saisie dans 📈 Prévisions revenus → 💳 Mes coûts, catégorie distribution, un titre par ligne — runbook § 33 |
| R256 | Saisir les **coûts d'exploitation** de l'app (fiche 66) | P3 | ta saisie dans ⚙️ Admin → 💸 Coûts d'exploitation & marge — runbook § 34 |

---

## 🔁 Consignes permanentes — ce ne sont PAS des tâches

Rien ici ne se coche, ne se livre ni ne s'archive : ce sont des gestes à faire le jour
où un évènement les déclenche. Ils vivent dans le fichier actif pour être relus, pas
pour être finis.

⚠️ Titre corrigé le 2026-09-17. Il s'appelait « Brick Status » et annonçait « ce qui
reste ouvert est ci-dessous » — deux affirmations fausses : aucune brique n'y figurait
depuis des mois, et rien de ce qui suit n'est ouvert au sens de la roadmap. Un lecteur
qui cherchait l'état des briques lisait une liste de secrets à faire tourner.

### Rotation des secrets — sur incident seulement (aucune action de code)

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, variables d'environnement de la prod (Hetzner). Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".
