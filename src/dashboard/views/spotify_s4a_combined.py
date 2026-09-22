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
from src.dashboard.utils.date_format import format_date

_SPOTIFY_GREEN = "#1DB954"
_LISTENER_INK = "#7C4DFF"
_GHOST_INK = "#CFD8DC"
# Le ratio (§2) et l'indice de popularité (§3, tiroir) vivent chacun sur un axe
# SECONDAIRE. Ils portent donc une encre qui n'est utilisée par aucune série de
# l'axe principal : c'est ce qui permet de voir, sans lire la légende, quelle
# courbe se lit à droite.
_RATIO_INK = "#FF6D00"
_PI_INK = "#0091EA"

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

    # La légende DIT l'horizon et ce que chaque sortie porte réellement. Sans elle,
    # une courbe qui s'arrête plus tôt se lit comme un essoufflement.
    detail = " · ".join(
        f"{r.title} : {int(r.contiguous_days)} j"
        for r in sel.itertuples())
    st.caption(t("spotify_s4a_combined.releases_caption",
                 "Comparées sur leurs **{h} premiers jours**, la plus courte série "
                 "mesurée de la sélection. Mesure disponible par sortie — {detail}.")
               .format(h=horizon, detail=detail))

    dropped = int(sel["pre_release_streams"].sum())
    if dropped:
        # Compté plutôt que perdu : 4 écoutes de veille de sortie chez l'artiste 1,
        # artefact de fuseau de publication. Aujourd'hui négligeable — le jour où
        # une sortie mondiale en portera des milliers, la phrase existera déjà.
        st.caption(t("spotify_s4a_combined.pre_release",
                     "↩︎ {n} écoute(s) datées de la **veille** d'une sortie ne sont "
                     "pas dans ces courbes : Spotify publie à minuit dans le fuseau "
                     "le plus en avance, et le rapport date dans un autre.")
                   .format(n=dropped))


# ── §2 — décision B : l'audience grandit-elle ? ────────────────────────────────
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
    st.subheader(t("spotify_s4a_combined.audience_header",
                   "👥 Je gagne des auditeurs, ou les mêmes réécoutent ?"))

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

    full = mon[mon["is_complete"]]
    tile_src = full if not full.empty else mon
    last = tile_src.iloc[-1]

    c1, c2 = st.columns(2)
    c1.metric(t("spotify_s4a_combined.kpi_listeners", "👥 Auditeurs (dernier mois complet)"),
              f"{int(last['listener_days']):,}".replace(",", " "))

    ratio = last["streams_per_listener_day"]
    prev = last["streams_per_listener_day_prev"]
    delta = None
    if pd.notna(ratio) and pd.notna(prev):
        # Le delta vient de la vue (LAG), pas d'une soustraction ici : une tuile qui
        # calcule en pandas est invisible à tout garde SQL.
        delta = f"{float(ratio) - float(prev):+.2f}"
    c2.metric(t("spotify_s4a_combined.kpi_ratio", "🔁 Écoutes par auditeur-jour"),
              f"{float(ratio):.2f}" if pd.notna(ratio) else "—", delta=delta)

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

    # ⚠️ « le rapport du bas » a survécu UN rendu au passage en panneau unique :
    # la phrase désignait la figure par sa POSITION, et la position a changé sous
    # elle. Elle nomme maintenant la série — un nom ne bouge pas avec la mise en page.
    st.caption(t("spotify_s4a_combined.audience_caption",
                 "**Auditeurs-jour** : un auditeur unique compté une fois par jour "
                 "d'écoute — quelqu'un qui revient dix jours compte dix fois. "
                 "**Écoutes / auditeur-jour**, la courbe pointillée lue sur l'axe de "
                 "DROITE, dit donc combien de fois on écoute, pas combien de "
                 "personnes écoutent. Quand elle baisse à volume stable, l'audience "
                 "se renouvelle sans se fidéliser."))


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
    excluded = len(spans) - len(merged)

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
    without_pi = int(merged["popularity"].isna().sum())

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

    note = t("spotify_s4a_combined.momentum_caption",
             "Barre pleine : les **{n} derniers jours mesurés** (jusqu'au {d}). "
             "Barre grise : le cumul depuis la sortie. **PI** : l'indice de "
             "popularité Spotify (0-100) au dernier relevé — c'est le seuil que "
             "chaque algorithme demande pour s'ouvrir.").format(
                 n=_MOMENTUM_DAYS, d=format_date(horizon))
    if without_pi:
        # Un titre sans PI se COMPTE, comme un titre sans mesure récente : une
        # étiquette absente se lit sinon comme un PI de zéro.
        note += " " + t("spotify_s4a_combined.momentum_no_pi",
                        "**{k} titre(s) sans PI** : aucun relevé de popularité — "
                        "le rattachement Spotify se fait depuis **🔗 Mapping "
                        "cross-plateforme**.").format(k=without_pi)
    if excluded:
        # Un titre écarté se COMPTE. Une exclusion muette est le défaut qu'on vient
        # de corriger ailleurs, dans l'autre sens.
        note += " " + t("spotify_s4a_combined.momentum_excluded",
                        "**{k} titre(s) écarté(s)** : aucune mesure dans cette "
                        "fenêtre.").format(k=excluded)
    st.caption(note)


