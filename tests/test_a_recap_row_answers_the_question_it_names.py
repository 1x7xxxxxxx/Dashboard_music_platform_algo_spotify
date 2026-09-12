"""Une boîte, une question, un chiffre stable — et jamais un écart contre du vide.

Type: Test
Uses: pytest, platform_chart.render_platform_chart, home._recap_metrics, home._render_tiles
Depends on: src/dashboard/utils/platform_chart_notes.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
L'accueil a porté un TABLEAU MARKDOWN à droite de la figure du 2026-09-12 au soir du
même jour, puis des BOÎTES : une par plateforme au-dessus de la figure, une par
indicateur dérivé en dessous. Le garde a suivi son sujet plutôt que de rester sur une
surface morte — un test qui garde une mise en page disparue passe au vert sur tout.

Ce qu'il tient, et chacune de ces questions a coûté un défaut vu à l'écran :

1. **Le coût par écoute ne dépend pas du MODE D'AFFICHAGE.** Mesuré à 0,0170 € en
   « Par période » et 0,0101 € en « Cumulé » pour la même période et la même dépense :
   le dénominateur était reparti sur la série dessinée, dont la somme sous-compte un
   compteur (facteur 887 mesuré le 2026-09-11).
2. **Une série cumulée n'a pas de « meilleur pas ».** Elle ne fait que monter, donc
   son maximum est toujours son dernier point : « Meilleure semaine 286 346 ·
   01/06/26 » affichait le niveau final et la fin de la fenêtre comme un pic.
3. **La plateforme dominante n'existe pas en « Part » ni en « Cumulé ».** En part,
   `aligned` porte déjà des pourcentages — ce serait la part d'une part ; en cumulé,
   des niveaux, dont le rapport n'est pas une part de période.
4. **« 200 / 200 » n'est pas une information.** La ligne des périodes mesurées ne
   s'affiche que si la fenêtre a des trous.
5. **Aucun écart n'est affiché contre une période non mesurée.** Un « +100 % » contre
   une fenêtre jamais collectée transforme le début de NOTRE observation en croissance
   de l'artiste.
6. **Une boîte vide nomme son dernier relevé.** Mesuré en prod le 2026-09-12 : Spotify
   s'arrêtait au 5 septembre, sept jours en arrière ; YouTube et SoundCloud avaient
   des points, la figure se dessinait, et rien ne distinguait « zéro écoute » de
   « aucun export déposé ».

Journal de mutation — chacune vue ROUGE avant que le garde soit gardé, le 2026-09-12 :
  * dénominateur remis sur la série dessinée → cas 1 nomme les deux coûts ;
  * garde `mode != "cumulative"` du meilleur pas retiré → cas 2 ;
  * `mode not in ("share", "cumulative")` réduit à `!= "cumulative"` → cas 3 ;
  * plancher `seen < len(span)` retiré → cas 4 nomme « 200 / 200 » ;
  * `_delta` rendant `0 %` au lieu de `None` sur `before` absent → cas 5 ;
  * `if not value and _last.get(key)` réduit à `if _last.get(key)` → cas 6.
"""
from __future__ import annotations

import datetime as _d
from contextlib import nullcontext
from unittest.mock import patch

from src.dashboard.utils import platform_chart as pc
from src.dashboard.views.home import _recap_metrics, _render_tiles

_DAYS = [_d.date(2025, 1, 1) + _d.timedelta(days=i) for i in range(200)]

# Un COMPTEUR dont la collecte a des trous : c'est là que la somme des écarts et la
# différence de niveau divergent, donc la seule mise en scène où le défaut 1 existe.
_SERIES = {
    "spotify": [(x, 100) for x in _DAYS],
    "youtube": [(x, 50) for x in _DAYS[::7]],       # un jour sur sept seulement
}
# `platform_totals` rendrait la DIFFÉRENCE DE NIVEAU ; on la pose à la main pour que
# le test ne dépende d'aucune base. 20 000 est volontairement loin de la somme des
# écarts dessinés — sans cet écart, le cas 1 ne pourrait pas rougir.
_TOTALS = {"spotify": 20_000, "youtube": 20_000}
_SIDE = {"meta_spend": 400.0, "ig_delta": -5, "ig_followers": 1_525,
         "best_cpr": 0.0112, "best_cpr_name": "CONKRETE", "best_cpr_spend": 18.41,
         "best_algo_p": 0.118, "best_algo_name": "Radio", "best_algo_song": "X"}


