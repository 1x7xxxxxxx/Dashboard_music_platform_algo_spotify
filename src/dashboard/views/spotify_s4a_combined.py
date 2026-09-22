"""Page Spotify & Spotify for Artists — une figure par décision.

Type: Feature
Uses: project_db, secondary_analyses, smart_period_filter, goto, i18n
Depends on: v_s4a_song_daily (105), v_s4a_audience_* (117), v_s4a_song_measured_span
            (118), v_s4a_release_cohort / _reach (119), v_spotify_followers_daily (120),
            v_spotify_track_pi_daily (130)
Persists in: — (lecture seule)

Ce que cette page était, et pourquoi elle a changé
--------------------------------------------------
Elle traçait **une seule métrique six fois** : deux tuiles, un Top 10, une courbe
d'audience, la même série en cumulé, et le détail par titre — toutes des streams.
Stephen Few le nomme (*Information Dashboard Design* p. 46 §3.4) : une mesure peut
être exacte sans être celle qui porte le message.

Pendant ce temps **889 jours d'auditeurs sans un trou** dormaient dans `s4a_audience`,
lus par le PDF et l'export CSV, et par aucune vue. L'artiste voyait ses auditeurs dans
le PDF exporté et jamais à l'écran. Ils disaient ceci : un auditeur écoutait **2,32**
fois en 2024, il écoute **1,14** fois en 2026. Il passe et ne revient pas.

La règle de composition : une section = une décision.
  §1 comparer mes sorties  ·  §2 mon audience grandit-elle  — les deux CÔTE À CÔTE,
  parce qu'elles sont les deux moitiés d'une même question  ·  §3 pousser ou laisser.

Le §4 — un renvoi vers META x Spotify — a été retiré le 2026-09-21 : c'était un
paragraphe et un bouton, pas une figure, et la barre de navigation le disait déjà.

Tout le reste descend dans `secondary_analyses()` — littéralement « une figure qui
affine une décision mais n'en prend aucune ». Le tiroir est OUVERT d'emblée depuis
le 2026-09-21 : le détail par titre est ce qu'on regarde juste après avoir vu quel
titre bouge. Rien n'est supprimé.

L'INDICE DE POPULARITÉ (PI), ajouté le 2026-09-21
--------------------------------------------------
Le PI est le seul signal de cette page qui soit relevé TOUS LES JOURS, par l'API ;
tout le reste vient d'un CSV importé au moment d'une sortie. Mesuré le 2026-09-21
sur le locataire 1 : les écoutes S4A s'arrêtent au 07/06/2026, le PI court jusqu'au
20/09/2026 — **105 jours** où la page montrait un titre mort qui ne l'était pas.
C'est aussi la PORTE de chaque algorithme : « ce titre bouge » et « ce titre bouge
avec un PI de 9 » n'appellent pas la même décision.

Il entre à deux endroits, et jamais comme une longueur sur une échelle de streams :
une ÉTIQUETTE par titre en §3, une COURBE sur axe secondaire borné à 0-100 dans le
détail par titre.

Aucune table brute n'est lue ici. C'est ce qui rend les deux règles S4A — retrait de
la ligne « Total » et déduplication (date, titre) — impossibles à oublier : elles
vivent dans `v_s4a_song_daily`, pas dans la mémoire de celui qui écrit la requête.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard.auth import artist_id_sql_filter
from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t
from src.dashboard.utils.navigation import goto
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.utils.ui import secondary_analyses

_SPOTIFY_GREEN = "#1DB954"
_LISTENER_INK = "#7C4DFF"
_GHOST_INK = "#CFD8DC"
# Le ratio (§2) et l'indice de popularité (§3, tiroir) vivent chacun sur un axe
# SECONDAIRE. Ils portent donc une encre qui n'est utilisée par aucune série de
# l'axe principal : c'est ce qui permet de voir, sans lire la légende, quelle
# courbe se lit à droite.
_RATIO_INK = "#FF6D00"
_PI_INK = "#0091EA"
# L'encre des ABONNÉS, sur l'axe secondaire de la figure d'engagement (2026-09-22).
# MESURÉE : ΔE 65 en CIELAB contre la plus proche des cinq encres ci-dessus — le
# meilleur des quatre candidats essayés (cyan 39, brun 54, jaune 60). ⚠️ Mesuré en
# vision NORMALE ; la deutéranopie n'a pas été simulée, donc ce 65 ne se compare pas au
# plancher de 15 d'un ΔE deutan. La lecture est portée par trois distinctions non
# chromatiques : l'axe de droite, son titre teinté, et barres contre ligne.
_FOLLOWER_INK = "#D81B60"

# La fenêtre sur laquelle « ce titre bouge-t-il encore » se juge. 28 jours est la
# fenêtre de Spotify for Artists elle-même — on parle la langue de la source plutôt
# que d'inventer un horizon.
_MOMENTUM_DAYS = 28


def _df(db, sql: str, params: tuple) -> pd.DataFrame:
    try:
        return db.fetch_df(sql, params)
    except Exception:  # noqa: BLE001 — une figure absente ne casse pas la page
        return pd.DataFrame()


# ── §0 — l'empan mesuré de chaque titre ────────────────────────────────────────
def _load_spans(db, frag: str, params: tuple) -> pd.DataFrame:
    """Jusqu'où chaque titre est mesuré. Chargement SEUL — plus aucun rendu.

    L'import S4A est ÉPISODIQUE, au moment d'une sortie : la mesure est dense autour
    de chaque sortie et s'arrête à la dernière campagne d'import. La légende qui
    l'expliquait a été retirée le 2026-09-21, à la demande du propriétaire : elle
    ouvrait la page sur un paragraphe avant la première figure. Le fait qu'elle
    portait — jusqu'à quand chaque titre est mesuré — n'est pas perdu : la légende
    de §3 nomme la date d'arrêt (« jusqu'au {d} »), celle de §1 donne la mesure
    disponible titre par titre, et la courbe de PI du tiroir montre désormais que
    le titre continue de vivre après le dernier import.
    """
    return _df(db, f"""
        SELECT song, first_streamed, last_measured, days_with_streams, streams_total
          FROM v_s4a_song_measured_span
         WHERE TRUE {frag}
         ORDER BY streams_total DESC
    """, params)


# ── §1 — décision D : comparer les sorties ─────────────────────────────────────
@st.fragment
def _frag_releases(frag: str, params: tuple) -> None:
    """Le comparateur de sorties — rejoué SEUL quand on change la sélection.

    @st.fragment (R118, 2026-09-16). Son multiselect rejouait tout le script.

    ⚠️ Il ouvre sa PROPRE connexion : la sélection pilote une requête, et celle de
    `show()` est refermée dès la fin du rendu complet.

    ⚠️ Et `_song_detail()` de ce même fichier N'EST PAS éligible, alors qu'il porte lui
    aussi un `st.selectbox` : il **rend une figure** (`fig, note = _song_detail(...)`) que
    son appelant pose ensuite. Un fragment rejoué seul ne peut rien rendre à un appelant
    qui, lui, ne se rejoue pas — la figure resterait celle du dernier rendu complet, et la
    page afficherait un titre choisi avec les données d'un autre. **Un fragment DESSINE,
    il ne RETOURNE pas.** Pour le rendre éligible il faudrait qu'il pose sa figure
    lui-même, ce que le docstring de `_render_secondary` refuse explicitement pour une
    autre raison — c'est donc un choix à trancher, pas un oubli.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, _artist_id):
        _render_releases(db, frag, params)


