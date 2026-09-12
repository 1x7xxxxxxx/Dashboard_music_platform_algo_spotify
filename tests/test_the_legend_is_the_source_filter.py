"""La légende EST le filtre de sources — sauf là où elle rendrait un chiffre faux.

Type: Test
Uses: platform_chart (Plotly, sans Streamlit — `plotly_chart` est neutralisé)
Depends on: src/dashboard/utils/platform_chart.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Demandé le 2026-09-11 : « peut-on intégrer le clickage des plateformes directement
sur le graphique plutôt qu'avec le filtre qui doit sélectionner ? ça enlèverait de la
complexité ». Un clic de légende est côté NAVIGATEUR : il ne relance pas le script.
Le `multiselect` qu'il remplace coûtait un rendu complet — **287 ms** mesurés en
production — pour masquer une bande.

Trois choses peuvent casser ça sans qu'aucune erreur n'apparaisse, et chacune est
épinglée ici :

* **Une plateforme est découpée en TRANCHES**, une par plage continue, donc plusieurs
  traces. Si chacune porte son entrée de légende, YouTube apparaît deux fois ; si le
  clic ne bascule pas le groupe, il n'en masque qu'un morceau. Une bande à moitié
  masquée se lit comme une donnée manquante.
* **La légende en haut recouvre le titre.** C'est le défaut de 2026-09-08 — « la
  légende est masquée, c'est assez moche » — et il revient au premier réglage par
  défaut, parce que le défaut de Plotly est précisément en haut à droite.
* **Le mode « part » doit garder son `multiselect`.** Ses pourcentages sont établis
  sur l'ensemble affiché, et un clic de légende masque une trace SANS recalculer les
  autres : la pile ne ferait plus 100 %. C'est un chiffre faux, pas une figure
  incomplète — la seule raison pour laquelle l'exception existe.
"""
from __future__ import annotations

import ast
import datetime as _d
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def figure():
    """Rend la figure hors Streamlit et la renvoie, pour un mode donné."""
    from src.dashboard.utils import platform_chart as pc

    captured = {}
    real_chart, real_notes = pc.st.plotly_chart, pc._render_notes
    pc.st.plotly_chart = lambda fig, **k: captured.__setitem__("fig", fig)
    pc._render_notes = lambda *a, **k: None

    span = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(40)]
    # YouTube en DEUX plages continues : c'est le cas qui produit plusieurs traces.
    series = {"spotify": [(d, 10) for d in span],
              "youtube": [(d, 2) for d in span[:12]] + [(d, 3) for d in span[20:]]}

    def build(mode: str):
        captured.clear()
        assert pc.render_platform_chart(series, since=span[0], until=span[-1],
                                        step="day", mode=mode, key="guard"), \
            f"la figure n'a rien rendu en mode {mode}"
        return captured["fig"]

    try:
        yield build
    finally:
        pc.st.plotly_chart, pc._render_notes = real_chart, real_notes


@pytest.mark.parametrize("mode", ["cumulative", "absolute"])
def test_each_platform_has_exactly_one_legend_entry(figure, mode) -> None:
    fig = figure(mode)
    # La mise en scène se prouve sur les TRACES, pas sur les entrées : mesurée sur
    # les entrées, elle échouait la première sous la mutation qu'elle est censée
    # laisser passer, et accusait la mise en scène au lieu du défaut.
    per_group: dict = {}
    for t in fig.data:
        per_group.setdefault(t.legendgroup, []).append(t)
    assert any(len(v) > 1 for v in per_group.values()), (
        f"aucune plateforme n'est découpée en plusieurs tranches ({ {k: len(v) for k, v in per_group.items()} }) "
        "— ce test ne vérifie donc rien de ce qu'il prétend")

    entries = [t.name for t in fig.data if t.showlegend]
    assert sorted(entries) == sorted(set(entries)), (
        f"une plateforme apparaît plusieurs fois dans la légende : {entries}. "
        "Seule la PREMIÈRE tranche doit porter l'entrée.")

    # La clé « ▨ Aucune mesure » n'est pas une plateforme : c'est la LÉGENDE d'un
    # encodage visuel, ajoutée le 2026-09-12 avec la bande hachurée. Elle n'a droit
    # qu'à UNE entrée, comme les plateformes — plusieurs bandes hachurées, une seule
    # clé. Sans cette distinction, le test compterait une entrée de plus à chaque
    # trou et se lirait comme « Spotify apparaît deux fois ».
    absence = [e for e in entries if e.startswith("▨")]
    assert len(absence) <= 1, f"la clé d'absence est répétée : {absence}"

    platforms = [e for e in entries if not e.startswith("▨")]
    assert len(platforms) == 2, f"attendu Spotify + YouTube, obtenu {platforms}"


