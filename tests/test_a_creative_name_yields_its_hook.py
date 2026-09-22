"""Le hook lu dans un nom de créative : les deux sens de l'erreur.

Type: Test
Uses: pytest
Depends on: src/dashboard/views/meta_creatives.py (_hook_family, _par_hook,
            _le_plus_sur)
Persists in: nothing

Pourquoi ce garde existe
------------------------
La page « Créatives Meta Ads » classe désormais les ACCROCHES, et Meta ne
connaît pas cette notion : le hook est lu dans le NOM que l'artiste donne à sa
créative. C'est donc un prédicat qui cherche une FORME D'ÉCRITURE pour parler
d'une PROPRIÉTÉ — exactement la classe
`a-sweep-predicate-that-matches-a-form-not-a-property`, et la règle transverse 20
impose de le muter dans les DEUX sens avant de publier le moindre nombre :

  · **faux positif** — un nom qui a la forme et n'est pas un hook ;
  · **faux négatif** — un hook écrit autrement que dans les exemples.

Les noms ci-dessous sont RÉELS : ils viennent de `v_meta_creative_daily`,
artiste 1, relevés le 2026-09-21.

L'entonnoir, sur ces mêmes données
----------------------------------
    56 créatives portant de la dépense
    12 dont le nom nomme un hook      → 1 500 € sur 3 088 (49 %)
    44 muettes                        → non classées, et la figure le DIT

La part non classée est affichée dans la légende de la figure. C'est le point :
un classement des hooks qui tairait la moitié de l'argent serait faux, et rien à
l'écran ne détromperait.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.dashboard.views.meta_creatives import (
    _hook_family, _le_plus_sur, _par_hook,
)


# ── Sens 1 : ce que le prédicat DOIT attraper (faux négatifs) ────────────────
# Chacun de ces noms est une orthographe réellement présente en base.
@pytest.mark.parametrize("nom,attendu", [
    ("Début Hook 1 I missed", "Hook 1"),
    ("Hook 2 début : You absolutely need to know this hardtechno release", "Hook 2"),
    ("Drop Hook 1 I missed", "Hook 1"),
    ("Sans hook début", "Sans hook"),
    ("1x7xxxxxxx - Sans hook - je ne parle pas très bien", "Sans hook"),
    # Orthographes voisines : le hook ne se nomme pas toujours pareil.
    ("HOOK 3 - version longue", "Hook 3"),
    ("hook4 test", "Hook 4"),
    ("Variante  Sans   Hook  ", "Sans hook"),
])
def test_a_named_hook_is_read(nom: str, attendu: str) -> None:
    assert _hook_family(nom) == attendu, (
        f"« {nom} » nomme {attendu} et le prédicat ne le voit pas. Un faux négatif "
        "ne fait pas rougir la figure : il retire silencieusement de la dépense du "
        "classement, et le pourcentage affiché ment d'autant.")


# ── Sens 2 : ce que le prédicat NE DOIT PAS attraper (faux positifs) ─────────
@pytest.mark.parametrize("nom", [
    "Début",
    "Drop",
    "Chorus - Kaiber Photo",
    "Publication : « New HardTechno release 🆕 »",
    "Dave Clark",
    "Test Warm up",
    None,
    "",
    # Le mot existe sans numéro NI négation : il ne désigne aucune variante.
    "Nouveau hook à tester",
])
def test_a_name_without_a_hook_yields_nothing(nom) -> None:
    assert _hook_family(nom) is None, (
        f"« {nom} » ne nomme aucune variante d'accroche et le prédicat en invente "
        "une. Un faux positif crée une famille fantôme, qui remonte au sommet du "
        "classement avec la dépense d'une créative qui n'a rien à y faire.")


def test_sans_hook_is_an_answer_not_an_absence() -> None:
    """« Sans hook » est une variante TOURNÉE EXPRÈS, pas un nom muet.

    La confondre avec l'absence coûterait la comparaison qui intéresse l'artiste :
    est-ce que mettre une accroche change quelque chose ?
    """
    assert _hook_family("Sans hook drop") == "Sans hook"
    assert _hook_family("Drop") is None


# ── Le CPR d'une famille se recalcule, il ne se moyenne pas ─────────────────
def test_a_family_cpr_is_recomputed_from_totals() -> None:
    """Moyenner des CPR donne à 10 € le même poids qu'à 800 €."""
    df = pd.DataFrame([
        {'creative_name': "Hook 1 a", 'total_spend': 900.0, 'total_results': 9000,
         'cpr': 0.10, 'avg_ctr': 1.0},
        {'creative_name': "Hook 1 b", 'total_spend': 10.0, 'total_results': 10,
         'cpr': 1.00, 'avg_ctr': 1.0},
    ])
    g = _par_hook(df)
    cpr = float(g.loc[g['hook'] == "Hook 1", 'cpr'].iloc[0])
    # Σdépense / Σrésultats = 910 / 9010 ≈ 0,101 — et surtout PAS (0,10+1,00)/2.
    assert cpr == pytest.approx(910 / 9010, rel=1e-6), cpr
    assert cpr < 0.2, (
        f"CPR de famille à {cpr:.3f} : c'est une moyenne de moyennes. Une créative "
        "à 10 € pèse alors autant qu'une à 900 €.")


