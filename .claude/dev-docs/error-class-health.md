<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**397 classes.** Fenêtre observée : `2026-05-15` → `2026-09-17` (279 révisions du catalogue rejouées).

## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **397** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
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
| `automatic_guard` | 387 |
| `classes` | 397 |
| `ever_recurred_observed` | 53 |
| `prose_only` | 10 |
| `with_signature` | 386 |

## Les trous — ce que le cliquet fait baisser

Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.

| trou | classes |
|---|---|
| `cause_inferred` | 0 |
| `cause_unknown` | 181 |
| `guards_ref_missing` | 0 |
| `scope_family_invalid` | 0 |
| `scope_on_a_shared_guard_without_naming_its_tests` | 15 |
| `scope_unknown` | 0 |
| `scope_without_not_covered` | 0 |
| `seen_red_never` | 0 |
| `seen_red_unknown` | 330 |
| `siblings_never_swept` | 127 |

## Récidive observée

**66 évènements** sur 7997 classe-jours d'exposition — **0.2509** par classe-mois (IC 95 % : 0.194 – 0.3192)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 63 | 0.2445 | 0.1878 – 0.3128 | insuffisant pour conclure (n=66) |
| by_guard · prose | 3 | 0.5595 | 0.1125 – 1.6348 | insuffisant pour conclure (n=66) |
| by_seen_red · daté | 4 | 0.4026 | 0.1083 – 1.0309 | insuffisant pour conclure (n=66) |
| by_seen_red · jamais-ou-inconnu | 62 | 0.2449 | 0.1878 – 0.314 | insuffisant pour conclure (n=66) |
| by_scope · ne-couvre-pas renseigné | 66 | 0.2509 | 0.194 – 0.3192 | une seule strate peuplée (n=66) |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

⚠️ **La strate `by_scope` porte sur 397 classes de 397, soit 100 % du catalogue.** Les 0 autres n'ont pas de `ne couvre pas:` écrit, et **zéro récidive y est observée** — mais une récidive se compte en lignes d'HISTOIRE ajoutées. Une classe qu'on n'a jamais rouverte n'en gagne aucune, qu'elle soit saine ou seulement ignorée.

Autrement dit : ce taux ne peut pas distinguer « écrire la portée protège » de « on ne regarde que là ». Il ne se cite pas comme s'il décrivait les 397 classes.

## Cohortes à horizon fixe

Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, jamais `0`.

| horizon | à risque | récidivées | taux |
|---|---|---|---|
| 7 j | 269 | 39 | 14 % |
| 14 j | 175 | 34 | 19 % |
| 30 j | 35 | 15 | 43 % |

## Avant la fenêtre git — DÉCLARATIF

5 classes introduites avant `2026-05-15`, 5 portant une date postérieure à leur `first_seen`.

⚠️ DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé. Le catalogue n'entre dans git qu'à cette date : tout ce qui précède a été écrit de mémoire, après coup. Comparer les deux serait `a-threshold-carried-across-instruments` appliqué à notre propre métrique.
