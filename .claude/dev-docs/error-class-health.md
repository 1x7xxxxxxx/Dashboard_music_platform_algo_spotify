<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est
     perdue à la prochaine exécution de `make error-health`. -->

# La santé du catalogue de classes d'erreur

**410 classes.** Fenêtre observée : `2026-05-15` → `2026-09-22` (356 révisions du catalogue rejouées).

## Ce que le balayage RAPPORTE

Le compteur `siblings_never_swept` mesure l'EFFORT. Celui-ci mesure le résultat, et c'est lui qui décide s'il faut continuer.

| grandeur | valeur |
|---|---|
| balayages faits | **409** |
| dont le verdict est LISIBLE | **407** |
| qui ont trouvé au moins un site | **111** |
| sites vivants trouvés | **469** |
| taux de trouvaille (sur verdicts lisibles) | **0.273** |

✅ **Aucun des 409 balayages n'est une relance de garde.** Ils étaient **97** le 2026-09-17, et les 97 ont rendu des sites vivants qu'un garde vert ne pouvait pas voir. La porte `audit_runner.py --sweep-verdict` refuse désormais cette forme **au moment de l'écrire**. Reste 1 classe(s) jamais balayée(s) — un trou déclaré, pas un faux balayage.

⚠️ **2 balayage(s) sont MUETS** : la question a été posée, la réponse s'est perdue en prose. Ils ne comptent ni comme trouvaille ni comme zéro — un balayage dont on ignore le résultat n'est pas un balayage sans résultat. Le dénominateur du taux ci-dessus les exclut délibérément : les inclure diviserait par une population qui ne répond pas à la question, ce que ce dépôt appelle `anchor-a-number-to-its-population`.

🔗 **Ces deux nombres NE S'ADDITIONNENT PAS.** Une relance de garde ne porte jamais de compte en gras, donc elle est muette par construction : l'intersection vaut **0**, et les muets qui ne sont pas une relance sont **2**. Au 2026-09-17 les deux paragraphes ci-dessus annonçaient 97 et 100 sans le dire — un lecteur y lisait 197 classes en défaut, là où il y en avait 100.


## Ce que ce document corrige

Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :

| avancé | mesuré |
|---|---|
| 367 classes | **410** — les 4 en trop étaient `Contract`, `Index`, `Per-class schema`, `CLASS-ID` |
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
| `automatic_guard` | 400 |
| `classes` | 410 |
| `ever_recurred_observed` | 39 |
| `prose_only` | 10 |
| `with_signature` | 398 |

## Les trous — ce que le cliquet fait baisser

Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.

| trou | classes |
|---|---|
| `cause_inferred` | 0 |
| `cause_unknown` | 140 |
| `guard_does_not_prove_itself` | 306 |
| `guards_ref_missing` | 0 |
| `scope_family_invalid` | 0 |
| `scope_on_a_shared_guard_without_naming_its_tests` | 15 |
| `scope_unknown` | 0 |
| `scope_without_not_covered` | 0 |
| `seen_red_never` | 0 |
| `seen_red_unknown` | 141 |
| `siblings_never_swept` | 1 |
| `sites_unknown` | 2 |
| `sites_unknown_hors_relance` | 2 |
| `swept_by_rerunning_the_guard` | 0 |

## Récidive observée

**47 évènements** sur 10013 classe-jours d'exposition — **0.1427** par classe-mois (IC 95 % : 0.1048 – 0.1898)

### Par strate

| strate | évènements | par classe-mois | IC 95 % | verdict |
|---|---|---|---|---|
| by_guard · automatique | 43 | 0.1334 | 0.0965 – 0.1797 | insuffisant pour conclure (n=47) |
| by_guard · prose | 4 | 0.5709 | 0.1536 – 1.4616 | insuffisant pour conclure (n=47) |
| by_guard_since · avec-garde | 43 | 0.1417 | 0.1026 – 0.1909 | insuffisant pour conclure (n=47) |
| by_guard_since · sans-garde | 4 | 0.1537 | 0.0414 – 0.3936 | insuffisant pour conclure (n=47) |
| by_seen_red · daté | 18 | 0.1682 | 0.0996 – 0.2659 | insuffisant pour conclure (n=47) |
| by_seen_red · jamais-ou-inconnu | 29 | 0.1304 | 0.0873 – 0.1873 | insuffisant pour conclure (n=47) |
| by_scope · ne-couvre-pas renseigné | 47 | 0.1427 | 0.1048 – 0.1898 | une seule strate peuplée (n=47) |

⚠️ **Quand deux intervalles se recouvrent, il n'y a PAS de résultat**, quel que soit l'écart des points. Le verdict ci-dessus le dit strate par strate plutôt que de laisser le lecteur comparer deux nombres et conclure.

#### Ce que le biais valait, en clair

| | avec garde | sans garde | rapport |
|---|---|---|---|
| `by_guard` — étiquette d'aujourd'hui, **confondu** | 0.1334 | 0.5709 | ×4.3 |
| `by_guard_since` — découpé au premier garde | 0.1417 | 0.1537 | ×1.1 |

L'écart de la première ligne est un **artefact de mesure**, pas un effet. Écrire un garde automatique reste la bonne pratique ; ce tableau dit seulement que **ce jeu de données ne la démontre pas**, et qu'aucune règle ne devrait citer la première ligne comme preuve.

⚠️ **La strate `by_scope` porte sur 410 classes de 410, soit 100 % du catalogue.** Les 0 autres n'ont pas de `ne couvre pas:` écrit, et **zéro récidive y est observée** — mais une récidive se compte en lignes d'HISTOIRE ajoutées. Une classe qu'on n'a jamais rouverte n'en gagne aucune, qu'elle soit saine ou seulement ignorée.

Autrement dit : ce taux ne peut pas distinguer « écrire la portée protège » de « on ne regarde que là ». Il ne se cite pas comme s'il décrivait les 410 classes.

## Cohortes à horizon fixe

Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, jamais `0`.

| horizon | à risque | récidivées | taux |
|---|---|---|---|
| 7 j | 332 | 35 | 11 % |
| 14 j | 245 | 30 | 12 % |
| 30 j | 117 | 25 | 21 % |

## Avant la fenêtre git — DÉCLARATIF

5 classes introduites avant `2026-05-15`, 5 portant une date postérieure à leur `first_seen`.

⚠️ DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé. Le catalogue n'entre dans git qu'à cette date : tout ce qui précède a été écrit de mémoire, après coup. Comparer les deux serait `a-threshold-carried-across-instruments` appliqué à notre propre métrique.
