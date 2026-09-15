# Le coût de la suite — ce qui est mesuré, et ce qui ne l'est pas

> Écrit le 2026-09-15, après une séance d'optimisation où **trois de mes propres
> chiffres étaient faux**. Ce document existe pour que la prochaine séance reparte
> des mesures et pas des intuitions — les miennes ont coûté un plan entier.

## La référence, et la seule façon de la reprendre

```bash
# Machine AU REPOS. Vérifier d'abord qu'on est seul :
ps -eo cmd | python3 -c "import sys; print(sum(1 for l in sys.stdin if any(k in l for k in ('pytest','audit_runner','agent'))),'processus lourds')"

# Puis, jamais `python3` nu, jamais `> fichier` (RTK avale la sortie redirigée) :
rtk proxy .venv/bin/python -m pytest tests/ -n auto --dist loadfile -q 2>&1 | tail -5
```

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
| `pytest-split` | découpe la suite en N shards de durée égale (matrice CI) | **absent** — c'est R109 |
| `pytest-xdist` | parallélisme par processus | **présent**, sous-exploité : `loadfile` groupe tous les fichiers alors que **9 seulement** en ont besoin — c'est R110 |
| `pytest-testmon` | ne rejoue que les tests touchés, via la couverture | **absent**, et redondant avec `select_tests.py` |

Écarté : `pytest-run-parallel` (threads) partagerait les imports — séduisant vu les
5,30 s de Streamlit — mais `AppTest` et psycopg2 ne sont pas sûrs en threads.

## Le matériel

i7-11370H (4 cœurs / 8 threads), 8 Go alloués à WSL, dépôt sur `/mnt/c`.
**Le GPU ne sert à rien** : pytest est lié aux entrées-sorties et à du CPU
mono-thread, aucun chemin GPU n'existe. Une exclusion Windows Defender a été posée sur
le dossier le 2026-09-15 ; **son effet n'a pas pu être isolé**, le dossier non exclu
allant aussi vite dans le même banc.
