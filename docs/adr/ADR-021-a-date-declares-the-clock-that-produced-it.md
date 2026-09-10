# ADR-021 — Une date déclare l'horloge qui l'a produite

- **Statut** : accepté — 2026-09-10
- **Supersède** : rien. Complète ADR-019 (bronze/argent/or comme frontière) sur l'axe du temps.
- **Contexte** : septième et dernière cause de l'audit de la figure d'accueil du 2026-09-10.

## Décision

Chaque colonne de date du produit déclare, dans `src/utils/clocks.py`, laquelle des
**quatre horloges** l'a produite :

| Horloge | Ce qu'elle produit | Exemples |
|---|---|---|
| `OURS` | un **instant**, UTC, écrit par nos collecteurs | `collected_at`, `snapshot_date`, `day_date`, `run_date` |
| `PUBLISHER_FILE` | un **jour calendaire** lu dans un fichier déposé | `date` (S4A), `reporting_date`, `release_date` |
| `PUBLISHER_FILENAME` | un **jour calendaire** lu dans un nom de fichier | `period_start`, `period_end` (Apple) |
| `READER` | un **jour calendaire** choisi dans un sélecteur | les bornes de période |

Deux constantes séparent ce que le dépôt confondait : `MEASUREMENT_TZ = "UTC"` décide
d'un **jour de mesure** ; `DISPLAY_TZ = "Europe/Paris"` décide de ce qu'un lecteur voit.
Un jour de mesure ne dépend pas de la machine qui affiche.

Et une règle, qui est l'inverse de ce qu'on attendait : **seules les dates de l'horloge
`OURS` sont convertibles.** Les trois autres portent un jour calendaire ; il n'y a pas
d'instant à réinterpréter.

## Ce que la mesure a dit, et pourquoi elle a retourné la décision

Le dossier d'architecture annonçait cette cause « ouverte » et je l'avais chiffrée à
« 200 lignes sur 2 535, 7,9 % ». **Ce chiffre était faux** — mesuré sur une base locale,
il mélangeait deux ères. Recompté en production le 2026-09-10 :

| Population | Lignes qui changent de jour selon le fuseau |
|---|---|
| `collected_at` post-migration-019 (YouTube) | **0 sur 5 807** |
| post-019, toutes plateformes | **29** — toutes des collectes déclenchées à la main, jusqu'à 23 h UTC |
| pré-019 (YouTube) | 267 — mais ce sont des `DATE`, pas des instants |

Les collectes nocturnes atterrissent à **10 h UTC**, à plus de quatre heures de toute
frontière de jour. La marge minimale mesurée est de 15 199 s.

Donc : **le risque était à l'envers**. Le danger n'est pas de laisser `collected_at`
tranquille, c'est de le « corriger ». Une harmonisation des fuseaux appliquée sans
distinction déplacerait 267 jours calendaires déjà justes d'une journée entière — et
c'est exactement la forme qu'une future tâche « unifier les fuseaux » prendrait.

## Alternatives rejetées

1. **Tout convertir en UTC, y compris les dates d'éditeur.** Rejeté : mesuré, cela
   déplace 267 jours déjà justes. Un jour calendaire n'a pas d'instant à convertir, et
   personne ne sait dans quel fuseau Spotify arrête sa journée de reporting.
2. **Passer toutes les colonnes en `timestamptz`.** Rejeté : 51 tables, une migration
   lourde, pour une population où **0 ligne** de l'ère actuelle est concernée. Le coût
   n'est pas payé par un défaut mesurable ; il le serait par une frontière de jour que
   la collecte n'approche pas.
3. **Ne rien déclarer et documenter en prose.** Rejeté pour la raison centrale de ce
   dépôt : une règle écrite que rien ne vérifie dérive — observé six fois. La
   déclaration est du code, et un test la tient.
4. **Décaler les collectes pour éloigner la frontière.** Rejeté : elles en sont déjà
   loin (10 h UTC). Les 29 lignes concernées viennent de déclenchements manuels, qu'on
   ne veut pas interdire.

## Ce qu'on ne peut pas fermer, et qu'on nomme

Les journées de reporting de Spotify et d'Apple sont arrêtées dans **leur** fuseau,
qu'aucun des deux ne publie. Un total « du 1er au 31 » peut donc différer du leur de
quelques heures aux bords. Cet écart n'est pas corrigeable. `UNRECONCILABLE_NOTE` le
dit là où deux sources d'horloges différentes sont additionnées — le nommer est le
correctif, l'effacer serait la faute.

## La règle d'expédition

Une nouvelle colonne de date entre avec son horloge déclarée, ou
`tests/test_a_naive_timestamp_is_not_reinterpreted.py` rougit. Et aucune surface ne
convertit le fuseau d'une date qui n'est pas de l'horloge `OURS` — le même test le
balaie sur `src/` et `airflow/`, par l'AST, en excluant les docstrings.
