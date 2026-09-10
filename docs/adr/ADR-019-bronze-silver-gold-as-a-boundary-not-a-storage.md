# ADR-019 — Bronze / argent / or est une FRONTIÈRE, pas un stockage

- **Status**: Accepted
- **Date**: 2026-09-10
- **Supersedes**: ADR-014 sur un seul point — le critère d'adoption d'une couche dérivée
- **Related**: ADR-002 (critère d'adoption d'un motif), ADR-007 (le travail de perf est conditionné), ADR-012 (le lignage est hors périmètre)
- **Closes**: roadmap R70 (la décision ; l'implémentation suit)

## Context

ADR-014 (2026-09-04) a différé dbt et toute la stack data moderne, avec des déclencheurs
calculables. Son déclencheur dbt : **≥ 10 objets dérivés ET ≥ 3 qui dépendent l'un de
l'autre**. Recompté le 2026-09-10, il n'est toujours pas atteint :

| Mesure (2026-09-10) | Valeur |
|---|---|
| Tables d'atterrissage brut | **64 / 95** |
| Tables **dérivées** (écrites par une transformation) | **2** (`imusician_monthly_revenue`, `distrokid_monthly_revenue`) |
| Vues SQL | **1** (`v_artist_monthly_revenue`) |
| Vues **matérialisées**, `REFRESH` | **0** — aucune occurrence dans tout le dépôt |
| Objets dérivés analytiques, dépendances entre eux | **5, zéro dépendance** |

**ADR-014 a posé la bonne question et compté la mauvaise chose.** Elle demandait « ai-je
assez de transformations ? ». Le balayage du 2026-09-10 donne l'autre chiffre : **18
calculs divergents de 6 métriques métier**, dont ADR-014 elle-même qualifie deux de
« défauts de correction vivants ».

| Ce qui est dupliqué | Ampleur mesurée le 2026-09-10 |
|---|---|
| `artist_id = %s` | **328** occurrences |
| Le filtre S4A `1x7xxxxxxx` | **35** fichiers |
| « dernière prédiction ML par titre » (`DISTINCT ON`) | **15** fichiers, dont l'API, le PDF et deux DAGs |
| Total de vues YouTube | **3 définitions incompatibles**, dont le compteur de chaîne prouvé ~10× faux, encore vivant sur `data_wrapped` et dans le PDF |
| Littéraux `SELECT` | vues **278** · utils **176** · PDF **53** (4ᵉ réimplémentation) · API **19** |

Et la même séance a produit trois défauts vivants issus de cette dispersion : un verdict
de rentabilité imprimé sur un PDF payant à partir d'une base injoignable, un e-mail
annonçant « 0 stream » à un artiste sans données, et une figure dessinant ×2,7 sa propre
mesure.

**Une couche conformée se justifie par le DÉSACCORD, pas par le volume.** C'est
l'argument neuf, et il n'annule aucune mesure d'ADR-014 : les 43 Mo et les 18,5 ms
restent vrais, et rien ici n'est motivé par la performance.

## Decision

Adopter le vocabulaire **bronze / argent / or** comme une **frontière qu'on fait
respecter**, implémentée par des **vues Postgres ordinaires et des helpers Python
partagés**. Aucun outil nouveau, aucune matérialisation, aucun découpage de stockage.

| Couche | Ce que c'est | Ce que ça coûte |
|---|---|---|
| **Bronze** | ce que les collecteurs et les parseurs écrivent, intact — les 64 tables existantes | **aucune migration** ; seulement la règle « rien ne lit le bronze directement » |
| **Argent** | une ligne par entité et par jour, conformée : la nature de chaque série y est résolue UNE fois (cumul → écart par entité, quotidien → tel quel, total de période → laissé à son grain) | `platform_timeseries.py` promu, plus une vue par plateforme |
| **Or** | une définition par métrique métier, et une seule : streams Spotify, vues YouTube, plays SoundCloud, plays Apple, followers Instagram, revenu mensuel | une vue par métrique |

Le précédent existe et il marche : `migrations/056_v_artist_monthly_revenue.sql` — une
vue Postgres ordinaire — a remplacé « les ~6 endroits qui copiaient-collaient cette
UNION » et compte **11 sites d'appel** aujourd'hui.

**Règle de livraison** : une plateforme à la fois, en commençant par YouTube (3
définitions divergentes). Jamais en balayage mécanique — ADR-007 rappelle qu'un balayage
« pour la cohérence » aurait donné à chaque admin les données de l'artiste 1. Les
définitions **fausses** partent d'abord ; les redondantes suivent une par une, chacune
avec son test.

## Alternatives rejetées

| Option | Pourquoi rejetée |
|---|---|
| **Un medallion MATÉRIALISÉ** (tables par couche, schémas ou préfixes) | Crée les objets dérivés et les dépendances qui déclenchent dbt par construction, sur une base de 43 Mo dont l'agrégat le plus lourd met 18,5 ms. On paierait un graphe de matérialisation pour un problème qui n'est pas de calcul. Et ADR-014 l'a mesuré : ces duplications vivent **dans des requêtes exécutées à la lecture**, donc matérialiser n'en retirerait **aucune**. |
| **Adopter dbt maintenant** | Son déclencheur est écrit et calculable, et il n'est pas atteint (5 objets, 0 dépendance). Ses tests génériques — la seule valeur qui manquait — existent déjà dans `data_quality_check.py:112-225`. Leur défaut n'est pas leur absence, c'est qu'ils finissent en `warnings.append()` et que le DAG n'a jamais été mis en service. |
| **Ne rien faire** | Trois défauts vivants en une séance, dont un sur un document payant. La dispersion n'est plus de la dette de style. |
| **Le lignage comme couche** | Écarté par ADR-012, avec son propre déclencheur. Rien ici ne le rouvre : la frontière décrite ci-dessus se lit dans le code, pas dans un graphe. |

## Consequences

### Positives
- Une métrique a **une** définition, lisible par le dashboard, l'API, le PDF et les DAGs.
- La règle « rien ne lit le bronze directement » est vérifiable mécaniquement, donc
  gardable — c'est ce qui manquait aux six définitions de CPR.
- Aucun composant ajouté : la stack reste Postgres + Airflow + Streamlit.

### Négatives / compromis
- Une vue de plus est une indirection de plus. Le seuil de tolérance est explicite :
  **une vue n'existe que si elle retire au moins deux sites d'appel divergents.**
- Le travail est long et se fait au fil de l'eau. Une couche à moitié posée est pire
  qu'aucune si elle laisse coexister l'ancien et le nouveau chemin sans le dire — d'où
  la règle « une plateforme à la fois, chacune avec son test ».

### Le déclencheur qui rouvre ADR-014
Le jour où la couche or compte **≥ 10 objets dérivés dont ≥ 3 interdépendants**, le
déclencheur dbt d'ADR-014 est atteint **par construction**. À ce moment-là, et pas avant,
deux options : ordonner les vues par leurs dépendances à la main, ou adopter dbt pour ses
tests génériques. Cet ADR ne présuppose pas la seconde.

Vérification du déclencheur, en une commande :
```bash
grep -rlE "CREATE (OR REPLACE )?VIEW" migrations/ | wc -l
```
