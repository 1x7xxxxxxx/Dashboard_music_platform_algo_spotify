"""Un double axe ne porte jamais deux séries de MÊME nature.

Type: Test
Uses: ast, matplotlib (Agg)
Depends on: src/dashboard/utils/pdf_charts.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
`platform_chart` s'interdit le double axe et dit pourquoi : deux séries de même
nature d'ampleurs incomparables, posées sur deux échelles CHOISIES PAR NOUS, se
croisent où nous avons décidé qu'elles se croisent. Le lecteur y lit une corrélation
que la donnée ne porte pas.

Cet interdit ne valait que pour ce module. Le 2026-09-11, le balayage de
`pdf_charts.py` a rendu **six** `twinx()`, dont deux tombaient exactement dans la
classe — `apple_daily_growth` (streams/jour contre shazams/jour) et `apple_timeline`
(plays cumulés contre shazams cumulés). Deux comptes du même genre d'événement, et la
question qu'on vient poser à ces figures est précisément « les Shazams précèdent-ils
les streams ? ». Le croisement répondait à notre place.

Les quatre autres joignent des natures DIFFÉRENTES — des euros et des résultats, des
comptes et un pourcentage, des écoutes et des actions d'engagement. Il n'y existe
aucune échelle commune, donc aucun croisement à sur-interpréter : le double axe y est
la forme standard, et le retirer coûterait de la place sans rien corriger.

`youtube_channel_growth` a été converti aussi, et pour une AUTRE raison, dite ici
parce qu'elle se perdrait : des abonnés et des vues sont bien de natures différentes.
Mais la page YouTube du dashboard trace déjà ces deux séries en deux panneaux
empilés. La même donnée prenait deux formes dans le même produit.

Ce que ce garde ne peut pas faire : décider si deux séries sont « de même nature ».
C'est un jugement, et il est rendu une fois, ici, dans `_SAME_NATURE`. Le garde tient
que le jugement rendu est APPLIQUÉ, et que la liste ne peut pas s'étendre en silence.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CHARTS = _ROOT / "src" / "dashboard" / "utils" / "pdf_charts.py"

# Figures qui joignent deux séries de MÊME nature : double axe interdit.
_SAME_NATURE = {
    "apple_daily_growth": "streams/jour et shazams/jour — deux comptes d'événements",
    "apple_timeline": "plays cumulés et shazams cumulés — deux comptes d'événements",
    "youtube_channel_growth":
        "abonnés et vues sont de natures différentes, mais l'écran les trace déjà en "
        "deux panneaux : la même donnée ne prend pas deux formes dans le même produit",
}

# Figures qui joignent des natures DIFFÉRENTES : double axe légitime, avec sa raison.
_DIFFERENT_NATURES = {
    "sc_multiaxis": "écoutes contre likes/reposts/commentaires — subir contre agir",
    "ig_engagement": "des comptes contre un pourcentage",
    "meta_daily": "des euros contre un nombre de résultats",
}


def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_CHARTS.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _uses_twinx(fn: ast.FunctionDef) -> bool:
    return any(getattr(n.func, "attr", "") == "twinx"
               for n in ast.walk(fn) if isinstance(n, ast.Call))


def test_no_same_nature_figure_uses_a_dual_axis() -> None:
    fns = _functions()
    offenders = []
    for name, why in _SAME_NATURE.items():
        fn = fns.get(name)
        if fn is None:
            offenders.append(f"{name} : la figure n'existe plus — retire-la de la liste")
            continue
        if _uses_twinx(fn):
            offenders.append(f"{name} : double axe revenu — {why}")
    assert not offenders, (
        "Un double axe pose deux séries sur deux échelles que NOUS choisissons : leur "
        "croisement est notre décision, pas une mesure. Pour des séries de même "
        "nature, la forme admissible est `_stacked()` — un panneau chacune, l'axe des "
        "temps partagé.\n\n" + "\n".join(offenders))


def test_the_legitimate_dual_axes_are_named_with_their_reason() -> None:
    """Une exemption qui perd son site élargit la règle en silence.

    Et une NOUVELLE figure à double axe qui n'est dans aucune des deux listes n'a
    jamais été jugée : c'est elle que ce test attrape.
    """
    fns = _functions()
    gone = [n for n in _DIFFERENT_NATURES if n not in fns]
    assert not gone, f"figure(s) exemptée(s) qui n'existent plus : {gone}"

    unjudged = [name for name, fn in fns.items()
                if _uses_twinx(fn)
                and name not in _DIFFERENT_NATURES and name not in _SAME_NATURE]
    assert not unjudged, (
        f"figure(s) à double axe jamais jugée(s) : {unjudged}. Décide si ses deux "
        "séries sont de même nature — si oui, `_stacked()` ; sinon, ajoute-la à "
        "`_DIFFERENT_NATURES` avec sa raison.")

    still = [n for n in _DIFFERENT_NATURES if not _uses_twinx(fns[n])]
    assert not still, (
        f"{still} n'utilise plus de double axe : l'exemption ne garde plus rien, "
        "retire-la plutôt que de la laisser couvrir une figure qui a changé de forme.")


def test_a_converted_figure_really_draws_two_panels() -> None:
    """Lire l'AST ne prouve pas que la figure a deux panneaux — on la construit.

    Un `twinx()` retiré et remplacé par un seul panneau où les deux séries se
    superposent serait pire que le double axe : la petite disparaîtrait sous la
    grande, sans même un axe pour la lire.
    """
    import datetime as _d

    import matplotlib
    matplotlib.use("Agg")

    from src.dashboard.utils import pdf_charts as pc

    xs = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(12)]
    cases = {
        "youtube_channel_growth": [(x, 9000 + i, 100000 + i * 900)
                                   for i, x in enumerate(xs)],
        "apple_daily_growth": [(x, 40 + i, 3 + i % 4) for i, x in enumerate(xs)],
        "apple_timeline": [(x, 1000 + i * 130, 20 + i * 3) for i, x in enumerate(xs)],
    }
    captured = {}
    real = pc._fig_to_uri

    def spy(fig):
        captured["axes"] = len(fig.axes)
        return real(fig)

    pc._fig_to_uri = spy
    try:
        for name, rows in cases.items():
            captured.clear()
            assert getattr(pc, name)(rows), f"{name} n'a rien rendu"
            assert captured["axes"] == 2, (
                f"{name} rend {captured['axes']} panneau(x) au lieu de 2 — les deux "
                "séries se superposent sur une seule échelle, ce qui est pire que le "
                "double axe qu'on vient de retirer")
    finally:
        pc._fig_to_uri = real
