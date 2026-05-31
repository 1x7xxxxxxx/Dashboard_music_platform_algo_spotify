import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import get_artist_id, is_admin


def _default_campaign_index(db, artist_id, available_campaigns: list) -> int:
    """Index of the campaign mapped to the most recent release (else 0)."""
    if not available_campaigns:
        return 0
    try:
        rows = db.fetch_query(
            "SELECT m.campaign_name FROM campaign_track_mapping m "
            "JOIN tracks t ON TRIM(t.track_name) = TRIM(m.track_name) "
            "WHERE m.campaign_name = ANY(%s) "
            "ORDER BY t.release_date DESC NULLS LAST LIMIT 1",
            (available_campaigns,),
        )
        if rows and rows[0][0] in available_campaigns:
            return available_campaigns.index(rows[0][0])
    except Exception:
        pass
    return 0


def _show_body(db, artist_id):
    """Main view body — db.close() is handled by show()."""

    # Campaign↔track mapping is managed exclusively in the dedicated Mapping page
    # (src/dashboard/views/meta_mapping.py). This view only *reads* the mapping.

    # =========================================================================
    # ANALYSE CROISÉE (SMART FILTER)
    # =========================================================================
    st.header("📊 Performance 360°")
    st.caption(
        "ℹ️ Les associations campagne ↔ titre se gèrent dans "
        "**📁 Données → 🔗 Mapping Spotify × Meta Ads (nom de campagne)**."
    )

    try:
        q_camp_list = ("SELECT campaign_name FROM meta_insights_performance_day "
                       "WHERE artist_id = %s GROUP BY campaign_name "
                       "ORDER BY MAX(day_date) DESC NULLS LAST")  # campagne la plus récente en haut
        camp_list_df = db.fetch_df(q_camp_list, (artist_id,))
        available_campaigns = camp_list_df['campaign_name'].tolist()
    except:
        available_campaigns = []

    # --- SÉLECTEUR CAMPAGNE ---
    col_filter, col_date = st.columns([1, 2])

    with col_filter:
        selected_campaign = st.selectbox(
            "Choisir la Campagne",
            options=available_campaigns,
            index=_default_campaign_index(db, artist_id, available_campaigns)
            if available_campaigns else None,
        )

    if not selected_campaign:
        st.info("Sélectionnez une campagne.")
        return

    # Période ancrée au début de la campagne (ici la "release" = lancement campagne)
    camp_start = None
    try:
        df_start = db.fetch_df(
            "SELECT MIN(day_date) AS s FROM meta_insights_performance_day "
            "WHERE artist_id = %s AND campaign_name = %s",
            (artist_id, selected_campaign),
        )
        if not df_start.empty and df_start.iloc[0]['s']:
            camp_start = pd.to_datetime(df_start.iloc[0]['s']).date()
    except Exception:
        pass

    with col_date:
        window = smart_period_filter(
            db, table="meta_insights_performance_day", date_column="day_date",
            artist_id=artist_id, key=f"mxs_{selected_campaign}",
            latest_release=camp_start, default_override="last_release",
        )
        st.caption("Période par défaut = depuis le début de la campagne.")
    start_date, end_date = window.start, window.end

    # --- RÉCUPÉRATION DU TITRE ASSOCIÉ ---
    mapped_track = None
    try:
        res_map = db.fetch_df("SELECT track_name FROM campaign_track_mapping WHERE campaign_name = %s LIMIT 1", (selected_campaign,))
        if not res_map.empty:
            mapped_track = res_map.iloc[0]['track_name']
            st.caption(f"🎵 Titre lié : **{mapped_track}**")
        else:
            st.warning("⚠️ Pas de titre associé. Configurez le lien en haut de page.")
    except: pass

    # =========================================================================
    # 3. RÉCUPÉRATION DES DONNÉES
    # =========================================================================

    # A. META ADS
    q_meta = """
        SELECT day_date as date, spend, results, cpr
        FROM meta_insights_performance_day
        WHERE artist_id = %s AND campaign_name = %s AND day_date >= %s AND day_date <= %s
    """
    df_meta = db.fetch_df(q_meta, (artist_id, selected_campaign, start_date, end_date))

    # B. HYPEDDIT
    q_hypeddit = """
        SELECT date, clicks as hypeddit_clicks, visits as hypeddit_visits
        FROM hypeddit_daily_stats
        WHERE artist_id = %s AND campaign_name = %s AND date >= %s AND date <= %s
    """
    try:
        df_hypeddit = db.fetch_df(q_hypeddit, (artist_id, selected_campaign, start_date, end_date))
    except:
        df_hypeddit = pd.DataFrame()

    # C. SPOTIFY
    df_spotify = pd.DataFrame()
    if mapped_track:
        try:
            q_streams = """
                SELECT date::date, streams
                FROM s4a_song_timeline
                WHERE artist_id = %s AND TRIM(song) = %s AND date >= %s AND date <= %s
                ORDER BY date ASC
            """
            df_streams = db.fetch_df(q_streams, (artist_id, mapped_track.strip(), start_date, end_date))
        except Exception as e:
            st.error(f"Erreur Streams SQL: {e}")
            df_streams = pd.DataFrame()

        try:
            q_pop = """
                SELECT date::date, popularity
                FROM track_popularity_history
                WHERE TRIM(track_name) = %s AND date >= %s AND date <= %s
            """
            df_pop = db.fetch_df(q_pop, (mapped_track.strip(), start_date, end_date))
        except: df_pop = pd.DataFrame()

        if not df_streams.empty:
            df_spotify = df_streams.copy()
            if not df_pop.empty:
                df_spotify['date'] = pd.to_datetime(df_spotify['date'])
                df_pop['date'] = pd.to_datetime(df_pop['date'])
                df_spotify = pd.merge(df_spotify, df_pop, on='date', how='outer')
        elif not df_pop.empty:
            df_spotify = df_pop.copy()

    # =========================================================================
    # 4. FUSION ET NETTOYAGE
    # =========================================================================

    all_dates = pd.concat([
        df_meta['date'] if 'date' in df_meta.columns else pd.Series(dtype='object'),
        df_hypeddit['date'] if 'date' in df_hypeddit.columns else pd.Series(dtype='object'),
        df_spotify['date'] if 'date' in df_spotify.columns else pd.Series(dtype='object')
    ]).dropna().unique()

    if len(all_dates) == 0:
        st.warning("Aucune donnée trouvée.")
        return

    # all_dates may mix datetime.date (raw psycopg2 day_date) and pd.Timestamp
    # (df_spotify after pd.to_datetime) — coerce to one type before sorting,
    # else `sorted()` raises "Cannot compare Timestamp with datetime.date".
    df_master = pd.DataFrame({'date': sorted(pd.to_datetime(all_dates))})

    if not df_meta.empty:
        df_meta['date'] = pd.to_datetime(df_meta['date'])
        df_master = pd.merge(df_master, df_meta, on='date', how='left')

    if not df_hypeddit.empty:
        df_hypeddit['date'] = pd.to_datetime(df_hypeddit['date'])
        df_master = pd.merge(df_master, df_hypeddit, on='date', how='left')

    if not df_spotify.empty:
        df_spotify['date'] = pd.to_datetime(df_spotify['date'])
        df_master = pd.merge(df_master, df_spotify, on='date', how='left')

    # Force conversion to float (cpr handled separately — must stay nullable)
    cols_num = ['spend', 'results', 'hypeddit_clicks', 'hypeddit_visits', 'streams', 'popularity']
    for c in cols_num:
        if c in df_master.columns:
            df_master[c] = pd.to_numeric(df_master[c], errors='coerce').fillna(0).astype(float)

    if 'popularity' in df_master.columns:
        df_master['popularity'] = df_master['popularity'].replace(0, pd.NA).ffill().fillna(0)

    # CPR comes straight from the collector, which already suppresses it (NULL) for
    # non-conversion goals (engagement/traffic). NaN is kept as-is → chart shows a gap,
    # table shows "—". No spend/results recompute — that would fabricate a CPR Meta hid.
    if 'cpr' in df_master.columns:
        df_master['cpr_display'] = pd.to_numeric(df_master['cpr'], errors='coerce')
    else:
        df_master['cpr_display'] = pd.NA

    # =========================================================================
    # 5. GRAPHIQUE AVANCÉ
    # =========================================================================

    # Combined chart — every metric rebased to 100 at the first non-zero day of the
    # period, so disparate scales (€, streams, 0-100 popularity, CPR) share ONE % axis.
    # No overlapping right-hand axes, a single bar-free plot. Absolute values live in the
    # raw-data table and in the hover. Budget = faint filled area for visual context.
    def _index100(col):
        """Return (indexed_to_100_series, raw_series) or (None, None) if no positive base."""
        if col not in df_master.columns:
            return None, None
        raw = pd.to_numeric(df_master[col], errors='coerce')
        positive = raw[raw > 0]
        if positive.empty:
            return None, None
        return raw / positive.iloc[0] * 100, raw

    fig = go.Figure()

    # Budget — faint filled area (context only), indexed like the rest
    idx, raw = _index100('spend')
    if idx is not None:
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=idx, name="Budget (€)", mode='lines',
            line=dict(color='#ff6361', width=0), fill='tozeroy',
            fillcolor='rgba(255, 99, 97, 0.12)',
            customdata=raw, hovertemplate="Budget : %{customdata:,.2f} €<extra></extra>",
        ))

    # (column, legend label, colour, dash, absolute hover format)
    _series = [
        ('results',         "Résultats",         '#003f5c', None,   ',.0f'),
        ('streams',         "Streams / jour",    '#1DB954', None,   ',.0f'),
        ('hypeddit_visits', "Visites Hypeddit",  '#ffa600', None,   ',.0f'),
        ('hypeddit_clicks', "Clics vers Stores", '#58508d', 'dash', ',.0f'),
        ('cpr_display',     "CPR (€)",           '#bc5090', 'dot',  ',.2f'),
        ('popularity',      "Popularité",        '#00D166', None,   ',.0f'),
    ]
    for col, label, color, dash, fmt in _series:
        idx, raw = _index100(col)
        if idx is None:
            continue
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=idx, name=label, mode='lines',
            line=dict(color=color, width=2, dash=dash), customdata=raw,
            hovertemplate=f"{label} : %{{customdata:{fmt}}} (idx %{{y:.0f}})<extra></extra>",
        ))

    fig.update_layout(
        height=560,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        title_text=f"Analyse Détaillée : {selected_campaign}",
        separators=", ",
        xaxis=dict(title="Date", type='date'),
        yaxis=dict(title="Indice (base 100 = début de période)", rangemode='tozero'),
    )
    fig.add_hline(y=100, line_dash="dot", line_color="rgba(0,0,0,0.25)",
                  annotation_text="base 100", annotation_position="top left")

    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Séries indexées (base 100 = 1er jour non nul de la période) pour comparer des "
        "échelles différentes sur un seul axe. Valeurs absolues au survol et dans le tableau."
    )

    # --- TABLEAU ---
    with st.expander("🔎 Voir les données brutes"):
        st.dataframe(
            df_master.sort_values('date', ascending=False).style.format({
                "spend": "{:.2f}",
                "cpr_display": "{:.2f}",
                "streams": lambda v: f"{v:,.0f}".replace(",", " "),
                "popularity": "{:.0f}",
            }, na_rep="—"),
            width="stretch",
        )



def show():
    from src.dashboard.auth import require_plan
    if not require_plan('premium'):
        return

    st.title("🔀 META x SPOTIFY - Analyse ROI")
    st.markdown("---")

    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide."); st.stop()
        artist_id = 1  # admin: defaults to artist 1 — full cross-tenant view in Admin panel
    try:
        _show_body(db, artist_id)
    finally:
        db.close()

if __name__ == "__main__":
    show()
