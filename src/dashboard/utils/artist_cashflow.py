"""Tout l'argent d'un artiste, et la date à laquelle il rentre dans ses frais.

Type: Utility
Uses: pandas, numpy
Depends on: v_artist_monthly_cashflow, v_artist_monthly_costs (migration 133),
            imusician_sales_detail, algo_lifecycle_benchmark
Persists in: nothing

Pourquoi un module et pas du code dans la vue
---------------------------------------------
Le point mort est un CALCUL, pas un dessin. Écrit dans la vue, il ne serait
vérifiable qu'en rendant Streamlit ; ici il est une fonction pure qu'un test
interroge avec des chiffres choisis. Ce dépôt a déjà payé l'autre forme — des
règles de lecture enfouies dans un `show()` que rien n'atteignait.

Ce que ces fonctions refusent de faire
--------------------------------------
Rendre un point mort quand la pente ne va pas vers zéro. Un artiste à −2 839 €
qui gagne 2,20 € par mois rentrera dans ses frais dans **107 ans** : c'est le
nombre juste, et il s'affiche. Mais un artiste dont le net mensuel est NÉGATIF ne
rentrera jamais dans ses frais, et afficher une date lointaine plutôt que « ça ne
converge pas » serait un mensonge poli. La fonction rend alors `None` avec un
motif nommé.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils.safe_number import nombre
from src.utils.track_matching import canonical_song_sql
from dateutil.relativedelta import relativedelta

# La fenêtre sur laquelle on lit le rythme ACTUEL, en mois.
#
# ⚠️ Pas toute l'histoire. Sur l'artiste 1, la dépense publicitaire s'arrête en
# septembre 2024 : moyenner depuis 2023 rendrait un net mensuel de −59 € et un
# point mort qui n'arrive jamais, alors que les douze derniers mois rendent
# +2,20 €. Les deux nombres sont vrais ; celui qui répond à « à ce stade » est le
# second, parce que la question porte sur le rythme d'aujourd'hui.
FENETRE_RYTHME = 12


def monthly_net(cashflow: pd.DataFrame) -> pd.DataFrame:
    """La série mensuelle : entrées, sorties, net, cumul.

    Les mois SANS aucune ligne sont réintroduits à zéro. Sans ça, le cumul saute
    par-dessus un trou et la pente lue sur l'axe des dates est fausse — un mois
    sans mouvement est un mois à zéro, pas un mois qui n'existe pas.
    """
    vide = pd.DataFrame(columns=['date', 'revenus', 'depenses', 'net', 'cumul'])
    if cashflow is None or cashflow.empty:
        return vide
    d = cashflow.copy()
    for c in ('year', 'month'):
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['year', 'month'])
    if d.empty:
        return vide
    d['amount_eur'] = pd.to_numeric(d['amount_eur'], errors='coerce').fillna(0.0)
    d['date'] = pd.to_datetime(
        d['year'].astype(int).astype(str) + "-"
        + d['month'].astype(int).astype(str).str.zfill(2) + "-01")

    entre = d[d['direction'] > 0].groupby('date')['amount_eur'].sum()
    sort = d[d['direction'] < 0].groupby('date')['amount_eur'].sum()
    idx = pd.date_range(d['date'].min(), d['date'].max(), freq='MS')
    out = pd.DataFrame({'date': idx})
    out['revenus'] = out['date'].map(entre).fillna(0.0)
    out['depenses'] = out['date'].map(sort).fillna(0.0)
    out['net'] = out['revenus'] - out['depenses']
    out['cumul'] = out['net'].cumsum()
    return out


def forward_rate(monthly: pd.DataFrame, window: int = FENETRE_RYTHME) -> float:
    """Le net mensuel du rythme ACTUEL — moyenne des `window` derniers mois."""
    if monthly is None or monthly.empty:
        return 0.0
    return float(monthly['net'].tail(max(1, window)).mean())


def break_even(monthly: pd.DataFrame, window: int = FENETRE_RYTHME) -> dict:
    """Quand le cumul net repasse à zéro, au rythme des derniers mois.

    Rend toujours un dictionnaire avec `etat` :

      * `deja`     — le cumul est déjà positif ; l'artiste est rentré dans ses frais.
      * `atteint`  — une date et un nombre de mois.
      * `jamais`   — le net mensuel est nul ou négatif : aucune date n'existe, et
                     en inventer une lointaine serait un mensonge poli.
      * `inconnu`  — pas d'historique.

    ⚠️ `mois` peut valoir plusieurs centaines, et on l'affiche tel quel. Sur
    l'artiste 1 le 2026-09-21 : −2 839,43 € de cumul, +2,20 €/mois sur douze mois,
    soit **1 290 mois — 107 ans**. C'est le chiffre qui répond à la question posée
    (« la durée à ce stade pour être break-even »), et l'arrondir à « > 10 ans »
    retirerait ce qu'il a d'utile : il dit que la publicité ne sera pas remboursée
    par les royalties, jamais, et qu'il faut changer autre chose que la patience.
    """
    if monthly is None or monthly.empty:
        return {'etat': 'inconnu', 'cumul': 0.0, 'rythme': 0.0,
                'mois': None, 'date': None}
    cumul = float(monthly['cumul'].iloc[-1])
    rythme = forward_rate(monthly, window)
    base = {'cumul': cumul, 'rythme': rythme, 'fenetre': window}
    if cumul >= 0:
        return {**base, 'etat': 'deja', 'mois': 0,
                'date': monthly['date'].iloc[-1].date()}
    if rythme <= 0:
        return {**base, 'etat': 'jamais', 'mois': None, 'date': None}
    import math
    mois = int(math.ceil(-cumul / rythme))
    # ⚠️ LA DATE SE CALCULE EN `datetime.date`, JAMAIS EN `pandas.Timestamp`.
    #
    # Défaut trouvé sur les données réelles de l'artiste 1 le 2026-09-21, au
    # premier essai : le point mort tombe en **novembre 2521**, et un `Timestamp`
    # pandas est un entier de nanosecondes qui déborde après 2262 —
    # `OutOfBoundsDatetime: Out of bounds timestamp: 2521-11-01`. La page entière
    # tombait sur une exception, pour un horizon parfaitement légitime : c'est
    # justement l'artiste le plus loin du point mort qui a le plus besoin de le lire.
    #
    # `datetime.date` va jusqu'à l'an 9999. Au-delà — plus de 95 000 mois, soit un
    # rythme inférieur à trois centimes par mois sur cette dette — on rend le
    # NOMBRE DE MOIS sans date : le compte reste juste, seule la date manque.
    depart = monthly['date'].iloc[-1].date()
    try:
        arrivee = depart + relativedelta(months=mois)
    except (OverflowError, ValueError):
        arrivee = None
    return {**base, 'etat': 'atteint', 'mois': mois, 'date': arrivee}


def project(monthly: pd.DataFrame, horizon: int, window: int = FENETRE_RYTHME
            ) -> pd.DataFrame:
    """Le cumul prolongé au rythme actuel — la même pente que le point mort.

    ⚠️ La projection et le point mort DOIVENT sortir du même calcul. Ce dépôt a
    mesuré ce que coûte l'écart : une figure qui monte selon une régression sur
    tout l'historique, sous une phrase qui date le point mort sur les douze
    derniers mois, affirme deux choses incompatibles dans le même écran.
    """
    if monthly is None or monthly.empty or horizon <= 0:
        return pd.DataFrame(columns=['date', 'cumul'])
    rythme = forward_rate(monthly, window)
    depart = monthly['date'].iloc[-1]
    cumul = float(monthly['cumul'].iloc[-1])
    lignes = [{'date': depart + relativedelta(months=i), 'cumul': cumul + rythme * i}
              for i in range(1, horizon + 1)]
    return pd.DataFrame(lignes)


# ── Ce qu'une écoute rapporte VRAIMENT, mesuré et non supposé ───────────────
_Q_TAUX = """
SELECT SUM(quantity)::numeric   AS streams,
       SUM(revenue_eur)::numeric AS revenus
