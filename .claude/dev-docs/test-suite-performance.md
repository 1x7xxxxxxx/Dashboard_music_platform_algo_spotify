# Le coût de la suite — ce qui est mesuré, et ce qui ne l'est pas

> Écrit le 2026-09-15, après une séance d'optimisation où **trois de mes propres
> chiffres étaient faux**. Ce document existe pour que la prochaine séance reparte
> des mesures et pas des intuitions — les miennes ont coûté un plan entier.

## La référence, et la seule façon de la reprendre

```bash
# Machine AU REPOS. Vérifier d'abord qu'on est seul :
ps -eo cmd | python3 -c "import sys; print(sum(1 for l in sys.stdin if any(k in l for k in ('pytest','audit_runner','agent'))),'processus lourds')"

# Puis, jamais `python3` nu, jamais `> fichier` (RTK avale la sortie redirigée).
# ⚠️ Passer par `make test` — les drapeaux vivent dans le Makefile et la forme nue les
# perd. `make` écrit `.pytest-last.log` au fil de l'eau, donc la progression est lisible.
make test 2>&1 | tail -5
```

⚠️ **Le bloc ci-dessus a nommé `-n auto --dist loadfile` jusqu'au 2026-09-20**, alors que
le Makefile est passé à `-n $(PYTEST_WORKERS) --dist loadgroup` le 2026-09-17, après deux
morts par OOM en une heure. `PYTEST_WORKERS` est **calculé** —
`(MemAvailable_Mo − 5120) / 700`, borné à `[2, nproc]` — et sur cette WSL plafonnée à
10 Go il ne peut pas atteindre 8 ; il tombe à **2** dès que la pile Docker tourne.
Reprendre la « référence » avec l'ancienne ligne mesurait donc une configuration que rien
ne lance, et la comparer aux chiffres de ce document aurait comparé deux régimes
différents. C'est la raison pour laquelle on passe par `make` et jamais par la forme nue.

| Mesure | Valeur | Date |
|---|---|---|
| Suite complète, `-n auto` (8), `.venv` 3.11 | **~400–560 s** selon l'état de la machine | 2026-09-15 |
| Suite complète, `-n 4` | 455,8 s | 2026-09-15 |
| Collecte seule (`--collect-only`) | **30,1 s** pour 5 764 tests | 2026-09-15 |
| Un fichier statique, avant l'allègement | 17,44 s | 2026-09-15 |
| Un fichier statique, après | **10,62 s** | 2026-09-15 |
| Un test trivial dans `tests/`, après | **9,24 s** | 2026-09-15 |
| `audit_runner --static` | 199,4 s | 2026-09-15 |
| `audit_runner --deterministic` | **expire à 1800 s** | 2026-09-15 |
| Suite complète, `make test` (`-n 2`, pile Docker up) | **236,75 s** pour 8 647 verts / 54 skippés | 2026-09-20 |

⚠️ **Les lignes datées du 2026-09-15 décrivent `/mnt/c` et `--dist loadfile`** — deux
choses qui ont changé depuis (R117 a déplacé le dépôt sur ext4 ; le 2026-09-17 a changé
les drapeaux). Elles restent ici parce qu'un chiffre daté est une citation, pas une
affirmation d'aujourd'hui ; elles ne se comparent pas à la ligne du 2026-09-20.
La suite a aussi **grossi de 25 %** entre les deux (5 764 tests collectés le 2026-09-15,
8 701 le 2026-09-20) : le mur ne se compare pas non plus à population différente.

La suite varie de ±40 % d'une exécution à l'autre sur cette machine. **Un écart de
moins de 40 % n'est pas un résultat.** Ne jamais conclure sur une seule paire.

## Les trois chiffres que j'ai eus faux, et pourquoi

1. **« 415 s »** — mesuré en série et avec `/usr/bin/python3`, qui n'a ni
   `googleapiclient` ni `spotipy`. Ce n'est le chemin de personne : la CI et le
   Makefile lancent `-n auto --dist loadfile` sur `.venv`.
2. **« La collecte coûte 387 s, plus de 90 % d'attente disque »** — mesuré pendant
   que **trois sous-agents et un audit** parcouraient `/mnt/c`. Machine au repos :
   **30,1 s**. Facteur 12,8 d'erreur, et trois conclusions bâties dessus.
