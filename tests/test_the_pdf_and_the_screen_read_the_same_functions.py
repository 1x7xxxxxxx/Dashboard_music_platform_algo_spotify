"""La figure du PDF et celle de l'écran lisent les mêmes fonctions.

Type: Test
Uses: ast, matplotlib (Agg)
Depends on: src/dashboard/utils/pdf_charts.py, src/dashboard/utils/pdf_exporter/_report.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
R91 : « donner au PDF les figures pertinentes en partageant la DONNÉE, pas le rendu ».
Le rendu ne PEUT pas être partagé — `kaleido` est absent, donc Plotly → PNG est
impossible, et c'est pour ça que `pdf_charts` existe en matplotlib. Ce qui peut l'être,
et qui compte davantage, ce sont les règles.

L'inventaire du 2026-09-11 a nommé le manque : le PDF portait **25 figures** et aucune
ne montrait l'évolution multi-plateformes, celle qui ouvre l'accueil. Il n'avait que
`platform_breakdown` — un bâton par plateforme, des totaux sans histoire.

Le risque de la corriger est la CINQUIÈME copie. Ce dépôt a payé quatre copies de
« somme des compteurs par vidéo », dont trois fausses au même instant. Ce garde tient
donc que la figure du PDF appelle les fonctions partagées plutôt que de refaire le
calcul, et qu'elle ne fabrique pas sa propre requête.

Et il tient une propriété qui ne se lit pas dans le code : **la pile ne retombe pas à
zéro au bord droit.** Trouvée en REGARDANT le PNG, pas en lisant le code — le `span`
va jusqu'à la dernière mesure de la plateforme la plus récente, et un `None` devenu 0
dans un `stackplot` dit « plus aucune écoute » là où il faut dire « plus aucune
mesure ».
"""
from __future__ import annotations

import ast
import datetime as _d
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CHARTS = _ROOT / "src" / "dashboard" / "utils" / "pdf_charts.py"
_REPORT = _ROOT / "src" / "dashboard" / "utils" / "pdf_exporter" / "_report.py"
_HOME = _ROOT / "src" / "dashboard" / "views" / "home.py"

# Les fonctions de série que les DEUX surfaces doivent appeler.
_SHARED = {"daily_streams_by_platform", "cumulative_by_platform"}


def _names_called(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
            for n in ast.walk(tree) if isinstance(n, ast.Call)}


def test_the_report_feeds_the_figure_from_the_shared_series_functions() -> None:
    missing = _SHARED - _names_called(_REPORT)
    assert not missing, (
        f"le PDF n'appelle plus {sorted(missing)} — soit il a recopié la règle, soit "
        "la figure a disparu. Une règle recopiée diverge : ce dépôt en a payé quatre "
        "copies, dont trois fausses au même instant.")


def test_the_screen_reads_the_same_two_functions() -> None:
    """Si l'écran cesse de les lire, « les mêmes » ne veut plus rien dire."""
    missing = _SHARED - _names_called(_HOME)
    assert not missing, (
        f"l'accueil n'appelle plus {sorted(missing)} — le PDF et l'écran ne partagent "
        "plus rien, et ce garde ne compare plus deux choses.")


def test_the_pdf_figure_reuses_the_screen_transformations() -> None:
    """Pas seulement les données : la mise en forme aussi.

    Le report en avant des compteurs, le plancher de seau et le refus d'inventer un
    jour non mesuré vivent dans `platform_chart`. Les réécrire en matplotlib serait
    exactement la duplication qu'on vient de retirer ailleurs.
    """
    tree = ast.parse(_CHARTS.read_text(encoding="utf-8"))
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "platform_evolution"),
              None)
    assert fn is not None, "la figure `platform_evolution` a disparu du PDF"
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    for needed in ("_window", "_as_mode", "stackable"):
        assert needed in called, (
            f"`platform_evolution` n'appelle plus `{needed}` : elle refait en "
            "matplotlib une mise en forme qui existe déjà, et qui divergera.")
    # Et elle ne parle pas à la base : la donnée lui est donnée.
    text = ast.unparse(fn).lower()
    assert "select" not in text and "fetch_query" not in text, (
        "`platform_evolution` interroge la base elle-même — elle doit recevoir les "
        "séries que l'appelant a déjà lues, sinon le PDF et l'écran peuvent lire deux "
        "instants différents")


def test_the_stack_does_not_fall_to_zero_at_the_right_edge() -> None:
    """Trouvé en REGARDANT le PNG. Une lecture du code ne l'aurait pas montré.

    Mise en scène : Spotify s'arrête cinq jours avant YouTube, comme en production le
    2026-09-11 (S4A au 06-07, YouTube au 06-12). Sans troncature, les cinq derniers
    points de Spotify valent `None` → tracés 0 → la bande tombe à la verticale et le
    lecteur voit un effondrement qui n'a pas eu lieu.
    """
    import matplotlib
    matplotlib.use("Agg")

    from src.dashboard.utils import pdf_charts as pc

    days = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(40)]
    series = {"spotify": [(d, 10) for d in days[:35]],
              "youtube": [(d, 1) for d in days]}
    cumulative = {"youtube": [(days[0], 500), (days[-1], 900)]}

    captured = {}
    real = pc._fig_to_uri

    def spy(fig):
        ax = fig.axes[0]
        # La hauteur totale de la pile au dernier point tracé.
        tops = [coll.get_paths()[0].vertices for coll in ax.collections]
        captured["last_total"] = max(float(v[:, 1].max()) for v in tops) if tops else 0
        captured["xmax"] = max(float(v[:, 0].max()) for v in tops) if tops else 0
        return real(fig)

    pc._fig_to_uri = spy
    try:
        assert pc.platform_evolution(series, cumulative, days[0], days[-1])
    finally:
        pc._fig_to_uri = real

    import matplotlib.dates as mdates
    last_drawn = mdates.num2date(captured["xmax"]).date()
    assert last_drawn <= days[34], (
        f"la figure va jusqu'au {last_drawn} alors que Spotify s'arrête le "
        f"{days[34]} : les journées sans mesure sont tracées à zéro, et la pile "
        "s'effondre au bord droit")
    assert captured["last_total"] > 0


def test_a_platform_has_one_colour_in_the_whole_product() -> None:
    """Deux figures d'une même page donnaient deux couleurs à chaque plateforme.

    Vu en regardant la page « Vue d'ensemble » le 2026-09-11 : Spotify bleu dans
    l'évolution, vert dans le bâton juste en dessous ; YouTube orange puis rouge. La
    couleur est l'identité d'une bande — c'est même le seul relief que porte la figure
    empilée — et une identité qui change d'une figure à l'autre n'en est pas une.
    """
    from src.dashboard.utils import pdf_charts as pdf
    from src.dashboard.utils import platform_chart as screen

    order = ["spotify", "youtube", "soundcloud", "apple"]
    assert list(pdf._PLATFORM_COLORS) == [screen._PALETTE_LIGHT[k] for k in order], (
        f"le PDF peint {list(pdf._PLATFORM_COLORS)} là où l'écran peint "
        f"{[screen._PALETTE_LIGHT[k] for k in order]} — la même plateforme change de "
        "couleur entre deux figures du même document")
