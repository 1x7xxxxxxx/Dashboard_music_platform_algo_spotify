"""Guard: la figure live et l'illustration committée montrent la MÊME chose.

Type: Utility
Uses: ast, src.dashboard.utils.platform_chart
Triggers: pytest
Persists in: nothing

Error class `the-live-chart-drifted-from-its-illustration`.

L'écran de bienvenue montre `assets/examples/dashboard-global.png` tant qu'un artiste
n'a pas de données, puis SA figure dès qu'il en a. Les deux doivent être la même
promesse, sinon la seconde se lit comme une régression — et c'est ce qui a été
signalé le 2026-09-08 : « ce n'est plus le même graphique, tu m'avais fait un plot qui
montre des courbes superposées des différentes plateformes avec différentes
couleurs ».

L'illustration est un `stackplot` aux couleurs `BLUE/ORANGE/AQUA` ; la figure live
était partie sur des lignes qui se croisent, aux couleurs de marque. Deux formes, deux
palettes, une seule promesse.

Ce garde tient les deux moitiés — la FORME (des aires empilées) et la PALETTE (celle
de l'illustration, lue dans le générateur et non recopiée ici, sinon les deux copies
divergent au premier changement).
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.dashboard.utils import platform_chart as pc

_GENERATOR = pathlib.Path("tools/dev/make_example_charts.py")
_CHART = pathlib.Path("src/dashboard/utils/platform_chart.py")


def _generator_palette() -> list:
    """Les couleurs de l'illustration, LUES dans son générateur.

    Par AST et non par import : le générateur importe matplotlib et bascule le backend
    au chargement, ce qu'un test n'a pas à déclencher pour lire trois constantes.
    """
    tree = ast.parse(_GENERATOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Tuple)
                and [getattr(t, "id", "") for t in node.targets[0].elts][:3]
                == ["BLUE", "ORANGE", "AQUA"]):
            return [c.value for c in node.value.elts][:3]
    pytest.fail("BLUE/ORANGE/AQUA introuvables dans le générateur — garde à repointer")
    return []


def test_the_live_palette_is_the_illustration_palette() -> None:
    """Mêmes couleurs, dans le même ordre — Spotify, YouTube, SoundCloud."""
    expected = _generator_palette()
    got = [pc._PALETTE_LIGHT[k] for k in ("spotify", "youtube", "soundcloud")]
    assert [c.lower() for c in got] == [c.lower() for c in expected], (
        f"la figure live utilise {got}, l'illustration {expected} : l'artiste voit "
        "deux figures différentes pour la même promesse")


def test_the_dark_palette_only_moves_what_the_validator_refused() -> None:
    """Le mode sombre garde la figure reconnaissable — un seul pas bouge.

    La bande de clarté du mode sombre (0,48–0,67) refuse `#eb6834` ; les deux autres
    passent tels quels. Décaler les trois « pour l'harmonie » ferait de la figure
    sombre une autre figure.
    """
    light, dark = pc._PALETTE_LIGHT, pc._PALETTE_DARK
    moved = [k for k in light if light[k].lower() != dark[k].lower()]
    assert moved == ["youtube"], (
        f"le mode sombre déplace {moved} — seul l'orange a été refusé par le "
        "validateur, le reste doit rester identique")


def test_the_form_is_a_stack_not_overlapping_lines() -> None:
    """`stackgroup` est ce qui distingue une aire empilée de lignes superposées.

    Lu sur la STRUCTURE : une recherche de texte trouverait ce mot dans cette
    docstring, et le cliquet du dépôt refuse les gardes textuels.
    """
    tree = ast.parse(_CHART.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "render_platform_chart")
    kwargs = {kw.arg for call in ast.walk(fn) if isinstance(call, ast.Call)
              for kw in call.keywords if kw.arg}
    assert "stackgroup" in kwargs, (
        "la figure n'empile plus : elle trace des lignes superposées, ce qui répond à "
        "« laquelle est la plus haute » et non à « combien au total, et qui y "
        "contribue » — la question de l'accueil")
    assert "fillcolor" in kwargs, "une aire empilée sans remplissage n'est pas une aire"


def test_a_missing_day_cuts_the_band_instead_of_dropping_it() -> None:
    """Une aire empilée n'a pas de trou : on coupe la bande, on ne la fait pas plonger.

    Compter l'absence pour zéro ferait chuter le TOTAL le jour où une source n'a pas
    tourné — exactement ce que la légende sous la figure interdit de laisser croire.
    """
    span = list(range(6))
    aligned = {"spotify": [1, 2, 3, 4, 5, 6],
               "soundcloud": [1, 1, None, None, 2, 2]}
    segments = pc._segments(span, aligned, ["spotify", "soundcloud"])
    assert segments == [[0, 1], [4, 5]], (
        f"les tranches sont {segments} : un jour non mesuré doit COUPER la bande")


def test_a_platform_with_no_point_takes_no_colour() -> None:
    """Une plateforme muette ne consomme pas une couleur qu'une autre porte ailleurs."""
    span = list(range(3))
    aligned = {"spotify": [1, 2, 3], "youtube": [None, None, None]}
    segments = pc._segments(span, aligned, ["spotify"])
    assert segments == [[0, 1, 2]], (
        "une plateforme sans aucun point ne doit pas casser la bande des autres")


# ── La couverture décide qui entre dans la pile ─────────────────────────────

def _coverage_order(span_len: int, measured: dict) -> tuple:
    """APPELLE la règle du rendu, ne la rejoue pas.

    La première version recopiait le calcul ici — deux règles pour une question, ce
    que ce fichier reproche justement à la figure. `stackable` est exportée pour ça.
    """
    aligned = {k: [1] * n + [None] * (span_len - n) for k, n in measured.items()}
    order, thin = pc.stackable(list(range(span_len)), aligned)
    return order, sorted(thin)


def test_a_sparse_platform_does_not_veto_the_others() -> None:
    """Les couvertures RÉELLES du 2026-09-08, pas un cas d'école.

    La bande se coupe dès qu'une plateforme manque : avec « au moins un point » pour
    critère, les 2 jours de YouTube du bac à sable supprimaient les 87 jours de
    Spotify, et la page n'affichait plus aucune figure.
    """
    principal = {"spotify": 87, "youtube": 90, "soundcloud": 82}
    bac_a_sable = {"spotify": 87, "youtube": 2, "soundcloud": 4}

    order, thin = _coverage_order(90, principal)
    assert order == ["spotify", "youtube", "soundcloud"] and not thin, (
        f"le profil principal perd une plateforme : empilées={order}, écartées={thin}")

    order, thin = _coverage_order(90, bac_a_sable)
    assert order == ["spotify"], (
        f"le bac à sable devrait empiler Spotify seul, il empile {order}")
    assert set(thin) == {"youtube", "soundcloud"}, (
        f"les sources clairsemées doivent être écartées et NOMMÉES, pas tues : {thin}")


def test_a_platform_left_out_is_named() -> None:
    """Une absence sans raison se lit comme une panne — la leçon de la matrice d'état."""
    phrase = pc.t_too_thin("🎬 YouTube", 2, 90)
    assert "2" in phrase and "90" in phrase, (
        "la phrase ne dit pas COMBIEN de jours sont mesurés — sans ce chiffre elle "
        "ne se distingue pas d'une panne")