3. **« `/mnt/c` est 3 568× plus lent qu'ext4 »** — même cause. Une fois seul, le
   rapport redevient ordinaire. Le profil `user 0m37s / real 387 s` ressemble
   exactement à un disque lent ; il ne distingue pas « lent » de « occupé par moi ».

## Où va le temps, mesuré

| Poste | Coût | Portée |
|---|---|---|
| `import streamlit` (via `src.dashboard.utils`) | **5,30 s** | par processus pytest — donc **par worker** |
| `import src.database.postgres_handler` | 0,19 s | la porte légère, sans Streamlit |
| `import pandas` | 3,70 s | par processus |
| Coût fixe ajouté par worker xdist | **+2,7 s** | ×8 sous `-n auto` |
| 286 tests rendant une page `AppTest` | les 10 plus lents font 48 s à 23 s chacun | 25 fichiers |
| 82 fichiers refaisant leur propre `rglob` + `ast.parse` | ~18 600 parses, mais `src/` entier ne coûte que **1,11 s** | modeste |

**Le parallélisme rend peu ici** : `-n 8` fait ~400 s, `-n 4` fait 456 s, la série
~415 s. Sur 12 fichiers purement statiques, `-n 8` est même **25 % plus LENT** que la
série (72,0 s contre 57,7 s) — le coût fixe par worker dépasse le gain.

## Les trois cibles, et quand les lancer

| Cible | Ce qu'elle lance | Mesuré |
|---|---|---|
| `make test-fast` | tout **sauf** les 4 tests de documents | **375,0 s** |
| `make test-docs` | seulement ces 4 fichiers | **45,7 s** |
| `make test` | **tout** — la barrière avant de livrer | **441,5 s** |

`make test-fast` est la boucle de code ; `make test-docs` se lance après avoir
touché aux documents ; `make test` et la CI lancent toujours tout. Les tests de la
**roadmap** ne sont jamais sautés — voir plus bas.

La liste vit en clair dans le `Makefile` (`DOC_TESTS`) parce que `--ignore` doit
l'avoir **avant** la collecte : `-m "not docs"` collecte d'abord et désélectionne
ensuite. Le prix de ce choix est une information à deux endroits, et
`tests/test_the_doc_marker_matches_what_make_skips.py` interdit qu'ils divergent —
dans les deux sens, plus l'entrée de la roadmap dans la liste.

## Ce qui a été fait le 2026-09-15

| Geste | Fichier | Effet mesuré |
|---|---|---|
| Les tests passent par la porte DB **légère** (`PostgresHandler.from_env_or_config`) au lieu de `get_db_connection` | `tests/db_gate.py`, `tests/conftest.py` | **−38 %** sur une exécution ciblée (17,44 → 10,62 s) |
| `audit_runner --deterministic` retiré de la CI au profit de `--static` | `.github/workflows/ci.yml` | une étape qui rejouait **219 des 362 fichiers en série** et expirait à 1800 s |
| `PYTHON` du Makefile résolu dynamiquement | `Makefile` | `make test` ne lançait **aucun test** (`PluginValidationError`, rc=3) |
| Frontière du registre posée par le **loader** au lieu d'un import inconditionnel | `tests/conftest.py` | neutre en temps, frontière plus étroite et gardée |
| `db_ready()` mis en cache (`lru_cache`) | `tests/db_gate.py` | 22 sondes Postgres à la collecte → **1**. Sans base, c'était 22 × 1,5 s de délai |
| `make test-fast` / `make test-docs` | `Makefile`, 4 fichiers marqués `docs` | **−66 s** sur la boucle locale (441,5 → 375,0 s) |
| Complétude du catalogue vérifiée dans la suite, par classe | `tests/test_every_error_class_is_complete.py` | **665 tests en 3,1 s**, sans lancer un seul pytest fils |

## Ce qui n'a PAS été fait, et pourquoi

- **Rendre `src/dashboard/utils/__init__.py` paresseux sur Streamlit.** C'est le
  dernier gros poste (5,30 s), mais la ligne 19 porte un `@st.cache_data` qui exige
  Streamlit à l'import. Toucher au cache du dashboard est une surface à haut risque :
  `code-critic` d'abord, ADR ensuite.
