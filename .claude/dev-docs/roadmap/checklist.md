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
| R692 | Courrier du parc msg:1793508762207058573-3097918 (fleet_apply) : (a) guard-lineage `guard_destructive.py` copie 9e456bd3 de lignée inconnue — vérifier qu'elle porte les octets du maître ; (b) blocs `cadrage:auto` de `docs/CADRAGE.md` en retard sur HEAD — générés par `project_brief.py` du master, que cette séance n'exécute pas : consigner au master <!-- scope: .claude/hooks/guard_destructive.py docs/CADRAGE.md --> <!-- critic: non — vérification d'octets + courrier, aucun code --> | P4 | `sha256sum` égal au maître ; courrier posté |
| R693 | Courrier du parc msg:1793519445111134427-1212512 (fleet_apply) : preset-refresh `roadmap_empty_beep.py` périmé — porter le preset `governance` du maître (T602 : un close par appel ; T609 : mots simples cause/garde/intégration des lignes 🙋) et remplir ces trois champs sur R686 et R661 <!-- scope: .claude/hooks/roadmap_empty_beep.py .claude/dev-docs/roadmap/checklist.md --> <!-- critic: non — copie verbatim d'un preset du parc --> | P4 | `diff` vide avec le preset ; `py_compile` ; tests du hook |
| R694 | Courrier du parc msg:1793623153287415207-499640 (fleet_apply) : (a) preset-refresh `roadmap_empty_beep.py` — même geste que R693 ; (b) `STACK.md` en retard sur le relevé du 2026-11-01T15:23:05Z — fichier généré par `stack_inventory.py` du master (« ne pas éditer », sha), non exécutable ici : consigner au master <!-- scope: .claude/hooks/roadmap_empty_beep.py STACK.md --> <!-- critic: non — courrier --> | P4 | R693 livrée ; courrier posté |
| R695 | Arbre sale : `test-suite-timing.json` porte une suite du 2026-11-02 verte mais à 857 skipped (12 400 passed contre 13 145 base allumée) — rejouer `make test` base allumée et commiter son verdict <!-- scope: .claude/dev-docs/test-suite-timing.json --> <!-- critic: non — fichier de mesure --> | P4 | `.pytest-last.log` ; `git status` propre |

---

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R686, R661, R692, R693, R694, R695 -->
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
| R686 | Les 18 nuits de pause (depuis le 2026-10-15) restent écrites `delivered = TRUE` dans `monitoring_run` en prod : R685 corrige les nuits à venir, pas celles-ci, indiscernables d'un vrai envoi. Tant qu'elles y sont, la première alerte après la reprise peut être réduite à « inchangé depuis le mail du X » si son empreinte égale celle d'une nuit en pause encore dans la fenêtre de répétition. <!-- critic: oui — code-critic R685, item 5 : pas une migration (date de reprise inconnue, `make migrate` touche tous les environnements) --> <!-- scope: .claude/dev-docs/runbook-actions-utilisateur.md --> <!-- problème: la date de fin de la fenêtre est la date de reprise, que seul le propriétaire fixe --> <!-- reco: Attendre — à faire le jour où OPS_MAIL_PAUSED repasse à False, pas avant --> <!-- cause: pendant la pause des mails de surveillance, chaque nuit a été notée « envoyée » alors que rien ne partait ; le correctif ne vaut que pour les nuits suivantes, pas pour celles déjà notées --> <!-- garde: le test qui vérifie qu'une nuit en pause n'est plus notée envoyée, puis la première alerte après la reprise, qui doit arriver complète et pas réduite à « inchangé » --> <!-- intégration: le jour où tu relances les mails, la séance de ce projet remet à « non envoyé » les nuits de pause dans la base de production, après une sauvegarde ; aucun autre projet du parc n'est touché --> | P2 | ⏳ reprise des mails ops (`OPS_MAIL_PAUSED = False`) : lancer la mise à jour du runbook § 48 sur la base de prod, sauvegarde faite avant |
| R661 | Norme RQ — deux questions de produit sorties de R649 : (1) le dossier d'architecture (33 p., 6 625 mots, score 2/8 en `decision`) ne porte AUCUNE décision ouverte — l'exempter des règles RQ-1 à RQ-4 comme document de référence (écrit dans son README), ou lui écrire une feuille de décision ? (2) le PDF artiste (`pdf_exporter`) doit-il passer la norme ? (3) le dossier des graphiques (`charts_dossier`, R649 C) : noté 5/8 en `--strict` sur `revue/dossier-graphiques.pdf` (83 p., 17 356 mots pour un budget de 2 500 — RQ-7 ; aucun arbre 5M ni cause racine — RQ-3 ; pas de palliatif — RQ-4) : le scinder en une feuille de décision ≤ 2 500 mots + une annexe séparée, ou l'exempter comme revue ? <!-- critic: non — question au propriétaire --> <!-- scope: .claude/dev-docs/runbook-actions-utilisateur.md --> <!-- cause: la nouvelle norme de rédaction des rapports a noté trois documents pour lesquels elle n'a pas été pensée : le dossier d'architecture, le rapport PDF de l'artiste et le dossier des graphiques --> <!-- garde: le contrôle de la norme, qui doit passer sur chacun de ces documents ou l'exempter noir sur blanc --> <!-- intégration: tu réponds aux trois questions, la séance de ce projet applique ton choix ici ; aucun autre projet du parc n'est concerné --> | P3 | répondre (1) exempter / feuille, (2) oui / non, (3) scinder / exempter — runbook § 46 |
