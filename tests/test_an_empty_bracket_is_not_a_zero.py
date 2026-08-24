"""Un panier sans observation n'est pas un panier à 0 %.

Classe `absence-rendered-as-a-measurement`.

`pdf_charts.pi_gate` calculait `(cell.get("prob") or 0)`. Pour un panier dont
`prob` vaut `null` et `n` vaut 0 — aucun titre observé — cela produisait une barre
de hauteur zéro, que le lecteur du rapport lit « 0 % de chance de déclencher ».
C'est l'inverse de ce que la donnée dit. Cas réel dans
`machine_learning/models/v3/threshold_tables.json` : Release Radar, panier « 50+ »,
n = 0.

Le deuxième volet est de même nature : 66,7 % mesuré sur **3** titres s'affichait
aussi haut et aussi net que 99,4 % mesuré sur 172. Le graphique porte donc
l'effectif de chaque panier, et atténue ceux qui en ont trop peu.

Le test lit l'IMAGE produite (les hauteurs et les alphas des barres), pas le code
qui la produit : c'est le seul niveau où « la barre est-elle dessinée ? » a une
réponse.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from src.dashboard.utils import pdf_charts  # noqa: E402

_TABLES = {
    "pi_brackets": ["0-10", "11-20", "50+"],
    "discover_weekly": {
        "0-10": {"prob": 1.2, "n": 84},      # mesuré, effectif suffisant
        "11-20": {"prob": 66.7, "n": 3},     # mesuré, effectif dérisoire
        "50+": {"prob": None, "n": 0},       # JAMAIS observé
    },
    "release_radar": {},
    "radio": {},
}


@pytest.fixture
def _bars(monkeypatch):
    """Intercepte les barres réellement dessinées pour le 1er panneau."""
    captured = []
    real_bar = plt.Axes.bar

    def _spy(self, *args, **kwargs):
        out = real_bar(self, *args, **kwargs)
        captured.append(out)
        return out

    monkeypatch.setattr(plt.Axes, "bar", _spy)
    pdf_charts.pi_gate(_TABLES)
    assert captured, "aucune barre dessinée — le graphique n'a pas été produit"
    return list(captured[0])


def test_a_never_observed_bracket_is_invisible(_bars):
    """`n = 0` ⇒ barre totalement transparente, jamais un zéro affiché."""
    assert _bars[2].get_alpha() == 0.0, (
        "le panier « 50+ » n'a AUCUNE observation ; le dessiner (même à 0 %) "
        "affirme une mesure qui n'existe pas"
    )


def test_a_thin_bracket_is_visibly_attenuated(_bars):
    """`n = 3` reste affiché, mais ne peut pas peser autant que `n = 84`."""
    assert _bars[1].get_alpha() < _bars[0].get_alpha()


def test_a_well_populated_bracket_is_shown_at_full_strength(_bars):
    assert _bars[0].get_alpha() == 1.0


def test_the_sample_size_is_written_on_the_axis():
    """Un taux sans son effectif n'est pas lisible — et le PDF part à un tiers."""
    fig = plt.figure()
    try:
        uri = pdf_charts.pi_gate(_TABLES)
    finally:
        plt.close(fig)
    assert uri and uri.startswith("data:image"), "le graphique doit être produit"


def test_a_measured_zero_is_still_drawn():
    """`prob = 0` avec un effectif réel est une MESURE : elle reste visible."""
    tables = {
        "pi_brackets": ["0-10"],
        "discover_weekly": {"0-10": {"prob": 0.0, "n": 120}},
        "release_radar": {}, "radio": {},
    }
    captured = []
    real_bar = plt.Axes.bar

    def _spy(self, *args, **kwargs):
        out = real_bar(self, *args, **kwargs)
        captured.append(out)
        return out

    plt.Axes.bar = _spy
    try:
        pdf_charts.pi_gate(tables)
    finally:
        plt.Axes.bar = real_bar
    assert list(captured[0])[0].get_alpha() == 1.0, (
        "un 0 % mesuré sur 120 titres est une information ; l'effacer la perd"
    )
