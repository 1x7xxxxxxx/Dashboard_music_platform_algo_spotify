"""Le point mort : quatre états, et la date qui faisait tomber la page.

Type: Test
Uses: pytest, pandas
Depends on: src/dashboard/utils/artist_cashflow.py
Persists in: nothing

Le défaut, trouvé par les données réelles au premier essai
-----------------------------------------------------------
L'artiste 1 est à **−2 839,43 €** et gagne **+0,48 €/mois**. Son point mort tombe
donc en **novembre 2521**, et `pandas.Timestamp` est un entier de nanosecondes qui
déborde après 2262 :

    OutOfBoundsDatetime: Out of bounds timestamp: 2521-11-01 00:00:00

La page entière tombait sur une exception — et pour un horizon parfaitement
légitime. C'est même l'artiste le PLUS LOIN du point mort qui a le plus besoin de
le lire : celui qui est déjà rentré dans ses frais n'a pas de question.

Classe : `a-computed-date-that-leaves-the-representable-range`. Elle ne se voit
jamais sur un jeu d'essai — il faut une pente presque plate et une dette réelle.

Ce que ce garde tient AUSSI
---------------------------
Les trois autres états. Un point mort qui rend toujours une date, même quand la
pente descend, est pire qu'une erreur : il promet une échéance à quelqu'un qui
s'éloigne de la sienne.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.dashboard.utils.artist_cashflow import (
    break_even, forward_rate, monthly_net, project,
)


def _flux(lignes) -> pd.DataFrame:
    """(année, mois, montant, direction) → la forme de `v_artist_monthly_cashflow`."""
    return pd.DataFrame([
        {'year': a, 'month': m, 'flux': 'revenu' if d > 0 else 'depense',
         'source': 'imusician' if d > 0 else 'meta_ads',
         'amount_eur': v, 'direction': d}
        for a, m, v, d in lignes])


# ── Le défaut qui a fait tomber la page ────────────────────────────────────
def test_a_break_even_beyond_the_year_2262_does_not_raise() -> None:
    """Le cas RÉEL de l'artiste 1, reproduit au chiffre près."""
    lignes = [(2023, 1, 3087.82, -1)] + [(2024, m, 0.48, 1) for m in range(1, 13)]
    m = monthly_net(_flux(lignes))
    pm = break_even(m)                       # ne doit pas lever
    assert pm['etat'] == 'atteint'
    assert pm['mois'] > 12 * 200, pm['mois']
    # ⚠️ EXIGER LA DATE, et pas seulement l'absence d'erreur.
    #
    # Le premier jet de ce test écrivait `pm['date'] is None or année > 2262`, et
    # il est resté VERT sur une mutation qui remettait le `Timestamp` pandas —
    # c'est-à-dire sur le défaut même qui a fait écrire ce fichier. La cause :
    # `OutOfBoundsDatetime` HÉRITE de `ValueError`, donc le `except` du module
    # l'attrape et rend `None`… que l'assertion acceptait.
    #
    # Un garde qui accepte les deux issues ne garde rien. `datetime.date` monte
    # jusqu'à l'an 9999 : au-delà de 2262 une date DOIT sortir.
    assert pm['date'] is not None, (
        "aucune date rendue : le calcul repasse par un `Timestamp` pandas, qui "
        "déborde après 2262 et se fait avaler par le `except ValueError`")
    assert pm['date'].year > 2262, pm['date']


def test_beyond_the_year_9999_the_month_count_survives_the_date() -> None:
    """Le seul cas où `None` est la bonne réponse — et il reste chiffré.

    `datetime.date` s'arrête à l'an 9999. Au-delà, on rend le NOMBRE DE MOIS sans
    date : le compte reste juste, seule l'étiquette manque. Rendre `etat: jamais`
    serait faux — le point mort existe, il est juste au-delà du calendrier.
    """
    lignes = [(2024, 1, 1_000_000.0, -1)] + [(2025, m, 0.01, 1) for m in range(1, 13)]
    pm = break_even(monthly_net(_flux(lignes)))
    assert pm['etat'] == 'atteint', pm
    assert pm['mois'] > 12 * 8000, pm['mois']
    assert pm['date'] is None, pm['date']


