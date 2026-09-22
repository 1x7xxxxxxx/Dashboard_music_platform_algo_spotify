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

# ── LES DEUX BORNES DE FIABILITÉ D'UNE LIGNE, descendues ici le 2026-09-22 ───
#
# Elles vivaient dans `views/trigger_algo/_reglages.py`, et un module partagé
# (`utils/meta_axes.py`) en a eu besoin. `test_a_shared_path_does_not_drag_a_view_
# behind_it` a refusé l'import, et il avait raison avec un chiffre : lire huit
# libellés dans une vue depuis un utilitaire a coûté **1 073 ms au premier rendu de
# l'accueil** le 2026-09-12, pour un budget de page de 287 ms.
#
# Le remède est celui que ce test nomme : faire DESCENDRE la donnée, jamais faire
# monter l'utilitaire ni recopier la valeur. `utils/csv_platforms.py` est le
# précédent. `_reglages` les lit désormais ici.
#
# Ce ne sont pas des seuils de modèle : ce sont « les bornes en dessous desquelles le
# classement de CE catalogue s'inverse d'une annonce à l'autre ». Mesuré sur les
# campagnes de l'artiste 1 : les effectifs vont de 1 à 84 annonces et les dépenses de
# 13 € à 5 198 €. Sans plancher, `MESSAGE_PAGE` à 1,45 €/clic — UNE annonce — et
# `VIDEO_VIEWS` à 2,72 € — deux campagnes, 30 € — feraient conseiller « ne fais
# jamais de vidéo ».
#
# ⚠️ Et le 2026-09-22, le plancher de dépense a intercepté un chiffre qui allait
# s'afficher : « meilleur pays = États-Unis à 0,0528 € » — sur **31 € dépensés**.
# Avec lui, le meilleur devient l'Allemagne à 0,1016 € et le facteur passe de ×3,7
# à ×1,92. Le plancher n'affine pas le classement, il l'INVERSE.
MIN_ADS = 5
MIN_DEPENSE = 100.0


def confidence_factor(resultats, k: float = K_DEFAUT) -> float:
    """`n / (n + k)` — le rétrécissement bayésien le plus simple qui soit.

    Il vaut 0,05 à 15 résultats, 0,5 à `k`, 0,95 à 19·`k`. Une créative minuscule
    au coût flatteur voit donc son score divisé par vingt, sans être exclue : elle
    reste visible, elle cesse d'être un conseil.
    """
    if resultats is None or pd.isna(resultats) or float(resultats) <= 0:
        return 0.0
    return float(resultats) / (float(resultats) + max(k, 1.0))