@pytest.mark.parametrize("mode", ["cumulative", "absolute"])
def test_one_click_hides_the_whole_platform(figure, mode) -> None:
    """Sans `togglegroup`, le clic ne masque que la tranche sur laquelle on a cliqué."""
    fig = figure(mode)
    assert fig.layout.legend.groupclick == "togglegroup", (
        f"groupclick={fig.layout.legend.groupclick!r} — masquer YouTube n'en "
        "masquerait qu'un morceau, et la bande tronquée se lit comme un trou de "
        "données")
    assert all(t.legendgroup for t in fig.data), (
        "une trace sans `legendgroup` échappe au groupe et reste affichée seule")


@pytest.mark.parametrize("mode", ["cumulative", "absolute"])
def test_the_legend_never_returns_to_the_title_margin(figure, mode) -> None:
    """Le défaut du 2026-09-08, et le défaut de Plotly : en haut, sur le titre."""
    fig = figure(mode)
    assert fig.layout.showlegend is True
    assert fig.layout.legend.y is not None and fig.layout.legend.y < 0, (
        f"legend.y={fig.layout.legend.y} — la légende est dans la zone du titre, "
        "qu'elle recouvre. Elle va SOUS la figure.")
    assert fig.layout.margin.b >= 56, (
        f"margin.b={fig.layout.margin.b} — la légende est sous la figure mais la "
        "marge basse ne lui laisse pas de place : elle sortira du cadre")


def test_the_share_mode_keeps_its_widget_because_clicking_would_lie(figure) -> None:
    fig = figure("share")
    assert fig.layout.showlegend is False, (
        "le mode « part » affiche une légende cliquable : masquer une trace n'y "
        "recalcule pas les pourcentages, donc la pile n'y ferait plus 100 %")
    assert not any(t.showlegend for t in fig.data)


def test_home_offers_the_widget_only_in_share_mode() -> None:
    """Le `multiselect` de sources ne doit subsister que dans l'exception.

    Lu par AST plutôt qu'en cherchant une chaîne : le nom `multiselect` survit dans un
    commentaire, et ce dépôt s'est déjà fait prendre par un garde textuel.
    """
    home = (_ROOT / "src" / "dashboard" / "views" / "home.py").read_text(encoding="utf-8")
    tree = ast.parse(home)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "multiselect"]
    sources = [n for n in calls
               if any(isinstance(a, ast.Constant) and "trend_sources" in str(a.value)
                      for a in ast.walk(n))]
    assert len(sources) == 1, (
        f"{len(sources)} `multiselect` de sources dans home.py — attendu exactement "
        "un, celui du mode « part »")

    # Il doit vivre sous un test qui NOMME le mode « share ».
    guarded = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.If)
        and any(isinstance(c, ast.Constant) and c.value == "share"
                for c in ast.walk(n.test))
        and any(m is sources[0] for m in ast.walk(n))
    ]
    assert guarded, (
        "le `multiselect` de sources n'est plus conditionné au mode « part » : il "
        "réapparaît dans les modes où la légende fait déjà le travail")
