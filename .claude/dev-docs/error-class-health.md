<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**365 classes.** Fenêtre observée : `2026-05-15` → `2026-09-16` (199 révisions du catalogue rejouées).

## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **365** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
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
| `automatic_guard` | 347 |
| `classes` | 365 |
| `ever_recurred_observed` | 46 |
| `prose_only` | 18 |
| `with_signature` | 354 |

## Les trous — ce que le cliquet fait baisser

Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.

| trou | classes |
|---|---|
| `cause_inferred` | 0 |
| `cause_unknown` | 242 |
| `guards_ref_missing` | 0 |
| `scope_family_disagreements` | 6 |
| `scope_unknown` | 0 |
| `scope_without_not_covered` | 351 |
| `seen_red_never` | 0 |
| `seen_red_unknown` | 332 |

### Familles en désaccord — à relire, pas à corriger d'office

La famille DÉCLARÉE dans `guard_scope` diffère de celle que `error_class_families.classify()` DÉRIVE du symptôme. Le désaccord se lit dans les deux sens : soit le garde vise autre chose que ce qu'il croit, soit l'expression de la famille matche un mot pour une mauvaise raison. **Aligner l'un sur l'autre sans trancher ferait écrire une fausseté pour faire baisser un compteur.**

| classe | déclarée | dérivée |
|---|---|---|
| `a-population-that-counts-its-own-headers` | un-nombre-affirmé-qui-n-a-pas-été-mesuré | un-cumul-pris-pour-un-quotidien |
| `an-overload-makes-the-old-call-ambiguous` | deux-surfaces-deux-nombres | un-coût-payé-sans-contrepartie |
| `central-app-missing` | la-frontière-avec-le-dehors | le-locataire |
| `two-clocks-subtracted-from-each-other` | le-temps-et-l-horloge | deux-surfaces-deux-nombres |
| `unregistered-write-table` | un-travail-qui-n-arrive-nulle-part | une-erreur-avalée-devient-une-absence |
| `watchdog-becomes-the-noise` | le-message-parle-au-mauvais-lecteur | la-frontière-avec-le-dehors |

## Récidive observée

**56 évènements** sur 7628 classe-jours d'exposition — **0.2232** par classe-mois (IC 95 % : 0.1686 – 0.2898)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 48 | 0.1976 | 0.1457 – 0.2619 | **séparent** |
| by_guard · prose | 8 | 1.005 | 0.4327 – 1.9803 | **séparent** |
| by_seen_red · daté | 0 | 0.0 | 0.0 – 0.7853 | insuffisant pour conclure (n=56) |
| by_seen_red · jamais-ou-inconnu | 56 | 0.2274 | 0.1718 – 0.2953 | insuffisant pour conclure (n=56) |
| by_scope · ne-couvre-pas renseigné | 22 | 0.8166 | 0.5116 – 1.2364 | **séparent** |
| by_scope · non renseigné | 34 | 0.1518 | 0.1051 – 0.2121 | **séparent** |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

## Cohortes à horizon fixe

Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, jamais `0`.

| horizon | à risque | récidivées | taux |
|---|---|---|---|
| 7 j | 245 | 34 | 14 % |
| 14 j | 167 | 30 | 18 % |
| 30 j | 35 | 13 | 37 % |

## Avant la fenêtre git — DÉCLARATIF

5 classes introduites avant `2026-05-15`, 5 portant une date postérieure à leur `first_seen`.

⚠️ DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé. Le catalogue n'entre dans git qu'à cette date : tout ce qui précède a été écrit de mémoire, après coup. Comparer les deux serait `a-threshold-carried-across-instruments` appliqué à notre propre métrique.