FROM imusician_sales_detail
WHERE artist_id = %s
"""


def stream_rate(db, artist_id: int) -> dict | None:
    """€ par écoute, mesuré sur les ventes du distributeur.

    Mesuré sur l'artiste 1 le 2026-09-21 : 163 443 écoutes pour 211,87 € →
    **0,001296 €/écoute**. Ce n'est pas un taux de barème, c'est le sien : le taux
    réel dépend du pays, de la plateforme et du type d'abonnement de l'auditeur,
    et il varie du simple au centuple d'un pays à l'autre.

    ⚠️ Ce taux ne couvre QUE le distributeur. La SACEM paie en plus, sur une
    assiette qui n'est pas la même — l'ajouter au taux ferait compter deux fois ce
    qui n'est pas comparable.
    """
    try:
        df = db.fetch_df(_Q_TAUX, (artist_id,))
    except Exception:
        return None
    if df is None or df.empty:
        return None
    streams = nombre(df['streams'].iloc[0])
    revenus = nombre(df['revenus'].iloc[0])
    if streams <= 0 or revenus <= 0:
        return None
    return {'eur_par_stream': revenus / streams,
            'streams': streams, 'revenus': revenus}


# Le taux d'UN titre. La normalisation est appliquée DES DEUX CÔTÉS de l'égalité :
# `song` vient de `s4a_song_timeline`, dérivé d'un nom de fichier où Spotify for
# Artists remplace `< > : " / \ | ? *` par `_`, tandis que `track_title` vient du
# CSV du distributeur et porte les vrais caractères. Mesuré en production le
# 2026-09-22 : **sans normalisation, 1 titre sur 11 se rattache ; avec, 4 sur 11**
# — la jointure des trois autres était muette, et leur repli sur le taux
# d'artiste passait pour une absence de relevé. Cas d'école : « Qui a bu le
# crachoir du saloon ? » côté distributeur contre « … saloon _ » côté S4A.
_Q_TAUX_TITRE = f"""
SELECT SUM(quantity)::numeric    AS streams,
       SUM(revenue_eur)::numeric AS revenus
