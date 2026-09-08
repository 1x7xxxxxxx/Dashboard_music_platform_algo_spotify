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


# ── Une source récente ne coûte pas l'historique des autres ─────────────────

def _shape(span_len: int, measured_last: dict) -> dict:
    """Des séries alignées où chaque plateforme n'est mesurée que sur ses N derniers pas."""
    return {k: [None] * (span_len - n) + [1] * n for k, n in measured_last.items()}


def test_a_recent_platform_does_not_cost_the_others_their_history() -> None:
    """La forme RÉELLE du bac à sable au 2026-09-08, pas un cas d'école.

    Spotify y est mesuré 87 jours sur 90, YouTube 2 et SoundCloud 4 — parce qu'ils
    viennent d'être branchés. Une bande empilée exige que toutes les plateformes soient
    connues le même jour ; si « pas encore collectée » comptait comme « on ne sait
    pas », les 2 jours de YouTube effaceraient les 87 de Spotify et la page n'aurait
    **aucune** figure. C'est ce qui s'est produit après le déploiement du matin.

    Avant sa première mesure, une plateforme n'a rien apporté à ce qu'on peut montrer :
    zéro y est la bonne valeur, et seuls les trous À L'INTÉRIEUR de sa plage coupent.
    """
    span = list(range(90))
    aligned = _shape(90, {"spotify": 87, "youtube": 2, "soundcloud": 4})
    order, _thin = pc.stackable(span, aligned)
    assert set(order) == {"spotify", "youtube", "soundcloud"}, (
        f"une plateforme récente est écartée de la pile : {order}")
    covered = sum(len(seg) for seg in pc._segments(span, aligned, order))
    assert covered >= 85, (
        f"la bande ne couvre que {covered} jours sur 90 : les plateformes branchées "
        "récemment effacent l'historique des autres")


def test_a_hole_inside_a_platform_range_still_cuts() -> None:
    """L'autre moitié : dans sa plage, un jour non mesuré reste inconnu."""
    span = list(range(6))
    aligned = {"spotify": [1, 1, 1, 1, 1, 1],
               "youtube": [None, 1, None, 1, 1, 1]}   # plage = 1..5, trou en 2
    order, _ = pc.stackable(span, aligned)
    segments = pc._segments(span, aligned, order)
    assert [0, 1] in segments and all(2 not in seg for seg in segments), (
        f"le trou interne n'a pas coupé la bande : {segments}")


def test_a_platform_measured_once_in_a_long_range_is_named_not_stacked() -> None:
    """Trop clairsemée DANS SA PROPRE PLAGE : elle couperait partout."""
    span = list(range(40))
    aligned = {"spotify": [1] * 40,
               "youtube": [None] * 10 + [1] + [None] * 28 + [1]}   # 2 mesures sur 30
    order, thin = pc.stackable(span, aligned)
    assert order == ["spotify"] and "youtube" in thin, (
        f"empilées={order}, écartées={sorted(thin)}")


def test_a_platform_left_out_is_named() -> None:
    """Une absence sans raison se lit comme une panne — la leçon de la matrice d'état."""
    phrase = pc.t_too_thin("🎬 YouTube", 2, 90)
    assert "2" in phrase and "90" in phrase, (
        "la phrase ne dit pas COMBIEN de jours sont mesurés — sans ce chiffre elle "
        "ne se distingue pas d'une panne")


# ── L'identité ne repose jamais sur la seule couleur ────────────────────────

def test_the_labels_are_on_the_bands_not_in_a_legend_box() -> None:
    """Le relief exigé par le validateur, et le correctif de « la légende est masquée ».

    La palette porte un avertissement de contraste ; le validateur impose alors
    « visible labels or a table view ». La table sous la figure a été retirée le
    2026-09-08 (« inutile ») — l'étiquette directe est donc le SEUL relief restant, et
    la retirer laisserait l'identité d'une aire à sa seule couleur.

    C'est aussi ce qui règle « la légende est masquée, c'est assez moche » : la légende
    horizontale était ancrée dans la marge où vit le titre sur deux lignes, et les deux
    se recouvraient. Une étiquette collée à sa bande n'a rien à recouvrir.
    """
    tree = ast.parse(_CHART.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "render_platform_chart")
    kwargs = {kw.arg for call in ast.walk(fn) if isinstance(call, ast.Call)
              for kw in call.keywords if kw.arg}
    assert "annotations" in kwargs, (
        "la figure n'a plus d'étiquette posée sur les bandes : l'identité d'une aire "
        "ne repose plus que sur sa couleur, ce que l'avertissement de contraste du "
        "validateur interdit")
    assert "showlegend" in kwargs, (
        "la boîte de légende n'est plus explicitement éteinte — elle revient dans la "
        "marge du titre, qu'elle recouvre")


def test_the_labels_are_spaced_in_the_margin_not_stuck_to_the_bands() -> None:
    """Ancrées à la FIGURE, à des hauteurs distinctes — sinon elles se recouvrent.

    La première version les posait au milieu de leur aire : dès qu'une bande devient
    fine, deux étiquettes se superposent. Vu au rendu le 2026-09-08 sur « Depuis le
    début », où YouTube et SoundCloud pèsent quelques écoutes contre plusieurs milliers.

    Le garde exerce la fonction plutôt que de lire le fichier : `annotations=` peut
    être passé avec n'importe quoi.
    """
    span = list(range(10))
    aligned = {"spotify": [1000] * 10, "youtube": [1] * 10, "soundcloud": [1] * 10}
    order, _ = pc.stackable(span, aligned)
    labels = pc.margin_labels(order, ink="#000")
    assert len(labels) == len(order), "une plateforme empilée sans étiquette"
    assert {a["yref"] for a in labels} == {"paper"}, (
        "les étiquettes suivent l'épaisseur des bandes : elles se recouvriront")
    ys = sorted(a["y"] for a in labels)
    gaps = [round(b - a, 6) for a, b in zip(ys, ys[1:])]
    assert gaps and min(gaps) > 0.1, (
        f"les étiquettes sont trop proches ({gaps}) — elles se chevaucheront")


def test_the_daily_table_is_gone_and_nothing_still_calls_it() -> None:
    """Retirée le 2026-09-08 (« inutile »), et retirée VRAIMENT.

    Une fonction morte laissée en place finit par cacher une conséquence vivante —
    classe `dead-code-can-hide-a-live-consequence`, mesurée dans ce dépôt le 2026-09-06.
    """
    # Lu sur la STRUCTURE : le cliquet `test_a_guard_reads_structure_not_text` refuse
    # une comparaison de chaînes au texte source, et il a raison ici comme ailleurs —
    # ce fichier NOMME `render_daily_table` deux fois dans sa propre documentation.
    gone = {"render_daily_table"}

    assert not hasattr(pc, next(iter(gone))), (
        "`render_daily_table` est encore définie alors que plus rien ne l'appelle")

    home_tree = ast.parse(pathlib.Path("src/dashboard/views/home.py")
                          .read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(home_tree) if isinstance(n, ast.Call)}
    imported = {a.name for n in ast.walk(home_tree)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not (called | imported) & gone, (
        "l'accueil appelle ou importe une fonction supprimée")
