---
description: "Transforme un défaut corrigé en classe d'erreur durable, avec une signature shell qui la détecte."
rex: []
---

# /capitalise

Un défaut corrigé une fois revient. Une classe écrite avec une signature qui la
détecte ne revient pas sans qu'on le sache.

## Ce que je fais

J'écris une entrée au schéma du catalogue, et je **valide sa signature par
exécution** avant de la livrer :

| Champ | Ce que j'y mets |
|---|---|
| `status` | `open` → `reported` → `guarded` → `resolved` |
| `kind` | `deterministic` si la signature n'a pas de faux positif, sinon `heuristic` |
| `signature` | une commande shell, **sortie ≠ 0 quand la classe est touchée** |
| `seen_red` | **la date où je l'ai vue sortir ≠ 0**, et sur quoi. `never` si je ne l'ai pas fait, `n-a` s'il n'y a pas de signature. **Jamais une date non observée** |
| `root_cause` | une ligne, `fichier:ligne` quand ça se lit dans le code |
| `cause_evidence` | `read` (j'ai lu le code) · `measured` (j'ai exécuté) · `inferred` (**plausible, non vérifié — et je le dis**) · `retracted` |
| `long_term_fix` | le changement qui rend la classe *impossible*, ou `— (le garde EST le fix)` |
| `guard` | le test ou le hook qui bloque, ou `—` |
| `guard_scope` | `<famille> — <le geste> ; couvre: … ; **ne couvre pas: …**` |
| `siblings` | `swept:<date> — <fichier:ligne, …>` · `swept:<date> — aucun autre site` · `not-swept`. **Le défaut existe-t-il DÉJÀ ailleurs ?** |
| `history` | daté, ce qui s'est passé — et **la ligne déclare sa nature** : `- AAAA-MM-JJ (récidive):` quand le défaut est réapparu sur un site neuf, `- AAAA-MM-JJ (garde):` quand c'est le GARDE qui a été pris en défaut (signature dérivée, prédicat aveugle, faux positif), **sans marque** pour une note de travail (garde ajouté, statut changé, verdict de balayage) |

**Et j'ajoute la ligne dans la table `## Index` en tête du catalogue** — l'entrée
seule ne suffit pas. C'est ce tableau qu'on lit en premier ; une classe absente de
l'index est une classe qu'on écrira une deuxième fois sous un autre nom. Mesuré le
2026-08-21 : 63 entrées, 51 lignes d'index, et les douze manquantes étaient les
douze plus récentes. Contrôle : `python3 -m pytest tests/test_error_class_index_is_complete.py -q`
(classe `catalogue-index-omits-its-own-entries`).

## La marque d'une ligne d'`History` — pourquoi elle n'est pas décorative

**Seule une ligne `(récidive)` compte dans le taux de récidive**, et ce taux est le
chiffre sur lequel repose l'argument « une classe sans garde automatique récidive N×
plus », cité dans `CLAUDE.md`.

Mesuré le 2026-09-18 : le compteur comptait **toute** ligne d'`History` ajoutée. Les 81
lignes concernées ont été classées une par une — **33** récidives, **26** défauts du
garde, **22** notes de travail. Le taux était donc surestimé d'un facteur **2,5**, et le
mode d'échec est le pire possible pour une mesure : *écrire le verdict d'un balayage qui
PROUVE qu'une classe est saine faisait monter sa récidive*. Deux balayages à zéro site
vivant, le même jour, ont porté `ever_recurred_observed` de 54 à 56.

Distinguer `(récidive)` de `(garde)` n'est pas une nuance de vocabulaire : **les deux
appellent des remèdes opposés.** Une récidive demande de chercher d'autres sites ; un
garde pris en défaut demande d'élargir le garde. Les confondre perd les deux signaux.

Contrôle : `tests/test_a_recurrence_is_not_a_note.py`, muté rouge trois fois.

## La seule étape non négociable

**Je lance la signature deux fois avant de l'écrire :**

- sur un arbre où le défaut est **présent** (`git stash`, une copie, ou en le
  remettant à la main) — elle doit sortir **≠ 0** ;
- sur l'arbre corrigé — elle doit sortir **0**.

Une signature qui n'a jamais été vue rouge n'a pas été testée : elle garde
peut-être, ou elle ne peut simplement pas échouer, et rien dans son texte ne
permet de trancher. Si je ne peux pas produire les deux exécutions, je livre la
classe en `kind: manual` **sans** signature plutôt qu'avec une signature non
vérifiée — une fausse garantie coûte plus cher qu'une absence de garantie.

**Et elle lit du code, pas du texte.** Une signature `deterministic` restreint sa
recherche aux fichiers de code (`--include`) et ne doit pas pouvoir matcher un
commentaire — sinon **écrire sur le défaut le fait rougir**, y compris le
commentaire qui explique le correctif. Vu le 2026-08-03 : une classe passait au
rouge sur les commentaires de son propre fix, donc la seule façon de garder la CI
verte était d'arrêter de documenter. Une deterministic bloque la CI par contrat ;
une qui bloque sur un commentaire apprend que le rouge peut être du bruit, et la
leçon est appliquée aux autres. Contrôle : `audit_runner.py --prose`.

## La troisième étape non négociable — je cherche le défaut AILLEURS

**Avant d'écrire l'entrée**, je pose la question que la règle transverse 14 impose déjà :
ce défaut existe-t-il **déjà** ailleurs dans l'arbre ? Pour un défaut à cause nommable,
c'est `Spawn sibling-sweeper` ; pour un cas évident, c'est un balayage que je fais et que
je consigne. Le résultat va dans `siblings:`.