class _Col:
    """Une colonne Streamlit réduite à ce que le code sous test lui demande."""

    def container(self, **_k):
        return nullcontext()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _metrics(mode: str, step: str = "month") -> list[tuple]:
    """Rend la figure et retourne les appels à `st.metric` des INDICATEURS."""
    seen: list[tuple] = []

    def _rec(label, value, delta=None, help=None, **_k):   # noqa: A002
        seen.append((str(label), str(value), delta, help))

    with patch("streamlit.plotly_chart", lambda f, **k: None), \
         patch("streamlit.caption", lambda *a, **k: None), \
         patch("streamlit.info", lambda *a, **k: None), \
         patch("streamlit.markdown", lambda *a, **k: None), \
         patch("streamlit.columns", lambda n, **k: [_Col() for _ in range(
             n if isinstance(n, int) else len(n))]), \
         patch("streamlit.metric", _rec):
        drawn = pc.render_platform_chart(
            _SERIES, since=_DAYS[0], until=_DAYS[-1], step=step, mode=mode,
            recap=True,
            recap_metrics=lambda al, sp, _gr, st_, md: _recap_metrics(
                _SIDE, _TOTALS, al, sp, st_, md),
            key=f"recap_{mode}_{step}")
    assert drawn, f"la figure ne s'est pas rendue en mode {mode}"
    return seen


def _one(rows: list[tuple], needle: str):
    """La boîte dont le libellé porte `needle` — jamais une autre."""
    return next((r for r in rows if needle in r[0]), None)


def _tiles(totals: dict, prev=None, side=None, last=None) -> list[tuple]:
    """Rend la rangée de boîtes du haut et retourne ses appels à `st.metric`."""
    seen: list[tuple] = []

    def _rec(label, value, delta=None, help=None, **_k):   # noqa: A002
        seen.append((str(label), str(value), delta, help))

    side = dict(side or _SIDE)
    if last is not None:
        side["last_measured"] = last

    with patch("streamlit.markdown", lambda *a, **k: None), \
         patch("streamlit.caption", lambda *a, **k: seen.append(("caption", str(a[0]), None, None))), \
         patch("streamlit.columns", lambda n, **k: [_Col() for _ in range(
             n if isinstance(n, int) else len(n))]), \
         patch("streamlit.metric", _rec):
        _render_tiles(totals, sum(v for v in totals.values() if v), 1_525,
                      prev=prev, side=side, prev_grand=None)
    return seen


# ── LES INDICATEURS DÉRIVÉS, SOUS LA FIGURE ─────────────────────────────────
#
# TROIS CAS ONT ÉTÉ RETIRÉS LE 2026-09-12 AVEC LEUR SUJET, et le geste mérite d'être
# nommé : supprimer des tests est exactement ce qu'on fait quand on veut du vert.
#
#   * `test_the_cost_per_stream_does_not_depend_on_the_display_mode`
#   * `test_a_cumulative_series_has_no_best_step`
#   * `test_the_dominant_platform_is_absent_where_it_would_be_a_share_of_a_share`
#
# Les trois gardaient le coût par écoute, le meilleur pas et la plateforme dominante,
# retirés de l'écran sur demande (« Enlève-moi les kpi : meilleur mois, coût par
# écoute, plateforme dominante »). Un garde dont la population est VIDE est pire
# qu'absent : il passe au vert sur n'importe quoi.
#
# ⚠️ Ce qu'ils défendaient n'est pas perdu pour autant. La règle « on ne somme pas des
# cumuls », qui était le fond du premier, vit dans
# `tests/test_the_live_chart_matches_the_illustration.py::test_no_indicator_ever_sums_cumulative_values`
# — mutation vue rouge le 2026-09-12. Si l'un de ces trois chiffres revient à
# l'écran un jour, son garde se réécrit à ce moment-là, contre la surface qu'il aura.

def test_measured_periods_only_speaks_when_the_window_has_holes():
    """« 200 / 200 » ne dit rien — la boîte ne s'affiche que si elle informe."""
    row = _one(_metrics("absolute", step="month"), "Périodes mesurées")
    if row is not None:
        a, _, b = row[1].partition(" / ")
        assert a != b.split()[0], (
            f"« {row[0]} » affiche {row[1]} : une fenêtre sans trou ne mérite pas de "
            "boîte. Elle occupe une place que le lecteur relit à chaque rendu pour y "
            "trouver la même absence d'information.")


# ── 5-6 : les boîtes du haut ─────────────────────────────────────────────────

def test_no_delta_is_claimed_against_an_unmeasured_period():
    """Sans période précédente MESURÉE, aucune flèche — jamais un « +100 % »."""
    for prev in (None, {}, {"spotify": None}, {"spotify": 0}):
        rows = _tiles({"spotify": 20_000}, prev=prev)
        box = _one(rows, "Spotify")
        assert box, f"la boîte Spotify a disparu avec prev={prev!r}"
        assert box[2] is None, (
            f"un écart {box[2]!r} s'affiche contre une période précédente {prev!r}. "
            "Un « +100 % » contre une fenêtre jamais collectée transforme le début de "
            "NOTRE observation en croissance de l'artiste.")

    # ⚠️ ET LA FLÈCHE DOIT EXISTER QUAND ELLE EST LÉGITIME. Sans cette moitié, le
    # garde passerait sur un `_delta` qui rend toujours `None` — l'absence attendue
    # serait produite par une fonction morte, pas par la règle.
    box = _one(_tiles({"spotify": 20_000}, prev={"spotify": 10_000}), "Spotify")
    assert box and box[2] == "+100,0 %", (
        f"l'écart de 10 000 → 20 000 ne vaut pas +100,0 % : {box[2]!r}")


