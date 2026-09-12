# ADR-022 — Le GRAIN vit en SQL, la PORTE lui donne sa forme

- **Status**: Accepted
- **Date**: 2026-09-12
- **Related**: ADR-019 (l'or est une frontière, pas un stockage), ADR-014 (les déclencheurs d'adoption dbt), ADR-013 (Meta multi-comptes)
- **Answers**: « la couche or gagne-t-elle un grain temporel, ou `platform_totals(db, aid, since, until)` reste-t-il la porte unique des fenêtres ? »

## Contexte

La question posée était binaire. Elle ne l'est pas : ce ne sont pas deux options
concurrentes, ce sont **deux étages**, et les deux existaient déjà sans être nommés.

|  | où | ce qu'il porte |
|---|---|---|
| **Le grain** | `v_platform_levels`, `v_s4a_song_daily`, `v_meta_daily`, `v_soundcloud_track_latest`, `v_meta_campaign_daily`… | la RÈGLE : déduplication, report en avant, retrait de la ligne « Total », exclusion d'une génération de lignes obsolète |
| **La porte** | `platform_totals(db, aid, since, until)` et ses voisines | la FORME : un dict, ne lève jamais, `None` ≠ `0`, résolution du locataire |

## Décision

**Le grain descend en SQL, systématiquement. La porte reste, et ne porte aucune règle.**

### Pourquoi le grain doit être en SQL

Reis & Housley, *Fundamentals of Data Engineering* p. 466 : une couche sémantique
consolide les définitions — *« write once, use anywhere »*. Le critère est
**« anywhere »**, et il est déjà vérifié ici : `src/api/routers/streams.py` lit
`v_platform_totals` depuis un **autre processus**, qui ne peut pas importer les portes
Python du dashboard. Airflow et `psql` sont les suivants. Une règle écrite en Python
n'est lisible que par Python.

Coût mesuré : le total seul 36 ms, la fenêtre dérivée des niveaux 45 ms, la série
complète 48 ms. **+9 ms pour le grain**, sans objet face à ADR-014.

### Pourquoi la porte reste

Elle ne duplique rien, elle met en forme : elle rend `None` quand rien n'a été mesuré
(jamais `0`), elle dégrade sans lever, elle applique la résolution du locataire. Ce sont
des décisions d'affichage. Une porte qui se mettrait à *calculer* devrait être coupée en
deux — c'est la vue qu'il faut allonger, pas la liste des exemptions.

### La limite, et c'est Kleppmann qui la pose

*Designing Data-Intensive Applications* p. 527 : procédures stockées et fonctions
définies par l'utilisateur « ont été un peu une arrière-pensée dans la conception des
bases », et la séparation du code applicatif et de l'état est la position par défaut.

Donc : **une VUE déclarative, toujours. Une fonction PL/pgSQL, seulement quand un
`GROUP BY` ne l'exprime pas.** `gold_apple_lifetime()` en est le seul cas — une
sélection gloutonne d'intervalles non chevauchants — et **doit le rester**. Le compte
est gelé à 1 par la classe `a-procedural-rule-in-the-database`, dont la signature
tourne en CI. Le franchir demandera une décision, pas une inadvertance.

## Ce que la décision coûte, et qu'il faut écrire

Une vue or est un objet de plus à faire vivre, et deux défauts mesurés le 2026-09-12
sont nés du passage lui-même, pas de la cible :

- **une colonne perdue au repointage.** La migration 106 a fait descendre la jointure
  créative dans `v_meta_creative_daily` ; le repointage a été fait colonne par colonne
  sur la liste du `SELECT`, et personne n'a regardé le `WHERE`. Trois requêtes
  filtraient sur `ad_account_id`, absent de la vue → la page tombait pour tout
  locataire multi-comptes. Gardé par
  `tests/test_an_account_filter_names_one_column.py`.
- **un agrégat qui n'est pas dans le SQL.** Une vue or ne protège rien si la surface
  lit des lignes brutes et les somme en pandas. Gardé par
  `tests/test_a_total_is_computed_where_a_guard_can_see_it.py`.

Une vue résout le « deux définitions » ; elle ne résout ni le « on a oublié une
colonne » ni le « le total est ailleurs ». Ces deux-là se gardent par des tests, et les
tests existent.

## Conséquence mesurée : le déclencheur dbt d'ADR-014 est ATTEINT

ADR-014 différait dbt tant que le dépôt n'aurait pas **≥ 10 objets dérivés ET ≥ 3 qui
dépendent l'un de l'autre**. Recompté le 2026-09-12, après les migrations 097 à 109 :

| Mesure | Valeur |
|---|---|
| objets dérivés (`v_*` + `gold_*`) | **13** |
| objets impliqués dans une dépendance entre dérivés | **4** (`v_platform_totals` → `v_s4a_song_daily`, `v_soundcloud_track_latest`, `gold_apple_lifetime`) |

Les deux conditions sont remplies. **Cette ADR ne tranche pas dbt** — elle enregistre
que le déclencheur qu'ADR-014 s'était donné a été franchi, et que la question se
rouvre donc légitimement. Ce qui manquait à ADR-014 pour être actionnable existe
maintenant : `.claude/dev-docs/gold-coverage.md` donne le graphe complet — quel objet
lit quoi, qui le lit, et ce que rien n'atteint.

## Alternatives écartées

- **Tout dans la porte Python.** Retenue jusqu'au 2026-09-10, abandonnée pour une
  raison mesurée : l'API est un autre processus et a déjà divergé du dashboard.
- **Une vue par fenêtre temporelle** (`v_platform_totals_30d`…). Multiplie les objets
  par le nombre de fenêtres et transforme un paramètre en schéma. La fenêtre est un
  argument, pas un grain.
- **Un `SELECT` matérialisé par plateforme.** Rien ne le justifie : 48 ms sur la série
  complète, et une matérialisation ajoute une fraîcheur à surveiller.