⚠️ **Ce n'est pas la même question que `guard_scope`**, et les confondre est le piège.
`ne couvre pas` parle du FUTUR — ce que le garde laissera passer. `siblings:` parle du
PRÉSENT — où le même défaut se trouve aujourd'hui. Une classe peut avoir une portée
impeccable et trois sites frères vivants.

Mesuré le 2026-09-17 : **69 classes sur 395 (17 %)** portaient une trace de balayage ;
326 n'en portaient aucune. Et le jour où la question a été posée pour de bon, sur
`a-replica-that-builds-its-own-image`, le balayage a trouvé **deux sites** que le
correctif laissait vivants — dont le fichier copié tel quel en production. **Le garde
écrit avant ce balayage était vert sur les deux.**

`swept:<date> — aucun autre site` est un RÉSULTAT et s'écrit. `not-swept` est compté
comme un TROU, jamais comme un zéro. « Je n'ai rien trouvé » et « je n'ai pas cherché » se ressemblent dans un
catalogue et pas du tout dans un dépôt.

## La seconde étape non négociable — je nomme le GESTE, pas le verbe

**Avant de choisir le garde**, je nomme la famille de geste qui partage la cause, et **au
moins un geste voisin que le garde n'atteint PAS.**

Mesuré, et c'est pour ça que cette étape existe :
`a-kill-pattern-that-matches-its-own-shell` a été écrite le 2026-09-12 **avec son hook**.
Elle s'est reproduite **trois fois** le 2026-09-16. Le hook gardait le verbe `pkill` ; la
cause était un motif qui se contient lui-même, et `pgrep` la partageait — même cause,
conséquence différente (le shell ne meurt pas, la boucle ne sort jamais), donc invisible.
**La portée du garde était le défaut, pas la connaissance.**

Si je ne peux nommer aucun geste voisin, j'écris `ne couvre pas: (non explorée)`. C'est
**compté comme un trou** par `make error-health` — ce qui est le bon résultat : j'ai
gardé le défaut, pas la classe, et le document le dit au lieu de me laisser croire le
contraire.

⚠️ Le garde couvre-t-il le geste tel qu'un humain le FAIT, ou tel qu'une API le nomme ?
`pkill` et `pgrep` sont deux verbes d'un même geste : « chercher un processus par un
motif ». Un garde écrit sur le verbe laisse la classe vivante sous l'autre nom.

## Je lis le CODE du garde, pas son nom

Mesuré le 2026-09-16, et le chiffre est brutal : sur six `guard_scope` que j'avais écrites
avec soin, **quatre étaient inexactes**. Une seule cause, la même quatre fois — j'avais lu
le garde NOMMÉ dans le champ `guard:`, sans ouvrir les autres fichiers cités par
`signature:` et `History:`.

Ce que ça a produit :

* `artist-id-or-1` — j'affirmais couvrir « les vues et les DAG ». **Aucun des deux gardes
  ne parcourt `airflow/dags/`** : tous deux fixent `views/`. Une affirmation de couverture
  fausse est pire qu'un trou déclaré, parce qu'elle fait cesser de chercher.
* `central-app-missing` — j'écrivais « les cinq applications » ; le tuple en définit
  **quatre**.
* `an-overload-…` — j'écrivais « ne couvre pas les autres plateformes » ; la signature SQL
  bloquante filtre `proname LIKE 'gold_%'`, donc elle couvre **tout le parc**.
* `db-connection-per-show` — j'annonçais un trou sur `@st.fragment` qui **n'en est pas
  un** : une classe sœur le garde déjà. Sous-déclarer envoie écrire un garde redondant.

La règle qui en sort, et elle coûte deux minutes : **ouvrir l'implémentation de CHAQUE
fichier cité par la classe**, et chercher dans le catalogue toute AUTRE entrée qui
référence le même fichier de test. Un `couvre:` se vérifie en lisant, jamais en se
souvenant.

⚠️ **Un déclencheur mécanique a été cherché et REJETÉ.** L'hypothèse — « les classes
citant ≥ 2 fichiers distincts sont celles qui se trompent » — a été testée sur ces six :
les quatre fausses citent 1, 1, 2 et 3 fichiers, les deux justes 1 et 3. **Aucune
séparation.** Faute de sélecteur, la relecture adversariale est demandée sur les lots de
revue de R122, pas sur chaque classe — six spawns par jour pour un artefact de cinq
minutes ne se justifient pas.

## Ce que je ne fais pas

- Je ne recopie pas un narratif dans un champ structuré : la prose contient des
  causes **rétractées trois lignes plus bas**, et la structure les blanchirait en
  faits. Je lis, je tranche, et je dis quand je ne suis pas sûr.
- **Je n'écris pas une cause plausible dans la voix d'un fait.** Quand rien n'a été lu ni
  exécuté, la bonne sortie est `cause_evidence: inferred` — pas une phrase affirmative.
  Le 2026-09-16 j'ai livré une cause plausible (« `grep -c` compte sa propre ligne
  malgré le crochet »), testée ensuite, **fausse**, et il a fallu la rétracter
  publiquement. Étiquetée `inferred`, elle n'aurait rien coûté.
- Je ne fais pas baisser un compteur en **supprimant** une classe. Les planchers de
  population de `tests/test_the_error_class_health_only_improves.py` refusent ce
  raccourci, et c'est délibéré : un taux s'améliore aussi bien en corrigeant qu'en
  effaçant.
- Je ne touche ni à la ROADMAP, ni au code.
