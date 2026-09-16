"""Page Spotify & Spotify for Artists — une figure par décision.

Type: Feature
Uses: project_db, secondary_analyses, smart_period_filter, goto, i18n
Depends on: v_s4a_song_daily (105), v_s4a_audience_* (117), v_s4a_song_measured_span
            (118), v_s4a_release_cohort / _reach (119), v_spotify_followers_daily (120)
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
  §1 comparer mes sorties  ·  §2 mon audience grandit-elle  ·  §3 pousser ou laisser
  ·  §4 quand relancer la pub (un renvoi, pas une figure : le couplage Meta est déjà
  construit et testé sur sa page — le refaire ici en serait la troisième définition).

Tout le reste descend dans `secondary_analyses()` — littéralement « une figure qui
affine une décision mais n'en prend aucune ». Rien n'est supprimé, tout est à un clic.

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

# La fenêtre sur laquelle « ce titre bouge-t-il encore » se juge. 28 jours est la
# fenêtre de Spotify for Artists elle-même — on parle la langue de la source plutôt
# que d'inventer un horizon.
_MOMENTUM_DAYS = 28


def _df(db, sql: str, params: tuple) -> pd.DataFrame:
    try:
        return db.fetch_df(sql, params)
    except Exception:  # noqa: BLE001 — une figure absente ne casse pas la page
        return pd.DataFrame()


# ── §0 — les horloges, une par titre ───────────────────────────────────────────
def _render_clocks(db, frag: str, params: tuple) -> pd.DataFrame:
    """Jusqu'où chaque titre est mesuré. Une date globale mentirait.

    L'import S4A est ÉPISODIQUE, au moment d'une sortie : la mesure est dense autour
    de chaque sortie et s'arrête à la dernière campagne d'import. Afficher une seule
    « dernière mise à jour » pour onze titres affirme un arrêt général qui n'a pas
    eu lieu — c'est la tuile que cette section remplace.
    """
    spans = _df(db, f"""
        SELECT song, first_streamed, last_measured, days_with_streams, streams_total
          FROM v_s4a_song_measured_span
         WHERE TRUE {frag}
         ORDER BY streams_total DESC
    """, params)
    if spans.empty:
        return spans

    last = pd.to_datetime(spans["last_measured"]).max()
    st.caption(t("spotify_s4a_combined.clocks",
                 "ⓘ **{n}** titres mesurés, le plus récemment jusqu'au **{d}**. "
                 "Le CSV Spotify for Artists s'importe au moment d'une sortie : "
                 "chaque titre a donc sa propre date de fin, et une absence de "
                 "mesure n'est pas une absence d'écoute.")
               .format(n=len(spans), d=last.strftime("%d/%m/%Y")))
    return spans


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
        fig.add_trace(go.Scatter(
            x=grp["day_index"], y=grp["streams_cumulative"],
            mode="lines", name=str(title), line=dict(width=2.5)))
    fig.update_layout(
        height=420, hovermode="x unified",
        xaxis_title=t("spotify_s4a_combined.days_since_release", "Jours depuis la sortie"),
        yaxis_title=t("spotify_s4a_combined.cumulative_streams", "Streams cumulés"))
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

    Deux panneaux, jamais un double axe : un compte et un ratio n'ont pas d'unité
    commune, et les superposer invite à lire un croisement qui ne veut rien dire.
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
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        row_heights=[0.58, 0.42])
    fig.add_trace(go.Bar(x=mon["month"], y=mon["listener_days"],
                         name=t("spotify_s4a_combined.listener_days", "Auditeurs-jour"),
                         marker_color=_LISTENER_INK, opacity=0.85), row=1, col=1)
    fig.add_trace(go.Scatter(x=mon["month"], y=mon["streams"], mode="lines",
                             name=t("common.streams", "Streams"),
                             line=dict(color=_SPOTIFY_GREEN, width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=mon["month"], y=mon["streams_per_listener_day"],
                             mode="lines+markers",
                             name=t("spotify_s4a_combined.ratio_short", "Écoutes / auditeur-jour"),
                             line=dict(color="#FF6D00", width=2.5)), row=2, col=1)
    fig.update_yaxes(title_text=t("common.count", "Nombre"), row=1, col=1)
    fig.update_yaxes(title_text=t("spotify_s4a_combined.ratio_axis", "× par auditeur-jour"),
                     row=2, col=1)
    fig.update_layout(height=470, hovermode="x unified",
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")

    st.caption(t("spotify_s4a_combined.audience_caption",
                 "**Auditeurs-jour** : un auditeur unique compté une fois par jour "
                 "d'écoute — quelqu'un qui revient dix jours compte dix fois. Le "
                 "rapport du bas dit donc combien de fois on écoute, pas combien de "
                 "personnes écoutent. Quand il baisse à volume stable, l'audience se "
                 "renouvelle sans se fidéliser."))


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

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=merged["song"], x=merged["streams_total"], orientation="h",
        name=t("spotify_s4a_combined.lifetime", "Cumul à vie"),
        marker_color=_GHOST_INK, hovertemplate="%{x:,.0f}<extra>cumul à vie</extra>"))
    fig.add_trace(go.Bar(
        y=merged["song"], x=merged["recent"], orientation="h",
        name=t("spotify_s4a_combined.recent_window", "{n} derniers jours mesurés")
              .format(n=_MOMENTUM_DAYS),
        marker_color=_SPOTIFY_GREEN,
        hovertemplate="%{x:,.0f}<extra>fenêtre récente</extra>"))
    fig.update_layout(barmode="overlay", height=max(320, 42 * len(merged)),
                      xaxis_title=t("common.streams", "Streams"),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")

    note = t("spotify_s4a_combined.momentum_caption",
             "Barre pleine : les **{n} derniers jours mesurés** (jusqu'au {d}). "
             "Barre grise : le cumul depuis la sortie.").format(
                 n=_MOMENTUM_DAYS, d=horizon.strftime("%d/%m/%Y"))
    if excluded:
        # Un titre écarté se COMPTE. Une exclusion muette est le défaut qu'on vient
        # de corriger ailleurs, dans l'autre sens.
        note += " " + t("spotify_s4a_combined.momentum_excluded",
                        "**{k} titre(s) écarté(s)** : aucune mesure dans cette "
                        "fenêtre.").format(k=excluded)
    st.caption(note)


# ── §4 — décision C : un renvoi, pas une figure ────────────────────────────────
def _render_ads_pointer() -> None:
    st.subheader(t("spotify_s4a_combined.ads_header", "💸 Quand relancer la pub ?"))
    st.markdown(t("spotify_s4a_combined.ads_body",
                  "Le rapprochement entre la dépense publicitaire et les écoutes "
                  "vit sur **🎵 META x Spotify** — budget, résultats et streams sur "
                  "la même échelle de temps. Cette page ne le redit pas : deux "
                  "définitions d'un même chiffre finissent toujours par diverger."))
    if st.button(t("spotify_s4a_combined.goto_meta", "🎵 Ouvrir META x Spotify")):
        goto("meta_x_spotify")


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
    with secondary_analyses():
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
    song = st.selectbox(t("spotify_s4a_combined.select_song", "Titre"),
                        spans["song"].tolist(), key="s4a_detail_song")
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
    fig = go.Figure(go.Scatter(x=df["day"], y=df["streams"], mode="lines",
                               line=dict(color=_SPOTIFY_GREEN, width=2)))
    fig.update_layout(height=320, hovermode="x unified",
                      yaxis_title=t("spotify_s4a_combined.streams_per_day", "Streams / jour"))
    return fig, t("spotify_s4a_combined.detail_caption",
                  "Série démarrée à la **première écoute** ({d}), pas au premier jour "
                  "du fichier : Spotify exporte la timeline du compte et y inscrit 0 "
                  "avant la sortie.").format(
                      d=start.strftime("%d/%m/%Y") if isinstance(start, date) else "—")


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

        spans = _render_clocks(db, frag, params)
        st.markdown("---")
        _frag_releases(frag, params)
        st.markdown("---")
        _render_audience(db, frag, params)
        st.markdown("---")
        _render_momentum(db, spans, frag, params)
        st.markdown("---")
        _render_ads_pointer()
        st.markdown("---")
        _render_secondary(db, spans, frag, params)
