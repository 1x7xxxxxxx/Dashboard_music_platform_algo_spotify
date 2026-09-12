# ADR-023 — dbt n'est pas adopté, et ce qui ferait changer d'avis

- **Status**: Accepted
- **Date**: 2026-09-12
- **Related**: ADR-014 (les déclencheurs d'adoption), ADR-019 (l'or est une frontière), ADR-022 (le grain en SQL, la porte en Python)
- **Closes**: roadmap R100

## Contexte

ADR-014 différait dbt derrière un déclencheur **calculable** : ≥ 10 objets dérivés ET
≥ 3 qui dépendent l'un de l'autre. Recompté le 2026-09-12, il est **franchi** :

| Mesure | Valeur |
|---|---|
| objets dérivés (`v_*` + `gold_*`) | **15** |
| arêtes entre dérivés | 3 (`v_platform_totals` → `v_s4a_song_daily`, `v_soundcloud_track_latest` ; `v_artist_monthly_revenue` → `v_sacem_monthly`) |
| objets impliqués dans une dépendance | **5** |
| profondeur maximale du graphe | **2** |
| SQL de la couche or | ~1 000 lignes sur 109 migrations |

Un déclencheur franchi n'est pas une décision. Il oblige à instruire la question,
pas à répondre oui.

## Décision

**Non.** La couche or reste des migrations SQL versionnées, appliquées par
`make migrate`.

### Ce que dbt vendrait, et ce qui l'achète déjà ici

| Ce que dbt apporte | État ici |
|---|---|
| Graphe de dépendances et ordre de construction | **profondeur 2, trois arêtes.** L'ordre est le numéro de migration, et il tient sur une ligne. |
| Tests de données (`unique`, `not_null`, `accepted_values`) | **5 282 tests pytest**, dont les gardes de cette session — un cliquet sur les agrégats hors couche or, un sur les totaux calculés en pandas, un sur les filtres de compte. dbt ne teste que ce qui est DANS la base ; la moitié des défauts de cette session vivaient dans le Python qui la lit. |
| Documentation générée du lignage | **`.claude/dev-docs/gold-coverage.md`**, qui va plus loin : il relie chaque vue or à la FIGURE et à la TUILE qui la lisent, ce que dbt ne voit pas. |
| Matérialisation incrémentale | **sans objet** : `read=0` sur l'agrégat le plus lourd (ADR-014), la base tient dans `shared_buffers`, la série complète coûte 48 ms. |
| Environnements (dev/prod) séparés | un seul schéma, un seul déploiement. |

### Ce que dbt coûterait, mesuré et non estimé

- une dépendance Python de plus dans une image déjà construite, et un binaire à
  installer dans le conteneur Airflow qui monte `src/` en bind-mount ;
- une **seconde** façon d'appliquer un changement de schéma, à côté de
  `make migrate`. Ce dépôt a une classe pour ça (`une-configuration-qui-diverge-de-la-prod`)
  et un test qui compare le dépôt à la production ;
- la réécriture des 15 objets en modèles, sans qu'aucun chiffre ne bouge — un
  refactor à valeur zéro le jour où on le fait, et à risque non nul.

Le rapport est mauvais **à cette taille**. Il ne le sera pas toujours.

## Le prochain déclencheur, et il n'est pas le même

ADR-014 comptait les objets. C'était le bon critère pour décider d'instruire ; c'est
le mauvais pour décider d'adopter, parce qu'il ne mesure pas ce qui fait mal. Ce qui
ferait mal ici, ce serait **de ne plus pouvoir dire dans quel ordre reconstruire**.

Donc le déclencheur devient :

> **profondeur du graphe des dérivés ≥ 4**, ou **≥ 3 objets dont la reconstruction
> demande un ordre qui n'est pas celui des numéros de migration**.

Il se recompte en une requête, et le compte vit dans la carte :

```sql
SELECT count(*) FROM pg_depend d
JOIN pg_rewrite r ON r.oid = d.objid
JOIN pg_class dep ON dep.oid = r.ev_class
JOIN pg_class src ON src.oid = d.refobjid
WHERE d.classid = 'pg_rewrite'::regclass
  AND dep.relname LIKE 'v_%' AND src.relname LIKE 'v_%'
  AND dep.relname <> src.relname;
```

La profondeur est à **2**. Le jour où elle atteint 4, cette ADR est à rouvrir — et
la carte donnera le graphe complet pour instruire la question, ce qui manquait à
ADR-014.

## Alternative écartée

**Adopter dbt « pour être prêt ».** C'est le raisonnement qu'ADR-002 rejette : un
motif s'adopte sur un coût mesuré, pas sur une anticipation. Les quinze objets
s'écrivent aujourd'hui en SQL lisible, avec le commentaire qui dit POURQUOI la règle
existe — et ce commentaire, dbt ne le rendrait ni plus vrai ni plus lu.
