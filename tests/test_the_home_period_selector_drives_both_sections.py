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

import pytest

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

    at = AppTest.from_file("src/dashboard/app.py", default_timeout=180)
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


def test_narrowing_the_period_shrinks_both_the_chart_and_the_totals() -> None:
    """La MOITIÉ qui compte : le sélecteur change les deux surfaces, pas une seule."""
    aid = _tenant_with_history()
    wide, narrow = _home(aid, "all"), _home(aid, "30d")

    wide_days, narrow_days = _chart_days(wide), _chart_days(narrow)
    assert narrow_days < wide_days, (
        f"la figure ne suit pas le sélecteur : {narrow_days} jours en « 30 jours » "
        f"contre {wide_days} en « depuis le début »")
    assert narrow_days <= 30, f"« 30 jours » en affiche {narrow_days}"

    wide_tile, narrow_tile = _tile(wide, "Spotify S4A"), _tile(narrow, "Spotify S4A")
    assert wide_tile and narrow_tile, "la tuile Spotify a disparu — garde à repointer"
    to_int = lambda v: int(str(v).replace(",", "").replace(" ", "").replace("—", "0"))  # noqa: E731
    assert to_int(narrow_tile) < to_int(wide_tile), (
        f"les totaux ne suivent pas le sélecteur : {narrow_tile} sur 30 jours contre "
        f"{wide_tile} depuis le début — le sélecteur ne change qu'une moitié de l'écran")


def test_apple_says_it_cannot_be_windowed_instead_of_showing_a_wrong_number() -> None:
    """Un instantané par CSV ne se découpe pas : on l'écrit, on ne devine pas."""
    at = _home(_tenant_with_history(), "30d")
    assert _tile(at, "Apple Music") == "—", (
        "Apple affiche un total sur une période bornée alors qu'elle n'a qu'un "
        "relevé : ce chiffre serait faux, ou celui d'une autre période")