# ── La demande explicite du propriétaire : « pas quand j'ai dépensé 10 € » ──
def test_a_tiny_spend_never_wins_on_a_lucky_cost() -> None:
    """Le couronnement est PONDÉRÉ. C'est la demande, et ses données la motivent.

    Mesuré sur l'artiste 1 le 2026-09-21 : « Sans hook » est au meilleur coût brut
    (0,104 €) sur **69 €** ; « Hook 1 » est à 0,113 € sur **846 €**. Sans
    pondération, la page conseillerait la première.
    """
    familles = pd.DataFrame([
        {'hook': "Sans hook", 'cpr': 0.104, 'total_spend': 68.94,  'total_results': 665},
        {'hook': "Hook 1",    'cpr': 0.113, 'total_spend': 845.61, 'total_results': 7490},
        {'hook': "Hook 2",    'cpr': 0.127, 'total_spend': 585.63, 'total_results': 4621},
    ])
    gagnant = _le_plus_sur(familles)
    assert gagnant is not None
    assert gagnant['hook'] == "Hook 1", (
        f"couronné : {gagnant['hook']}. Le meilleur coût BRUT est « Sans hook », "
        "jugé sur 69 € — un dixième de ce qui soutient Hook 1. Le score doit "
        "multiplier l'efficacité par la confiance `n/(n+300)`.")

    # NON-VACUITÉ : sans la pondération, c'est bien l'autre qui gagnerait.
    assert familles.loc[familles['cpr'].idxmin(), 'hook'] == "Sans hook"


def test_the_winner_is_none_when_nothing_converted() -> None:
    """Aucun résultat ⇒ aucun couronnement. Une carte vide vaut mieux qu'un faux."""
    vide = pd.DataFrame([
        {'hook': "Hook 1", 'cpr': float("nan"), 'total_spend': 40.0, 'total_results': 0},
    ])
    assert _le_plus_sur(vide) is None


# ── Le préfixe dynamique `meta_creatives.rank.` a une clé PAR panneau ───────
#
# `test_i18n_orphans` exempte ce préfixe de son balayage : une clé construite par
# f-string n'a pas de référence littérale à trouver. L'exemption ouvre donc un
# trou — un panneau ajouté sans traduction passerait —, et c'est ce test qui le
# bouche. Même forme que `credentials.resolve.` et `home.mode_`.
def test_the_ranking_names_every_panel_it_draws() -> None:
    from src.dashboard.utils.i18n_catalog.meta_creatives import EN
    from src.dashboard.views.meta_creatives import _RANG_PANNEAUX

    manquantes = [col for _lab, col, _f, _c, _b in _RANG_PANNEAUX
                  if f"meta_creatives.rank.{col}" not in EN]
    assert not manquantes, (
        f"panneau(x) du classement sans traduction : {manquantes}. Le préfixe "
        "`meta_creatives.rank.` est exempté du balayage des orphelines parce que "
        "les clés sont construites par f-string ; c'est ce test qui tient l'autre "
        "bout, et lui seul.")


def test_the_global_perf_names_every_panel_it_draws() -> None:
    """Même trou, même bouchon, pour « 🚀 Performance Globale ».

    Six `st.metric` y ont été remplacés par six cadres le 2026-09-21 — la somme de
    deux campagnes ne répondait à aucune question qu'on se pose en en sélectionnant
    deux. Les titres sont construits par f-string, donc exemptés du balayage des
    orphelines : c'est ici que l'oubli se voit.
    """
    from src.dashboard.utils.i18n_catalog.meta_ads_overview import EN
    from src.dashboard.views.meta_ads_overview import _PERF_PANNEAUX

    manquantes = [i for i in range(len(_PERF_PANNEAUX))
                  if f"meta_ads_overview.perf.{i}" not in EN]
    assert not manquantes, (
        f"cadre(s) de performance globale sans traduction : {manquantes}.")