FROM imusician_sales_detail
WHERE artist_id = %s
  AND {canonical_song_sql('track_title')} = {canonical_song_sql('%s')}
"""


def track_stream_rate(db, artist_id: int, song: str) -> dict | None:
    """€ par écoute pour CE titre, avec repli explicite sur le taux de l'artiste.

    Mesuré le 2026-09-22 : le taux varie de **0,001058 à 0,002484 €/écoute** selon
    le titre, pour une moyenne d'artiste à 0,001819 sur Spotify. Un facteur 2,3 entre
    le meilleur et le pire — appliquer le taux moyen à tous les titres écraserait
    précisément l'écart qu'on cherche à montrer.

    Rend `{'eur_par_stream', 'streams', 'revenus', 'source'}` où `source` vaut
    `'track'` ou `'artist'`, **ou `None`** quand rien n'est mesurable.

    ⚠️ `source` n'est pas décoratif : l'écran DOIT dire lequel des deux taux il
    affiche. Un titre neuf hérite du taux d'artiste, et présenter cet héritage comme
    une mesure du titre serait une valeur inventée portant le nom d'un relevé.
    """
    try:
        df = db.fetch_df(_Q_TAUX_TITRE, (artist_id, song))
    except Exception:
        return None
    if df is not None and not df.empty:
        streams = nombre(df['streams'].iloc[0])
        revenus = nombre(df['revenus'].iloc[0])
        if streams > 0 and revenus > 0:
            return {'eur_par_stream': revenus / streams, 'streams': streams,
                    'revenus': revenus, 'source': 'track'}
    repli = stream_rate(db, artist_id)
    return {**repli, 'source': 'artist'} if repli else None


_Q_BENCH = """
SELECT algorithm,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_stream_median) AS streams_med,
       SUM(sample_count) AS n