def test_an_empty_box_names_its_last_reading():
    """Zéro écoute et « aucun export déposé » sont deux faits différents."""
    day = _d.date(2026, 9, 5)
    rows = _tiles({"spotify": None, "youtube": 12_000},
                  last={"spotify": day, "youtube": _d.date(2026, 9, 12)})
    captions = [r[1] for r in rows if r[0] == "caption"]
    assert any("05/09/26" in c for c in captions), (
        "une plateforme SANS mesure sur la fenêtre, mais avec un relevé au "
        f"{day}, n'affiche pas sa dernière date : {captions!r}. C'est le signalement "
        "du 2026-09-12 — la figure se dessinait grâce aux autres plateformes, et "
        "rien ne distinguait « zéro écoute » de « aucun export déposé ».")
    assert not any("12/09/26" in c for c in captions), (
        "une plateforme qui A des chiffres sur la fenêtre affiche quand même son "
        "dernier relevé : la mention devient du bruit sur toutes les boîtes au lieu "
        "de signaler les seules qui manquent.")


# ── LES TROIS PORTES DE LA DERNIÈRE SORTIE (2026-09-12) ─────────────────────
#
# « rajoute dans les kpi juste en dessous de streams totaux, la meilleure
# probabilité pour la dernière release de trigger : DW Radio et RR : 3 kpi ».
#
# Journal de mutation, chacune vue ROUGE :
#   * `_gates` réduit au seul maximum des trois → test_the_three_gates_are_three
#     ÉCHOUE en nommant les libellés trouvés ;
#   * le mot « prédite » retiré du bandeau → test_a_prediction_never_passes_for_an
#     _observed_rate ÉCHOUE ;
#   * `if any(...)` remplacé par `if True` → test_no_gate_is_shown_without_a
#     _prediction ÉCHOUE en nommant les « — » affichés.

_RELEASE = {"release_song": "Ô Chiotte l'arbitre", "release_age": 743,
            "release_dw": 0.07002, "release_rr": 0.06554, "release_radio": 0.11068}


def test_the_three_gates_are_three():
    """Trois portes distinctes, trois chiffres — jamais leur maximum."""
    rows = _tiles({"spotify": 20_000}, side={**_SIDE, **_RELEASE})
    labels = [r[0] for r in rows if r[0] != "caption"]
    for needle, pct in (("Discover Weekly", "7,0 %"),
                        ("Radio", "11,1 %"),
                        ("Release Radar", "6,6 %")):
        box = next((r for r in rows if needle in r[0]), None)
        assert box, (
            f"la porte « {needle} » n'a pas sa boîte. Libellés rendus : {labels}. "
            "Le maximum des trois répond à « quel titre du catalogue est le mieux "
            "placé », pas à « comment se présente ma dernière sortie ».")
        assert box[1] == pct, (
            f"« {needle} » affiche {box[1]!r} au lieu de {pct!r} — les trois "
            "probabilités ont été mélangées ou arrondies autrement")


def test_a_prediction_never_passes_for_an_observed_rate():
    """Le taux OBSERVÉ demanderait `s4a_song_algo_outcomes`, à 0 ligne."""
    rows = _tiles({"spotify": 20_000}, side={**_SIDE, **_RELEASE})
    captions = " ".join(r[1] for r in rows if r[0] == "caption")
    assert "prédite" in captions.lower() or "prédit" in captions.lower(), (
        f"aucun texte ne dit que ces pourcentages sont PRÉDITS : {captions!r}. "
        "Aucune issue de prédiction n'a jamais été saisie (0 ligne dans "
        "`s4a_song_algo_outcomes`, mesuré le 2026-09-12) : les présenter comme un "
        "taux de déclenchement inventerait une mesure.")
    assert "Ô Chiotte l'arbitre" in captions, (
        f"le titre auquel se rapportent les trois pourcentages n'est pas nommé : "
        f"{captions!r}. Trois nombres sans leur sujet sont trois nombres orphelins.")


def test_no_gate_is_shown_without_a_prediction():
    """Sans prédiction, pas de bloc — jamais trois « — » qui occupent la place."""
    rows = _tiles({"spotify": 20_000}, side=_SIDE)   # `_SIDE` n'a pas de release_*
    for needle in ("Discover Weekly", "Release Radar"):
        bad = next((r for r in rows if needle in r[0]), None)
        assert bad is None, (
            f"« {needle} » s'affiche à {bad[1]!r} alors qu'aucune prédiction n'existe "
            "pour la dernière sortie. Un « — » dans une boîte de probabilité se lit "
            "comme « le modèle donne zéro chance », pas comme « le modèle n'a pas "
            "encore tourné ».")
