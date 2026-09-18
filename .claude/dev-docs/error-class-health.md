<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**400 classes.** Fenêtre observée : `2026-05-15` → `2026-09-18` (291 révisions du catalogue rejouées).

## Ce que le balayage RAPPORTE

Le compteur `siblings_never_swept` mesure l'EFFORT. Celui-ci mesure le résultat, et c'est lui qui décide s'il faut continuer.

| grandeur | valeur |
|---|---|
| balayages faits | **296** |
| dont le verdict est LISIBLE | **195** |
| qui ont trouvé au moins un site | **24** |
| sites vivants trouvés | **58** |
| taux de trouvaille (sur verdicts lisibles) | **0.123** |

⚠️ **97 des 296 « balayages » n'en sont PAS** : ils disent que le garde a été relancé et qu'il était vert. Un garde vert prouve que SON prédicat ne trouve rien, jamais qu'il n'y a rien — mesuré trois fois la nuit du 17 au 18, dont un garde vert sur **8 sites vivants**. Le nombre de classes dont personne n'a cherché les frères est donc **201**, et non 104.

⚠️ **101 balayages sont MUETS** : la question a été posée, la réponse s'est perdue en prose. Ils ne comptent ni comme trouvaille ni comme zéro — un balayage dont on ignore le résultat n'est pas un balayage sans résultat. Le dénominateur du taux ci-dessus les exclut délibérément : les inclure diviserait par une population qui ne répond pas à la question, ce que ce dépôt appelle `anchor-a-number-to-its-population`.

## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **400** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
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
| `automatic_guard` | 390 |
| `classes` | 400 |
| `ever_recurred_observed` | 53 |
| `prose_only` | 10 |
| `with_signature` | 389 |

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
| `seen_red_unknown` | 309 |
| `siblings_never_swept` | 104 |
| `sites_unknown` | 101 |
| `swept_by_rerunning_the_guard` | 97 |

## Récidive observée

**66 évènements** sur 8394 classe-jours d'exposition — **0.239** par classe-mois (IC 95 % : 0.1849 – 0.3041)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 63 | 0.233 | 0.179 – 0.2981 | insuffisant pour conclure (n=66) |
| by_guard · prose | 3 | 0.5272 | 0.106 – 1.5403 | insuffisant pour conclure (n=66) |
| by_seen_red · daté | 15 | 0.4497 | 0.2515 – 0.7418 | insuffisant pour conclure (n=66) |
| by_seen_red · jamais-ou-inconnu | 51 | 0.2101 | 0.1564 – 0.2762 | insuffisant pour conclure (n=66) |
| by_scope · ne-couvre-pas renseigné | 66 | 0.239 | 0.1849 – 0.3041 | une seule strate peuplée (n=66) |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

⚠️ **La strate `by_scope` porte sur 400 classes de 400, soit 100 % du catalogue.** Les 0 autres n'ont pas de `ne couvre pas:` écrit, et **zéro récidive y est observée** — mais une récidive se compte en lignes d'HISTOIRE ajoutées. Une classe qu'on n'a jamais rouverte n'en gagne aucune, qu'elle soit saine ou seulement ignorée.

Autrement dit : ce taux ne peut pas distinguer « écrire la portée protège » de « on ne regarde que là ». Il ne se cite pas comme s'il décrivait les 400 classes.

## Cohortes à horizon fixe

Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, jamais `0`.

| horizon | à risque | récidivées | taux |
|---|---|---|---|
| 7 j | 279 | 43 | 15 % |
| 14 j | 185 | 34 | 18 % |
| 30 j | 35 | 15 | 43 % |

## Avant la fenêtre git — DÉCLARATIF

5 classes introduites avant `2026-05-15`, 5 portant une date postérieure à leur `first_seen`.

⚠️ DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé. Le catalogue n'entre dans git qu'à cette date : tout ce qui précède a été écrit de mémoire, après coup. Comparer les deux serait `a-threshold-carried-across-instruments` appliqué à notre propre métrique.
