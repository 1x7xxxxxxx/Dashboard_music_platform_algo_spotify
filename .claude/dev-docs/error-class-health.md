<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**394 classes.** Fenêtre observée : `2026-05-15` → `2026-09-17` (236 révisions du catalogue rejouées).

## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **394** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
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
| `automatic_guard` | 384 |
| `classes` | 394 |
| `ever_recurred_observed` | 49 |
| `prose_only` | 10 |
| `with_signature` | 383 |

## Les trous — ce que le cliquet fait baisser

Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.

| trou | classes |
|---|---|
| `cause_inferred` | 0 |
| `cause_unknown` | 241 |
| `guards_ref_missing` | 0 |
| `scope_family_invalid` | 0 |
| `scope_on_a_shared_guard_without_naming_its_tests` | 11 |
| `scope_unknown` | 0 |
| `scope_without_not_covered` | 195 |
| `seen_red_never` | 0 |
| `seen_red_unknown` | 331 |
| `siblings_never_swept` | 386 |

## Récidive observée

**60 évènements** sur 7997 classe-jours d'exposition — **0.2281** par classe-mois (IC 95 % : 0.174 – 0.2936)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 57 | 0.2212 | 0.1675 – 0.2866 | insuffisant pour conclure (n=60) |
| by_guard · prose | 3 | 0.5595 | 0.1125 – 1.6348 | insuffisant pour conclure (n=60) |
| by_seen_red · daté | 3 | 0.4701 | 0.0945 – 1.3735 | insuffisant pour conclure (n=60) |
| by_seen_red · jamais-ou-inconnu | 57 | 0.2221 | 0.1682 – 0.2877 | insuffisant pour conclure (n=60) |
| by_scope · ne-couvre-pas renseigné | 60 | 0.4336 | 0.3308 – 0.5581 | **séparent** |
| by_scope · non renseigné | 0 | 0.0 | 0.0 – 0.0294 | **séparent** |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

⚠️ **La strate `by_scope` porte sur 199 classes de 394, soit 51 % du catalogue.** Les 195 autres n'ont pas de `ne couvre pas:` écrit, et **zéro récidive y est observée** — mais une récidive se compte en lignes d'HISTOIRE ajoutées. Une classe qu'on n'a jamais rouverte n'en gagne aucune, qu'elle soit saine ou seulement ignorée.

Autrement dit : ce taux ne peut pas distinguer « écrire la portée protège » de « on ne regarde que là ». Il ne se cite pas comme s'il décrivait les 394 classes.

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
