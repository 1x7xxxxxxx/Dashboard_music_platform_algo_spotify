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
| R592 | Glossaire — vue « 📖 Glossaire » dans Compte, juste après Mon compte : schéma du fonctionnement de l'app + toutes les définitions techniques ; livrable `revue/glossaire-inventaire.md` : chaque définition trouvée dans les vues, et la preuve qu'aucune vue ne garde de prose explicative <!-- critic: requis — nouvelle vue + inventaire transverse --> <!-- scope: src/dashboard/views/, src/dashboard/utils/, src/dashboard/utils/nav_sections.py, src/dashboard/routes.py, src/dashboard/app.py, src/dashboard/utils/i18n.py, src/dashboard/utils/i18n_catalog/, tools/dev/, tests/ , src/database/stripe_schema.py, src/dashboard/utils/plan_pitch.py, .claude/dev-docs/architecture.md, Makefile --> | P3 | test : vue routée après Mon compte, chaque terme de l'inventaire défini, garde « pas de prose de définition dans les vues » |
| R597 | Meilleurs réglages — couleurs = campagnes avec leur légende, filtre deux campagnes à comparer ; panneau « optimisation de l'ad set » supprimé <!-- critic: non — habillage + suppression --> <!-- scope: src/dashboard/utils/best_settings.py, src/dashboard/views/meta_creatives.py, src/dashboard/views/trigger_algo/, src/dashboard/utils/i18n_catalog/, tools/dev/, tests/, migrations/, src/utils/gold_invariants.py, src/utils/metric_registry.py --> | P3 | test : légende des campagnes, plus de panneau d'optimisation |
| R598 | Meilleurs réglages déplacés dans Prédiction algos, avec la « photo » des réglages Meta optimaux : chaque paramètre modifiable d'une campagne et sa meilleure valeur ; offre décrite sur Facturation & abonnement <!-- critic: requis — déplacement entre pages + offre --> <!-- scope: src/dashboard/views/, src/dashboard/utils/, src/dashboard/utils/stripe_schema.py, src/database/, src/dashboard/utils/i18n_catalog/, tools/dev/, tools/dev/, tests/ --> | P3 | test : la page Prédiction rend les réglages, la vue croisée non, l'offre les cite |
| R599 | Filtres — sortie de référence et « comparer à » l'un AU-DESSUS de l'autre (cohérence de tous les filtres de l'app) <!-- critic: non — disposition --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/views/meta_creatives.py, src/dashboard/utils/, tools/dev/, tests/ --> | P3 | test : les deux sélecteurs hors colonnes, référence d'abord |
| R600 | Prédiction algos — « poids valeur » renommé « poids principaux des modèles de machine learning » ; pastilles bleu/jaune/rouge alignées sur leur rangée de jauges <!-- critic: non — libellé + alignement --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/utils/i18n_catalog/, tools/dev/, tests/ --> | P3 | test : centre vertical de chaque pastille = centre de sa rangée |
| R601 | Prédiction algos — Release Radar : la courbe de cohorte ne retombe pas après le 1er mois comme DW et Radio — cause à lire dans les données puis correctif <!-- critic: requis — défaut de données possible --> <!-- scope: src/dashboard/views/trigger_algo/, src/utils/, src/dashboard/utils/, airflow/dags/, machine_learning/, tools/dev/, tests/ --> | P3 | test qui rougit sur la cause trouvée |
| R602 | Prédiction algos — graphique des valeurs : nom des playlists à GAUCHE dans la même pastille « déclenché par » que les jauges ; la verticale pointillée de droite nommée « 100 % = déclenche » <!-- critic: non — habillage --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/utils/i18n_catalog/, tools/dev/, tests/ --> | P3 | test : pastilles à gauche, annotation sur la verticale |
| R603 | Couleurs — une couleur par type de donnée dans toute l'app (campagne 1/2 bleu/jaune, créas, titres, playlists, mesures) ; registre unique + livrable `revue/couleurs.md` ; la prévision suit le registre <!-- critic: requis — BUILD-MODIFIED 2026-10-15 : registre DANS platform_colors.py (pas de 4ᵉ module) ; titres ≠ campagnes (paires distinctes) ; garde = cliquet positif des littéraux hex par fichier, étendu dans test_a_platform_colour_has_one_definition.py, pas un prédicat sur les noms ; pas de familles mesure/verdict --> <!-- scope: src/dashboard/utils/, src/dashboard/views/, tools/dev/, tests/, Makefile --> | P3 | test : aucune vue ne choisit une couleur hors registre pour un type déclaré |
| R604 | Statusline — le nombre de tâches de roadmap encore ouvertes (les deux tables, le même compte que `make night-status`), à côté de « non commité(s) · non poussé(s) » <!-- critic: non — une lecture de plus dans le HUD, même définition que night_run --> <!-- scope: .claude/scripts/statusline.py, tests/ --> | P4 | test : « N tâche(s) roadmap » rendu, compte = night_run._open_tasks |

---

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R592, R597, R598, R599, R600, R601, R602, R603, R604 -->

**État au 2026-10-10 (fin de nuit)** : toutes les recos portées en roadmap — R507 tranchée (a), R509 mutmut, R510 inachevés, R511 YouTube Analytics. **État au 2026-10-10 (nuit)** : R501-R508 — passe défauts produit (Hypothesis : iMusician P1, rejets comptés, locale par fichier, bornes), propriétés vague 2, portes de documents allégées, Dependabot uv, cibles make ; études E1-E6 dans `.claude/dev-docs/studies/`. **État au 2026-10-10 (soir)** : R497-R500 — moins de rouges auto-infligés (analyse : 42 % des ids testent le processus, 1 rouge CI sur 15 est un défaut produit) : porte des durées, deux voies, pilote Hypothesis, admission du catalogue. **État au 2026-10-10** : R494-R496 — restes vivants des balayages de R493 et R495 (résolution d’imports au nom importé ; un plantage n’est pas un verdict ; déclencheur p50 non lu). **État au 2026-10-09** : 2ᵉ lot de retours vocaux (W1-W14, `revue/notes-vocales-2026-10-09.md`) → R474-R489, à faire en séance de nuit dans l'ordre de l'index (bugs P2/P3, puis les deux vues réceptrices R476/R477 et le filtre commun R478, puis vue par vue). Avant :  retours vocaux du propriétaire sur l'app → R437-R443 (assistant, mapping, saisie S4A, Hypeddit), toutes livrées et déployées le 2026-10-07 (R442 en option A : le pari du modèle est un onglet admin, les grilles restent chez l’artiste). R116 (ADR-027) et R131
(seuils de charge dérivés par Prometheus) sont livrées le 2026-10-12 : plus aucun bloc ⏸️.
Le récit des journées précédentes est dans l'archive (« 🗄️ Historique de l'actif »).

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.