def _render_releases(db, frag: str, params: tuple) -> None:
    """Les sorties recalées sur J+0, comparées à fenêtre ÉGALE.

    C'est la colonne vertébrale, et elle découle de l'import épisodique : autour
    d'une sortie, c'est le seul cadre où deux séries sont comparables. Comparer
    40 jours de l'une à 120 jours de l'autre est la « comparaison qui n'a pas de
    sens » de Few p. 142 §7.1.5 — d'autant plus tentante que les deux courbes
    s'affichent côte à côte sans rien dire.
    """
    st.subheader(t("spotify_s4a_combined.releases_header", "🚀 Mes sorties, à âge égal"))

    reach = _df(db, f"""
        SELECT match_key, title, release_date, contiguous_days, last_measured,
               pre_release_streams
          FROM v_s4a_release_reach
         WHERE first_index = 0 {frag}
         ORDER BY release_date DESC
    """, params)
    if reach.empty:
        st.info(t("spotify_s4a_combined.no_releases",
                  "Aucune sortie rattachée à un titre Spotify for Artists. "
                  "Le rattachement se fait depuis **🔗 Mapping cross-plateforme**."))
        if st.button(t("spotify_s4a_combined.goto_mapping", "🔗 Rattacher mes titres")):
            goto("meta_mapping")
        return

    labels = reach["title"].tolist()
    default = labels[:2]
    chosen = st.multiselect(
        t("spotify_s4a_combined.pick_releases", "Sorties à comparer"),
        labels, default=default, key="s4a_release_pick")
    if not chosen:
        st.info(t("spotify_s4a_combined.pick_at_least_one",
                  "Choisis au moins une sortie."))
        return

    sel = reach[reach["title"].isin(chosen)]
    horizon = int(sel["contiguous_days"].min())

    keys = tuple(sel["match_key"].tolist())
    cohort = _df(db, f"""
        SELECT title, day_index, streams_cumulative
          FROM v_s4a_release_cohort
         WHERE day_index BETWEEN 0 AND %s
           AND match_key = ANY(%s) {frag}
         ORDER BY title, day_index
    """, (horizon - 1, list(keys), *params))
    if cohort.empty:
        st.info(t("spotify_s4a_combined.no_data", "Pas de données disponibles."))
        return

    fig = go.Figure()
    for title, grp in cohort.groupby("title", sort=False):
        # L'ÉTIQUETTE DE VALEUR EST AU DERNIER POINT, ET NULLE PART AILLEURS.
        # C'est la seule abscisse où deux sorties se comparent — le bout de
        # l'horizon commun — donc la seule où un nombre décide quelque chose.
        # Étiqueter chaque point écrirait plusieurs centaines de nombres les uns
        # sur les autres et rendrait la courbe illisible, ce qui est l'inverse de
        # ce qu'on vient chercher.
        labels = [""] * len(grp)
        if len(labels):
            labels[-1] = f"{int(grp['streams_cumulative'].iloc[-1]):,}".replace(",", " ")
        fig.add_trace(go.Scatter(
            x=grp["day_index"], y=grp["streams_cumulative"],
            mode="lines+text", name=str(title), line=dict(width=2.5),
            text=labels, textposition="middle left",
            textfont=dict(size=13), cliponaxis=False))
    fig.update_layout(
        height=420, hovermode="x unified",
        # Le dernier point porte son nombre : sans marge à droite, il sort du cadre.
        margin=dict(r=90),
        xaxis_title=t("spotify_s4a_combined.days_since_release", "Jours depuis la sortie"),
        yaxis_title=t("spotify_s4a_combined.cumulative_streams", "Streams cumulés"),
        legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")

    # ⚠️ DEUX LÉGENDES RETIRÉES le 2026-09-22, demandé en regardant l'écran.
    #
    # La première disait l'horizon de comparaison et ce que chaque sortie porte
    # (« Comparées sur leurs 737 premiers jours… »). La seconde comptait les écoutes
    # datées de la veille d'une sortie, un artefact de fuseau de publication.
    #
    # Les deux étaient JUSTES et personne ne les lisait : quatre lignes de réserve
    # sous une figure de deux courbes. L'horizon est visible sur l'axe des abscisses,
    # qui porte « Jours depuis la sortie » ; l'artefact de fuseau vaut 2 écoutes sur
    # ce catalogue. Le calcul, lui, n'a pas changé — `pre_release_streams` est
    # toujours écarté des courbes, et le dire dans le code plutôt qu'à l'écran est
    # le bon endroit pour une précision que personne n'actionne.
    #
    # ⚠️ Si une sortie mondiale en portait des milliers un jour, la phrase devrait
    # revenir. Le seuil n'est pas gardé : c'est un jugement, et il est écrit ici.


def _render_audience(db, frag: str, params: tuple) -> None:
    """Auditeurs, écoutes, et le rapport des deux.

    ⚠️ `listeners` compte les auditeurs UNIQUES PAR JOUR. Les sommer compte une fois
    par jour celui qui revient : le dénominateur est un nombre d'AUDITEURS-JOUR, pas
    de personnes. Le libellé le dit, et un garde le vérifie — appeler ce ratio
    « par auditeur » serait exact au calcul et faux au sens.

    UN SEUL PANNEAU, un axe à droite pour le ratio — changé le 2026-09-21 à la
    demande du propriétaire, et le compromis mérite d'être écrit.

    La forme d'avant était deux panneaux empilés, exactement pour que rien n'invite
    à lire un « croisement » entre un COMPTE (auditeurs-jour, streams) et un RATIO
    (écoutes par auditeur-jour) : deux séries sur deux échelles se croisent à
    l'endroit que choisit l'échelle, pas à un endroit qui existe. Ce risque n'a pas
    disparu, il est assumé — ce qu'on achète en échange est une légende unique et
    un seul axe de temps, donc une lecture d'un coup d'œil au lieu de deux.

    Ce qui rend le double axe lisible ici, et pas seulement toléré : le ratio est
    la SEULE série de droite, tracée en pointillé et dans une couleur qui n'est
    utilisée nulle part ailleurs sur la page, et son axe porte son unité. Un
    croisement reste possible à l'œil ; rien dans la figure ne le présente comme un
    évènement.
    """
    # ⚠️ SOUS-TITRE ET DEUX JAUGES RETIRÉS le 2026-09-22, demandé en regardant
    # l'écran. La question « je gagne des auditeurs ou les mêmes réécoutent ? » est
    # exactement ce que la figure MONTRE — les barres d'auditeurs-jour contre la
    # courbe pointillée du ratio — et les deux tuiles répétaient en chiffre le
    # dernier point de ces deux séries. Trois éléments pour une seule lecture.
    mon = _df(db, f"""
        SELECT month, streams, listener_days, streams_per_listener_day,
               streams_per_listener_day_prev, followers_end, is_complete
          FROM v_s4a_audience_monthly
         WHERE TRUE {frag}
         ORDER BY month
    """, params)
    if mon.empty:
        st.info(t("spotify_s4a_combined.no_audience",
                  "Aucun rapport d'audience importé. Il s'importe depuis "
                  "**📂 Ajouter mes chiffres Spotify for Artists & Apple**."))
        return

    mon = mon.copy()
    mon["month"] = pd.to_datetime(mon["month"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=mon["month"], y=mon["listener_days"],
                         name=t("spotify_s4a_combined.listener_days", "Auditeurs-jour"),
                         marker_color=_LISTENER_INK, opacity=0.85),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=mon["month"], y=mon["streams"], mode="lines",
                             name=t("common.streams", "Streams"),
                             line=dict(color=_SPOTIFY_GREEN, width=2.5)),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=mon["month"], y=mon["streams_per_listener_day"],
                             mode="lines+markers",
                             name=t("spotify_s4a_combined.ratio_short", "Écoutes / auditeur-jour"),
                             line=dict(color=_RATIO_INK, width=2.5, dash="dot"),
                             marker=dict(size=7)),
                  secondary_y=True)
    fig.update_yaxes(title_text=t("common.count", "Nombre"), secondary_y=False)
    # L'axe de droite est TEINTÉ de la couleur de sa seule série : sans ça, deux
    # échelles se lisent comme une, et c'est là que naît le faux croisement.
    fig.update_yaxes(title_text=t("spotify_s4a_combined.ratio_axis", "× par auditeur-jour"),
                     secondary_y=True, showgrid=False,
                     title_font=dict(color=_RATIO_INK), tickfont=dict(color=_RATIO_INK))
    fig.update_layout(height=470, hovermode="x unified",
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")

    # ⚠️ LÉGENDE RETIRÉE le 2026-09-22, demandé en regardant l'écran. Elle
    # expliquait ce qu'est un auditeur-jour et ce que dit la courbe pointillée —
    # six lignes sous une figure de trois séries.
    #
    # Ce qui PORTE le sens reste en place et c'est là qu'il doit être : le libellé de
    # la série dit « Écoutes / auditeur-jour », l'axe de droite porte son unité
    # « × par auditeur-jour » et la couleur de cet axe est celle de sa seule série.
    # Nommer le denominateur DANS le libellé était déjà la décision — appeler ce
    # ratio « par auditeur » serait exact au calcul et faux au sens — et c'est elle
    # qui survit, pas sa paraphrase.


# ── §3 — décision A : pousser ou laisser ───────────────────────────────────────
def _render_momentum(db, spans: pd.DataFrame, frag: str, params: tuple) -> None:
    """Ce qui bouge MAINTENANT, devant le cumul à vie en fantôme.

    Remplace le Top 10 all-time, qui est exact et ne décide rien : il classe
    toujours pareil, quelle que soit la question posée. L'écart entre la barre
    pleine et la barre fantôme est précisément ce qu'on vient chercher — un gros
    catalogue qui ne bouge plus ne se distinguait pas d'un titre qui monte.
    """
    st.subheader(t("spotify_s4a_combined.momentum_header",
                   "🔥 Ce qui bouge en ce moment"))
    if spans.empty:
        st.info(t("spotify_s4a_combined.no_data", "Pas de données disponibles."))
        return

    horizon = pd.to_datetime(spans["last_measured"]).max().date()
    since = horizon - pd.Timedelta(days=_MOMENTUM_DAYS - 1)

    recent = _df(db, f"""
        SELECT s.song, COALESCE(SUM(d.streams), 0) AS recent
          FROM v_s4a_song_measured_span s
          LEFT JOIN v_s4a_song_daily d
                 ON d.artist_id = s.artist_id AND d.song = s.song
                AND d.day BETWEEN %s AND %s
         WHERE s.last_measured >= %s {frag.replace('artist_id', 's.artist_id')}
         GROUP BY s.song
    """, (since.date() if hasattr(since, "date") else since, horizon, since.date()
          if hasattr(since, "date") else since, *params))
    if recent.empty:
        st.info(t("spotify_s4a_combined.no_recent",
                  "Aucun titre mesuré sur les {n} derniers jours importés.")
                .format(n=_MOMENTUM_DAYS))
        return

    merged = spans.merge(recent, on="song", how="inner").sort_values("recent")
    # ⚠️ `excluded = len(spans) - len(merged)` a été RETIRÉ avec la légende qu'il
    # nourrissait (2026-09-22). Il ne servait qu'à écrire « N titre(s) écarté(s) », et
    # un calcul qui n'alimente plus rien pourrit — ce dépôt a payé deux fois « une
    # couche débranchée » et « du code mort cache une conséquence vivante ». Le filtre
    # lui-même n'a pas bougé : c'est le `how="inner"` ci-dessus qui écarte, et il est
    # visible là où il agit.

    # L'INDICE DE POPULARITÉ, collé au titre qu'il qualifie.
    #
    # Le PI est la PORTE de chaque algorithme (Discover Weekly, Release Radar,
    # Radio ont chacun leur seuil). « Ce titre bouge » et « ce titre bouge avec un
    # PI de 9 » n'appellent pas la même décision, et rien sur cette page ne
    # permettait de les distinguer : il fallait aller sur Road to Algo.
    #
    # Il est écrit comme une ÉTIQUETTE, jamais tracé sur un second axe de ce
    # graphique : les barres sont en streams, le PI est sur 0-100, et poser les
    # deux sur la même bande horizontale ferait lire une longueur comme une
    # comparaison. Une étiquette n'a pas de longueur.
    pi = _df(db, f"""
        SELECT DISTINCT ON (song) song, popularity
          FROM v_spotify_track_pi_daily
         WHERE TRUE {frag}
         ORDER BY song, day DESC
    """, params)
    merged = merged.merge(pi, on="song", how="left") if not pi.empty else merged
    if "popularity" not in merged.columns:
        merged["popularity"] = pd.NA
    pi_labels = [
        t("spotify_s4a_combined.pi_tag", "PI {v}").format(v=int(v))
        if pd.notna(v) else ""
        for v in merged["popularity"]
    ]
    # ⚠️ `without_pi` a été RETIRÉ avec la même légende : il comptait les titres sans
    # indice de popularité pour l'annoncer sous la figure. Les barres concernées
    # portent déjà l'absence dans leur étiquette.

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=merged["song"], x=merged["streams_total"], orientation="h",
        name=t("spotify_s4a_combined.lifetime", "Cumul à vie"),
        marker_color=_GHOST_INK,
        # L'étiquette est posée au bout de la barre LA PLUS LONGUE des deux, pour
        # qu'elle ne tombe jamais au milieu de l'autre.
        text=pi_labels, textposition="outside", cliponaxis=False,
        textfont=dict(color=_PI_INK, size=12),
        hovertemplate="%{x:,.0f}<extra>cumul à vie</extra>"))
    fig.add_trace(go.Bar(
        y=merged["song"], x=merged["recent"], orientation="h",
        name=t("spotify_s4a_combined.recent_window", "{n} derniers jours mesurés")
              .format(n=_MOMENTUM_DAYS),
        marker_color=_SPOTIFY_GREEN,
        hovertemplate="%{x:,.0f}<extra>fenêtre récente</extra>"))
    fig.update_layout(barmode="overlay", height=max(320, 42 * len(merged)),
                      xaxis_title=t("common.streams", "Streams"),
                      margin=dict(r=80),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")

    # ⚠️ LÉGENDE RETIRÉE le 2026-09-22, demandé en regardant l'écran. Elle disait
    # ce que valent la barre pleine, la barre grise et le sigle PI, plus le nombre de
    # titres écartés faute de mesure dans la fenêtre.
    #
    # Ce qui la remplace n'est pas rien : la LÉGENDE de la figure nomme déjà ses deux
    # séries, et c'est l'endroit où on regarde quand on se demande ce qu'une barre
    # représente. Une phrase sous la figure redit ce que la légende porte à
    # l'intérieur.
    #
    # ⚠️ CE QUI EST PERDU, et le dire est le point : le nombre de titres ÉCARTÉS
    # faute de mesure dans la fenêtre. C'était une information d'absence — « 1 titre
    # n'est pas là » — et une absence non dite se lit comme un catalogue plus petit.
    # Elle disparaît de l'écran sur demande explicite ; la valeur reste calculée et
    # lisible dans le code, et si un catalogue en écartait la moitié un jour, il
    # faudrait la remettre.


def _render_secondary(db, spans: pd.DataFrame, frag: str, params: tuple) -> None:
    """Le tiroir. Les `st.plotly_chart` sont LEXICALEMENT dans le `with`.

    Ce n'est pas un détail de style : `tests/test_chart_budget.py` et
    `test_a_view_opens_on_one_decision.py` lisent la STRUCTURE du fichier pour
    compter ce qui s'affiche au premier écran. Une figure tracée dans une fonction
    appelée depuis le `with` leur est indistinguable d'une figure principale — et
    ils ont raison de refuser : un lecteur du code ne peut pas le savoir non plus.
    Les renderers rendent donc une figure, ils ne la posent pas.
    """
    # ⚠️ CE N'EST PLUS UN TIROIR — 2026-09-22, demandé en regardant l'écran :
    # « ouvert de façon automatique sans possibilité de refermer le bandeau : le
    # rendre permanent ».
    #
    # Il était déjà ouvert d'emblée depuis le 2026-09-21 (`expanded=True`), et cela
    # ne suffisait pas : **un `st.expander` reste refermable par construction**, donc
    # un clic malheureux cachait le détail et rien ne le rouvrait au rerun suivant.
    # « Ouvert par défaut » et « permanent » sont deux choses, et seule la seconde
    # était demandée.
    #
    # `secondary_analyses` n'est donc PLUS appelée ici. Elle reste le bon outil
    # partout ailleurs — c'est un helper partagé par plusieurs vues et on ne le
    # change pas pour une page.
    #
    # ⚠️ CE QUE ÇA COÛTE, ET QUI LE SAIT. Les deux gardes de budget de figures
    # (`test_chart_budget`, `test_a_view_opens_on_one_decision`) abritaient ce bloc
    # par son NOM. Sans ce nom, les trois figures d'ici deviennent des figures de
    # premier écran à leurs yeux — ce qui est **exact** : elles le sont vraiment,
    # depuis le 2026-09-21. Le plafond de cette page est donc relevé à leur vraie
    # valeur, dans le même commit, et l'ancien chiffre était l'angle mort que le
    # commentaire du 2026-09-21 annonçait déjà.
    st.markdown(f"#### {t('ui.secondary_analyses', '📊 Analyses détaillées')}")
    fig, note = _song_detail(db, spans, frag, params)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")
        if note:
            st.caption(note)
    st.markdown("---")
    # UNE figure au lieu de deux (2026-09-22) : sauvegardes, playlists et abonnés.
    # La légende « Deux sources, deux horloges… » est retirée — c'est le TRAIT qui le
    # dit désormais, plein pour l'API, pointillé pour le CSV.
    fig = _engagement_fig(db, frag, params)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")


def _song_detail(db, spans: pd.DataFrame, frag: str, params: tuple):
    st.markdown(f"##### {t('spotify_s4a_combined.detail_header', '🎸 Détail par titre')}")
    if spans.empty:
        return None, None

    # LA DERNIÈRE SORTIE EST PROPOSÉE D'OFFICE (2026-09-21).
    #
    # `spans` arrive trié par cumul à vie décroissant, donc le premier choix était
    # le plus GROS titre — celui qu'on connaît déjà. La question qu'on se pose en
    # ouvrant cette page est presque toujours « et ma dernière sortie, elle fait
    # quoi ? ». On classe donc par `first_streamed` décroissant : la première
    # écoute d'un titre S4A est le jour de sa sortie, à un fuseau près (la cohorte
    # de §1 mesure ce décalage à 4 écoutes de veille sur 163 088).
    #
    # `sort_values(na_position="last")` : un titre sans première écoute connue ne
    # doit pas remonter en tête par l'effet d'un NULL.
    ordered = spans.sort_values("first_streamed", ascending=False, na_position="last")
    song = st.selectbox(t("spotify_s4a_combined.select_song", "Titre"),
                        ordered["song"].tolist(), key="s4a_detail_song")
    row = spans[spans["song"] == song].iloc[0]

    # La fenêtre proposée est celle DU TITRE choisi, et elle démarre à sa première
    # écoute. Spotify exporte la timeline du COMPTE et y met 0 avant la sortie :
    # partir du premier jour du fichier dessinerait des mois de plat à zéro pour un
    # morceau qui n'était pas publié.
    start = row["first_streamed"] or row["first_measured"]
    window = smart_period_filter(
        db, table="v_s4a_song_daily", date_column="day",
        artist_id=None, key=f"s4a_detail_{song}",
        latest_release=start if isinstance(start, date) else None,
        default_override="last_release")
    wfrag, wparams = window.sql_between("day")

    df = _df(db, f"""
        SELECT day, streams FROM v_s4a_song_daily
         WHERE song = %s AND day >= %s {frag} {wfrag}
         ORDER BY day
    """, (song, start, *params, *wparams))
    if df.empty:
        st.info(t("spotify_s4a_combined.no_data_period", "Pas de données pour cette période."))
        return None, None

    # L'INDICE DE POPULARITÉ, SUR LA MÊME HORLOGE — et c'est là qu'il décide.
    #
    # Les deux séries répondent à deux questions que la page posait séparément :
    # « ce titre est-il encore écouté ? » (les écoutes, importées par campagnes) et
    # « ce titre est-il encore VU par Spotify ? » (le PI, relevé par l'API tous les
    # jours). Mesuré le 2026-09-21 sur le locataire 1 : les écoutes S4A s'arrêtent
    # au 07/06/2026, le PI court jusqu'au 20/09/2026 — **105 jours** pendant
    # lesquels la courbe seule donnait un titre mort alors qu'il ne l'était pas.
    #
    # La MÊME fenêtre borne les deux (`{wfrag}`) : deux séries d'un même graphique
    # sur deux périodes différentes est la comparaison sans objet que le garde
    # `test_a_chart_is_bounded_by_the_period_it_announces` existe pour interdire.
    pi = _df(db, f"""
        SELECT day, popularity FROM v_spotify_track_pi_daily
         WHERE song = %s {frag} {wfrag}
         ORDER BY day
    """, (song, *params, *wparams))

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df["day"], y=df["streams"], mode="lines",
                             name=t("spotify_s4a_combined.streams_per_day",
                                    "Streams / jour"),
                             line=dict(color=_SPOTIFY_GREEN, width=2)),
                  secondary_y=False)
    if not pi.empty:
        fig.add_trace(go.Scatter(x=pi["day"], y=pi["popularity"],
                                 mode="lines+markers",
                                 name=t("spotify_s4a_combined.pi_series",
                                        "Indice de popularité (0-100)"),
                                 line=dict(color=_PI_INK, width=2, dash="dot"),
                                 marker=dict(size=5)),
                      secondary_y=True)
    fig.update_yaxes(title_text=t("spotify_s4a_combined.streams_per_day", "Streams / jour"),
                     secondary_y=False)
    # Borné à 0-100 même quand les valeurs sont basses : un PI de 9 autoscalé
    # remplirait la hauteur et se lirait comme un titre au sommet. L'échelle du PI
    # est sa propre information — c'est la distance aux portes algorithmiques.
    fig.update_yaxes(title_text=t("spotify_s4a_combined.pi_axis", "Indice de popularité"),
                     secondary_y=True, range=[0, 100], showgrid=False,
                     title_font=dict(color=_PI_INK), tickfont=dict(color=_PI_INK))
    fig.update_layout(height=340, hovermode="x unified",
                      legend=dict(orientation="h", y=1.15))

    # ⚠️ DEUX TIERS DE CETTE LÉGENDE SONT RETIRÉS — 2026-09-22, demandé en regardant
    # l'écran. Partaient : « Série démarrée à la première écoute… » et « L'indice de
    # popularité est relevé par l'API tous les jours… ». Toutes deux vraies, toutes deux
    # longues, et toutes deux expliquant la FORME de la figure à quelqu'un qui voulait
    # lire son CONTENU.
    #
    # ⚠️ CE QUI RESTE, ET POURQUOI IL RESTE. `pi_missing` n'est pas une paraphrase : il
    # dit une ABSENCE et nomme le GESTE qui la lève (« le rattachement se fait depuis
    # 🔗 Mapping cross-plateforme »). C'est la seule forme de texte que ce dépôt tient
    # pour non négociable sur un écran — une absence muette se lit comme un zéro, et un
    # artiste ne peut pas deviner qu'il doit rattacher un titre.
    note = ""
    if pi.empty:
        note = t("spotify_s4a_combined.pi_missing",
                 "Aucun indice de popularité sur cette période : ce titre "
                 "n'a pas de lien Spotify confirmé, ou l'API n'a pas encore "
                 "relevé. Le rattachement se fait depuis **🔗 Mapping "
                 "cross-plateforme**.")
    return fig, note


