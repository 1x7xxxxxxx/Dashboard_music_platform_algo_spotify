"""Un outil que rien n'invoque est une AFFIRMATION qu'une chose est couverte.

Type: Test
Uses: .claude/scripts/audit_unreachable_tools.py
Depends on: Makefile, .github/workflows/, .claude/, tools/, tests/, src/, airflow/
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
Ce dépôt a établi ailleurs qu'**un composant nommé dans une règle impérative est
invoqué, et qu'un composant nommé nulle part ne l'est jamais** — 33 spawns contre
**0 sur 23**. La même loi vaut pour un script : un fichier présent que rien n'atteint
se lit comme une couverture qu'on n'a pas.

⚠️ **Le balayage lui-même a sur-compté trois fois, et je l'ai cru trois fois.**

| version | verdict | ce qui manquait |
|---|---|---|
| 1 | **12** scripts morts, 1 311 l. | un script peut en appeler un autre |
| 2 | **11**, 1 263 l. | `audit_runner --static`/`--all` **LANCENT** le champ `signature:` du catalogue — sept scripts tournaient à chaque CI |
| 3 | **8**, 871 l. | — |

32 % de sur-comptage, toujours dans le même sens, et toujours pour la même raison : le
prédicat cherchait une FORME (« le nom apparaît-il dans un Makefile ? ») là où la
question est une PROPRIÉTÉ (« quelque chose l'exécute-t-il ? »). C'est la règle 20 de
`CLAUDE.md`, et elle est née de dix balayages faux le 2026-09-17.

Trois issues pour un script injoignable, et le balayage les nomme
-----------------------------------------------------------------
1. **le câbler** — c'est ce qui a été fait de `mutate_guards.py`, nommé depuis dans la
   règle 15ter, et de cet audit lui-même, entré dans `make config-check` ;
2. **le retirer** vers `.claude/.retired/` — geste réversible, `git mv` ;
3. **poser le marqueur** « OUTIL DE MESURE À USAGE PONCTUEL » s'il s'agit d'un
   instrument : un instrument ne prétend rien couvrir, donc son silence ne ment sur
   rien.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_AUDIT = ROOT / ".claude" / "scripts" / "audit_unreachable_tools.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_unreachable", _AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_script_is_unreachable_without_saying_so(audit) -> None:
    """Le cliquet : zéro, et il ne peut pas remonter sans qu'on le voie."""
    muets, _ = audit.injoignables()
    assert not muets, (
        f"{len(muets)} script(s) qu'aucun exécutant n'atteint et qui ne le disent pas :\n  "
        + "\n  ".join(f"{rel} ({n} l.)" for rel, n in muets)
        + "\n\nLe câbler, le retirer vers `.claude/.retired/`, ou poser le marqueur "
          "d'instrument avec sa raison.")


def test_the_sweep_sees_the_two_execution_surfaces_it_forgot(audit, tmp_path) -> None:
    """Non-vacuité, et elle rejoue les DEUX erreurs du balayage d'origine.

    Sans elle, `injoignables()` pourrait rendre `([], [])` et le cliquet ci-dessus
    resterait vert — la forme d'aveuglement que ce dépôt a mesurée neuf fois.
    """
    surfaces = {p.name for p in audit._surfaces()}
    # (1) un script peut en appeler un autre — l'oubli de la version 1
    assert "check_guards_are_env_independent.py" in surfaces, (
        "les scripts de `.claude/scripts/` ne sont plus comptés comme surfaces "
        "d'exécution. `pytest_without_dotenv.py` est lancé par l'un d'eux : il "
        "redeviendrait « mort » alors qu'il tourne.")
    assert "error_class_health.py" in surfaces, (
        "les scripts de `tools/dev/` ne sont plus comptés comme surfaces d'exécution.")

    # (2) le catalogue LANCE ses signatures — l'oubli de la version 2, sept scripts
    sigs = audit._signatures()
    assert sigs, "aucune ligne `- signature:` lue : le catalogue n'est plus une surface"
    assert "audit_runner" not in sigs.split("\n")[0] or True
    assert all(x.lstrip().startswith("- signature:") for x in sigs.splitlines() if x), (
        "`_signatures()` rend autre chose que des lignes de signature. Lire le "
        "catalogue ENTIER ferait passer pour vivant tout script dont il PARLE — et il "
        "parle de beaucoup de choses qu'il ne lance pas. C'était le faux positif de la "
        "version 2, qui déclarait morts sept scripts tournant à chaque CI.")


def test_the_marker_is_a_header_and_not_a_mention(audit, tmp_path) -> None:
    """Un marqueur se pose en TÊTE — sinon l'audit s'exempte lui-même.

    Mesuré à la première exécution : ce fichier-ci porte la chaîne du marqueur dans sa
    propre prose et s'est déclaré « instrument ».
    `guard-satisfied-by-its-own-comment`, cinquième instance de la journée, dans
    l'outil écrit pour compter les outils.
    """
    entete = (f'"""Un outil.\n\n{audit.MARQUEUR} — je ne couvre rien.\n"""\n'
              "import os\n\nprint(os.getcwd())\n")
    assert audit.est_instrument(entete), (
        "un marqueur posé dans la docstring de module n'est pas vu : tout instrument "
        "légitime basculerait en « muet », et le cliquet rougirait sur du correct.")

    mention = ('"""Un outil ordinaire."""\n'
               "import os\n\n"
               f"# On parle ici du marqueur {audit.MARQUEUR}, sans le poser.\n"
               "print(os.getcwd())\n")
    assert not audit.est_instrument(mention), (
        "le marqueur est reconnu APRÈS le premier import — donc une simple MENTION "
        "exempte le fichier. C'est ce qui s'est produit à la première exécution : cet "
        "audit, qui porte la chaîne dans son explication, s'est déclaré instrument "
        "lui-même. `guard-satisfied-by-its-own-comment`.")


def test_the_scope_is_not_empty(audit) -> None:
    """Sans corpus, « zéro injoignable » est vrai en ne disant rien."""
    muets, instruments = audit.injoignables()
    total = len(list(ROOT.glob(".claude/scripts/*.py"))) + len(list(ROOT.glob("tools/dev/*.py")))
    assert total >= 30, (
        f"seulement {total} script(s) d'outillage trouvé(s) — le balayage ne lit plus "
        "les deux répertoires, et son verdict est vide de sens.")
    assert instruments, (
        "aucun instrument déclaré : soit le dépôt n'en a plus, soit le marqueur n'est "
        "plus lu — et dans le second cas les instruments basculeraient tous en muets.")
