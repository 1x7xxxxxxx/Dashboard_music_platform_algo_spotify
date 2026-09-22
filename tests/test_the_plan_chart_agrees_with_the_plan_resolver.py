"""La figure d'évolution des plans ne peut pas contredire le résolveur de plan.

Type: Sub
Uses: src.dashboard.views.alerts._plan_events, src.utils.plan_resolver.plan_from_row
Depends on: pandas
Persists in: nothing

⚠️ CE GARDE EST NÉ ROUGE — mesuré en PRODUCTION le 2026-09-22.

La page Alertes portait deux surfaces qui lisaient deux sources différentes sur la
même question, et qui se contredisaient sur **quatre artistes sur huit** :

  · la figure « Évolution du nombre d'artistes » reconstruisait l'état depuis le seul
    `subscription_plan_history` — elle annonçait **5 Premium sur 6 artistes** ;
  · le tableau des utilisateurs, vingt lignes plus bas, appliquait l'expiration de
    l'essai — la vérité était **2 Premium sur 8 artistes**.

Trois trous du journal, chacun observé en production :
  · aucune ligne n'est jamais écrite quand un essai EXPIRE (trois essayeurs comptés
    Premium à vie, clos les 2026-07-14, 2026-07-15 et 2026-09-11) ;
  · `log_plan_change` avale ses erreurs par conception, et le remplissage de la
    migration 029 ne couvrait que les comptes d'alors — deux artistes n'avaient
    aucune ligne et n'apparaissaient nulle part sur la figure ;
  · un plan posé hors du chemin d'inscription ne passe par aucun appelant.

Classe : `a-figure-that-rebuilds-a-state-from-a-log-missing-an-event-type`.

Ce que ce garde couvre : le DERNIER point de la courbe, pour chaque artiste, contre
`plan_from_row` — la même précédence que celle que l'artiste voit dans son compte.
Ce qu'il NE couvre PAS, et c'est dit exprès : les seaux du passé, qu'aucune source
ne permet de reconstituer exactement (la date d'octroi d'un plan posé à la main
n'est portée par aucune colonne). Un geste voisin non couvert : une figure qui
lirait `saas_artists.tier` nu — elle serait fausse pour la même raison et ce test
ne la verrait pas.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.dashboard.views.alerts import _plan_events
from src.utils.plan_resolver import plan_from_row

_NOW = pd.Timestamp("2026-09-22 12:00:00")
_UTC_NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def _aware(d: str):
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


# (id, created_at, promo_plan, promo_expires, subscription_plan, tier)
# Les six lignes sont calquées sur la production du 2026-09-22.
_ETATS = [
    (1,  _aware("2026-03-10"), None,      None,                   None, "premium"),
    (10, _aware("2026-06-14"), None,      None,                   None, "free"),
    (11, _aware("2026-06-14"), "premium", _aware("2026-07-14"),   None, "free"),
    (13, _aware("2026-08-12"), "premium", _aware("2026-09-11"),   None, "free"),
    (14, _aware("2026-08-21"), None,      None,                   None, "free"),
    (18, _aware("2026-08-31"), "premium", _aware("2026-10-17"),   None, "free"),
]

# Le journal tel qu'il est RÉELLEMENT : il rate 14 et 18, et n'a aucune expiration.
_JOURNAL = [
    (1,  "premium", pd.Timestamp("2026-03-10")),
    (10, "free",    pd.Timestamp("2026-06-14")),
    (11, "premium", pd.Timestamp("2026-06-14")),
    (13, "premium", pd.Timestamp("2026-08-12")),
]


def _frames():
    hist = pd.DataFrame(_JOURNAL, columns=["artist_id", "plan", "changed_at"])
    etats = pd.DataFrame(_ETATS, columns=["id", "created_at", "promo_plan",
                                          "promo_plan_expires_at",
                                          "subscription_plan", "tier"])
    return hist, etats


def _dernier_plan(evts: pd.DataFrame) -> dict[int, str]:
    """Ce que la figure dessine sur son dernier seau, artiste par artiste."""
    asof = evts[evts["changed_at"] <= _NOW]
    dernier = asof.sort_values("changed_at").groupby("artist_id").tail(1)
    return {int(r.artist_id): r.plan for r in dernier.itertuples()}


@pytest.mark.parametrize("etat", _ETATS, ids=lambda e: f"artiste-{e[0]}")
def test_the_last_bucket_matches_the_resolver_for_every_artist(etat, monkeypatch):
    monkeypatch.setattr("src.utils.plan_resolver.datetime", _Gele)
    hist, etats = _frames()
    dessine = _dernier_plan(_plan_events(hist, etats, _NOW))

    aid, _created, promo, expires, sub, tier = etat
    attendu = plan_from_row((promo, expires, sub, tier))
    assert dessine.get(aid) == attendu, (
        f"artiste {aid} : la figure dessine {dessine.get(aid)!r}, "
        f"le résolveur rend {attendu!r}"
    )


def test_every_artist_appears_on_the_chart(monkeypatch):
    """Un compte que le journal a raté existe quand même — 14 et 18 en production."""
    monkeypatch.setattr("src.utils.plan_resolver.datetime", _Gele)
    hist, etats = _frames()
    dessine = _dernier_plan(_plan_events(hist, etats, _NOW))
    manquants = [int(e[0]) for e in _ETATS if int(e[0]) not in dessine]
    assert not manquants, f"artistes absents de la figure : {manquants}"


def test_an_expired_trial_stops_counting_as_premium(monkeypatch):
    """Le défaut EXACT qui a fait écrire ce fichier : l'essai immortel."""
    monkeypatch.setattr("src.utils.plan_resolver.datetime", _Gele)
    hist, etats = _frames()
    dessine = _dernier_plan(_plan_events(hist, etats, _NOW))
    expires = [11, 13]      # essais clos les 2026-07-14 et 2026-09-11
    toujours_premium = [a for a in expires if dessine.get(a) == "premium"]
    assert not toujours_premium, (
        f"essai expiré encore compté Premium : {toujours_premium}"
    )


