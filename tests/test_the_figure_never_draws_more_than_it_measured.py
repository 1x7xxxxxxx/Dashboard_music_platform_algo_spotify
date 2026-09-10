"""La figure ne peut pas dessiner plus que ce qui a été mesuré dans la fenêtre.

Type: Test
Uses: pytest, plotly
Depends on: src/dashboard/utils/platform_chart.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10, base locale, locataire 1)
----------------------------------------------------------
La figure de l'accueil dessinait PLUS que la somme des jours mesurés dans la période
demandée :

    période        pas       Σ mesuré    Σ dessinée
    Cette année    semaine      4 559        4 671    (+2,5 %)
    12 mois        semaine      8 490        8 609    (+1,4 %)
    12 mois        année        8 490       23 251    (×2,7)

Deux causes composées. `_aggregate` sommait **toute** la série dans ses seaux —
`since`/`until` ne servaient qu'au plancher, jamais à la somme — et `_bucket_key(since)`
ramenait la borne basse EN ARRIÈRE (au lundi, ou au 1ᵉʳ janvier), donc la fenêtre
s'élargissait au lieu que le seau de bord se découpe. « 12 mois » au pas annuel retenait
le seau `2025-01-01`, qui embarque **toute l'année 2025** — huit mois que personne n'a
demandés.

Pourquoi aucun test ne le voyait
--------------------------------
`test_a_bounded_period_is_never_larger_than_the_lifetime` compare deux **tuiles** entre
elles. Rien ne comparait la figure à sa propre source. Et l'écart allait dans le sens
INVERSE de ce que la prose du produit affirmait (« la courbe ne trace que ce que nous
avons mesuré, elle est donc plus petite »), donc personne ne le cherchait de ce côté.

L'invariant ci-dessous est le plus petit qui l'aurait attrapé, et il ne demande aucune
base : **une figure ne peut pas montrer une écoute qui n'a pas été mesurée dans sa
fenêtre.**
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.dashboard.utils import platform_chart as pc

_DAY0 = dt.date(2024, 1, 1)


def _cadences() -> dict:
    """Des séries aux cadences du même ordre que les vraies, épinglées dans le module.

    `platform_chart.py:96-107` mesure sur l'artiste 1 : Spotify 100 % des jours,
    SoundCloud 56 %, YouTube 39 %. On reproduit ces trous — une série sans trou ne
    testerait ni le plancher de seau, ni les bords de fenêtre.
    """
    spotify = [(_DAY0 + dt.timedelta(days=i), 100) for i in range(500)]
    youtube = [(_DAY0 + dt.timedelta(days=i), 7) for i in range(500) if i % 5 == 0]
    soundcloud = [(_DAY0 + dt.timedelta(days=i), 3) for i in range(300) if i % 2 == 0]
    return {"spotify": spotify, "youtube": youtube, "soundcloud": soundcloud}


def _figure(monkeypatch, series, **kw):
    import streamlit as st_mod
    captured = {}
    monkeypatch.setattr(st_mod, "plotly_chart",
                        lambda fig, **k: captured.setdefault("fig", fig))
    monkeypatch.setattr(st_mod, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st_mod, "info", lambda *a, **k: None)
    drawn = pc.render_platform_chart(series, title="T", key="t", **kw)
    return (captured.get("fig") if drawn else None)


def _drawn_per_platform(fig) -> dict:
    """Σ des y RÉELLEMENT remis à Plotly, par plateforme, d'après le nom des traces."""
    out: dict = {}
    for tr in fig.data:
        out[tr.name] = out.get(tr.name, 0) + sum(v for v in (tr.y or []) if v)
    return out


def _measured(series, key, since, until) -> int:
    return sum(v for d, v in series.get(key, [])
               if (since is None or d >= since) and (until is None or d <= until))


# ── L'invariant, sur le produit cartésien des menus ─────────────────────────

@pytest.mark.parametrize("days", [30, 90, 365, None])
@pytest.mark.parametrize("step", [None, "week", "year"])
def test_no_period_and_no_step_draws_more_than_the_window_holds(
        monkeypatch, days, step) -> None:
    """Le cœur du garde. `mode="absolute"` : chaque y EST une quantité du pas."""
    series = _cadences()
    until = _DAY0 + dt.timedelta(days=499)
    since = (until - dt.timedelta(days=days - 1)) if days else None

    fig = _figure(monkeypatch, series, since=since, until=until,
                  step=step, mode="absolute")
    if fig is None:
        pytest.skip(f"aucune figure pour days={days} step={step} — cas couvert ailleurs")

    drawn = _drawn_per_platform(fig)
    for key, label in pc.PLATFORM_LABELS.items():
        if label not in drawn:
            continue
        held = _measured(series, key, since, until)
        assert drawn[label] <= held + 1e-6, (
            f"days={days} step={step} — {label} : la figure dessine {drawn[label]:,} "
            f"pour {held:,} mesurés dans la fenêtre. Une figure ne peut pas montrer "
            "une écoute qui n'a pas été mesurée dans sa période : le seau de bord "
            "doit être DÉCOUPÉ, pas la fenêtre élargie."
        )