# ── « À couper » désigne l'ARGENT PERDU, pas le pire ratio ──────────────────
def test_the_cut_card_points_at_the_money_not_the_ratio() -> None:
    """Le premier jet désignait une créative à 25 €. Mesuré, corrigé, gardé.

    La règle « pire CPR au-dessus de la dépense médiane » a rendu, sur les données
    réelles de l'artiste 1 (61 créatives, dépense médiane 25 €), une créative de
    25 €. Techniquement juste, sans intérêt : la couper ne libère rien.
    """
    from src.dashboard.views.meta_creatives import _a_couper

    # Coût d'ensemble = 1 204 / 501 ≈ 2,40 €.
    d = pd.DataFrame([
        # Ratio catastrophique, budget dérisoire : ~2 € perdus.
        {'creative_name': "miette",  'cpr': 4.00, 'total_spend': 4.0,    'total_results': 1},
        {'creative_name': "normale", 'cpr': 2.00, 'total_spend': 200.0,  'total_results': 100},
        # Ratio à peine mauvais, GROS budget : ~160 € perdus.
        {'creative_name': "gouffre", 'cpr': 2.50, 'total_spend': 1000.0, 'total_results': 400},
    ])
    pire = _a_couper(d)
    assert pire is not None
    assert pire['creative_name'] == "gouffre", (
        f"désignée : {pire['creative_name']}. « miette » a le pire RATIO et ne "
        "coûte que 2 € de trop ; « gouffre » n'est qu'à peine au-dessus du coût "
        "d'ensemble et en coûte cent fois plus. C'est le second geste qui rend "
        "de l'argent.")
    ref = 1204.0 / 501.0
    assert pire['surcout'] == pytest.approx(1000.0 * (1 - ref / 2.5))


def test_the_cut_reference_is_the_blended_cost_not_the_median() -> None:
    """La référence est pondérée par l'ARGENT, pas une voix par créative.

    Mesuré sur l'artiste 1 le 2026-09-21 : CPR médian **0,310 €** contre coût
    d'ensemble **0,130 €**. Une nuée de petits essais ratés tire le médian vers le
    haut et fait passer les grosses dépenses pour bonnes — tous les surcoûts
    tombaient alors sous 20 €, et le vrai (70 € sur une créative à 220 €) était
    enterré.
    """
    from src.dashboard.views.meta_creatives import _a_couper

    d = pd.DataFrame(
        # Vingt petits essais ratés à 1 € pièce : ils font le médian, pas le coût.
        [{'creative_name': f"essai {i}", 'cpr': 1.0, 'total_spend': 1.0,
          'total_results': 1} for i in range(20)]
        # Et la vraie dépense, juste au-dessus du coût d'ensemble.
        + [{'creative_name': "le gros", 'cpr': 0.12, 'total_spend': 600.0,
            'total_results': 5000}]
        + [{'creative_name': "l'efficace", 'cpr': 0.08, 'total_spend': 400.0,
            'total_results': 5000}]
    )
    pire = _a_couper(d)
    assert pire is not None
    assert pire['creative_name'] == "le gros", (
        f"désignée : {pire['creative_name']}. Avec le CPR MÉDIAN (1,00 €) pour "
        "référence, aucune des deux vraies dépenses n'est au-dessus et la carte "
        "désigne un essai à 1 €. La référence doit être Σdépense / Σrésultats.")
    assert pire['reference'] == pytest.approx(1020.0 / 10020.0)
    # NON-VACUITÉ DU DÉCOR : sans un écart net entre les deux références, ce test
    # passerait aussi avec le médian. L'écart mesuré en production vaut ×2,4.
    assert float(d['cpr'].median()) > 2 * pire['reference'], (
        "le décor ne reproduit plus l'écart qu'il prétend garder")


def test_nothing_to_cut_when_everything_is_at_the_median() -> None:
    """Pas de gaspillage ⇒ pas de carte. Une reco inventée se paie en confiance."""
    from src.dashboard.views.meta_creatives import _a_couper

    d = pd.DataFrame([
        {'creative_name': "a", 'cpr': 2.0, 'total_spend': 100.0, 'total_results': 50},
        {'creative_name': "b", 'cpr': 2.0, 'total_spend': 100.0, 'total_results': 50},
    ])
    assert _a_couper(d) is None
