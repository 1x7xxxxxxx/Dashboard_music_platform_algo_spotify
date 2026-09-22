"""Le poids qu'on accorde à un coût mesuré sur peu de résultats.

Type: Utility
Uses: pandas
Depends on: nothing
Persists in: nothing

Extrait de `views/meta_cpr_optimizer.py` le 2026-09-21, parce qu'une SECONDE
surface en avait besoin le même jour : le classement des créatives. Le
propriétaire a formulé la demande deux fois, à deux endroits — « je ne veux pas
que ce soit le cas quand j'ai dépensé que 10 € » — et la réponse ne pouvait pas
vivre dans une vue et être recopiée dans l'autre.

Le défaut qu'il nomme est réel et mesuré sur ses propres données le 2026-09-21 :
la famille de créatives « Sans hook » sort au MEILLEUR coût par résultat
(0,104 €) devant « Hook 1 » (0,113 €) — sur **69 € dépensés contre 846 €**.
Couronner la première, c'est conseiller de tout miser sur un essai que rien ne
soutient.
"""
from __future__ import annotations

import pandas as pd

# 300 résultats pour peser la moitié. Le barème vient de `meta_cpr_optimizer`,
# où il a été calé sur la distribution réelle des campagnes de l'artiste 1.
K_DEFAUT = 300


def confidence_factor(resultats, k: float = K_DEFAUT) -> float:
    """`n / (n + k)` — le rétrécissement bayésien le plus simple qui soit.

    Il vaut 0,05 à 15 résultats, 0,5 à `k`, 0,95 à 19·`k`. Une créative minuscule
    au coût flatteur voit donc son score divisé par vingt, sans être exclue : elle
    reste visible, elle cesse d'être un conseil.
    """
    if resultats is None or pd.isna(resultats) or float(resultats) <= 0:
        return 0.0
    return float(resultats) / (float(resultats) + max(k, 1.0))