def test_a_full_window_draws_a_dense_platform_exactly(monkeypatch) -> None:
    """L'autre bord : ne rien perdre non plus quand la source est complète.

    Sans cette moitié, « ne jamais dépasser » se satisferait d'une figure vide.
    """
    series = _cadences()
    until = _DAY0 + dt.timedelta(days=499)
    fig = _figure(monkeypatch, series, since=_DAY0, until=until,
                  step="week", mode="absolute")
    drawn = _drawn_per_platform(fig)
    held = _measured(series, "spotify", _DAY0, until)
    assert drawn[pc.PLATFORM_LABELS["spotify"]] == held, (
        "Spotify est mesurée tous les jours : la figure doit en dessiner le total exact")


# ── Une collecte qui s'arrête ne retombe pas à zéro ─────────────────────────

def test_a_platform_that_stops_being_collected_holds_its_plateau(monkeypatch) -> None:
    """`known()` traitait « après la dernière mesure » comme « avant la première ».

    Les deux ne sont pas symétriques : avant, zéro est vrai — la plateforme n'était pas
    collectée. Après, la plateforme existe toujours, c'est NOUS qui avons cessé de
    regarder. En mode Cumulé — le défaut de l'accueil — la bande montait puis
    **retombait à zéro**, ce qui se lit « YouTube a perdu toutes ses écoutes ».
    """
    day = dt.date(2026, 1, 1)
    series = {
        "spotify": [(day + dt.timedelta(days=i), 100) for i in range(20)],
        "youtube": [(day + dt.timedelta(days=i), 10) for i in range(5)],
    }
    fig = _figure(monkeypatch, series, step="day", mode="cumulative")
    ys = [list(tr.y) for tr in fig.data if tr.name == pc.PLATFORM_LABELS["youtube"]]
    assert ys, "YouTube doit être tracée"
    flat = [v for seg in ys for v in seg]
    assert flat[-1] == max(flat), (
        f"la bande cumulée de YouTube finit à {flat[-1]} après un maximum de "
        f"{max(flat)} : un cumul ne redescend jamais. Tracé : {flat}")
    assert 0 not in flat[1:], (
        f"des zéros après la dernière mesure : {flat}. Ils affirment « compteur "
        "inchangé » un jour où personne n'a regardé.")


def test_the_note_counts_the_days_after_the_last_measurement(monkeypatch) -> None:
    """`t_missing` promet « un blanc, jamais un zéro » — le décompte doit le suivre."""
    day = dt.date(2026, 1, 1)
    span = [day + dt.timedelta(days=i) for i in range(20)]
    aligned = {"youtube": [10] * 5 + [None] * 15}
    gaps = pc.gap_counts(span, aligned, ["youtube"])
    assert gaps["youtube"] == 15, (
        f"{gaps['youtube']} pas comptés manquants au lieu de 15 — les jours postérieurs "
        "à la dernière mesure étaient dessinés à zéro ET absents du décompte censé les "
        "nommer.")


def test_the_aggregation_honours_the_window_at_every_step() -> None:
    """`_aggregate` reçoit `since`/`until` : elle les applique à TOUS les pas.

    Écrit après une mutation restée VERTE. Au pas jour, `_window` borne déjà l'axe, donc
    retirer le découpage ici ne change rien à la figure — l'invariant du haut ne pouvait
    pas le voir. Une fonction qui accepte une fenêtre et l'ignore à un seul de ses pas
    est exactement la classe d'asymétrie que cette séance corrige ailleurs
    (`known()`) : on la garde fermée par un test qui l'atteint directement.
    """
    rows = [(_DAY0 + dt.timedelta(days=i), 10) for i in range(30)]
    since = _DAY0 + dt.timedelta(days=10)
    until = _DAY0 + dt.timedelta(days=19)

    for step in ("day", "week", "year"):
        out = pc._aggregate({"spotify": rows}, step, since, until)["spotify"]
        total = sum(v for _, v in out)
        assert total <= 100, (
            f"pas {step} : {total} sommés pour 10 jours à 10 dans la fenêtre. "
            "`_aggregate` doit découper avant de sommer, quel que soit le pas.")
