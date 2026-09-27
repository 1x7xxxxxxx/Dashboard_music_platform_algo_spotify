"""Which creative to cut — the decision rule of the Creatives page, pure.

Type: Utility
Uses: pandas
Triggers: views/meta_creatives.py (_render_decision_banner)
Persists in: nothing

Moved out of `views/meta_creatives.py` on 2026-09-27 (R233): the view crossed its frozen
size ceiling (`tests/test_a_file_only_gets_shorter.py`), and a decision rule that a test
calls directly (`tests/test_a_creative_name_yields_its_hook.py`) belongs outside a view.
"""
from __future__ import annotations

import pandas as pd


def _a_couper(d: pd.DataFrame) -> pd.Series | None:
    """Celle qui a coûté le plus d'ARGENT EN TROP — mesuré contre le coût d'ensemble.

    ⚠️ Deux jets corrigés le 2026-09-21, et les deux erreurs sont instructives.

    **1. Le pire RATIO n'est pas le plus gros gaspillage.** La règle était « la
    pire CPR parmi celles au-dessus de la dépense médiane ». Sur les données
    réelles de l'artiste 1 — 61 créatives, dépense médiane **25 €** — elle
    désignait une créative de 25 €. Techniquement juste, et sans intérêt : la
    couper ne libère rien. La question devant cet écran n'est pas « laquelle a le
    pire ratio » mais « où part l'argent que je perds ». Ça se mesure :

        surcoût = dépense × (1 − CPR_référence / CPR)

    soit les euros payés EN PLUS de ce qu'auraient coûté les mêmes résultats au
    coût de référence.

    **2. La référence n'est pas le CPR MÉDIAN.** Le médian se prend sur les
    créatives, une voix chacune : une nuée de petits essais ratés le tire vers le
    haut et fait passer les grosses dépenses pour bonnes. Mesuré le même jour :
    médian **0,310 €** contre coût d'ensemble **0,130 €** — un facteur 2,4, qui
    plafonnait tous les surcoûts sous 20 € et enterrait le vrai.

    ⚠️ Correction du 2026-09-26 : ces **0,130 €** (reproduits : 0,1296 € =
    3 006,77 € / 23 206 résultats, 55 couples créative × campagne à objectif de
    conversion, artiste 1, spotify_etl_review) ont un dénominateur DOUBLÉ — le
    collecteur comptait l'évènement sortant d'Hypeddit sous deux action_type. Le coût
    par clic sortant à la maille campagne, mesuré le même jour, est **0,2627 €**
    (Σdépense / Σcustom_conversions, 196 jours). Le chiffre à la maille créative
    n'existe qu'après la re-collecte `full_history` (migration 138) ; les 220 € /
    0,19 € / 70 € ci-dessous sont du même régime doublé et restent à re-mesurer.

    La référence est donc le coût d'ENSEMBLE, `Σdépense / Σrésultats` : ce que
    l'artiste paie réellement en moyenne, pondéré par l'argent. Avec elle, la
    carte désigne « Chorus - Kaiber Photo » — 220 € dépensés à 0,19 €, soit **70 €
    au-dessus** de son propre coût d'ensemble — et 462 € au total dépassent la
    référence sur 3 088 €. C'est un constat qu'on peut aller vérifier.
    """
    d = d[d['cpr'].notna() & (d['cpr'] > 0) & (d['total_spend'] > 0)]
    if len(d) < 2:
        return None
    resultats = float(d['total_results'].sum())
    if resultats <= 0:
        return None
    reference = float(d['total_spend'].sum()) / resultats
    if reference <= 0:
        return None
    surcout = d['total_spend'] * (1 - reference / d['cpr'])
    if not (surcout > 0).any():
        return None
    pire = d.loc[surcout.idxmax()].copy()
    pire['surcout'] = float(surcout.max())
    pire['reference'] = reference
    return pire
