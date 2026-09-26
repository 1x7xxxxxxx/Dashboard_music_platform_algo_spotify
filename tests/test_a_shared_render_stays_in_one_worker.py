"""Le rendu partagé ne vaut que si les deux gardes tombent dans le même worker.

Type: Test
Uses: pytest collection, tests/render_harness.py
Depends on: tests/test_views_render_smoke.py, tests/test_a_render_opens_one_connection.py
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
Les 39 vues étaient rendues DEUX fois par exécution, une fois par fichier de garde :
88,6 s, 21,3 % de la suite. `render_harness.render_once()` les rend une fois et sert
les deux propriétés depuis un `lru_cache`. Mesuré en alternance, deux tours à `-n 4` :
30,7 · 30,6 s avant, 17,8 · 18,4 s après — **−41 %**.

Ce que ce fichier garde est le mode d'échec SILENCIEUX de ce montage, et c'est le
seul qui compte : un `lru_cache` vit dans UN processus. Si les deux tests d'une même
vue partent dans deux workers, le cache ne sert rien et le rendu est repayé — sans
qu'un seul test rougisse, parce que les deux propriétés restent vraies. Le gain
s'évapore, la suite reste verte, et rien ne le dit.

Trois choses doivent tenir ensemble, et ce fichier les vérifie toutes les trois :
le `--dist loadgroup` du Makefile, la marque `xdist_group` sur CHAQUE cas des deux
fichiers, et le fait que la marque porte le nom de la VUE (deux vues différentes
dans le même groupe sérialiseraient sans rien partager).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[1]

# Des MODULES, pas des chemins : ce fichier ne lit aucune source Python, il importe
# les deux gardes et interroge les marques que pytest a réellement collectées. Une
# marque se lit dans l'objet `pytest.param`, jamais dans le texte qui l'écrit —
# `ast` lui-même ne dirait pas si la marque a survécu à la collecte.
_MODULES = (
    "tests.test_views_render_smoke",
    "tests.test_a_render_opens_one_connection",
)


def _cas_groupes(module) -> dict[str, set[str]]:
    """Les groupes xdist déclarés, par identifiant de vue, lus à la COLLECTE."""
    groupes: dict[str, set[str]] = {}
    for param in module._VUES:
        vue = param.values[0]
        noms = {m.args[0] for m in param.marks if m.name == "xdist_group"}
        groupes[vue] = noms
    return groupes


@pytest.mark.parametrize("nom", _MODULES)
def test_chaque_cas_de_rendu_declare_son_groupe(nom):
    """Une vue sans groupe repart dans un worker au hasard : rendu repayé, suite verte."""
    import importlib

    groupes = _cas_groupes(importlib.import_module(nom))
    assert groupes, f"{nom} ne paramètre plus par `_VUES`"
    sans = sorted(v for v, noms in groupes.items() if not noms)
    assert not sans, (
        f"{nom} : ces vues n'ont pas de `xdist_group`, donc leur rendu sera repayé "
        f"dans un autre worker sans qu'aucun test ne rougisse : {sans}"
    )
    mal_nommes = sorted(v for v, noms in groupes.items() if noms != {v})
    assert not mal_nommes, (
        f"{nom} : le groupe doit porter le nom de la VUE — deux vues dans un même "
        f"groupe sérialisent sans rien partager : {mal_nommes}"
    )


def test_les_deux_fichiers_groupent_les_memes_vues():
    """Le partage suppose que les deux cas d'une vue portent le MÊME nom de groupe."""
    import importlib

    vus = [_cas_groupes(importlib.import_module(n)) for n in _MODULES]
    a, b = ({v: tuple(sorted(n)) for v, n in g.items()} for g in vus)
    assert a == b, (
        "les deux fichiers ne groupent pas les vues de la même façon — le rendu "
        f"partagé ne s'applique qu'à l'intersection :\n  seulement dans l'un : "
        f"{sorted(set(a) ^ set(b))}"
    )


