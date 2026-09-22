"""Les réglages de campagne qui changent quelque chose — mesurés, pas supposés.

Type: Sub
Uses: pandas
Depends on: meta_campaigns, meta_ads, meta_insights (lus par l'appelant)
Triggers: views/trigger_algo/_tab_budget_roi.py
Persists in: nothing

Pourquoi un module à part, et pur
----------------------------------
Il ne touche ni Streamlit ni la base : il reçoit des lignes et rend un classement.
C'est ce qui permet de vérifier la règle de comparaison sur des valeurs, et c'est
le motif qu'impose le traceur de couverture or — une figure se dessine dans la
fonction qui a lu la base, jamais dans une fabrique appelée d'ailleurs.

Les quatre axes, et ce qu'ils valent VRAIMENT (production, 2026-09-22)
-----------------------------------------------------------------------

**Appel à l'action** — 132 annonces, 6 169 € :

    LISTEN_NOW     84 ads   5 198 €   0,1177 €/clic   CTR 1,33 %
    (aucun)        25 ads     897 €   0,2117 €/clic   CTR 1,58 %
    LEARN_MORE     22 ads      60 €   0,2215 €/clic   CTR 1,86 %
    MESSAGE_PAGE    1 ad       13 €   1,4489 €/clic   CTR 0,82 %

**Objectif de campagne** — 22 campagnes :

    OUTCOME_ENGAGEMENT   17 camp.   6 078 €   0,1256 €/clic
    CONVERSIONS           3 camp.      61 €   0,2279 €/clic
    VIDEO_VIEWS           2 camp.      30 €   2,7164 €/clic

**Créative (titre)** — facteur **3** entre la meilleure et la pire, et une créative
SANS titre coûte 2,8 fois la meilleure.

⚠️ **CE QUI REND CES CHIFFRES DANGEREUX, ET CE QUE LE MODULE FAIT CONTRE**
Les effectifs vont de **1 annonce à 84**, et les dépenses de **13 € à 5 198 €**.
`MESSAGE_PAGE` à 1,45 €/clic est une seule annonce ; `VIDEO_VIEWS` à 2,72 €/clic
sont deux campagnes et trente euros. Classer ces lignes sans leur effectif
produirait un conseil — « ne fais jamais de vidéo » — que la donnée ne porte pas.

Chaque ligne rend donc `ads`, `depense` et un drapeau `fiable`, et la vue refuse de
recommander sous le plancher. C'est la même discipline que R147 sur les cohortes
d'essai : un taux sur une population trop petite n'est pas un résultat.
"""
from __future__ import annotations

import pandas as pd

#: Sous ces deux bornes, une ligne est affichée mais jamais présentée comme un
#: enseignement. Elles ne sont pas des seuils du modèle : ce sont les bornes en
#: dessous desquelles le classement de CE catalogue s'inverse d'une annonce à
#: l'autre — `MESSAGE_PAGE` (1 annonce, 13 €) en est l'exemple.
MIN_ADS = 5
MIN_DEPENSE = 100.0


def classer(lignes: list[dict], axe: str) -> pd.DataFrame:
    """Le classement d'un axe de réglage, du moins cher au plus cher par clic.

    `lignes` : des dicts portant `valeur`, `ads`, `depense`, `clics`, `impressions`.

    Rend les colonnes `valeur, ads, depense, cpc, ctr, fiable, part_depense`, triées
    par `cpc` croissant — les non fiables **en fin de liste**, quel que soit leur
    coût. Une ligne à une annonce qui sort en tête du classement serait lue comme
    « voilà ce qu'il faut faire », ce qu'un seul relevé ne peut pas dire.
    """
    out = []
    for r in lignes or []:
        depense = float(r.get("depense") or 0)
        clics = float(r.get("clics") or 0)
        impressions = float(r.get("impressions") or 0)
        ads = int(r.get("ads") or 0)
        out.append({
            "axe": axe,
            "valeur": r.get("valeur") or "(non renseigné)",
            "ads": ads,
            "depense": depense,
            "cpc": (depense / clics) if clics > 0 else None,
            "ctr": (clics / impressions * 100) if impressions > 0 else None,
            "fiable": ads >= MIN_ADS and depense >= MIN_DEPENSE,
        })
    if not out:
        return pd.DataFrame(columns=["axe", "valeur", "ads", "depense", "cpc",
                                     "ctr", "fiable", "part_depense"])
    df = pd.DataFrame(out)
    total = df["depense"].sum()
    df["part_depense"] = df["depense"] / total if total > 0 else 0.0
    # `fiable` d'abord, puis le coût : une ligne non fiable ne prend jamais la tête.
    return df.sort_values(["fiable", "cpc"], ascending=[False, True],
                          na_position="last").reset_index(drop=True)


def recommandation(df: pd.DataFrame) -> dict | None:
    """Le réglage à retenir sur cet axe, ou `None` si rien n'est comparable.

    Exige **deux** lignes fiables : un « meilleur » sans rival mesuré n'est pas un
    enseignement, c'est la seule chose qu'on ait essayée. Rend aussi l'écart, parce
    que c'est lui qui dit si le réglage mérite qu'on y touche.
    """
    fiables = df[df["fiable"] & df["cpc"].notna()] if not df.empty else df
    if fiables is None or len(fiables) < 2:
        return None
    meilleur, pire = fiables.iloc[0], fiables.iloc[-1]
    if not meilleur["cpc"] or not pire["cpc"]:
        return None
    return {
        "axe": meilleur["axe"],
        "retenir": meilleur["valeur"],
        "eviter": pire["valeur"],
        "cpc_min": float(meilleur["cpc"]),
        "cpc_max": float(pire["cpc"]),
        "facteur": float(pire["cpc"]) / float(meilleur["cpc"]),
        "sur_ads": int(meilleur["ads"]),
        "sur_depense": float(meilleur["depense"]),
    }


def budget_pour_streams(streams_manquants: float, cout_par_stream: float | None) -> float | None:
    """Ce que coûterait d'acheter ces écoutes, au coût observé — ou `None`.

    ⚠️ **Ce nombre porte une limite qu'il faut afficher AVEC lui.** `cout_par_stream`
    est agrégé sur toutes les campagnes et tous les titres de l'artiste : il ne dit
    pas ce que coûtent les écoutes de CE titre. L'attribution passerait par
    `campaign_track_mapping`, qui porte 19 correspondances, et la dépense Meta
    s'arrête au 2024-09-30 quand les écoutes vont jusqu'en 2026.

    On le rend quand même, parce qu'un ordre de grandeur aide à décider d'un budget
    — mais la vue doit écrire que c'en est un, et non un devis.
    """
    if not cout_par_stream or cout_par_stream <= 0 or streams_manquants is None:
        return None
    manque = float(streams_manquants)
    return manque * float(cout_par_stream) if manque > 0 else 0.0