- **Un marqueur `-m "not docs"`.** Écarté au profit de `--ignore` : un marqueur
  collecte d'abord et désélectionne ensuite. Le marqueur `docs` existe quand même,
  comme déclaration lisible dans chaque fichier, mais ce n'est pas lui qui fait
  gagner le temps.
- **Mutualiser le parcours d'arbre** (`tests/tree.py`). Le gisement existe — 82
  fichiers, ~18 600 `ast.parse` — mais parser tout `src/` coûte **1,11 s**. L'ordre de
  grandeur total est de 30 à 60 s, pas le poste dominant. À faire pour la lisibilité,
  pas pour la vitesse.
- **Un test générique par classe d'erreur.** Chaque classe garde une question
  *différente* ; le seul générique utile vérifie la FORME du catalogue, et il existe
  déjà : `tests/test_every_named_guard_exists.py` (252 chemins + 32 node-ids, par AST,
  sans lancer pytest).

## Mesuré en CI, et ce que le local ne peut pas dire

Runs réels de `ci.yml` (médiane **428 s** sur 8 runs verts, étendue 366–496 s) :

| Étape | Avant (34900702613) | Après (35001871244) |
|---|---|---|
| Gardes de classes d'erreur | 145 s (`--deterministic`) | **96 s** (`--static`) |
| `Run tests` | 183 s | **261 s** |
| **Total** | 393 s | **423 s** |

**La CI n'est pas devenue plus rapide, et il faut savoir pourquoi.** L'étape retirée
servait aussi de **préchauffage** : elle lisait 219 des 362 fichiers juste avant que
`Run tests` ne les relise. Le gain de 49 s sur la porte est mangé par 78 s sur la
suite. Avec une variance de ±40 % et un seul run de chaque côté, la lecture honnête
est « pas de changement mesurable en CI » — le bénéfice de ce changement est
ailleurs : la porte ne peut plus expirer, et le rapport par classe reste la nuit.

### Les pistes mesurées et NON exploitées, avec leur taille

À reprendre dans cet ordre ; chaque ligne porte la commande qui l'a établie.

| Piste | Mesure | Pourquoi pas encore |
|---|---|---|
| **48 fichiers** de tests passent par la porte DB lourde (`from src.dashboard.utils import get_db_connection`, **5,30 s**) ; **5** par la porte légère `db_gate` (`lru_cache`, **0,19 s**) | balayage AST sur `tests/` | le correctif est prouvé sur 3 sites (−38 % en ciblé) mais 48 sites demandent un passage dédié, pas une fin de séance |
| **40 rendus sont des doublons STRICTS** entre `test_views_render_smoke.py` et `test_a_render_opens_one_connection.py` — même `_SCRIPT` à la ligne près, seule la mesure diffère | 192 rendus au total pour 44 vues | fusionner les deux fichiers change ce que chacun prouve : l'un lit `at.exception`, l'autre compte les connexions |
| Le cache `setup-uv` a un hit-rate de **0 %** | `Failed to restore: 400` sur tous les runs vérifiés ; **zéro** entrée `setup-uv` dans l'API des caches | gain plafond **~5 s** (le lock s'installe en 5–11 s à froid) |
| **Deux signatures `--static` sont vides en CI** : `an-overload-makes-the-old-call-ambiguous` vise le port **5433** quand la CI écoute sur **5432** ; `a-merged-branch-outlives-its-pull-request` fait `gh api … \|\| echo true` sans jeton | lecture des signatures | elles passent **toujours** — des gardes qui ne gardent rien, à retriager ou à retirer |
| **24 % des runs CI** sont déclenchés par des `.md` seuls | 6 SHA doc-only sur les 25 analysables des 40 derniers runs | un filtre `paths:` naïf tuerait les tests `docs`, qui lisent vraiment ces `.md` |
| `.audit-venv/` (**3 258 entrées**, Python 3.12) et `.archive/` traînent dans l'arbre | ignorés par git, donc invisibles en CI | mais parcourus par tout `rglob` non scopé — c'est un piège de MESURE locale, pas un coût de CI |

### ⛔ Ne pas retirer `--cov` de la CI — c'est la deuxième fois