def _engagement_fig(db, frag: str, params: tuple):
    """Sauvegardes, ajouts en playlist et ABONNÉS sur une seule figure.

    Demandé le 2026-09-22 : « ajoute sur le même graphique les sauvegardes et ajouts en
    playlist + le nombre d'abonnés en couleur différente et visuellement identifiable ».
    C'étaient deux figures (`_saves_fig`, `_followers`) l'une sous l'autre.

    ⚠️ DEUX GRAINS, DEUX NATURES, DONC DEUX AXES — et ce n'est pas un détail de forme.
    Les sauvegardes et les ajouts en playlist sont des FLUX mensuels : « combien ce
    mois-ci ». Les abonnés sont un NIVEAU quotidien : « combien en tout, aujourd'hui ».
    Les mettre sur la même échelle ferait lire un niveau comme un flux — c'est
    exactement `un-cumul-pris-pour-un-quotidien`, la famille qui a coûté le plus cher
    à ce dépôt sur les figures.

    Les abonnés vont donc sur l'axe de DROITE, et la figure porte cette distinction de
    trois façons indépendantes — parce que la couleur seule ne suffit pas pour qui ne
    la voit pas :

      * la POSITION : une seule série se lit à droite ;
      * le TITRE DE L'AXE, teinté de l'encre de cette série — la convention de cette
        page depuis le 2026-09-21, écrite en tête du fichier ;
      * la FORME : des barres pour les flux, une ligne pour le niveau.

    L'encre des abonnés est `_FOLLOWER_INK`, et elle est MESURÉE : ΔE 65 en CIELAB
    contre la plus proche des cinq encres déjà utilisées sur cette page. ⚠️ Mesuré en
    vision NORMALE — la deutéranopie n'a pas été simulée, donc ce 65 ne se compare pas
    au plancher de 15 que ce dépôt utilise pour un ΔE deutan. Ce sont les trois
    distinctions non chromatiques ci-dessus qui portent la lecture dans ce cas.

    ⚠️ LES DEUX SOURCES D'ABONNÉS RESTENT DEUX SÉRIES, jamais raboutées : le CSV porte
    l'historique profond et s'arrête au dernier import, l'API court au jour le jour et
    ne remonte pas avant sa mise en service. Les coller ferait passer un changement de
    source pour une inflexion. La LÉGENDE qui l'expliquait a été retirée le 2026-09-22
    sur demande ; c'est donc le TRAIT qui le dit maintenant — plein pour l'API qui
    mesure tous les jours, pointillé pour le CSV qui s'arrête.
    """
    st.markdown(f"##### {t('spotify_s4a_combined.engagement_header', '💾 Sauvegardes, playlists et abonnés')}")

    flux = _df(db, f"""
        SELECT month, saves, playlist_adds FROM v_s4a_audience_monthly
         WHERE TRUE {frag} ORDER BY month
    """, params)
    abo = _df(db, f"""
        SELECT day, followers, source FROM v_spotify_followers_daily
         WHERE TRUE {frag} ORDER BY day
    """, params)
    if flux.empty and abo.empty:
        st.info(t("spotify_s4a_combined.no_data", "Pas de données disponibles."))
        return None

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not flux.empty:
        flux = flux.copy()
        flux["month"] = pd.to_datetime(flux["month"])
        fig.add_trace(go.Bar(x=flux["month"], y=flux["saves"],
                             name=t("spotify_s4a_combined.saves", "Sauvegardes"),
                             marker_color=_SPOTIFY_GREEN),
                      secondary_y=False)
        fig.add_trace(go.Bar(x=flux["month"], y=flux["playlist_adds"],
                             name=t("spotify_s4a_combined.playlist_adds",
                                    "Ajouts en playlist"),
                             marker_color=_LISTENER_INK),
                      secondary_y=False)

    if not abo.empty:
        for src, grp in abo.groupby("source", sort=False):
            csv = src == "s4a_csv"
            label = t(f"spotify_s4a_combined.source.{src}",
                      "CSV Spotify for Artists" if csv else "API Spotify")
            fig.add_trace(
                go.Scatter(x=grp["day"], y=grp["followers"], mode="lines",
                           name=t("spotify_s4a_combined.followers_src",
                                  "Abonnés · {src}").format(src=label),
                           line=dict(color=_FOLLOWER_INK, width=2.5,
                                     dash="dot" if csv else "solid")),
                secondary_y=True)

    fig.update_yaxes(title_text=t("spotify_s4a_combined.monthly_flow", "Par mois"),
                     secondary_y=False)
    # L'axe de droite est TEINTÉ de l'encre de ses séries : sans ça, deux échelles se
    # lisent comme une, et c'est là que naît le faux croisement.
    fig.update_yaxes(title_text=t("spotify_s4a_combined.followers", "Abonnés"),
                     secondary_y=True, showgrid=False,
                     title_font=dict(color=_FOLLOWER_INK),
                     tickfont=dict(color=_FOLLOWER_INK))
    fig.update_layout(height=380, barmode="group", hovermode="x unified",
                      legend=dict(orientation="h", y=1.14))
    return fig


