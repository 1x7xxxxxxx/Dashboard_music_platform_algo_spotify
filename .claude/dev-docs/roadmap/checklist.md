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
| R607 | REA·1 — actions GitHub épinglées par SHA + garde : MESURER les `uses:@tag` (37 contre 2 SHA) et le bruit de Dependabot `github-actions` sur 30 j → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure — **DÉCIDÉ OUI 2026-10-15** : mesuré 37 `uses:` dont 2 par SHA ; `gitleaks/gitleaks-action@v2` (tierce, tag mobile) reçoit `GITHUB_TOKEN` (security-nightly.yml:213) ⇒ critère tenu ; bruit Dependabot actions = 1 PR/30 j (#179). Défaut vivant trouvé : `check_action_drift.py` déclare les 2 épinglages SHA existants « 🚫 INTROUVABLE » chaque nuit (fausse alerte). code-critic BUILD-MODIFIED : tout épingler (pas de liste blanche « first-party »), outil de dérive lisant la version du commentaire ET vérifiant commentaire↔SHA (« COMMENTAIRE MENTEUR »), garde en lecture ligne à ligne couvrant `.github/actions/*/action.yml` ; `permissions:` de security-nightly = ligne séparée <!-- critic: fait --> <!-- scope: .github/, tools/dev/, tests/, .claude/dev-docs/ --> | P2 | oui si ≥1 action tierce non épinglée voit un secret ; garde : 0 `uses:@v` hors action locale |
| R608 | REA·2 — SECURITY.md (+ DISCLAIMER) : MESURER ce qui existe (adresse de signalement, `security/`, pages légales de l'app) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: SECURITY.md, .github/, tests/, .claude/dev-docs/ --> | P3 | oui si aucune voie de signalement privée n'existe ; test de présence |
| R609 | REA·3 — cliquet de code mort (`vulture`) : MESURER l'entonnoir candidats bruts → faux positifs (`show()`, DAGs, fixtures) → sites vivants, muté dans les deux sens (règle 20) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: pyproject.toml, uv.lock, requirements.txt, Makefile, tests/, tools/dev/, .claude/dev-docs/ --> | P3 | oui si ≥2 sites vivants ; cliquet par fichier qui ne peut que descendre |
| R610 | REA·4 — coût de CLAUDE.md (7 640 mots contre 1 455) : MESURER les tokens par section et le nombre de séances où chaque section a changé une décision (transcripts 30 j) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: CLAUDE.md, .claude/, tools/dev/, tests/ --> | P3 | oui si une section ne sert jamais en 30 j ; budget d'octets abaissé d'autant |
| R611 | REA·5 — mutation ciblée (Stryker `mutationRanges` contre `mutate_guards.py` hebdo) : MESURER gardes jamais mutés / gardes totaux → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: tools/dev/, .github/workflows/, tests/, .claude/dev-docs/ --> | P4 | oui si >20 % des gardes n'ont jamais rougi |
| R612 | REA·6 — CI planifiée par le diff : MESURER la durée de la CI sur 30 runs de main → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: .github/workflows/, tools/dev/, tests/, .claude/dev-docs/ --> | P4 | oui si p50 > 15 min ; sinon condition d'attente écrite |
| R613 | REA·7 — tests à côté du code plutôt que sous `tests/` : MESURER le coût de collecte et de sélection (`select_tests.py`) des deux formes → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: tests/, tools/dev/, .claude/dev-docs/ --> | P4 | oui si la sélection gagne >20 % ; sinon clos |
| R614 | REA·8 — étiquette « mesuré / calculé / projeté » sur les figures (leur enveloppe de preuve) : MESURER le nombre de figures qui mêlent mesure et projection → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: src/dashboard/, tests/, .claude/dev-docs/ --> | P3 | oui si ≥1 figure mêle les deux sans le dire |
| R615 | REA·9 — utiliser REA sur un concurrent (Chartmetric, Songstats, Soundcharts) : MESURER ce que leurs CGU autorisent et la question produit à laquelle ça répondrait → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: .claude/dev-docs/ --> | P4 | oui seulement si les CGU le permettent ET une question produit est nommée |
| R616 | REA·A1 — frontières entre couches imposées (leur `module-boundaries.mjs`) : MESURER avec import-linter en rapport les arcs montants (`src/utils/platform_probes.py`→dashboard, `src/api/deps.py`→dashboard…) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: pyproject.toml, uv.lock, requirements.txt, Makefile, src/, tests/, .claude/dev-docs/ --> | P3 | oui si ≥2 arcs non justifiés ; cliquet qui ne peut que descendre |
| R617 | REA·A2 — un contrat par objet, plusieurs consommateurs (leur `ToolContract`) : MESURER les objets dont la forme est définie ≥2 fois (Pydantic `src/models/`, modèles en ligne `src/api/routers/`, colonnes lues par le dashboard) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: src/models/, src/api/, src/dashboard/, tests/, .claude/dev-docs/ --> | P3 | oui si ≥2 objets ont divergé ou peuvent diverger |
| R618 | REA·A3 — erreurs typées + projection stable `{code, catégorie, retryable, remède}` : MESURER la part d'`app_error_log` sans classe typée et les défauts mal routés (retry ou alerte) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: src/utils/, src/api/, src/dashboard/, src/collectors/, tests/, .claude/dev-docs/ --> | P3 | oui si >30 % des empreintes n'ont pas de classe, ou ≥1 mauvais routage |
| R619 | REA·A4 — configuration validée par un schéma au démarrage : MESURER les clés de `config.yaml`/`.env` lues sans validation et les incidents passés dus à une clé absente → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: src/utils/, config/, tests/, .claude/dev-docs/ --> | P3 | oui si ≥1 incident passé ou ≥5 clés non validées |
| R620 | REA·A5 — niveaux de tests + seuils de couverture par couche : MESURER la couverture actuelle par couche (collectors, transformers, utils, api, dashboard) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: pyproject.toml, Makefile, .github/workflows/, tests/, .claude/dev-docs/ --> | P4 | oui si une couche est sous 60 % ; plancher par couche |
| R621 | REA·A6 — versionnage, CHANGELOG, compatibilité d'API : MESURER les consommateurs externes de l'API et l'écart `pyproject 0.1.0` ≠ API `1.0.0` → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: pyproject.toml, src/api/, tests/, .claude/dev-docs/ --> | P4 | oui si ≥1 consommateur externe ; sinon une seule version vraie + condition d'attente |
| R622 | REA·A7 — catalogue des messages d'erreur visibles (leur `user-visible-errors.csv`) : MESURER les messages visibles qui nomment un détail interne (DAG, table, variable) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: src/dashboard/, tools/dev/, tests/, .claude/dev-docs/ --> | P3 | oui si ≥1 message nomme la plomberie ; catalogue généré + garde |

---

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R607, R608, R609, R610, R611, R612, R613, R614, R615, R616, R617, R618, R619, R620, R621, R622 -->

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
