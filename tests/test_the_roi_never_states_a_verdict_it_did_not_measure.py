"""Un ROI ne s'affirme pas sur un chiffre qu'on n'a pas lu.

Type: Test
Uses: pytest
Depends on: src/dashboard/utils/kpi_helpers.py, src/dashboard/utils/pdf_exporter/_renderers.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
Trois défauts empilés sur le même écran, tous sur de l'argent affiché à des artistes.

1. **Deux grains, une comparaison.** `v_artist_monthly_revenue` n'a pas de jour — ses
   colonnes sont `year` et `month`. Le revenu était donc filtré sur
   `make_date(year, month, 1) BETWEEN from AND to` pendant que la dépense Meta l'était
   sur `day_date`. Une fenêtre 15 janvier → 10 septembre **excluait janvier en entier**
   (sa clé 2026-01-01 précède `from`) et **comptait tout septembre**, 20 jours après la
   fin de la fenêtre comprise. Le numérateur et le dénominateur du ROI ne couvraient
   pas la même période.

2. **Une panne rendue en verdict.** `except Exception: pass` laissait `revenue_eur` à
   `0.0` et `profitable` à `False`. Pire, `_render_roi` du PDF PAYANT recalculait son
   propre statut : `rev = float(roi.get('revenue_eur') or 0)` → `net = 0` →
   **« ✅ Rentable »** imprimé sur le rapport d'un artiste, produit par une base
   injoignable. Corriger le helper seul ne l'aurait pas protégé — la revue de design
   l'a trouvé, pas moi.

3. **`.fillna(0)` après un `outer merge`** faisait lire « 0 € dépensé » un mois sans
   dépense Meta. Les deux appelants pandas étaient DÉJÀ écrits pour l'absence (`.sum()`
   saute les NaN, l'un fait un `dropna` explicite) : c'est le helper qui la leur cachait.

Ce que ce garde vérifie est l'EFFET, jamais la forme du code : ce que la requête rend
sur une vraie base, et ce que le gabarit du PDF écrit.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.dashboard.utils.kpi_helpers import fmt_eur, get_roi_data, month_window

_ABSENT_TENANT = 999_999


def _live_db():
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return None
        db.fetch_query("SELECT 1")
        return db
    except Exception:
        return None


# ── La fenêtre, pure ────────────────────────────────────────────────────────

def test_the_window_covers_whole_months_at_both_ends() -> None:
    """Le mois est le grain NATIF du revenu, pas une approximation choisie."""
    assert month_window(dt.date(2026, 1, 15), dt.date(2026, 9, 10)) == (
        dt.date(2026, 1, 1), dt.date(2026, 9, 30))
    # Février bissextile : la borne haute est le dernier jour réel, pas le 30.
    assert month_window(dt.date(2024, 2, 5), dt.date(2024, 2, 20))[1] == dt.date(2024, 2, 29)
    # Un mois déjà entier n'est pas déplacé.
    assert month_window(dt.date(2026, 3, 1), dt.date(2026, 3, 31)) == (
        dt.date(2026, 3, 1), dt.date(2026, 3, 31))


# ── Les deux côtés du ratio partagent leurs bornes ──────────────────────────

def test_both_sides_of_the_ratio_are_bounded_the_same_way() -> None:
    """Le revenu rendu doit être EXACTEMENT celui de la fenêtre effective.

    C'est ce qui prouve la symétrie : si le helper bornait encore le revenu sur la clé
    de mois et la dépense sur le jour, l'un des deux différerait de la somme calculée
    ici sur les mêmes bornes.
    """
    db = _live_db()
    if db is None:
        pytest.skip("pas de Postgres sur 5433 — ce garde a besoin du vrai moteur")
    since, until = dt.date(2026, 1, 15), dt.date(2026, 9, 10)
    eff_from, eff_to = month_window(since, until)
    try:
        roi = get_roi_data(db, 1, since, until)
        rev = db.fetch_query(
            "SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue "
            "WHERE artist_id = %s AND make_date(year, month, 1) BETWEEN %s AND %s",
            (1, eff_from, eff_to))[0][0]
        spend = db.fetch_query(
            "SELECT SUM(spend) FROM meta_insights_performance_day "
            "WHERE artist_id = %s AND day_date BETWEEN %s AND %s",
            (1, eff_from, eff_to))[0][0]
    finally:
        db.close()

    assert (roi['effective_from'], roi['effective_to']) == (eff_from, eff_to), (
        "la fenêtre effective doit être rendue à l'appelant : sans elle, l'élargissement "
        "aux mois entiers est silencieux")
    assert roi['revenue_eur'] == (float(rev) if rev is not None else None)
    assert roi['meta_spend'] == (float(spend) if spend is not None else None)


# ── Absence, panne et mesure sont trois états distincts ─────────────────────

def test_an_absent_tenant_is_unknown_not_zero_and_not_a_failure() -> None:
    db = _live_db()
    if db is None:
        pytest.skip("pas de Postgres sur 5433")
    try:
        roi = get_roi_data(db, _ABSENT_TENANT, dt.date(2026, 1, 1), dt.date(2026, 9, 10))
    finally:
        db.close()
    assert roi['revenue_eur'] is None, "un locataire sans revenu n'a pas gagné 0 €"
    assert roi['meta_spend'] is None
    assert roi['profitable'] is None, "aucun verdict sans les deux côtés"
    assert roi['unreadable'] == [], "rien n'a échoué : c'est une absence, pas une panne"


def test_a_read_failure_is_named_and_produces_no_verdict() -> None:
    class _BrokenDB:
        def fetch_query(self, *_a, **_k):
            raise RuntimeError("connection lost")

    roi = get_roi_data.__wrapped__(_BrokenDB(), 1, dt.date(2026, 1, 1), dt.date(2026, 9, 10))
    assert set(roi['unreadable']) == {'revenue', 'spend'}
    assert roi['revenue_eur'] is None and roi['meta_spend'] is None
    assert roi['profitable'] is None, (
        "une base injoignable produisait `profitable=False` — un VERDICT métier tiré "
        "d'une panne")


def test_the_formatter_shows_a_dash_never_a_fabricated_amount() -> None:
    assert fmt_eur(None) == "—"
    assert fmt_eur(None, 0) == "—"
    assert fmt_eur(0.0) == "0.00 €", "un zéro MESURÉ reste un zéro"


# ── Le PDF payant n'imprime pas de verdict sur l'inconnu ────────────────────

@pytest.mark.parametrize("roi,why", [
    ({'unreadable': ['revenue'], 'revenue_eur': None, 'meta_spend': 12.0}, "panne de lecture"),
    ({'unreadable': [], 'revenue_eur': None, 'meta_spend': None}, "rien de mesuré"),
])
def test_the_pdf_prints_no_verdict_without_both_sides(roi, why) -> None:
    """C'est le document PAYANT : « ✅ Rentable » y est une affirmation contractuelle."""
    from src.dashboard.utils.pdf_exporter._renderers import _render_roi
    html = _render_roi(roi, dt.date(2026, 1, 1), dt.date(2026, 9, 10))
    # Les deux catalogues : le rendu résout en EN dans la suite, en FR à l'écran.
    for verdict in ("Rentable", "Profitable", "Déficitaire", "Deficit"):
        assert verdict not in html, f"verdict « {verdict} » imprimé sur {why}"
    assert "0,00 €" not in html and "0.00 €" not in html, (
        f"montant fabriqué imprimé sur {why}")


def test_the_pdf_still_states_a_verdict_when_both_sides_are_known() -> None:
    """Le correctif ne doit pas rendre le PDF muet sur un cas parfaitement mesuré."""
    from src.dashboard.utils.pdf_exporter._renderers import _render_roi
    html = _render_roi({'unreadable': [], 'revenue_eur': 100.0, 'meta_spend': 40.0},
                       dt.date(2026, 1, 1), dt.date(2026, 9, 10))
    assert "60.00" in html, "le net (100 − 40) doit être imprimé"
    assert ("Rentable" in html) or ("Profitable" in html), (
        "un cas parfaitement mesuré doit toujours porter son verdict")
