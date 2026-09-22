"""Le Pareto d'un titre, et ce que chaque levier vaut en euros.

Type: Sub
Uses: src.dashboard.utils.algo_knowledge (pur), src.utils.ml_inference (modèle)
Depends on: ALGO_FEATURE_ZONES, local_sensitivity
Triggers: views/trigger_algo/_tab_titre.py
Persists in: nothing

Les trois nombres, et lequel compte
------------------------------------
    valeur(algo)     = médiane des écoutes d'un titre qui a déclenché × €/écoute
    espérance(algo)  = probabilité calibrée × valeur(algo)
    valeur du levier = Δprobabilité(actuel → cible) × valeur(algo)

**Le troisième est le seul qui répond à la question posée.** Les deux premiers
disent ce qu'une porte VAUT ; le troisième dit ce que le prochain geste RAPPORTE :
« passer de 24 à 165 saves fait passer ta chance DW de 7 % à 23 % — +16 points ×
37,49 €, soit +6,00 € d'espérance. »

Il n'existe qu'ici parce qu'il demande `ml_inference.local_sensitivity`, le seul
endroit du dépôt qui convertit un écart de levier en écart de probabilité. C'est une
dépendance lourde — 25 `predict_proba` par levier — d'où les deux bornes ci-dessous.

⚠️ CE QUI N'EST PAS CALCULÉ, ET POURQUOI
-----------------------------------------
**Le COÛT d'ouverture d'une porte.** `_tab_budget_roi` le chiffrait par
`coût_par_stream × seuil`, avec un coût par stream agrégé sur TOUTES les campagnes
et TOUS les titres de l'artiste. Ce n'est pas un coût par titre, et changer le
multiplicande n'y changerait rien : l'attribution passerait par
`campaign_track_mapping`, qui porte **19 correspondances**, et la dépense Meta
s'arrête au **2024-09-30** quand les écoutes vont jusqu'en 2026. Un euro par titre
sorti de là serait une fiction. La vue dit donc ce qu'une porte vaut, et énonce
qu'elle ne sait pas ce qu'elle coûte.
"""
from __future__ import annotations

from src.dashboard.utils.algo_knowledge import nearest_gate, split_coach_actions

#: Combien de leviers reçoivent leur valeur en euros. `local_sensitivity` fait 25
#: appels au modèle par levier ; trois suffisent à décider du prochain geste, et
#: c'est le prochain geste qu'on cherche.
LEVIERS_CHIFFRES = 3


def _colonne_modele(algo: str, feature_id: str) -> str | None:
    """Le nom que le MODÈLE donne à ce levier — ce n'est pas celui de la zone.

    ⚠️ Trouvé en exécutant, pas en relisant. `ALGO_FEATURE_ZONES` nomme un levier
    `SavesLast28Days` ; la colonne du modèle s'appelle `SavesLast28Days_adj`, et
    `StreamsLast7Days` devient `StreamsLast7Days_log`. `local_sensitivity` rejette
    silencieusement (`feature not in FEATURE_COLUMNS` → `None`) tout nom qui n'est
    pas le sien : passer l'identifiant de zone rendait donc **zéro euro sur tous
    les leviers**, sans le moindre message.

    La spec porte déjà la correspondance dans `json_key`. On la LIT au lieu d'en
    refaire une — une seconde table de noms divergerait au prochain renommage.
    """
    from src.dashboard.utils.algo_knowledge import ALGO_FEATURE_ZONES

    spec = ALGO_FEATURE_ZONES.get(algo, {}).get(feature_id) or {}
    return spec.get("json_key") or feature_id


def _delta_proba(algo: str, feature: str, feats: dict,
                 courant: float, cible: float) -> float | None:
    """Le gain de probabilité entre la valeur actuelle et la cible, ou `None`.

    L'interpolation se fait sur la courbe que `local_sensitivity` rend déjà — on ne
    refait pas de prédiction, on lit deux points de la même courbe. Non linéaire par
    construction (XGBoost) : c'est pourquoi la courbe est locale à CE titre et ne
    donne aucune règle générale du type « +10 saves = +1 point ».
    """
    try:
        from src.utils.ml_inference import local_sensitivity

        courbe = local_sensitivity(algo, feature, feats)
    except Exception:                                    # noqa: BLE001
        return None
    if not courbe or not courbe.get("x_human"):
        return None
    xs, ps = courbe["x_human"], courbe["probs"]

    def _lire(x: float) -> float | None:
        if x <= xs[0]:
            return ps[0]
        if x >= xs[-1]:
            return ps[-1]
        for i in range(1, len(xs)):
            if xs[i] >= x:
                largeur = xs[i] - xs[i - 1]
                if largeur <= 0:
                    return ps[i]
                part = (x - xs[i - 1]) / largeur
                return ps[i - 1] + part * (ps[i] - ps[i - 1])
        return ps[-1]

    a, b = _lire(float(courant)), _lire(float(cible))
    if a is None or b is None:
        return None
    return max(0.0, b - a)


def pareto(feats: dict, valeur_porte: float | None = None,
           chiffrer: int = LEVIERS_CHIFFRES) -> dict | None:
    """Le plan d'action du titre : la porte la plus proche et ses leviers, ordonnés.

    Rend `{'algo', 'leviers', 'artiste', 'smooth'}` ou `None` si rien n'est en zone
    malus. `leviers` est déjà trié par urgence croissante — le plus proche de sa
    cible d'abord, c'est-à-dire le moins d'effort pour le prochain pas.

    Chaque levier reçoit `delta_proba` et `valeur_eur` pour les `chiffrer` premiers ;
    au-delà, les deux valent `None` — une absence déclarée, jamais un zéro qui se
    lirait comme « ce levier ne rapporte rien ».

    ⚠️ Le levier « smooth » (vélocité trop haute) est SORTI de la liste. Il porte
    `urgency = -1.0` et sort donc toujours en tête, sans cible ni écart : rendu en
    ligne 1 d'un tableau, il donnerait une première ligne vide. Il revient dans la
    clé `smooth`, que la vue affiche en bandeau.
    """
    porte = nearest_gate(feats)
    if not porte:
        return None
    algo = porte["algo"]
    titre, artiste = split_coach_actions(algo, feats)
    smooth = next((a for a in titre if a.get("kind") == "smooth"), None)
    leviers = [dict(a) for a in titre if a.get("kind") != "smooth"]

    for rang, levier in enumerate(leviers):
        levier["delta_proba"] = None
        levier["valeur_eur"] = None
        if rang >= chiffrer or not levier.get("target"):
            continue
        colonne = _colonne_modele(algo, levier["feature"])
        d = _delta_proba(algo, colonne, feats,
                         levier["current"], levier["target"])
        levier["delta_proba"] = d
        if d is not None and valeur_porte:
            levier["valeur_eur"] = d * float(valeur_porte)

    return {"algo": algo, "leviers": leviers, "artiste": artiste, "smooth": smooth}