FROM algo_lifecycle_benchmark
WHERE dataset_version = 'v2' AND total_stream_median IS NOT NULL
GROUP BY algorithm
"""

# L'ordre d'affichage, et le nom que l'artiste reconnaît.
ALGOS = [("DW", "Discover Weekly"), ("RR", "Release Radar"), ("RADIO", "Radio")]


def trigger_value(db, eur_par_stream: float) -> pd.DataFrame:
    """Ce que VAUT un titre qui déclenche chaque algorithme, en euros.

    ⚠️ CE N'EST PAS LE GAIN DU DÉCLENCHEMENT, et la vue doit le dire là où elle
    l'affiche. `total_stream_median` est la médiane des écoutes TOTALES des titres
    de la cohorte qui ont déclenché ; la cohorte ne contient aucun témoin — aucun
    titre comparable qui n'aurait pas déclenché. On ne peut donc pas en tirer un
    effet causal, seulement un ORDRE DE GRANDEUR : voilà où arrivent les titres qui
    y arrivent.

    Le contraste que la donnée supporte, lui, est la comparaison avec les propres
    titres de l'artiste — c'est `own_median_streams`, et la vue l'affiche à côté.

    Cohortes v2, mesurées le 2026-09-21 : DW n=104, RADIO n=239, RR n=100.
    """
    try:
        df = db.fetch_df(_Q_BENCH)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    par_algo = {r['algorithm']: r for _, r in df.iterrows()}
    lignes = []
    for code, nom in ALGOS:
        r = par_algo.get(code)
        if r is None:
            continue
        streams = nombre(r['streams_med'])
        if streams <= 0:
            continue
        lignes.append({'algo': code, 'nom': nom, 'streams_med': streams,
                       'valeur_eur': streams * float(eur_par_stream),
                       'n': int(r['n'] or 0)})
    return pd.DataFrame(lignes)


# ── L'ESPÉRANCE : la valeur d'un déclenchement × la chance de l'obtenir ─────
#
# C'est la seconde moitié de la demande du 2026-09-21 — « proba de trigger algos
# pour les streams que ça va nous rapporter ». Sans la probabilité, la figure dit
# ce qu'un déclenchement VAUT ; avec elle, elle dit ce qu'on peut en ATTENDRE.
#
# ⚠️ Multiplier une probabilité par une valeur ne se fait qu'avec une probabilité
# CALIBRÉE — sinon le produit n'a pas d'unité. Celles-ci le sont : calibration de
# Platt ajustée sur des prédictions hors-échantillon en validation croisée par
# groupe (v3), et `ALGO_CALIBRATION_BANDS` porte la réussite OBSERVÉE par bande.
# Les titres de l'artiste 1 tombent tous dans 0,0–0,2, dont la bande dit
# « réussite observée ~7 %, n=384 ».
_Q_PROBAS = """
SELECT DISTINCT ON (song)
       song, prediction_date,
       dw_probability, rr_probability, radio_probability
FROM ml_song_predictions
WHERE artist_id = %s AND song NOT ILIKE %s
ORDER BY song, prediction_date DESC
"""

_COL_PROBA = {"DW": "dw_probability", "RR": "rr_probability",
              "RADIO": "radio_probability"}


def trigger_expectation(db, artist_id: int, valeurs: pd.DataFrame) -> dict | None:
    """Ce que le catalogue peut espérer, algorithme par algorithme.

    Rend `{'par_algo': DataFrame, 'titres': int, 'date': date, 'total': float}`,
    ou `None` s'il n'y a aucune prédiction.

    Le total additionne, sur tous les titres et tous les algorithmes, la
    probabilité du titre multipliée par la valeur médiane de la cohorte. C'est une
    ESPÉRANCE, pas une promesse : la moitié des tirages tombe en dessous.
    """
    try:
        df = db.fetch_df(_Q_PROBAS, (artist_id, '%1x7xxxxxxx%'))
    except Exception:
        return None
    if df is None or df.empty or valeurs is None or valeurs.empty:
        return None

    par_valeur = {r['algo']: float(r['valeur_eur']) for _, r in valeurs.iterrows()}
    lignes, total = [], 0.0
    for algo, col in _COL_PROBA.items():
        if algo not in par_valeur or col not in df.columns:
            continue
        probas = pd.to_numeric(df[col], errors='coerce').dropna()
        if probas.empty:
            continue
        esperance = float(probas.sum()) * par_valeur[algo]
        total += esperance
        lignes.append({'algo': algo, 'proba_moyenne': float(probas.mean()),
                       'valeur_eur': par_valeur[algo],
                       'esperance_eur': esperance,
                       'titres': int(probas.shape[0])})
    if not lignes:
        return None
    date = pd.to_datetime(df['prediction_date']).max()
    return {'par_algo': pd.DataFrame(lignes), 'titres': int(df.shape[0]),
            'date': date.date() if pd.notna(date) else None, 'total': total}