def test_le_makefile_lance_la_suite_en_loadgroup():
    """`xdist_group` n'a d'effet qu'avec `--dist loadgroup`. Sans lui, tout retombe."""
    texte = (_RACINE / "Makefile").read_text(encoding="utf-8")
    dist = [ligne for ligne in texte.splitlines()
            if re.match(r"\s*PYTEST_DIST\s*[:?]?=", ligne)]
    assert dist, "PYTEST_DIST a disparu du Makefile"
    assert all("--dist loadgroup" in ligne for ligne in dist), (
        "PYTEST_DIST ne porte plus `--dist loadgroup` : les marques `xdist_group` des "
        "deux fichiers de rendu deviennent inertes et les 39 vues sont rendues deux "
        f"fois, en silence.\n  {dist}"
    )


def test_le_rendu_partage_ne_retient_pas_lobjet_apptest():
    """La rétention d'`AppTest` est ce qui a fait sortir la suite par l'OOM le 2026-09-17."""
    from tests.render_harness import _Rendu

    assert _Rendu._fields == ("erreur", "connexions", "figures"), (
        "`render_once` doit retenir des SCALAIRES. Un `AppTest` mis en cache pour 39 "
        f"vues retient l'arbre de rendu entier : {_Rendu._fields}"
    )
    # `figures` (R189, 2026-09-26) : un tuple de `Fig`, chacun fait de scalaires et de
    # tuples de scalaires — jamais un nœud de l'arbre ni la spec Plotly entière.
    from tests.render_harness import _fig_facts
    spec = {"data": [{"x": ["2026-01-01", "2026-01-31"], "name": "a"}],
            "layout": {"annotations": [{"x": "2026-01-10", "text": "t"}]}}
    fig = _fig_facts(spec, 1, 0, 0.5, "{}")

    def _scalaire(v) -> bool:
        return (v is None or isinstance(v, (str, int, float, bool))
                or (isinstance(v, tuple) and all(_scalaire(x) for x in v)))
    assert all(_scalaire(v) for v in fig), f"un fait de figure n'est pas scalaire : {fig}"


def test_le_predicat_separe_un_montage_garde_dun_montage_nu(tmp_path):
    """La preuve que ce fichier se donne à lui-même, à chaque exécution.

    Les quatre tests ci-dessus lisent l'arbre RÉEL : ils sont verts tant qu'il est
    sain, donc ils ne disent pas si le prédicat saurait voir un montage cassé. Ici on
    fabrique les deux formes — celle qui perd le partage, celle qui le tient — et on
    exige que `_cas_groupes` les sépare. Un prédicat qui rendrait la même chose des
    deux côtés serait vert sur l'arbre réel et aveugle le jour où il compte.

    C'est aussi ce qui rend la classe `a-cache-whose-sharing-depends-on-an-unasserted-scheduler-flag` prouvée sans dépendre d'une date passée : la mutation est rejouée à
    chaque exécution au lieu d'avoir été observée une fois.
    """
    import pytest as _pytest

    nu = [_pytest.param(v) for v in ("home", "admin")]
    garde = [_pytest.param(v, marks=_pytest.mark.xdist_group(v)) for v in ("home", "admin")]
    constant = [_pytest.param(v, marks=_pytest.mark.xdist_group("x"))
                for v in ("home", "admin")]

    class _Faux:
        pass

    def groupes(vues):
        faux = _Faux()
        faux._VUES = vues
        return _cas_groupes(faux)

    assert groupes(nu) == {"home": set(), "admin": set()}, (
        "le prédicat trouve un groupe là où aucune marque n'est posée — il lit autre "
        "chose que les marques, et le montage nu lui paraîtrait sain."
    )
    assert groupes(garde) == {"home": {"home"}, "admin": {"admin"}}, (
        "le prédicat ne voit pas une marque correctement posée — il rendrait tout "
        "l'arbre rouge, ce qui revient à ne rien garder."
    )
    assert groupes(constant) == {"home": {"x"}, "admin": {"x"}}, (
        "le prédicat n'expose pas la VALEUR du groupe, donc il ne peut pas distinguer "
        "un groupe par vue d'un groupe constant — qui sérialise sans rien partager."
    )
