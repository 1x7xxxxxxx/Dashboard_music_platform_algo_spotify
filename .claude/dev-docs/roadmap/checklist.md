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
| R575 | Vue croisée — entonnoir en VRAIE forme d'entonnoir (haut→bas, large→étroit, `go.Funnel`), et deux campagnes ⇒ deux entonnoirs côte à côte visibles par défaut <!-- critic: non — remplacement d'une figure --> <!-- scope: src/dashboard/utils/full_funnel.py, src/dashboard/views/meta_x_spotify.py, src/dashboard/utils/meta_filter_bar.py, tools/dev/, tests/ --> | P3 | test : la figure est un `go.Funnel` ordonné ; rendu à deux campagnes = 2 figures |
| R576 | Vue croisée — CPM/CPC/CPR présentés autrement (cartes KPI par campagne) ; courbes cumulées « même horloge » en petits multiples (un panneau par métrique, couleur = campagne, traits pleins, légende sur le graphique) <!-- critic: non — refonte de deux figures --> <!-- scope: src/dashboard/views/meta_ads_overview.py, src/dashboard/utils/campaign_pair.py, tools/dev/charts_dossier/cross_view.yaml, tools/dev/, tests/ --> | P3 | tests : aucune largeur de trait ne code une métrique ; registre cross_view à jour |
| R577 | Vue croisée — supprimer « quelle campagne a acheté l'écoute la moins chère » (`campaign_compare.render#1`) <!-- critic: non — suppression --> <!-- scope: src/dashboard/utils/campaign_compare.py, tools/dev/charts_dossier/cross_view.yaml, tools/dev/, tests/ --> | P3 | test cross_view : figure absente du registre et de la marche |
| R578 | Vue croisée — « quel titre transforme le mieux les clics en écoutes » : autre visuel que Pareto (nuage clics × écoutes gagnées) ; hiérarchie campagne → ad set → pub explicite dans les libellés <!-- critic: non — refonte d'une figure --> <!-- scope: src/dashboard/utils/campaign_compare.py, src/dashboard/views/meta_creatives.py, tools/dev/, tests/ --> | P3 | test : figure en nuage ; libellé « campagne › ad set › pub » |
| R579 | Prédiction algos — deux filtres séparés : sortie de référence (défaut dernière) et sortie de comparaison (défaut avant-dernière) <!-- critic: non — sélecteurs --> <!-- scope: src/dashboard/views/trigger_algo/, tools/dev/, tests/ --> | P3 | test : défauts = dernière / avant-dernière |
| R580 | Prédiction algos — à côté de « déclenché par 3 paramètres », le poids SHAP en % de chaque paramètre et sa valeur <!-- critic: non — affichage --> <!-- scope: src/dashboard/views/trigger_algo/, tools/dev/, tests/ --> | P3 | test : chaque paramètre porte son % et sa valeur |
| R581 | Prédiction algos — remettre le budget Meta restant au meilleur CPR pour déclencher la playlist, et la valeur générée si déclenchée, à côté de chaque playlist <!-- critic: non — affichage de calculs existants --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/utils/algo_preview_data.py, tools/dev/, tests/ --> | P3 | test : budget restant et valeur par playlist rendus |
| R582 | Prédiction algos — description du graphique d'estimations (ce que dit le repère de référence) <!-- critic: non — texte --> <!-- scope: src/dashboard/views/trigger_algo/, tools/dev/, tests/ --> | P3 | rendu : description présente sous le graphique |
| R583 | Prédiction algos — mini-graphique « ce qu'un déclenchement rapporte » déplacé à côté de la playlist dans « où en sont mes titres », fusionné avec le taux de déclenchement <!-- critic: non — déplacement --> <!-- scope: src/dashboard/views/trigger_algo/, tools/dev/, tests/ --> | P3 | test : la section séparée n'existe plus |
| R584 | Prédiction algos — prévision : les deux titres (référence + comparaison) sur le MÊME graphique ; 5 ans et 10 ans en couleur distincte (long terme) <!-- critic: non — refonte d'une figure --> <!-- scope: src/dashboard/views/trigger_algo/, tools/dev/, tests/ --> | P3 | test : une figure, deux titres, horizons longs colorés à part |

---

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R575, R576, R577, R578, R579, R580, R581, R582, R583, R584 -->

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
