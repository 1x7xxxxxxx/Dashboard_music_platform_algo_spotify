"""Lire un nombre d'une ligne SQL sans qu'une absence devienne un `NaN`.

Type: Utility
Uses: pandas
Depends on: rien
Persists in: nothing

Pourquoi ce module — TROUVÉ PAR UN TEST LE 2026-09-22
------------------------------------------------------

Le dépôt écrivait, en huit endroits, la forme suivante :

    float(pd.to_numeric(valeur, errors="coerce") or 0)

Le `or 0` a l'air de couvrir l'absence. **Il ne la couvre pas** : `pd.to_numeric`
rend `NaN` sur une valeur manquante, et **`NaN` est VRAI en Python**. Le `or` ne se
déclenche donc jamais, et c'est `NaN` qui sort.

Le cas qui l'a révélé : `SUM()` sur zéro ligne rend `NULL`. Un artiste sans aucun
relevé de ventes obtenait `{'eur_par_stream': nan}` au lieu de `None` — et le garde
juste en dessous, `if streams <= 0`, ne l'attrapait pas non plus, puisque
`nan <= 0` est faux. Le `NaN` traversait alors toutes les multiplications en
silence jusqu'à l'écran, où il s'affiche « nan € ».

Deux modes d'échec selon le site, tous deux mesurés :

  · `float(nan)` → la valeur se propage, **silencieusement**, et s'affiche ;
  · `int(nan)` → `ValueError: cannot convert float NaN to integer`, donc un
    **plantage** sur une ligne dont une colonne est nulle (`meta_creatives.py`).

Classe : `an-absence-that-becomes-a-nan-because-nan-is-truthy`.
"""
from __future__ import annotations

import math

import pandas as pd


def nombre(valeur, defaut: float = 0.0) -> float:
    """La valeur en flottant, ou `defaut` si elle est absente ou illisible.

    Contrairement à `float(pd.to_numeric(v, errors="coerce") or defaut)`, elle
    attrape bien le `NaN` — c'est tout l'objet du module.
    """
    converti = pd.to_numeric(valeur, errors="coerce")
    try:
        f = float(converti)
    except (TypeError, ValueError):
        return float(defaut)
    return float(defaut) if math.isnan(f) or math.isinf(f) else f


def entier(valeur, defaut: int = 0) -> int:
    """La valeur en entier, ou `defaut`. Ne lève jamais sur un `NaN`."""
    return int(nombre(valeur, defaut))


def mesure(valeur):
    """La valeur, ou **`None` quand elle n'a pas été mesurée**.

    À préférer à `nombre()` partout où zéro et « pas de relevé » ne veulent pas dire
    la même chose — c'est-à-dire presque partout dans ce dépôt : une absence rendue
    en zéro se dessine, et un zéro dessiné est un fait affirmé.
    """
    converti = pd.to_numeric(valeur, errors="coerce")
    try:
        f = float(converti)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f