Mesuré en local le 2026-09-15 : **+92 %** (61,8 → 118,7 s sur un échantillon mixte).
Conclusion tentante, et fausse. `ci.yml` porte déjà la mesure faite **sur le
runner** : *« 160,6 s sans, 174,0 s avec — +8 %, soit 13 s »*, et la note dit
explicitement que la suppression avait déjà été envisagée sur une supposition à
~30 %.

Les chiffres `/mnt/c` ne valent qu'en **rapport**, jamais en absolu, et ici même le
rapport est faux : l'instrumentation de couverture écrit et lit beaucoup, ce que ce
montage amplifie. Pour 13 s sur le runner, on garde le seul rapport de couverture du
dépôt.

## La cadence — non, la suite complète n'est pas obligatoire après chaque feature

| Moment | Ce qui tourne | Coût |
|---|---|---|
| pendant le code | `make test-changed` (règle transverse #16) | secondes à dizaines de secondes |
| avant de pousser | `make test-fast` | **375 s** |
| après avoir touché aux documents | `make test-docs` | **45,7 s** |
| sur la PR | la CI complète | **~390–423 s** |
| une fois par semaine | `make audit`, `audit_runner --deterministic`, la revue des lents | le ménage |

**Ce qui ne doit PAS bouger : la barrière de la PR.** Ce dépôt a déjà payé pour
l'apprendre deux fois — `tests/test_a_red_gate_does_not_hide_the_suite.py` documente
**27 exécutions consécutives** (2026-09-04 → 06) où la suite n'a pas tourné du tout
derrière un signal rouge sans rapport, et le 2026-09-15 la sonde de production a
passé **neuf jours** à ne rien exécuter. Dans les deux cas, le coût n'a pas été le
temps : il a été l'ignorance. C'est le temps d'ATTENTE qu'on attaque, jamais la
couverture du gate.

## Le framework : pytest reste le bon choix

Aucun remplaçant n'améliorerait ce dépôt — `unittest` et `nose2` perdent `parametrize`
et les fixtures, dont 146 fichiers dépendent (213 sites de décorateur). Ce qui manque
est un **greffon**, pas un framework :

| Greffon | Ce qu'il résout | État |
|---|---|---|
| `pytest-split` | découpe la suite en N shards de durée égale (matrice CI) | **présent** depuis le 2026-09-16 (R109) — 4 shards, **6 depuis le 2026-09-25**, `.test_durations` versionné |
| `pytest-xdist` | parallélisme par processus | **présent**, `--dist loadgroup` depuis le 2026-09-16 (R110) |
| `pytest-randomly` | trouve les dépendances accidentelles entre tests | **présent** depuis le 2026-09-16, **désactivé par défaut** (`-p no:randomly`) et lancé chaque nuit |
| `pytest-testmon` | ne rejoue que les tests touchés, via la couverture | **absent**, et redondant avec `select_tests.py` |

Écarté : `pytest-run-parallel` (threads) partagerait les imports — séduisant vu les
5,30 s de Streamlit — mais `AppTest` et psycopg2 ne sont pas sûrs en threads.

## Le matériel

i7-11370H (4 cœurs / 8 threads), 8 Go alloués à WSL, dépôt sur `/mnt/c`.
**Le GPU ne sert à rien** : pytest est lié aux entrées-sorties et à du CPU
mono-thread, aucun chemin GPU n'existe. Une exclusion Windows Defender a été posée sur
le dossier le 2026-09-15 ; **son effet n'a pas pu être isolé**, le dossier non exclu
allant aussi vite dans le même banc.


---

# La séance du 2026-09-16 — ce qu'elle a mesuré, et ce qu'elle a démenti

> Écrite comme la précédente : les chiffres d'abord, et surtout **ce qui s'est révélé
> faux**. Deux énoncés de la roadmap ont été démentis par la mesure.

## Les chiffres, avant et après

| Mesure | Avant | Après |
|---|---|---|
| **CI, mur du run** (médiane) | **427 s** sur 18 runs verts (279–504) | **109 s** (run 35035830958) |
| CI, forme | 1 job, 15 étapes en file | `gates` + 4 shards (6 depuis le 2026-09-25), en parallèle, sans `needs:` |
| Suite locale, `-n auto --dist loadfile` | **340,2 s** | — |
| Suite locale, `-n auto --dist loadgroup` | — | **349,6 s** puis 352,0 s |
| Suite locale, série, ordre aléatoire | — | 751,9 s (référence froide) |
| `import src.dashboard.utils` (la porte de la base) | **5,30 s** | **0,21 s** |
| `import src.database.postgres_handler` (référence) | 0,19 s | 0,19 s |
| Un test trivial dans `tests/` | 9,24 s | 7,7 / 8,4 / 8,9 s |
| Collecte de la suite entière | 30,1 s (5 764 tests) | 27,3 s (6 477 tests) |
| Durées par test (`--store-durations`) | — | 6 469 tests, **907 s en série** |

## Le démenti qui compte : `loadgroup` ne gagne RIEN sur la suite complète

R110 était justifiée par « `pytest tests/test_views_render_smoke.py -q` → **152,5 s**
pour un seul fichier, tenu par un seul worker sous `loadfile` ». Le fichier coûte bien
cela (172,6 s dans `.test_durations`), mais **ce n'est pas le chemin critique à
8 workers** : les autres workers l'absorbent.

Mesuré en ALTERNANCE — et l'alternance est le point, mesurer deux configurations
d'affilée sur une machine dont la charge dérive ne prouve rien :

| distribution | mesures (s) | médiane |
|---|---|---|
| `--dist loadfile` | 339,1 / 341,3 | **340,2** |
| `--dist loadgroup` | 337,5 / 359,4 / 344,1 / 355,2 | **349,6** |

2,8 % en faveur de `loadfile`. Sous le seuil de ±40 %. **Aucun résultat.**

Ce que `loadgroup` a acheté est ailleurs, et le vaut : **quatre courses latentes**
qu'aucune exécution sous `loadfile` ne pouvait montrer, plus la condition pour que le
sharding rende (à 4 shards, un fichier de 172 s DEVIENT dominant dans le sien).

## Où va vraiment le temps — mesuré par test, plus par intuition

| Fichier | Coût | Part des 907 s |
|---|---|---|
| `test_views_render_smoke.py` | 172,6 s | 19 % |
| `test_a_render_opens_one_connection.py` | 82,6 s | 9 % |
| `test_stray_session_reads_nothing.py` | 72,8 s | 8 % |
| **les trois premiers** | **328 s** | **36 %** |

Aucun test isolé ne dépasse **31,5 s**, ce qui est la condition pour que quatre shards
s'équilibrent. Ils l'ont fait : 64 / 92 / 100 / 106 s en CI.

## Le seam, et pourquoi son gain n'est PAS celui qu'on croit

La porte de la base est passée de 5,30 s à 0,21 s — elle rejoint la référence brute.
Mais **le mur de la suite complète n'a pas bougé** : les 27 fichiers de rendu importent
`src.dashboard.views.*`, donc Streamlit entre dans le processus de toute façon à la
collecte. Le gain est sur la boucle LOCALE (un fichier seul, `make test-changed`) et
sur l'image de l'API. Ne pas l'annoncer plus grand qu'il n'est.

## Ce qui reste, et qui n'a pas été fait

- **Réduire le NOMBRE de rendus.** Les deux fichiers de rendu font 94 rendus pour 41
  vues, avec des listes qui ont divergé (41 contre 40) et un `_SCRIPT` dupliqué à
  l'octet près. Fusionner les mesures en rendant UNE fois économiserait ~40 rendus.
  **Écarté sciemment** : `test_a_render_opens_one_connection.py` est nommé comme garde
  par une signature de `error-classes.md`, et déplacer sa propriété ailleurs affaiblit
  ce que la signature détecte. Ce dépôt attaque le temps d'ATTENTE, jamais la
  couverture de la porte — et le sharding parallélise ces rendus au lieu de les couper.
- **Les deux signatures `--static` vides en CI** (port 5433 contre 5432 ; `gh api … ||
  echo true` sans jeton). Toujours ouvertes. La première demande que l'étape des gardes
  vive dans un job qui a Postgres — ce que la nouvelle forme rend possible, mais qui
  n'a pas été fait cette nuit.
- **Le cliquet des allers-retours coûte maintenant 21,9 s** (son nouveau garde ouvre un
  sous-processus). C'est cher pour un fichier, et c'est assumé : il garde une classe
  qui a mordu trois fois.

---

# Le 2026-09-16 au matin — le goulot a changé de nature

Une fois la suite shardée, **la mise en route domine les tests**. Décomposition d'un
shard, mesurée :

| Poste | Coût |
|---|---|
| `Initialize containers` | 14 s |
| `Install uv` — **v4** | **20 s** |
| `Install uv` — **v10.1.0** | **1 s** |
| `Install dependencies from lockfile` | 6 s |
| `Provision Postgres` | 12 s |
| **`Run tests`** | **37–47 s** |

## `setup-uv` : v4 → v10.1.0, et les trois choses qu'il a fallu apprendre

1. **Le retard était invisible.** `.github/dependabot.yml` ignore les MAJEURES pour
   `github-actions` — bonne règle, une majeure change le runner sous la CI. Mais une
   action qui ne publie QUE des majeures ne produit alors aucune PR : le silence est
   indiscernable d'« à jour ». Six majeures de retard, et la v4 parlait à l'API de
   cache retirée par GitHub (`Failed to restore: 400`, 0 % de succès).
   Le rapporteur `tools/dev/check_action_drift.py` tourne désormais chaque nuit.
2. **`@v10` n'existe pas.** `astral-sh/setup-uv` publie `v10.1.0` et PAS de tag majeur
   flottant, alors que `@v4` en avait un. Les cinq jobs ont échoué en **9 secondes**
   sur `Unable to resolve action`, avant la mise en route. Le rapporteur vérifie
   maintenant que chaque `uses:` RÉSOUT, et n'imprime que des tags écrivables.
3. **La majeure a déplacé un défaut.** `cache-dependency-glob` passe de `**/uv.lock`
   (v4) à `**/*requirements*.txt` (v10). Or `uv sync --frozen` n'installe que ce que
   dit `uv.lock` : le cache se serait invalidé quand rien ne change, et pas quand tout
   change — vert dans les deux cas, faux dans les deux cas. Le glob est explicite sur
   les trois sites.

## Une observation à SURVEILLER, pas à corriger

Un run sur `main` (35071279926) a passé **133 s** dans `Set up Python 3.11`
(`uv python install 3.11`), pour un mur de 218 s. Le run frère en v10 (35071014744) a
fait la même étape en **moins de 3 s**, pour un mur de 162 s.

Un point ne conclut pas, et 40× d'écart sur une étape est exactement ce que le seuil de
±40 % interdit d'interpréter. Cause probable : `uv python install` télécharge un CPython
quand le cache d'outils du runner ne l'a pas — variable, pas systématique.

**Ce qui déclencherait une action** : `Set up Python 3.11` au-dessus de 30 s sur trois
runs. Le remède serait alors de replier l'installation de Python dans `setup-uv`
lui-même (`python-version:`), pour qu'elle passe par le même cache. À mesurer avant,
pas à supposer.

## Deux optimisations ÉCARTÉES par leur propre mesure — 2026-09-18

Les deux venaient d'un plan approuvé. Les deux sont mortes en étant chiffrées, et c'est
la mesure qui vaut d'être gardée, pas le renoncement.

### Scinder le catalogue en deux fichiers — gain ≈ 0 s

Le plan proposait `error-classes.md` (196 classes vivantes) + `error-classes-archive.md`
(206 dormantes), pour passer de 8 400 à ~4 500 lignes.

| ce qu'on croyait acheter | ce que ça achète réellement |
|---|---|
| « la suite lit un fichier deux fois plus court » | **≈ 0 s.** Les 13 s que le catalogue coûte à la suite sont dominées par les **8,46 s** du cliquet de santé, qui viennent du rejeu de l'historique **git** — scinder le fichier d'aujourd'hui ne change rien aux révisions d'hier |
| — | le rayon de souffle : **47 sites lecteurs** (33 en Python, 14 ailleurs), chacun devant décider « le fichier actif seul, ou les deux ? » |

Retenu à la place : **une section `## 💤 Classes DORMANTES` dans le même fichier**. Même
bénéfice de lecture, un seul fichier, aucun lecteur à modifier — les trois parseurs
ignorent déjà tout titre hors kebab-case.

### Fusionner les cinq gardes du catalogue — gain ≈ 0,1 s

Le plan proposait de regrouper `test_every_error_class_is_complete`,
`test_error_class_index_is_complete`, `test_a_guard_names_a_class_that_exists`,
`test_the_error_class_families_only_improve` et
`test_the_error_class_health_only_improves` — « 10,8 s cumulées et trois dicts gelés ».

Mesuré :

* **lire et découper le catalogue coûte 23 ms** (12,4 ms de lecture, 10,3 ms de
  découpage, 1,8 Mo, 409 blocs). Cinq gardes = **114 ms**, pas 10,8 s ;
* les 10,8 s sont **8,46 s de cliquet de santé** (git, pas le fichier) plus des cas
  PARAMÉTRÉS — `test_a_guard_names_a_class_that_exists` rend 101 cas à ~0,04 s chacun,
  et fusionner les fichiers ne réduit pas le nombre de cas ;
* le coût : **16 champs `guard:`/`signature:` du catalogue** pointent ces cinq fichiers.

Gain ≈ 0,1 s contre 16 références à réécrire. Écarté.

**La leçon des deux, et elle est la même** : le temps d'une suite ne se lit pas dans la
taille de ce qu'elle ouvre. Il se lit dans `.test_durations`, test par test — et les
deux fois, le poste dominant n'était pas celui que le plan nommait.

## Le rendu payé une fois — 2026-09-18, et ce que le gain N'EST PAS

`tests/test_views_render_smoke.py` et `tests/test_a_render_opens_one_connection.py`
importaient le même `SCRIPT` et la même liste `VIEWS` de `tests/render_harness.py`, et
rendaient les **mêmes 39 vues chacun de son côté** — mesuré à **88,6 s, 21,3 %** de la
suite, dont `airflow_kpi` seule à 9,96 + 12,91 s.

Les deux propriétés se lisent sur le même `AppTest` : `at.exception` d'un côté, le
compte de `PostgresHandler._connect` de l'autre. `render_harness.render_once()` rend la
vue, retient **deux scalaires** `(erreur, connexions)` — jamais l'objet `AppTest`, dont
la rétention avait fait sortir la suite par l'OOM le 2026-09-17 — et sert les deux.

**Mesuré en ALTERNANCE, deux tours, sur ces deux fichiers seuls à `-n 4`** :

| | tour 1 | tour 2 | médiane |
|---|---|---|---|
| avant | 30,70 s | 30,56 s | **30,6 s** |
| après | 17,83 s | 18,37 s | **18,1 s** |

**−41 %.** Dispersion intra-bras ~3 %, séparation 41 % : au-dessus du seuil de bruit de
±40 %, et c'est le premier gain de ce document qui le franchisse sur un poste de rendu.
93 tests des deux côtés — rien n'a été perdu en route.

⚠️ **Ce gain n'est PAS un gain de 41 % sur la suite complète, et le confondre serait
refaire l'erreur que ce document reproche à R110.** `make test` rend **190,5 s** après,
contre 193,5 s de référence : **1,5 %, sous le bruit, donc aucun résultat.** La raison
est exactement celle du démenti `loadgroup` ci-dessus — à `PYTEST_WORKERS` workers, ces
deux fichiers ne sont pas le chemin critique, les autres workers absorbaient déjà leur
temps. Ce qui est acheté est **44 s de travail CPU** qui cessent d'être payées, donc de
la marge sur un runner plus étroit et sur les shards de CI, pas de l'horloge locale.

⚠️ **Et le montage a un mode d'échec silencieux**, qui est la vraie raison d'être du
garde : un `lru_cache` vit dans UN processus. Si les deux tests d'une vue partent dans
deux workers, le cache ne sert rien, le rendu est repayé, **et les deux propriétés
restent vraies**. Trois choses doivent tenir ensemble — `--dist loadgroup` dans le
`Makefile`, `@pytest.mark.xdist_group(<vue>)` sur chaque cas, et le même nom de groupe
des deux côtés — et aucune n'est impliquée par ce que les tests affirment.
`tests/test_a_shared_render_stays_in_one_worker.py` les vérifie toutes les trois en
important les modules et en lisant les marques **réellement collectées**, et se prouve
lui-même en fabriquant à chaque exécution un montage nu, un montage gardé et un montage
à groupe constant. Classe :
`a-cache-whose-sharing-depends-on-an-unasserted-scheduler-flag`.

## Le chemin critique n'était pas la suite — 2026-09-25

**Question posée : « 4 shards, c'est peut-être pas assez ? »** Mesuré avant de toucher au
nombre : sur trois runs verts (`13dd188`, `2c918fe`, `f3593e8`), le mur était **202 · 213 ·
193 s**, et le job le plus long n'était PAS un shard (95–135 s) mais `gates`
(189–208 s). Ajouter des shards seul n'aurait rien acheté.

| poste du job `gates` | avant | après |
|---|---|---|
| `check_guards_are_env_independent.py` (104 fichiers rejoués sans `.env`) | **100 s en série** | sous xdist, `-n 4` (poste : 117 → 58 s) |
| `gold_coverage.py --check` | 20 s × **2** (ligne explicite + signature `--static`) | × 1 — garde `tests/test_a_gate_runs_each_check_once.py` |
| les 48 signatures de `--static` | en file | concurrentes, 4 à la fois (poste : ~130 → 60 s) |

Puis **4 → 6 shards**, parce qu'alors la suite redevenait le chemin critique. Un shard paie
~60 s fixes (conteneur Postgres 13–23 s, uv 14–18 s, provision 13–22 s) pour ~180 s de
travail total : 4 ≈ 130 s, 6 ≈ 105 s, 8 ≈ 98 s. Six est le coude.

Mur mesuré sur `e8b20d4` (6 shards + les deux premiers gestes), trois exécutions :
**125 · 154 · 139 s** contre **193–213 s**. Le parallélisme de `--static` est arrivé après
ces trois mesures ; il n'est pas compté dedans.

### Le poste : `make test-changed` rendait la suite entière

`select_tests.py` rendait « SUITE ENTIÈRE » dès qu'un fichier non-`.py` bougeait. Ce dépôt
touche un `.md`, un `.yml` ou `.test_durations` dans presque chaque séance : trois fois
sur trois le 2026-09-25, soit **9 656 tests et ~280 s** à chaque boucle. Désormais seul
l'environnement (lock, `requirements*`, `.env*`, `*.sql`, `config/`) force tout ; le reste
sélectionne par mention, par dossier et par module voisin. Même diff : **66 s**.

### Les workers locaux : mesurés, pas changés

Pic réel en `VmHWM` sur la suite ENTIÈRE à `-n 3` : **573 · 414 · 411 Mo**, 1 753 Mo en
tout. Un diviseur de 600 au lieu de 700 rendrait toujours **2** workers ici
(`(6 667 − 5 120) / 600 = 2,6`) : le frein est la réserve de 5 120 Mo, qui protège de
l'OOM vécu deux fois le 2026-09-17. Elle ne se desserre pas sans une mesure de ce que
`n8n-ollama` et `knowledge-rag` tiennent au pic.

### Mise à jour du même jour — les workers ont bougé, avec leur mesure

La réserve de 5 120 Mo couvrait deux croissances possibles en pleine suite : Ollama (n8n)
et le préchargement du modèle knowledge-rag. Le propriétaire a décidé que n8n ne tourne
que le dimanche, et le modèle knowledge-rag se décharge désormais après 10 min
(1 439 → 97 Mo mesurés). `tools/dev/pytest_workers.py` réserve donc selon ce qui tourne ;
un verrou `~/.cache/heavy-memory.lock` fait sauter aux crons d'ingestion leur passe
pendant une suite. Porte de sécurité, trois suites complètes alternées :

| workers | durée | creux de `MemAvailable` |
|---|---|---|
| 4 | 179 s | 4 454 Mo |
| 2 | 269 s | 5 228 Mo |
| 4 | 180 s | 4 278 Mo |

**−33 %** sur `make test`, avec plus de 4 Go de marge au pire moment.

**Écarté le même jour, par sa propre porte** : resserrer la règle « dossier » de
`select_tests.py`. Un `.md` de `.claude/dev-docs/` sélectionne 159 fichiers de test sur
533, dont 30 seulement par la règle du dossier — sous le seuil de 50 % fixé avant de
commencer, et resserrer aurait risqué un faux négatif (`code-critic`).
