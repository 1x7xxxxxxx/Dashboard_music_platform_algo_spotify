"""Guard: une seule période, choisie une fois, lue par les totaux ET par la figure.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl), date_range
Depends on: views/home._section_streams, views/home._section_platform_trend
Persists in: —

Demandé le 2026-09-08 : « un filtre de date intelligent qui sélectionne d'office depuis
le début, avec sélecteur cette année etc. Ce sélecteur intervient dans les streams
totaux et évolution par plateforme ».

Les trois choses que ce fichier tient, et qu'aucune autre ne tient :

1. **Un seul sélecteur.** Deux widgets pour un même réglage se réécrivent l'un l'autre
   à chaque rerun — le dépôt l'a payé avec les deux sélecteurs de langue.
2. **Il change vraiment les deux surfaces.** Un sélecteur qui ne change qu'une moitié
   de l'écran est pire que pas de sélecteur : les deux moitiés se contredisent.
3. **« Depuis le début » est le défaut**, et ce n'est pas « une très grande fenêtre » :
   les totaux y sont les compteurs des plateformes, pas la somme de nos mesures.
"""
from __future__ import annotations

import datetime as _dt
import os
import socket
import time

from pathlib import Path

import pytest

# CHEMIN ABSOLU, dérivé de la racine du dépôt.
#
# `AppTest.from_file` résout un chemin RELATIF depuis le fichier qui l'appelle — donc
# depuis `tests/`, ce qui donne `tests/src/dashboard/app.py`. Le chemin relatif ne
# marchait que par la grâce de la version de Streamlit installée localement ; en CI il
# a rendu `FileNotFoundError` sur trois tests, et le rouge cachait tout ce qui suivait.
_APP = str(Path(__file__).resolve().parent.parent / "src" / "dashboard" / "app.py")

from src.dashboard.utils import date_range

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


# ── La règle de période, pure : testable sans base ni Streamlit ─────────────

def test_the_default_is_since_the_beginning() -> None:
    """« D'office depuis le début » — et sans borne, pas une borne très ancienne."""
    assert date_range.DEFAULT == "all"
    assert date_range.bounds("all") == (None, None)
    assert date_range.is_bounded("all") is False


def test_this_year_starts_on_january_first() -> None:
    """`today` est injecté : un test qui lit l'horloge change de verdict le 1ᵉʳ janvier."""
    since, until = date_range.bounds("ytd", today=_dt.date(2026, 9, 8))
    assert (since, until) == (_dt.date(2026, 1, 1), _dt.date(2026, 9, 8))


@pytest.mark.parametrize("key,span", [("30d", 30), ("90d", 90), ("12m", 365)])
def test_a_rolling_window_counts_its_own_last_day(key, span) -> None:
    """Bornes INCLUSES des deux côtés : « 30 jours » en compte 30, pas 31."""
    today = _dt.date(2026, 9, 8)
    since, until = date_range.bounds(key, today=today)
    assert until == today
    assert (until - since).days + 1 == span


def test_every_option_has_a_label() -> None:
    """Un sélecteur dont une option n'a pas de mot est une option qu'on ne choisit pas."""
    for key in date_range.RANGES:
        assert date_range.label(key).strip(), key


# ── Le comportement à l'écran ───────────────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — needs the live DB",
)


def _tenant_with_history() -> int:
    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.platform_timeseries import daily_streams_by_platform

    db = get_db_connection()
    try:
        rows = db.fetch_query("SELECT id FROM saas_artists WHERE active ORDER BY id")
        for (aid,) in rows or []:
            series = daily_streams_by_platform(db, int(aid))
            if sum(len(r) for r in series.values()) > 60:
                return int(aid)
    finally:
        db.close()
    pytest.skip("aucun locataire avec assez d'historique dans la base locale")
    return 0