def show():
    # ⚠️ PAS DE `st.title` — retiré le 2026-09-22, demandé en regardant l'écran.
    # L'entrée du menu porte déjà « 🎵 Spotify + Spotify for Artists » et reste
    # surlignée : le titre le répétait à un centimètre, en mangeant la hauteur du
    # premier écran. Les quatre sous-titres de section suffisent à se repérer.

    # La connexion vivante est DECLAREE pour les fragments de cette page : dans un
    # rendu complet ils la reutilisent au lieu d'en ouvrir une (~13 ms la poignee
    # SCRAM, mesure) ; lors d'un rerun de fragment la fente est vide et ils rouvrent
    # proprement. Voir `src/dashboard/utils/fragment_db.py`.
    from src.dashboard.utils.fragment_db import page_db_scope

    with project_db() as db, page_db_scope(db):
        frag, params = artist_id_sql_filter()
        params = tuple(params)

        spans = _load_spans(db, frag, params)

        # §1 ET §2 CÔTE À CÔTE (2026-09-21). Les deux répondent à la même
        # question posée de deux côtés — « qu'est-ce que ma dernière sortie a
        # produit » et « est-ce que ça m'a fait gagner des gens » — et les lire
        # l'une sous l'autre demandait de faire défiler entre les deux moitiés
        # d'une même réponse.
        #
        # ⚠️ `_frag_releases` est un `@st.fragment` : il DESSINE dans le conteneur
        # où il est appelé, il ne rend rien. C'est ce qui lui permet d'entrer dans
        # une colonne sans rien changer à son rejeu isolé.
        left, right = st.columns(2)
        with left:
            _frag_releases(frag, params)
        with right:
            _render_audience(db, frag, params)

        st.markdown("---")
        # §3 ET LE DÉTAIL CÔTE À CÔTE — 2026-09-22, demandé en regardant l'écran :
        # « mets sur la même ligne le graph ce qui bouge en ce moment et analyses
        # détaillées ».
        #
        # C'est le même geste, pour la même raison, que §1 et §2 le 2026-09-21 : on
        # voit quel titre bouge, puis on veut son détail — les lire l'un SOUS l'autre
        # demandait de faire défiler entre les deux moitiés d'une même question.
        gauche, droite = st.columns(2)
        with gauche:
            _render_momentum(db, spans, frag, params)
        with droite:
            _render_secondary(db, spans, frag, params)
        st.markdown("---")
        _render_wrapped(db)


