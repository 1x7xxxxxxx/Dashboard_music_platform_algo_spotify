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

## Le matériel

i7-11370H (4 cœurs / 8 threads), 8 Go alloués à WSL, dépôt sur `/mnt/c`.
**Le GPU ne sert à rien** : pytest est lié aux entrées-sorties et à du CPU
mono-thread, aucun chemin GPU n'existe. Une exclusion Windows Defender a été posée sur
le dossier le 2026-09-15 ; **son effet n'a pas pu être isolé**, le dossier non exclu
allant aussi vite dans le même banc.