def _home(artist_id: int, period: str | None = None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(_APP, default_timeout=180)
    state = {
        "authenticated": True, "role": "artist", "artist_id": artist_id,
        "username": "artist@test", "email": "artist@test", "name": "artist@test",
        "_last_activity": time.time(), "_nav_page": "home",
    }
    if period:
        state["_home_range"] = period
        state["_home_range_widget"] = period
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def _chart_days(at) -> int:
    import json
    figs = at.get("plotly_chart")
    if not figs:
        return 0
    proto = figs[0].proto
    raw = getattr(proto, "spec", None) or getattr(getattr(proto, "figure", None), "spec", None)
    spec = json.loads(raw)
    days = {x for tr in spec.get("data", []) for x in (tr.get("x") or [])}
    return len(days)


def _tile(at, label: str):
    for m in at.metric:
        if label in m.label:
            return m.value
    return None


def test_there_is_exactly_one_period_selector() -> None:
    """Deux widgets pour un réglage se réécrivent l'un l'autre à chaque rerun."""
    at = _home(_tenant_with_history())
    # `st.segmented_control` se lit sous `button_group` dans AppTest, pas sous son
    # propre nom — vérifié le 2026-09-08, la première version de ce test comptait 0
    # widget sur une page qui en portait bien un. Les deux formes sont interrogées
    # parce que le rendu retombe sur `st.radio` sur les vieilles versions.
    widgets = [w for w in (list(at.get("button_group")) + list(at.radio))
               if str(getattr(w, "key", "") or "").startswith("_home_range")]
    assert len(widgets) == 1, (
        f"{len(widgets)} sélecteurs de période sur l'accueil — il en faut exactement un")


def test_narrowing_the_period_shrinks_the_chart() -> None:
    """Le sélecteur commande la figure.

    Il commandait DEUX surfaces jusqu'au 2026-09-10 ; les tuiles ont quitté l'accueil
    ce jour-là, parce qu'elles portaient les compteurs « depuis le début » des
    plateformes à côté d'une figure qui ne trace que le mesuré — deux nombres pour la
    même période, dont aucun n'était faux.

    Ce que ce garde ne couvre PLUS, et il faut le dire : que les totaux suivent la
    période. Ils sont désormais sur les pages plateforme, chacune avec son propre
    filtre (`period_filter`), et aucun test ne relie encore ces deux filtres.
    """
    aid = _tenant_with_history()
    wide, narrow = _home(aid, "all"), _home(aid, "30d")

    wide_days, narrow_days = _chart_days(wide), _chart_days(narrow)
    assert narrow_days < wide_days, (
        f"la figure ne suit pas le sélecteur : {narrow_days} jours en « 30 jours » "
        f"contre {wide_days} en « depuis le début »")
    assert narrow_days <= 30, f"« 30 jours » en affiche {narrow_days}"

    assert not _tile(wide, "Spotify S4A"), (
        "une tuile de total est revenue sur l'accueil. Elle porte un compteur « depuis "
        "le début » que la figure d'à côté contredit par construction — c'est la "
        "contradiction retirée le 2026-09-10, et `RANGE_NOTE` était la prose qui "
        "l'excusait.")


# La règle « Apple ne se découpe pas » vit toujours, ailleurs : elle est gardée par
# `tests/test_apple_periods_are_asked_not_guessed.py` (non_overlapping_cover,
# apple_period_plays rendant None sous deux relevés) et par la page Apple elle-même.
# Le garde qui la lisait SUR L'ACCUEIL est retiré avec la tuile qu'il lisait.


# ── Ce que la période a ajouté le 2026-09-08 ────────────────────────────────

def test_a_custom_range_is_offered_and_bounded_by_its_two_dates() -> None:
    """« Un filtre intelligent PERSONNALISABLE » : deux dates, pas six raccourcis."""
    assert "custom" in date_range.RANGES, "aucune période sur mesure"
    # Tant que les deux dates ne sont pas posées, « sur mesure » ne borne rien : une
    # fenêtre vide serait pire que pas de filtre.
    assert date_range.bounds("custom") == (None, None)


def test_the_tile_of_an_unmeasured_platform_shows_a_dash_on_screen() -> None:
    """La règle À L'ÉCRAN, pas seulement dans son helper.

    La première version de ce garde n'exerçait que `measured_days`, et elle est restée
    VERTE quand on a débranché la règle dans `home` — le helper marchait, la page
    affichait « 0 ». C'est la question qui compte : que lit l'artiste sur la tuile ?

    Le couple (locataire, période) est CHOISI par la mesure : on cherche un cas où une
    plateforme n'a aucune mesure et une autre en a. Sans un tel cas, le test saute — il
    ne s'invente pas un verdict.
    """
    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.platform_timeseries import (
        daily_streams_by_platform, measured_days,
    )

    labels = {"spotify": "Spotify S4A", "youtube": "YouTube", "soundcloud": "SoundCloud"}
    db = get_db_connection()
    try:
        tenants = [int(r[0]) for r in
                   (db.fetch_query("SELECT id FROM saas_artists WHERE active ORDER BY id") or [])]
        for aid in tenants:
            series = daily_streams_by_platform(db, aid)
            if not any(series.values()):
                continue
            for period in ("30d", "90d", "ytd", "12m"):
                since, until = date_range.bounds(period)
                missing = [k for k in labels if not measured_days(series, k, since, until)]
                present = [k for k in labels if measured_days(series, k, since, until)]
                if missing and present:
                    at = _home(aid, period)
                    value = _tile(at, labels[missing[0]])
                    assert value == "—", (
                        f"locataire {aid}, période {period} : la tuile "
                        f"{labels[missing[0]]} affiche {value!r} alors qu'AUCUNE mesure "
                        "n'existe sur la période. « 0 » affirme qu'il ne s'est rien "
                        "passé ; on n'a pas regardé.")
                    return
    finally:
        db.close()
    pytest.skip("aucun couple (locataire, période) sans mesure dans la base locale")


def test_the_measured_days_helper_separates_the_two_absences() -> None:
    """Zéro mesure et zéro écoute ne sont pas la même chose.

    Signalé le 2026-09-08 : « on a des 0 sur youtube et soundcloud, je pense qu'on a
    tout simplement pas la data ». Un « 0 » affirme qu'il ne s'est rien passé ; « — »
    dit qu'on n'a pas regardé.
    """
    from src.dashboard.utils.platform_timeseries import measured_days
    import datetime as d

    series = {"youtube": [(d.date(2026, 1, 1), 5)]}
    assert measured_days(series, "youtube",
                         d.date(2026, 6, 1), d.date(2026, 6, 30)) == 0
    assert measured_days(series, "spotify") == 0
    assert measured_days(series, "youtube") == 1


def test_the_followers_delta_needs_two_readings() -> None:
    """Un écart a besoin de deux points ; « +0 » sur un seul relevé serait inventé."""
    from src.dashboard.utils.platform_timeseries import followers_change

    class _DB:
        def __init__(self, rows): self.rows = rows
        def fetch_query(self, sql, params=None): return self.rows

    import datetime as d
    assert followers_change(_DB([]), 1) is None
    assert followers_change(_DB([(d.date(2026, 1, 1), 100)]), 1) is None
    assert followers_change(
        _DB([(d.date(2026, 1, 1), 100), (d.date(2026, 2, 1), 92)]), 1
    ) == (100, 92, -8)