# ── §4 — le renvoi vers META x Spotify : RETIRÉ le 2026-09-21 ──────────────────
#
# Cette section n'était pas une figure mais un paragraphe et un bouton, qui
# disaient où vivait le rapprochement dépense/écoutes. La barre de navigation le
# dit déjà, et un renvoi qui occupe une section entière se lit comme du contenu.
# Le principe qu'il défendait — le couplage Meta n'a qu'UNE définition, sur sa
# page — n'a pas changé : cette page ne le recalcule toujours pas.


# ── Le tiroir ──────────────────────────────────────────────────────────────────
def _render_secondary(db, spans: pd.DataFrame, frag: str, params: tuple) -> None:
    """Le tiroir. Les `st.plotly_chart` sont LEXICALEMENT dans le `with`.

    Ce n'est pas un détail de style : `tests/test_chart_budget.py` et
    `test_a_view_opens_on_one_decision.py` lisent la STRUCTURE du fichier pour
    compter ce qui s'affiche au premier écran. Une figure tracée dans une fonction
    appelée depuis le `with` leur est indistinguable d'une figure principale — et
    ils ont raison de refuser : un lecteur du code ne peut pas le savoir non plus.
    Les renderers rendent donc une figure, ils ne la posent pas.
    """
    # OUVERT d'emblée (2026-09-21, demande du propriétaire) : le détail par titre
    # est ce qu'on vient regarder après avoir vu quel titre bouge, et le clic
    # supplémentaire le cachait. ⚠️ Les deux gardes de budget de figures
    # (`test_chart_budget`, `test_a_view_opens_on_one_decision`) reconnaissent ce
    # bloc par son NOM et non par son état : cette page peint donc SIX figures au
    # premier écran là où ils en comptent trois. Écrit ici pour que le chiffre soit
    # une décision et pas un angle mort.
    with secondary_analyses(expanded=True):
        fig, note = _song_detail(db, spans, frag, params)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
            if note:
                st.caption(note)
        st.markdown("---")
        fig = _saves_fig(db, frag, params)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        st.markdown("---")
        fig, note = _followers(db, frag, params)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
            st.caption(note)


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

    note = t("spotify_s4a_combined.detail_caption",
             "Série démarrée à la **première écoute** ({d}), pas au premier jour "
             "du fichier : Spotify exporte la timeline du compte et y inscrit 0 "
             "avant la sortie.").format(
                 d=format_date(start) if isinstance(start, date) else "—")
    if pi.empty:
        note += " " + t("spotify_s4a_combined.pi_missing",
                        "Aucun indice de popularité sur cette période : ce titre "
                        "n'a pas de lien Spotify confirmé, ou l'API n'a pas encore "
                        "relevé. Le rattachement se fait depuis **🔗 Mapping "
                        "cross-plateforme**.")
    else:
        # LES DEUX HORLOGES, DITES. C'est le fait que la figure montre et qu'un
        # lecteur pourrait prendre pour un défaut de données.
        note += " " + t("spotify_s4a_combined.pi_clock",
                        "L'**indice de popularité** est relevé par l'API tous les "
                        "jours (jusqu'au {pi_d}) ; les écoutes viennent du CSV, "
                        "importé au moment d'une sortie (jusqu'au {s_d}). Une "
                        "courbe d'écoutes qui s'arrête est un import qui s'arrête, "
                        "pas un titre qui meurt.").format(
                            pi_d=format_date(pd.to_datetime(pi["day"]).max()),
                            s_d=format_date(pd.to_datetime(df["day"]).max()))
    return fig, note


