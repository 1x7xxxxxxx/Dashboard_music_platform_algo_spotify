"""Guard: the architecture Views Map names every view that exists.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `views-map-drifts-from-the-views`.

`CLAUDE.md` has carried the sentence "La Views Map a déjà divergé deux fois sans que
rien ne le signale" since 2026-08-21. Measured 2026-08-28: it had drifted a third time.
**15 of 44 views were absent** — `onboarding`, `onboarding_health`, `db_health`,
`meta_cpr_optimizer`, `sacem`, `data_wrapped`, `account`, `referral`, `upgrade`,
`register`, `privacy`, `usage_analytics`, `etl_logs`, `referral_admin`, `promo_admin` —
a third of the dashboard, including two of the three surfaces an artist meets first.

Rule 18 asks for a `code-architecture-reviewer` spawn past five module changes. That is
a review, and a review is a thing someone has to remember to ask for; three drifts
happened while it existed. This asks the question mechanically, on every run.

It checks **presence, not prose**: whether each view is named at all, never whether its
description is good. A guard that tried to judge the description would either be
unfalsifiable or would fail on every honest edit, and this file would be deleted within
a week. Presence is the property that actually rotted.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Ce fichier ne lit QUE des documents : rien sous src/, airflow/ ni migrations/.
# `make test-fast` le saute, `make test-docs` ne lance que lui et ses pairs,
# `make test` et la CI le lancent toujours.
# Voir `.claude/dev-docs/test-suite-performance.md`.
pytestmark = pytest.mark.docs


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
ARCH = REPO / ".claude" / "dev-docs" / "architecture.md"
VIEWS_DIR = REPO / "src" / "dashboard" / "views"

# Not views: the package marker, and `home/`-style internals are covered by their
# package name. Anything else under views/ is a page and belongs in the map.
_NOT_A_VIEW = {"__init__", "__pycache__"}


def _views() -> set[str]:
    return {
        p.stem if p.is_file() else p.name
        for p in VIEWS_DIR.iterdir()
        if (p.is_file() and p.suffix == ".py") or (p.is_dir() and (p / "__init__.py").exists())
    } - _NOT_A_VIEW


def _views_map_text() -> str:
    """The `## Dashboard Views Map` section only — not the whole document.

    Scoped deliberately. Several of these names also appear elsewhere in
    architecture.md (data-flow prose, the DAG table), so searching the full file would
    make the guard pass on views the map itself never lists — the exact vacuity that
    let three drifts through.
    """
    text = ARCH.read_text(encoding="utf-8")
    m = re.search(r"^## Dashboard Views Map\s*$", text, re.M)
    assert m, "the `## Dashboard Views Map` heading is gone from architecture.md"
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _is_package(view: str) -> bool:
    return (VIEWS_DIR / view).is_dir()


def is_named(view: str, body: str) -> bool:
    """Does the map name this view anywhere? Pure."""
    return re.search(rf"`{re.escape(view)}(?:\.py|/)?`", body) is not None


def ghosts_in(body: str, views: set[str]) -> list[str]:
    """Views the map gives a ROW to (first cell only) that no longer exist. Pure."""
    first_cells = re.findall(r"^\| `([a-z_0-9]+)(?:\.py|/)?`", body, re.M)
    return sorted(set(first_cells) - views)


@pytest.mark.parametrize("view", sorted(_views()))
def test_every_view_is_named_in_the_views_map(view):
    body = _views_map_text()
    assert is_named(view, body), (
        f"`{view}` exists under src/dashboard/views/ but the Dashboard Views Map in "
        f"architecture.md does not name it. Add a row: file, page name, data sources, "
        f"role. The map is what a reader consults instead of listing the directory — "
        f"a view missing from it is a view nobody knows to look at."
    )


def test_the_map_does_not_name_views_that_are_gone():
    """The other direction: a deleted view must not keep a row.

    Reads only the first column of each row, so a view named inside another row's
    prose (`saisie_s4a.py` mentions the deleted `reglages.py` on purpose, to record
    what replaced it) is not mistaken for a live entry.
    """
    ghosts = ghosts_in(_views_map_text(), _views())
    assert not ghosts, (
        f"the Views Map has rows for {ghosts}, which no longer exist under "
        "src/dashboard/views/. A map that points at deleted modules sends readers "
        "nowhere — the same thing the code graph does, and the reason CLAUDE.md says "
        "the graph orients but does not prove."
    )


def test_the_extraction_is_not_vacuous():
    """A section regex that matched nothing would make every check above pass."""
    body = _views_map_text()
    assert body.count("\n|") > 20, (
        f"the Views Map section yielded only {body.count(chr(10) + '|')} table rows. "
        "Either the map was gutted, or the heading match landed in the wrong place "
        "and the parametrised checks are asserting against an empty string."
    )
    assert len(_views()) > 20, "views/ yielded almost nothing — check the listing"


@pytest.mark.parametrize("view", sorted(_views()))
def test_the_map_says_whether_a_view_is_a_file_or_a_package(view):
    r"""Le NOM ne suffit pas : la carte doit dire la FORME.

    Mesuré le 2026-09-18. `trigger_algo.py` et `meta_mapping.py` ont été scindés en
    PAQUETS (`src/dashboard/views/trigger_algo/`, `meta_mapping/`) — le même mouvement
    que `credentials.py → credentials/`, que la carte dénote correctement. Les deux
    autres lignes sont restées en `.py`, et **le garde est passé vert** : son motif
    `` `{view}(?:\.py|/)?` `` accepte le nom suivi de `.py`, de `/`, ou de rien, donc
    il ne peut pas distinguer un fichier d'un répertoire.

    Un lecteur qui cherche `trigger_algo.py` sur le disque ne le trouve pas — et la
    carte existe précisément pour qu'on la consulte AU LIEU de lister le répertoire.
    C'est l'exclusion nº 2 que `guard_scope` déclarait déjà : « le CONTENU de ce que
    la carte dit d'une vue, seulement son nom ».
    """
    body = _views_map_text()
    paquet = _is_package(view)
    comme_fichier = re.search(rf"`{re.escape(view)}\.py`", body) is not None
    comme_paquet = re.search(rf"`{re.escape(view)}/`", body) is not None
    if paquet:
        assert comme_paquet and not comme_fichier, (
            f"`{view}` est un PAQUET sur le disque "
            f"(`src/dashboard/views/{view}/__init__.py`), et la carte l'écrit "
            f"{'aussi en `.py` ' if comme_fichier else ''}"
            f"{'sans jamais le suffixer par `/`' if not comme_paquet else ''}. "
            "Écrire `" + view + "/` (package) — la ligne `credentials/` est le modèle."
        )
    else:
        assert comme_fichier and not comme_paquet, (
            f"`{view}` est un FICHIER sur le disque "
            f"(`src/dashboard/views/{view}.py`), et la carte l'écrit comme un "
            "répertoire. Un lecteur ira chercher un dossier qui n'existe pas."
        )


def test_the_form_predicate_separates_the_two_shapes():
    """La preuve que ce fichier se donne à lui-même, à chaque exécution.

    Le test ci-dessus est vert tant que l'arbre est sain, donc il ne dit pas s'il
    SAURAIT voir une carte qui ment sur la forme. On fabrique les deux écritures et on
    exige qu'elles se séparent — un prédicat qui rendrait la même chose des deux côtés
    serait vert sur l'arbre réel et aveugle le jour où il compte.
    """
    corps = "| `foo.py` | une vue | - | all |\n| `bar/` (package) | une autre | - | all |"
    assert re.search(r"`foo\.py`", corps) and not re.search(r"`foo/`", corps)
    assert re.search(r"`bar/`", corps) and not re.search(r"`bar\.py`", corps)
    # Et le motif de l'ANCIEN garde ne les separe PAS — c'est le defaut lui-meme.
    def ancien(v):
        return re.search(rf"`{v}(?:\.py|/)?`", corps) is not None

    assert ancien("foo") and ancien("bar"), (
        "le motif historique devrait matcher les deux formes — s'il ne le fait plus, "
        "la demonstration de sa cecite ne tient plus et ce test doit etre relu")


def test_at_least_one_view_of_each_shape_exists():
    """Non-vacuite : sans les deux formes dans l'arbre, le test ci-dessus ne garde rien."""
    formes = {_is_package(v) for v in _views()}
    assert formes == {True, False}, (
        f"l'arbre ne porte plus qu'une seule forme de vue ({formes}) — "
        "`test_the_map_says_whether_a_view_is_a_file_or_a_package` ne prouve plus rien")


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, both directions: a view absent from the map is seen, a row for a
    deleted view is seen, and a deleted view named in ANOTHER row's prose (the
    `saisie_s4a` → `reglages` case) is not mistaken for a row."""
    body = ("| `home.py` | Accueil | - | all |\n"
            "| `reglages.py` | Réglages | - | all |\n"
            "| `saisie_s4a.py` | Saisie (remplace `reglages.py`) | - | all |\n")
    assert not is_named("youtube", body) and is_named("home", body)
    assert ghosts_in(body, {"home", "saisie_s4a"}) == ["reglages"]
    assert ghosts_in(body.replace("| `reglages.py` | Réglages | - | all |\n", ""),
                     {"home", "saisie_s4a"}) == []
