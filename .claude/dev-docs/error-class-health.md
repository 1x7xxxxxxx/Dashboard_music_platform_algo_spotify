<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**418 classes.** Fenêtre observée : `2026-05-15` → `2026-09-26` (488 révisions du catalogue rejouées).

## Ce que le balayage RAPPORTE

Le compteur `siblings_never_swept` mesure l'EFFORT. Celui-ci mesure le résultat, et c'est lui qui décide s'il faut continuer.

| grandeur | valeur |
|---|---|
| balayages faits | **418** |
| dont le verdict est LISIBLE | **418** |
| qui ont trouvé au moins un site | **120** |
| sites vivants trouvés | **499** |
| taux de trouvaille (sur verdicts lisibles) | **0.287** |

✅ **Aucun des 418 balayages n'est une relance de garde.** Ils étaient **97** le 2026-09-17, et les 97 ont rendu des sites vivants qu'un garde vert ne pouvait pas voir. La porte `audit_runner.py --sweep-verdict` refuse désormais cette forme **au moment de l'écrire**. Reste 0 classe(s) jamais balayée(s) — un trou déclaré, pas un faux balayage.

⚠️ **0 balayage(s) sont MUETS** : la question a été posée, la réponse s'est perdue en prose. Ils ne comptent ni comme trouvaille ni comme zéro — un balayage dont on ignore le résultat n'est pas un balayage sans résultat. Le dénominateur du taux ci-dessus les exclut délibérément : les inclure diviserait par une population qui ne répond pas à la question, ce que ce dépôt appelle `anchor-a-number-to-its-population`.

🔗 **Ces deux nombres NE S'ADDITIONNENT PAS.** Une relance de garde ne porte jamais de compte en gras, donc elle est muette par construction : l'intersection vaut **0**, et les muets qui ne sont pas une relance sont **0**. Au 2026-09-17 les deux paragraphes ci-dessus annonçaient 97 et 100 sans le dire — un lecteur y lisait 197 classes en défaut, là où il y en avait 100.


## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **418** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
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
| `automatic_guard` | 409 |
| `classes` | 418 |
| `ever_recurred_observed` | 48 |
| `prose_only` | 9 |
| `with_signature` | 407 |

## Les trous — ce que le cliquet fait baisser

Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.

| trou | classes |
|---|---|
| `cause_inferred` | 0 |
| `cause_unknown` | 13 |
| `guard_does_not_prove_itself` | 141 |
| `guards_ref_missing` | 0 |
| `scope_family_invalid` | 0 |
| `scope_on_a_shared_guard_without_naming_its_tests` | 15 |
| `scope_unknown` | 0 |
| `scope_without_not_covered` | 0 |
| `seen_red_never` | 0 |
| `seen_red_unknown` | 58 |
| `siblings_never_swept` | 0 |
| `sites_unknown` | 0 |
| `sites_unknown_hors_relance` | 0 |
| `swept_by_rerunning_the_guard` | 0 |

## Récidive observée

**61 évènements** sur 11661 classe-jours d'exposition — **0.159** par classe-mois (IC 95 % : 0.1216 – 0.2043)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 56 | 0.1488 | 0.1124 – 0.1932 | **séparent** |
| by_guard · prose | 5 | 0.7005 | 0.2257 – 1.6346 | **séparent** |
| by_guard_since · avec-garde | 56 | 0.1574 | 0.1189 – 0.2044 | insuffisant pour conclure (n=61) |
| by_guard_since · sans-garde | 5 | 0.1803 | 0.0581 – 0.4208 | insuffisant pour conclure (n=61) |
| by_seen_red · daté | 6 | 0.093 | 0.0339 – 0.2024 | insuffisant pour conclure (n=61) |
| by_seen_red · jamais-ou-inconnu | 55 | 0.1724 | 0.1299 – 0.2244 | insuffisant pour conclure (n=61) |
| by_scope · ne-couvre-pas renseigné | 61 | 0.159 | 0.1216 – 0.2043 | une seule strate peuplée (n=61) |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

#### Ce que le biais valait, en clair

| | avec garde | sans garde | rapport |
|---|---|---|---|
| `by_guard` — étiquette d'aujourd'hui, **confondu** | 0.1488 | 0.7005 | ×4.7 |
| `by_guard_since` — découpé au premier garde | 0.1574 | 0.1803 | ×1.1 |

L'écart de la première ligne est un **artefact de mesure**, pas un effet. Écrire un garde automatique reste la bonne pratique ; ce tableau dit seulement que **ce jeu de données ne la démontre pas**, et qu'aucune règle ne devrait citer la première ligne comme preuve.

⚠️ **La strate `by_scope` porte sur 418 classes de 418, soit 100 % du catalogue.** Les 0 autres n'ont pas de `ne couvre pas:` écrit, et **zéro récidive y est observée** — mais une récidive se compte en lignes d'HISTOIRE ajoutées. Une classe qu'on n'a jamais rouverte n'en gagne aucune, qu'elle soit saine ou seulement ignorée.

Autrement dit : ce taux ne peut pas distinguer « écrire la portée protège » de « on ne regarde que là ». Il ne se cite pas comme s'il décrivait les 418 classes.

## Cohortes à horizon fixe

Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, jamais `0`.

| horizon | à risque | récidivées | taux |
|---|---|---|---|
| 7 j | 404 | 44 | 11 % |
| 14 j | 315 | 37 | 12 % |
| 30 j | 141 | 28 | 20 % |

## Avant la fenêtre git — DÉCLARATIF

5 classes introduites avant `2026-05-15`, 5 portant une date postérieure à leur `first_seen`.

⚠️ DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé. Le catalogue n'entre dans git qu'à cette date : tout ce qui précède a été écrit de mémoire, après coup. Comparer les deux serait `a-threshold-carried-across-instruments` appliqué à notre propre métrique.