# ── Le bilan annuel (ex « Data Wrapped ») ──────────────────────────────────────
def _render_wrapped(db) -> None:
    """La saisie Wrapped et son évolution, rapatriées ici le 2026-09-21.

    Elles avaient leur propre entrée de menu, « 🎁 Data Wrapped », entre Instagram
    et les autres plateformes. Or ce qu'on y saisit sont les chiffres du **Spotify
    Wrapped for Artists** — listeners, streams, saves, playlist adds, pays, heures
    d'écoute — c'est-à-dire des chiffres Spotify, pour la seule plateforme que
    cette page raconte. Une entrée de menu par SOURCE de saisie éparpillait ce qui
    est une seule histoire.

    ⚠️ REPLIÉ, et c'est délibéré. Ce sont des chiffres ANNUELS : ils ne décident
    rien un mardi, et la page ouvre déjà sur trois figures quotidiennes. C'est
    exactement le critère de `secondary_analyses` — « une figure qui affine une
    décision mais n'en prend aucune ».

    ⚠️ ET UN ANGLE MORT EST OUVERT ICI, autant l'écrire. Les deux cliquets de
    budget comptent les `st.plotly_chart` du FICHIER qu'ils lisent : ceux que
    `data_wrapped.py` dessine ne sont donc comptés dans aucun budget de cette
    page. Ils restent comptés dans le sien, mais un lecteur des budgets de
    `spotify_s4a_combined.py` ne les verra pas. Le repli est ce qui rend la
    situation acceptable ; il ne la rend pas invisible.
    """
    from src.dashboard.auth import get_artist_id
    from src.dashboard.views.data_wrapped import render_wrapped_section

    artist_id = get_artist_id()
    if artist_id is None:
        return      # admin sans locataire résolu : la route autonome reste ouverte
    with secondary_analyses(t("spotify_s4a_combined.wrapped_header",
                              "🎁 Spotify Wrapped (bilan annuel)")):
        st.caption(t("spotify_s4a_combined.wrapped_intro",
                     "Ces chiffres ne sont dans aucune API : Spotify ne les publie "
                     "qu'une fois l'an, dans ton Wrapped for Artists. Saisis-les ici "
                     "et la courbe d'évolution se construit d'année en année."))
        render_wrapped_section(db, artist_id)
