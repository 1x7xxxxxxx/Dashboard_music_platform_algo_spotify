"""Un rendu ne calcule pas DEUX FOIS la même matrice pour le même locataire.

Type: Utility
Uses: streamlit.testing (AppTest)
Triggers: pytest (nécessite Postgres)
Persists in: nothing

Error class `a-renderer-that-recomputes-what-its-caller-already-has`.

Mesuré le 2026-09-17 sur `views/onboarding_health.py`. `show()` calcule
`artist_readiness(db, aid)` pour composer l'en-tête de chaque artiste, puis appelle
`render_status_matrix(db, aid)` — qui la **recalcule**. Sur douze locataires actifs :

    artist_readiness    24×  →  12×          check_freshness  24×  →  12×
    requêtes du rendu  324   →  181                                  (−44 %)

Le défaut ne se voit pas à la lecture. Le calcul et le rendu sont à cinquante lignes
d'écart dans `show()`, et **un renderer qui recharge ses propres données est exactement
ce qu'on attend d'un renderer autonome** — c'est sa qualité, pas son défaut. Ce qui est
faux, c'est qu'un appelant qui a déjà la réponse n'ait aucun moyen de la passer.

La même forme a été trouvée le même jour dans `views/db_health.py` : `show()` appelait
`_load_weekly_activity()` puis `_load_cumulative()`, qui la rechargeait — 22 `fetch_df`
au lieu de 11, une par dataset.

## Pourquoi ce garde et pas un plafond de requêtes

Un plafond sur le NOMBRE de requêtes d'un rendu serait tentant — et il serait
**dépendant des données** : `onboarding_health` boucle sur les artistes ACTIFS, donc un
locataire de plus le ferait rougir sans qu'aucun code ait changé. Ce dépôt a une classe
pour ça (`a-threshold-written-on-instinct`) et une leçon : calibrer un seuil sur les
données réelles, ou ne pas l'écrire.

La question posée ici est **structurelle et invariante** : combien de fois la matrice
d'UN locataire est-elle calculée pendant UN rendu ? La réponse doit être 1, que le parc
compte deux artistes ou deux cents.

## Ce qu'il ne couvre pas

Les autres doublons de calcul d'un rendu — seul `artist_readiness` est compté ; les
autres pages qui appellent `render_status_matrix` (`home`, `onboarding`,
`platform_status`) n'en rendent qu'un seul locataire, donc le défaut n'y est pas
observable ; et le cas où la matrice serait calculée une fois mais par une requête
elle-même redondante.

Mutation record — 2026-09-17, vue rouge : `rows=matrix` retiré de l'appel dans
`onboarding_health.py` → 2 calculs par locataire, ce test nomme le compte ; remis, vert.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready

pytestmark = pytest.mark.skipif(
    not db_ready(),
    reason="compter les calculs d'un rendu demande le vrai chemin de rendu",
)


def _readiness_calls_during(view: str) -> tuple[int, int]:
    """(matrices calculées, locataires rendus) pour un rendu de `view`.

    R266 (e) : la page calcule désormais la flotte par `readiness_many`, et le calcul
    d'UNE matrice vit dans `_matrix` — la seule copie, par locataire ou en lot. On compte
    donc `_matrix` (combien de matrices), et les locataires par les deux entrées.
    """
    from streamlit.testing.v1 import AppTest

    import src.utils.artist_readiness as ar
    from tests.render_harness import SCRIPT
    import src.dashboard.views.onboarding_health as oh

    seen: list[int] = []
    built = [0]
    orig_one, orig_many, orig_matrix = ar.artist_readiness, ar.readiness_many, ar._matrix

    def one(db, artist_id, probe=None):
        seen.append(artist_id)
        return orig_one(db, artist_id, probe=probe)

    def many(db, artist_ids):
        seen.extend(int(a) for a in artist_ids)
        return orig_many(db, artist_ids)

    def matrix(*a, **k):
        built[0] += 1
        return orig_matrix(*a, **k)

    # `status_matrix` importe la fonction DANS son corps, donc il verra le patch ;
    # `onboarding_health`, lui, l'importe au niveau module — il faut patcher les deux.
    ar.artist_readiness, ar.readiness_many, ar._matrix = one, many, matrix
    saved = {n: getattr(oh, n) for n in ("artist_readiness", "readiness_many") if hasattr(oh, n)}
    for n in saved:
        setattr(oh, n, one if n == "artist_readiness" else many)
    try:
        at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view=view))
        at.run(timeout=180)
        if at.exception:
            raise AssertionError(
                f"le rendu de `{view}` a levé — le compte porterait sur du vide :\n"
                f"{at.exception[0].value}")
    finally:
        ar.artist_readiness, ar.readiness_many, ar._matrix = orig_one, orig_many, orig_matrix
        for n, v in saved.items():
            setattr(oh, n, v)
    return built[0], len(set(seen))


def test_the_counter_actually_counts() -> None:
    """Non-vacuité : un compte de zéro passerait toutes les assertions ci-dessous."""
    calls, tenants = _readiness_calls_during("onboarding_health")
    assert tenants >= 1, (
        "aucun locataire rendu — le patch n'attrape plus les appels, ou la page ne "
        "boucle plus sur les artistes actifs. Dans les deux cas ce garde est aveugle.")
    assert calls >= tenants


def test_onboarding_health_computes_each_matrix_once() -> None:
    calls, tenants = _readiness_calls_during("onboarding_health")
    assert calls == tenants, (
        f"{calls} matrices calculées pour {tenants} locataire(s) — la "
        f"matrice est recalculée {calls / tenants:.1f}× par artiste.\n\n"
        "`show()` la calcule pour l'en-tête, puis `render_status_matrix` la refait. "
        "Lui passer `rows=` : mesuré le 2026-09-17, 324 requêtes de rendu au lieu "
        "de 181. Le coût croît avec le PARC, pas avec la page.")
