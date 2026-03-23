"""Data Wrapped — annual Spotify for Artists metrics entry and evolution charts."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
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
    """Return existing row as dict, or empty dict if not found."""
    rows = db.fetch_query(
        "SELECT * FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )
    if not rows:
        return {}
    cols = [
        'id', 'artist_id', 'year', 'listeners', 'streams', 'hours_listened',
        'countries', 'listener_gain', 'stream_gain', 'save_gain',
        'playlist_add_gain', 'saves', 'playlist_adds',
        'top_artist_name', 'top_artist_fan_pct', 'updated_at'
    ]
    return dict(zip(cols, rows[0]))


def _upsert_wrapped(db, artist_id, year, values: dict):
    db.execute_query(
        """
        INSERT INTO artist_wrapped (
            artist_id, year,
            listeners, streams, hours_listened, countries,
            listener_gain, stream_gain, save_gain, playlist_add_gain,
            saves, playlist_adds,
            top_artist_name, top_artist_fan_pct,
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
            listener_gain       = EXCLUDED.listener_gain,
            stream_gain         = EXCLUDED.stream_gain,
            save_gain           = EXCLUDED.save_gain,
            playlist_add_gain   = EXCLUDED.playlist_add_gain,
            saves               = EXCLUDED.saves,
            playlist_adds       = EXCLUDED.playlist_adds,
            top_artist_name     = EXCLUDED.top_artist_name,
            top_artist_fan_pct  = EXCLUDED.top_artist_fan_pct,
            updated_at          = NOW()
        """,
        (
            artist_id, year,
            values['listeners'], values['streams'], values['hours_listened'],
            values['countries'],
            values['listener_gain'], values['stream_gain'],
            values['save_gain'], values['playlist_add_gain'],
            values['saves'], values['playlist_adds'],
            values['top_artist_name'] or None, values['top_artist_fan_pct'],
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


def _bar_gain_chart(df, col, title, pos_color="#1DB954", neg_color="#e63946"):
    df_plot = df[['year', col]].dropna().sort_values('year')
    if df_plot.empty:
        return None
    colors = [pos_color if v >= 0 else neg_color for v in df_plot[col]]
    fig = go.Figure(go.Bar(
        x=df_plot['year'],
        y=df_plot[col],
        marker_color=colors,
        text=[_fmt_big(v) for v in df_plot[col]],
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


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

def show():
    st.title("🎁 Data Wrapped — Bilan annuel")
    st.markdown(
        "Saisie manuelle des métriques annuelles Spotify for Artists "
        "(téléchargées en fin d'année) et évolution année par année."
    )

    tab_form, tab_charts, tab_data = st.tabs(["✏️ Saisie", "📊 Évolution", "🗃️ Données"])

    db = get_db_connection()
    if db is None:
        st.error("Base de données inaccessible.")
        return

    try:
        # Resolve artist context
        if is_admin():
            artists_df = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
            )
            if artists_df.empty:
                st.warning("Aucun artiste actif.")
                return
            artist_options = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        else:
            aid = get_artist_id()
            artist_options = {f"Artiste {aid}": aid}

        # ── Onglet 1 : Formulaire ───────────────────────────────────────────
        with tab_form:
            st.subheader("Ajouter / modifier une année")

            col_a, col_b = st.columns(2)
            with col_a:
                selected_name = st.selectbox(
                    "Artiste", list(artist_options.keys()), key="form_artist"
                )
                target_artist_id = artist_options[selected_name]
            with col_b:
                year = st.number_input(
                    "Année", min_value=2015, max_value=datetime.now().year,
                    value=datetime.now().year - 1, step=1, key="form_year"
                )

            # Pre-fill from DB if row exists
            existing = _load_row_for_year(db, target_artist_id, int(year))
            g = existing.get  # shorthand

            st.markdown("---")
            st.markdown("**Audience**")
            c1, c2, c3 = st.columns(3)
            with c1:
                listeners = st.number_input(
                    "Listeners", min_value=0, value=int(g('listeners') or 0), step=1000
                )
            with c2:
                listener_gain = st.number_input(
                    "Gain listeners", value=int(g('listener_gain') or 0), step=100
                )
            with c3:
                countries = st.number_input(
                    "Pays", min_value=0, value=int(g('countries') or 0), step=1
                )

            st.markdown("**Streams**")
            c4, c5, c6 = st.columns(3)
            with c4:
                streams = st.number_input(
                    "Streams totaux", min_value=0, value=int(g('streams') or 0), step=10000
                )
            with c5:
                stream_gain = st.number_input(
                    "Gain streams", value=int(g('stream_gain') or 0), step=1000
                )
            with c6:
                hours_listened = st.number_input(
                    "Heures d'écoute", min_value=0.0,
                    value=float(g('hours_listened') or 0.0), step=100.0, format="%.1f"
                )

            st.markdown("**Engagement**")
            c7, c8, c9, c10 = st.columns(4)
            with c7:
                saves = st.number_input(
                    "Saves", min_value=0, value=int(g('saves') or 0), step=100
                )
            with c8:
                save_gain = st.number_input(
                    "Gain saves", value=int(g('save_gain') or 0), step=100
                )
            with c9:
                playlist_adds = st.number_input(
                    "Playlist adds", min_value=0, value=int(g('playlist_adds') or 0), step=100
                )
            with c10:
                playlist_add_gain = st.number_input(
                    "Gain playlist adds", value=int(g('playlist_add_gain') or 0), step=100
                )

            st.markdown("**Top artiste similaire**")
            ct1, ct2 = st.columns(2)
            with ct1:
                top_artist_name = st.text_input(
                    "Artiste (top fans)", value=g('top_artist_name') or "",
                    placeholder="Ex: Nekfeu"
                )
            with ct2:
                top_artist_fan_pct = st.number_input(
                    "% fans communs", min_value=0.0, max_value=100.0,
                    value=float(g('top_artist_fan_pct') or 0.0),
                    step=0.1, format="%.1f"
                )

            st.markdown("---")
            if st.button("💾 Enregistrer", type="primary"):
                try:
                    _upsert_wrapped(db, target_artist_id, int(year), {
                        'listeners': listeners, 'streams': streams,
                        'hours_listened': hours_listened, 'countries': countries,
                        'listener_gain': listener_gain, 'stream_gain': stream_gain,
                        'save_gain': save_gain, 'playlist_add_gain': playlist_add_gain,
                        'saves': saves, 'playlist_adds': playlist_adds,
                        'top_artist_name': top_artist_name,
                        'top_artist_fan_pct': top_artist_fan_pct,
                    })
                    st.success(f"✅ Données {int(year)} enregistrées.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

            # Delete expander
            with st.expander("🗑️ Supprimer une année"):
                del_name = st.selectbox(
                    "Artiste", list(artist_options.keys()), key="del_artist"
                )
                del_artist_id = artist_options[del_name]
                del_year = st.number_input(
                    "Année", min_value=2015, max_value=datetime.now().year,
                    value=datetime.now().year - 1, step=1, key="del_year"
                )
                if st.button("🗑️ Supprimer", type="secondary"):
                    try:
                        _delete_wrapped(db, del_artist_id, int(del_year))
                        st.success(f"Année {int(del_year)} supprimée.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

        # ── Onglet 2 : Évolution ────────────────────────────────────────────
        with tab_charts:
            # Artist selector (separate from form tab)
            chart_name = st.selectbox(
                "Artiste", list(artist_options.keys()), key="chart_artist"
            )
            chart_artist_id = artist_options[chart_name]
            df = _load_wrapped(db, chart_artist_id)

            if df.empty:
                st.info("Aucune donnée. Renseignez au moins deux années via l'onglet Saisie.")
            else:
                # KPI row — latest year
                latest = df.iloc[0]
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Listeners", _fmt_big(latest.get('listeners')),
                          delta=_fmt_big(latest.get('listener_gain')))
                k2.metric("Streams", _fmt_big(latest.get('streams')),
                          delta=_fmt_big(latest.get('stream_gain')))
                k3.metric("Saves", _fmt_big(latest.get('saves')),
                          delta=_fmt_big(latest.get('save_gain')))
                k4.metric("Pays", _fmt_big(latest.get('countries')))

                st.markdown("---")

                # Section — Audience
                st.markdown("#### Audience")
                col_l, col_c = st.columns(2)
                with col_l:
                    fig = _line_chart(df, 'listeners', "Listeners", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                with col_c:
                    fig = _line_chart(df, 'countries', "Pays touchés",
                                      color="#457b9d", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                fig = _bar_gain_chart(df, 'listener_gain', "Gain listeners / an")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### Streams & Écoute")
                col_s, col_h = st.columns(2)
                with col_s:
                    fig = _line_chart(df, 'streams', "Streams", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                with col_h:
                    fig = _line_chart(df, 'hours_listened', "Heures d'écoute",
                                      color="#e9c46a", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                fig = _bar_gain_chart(df, 'stream_gain', "Gain streams / an")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### Engagement")
                col_sv, col_pl = st.columns(2)
                with col_sv:
                    fig = _line_chart(df, 'saves', "Saves", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                with col_pl:
                    fig = _line_chart(df, 'playlist_adds', "Playlist adds",
                                      color="#f4a261", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                col_sg, col_pg = st.columns(2)
                with col_sg:
                    fig = _bar_gain_chart(df, 'save_gain', "Gain saves / an")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                with col_pg:
                    fig = _bar_gain_chart(df, 'playlist_add_gain', "Gain playlist adds / an")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                # Top artist similarity
                top_rows = df[df['top_artist_name'].notna()][
                    ['year', 'top_artist_name', 'top_artist_fan_pct']
                ].sort_values('year')
                if not top_rows.empty:
                    st.markdown("#### Top artiste similaire")
                    st.dataframe(
                        top_rows.rename(columns={
                            'year': 'Année',
                            'top_artist_name': 'Artiste',
                            'top_artist_fan_pct': '% fans communs',
                        }),
                        hide_index=True,
                        use_container_width=True,
                    )

        # ── Onglet 3 : Données brutes ────────────────────────────────────────
        with tab_data:
            data_name = st.selectbox(
                "Artiste", list(artist_options.keys()), key="data_artist"
            )
            data_artist_id = artist_options[data_name]
            df_raw = _load_wrapped(db, data_artist_id)

            if df_raw.empty:
                st.info("Aucune donnée enregistrée.")
            else:
                display_cols = [
                    'year', 'listeners', 'listener_gain', 'streams', 'stream_gain',
                    'hours_listened', 'countries', 'saves', 'save_gain',
                    'playlist_adds', 'playlist_add_gain',
                    'top_artist_name', 'top_artist_fan_pct',
                ]
                rename_map = {
                    'year': 'Année', 'listeners': 'Listeners',
                    'listener_gain': '△ Listeners', 'streams': 'Streams',
                    'stream_gain': '△ Streams', 'hours_listened': 'Heures écoute',
                    'countries': 'Pays', 'saves': 'Saves', 'save_gain': '△ Saves',
                    'playlist_adds': 'Playlist adds', 'playlist_add_gain': '△ PL adds',
                    'top_artist_name': 'Top artiste', 'top_artist_fan_pct': '% fans communs',
                }
                existing_cols = [c for c in display_cols if c in df_raw.columns]
                st.dataframe(
                    df_raw[existing_cols].rename(columns=rename_map),
                    hide_index=True,
                    use_container_width=True,
                )

    finally:
        db.close()