def test_a_bucket_before_the_expiry_still_shows_the_trial(monkeypatch):
    """L'inverse, et il compte autant : on ne réécrit pas le passé.

    L'artiste 11 ÉTAIT premium entre le 2026-06-14 et le 2026-07-14. Une correction
    qui le rendrait gratuit sur toute la ligne remplacerait un mensonge par un autre.
    """
    monkeypatch.setattr("src.utils.plan_resolver.datetime", _Gele)
    hist, etats = _frames()
    evts = _plan_events(hist, etats, _NOW)
    avant = evts[evts["changed_at"] <= pd.Timestamp("2026-07-01")]
    dernier = avant.sort_values("changed_at").groupby("artist_id").tail(1)
    plans = {int(r.artist_id): r.plan for r in dernier.itertuples()}
    assert plans.get(11) == "premium", (
        f"le 2026-07-01 l'artiste 11 était en essai ; la figure dit {plans.get(11)!r}"
    )


class _Gele(datetime):
    """Un « maintenant » figé — sinon le test change de verdict le 2026-10-17."""

    @classmethod
    def now(cls, tz=None):
        return _UTC_NOW

    @classmethod
    def utcnow(cls):
        return _UTC_NOW.replace(tzinfo=None)


def test_the_frozen_clock_is_really_used():
    """Le gel doit mordre : sans lui, l'artiste 18 bascule le 2026-10-17.

    Un garde dont l'horloge dérive rend un verdict qui dépend du jour où on le
    lance — c'est `a-guard-whose-verdict-depends-on-the-day-it-runs`.
    """
    assert _Gele.now(timezone.utc) == _UTC_NOW
    assert _UTC_NOW < _aware("2026-10-17"), (
        "l'essai de l'artiste 18 doit être ENCORE ACTIF à l'instant figé, "
        "sans quoi le cas « essai en cours hors journal » n'est plus couvert"
    )