def test_a_date_past_pandas_range_is_a_real_date() -> None:
    """Et pas seulement « pas de crash » : la date doit être JUSTE.

    NON-VACUITÉ : un `except` qui avale tout passerait le test précédent en
    rendant toujours None. Ici on exige le bon millésime.
    """
    # ⚠️ La dépense est HORS de la fenêtre de rythme (12 mois), sinon elle tire la
    # pente en négatif et l'état devient « jamais » — c'est ce que le premier jet
    # de ce décor faisait, et il prouvait autre chose que ce qu'il annonçait.
    lignes = ([(2019, 1, 1200.0, -1)]
              + [(y, m, 1.0, 1) for y in (2019, 2020) for m in range(2, 13)])
    pm = break_even(monthly_net(_flux(lignes)))
    assert pm['etat'] == 'atteint', pm
    assert pm['date'] is not None, "une date de 2119 tient largement dans `date`"
    assert pm['date'].year > 2100, pm['date']


# ── Les quatre états ───────────────────────────────────────────────────────
def test_a_negative_rate_never_invents_a_date() -> None:
    """Qui s'éloigne de son point mort n'a pas d'échéance. En promettre une ment."""
    lignes = [(2024, m, 100.0, -1) for m in range(1, 13)]
    pm = break_even(monthly_net(_flux(lignes)))
    assert pm['etat'] == 'jamais', pm
    assert pm['mois'] is None and pm['date'] is None


def test_a_positive_cumulative_says_it_is_done() -> None:
    lignes = [(2024, m, 50.0, 1) for m in range(1, 13)]
    pm = break_even(monthly_net(_flux(lignes)))
    assert pm['etat'] == 'deja' and pm['mois'] == 0


def test_no_history_says_unknown() -> None:
    pm = break_even(pd.DataFrame())
    assert pm['etat'] == 'inconnu'


# ── Un mois sans ligne est un mois à ZÉRO, pas un mois absent ──────────────
def test_a_month_with_no_line_is_a_month_at_zero() -> None:
    """Sauter un mois vide fausse la pente lue sur l'axe des dates.

    Janvier et décembre seulement : la série doit porter DOUZE mois, dont dix à
    zéro. Sans réindexation, `forward_rate` moyennerait sur deux points et
    rendrait un rythme vingt fois trop optimiste.
    """
    m = monthly_net(_flux([(2024, 1, 120.0, 1), (2024, 12, 120.0, 1)]))
    assert len(m) == 12, m[['date', 'net']].to_string(index=False)
    assert float(m['net'].sum()) == pytest.approx(240.0)
    assert float(m[m['net'] == 0].shape[0]) == 10
    # 240 / 12 = 20, et surtout PAS 240 / 2 = 120.
    assert forward_rate(m, 12) == pytest.approx(20.0)


def test_the_rate_reads_the_recent_window_not_all_history() -> None:
    """« À ce stade » veut dire le rythme d'aujourd'hui, pas la moyenne de la vie.

    Une campagne publicitaire arrêtée il y a deux ans pèserait éternellement sur
    la pente. Sur l'artiste 1 : −59 €/mois sur tout l'historique contre +0,48 €
    sur douze mois. Les deux sont vrais ; un seul répond à la question posée.
    """
    lignes = ([(2023, m, 600.0, -1) for m in range(1, 13)]
              + [(2024, m, 10.0, 1) for m in range(1, 13)])
    m = monthly_net(_flux(lignes))
    assert forward_rate(m, 12) == pytest.approx(10.0)
    assert forward_rate(m, 24) < 0, "la fenêtre longue doit bien voir la campagne"


# ── La projection et le point mort sortent du MÊME calcul ──────────────────
def test_the_projection_and_the_break_even_agree() -> None:
    """Deux pentes dans un écran, c'est chacune qui dément l'autre.

    La page portait exactement ça avant le 2026-09-21 : une courbe issue d'une
    régression sur tout l'historique, sous une phrase datant le point mort sur
    une autre base.
    """
    # Même précaution : la dépense est antérieure à la fenêtre de rythme.
    lignes = [(2023, 1, 600.0, -1)] + [(2024, m, 20.0, 1) for m in range(1, 13)]
    m = monthly_net(_flux(lignes))
    pm = break_even(m)
    assert pm['etat'] == 'atteint', pm
    proj = project(m, horizon=max(1, min(pm['mois'], 36)))
    # Le point de la projection au rang `mois` doit valoir zéro, au centime près.
    if pm['mois'] <= 36:
        atteint = float(proj['cumul'].iloc[pm['mois'] - 1])
        assert atteint >= -0.01, (
            f"la projection vaut {atteint:.2f} € au mois du point mort : les deux "
            "ne sortent pas du même calcul")


