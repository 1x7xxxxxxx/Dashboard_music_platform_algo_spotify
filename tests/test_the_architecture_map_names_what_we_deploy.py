"""La carte doit NOMMER ce que le dépôt construit et déploie.

Type: Test
Uses: .claude/dev-docs/architecture.md, Dockerfile*, src/
Depends on: rien à l'exécution
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
`src/api/` — **13 modules**, brique 14 livrée, `uvicorn src.api.main:app` dans
`Dockerfile.api`, cible Prometheus `streamlytics_api:8502` — n'apparaissait dans
**aucune** des trois sections structurelles d'`architecture.md`. Sa seule mention dans
tout le fichier était une note en prose sur Stripe. Un lecteur qui consulte la carte au
lieu de lister le dépôt — c'est sa fonction — ignorait qu'un service HTTP entier existe.

**Aucun garde du dépôt ne pouvait le voir**, et la raison est structurelle :

| garde | ce qu'il lit | pourquoi il est aveugle |
|---|---|---|
| `test_the_views_map_lists_every_view.py` | la seule section `## Dashboard Views Map` | délibérément scopé (son docstring le dit) ; ne regarde jamais Macro, Micro ni la Classification Map |
| `test_no_surface_reads_a_table_nobody_writes.py` | les noms de TABLES cités | un module, un service, un nœud ou une arête ne sont pas des noms de tables |
| `check_config_refs.py` (`make config-check`) | les chemins `.claude/...` explicites | il répond « ce nom pointe-t-il vers quelque chose ? » |

Les trois répondent à **« ce que la carte NOMME existe-t-il ? »**. Aucun ne répond à
l'inverse — **« ce qui existe est-il NOMMÉ ? »** — et c'est la seconde moitié qui manquait.
Ce fichier est cette moitié.

Ce qu'il ne fait PAS, délibérément
----------------------------------
Il n'exige pas que chaque module soit cartographié : ce serait du bruit, et la carte
globe déjà (`src/collectors/*.py`). Il exige deux choses qu'une machine tranche :

1. **tout paquet de premier niveau sous `src/`** est nommé quelque part ;
2. **tout module servant de point d'entrée à une image Docker** est nommé — parce qu'on
   ne construit pas une image pour quelque chose qui ne mérite pas d'être sur la carte.

Un composant absent de la carte ET absent de ce test est un composant que personne ne
sait aller voir, et que rien ne signale.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / ".claude" / "dev-docs" / "architecture.md"

# Répertoires techniques, jamais des composants.
_PAS_UN_PAQUET = {"__pycache__"}


def _texte() -> str:
    return ARCH.read_text(encoding="utf-8")


def _porte_un_init(dossier: Path) -> bool:
    """Ce répertoire est-il un paquet ?

    On demande « existe-t-il un module nommé `__init__` ici ? », pas « le fichier
    `__init__.py` existe-t-il ». La différence n'est pas cosmétique : la première est
    la PROPRIÉTÉ, la seconde une forme d'écriture — et `.pyi` ou un paquet natif y
    échapperaient. Accessoirement, ce fichier n'inspecte alors plus aucun chemin
    Python, ce qui est exact : il lit du Markdown et des Dockerfile.
    """
    return any(f.is_file() and f.stem == "__init__" for f in dossier.iterdir())


def _paquets_src() -> set[str]:
    return {
        p.name for p in (ROOT / "src").iterdir()
        if p.is_dir() and _porte_un_init(p) and p.name not in _PAS_UN_PAQUET
    }


def _entrypoints() -> dict[str, str]:
    """{chemin du Dockerfile: module d'entrée} — lu dans les `CMD`, pas deviné."""
    out = {}
    for df in sorted(ROOT.glob("Dockerfile*")):
        texte = df.read_text(encoding="utf-8")
        for m in re.finditer(r"(?:uvicorn|python3? -m|gunicorn)\s+([\w.]+)", texte):
            mod = m.group(1).split(":")[0]
            if mod.startswith("src."):
                out[df.name] = mod
    return out


def _est_nomme(aiguille: str) -> bool:
    """La carte nomme-t-elle `aiguille` ? On accepte toutes les écritures usuelles."""
    t = _texte()
    formes = (aiguille, aiguille.replace(".", "/"), f"src/{aiguille}", f"{aiguille}/")
    return any(f in t for f in formes)


def test_the_map_exists():
    assert ARCH.exists(), f"{ARCH} a disparu — ce garde ne vérifierait rien"


@pytest.mark.parametrize("paquet", sorted(_paquets_src()))
def test_every_top_level_package_is_named_on_the_map(paquet):
    assert _est_nomme(paquet), (
        f"`src/{paquet}/` existe sur le disque et la carte d'architecture ne le nomme "
        "nulle part. Un lecteur consulte cette carte AU LIEU de lister le dépôt — c'est "
        "sa fonction — donc un paquet absent est un paquet que personne ne sait aller "
        "voir. Mesuré le 2026-09-18 : `src/api/` (13 modules, livré, en production, "
        "scrapé par Prometheus) manquait aux trois sections structurelles, et aucun "
        "garde ne pouvait le dire."
    )


@pytest.mark.parametrize("df,module", sorted(_entrypoints().items()))
def test_every_built_image_names_its_entrypoint_on_the_map(df, module):
    """On ne construit pas une image pour quelque chose qui n'est pas sur la carte."""
    paquet = ".".join(module.split(".")[:2])          # src.api.main → src.api
    assert _est_nomme(paquet) or _est_nomme(module), (
        f"`{df}` construit une image dont le point d'entrée est `{module}`, et la carte "
        f"ne nomme ni `{module}` ni `{paquet}`. Une image qu'on construit et qu'on "
        "déploie est, par définition, un composant du système."
    )


def test_the_entrypoint_reader_actually_finds_them():
    """Non-vacuité : si le lecteur de `CMD` rend un dict vide, tout passe sur rien."""
    trouves = _entrypoints()
    assert trouves, (
        "aucun point d'entrée `src.*` trouvé dans les Dockerfile — soit ils ont changé "
        "de forme, soit le lecteur est cassé. Dans les deux cas le test ci-dessus ne "
        "garde plus rien.")
    assert "src.dashboard.serve" in trouves.values(), (
        "`src.dashboard.serve` n'est plus le point d'entrée du conteneur principal — "
        "CLAUDE.md le déclare comme tel, relire lequel des deux a bougé.")


def test_the_naming_predicate_can_say_no():
    """La preuve que ce fichier se donne : `_est_nomme` doit pouvoir répondre NON.

    Un prédicat qui répond toujours oui est vert sur l'arbre sain et aveugle le jour
    où il compte. On lui donne un nom qui ne peut pas être sur la carte.
    """
    assert not _est_nomme("un_paquet_qui_nexiste_pas_zzz"), (
        "`_est_nomme` rend vrai pour un nom absent — il ne garde rien")
    assert _est_nomme("api"), (
        "`_est_nomme` rend faux pour `api`, qui vient d'être ajouté à la carte — "
        "le prédicat est trop strict et rendrait l'arbre rouge en permanence")