| Ce qu'on ne fait pas | Ce qui le rouvrirait, calculable |
|---|---|
| Chercher un 3ᵉ worker pytest en baissant la réserve mémoire | `MemAvailable` au repos dépasse durablement **7 220 Mo** SANS éteindre Airflow — c'est-à-dire si le RAG paresseux tient sa promesse (`ps -eo rss` sur `knowledge-rag` après un redémarrage de session) |
| Retirer les **110 index jamais scannés** (5,7 Mo) | une table de faits dépasse **1 M lignes** — l'amplification d'écriture devient réelle. Aujourd'hui : 34 078. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| Sortir **Airflow** de la boîte (il prend 2,3 Go des 7,7) | la RAM des conteneurs dashboard dépasse **2 Go** — ce que R87 rapproche. `docker stats --no-stream` |
| Construire la **couche or** (table de faits agrégée) | un locataire dépasse **100 000 lignes** sur une table de faits, ou un agrégat d'accueil dépasse **200 ms**. Aujourd'hui : 14 694 lignes, 46 ms |
| ClickHouse / Parquet / dbt / Dagster | déclencheurs d'**ADR-014**, relus le 2026-09-11 : aucun n'est tiré (62 Mo contre 50 Go, 34 k lignes contre 10 M) |
| Fragmenter les **5 vues restantes** de R118 — `imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin` | l'une d'elles dépasse **300 ms de vue** dans l'histogramme SERVEUR : `histogram_quantile(0.5, sum by (page,le) (rate(streamlytics_rerun_duration_seconds_bucket{phase="view"}[1h])))`. Mesuré localement le 2026-09-17 : 20 à 130 ms de rerun à chaud, **dans la même bande que les six déjà fragmentées** (78 à 172 ms) — donc rien ne les distingue, et le bruit local (±60 à 100 %) est plus large que les écarts. Seul le serveur peut trancher, et il lui faut du trafic sur ces pages |

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

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