def _saves_fig(db, frag: str, params: tuple):
    st.markdown(f"##### {t('spotify_s4a_combined.saves_header', '💾 Sauvegardes et ajouts en playlist')}")
    df = _df(db, f"""
        SELECT month, saves, playlist_adds FROM v_s4a_audience_monthly
         WHERE TRUE {frag} ORDER BY month
    """, params)
    if df.empty:
        st.info(t("spotify_s4a_combined.no_data", "Pas de données disponibles."))
        return None
    df = df.copy()
    df["month"] = pd.to_datetime(df["month"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["month"], y=df["saves"],
                         name=t("spotify_s4a_combined.saves", "Sauvegardes"),
                         marker_color=_SPOTIFY_GREEN))
    fig.add_trace(go.Bar(x=df["month"], y=df["playlist_adds"],
                         name=t("spotify_s4a_combined.playlist_adds", "Ajouts en playlist"),
                         marker_color=_LISTENER_INK))
    fig.update_layout(height=320, barmode="group", hovermode="x unified")
    return fig


def _followers(db, frag: str, params: tuple):
    st.markdown(f"##### {t('spotify_s4a_combined.followers_header', '🔔 Abonnés')}")
    df = _df(db, f"""
        SELECT day, followers, source FROM v_spotify_followers_daily
         WHERE TRUE {frag} ORDER BY day
    """, params)
    if df.empty:
        st.info(t("spotify_s4a_combined.no_data", "Pas de données disponibles."))
        return None, None
    fig = go.Figure()
    # UNE SÉRIE PAR SOURCE, jamais raboutées : le CSV s'arrête au dernier import,
    # l'API court au jour le jour. Les coller ferait passer un changement de source
    # pour une inflexion.
    for src, grp in df.groupby("source", sort=False):
        label = t(f"spotify_s4a_combined.source.{src}",
                  "CSV Spotify for Artists" if src == "s4a_csv" else "API Spotify")
        fig.add_trace(go.Scatter(x=grp["day"], y=grp["followers"], mode="lines",
                                 name=label, line=dict(width=2)))
    fig.update_layout(height=320, hovermode="x unified",
                      yaxis_title=t("spotify_s4a_combined.followers", "Abonnés"))
    return fig, t("spotify_s4a_combined.followers_caption",
                  "Deux sources, deux horloges : le CSV porte l'historique profond et "
                  "s'arrête au dernier import ; l'API relève tous les jours mais ne "
                  "remonte pas avant sa mise en service. Elles ne se raboutent pas.")


def show():
    st.title(t("spotify_s4a_combined.title", "🎵 Spotify & Spotify for Artists"))

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
        _render_momentum(db, spans, frag, params)
        st.markdown("---")
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
                              "🎁 Mon bilan annuel (Spotify Wrapped for Artists)")):
        st.caption(t("spotify_s4a_combined.wrapped_intro",
                     "Ces chiffres ne sont dans aucune API : Spotify ne les publie "
                     "qu'une fois l'an, dans ton Wrapped for Artists. Saisis-les ici "
                     "et la courbe d'évolution se construit d'année en année."))
        render_wrapped_section(db, artist_id)