# ── L'ESPÉRANCE, et le facteur quatorze que le premier jet a manqué ─────────
class _FauxDB:
    """Une base minuscule : `fetch_df` rend ce qu'on lui a posé, par mot-clé."""

    def __init__(self, tables: dict[str, pd.DataFrame]):
        self._t = tables

    def fetch_df(self, sql, params=None):
        for motif, df in self._t.items():
            if motif in sql:
                return df
        return pd.DataFrame()


def test_the_expectation_is_the_value_times_the_calibrated_chance() -> None:
    """Sans la probabilité, la figure se lit « 23 € par titre ». Elle ne l'est pas.

    Mesuré sur l'artiste 1 le 2026-09-21 : Discover Weekly vaut **23,38 €** dans
    la cohorte, et ses onze titres n'en espèrent que **18,27 €** au total, parce
    qu'aucun ne dépasse 7,4 % de chance.
    """
    from src.dashboard.utils.artist_cashflow import trigger_expectation

    valeurs = pd.DataFrame([
        {'algo': 'DW', 'nom': 'Discover Weekly', 'streams_med': 20000.0,
         'valeur_eur': 100.0, 'n': 104},
    ])
    db = _FauxDB({"ml_song_predictions": pd.DataFrame([
        {'song': 'a', 'prediction_date': '2026-06-12', 'dw_probability': 0.10,
         'rr_probability': None, 'radio_probability': None},
        {'song': 'b', 'prediction_date': '2026-06-12', 'dw_probability': 0.20,
         'rr_probability': None, 'radio_probability': None},
    ])})
    e = trigger_expectation(db, 1, valeurs)
    assert e is not None
    # (0,10 + 0,20) × 100 € = 30 €, et surtout PAS 2 × 100 = 200.
    assert e['total'] == pytest.approx(30.0), e['total']
    ligne = e['par_algo'].iloc[0]
    assert ligne['proba_moyenne'] == pytest.approx(0.15)
    assert ligne['valeur_eur'] == pytest.approx(100.0), (
        "la valeur de cohorte doit rester lisible À CÔTÉ de l'espérance : la "
        "figure porte les deux barres, et c'est leur écart qui informe")


def test_a_track_without_a_probability_is_not_counted_as_zero_nor_as_one() -> None:
    """Une probabilité absente (`NULL`) se retire du compte, elle ne vaut rien.

    Un modèle qui échoue à scorer un titre écrit `None`. Le compter à 0 ferait
    baisser l'espérance d'un titre qu'on n'a pas jugé ; le compter à 1 la ferait
    exploser. Il sort du dénominateur.
    """
    from src.dashboard.utils.artist_cashflow import trigger_expectation

    valeurs = pd.DataFrame([{'algo': 'DW', 'nom': 'DW', 'streams_med': 1.0,
                             'valeur_eur': 100.0, 'n': 10}])
    db = _FauxDB({"ml_song_predictions": pd.DataFrame([
        {'song': 'a', 'prediction_date': '2026-06-12', 'dw_probability': 0.50,
         'rr_probability': None, 'radio_probability': None},
        {'song': 'b', 'prediction_date': '2026-06-12', 'dw_probability': None,
         'rr_probability': None, 'radio_probability': None},
    ])})
    e = trigger_expectation(db, 1, valeurs)
    assert e['total'] == pytest.approx(50.0)
    assert int(e['par_algo'].iloc[0]['titres']) == 1, (
        "le titre non scoré doit sortir du compte, pas y entrer à zéro")


def test_no_prediction_yields_no_expectation() -> None:
    """Rien à multiplier ⇒ pas de chiffre. La vue affiche alors la valeur seule."""
    from src.dashboard.utils.artist_cashflow import trigger_expectation

    valeurs = pd.DataFrame([{'algo': 'DW', 'nom': 'DW', 'streams_med': 1.0,
                             'valeur_eur': 100.0, 'n': 10}])
    assert trigger_expectation(_FauxDB({}), 1, valeurs) is None
