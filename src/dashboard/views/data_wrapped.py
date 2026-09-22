"""Data Wrapped — la saisie annuelle Spotify for Artists, et son évolution.

Type: Feature
Uses: get_db_connection, fragment_db, secondary_analyses, i18n
Depends on: artist_wrapped
Persists in: artist_wrapped

⚠️ CETTE PAGE N'EST PLUS DANS LE MENU depuis le 2026-09-21. Son contenu est
RENDU par `views/spotify_s4a_combined.py`, où il appartient : les métriques d'un
Wrapped sont des chiffres Spotify for Artists, saisis pour la seule plateforme
que cette page-là raconte. La ROUTE survit — `show()` reste valide, des liens la
visent, et le dépôt garde `process_guide` pour exactement cette raison.

CE QUI EST PARTI AVEC LE DÉPLACEMENT
--------------------------------------
Le « Recap auto », qui recalculait en carrière des chiffres ayant déjà leur page.
Le détail du raisonnement est écrit au-dessus de `_tab_charts`, à l'endroit où
les cinq fonctions vivaient.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import flash, secondary_analyses
from src.dashboard.auth import get_artist_id, is_admin


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_wrapped(db, artist_id):
    if artist_id is None:
        query = """
            SELECT w.*, s.name AS artist_name
            FROM artist_wrapped w
            JOIN saas_artists s ON s.id = w.artist_id
            ORDER BY w.year DESC
        """
        return db.fetch_df(query)
    query = """
        SELECT * FROM artist_wrapped
        WHERE artist_id = %s
        ORDER BY year DESC
    """
    return db.fetch_df(query, (artist_id,))


def _load_row_for_year(db, artist_id, year):
    """Return existing row as dict (keyed by column name), or empty dict if not found."""
    df = db.fetch_df(
        "SELECT * FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def _upsert_wrapped(db, artist_id, year, values: dict):
    db.execute_query(
        """
        INSERT INTO artist_wrapped (
            artist_id, year,
            listeners, streams, hours_listened, countries,
            listener_gain_pct, stream_gain_pct, save_gain_pct, playlist_add_gain_pct,
            saves, playlist_adds,
            top_fans_count, top_fans_rank,
            updated_at
        ) VALUES (
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            NOW()
        )
        ON CONFLICT (artist_id, year) DO UPDATE SET
            listeners           = EXCLUDED.listeners,
            streams             = EXCLUDED.streams,
            hours_listened      = EXCLUDED.hours_listened,
            countries           = EXCLUDED.countries,
            listener_gain_pct       = EXCLUDED.listener_gain_pct,
            stream_gain_pct         = EXCLUDED.stream_gain_pct,
            save_gain_pct           = EXCLUDED.save_gain_pct,
            playlist_add_gain_pct   = EXCLUDED.playlist_add_gain_pct,
            saves               = EXCLUDED.saves,
            playlist_adds       = EXCLUDED.playlist_adds,
            top_fans_count      = EXCLUDED.top_fans_count,
            top_fans_rank       = EXCLUDED.top_fans_rank,
            updated_at          = NOW()
        """,
        (
            artist_id, year,
            values['listeners'], values['streams'], values['hours_listened'],
            values['countries'],
            values['listener_gain_pct'], values['stream_gain_pct'],
            values['save_gain_pct'], values['playlist_add_gain_pct'],
            values['saves'], values['playlist_adds'],
            values['top_fans_count'], values['top_fans_rank'],
        )
    )


def _delete_wrapped(db, artist_id, year):
    db.execute_query(
        "DELETE FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _fmt_big(n):
    if n is None:
        return "—"
    n = int(n)
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _fmt_pct(v):
    if v is None:
        return "—"
    return f"{float(v):+.1f}%"


def _line_chart(df, col, title, color="#1DB954", fmt_fn=None):
    df_plot = df[['year', col]].dropna().sort_values('year')
    if df_plot.empty:
        return None
    fig = px.line(
        df_plot, x='year', y=col,
        markers=True,
        title=title,
        color_discrete_sequence=[color],
        labels={'year': '', col: ''},
    )
    fig.update_traces(
        mode='lines+markers',
        line=dict(width=2.5),
        marker=dict(size=8),
    )
    if fmt_fn:
        fig.update_traces(
            text=[fmt_fn(v) for v in df_plot[col]],
            textposition='top center',
            mode='lines+markers+text',
        )
    fig.update_layout(
        xaxis=dict(dtick=1, tickformat='d'),
        yaxis_title='',
        showlegend=False,
        hovermode='x unified',
        margin=dict(t=40, b=20),
        height=260,
    )
    return fig


def _bar_gain_chart(df, col, title, pos_color="#1DB954", neg_color="#e63946",
                    fmt_fn=_fmt_big):
    df_plot = df[['year', col]].dropna().sort_values('year')
    if df_plot.empty:
        return None
    colors = [pos_color if v >= 0 else neg_color for v in df_plot[col]]
    fig = go.Figure(go.Bar(
        x=df_plot['year'],
        y=df_plot[col],
        marker_color=colors,
        text=[fmt_fn(v) for v in df_plot[col]],
        textposition='outside',
    ))
    fig.update_layout(
        title=title,
        xaxis=dict(dtick=1, tickformat='d'),
        yaxis_title='',
        showlegend=False,
        hovermode='x unified',
        margin=dict(t=40, b=20),
        height=260,
    )
    return fig


def _multi_line_chart(df, series, title, log_scale=False):
    """Combine several volume metrics on one chart. series: list of (col, label, color)."""
    df_s = df.sort_values('year')
    fig = go.Figure()
    has_data = False
    for col, label, color in series:
        if col not in df_s.columns:
            continue
        sub = df_s[['year', col]].dropna()
        if sub.empty:
            continue
        has_data = True
        fig.add_trace(go.Scatter(
            x=sub['year'], y=sub[col],
            mode='lines+markers', name=label,
            line=dict(width=2.5, color=color), marker=dict(size=8),
            hovertemplate=f"{label}: %{{y:,.0f}}<extra></extra>",
        ))
    if not has_data:
        return None
    fig.update_layout(
        title=title,
        xaxis=dict(dtick=1, tickformat='d'),
        yaxis=dict(title='', type='log' if log_scale else 'linear'),
        hovermode='x unified',
        margin=dict(t=60, b=20),
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    return fig


# ---------------------------------------------------------------------------
# Recap auto — all-time multi-platform bilan (read-only, reuses kpi_helpers)
# ---------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════
# LE « RECAP AUTO » A ÉTÉ SUPPRIMÉ le 2026-09-21 — demandé, et mesuré redondant.
# ═══════════════════════════════════════════════════════════════════════════
#
# Cinq blocs partaient avec lui : `_recap_spotify`, `_recap_platforms`,
# `_recap_revenue`, `_recap_ml`, `_recap_freshness`. Chacun recalculait, en
# « carrière / all-time », des chiffres qui ont déjà leur page :
#
#     🎧 Spotify            → 🎵 Spotify & Spotify for Artists
#     📺 Autres plateformes → Apple, YouTube, SoundCloud, Instagram
#     💶 Revenus            → 💶 Revenus (iMusician, SACEM, Prévisions)
#     🔮 Highlight ML       → 🚀 Prédiction déclenchement algos
#     🩺 Fraîcheur          → 🚦 Santé onboarding + 🗄️ Santé des données
#
# Ce n'est pas seulement du doublon d'écran : c'est une SECONDE DÉFINITION de
# chaque chiffre. Le dépôt a déjà payé cette forme — un total Apple différent
# entre deux pages du même produit, pour le même artiste au même instant. Une
# page qui re-somme ce qu'une autre somme déjà finit par en différer.
#
# Ce qui reste ici est ce qui n'existe nulle part ailleurs : la SAISIE annuelle
# Spotify for Artists (Wrapped), son évolution, et ses données brutes.


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

@st.fragment
def _tab_charts(artist_options: dict) -> None:
    """L'onglet Évolution — rejoué SEUL quand on change d'artiste.

    @st.fragment (R118, 2026-09-16). C'est la deuxième vue la plus chère de la
    session mesurée le 2026-09-16 : **357,7 ms de phase `view`** contre 13,4 ms de
    chrome. Changer le sélecteur rejouait tout le script — les quatre onglets, dont
    `st.tabs` exécute TOUS les corps, plus la barre latérale.

    ⚠️ Elle ouvre sa PROPRE connexion, et c'est obligatoire, pas un style : son
    sélecteur pilote `_load_wrapped(db, …)`, donc elle relit la base à chaque
    changement — alors que la connexion de `show()` est fermée par son `finally` dès
    la fin du rendu complet. Un fragment qui capturerait celle-là la ré-emprunterait
    au pool sans jamais la rendre : une fuite par session, sur un pool à 10. Garde :
    `tests/test_a_fragment_never_captures_a_connection.py`.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, _artist_id):
        # Même règle que la saisie : pas de question quand la réponse est forcée.
        chart_artist_id = _artiste(artist_options, "chart_artist")
        df = _load_wrapped(db, chart_artist_id)

        if df.empty:
            st.info(t("data_wrapped.charts_no_data",
                      "Aucune donnée. Renseignez au moins deux années via l'onglet Saisie."))
        else:
            # KPI row — latest year
            latest = df.iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(t("data_wrapped.field_listeners", "Listeners"),
                      _fmt_big(latest.get('listeners')),
                      delta=_fmt_pct(latest.get('listener_gain_pct')))
            k2.metric(t("data_wrapped.col_streams", "Streams"),
                      _fmt_big(latest.get('streams')),
                      delta=_fmt_pct(latest.get('stream_gain_pct')))
            k3.metric(t("data_wrapped.field_saves", "Saves"),
                      _fmt_big(latest.get('saves')),
                      delta=_fmt_pct(latest.get('save_gain_pct')))
            k4.metric(t("data_wrapped.kpi_countries", "Pays"),
                      _fmt_big(latest.get('countries')))

            st.markdown("---")

            # Combined evolution — listeners / streams / saves / playlist adds
            st.markdown(t("data_wrapped.combined_header", "#### Évolution combinée"))
            log_scale = st.toggle(
                t("data_wrapped.log_scale", "Échelle logarithmique"),
                value=False, key="wrapped_log_scale",
                help=t("data_wrapped.log_scale_help",
                       "Recommandé si les volumes diffèrent fortement "
                       "(ex: streams ≫ saves), pour voir toutes les courbes."),
            )
            fig = _multi_line_chart(
                df,
                [
                    ('listeners', 'Listeners', '#1DB954'),
                    ('streams', 'Streams', '#457b9d'),
                    ('saves', 'Saves', '#e9c46a'),
                    ('playlist_adds', 'Playlist adds', '#f4a261'),
                ],
                t("data_wrapped.chart_combined_title",
                  "Listeners · Streams · Saves · Playlist adds"),
                log_scale=log_scale,
            )
            # ── LES TROIS SUR UNE LIGNE — 2026-09-22 ────────────────────────
            #
            # Demandé en regardant l'écran : « mets les 3 graphiques de Spotify
            # Wrapped sur la même ligne pour gagner en visibilité ». Le combiné
            # était pleine largeur, puis Pays et Heures côte à côte en dessous —
            # donc deux rangées, et un défilement entre trois figures qui
            # racontent la même année.
            #
            # Le sous-titre « Pays & écoute » disparaît avec la rangée qu'il
            # coiffait : chaque figure porte déjà son propre titre.
            c_vol, c_pays, c_heures = st.columns(3)
            with c_vol:
                if fig:
                    st.plotly_chart(fig, width="stretch")
            with c_pays:
                fig_p = _line_chart(df, 'countries',
                                    t("data_wrapped.chart_countries_reached",
                                      "Pays touchés"),
                                    color="#457b9d", fmt_fn=_fmt_big)
                if fig_p:
                    st.plotly_chart(fig_p, width="stretch")
            with c_heures:
                fig_h = _line_chart(df, 'hours_listened',
                                    t("data_wrapped.chart_hours_listened",
                                      "Heures d'écoute"),
                                    color="#e9c46a", fmt_fn=_fmt_big)
                if fig_h:
                    st.plotly_chart(fig_h, width="stretch")

            # Quatre graphiques de GAIN : ils raffinent la lecture des volumes
            # ci-dessus, aucun ne fait décider seul. Repliés — rien n'est
            # supprimé, tout reste à un clic. `secondary_analyses()` a été
            # écrit le 2026-08-12 pour la remarque « réduire le nombre de
            # graphs » et n'était appliqué sur aucune des cinq vues denses.
            with secondary_analyses(t("data_wrapped.gains_expander",
                                      "📊 Gains annuels (%) — détail")):
                # Annual gains (%)
                st.markdown(t("data_wrapped.annual_gains_header", "#### Gains annuels (%)"))
                col_lg, col_stg = st.columns(2)
                with col_lg:
                    fig = _bar_gain_chart(df, 'listener_gain_pct',
                                          t("data_wrapped.chart_listener_gain",
                                            "Gain listeners / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                with col_stg:
                    fig = _bar_gain_chart(df, 'stream_gain_pct',
                                          t("data_wrapped.chart_stream_gain",
                                            "Gain streams / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")

                col_sg, col_pg = st.columns(2)
                with col_sg:
                    fig = _bar_gain_chart(df, 'save_gain_pct',
                                          t("data_wrapped.chart_save_gain",
                                            "Gain saves / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                with col_pg:
                    fig = _bar_gain_chart(df, 'playlist_add_gain_pct',
                                          t("data_wrapped.chart_playlist_gain",
                                            "Gain playlist adds / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")

            # Super-fans — fans who ranked the artist in their top N
            top_rows = df[df['top_fans_count'].notna()][
                ['year', 'top_fans_count', 'top_fans_rank']
            ].sort_values('year')
            if not top_rows.empty:
                st.markdown(t("data_wrapped.superfans_header",
                              "#### Super-fans (vous dans leur top artistes)"))
                fig = _line_chart(df, 'top_fans_count',
                                  t("data_wrapped.chart_superfans",
                                    "Fans vous ayant en top artiste"),
                                  color="#9d4edd", fmt_fn=_fmt_big)
                if fig:
                    st.plotly_chart(fig, width="stretch")
                st.dataframe(
                    top_rows.rename(columns={
                        'year': t("data_wrapped.col_year", "Année"),
                        'top_fans_count': t("data_wrapped.col_fans_count", "Nb fans"),
                        'top_fans_rank': t("data_wrapped.col_fans_rank", "Rang (top N)"),
                    }),
                    hide_index=True,
                    width="stretch",
                )




def render_wrapped_section(db, artist_id: int) -> None:
    """La section Wrapped, rendue dans une page qui a DÉJÀ sa connexion.

    Ajoutée le 2026-09-21 pour l'intégration dans `spotify_s4a_combined`. Elle
    ne prend ni ne ferme de connexion : c'est celle de l'appelant (règle #9,
    une connexion par vue).

    ⚠️ Elle N'OUVRE PAS de sélecteur d'artiste — la page hôte a déjà résolu son
    locataire. Le sélecteur de `show()` existe pour l'usage ADMIN de la route
    autonome, qui survit : des liens la visent, et le dépôt garde
    `process_guide` pour exactement cette raison.
    """
    _render_wrapped_body(db, {"": artist_id})


def _artiste(artist_options: dict, cle: str):
    """L'artiste visé, et un sélecteur SEULEMENT s'il y a un choix à faire.

    ⚠️ POSÉ LE 2026-09-22, demandé en regardant l'écran : « pour le choix d'artiste
    il faudrait automatiquement mettre celui du compte ».

    Quatre sélecteurs d'artiste vivaient sur cette page — saisie, suppression,
    évolution, données. Pour un artiste, `artist_options` ne porte qu'UNE entrée :
    les quatre lui demandaient donc de choisir entre lui-même et rien, quatre fois,
    et il devait le faire avant de pouvoir saisir. Un choix qui n'en est pas un est
    une étape de trop.

    Le sélecteur SURVIT quand il y a plusieurs options, parce qu'alors il sert
    vraiment : `show()` est la route autonome et un admin y voit toute la flotte.
    C'est le même critère que partout ailleurs dans ce dépôt — on ne supprime pas la
    possibilité, on supprime la question quand la réponse est forcée.
    """
    noms = list(artist_options.keys())
    if len(noms) <= 1:
        return artist_options[noms[0]] if noms else None
    return artist_options[st.selectbox(
        t("data_wrapped.artist_label", "Artiste"), noms, key=cle)]


def _render_wrapped_body(db, artist_options: dict) -> None:
    """Saisie → évolution → données, sur une connexion FOURNIE.

    Extraite de `show()` le 2026-09-21 pour que `spotify_s4a_combined` puisse
    rendre la même section sans ouvrir une seconde connexion (règle #9). Les
    deux appelants passent donc la leur.
    """
    # L'ORDRE EST LINÉAIRE DEPUIS LE 2026-09-21 : saisie, puis évolution,
    # puis données. Demandé — « intègre le panneau évolution en dessous de
    # saisie et le panneau données ».
    #
    # Et les onglets partent avec le récap, pour une raison mesurée : `st.tabs`
    # exécute le corps de TOUS ses onglets à chaque rendu. Quatre onglets, c'est
    # quatre fois le travail pour un seul regardé — c'est ce qui faisait de
    # cette page la deuxième plus chère de la session du 2026-09-16 (357,7 ms
    # de phase `view` contre 13,4 ms de chrome). Trois sections empilées ne
    # coûtent pas moins en soi ; ce qui coûte moins, c'est d'en avoir supprimé
    # une sur quatre — la plus lourde, qui interrogeait cinq domaines.
    if True:
        st.subheader(t("data_wrapped.form_header", "Ajouter / modifier une année"))

        # L'ARTISTE EST CELUI DU COMPTE quand il n'y a qu'un candidat (2026-09-22).
        # L'année reste pleine largeur : c'est la seule chose à choisir ici.
        target_artist_id = _artiste(artist_options, "form_artist")
        year = st.number_input(
            t("data_wrapped.year_label", "Année"),
            min_value=2015, max_value=datetime.now().year,
            value=datetime.now().year - 1, step=1, key="form_year"
        )

        # Pre-fill from DB if row exists
        existing = _load_row_for_year(db, target_artist_id, int(year))
        g = existing.get  # shorthand

        st.markdown("---")
        st.markdown(t("data_wrapped.section_audience", "**Audience**"))
        c1, c2, c3 = st.columns(3)
        with c1:
            listeners = st.number_input(
                t("data_wrapped.field_listeners", "Listeners"),
                min_value=0, value=int(g('listeners') or 0), step=1000
            )
        with c2:
            listener_gain_pct = st.number_input(
                t("data_wrapped.field_listener_gain", "Gain listeners (%)"),
                value=float(g('listener_gain_pct') or 0.0),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )
        with c3:
            countries = st.number_input(
                t("data_wrapped.field_countries", "Pays"),
                min_value=0, value=int(g('countries') or 0), step=1
            )

        st.markdown(t("data_wrapped.section_streams", "**Streams**"))
        c4, c5, c6 = st.columns(3)
        with c4:
            streams = st.number_input(
                t("data_wrapped.field_total_streams", "Streams totaux"),
                min_value=0, value=int(g('streams') or 0), step=10000
            )
        with c5:
            stream_gain_pct = st.number_input(
                t("data_wrapped.field_stream_gain", "Gain streams (%)"),
                value=float(g('stream_gain_pct') or 0.0),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )
        with c6:
            hours_listened = st.number_input(
                t("data_wrapped.field_hours_listened", "Heures d'écoute"),
                min_value=0.0,
                value=float(g('hours_listened') or 0.0), step=100.0, format="%.1f"
            )

        st.markdown(t("data_wrapped.section_engagement", "**Engagement**"))
        c7, c8, c9, c10 = st.columns(4)
        with c7:
            saves = st.number_input(
                t("data_wrapped.field_saves", "Saves"),
                min_value=0, value=int(g('saves') or 0), step=100
            )
        with c8:
            save_gain_pct = st.number_input(
                t("data_wrapped.field_save_gain", "Gain saves (%)"),
                value=float(g('save_gain_pct') or 0.0),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )
        with c9:
            playlist_adds = st.number_input(
                t("data_wrapped.field_playlist_adds", "Playlist adds"),
                min_value=0, value=int(g('playlist_adds') or 0), step=100
            )
        with c10:
            playlist_add_gain_pct = st.number_input(
                t("data_wrapped.field_playlist_add_gain", "Gain playlist adds (%)"),
                value=float(g('playlist_add_gain_pct') or 0.0),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )

        st.markdown(t("data_wrapped.section_superfans",
                      "**Super-fans (vous dans leur top artistes)**"))
        ct1, ct2 = st.columns(2)
        with ct1:
            top_fans_count = st.number_input(
                t("data_wrapped.field_fans_count", "Nombre de fans"),
                min_value=0,
                value=int(g('top_fans_count') or 0), step=1,
                help=t("data_wrapped.fans_count_help",
                       "Fans qui vous avaient en top artiste, ex: 11")
            )
        with ct2:
            top_fans_rank = st.number_input(
                t("data_wrapped.field_fans_rank", "Rang (vous dans leur top N)"),
                min_value=1,
                value=int(g('top_fans_rank') or 5), step=1,
                help=t("data_wrapped.fans_rank_help", "Ex: 5 = vous étiez dans leur top 5")
            )

        st.markdown("---")
        if st.button(t("data_wrapped.btn_save", "💾 Enregistrer"), type="primary"):
            try:
                _upsert_wrapped(db, target_artist_id, int(year), {
                    'listeners': listeners, 'streams': streams,
                    'hours_listened': hours_listened, 'countries': countries,
                    'listener_gain_pct': listener_gain_pct,
                    'stream_gain_pct': stream_gain_pct,
                    'save_gain_pct': save_gain_pct,
                    'playlist_add_gain_pct': playlist_add_gain_pct,
                    'saves': saves, 'playlist_adds': playlist_adds,
                    'top_fans_count': top_fans_count,
                    'top_fans_rank': top_fans_rank,
                })
                flash(t("data_wrapped.save_success",
                             "✅ Données {year} enregistrées.").format(year=int(year)))
                st.rerun()
            except Exception as e:
                st.error(t("data_wrapped.error_generic", "Erreur : {err}").format(err=e))

    # ── Évolution, sous la saisie ───────────────────────────────────────
    st.markdown("---")
    _tab_charts(artist_options)

    # ── LA SUPPRESSION, TOUT EN BAS — 2026-09-22 ────────────────────────
    #
    # Demandé en regardant l'écran : « déplace supprimer une année tout en bas
    # après les graphiques d'évolution ». Elle vivait sous le formulaire de saisie,
    # donc un geste destructeur était le voisin immédiat d'un geste de création —
    # et il fallait passer devant lui pour atteindre les courbes.
    #
    # En bas, l'ordre de la page raconte : je saisis, je regarde ce que ça donne, et
    # si je me suis trompé je corrige. La suppression reste dans un `st.expander`
    # REFERMÉ : c'est le seul geste irréversible de cette page.
    st.markdown("---")
    with st.expander(t("data_wrapped.expander_delete", "🗑️ Supprimer une année")):
        del_artist_id = _artiste(artist_options, "del_artist")
        del_year = st.number_input(
            t("data_wrapped.year_label", "Année"),
            min_value=2015, max_value=datetime.now().year,
            value=datetime.now().year - 1, step=1, key="del_year"
        )
        if st.button(t("data_wrapped.btn_delete", "🗑️ Supprimer"), type="secondary"):
            try:
                _delete_wrapped(db, del_artist_id, int(del_year))
                flash(t("data_wrapped.delete_success",
                        "Année {year} supprimée.").format(year=int(del_year)))
                st.rerun()
            except Exception as e:
                st.error(t("data_wrapped.error_generic",
                           "Erreur : {err}").format(err=e))

    # ⚠️ LE TABLEAU RÉCAP A ÉTÉ RETIRÉ le 2026-09-22, demandé en regardant l'écran :
    # « supprime le tableau récap car déjà la visualisation via graphique ».
    #
    # C'était une section « Données brutes » de treize colonnes — listeners, streams,
    # heures, pays, saves, playlist adds, super-fans, et les quatre pourcentages de
    # gain — plus son propre sélecteur d'artiste. Chacune de ces colonnes est déjà une
    # COURBE au-dessus : le tableau redisait en chiffres ce que les figures montrent
    # en formes, sur une page dont la valeur est justement de voir l'évolution.
    #
    # ⚠️ CE QUI EST PERDU, et le dire est le point : la valeur EXACTE de chaque année.
    # Une courbe se lit à l'œil, un tableau se lit au chiffre — et la saisie
    # elle-même sert de relecture, puisqu'elle recharge l'année choisie. Le petit
    # tableau des super-fans SURVIT, parce qu'il porte `top_fans_rank`, que AUCUNE
    # figure ne dessine.


def show():
    # « Spotify Wrapped (bilan annuel) » depuis le 2026-09-22 : « Data Wrapped »
    # était le nom du fichier, pas celui de la chose. Ce qu'on saisit ici est le
    # Wrapped for Artists de Spotify, une fois l'an.
    st.title(t("data_wrapped.title", "🎁 Spotify Wrapped (bilan annuel)"))
    st.caption(t(
        "data_wrapped.intro",
        "Les métriques annuelles de ton **Spotify Wrapped for Artists**, saisies à "
        "la main : elles ne sont dans aucune API. Saisie, puis évolution année par "
        "année, puis les données brutes."
    ))

    db = get_db_connection()
    if db is None:
        st.error(t("data_wrapped.db_unreachable", "Base de données inaccessible."))
        return

    # Les fragments de cette page REUTILISENT cette connexion pendant un rendu
    # complet (~13 ms de poignee SCRAM economises chacun) et n'en ouvrent une que
    # lors d'un rerun de fragment. Libere AVANT `close()` : entre les deux, un
    # fragment verrait une connexion fermee dans la fente.
    from src.dashboard.utils.fragment_db import declare_page_db, release_page_db

    declare_page_db(db)
    try:
        # Resolve artist context — include inactive artists (historical data entry)
        if is_admin():
            artists_df = db.fetch_df(
                "SELECT id, name FROM saas_artists ORDER BY name"
            )
            if artists_df.empty:
                st.warning(t("data_wrapped.no_artist", "Aucun artiste en base."))
                return
            artist_options = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        else:
            aid = get_artist_id()
            # Guard (CLAUDE.md rule #7): a non-admin with no artist_id must never fall
            # through to target_artist_id=None, which _load_wrapped treats as the admin
            # all-tenants query → cross-tenant leak. Stop the session instead.
            if aid is None:
                st.error(t("data_wrapped.session_invalid", "Session invalide."))
                st.stop()
            name_row = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (aid,))
            name = name_row[0][0] if name_row else f"Artiste {aid}"
            artist_options = {name: aid}

        _render_wrapped_body(db, artist_options)

    finally:
        release_page_db()
        db.close()
