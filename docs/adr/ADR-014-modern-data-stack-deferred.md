# ADR-014 — La stack data moderne est différée ; le trou réel était ailleurs

- **Status**: Accepted
- **Date**: 2026-09-04
- **Related**: ADR-002 (critère d'adoption d'un motif), ADR-003 (React différé, mêmes déclencheurs), ADR-007 (la performance est conditionnée), ADR-012 (le lignage est hors périmètre)

## Context

Question posée : faut-il ajouter **dbt**, et plus largement Next.js/React, ECharts,
dlt, S3/R2, Parquet, DuckDB, ClickHouse, Supabase, Dagster ? Objectif déclaré :
**stabilité, robustesse, rapidité, long terme.**

Tout ce qui suit a été mesuré en production le 2026-09-03, pas estimé.

| Mesure | Valeur |
|---|---|
| Lignes en base, toutes tables | **49 096** |
| Taille de la base | **43 Mo** |
| Tables peuplées / existantes | **50 / 94** |
| Plus grosse table | `soundcloud_tracks_daily`, **21 813** lignes |
| Agrégat complet `GROUP BY` sur cette table | **18,5 ms** |
| Croissance | **2 736 lignes/jour** (≈ 1 M/an à la locataire actuelle) |
| Machine | 4 vCPU, 7,7 Go — **4,8 Go libres**, charge **12 %** |
| RAM Postgres / RAM Airflow | **172 Mo** / **1,6 Go** |
| Locataires avec de la donnée | **1** ; 6 invités, rétention 0/6 |

Deux lignes tranchent la moitié de la liste : **43 Mo** et **18,5 ms**. Il n'existe
aujourd'hui aucun problème analytique. Et **Airflow coûte dix fois la base qu'il
orchestre** — si un poste mérite d'être interrogé dans cette stack, ce n'est pas le
stockage.

## Le critère, déjà posé par ADR-002

On adopte un motif quand le problème qu'il résout est **présent ici** — pas parce
qu'une architecture de référence l'a. ADR-002 a rejeté 7 motifs sur 10 sur ce critère,
et adopté les 3 qui étaient *« low cost and clear benefit regardless of project
criticality »*. Cet ADR applique la même grille.

## Decision

**Différer l'ensemble de la stack proposée.** Chaque refus porte un déclencheur
mesurable ; aucun n'est « quand ça deviendra gros ».

| Outil | Verdict | Déclencheur de réouverture, **calculable** |
|---|---|---|
| **ClickHouse** | Non | Un agrégat de tableau de bord dépasse **1 s** en conteneur, ou une table dépasse **10 M lignes**. Aujourd'hui : 18,5 ms / 21 813 lignes. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| **Parquet + S3/R2 en stockage brut** | Non | La base dépasse **50 Go**. Aujourd'hui : 43 Mo. `SELECT pg_database_size('spotify_etl')` |
| **DuckDB** | Non | Un besoin analytique sans serveur SQL disponible. Il y en a un, à 172 Mo |
| **dlt** | Non | Une 3ᵉ plateforme à intégrer **la même semaine**. Les 6 collecteurs existants sont gardés par la règle #6 et `audit_collectors_ast.py` |
| **Dagster** | Non | Voir « Conséquences » : le levier mesuré n'est pas l'orchestrateur |
| **Supabase** | Non | C'est Postgres plus des services déjà construits ici (auth, Stripe) |
| **Next.js + React** | Déjà décidé | ADR-003, 4 signaux, relus le 2026-08-30, aucun tiré |
| **ECharts** | Non | Une limite de plotly rencontrée sur une vue réelle. 29 vues l'utilisent |
| **dbt** | Différé | **≥ 10 objets dérivés ET ≥ 3 qui dépendent l'un de l'autre.** Aujourd'hui : 5 objets, **0 dépendance** |

### dbt, en détail — la seule qui méritait un examen

Sa valeur, telle que la décrivent Moses/Gavish/Vorwerck (*Data Quality Fundamentals*,
p. 76-77), n'est **pas** la performance : c'est **tester, modulariser et documenter des
transformations**. La question est donc « ai-je assez de transformations », pas « assez
de données ».

**La première mesure était fausse, et la corriger a rendu la conclusion plus solide.**
Chercher `CREATE VIEW` dans les migrations rend **1** (`v_artist_monthly_revenue`). La
vraie couche dérivée en compte **5** : quatre sont des `INSERT … SELECT` dans des
modules Python — `src/utils/imusician_rollup.py:16`, `src/utils/distrokid_rollup.py:19`,
`ml_song_predictions` via `airflow/dags/ml_scoring_daily.py:86`, et
`s4a_song_algo_outcomes` via `src/utils/ml_outcome_labeling.py:129`. Un `grep` sur un
mot-clé SQL ne pouvait pas voir 80 % de la réponse.

Et la duplication est massive, mesurée, et **par endroits déjà fausse** :

| Ce qui est dupliqué | Ampleur |
|---|---|
| Le filtre `1x7xxxxxxx` | ~60 sites, **5 orthographes**. `data_quality_check.py:121-125` l'écrit deux fois dans le même `NOT EXISTS` |
| `artist_id = %s` | **286 sites** ; la primitive `auth.artist_id_sql_filter()` n'est utilisée que dans **6 fichiers** |
| Le KPI **CPR** | **5 définitions**, arrondis et NULL différents, contre **2 tables sources** |
| « dernière prédiction ML par titre » | 6 copies du même `DISTINCT ON` |
| « streams récents » | **7/28/35-7 j** pour le modèle (`ml_inference.py:264`), **7/14-7 j** pour l'e-mail artiste (`weekly_digest.py:119`) |

