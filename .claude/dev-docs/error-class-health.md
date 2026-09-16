<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**369 classes.** Fenêtre observée : `2026-05-15` → `2026-09-17` (205 révisions du catalogue rejouées).

## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **369** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
| « 57 récidives » | **non reproductible** : cinq définitions défendables donnent 39 / 49 / 55 / 67 / 167. Ce document n'en retient qu'une, écrite ci-dessous, et c'est celle que le cliquet utilise |
| gardes 15,1 % contre prose 22,7 % | voir les intervalles : les sous-groupes portent trop peu d'évènements pour trancher |
| le taux s'améliore (38 → 18 → 9 %) | **il empire** une fois normalisé par l'exposition. L'ancien chiffre comptait comme « n'a pas récidivé » des classes trop jeunes pour avoir pu le faire |
| `--fields` rouge sur 29 classes | **vert** — le commentaire du Makefile était périmé |

## La définition, une seule

> **Une récidive est un commit qui AJOUTE une ligne d'historique à une classe**, dans la fenêtre où le catalogue est versionné.

Elle vient de git, donc aucun champ tenu à la main ne peut la contredire. Un compteur écrit à côté serait une seconde définition de la même grandeur, et elles ne se comparent jamais.

## Population

| grandeur | valeur |
|---|---|
| `automatic_guard` | 351 |
| `classes` | 369 |
| `ever_recurred_observed` | 47 |
| `prose_only` | 18 |
| `with_signature` | 358 |

## Les trous — ce que le cliquet fait baisser

Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.

| trou | classes |
|---|---|
| `cause_inferred` | 0 |
| `cause_unknown` | 241 |
| `guards_ref_missing` | 0 |
| `scope_family_invalid` | 0 |
| `scope_unknown` | 0 |
| `scope_without_not_covered` | 331 |
| `seen_red_never` | 0 |
| `seen_red_unknown` | 331 |

## Récidive observée

**58 évènements** sur 7997 classe-jours d'exposition — **0.2205** par classe-mois (IC 95 % : 0.1674 – 0.285)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 50 | 0.1965 | 0.1458 – 0.259 | **séparent** |
| by_guard · prose | 8 | 0.9354 | 0.4028 – 1.8432 | **séparent** |
| by_seen_red · daté | 1 | 0.1567 | 0.002 – 0.8718 | insuffisant pour conclure (n=58) |
| by_seen_red · jamais-ou-inconnu | 57 | 0.2221 | 0.1682 – 0.2877 | insuffisant pour conclure (n=58) |
| by_scope · ne-couvre-pas renseigné | 43 | 1.1154 | 0.8071 – 1.5024 | **séparent** |
| by_scope · non renseigné | 15 | 0.0668 | 0.0374 – 0.1102 | **séparent** |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

## Cohortes à horizon fixe

Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, jamais `0`.

| horizon | à risque | récidivées | taux |
|---|---|---|---|
| 7 j | 269 | 36 | 13 % |
| 14 j | 175 | 31 | 18 % |
| 30 j | 35 | 13 | 37 % |

## Avant la fenêtre git — DÉCLARATIF

5 classes introduites avant `2026-05-15`, 5 portant une date postérieure à leur `first_seen`.

⚠️ DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé. Le catalogue n'entre dans git qu'à cette date : tout ce qui précède a été écrit de mémoire, après coup. Comparer les deux serait `a-threshold-carried-across-instruments` appliqué à notre propre métrique.
