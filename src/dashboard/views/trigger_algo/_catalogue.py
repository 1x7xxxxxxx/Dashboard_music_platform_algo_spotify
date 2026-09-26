"""La trame du catalogue : où en est chaque titre, et ce qui lui manque.

Type: Sub
Uses: pandas, src.dashboard.utils.algo_knowledge (module pur)
Depends on: ml_song_predictions (lu par l'appelant, jamais ici)
Triggers: views/trigger_algo/_tab_catalogue.py
Persists in: nothing

Pourquoi ce module est PUR — et pourquoi ça compte ici
------------------------------------------------------
Il ne touche ni Streamlit ni la base : il reçoit des lignes et rend un DataFrame.
C'est ce qui permet de vérifier la règle de classement sur des valeurs plutôt que
sur un rendu, et c'est le motif que `_common/_lifecycle.py` applique déjà pour la
seule fabrique de figure du paquet.

Ce qui porte le classement, et pourquoi ce n'est PAS la probabilité
-------------------------------------------------------------------
Mesuré en production le 2026-09-22 sur les dix titres de l'artiste 1 :

    dw_probability    0,0695 → 0,0731     (0,36 point d'étendue)
    rr_probability    0,0654 → 0,0656     (0,02 point)
    radio_probability 0,1101 → 0,1175

La calibration Platt a un PLANCHER : un score brut nul rend 6,53 % (DW), 6,51 % (RR),
10,72 % (Radio). Les dix titres sont posés dessus. Leur « écart » de probabilité est
l'image, comprimée par la sigmoïde, d'un écart de score brut de 0,0007 sur RR.
Classer là-dessus, c'est classer du bruit — et le `Score /20` qu'on remplace le
faisait en pire, puisqu'il étirait ces fractions de point en min-max sur 20.

Le classement repose donc sur **l'avancement vers la porte la plus proche** :
`nearest_gate` (dans `algo_knowledge`) choisit, parmi DW/RR/Radio, l'algo dont le
premier levier de TITRE est le moins loin de sa cible, et rend `current / target`.
Quatre propriétés qu'aucune probabilité n'a ici : il est mesuré (jamais imputé), il
est actionnable, il s'exprime dans l'unité du geste — « il manque 141 saves » — et
il **bouge quand l'artiste agit**.

⚠️ Seuls les leviers de TITRE entrent dans le classement. Les leviers d'artiste
(followers, cadence, catalogue, compteur Radio) sont identiques sur toutes les
chansons : les inclure donnerait le même rang à tout le monde. Voir `LEVER_SCOPE`.
"""
from __future__ import annotations

import json

import pandas as pd

from src.dashboard.utils.algo_knowledge import nearest_gate, split_coach_actions
from src.dashboard.utils.algo_preview_data import BRUT_NEGLIGEABLE, sur_le_plancher  # noqa: F401,E402 — moved (R193)

#: Les colonnes de la trame, dans l'ordre d'affichage. La probabilité vient EN
#: DERNIER : elle est vraie, et inutile pour comparer deux titres (voir le module).
COLONNES = [
    "song", "days_since_release", "gate_algo", "gate_label", "gate_gap",
    "gate_unit", "avancement", "n_leviers", "saves_28d", "adds_28d",
    "streams_28d", "dw_probability", "rr_probability", "radio_probability",
]



def _feats(valeur) -> dict:
    """`features_json` en dict, quelle que soit la forme rendue par le pilote."""
    if isinstance(valeur, dict):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return json.loads(valeur)
        except (ValueError, TypeError):
            return {}
    return {}


def construire(lignes: list[dict]) -> pd.DataFrame:
    """La trame du catalogue, triée par ce qui porte réellement l'information.

    `lignes` : un dict par titre, avec au moins `song` et `features_json`. Les
    autres clés sont recopiées telles quelles quand elles existent.

    Tri : **avancement décroissant**, puis **leviers restants croissant**, puis
    **streams 28 j décroissant**. C'est la règle que `build_coach_actions` applique
    déjà À L'INTÉRIEUR d'un titre (le levier le plus proche d'abord), étendue au
    catalogue. Un titre sans porte — rien en zone malus, ou rien de mesuré — tombe
    en fin de liste avec un avancement absent, jamais un zéro : une absence de
    levier n'est pas un travail non fait.
    """
    out = []
    for ligne in lignes or []:
        feats = _feats(ligne.get("features_json"))
        porte = nearest_gate(feats)
        action = porte["action"] if porte else None
        _titre, artiste = (split_coach_actions(porte["algo"], feats)
                           if porte else ([], []))
        out.append({
            "song": ligne.get("song"),
            "days_since_release": ligne.get("days_since_release"),
            "gate_algo": porte["algo"] if porte else None,
            "gate_label": action["label"] if action else None,
            "gate_gap": action.get("gap") if action else None,
            "gate_unit": action.get("unit") if action else None,
            "avancement": porte["avancement"] if porte else None,
            "n_leviers": porte["n_leviers"] if porte else 0,
            "saves_28d": feats.get("SavesLast28Days_adj"),
            "adds_28d": feats.get("PlaylistAddsLast28Days_adj"),
            "streams_28d": ligne.get("streams_28d"),
            "dw_probability": ligne.get("dw_probability"),
            "rr_probability": ligne.get("rr_probability"),
            "radio_probability": ligne.get("radio_probability"),
            "_leviers_artiste": artiste,
        })
    if not out:
        return pd.DataFrame(columns=COLONNES)
    df = pd.DataFrame(out)
    # `na_position="last"` : un titre sans porte n'est pas un titre à 0 % — il
    # descend en fin de liste sans prétendre qu'on n'a rien fait pour lui.
    return df.sort_values(
        ["avancement", "n_leviers", "streams_28d"],
        ascending=[False, True, False], na_position="last",
    ).reset_index(drop=True)


def leviers_artiste(df: pd.DataFrame) -> list[dict]:
    """Les leviers valables pour TOUT le catalogue, dédoublonnés.

    Ils sont identiques sur chaque titre par construction ; les afficher une fois
    est exactement le « regrouper les panneaux » demandé, et c'est aussi ce qui
    empêche un conseil répété dix fois de passer pour dix conseils.
    """
    vus, out = set(), []
    for lot in df.get("_leviers_artiste", []):
        for a in lot or []:
            if a["feature"] not in vus:
                vus.add(a["feature"])
                out.append(a)
    return sorted(out, key=lambda a: a["urgency"])