Les deux dernières ne sont pas de la dette de style : **ce sont des défauts de
correction vivants.**

**Pourquoi dbt ne les résout pas.** dbt **matérialise** — il construit des tables à
partir d'autres tables dans un graphe qu'il ordonne. Or ces duplications vivent
**à l'intérieur de requêtes que Streamlit exécute à la lecture, contre des tables
vivantes**. Adopter dbt ne retirerait **aucun** de ces sites : on aurait un outil de
plus, et les cinq CPR seraient toujours là.

Ce qui les retire, ce dépôt l'a déjà fait et écrit :
`migrations/056_v_artist_monthly_revenue.sql` documente que cette **vue Postgres
ordinaire** a remplacé « les ~6 endroits qui copiaient-collaient cette UNION ». Elle a
11 sites d'appel aujourd'hui. C'est le précédent, il marche, et il coûte une migration.

**Ce que dbt aurait apporté et qu'on prend séparément** : ses tests génériques. Ils
existent déjà — `airflow/dags/data_quality_check.py:112-225` implémente cinq contrôles
correspondant un pour un à `relationships`, `accepted_values`, `unique` et un contrôle
de volume. Leur défaut est qu'ils finissent dans un `warnings.append()` : **ils ne font
échouer aucune construction.** Une migration de contraintes comble ça sans runtime.

## Le trou que la question ne cherchait pas

En vérifiant la robustesse — l'objectif déclaré — deux trous réels, aucun lié à dbt :

1. **Les 21 sauvegardes quotidiennes vivent sur `/dev/sda1`, le disque de la base.**
   Aucune copie hors-site : le `crontab` ne contient ni `rsync`, ni `s3`, ni `rclone`.
   Si ce disque meurt, **les sauvegardes meurent avec la base**.
2. **`tools/db_restore_test.sh` existe et n'est jamais lancé.** Trois crons tournent,
   aucun ne restaure. Une sauvegarde jamais restaurée n'est pas prouvée.

**L'intuition « S3 / Cloudflare R2 » était donc juste — mais pour la durabilité des
sauvegardes, pas pour un data lake.** Les deux sont corrigés dans la même séance.

## Consequences

- La stack reste **Postgres + Airflow + Streamlit**. Aucun composant ajouté, aucun
  fournisseur de plus à surveiller.
- **Airflow était le poste le plus cher, et il a été traité le 2026-09-04** — sans
  changer d'orchestrateur. Trois mesures, trois corrections :

  | Constat mesuré | Correction | Résultat mesuré |
  |---|---|---|
  | 16 DAGs reparsés **toutes les 30 s** (défaut d'Airflow) ; scheduler à **28,9 %** de CPU, webserver à 0,33 % | `AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL` 30 → 300 | **CPU 2,45 %**, RAM scheduler **878 → 622 Mo** |
  | Les 4 `*_csv_watcher` = **97,2 % des `dag_run`** et **98,4 % des `task_instance`**, 1 536 exécutions/jour, toutes `skipped`, sur des répertoires **vides** | cadence `*/15` → horaire | 1 536 → **384** exécutions/jour |
  | Base de métadonnées à **246 Mo** — six fois la base applicative — 83 jours jamais purgés, `airflow db clean` **jamais lancé** | `tools/airflow_db_clean.sh`, cron hebdomadaire, rétention 30 j, plus un `VACUUM FULL` initial | **246 → 91 Mo** |

  **Non fait, et c'est une décision** : fusionner les 4 watchers en un seul. À cadence
  horaire cela économise 72 exécutions/jour pour un refactor touchant 4 DAGs, 4 scripts
  de debug et leurs parseurs. Le levier était la **cadence**, pas le nombre de DAGs —
  et ADR-007 pose que dépenser du risque contre un bénéfice mesuré proche de zéro est
  le défaut, pas le correctif.

  Ce que la mesure a aussi corrigé : réduire les exécutions ne rend **pas** la RAM.
  Les 1,6 Go sont les processus Python eux-mêmes. C'est l'intervalle de parsing qui a
  rendu 256 Mo, pas la cadence des watchers.
- La duplication se traite **au fil de l'eau**, jamais en balayage : ADR-007 rappelle
  qu'un balayage mécanique « pour la cohérence » aurait donné à chaque admin les données
  de l'artiste 1. Seules les deux définitions **fausses** se corrigent tout de suite.
- **Ce qu'aucun de ces outils ne déplace** : 6 locataires invités, 1 seul avec de la
  donnée, rétention 0 sur 6, 0 dépôt CSV sur 4. C'est un fait de produit, pas
  d'architecture.

## Comment relire cette décision

Chaque déclencheur du tableau est une commande. Les relire coûte cinq minutes :

```bash
# volume et taille
docker exec <pg> psql -U postgres -d spotify_etl -tA -c \
  "SELECT sum(n_live_tup), max(n_live_tup), pg_size_pretty(pg_database_size('spotify_etl')) FROM pg_stat_user_tables"
# objets dérivés (le déclencheur dbt)
git grep -clE "INSERT INTO .* SELECT" -- 'src/**/*.py' 'airflow/dags/*.py' | wc -l
git grep -cE "CREATE (OR REPLACE )?(MATERIALIZED )?VIEW" -- 'migrations/*.sql'
```

Comme ADR-007, cet ADR est fait pour être **relu contre la production**, pas cru.
