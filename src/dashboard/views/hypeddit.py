"""Page Hypeddit - Saisie Manuelle & Analyse Globale (Multi-Axes)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import get_artist_id, is_admin

# --- FONCTION DE CALLBACK POUR LE RESET ---
def clear_form_data():
    """Réinitialise les valeurs du formulaire dans le session state."""
    st.session_state["h_visits"] = 0
    st.session_state["h_clicks"] = 0
    if "h_new_camp_name" in st.session_state:
        st.session_state["h_new_camp_name"] = ""


def add_campaign_stats(db, campaign_name: str, date, visits: int, clicks: int):
    """Ajoute ou met à jour les statistiques d'une campagne.

    Le budget n'est plus saisi côté Hypeddit : la dépense publicitaire réelle est
    celle de Meta Ads (ROI Breakeven). La colonne DB `budget` reste à sa valeur par
    défaut (0). Seules les visites/clics (vraies métriques smart-link) sont saisies.
    """
    artist_id = _resolve_artist_id_or_none()
    if artist_id is None:
        return False, t("hypeddit.invalid_session", "❌ Session invalide.")

    try:
        # 1. Assurer que la campagne existe
        campaign_data = [{
            'artist_id': artist_id,
            'campaign_name': campaign_name,
            'is_active': True
        }]

        db.upsert_many(
            table='hypeddit_campaigns',
            data=campaign_data,
            conflict_columns=['artist_id', 'campaign_name'],
            update_columns=['is_active', 'updated_at']
        )

        # 2. Stats
        stats_data = [{
            'artist_id': artist_id,
            'campaign_name': campaign_name,
            'date': date,
            'visits': visits,
            'clicks': clicks
        }]

        db.upsert_many(
            table='hypeddit_daily_stats',
            data=stats_data,
            conflict_columns=['artist_id', 'campaign_name', 'date'],
            update_columns=['visits', 'clicks', 'updated_at']
        )

        return True, t("hypeddit.save_success", "✅ Données enregistrées avec succès")

    except Exception as e:
        return False, t("hypeddit.save_error", "❌ Erreur: {err}").format(err=e)


def _resolve_artist_id_or_none() -> int | None:
    """LA décision du locataire, en un seul endroit — sans décider quoi en faire.

    Règle #7 : `get_artist_id() or 1` est interdit. Rend l'identifiant, ou `None`
    quand la session ne permet pas de le résoudre.

    Cette forme existe parce que les appelants ne peuvent pas tous réagir de la même
    façon : une fonction de RENDU arrête la page (`st.stop()`), une fonction
    d'ÉCRITURE doit rendre un couple `(False, message)` à son appelant. Le garde
    lui-même — « personne d'autre qu'un administrateur ne retombe sur le locataire
    1 » — est identique dans les deux cas, et c'est LUI qu'on ne veut pas voir
    réécrit à la main : il l'était encore sur deux sites, chacun avec sa propre
    version du message.
    """
    artist_id = get_artist_id()
    if artist_id is not None:
        return artist_id
    if not is_admin():
        return None
    return 1  # admin fallback — documented, admins only


def _resolve_artist_id() -> int:
    """Le même garde, pour un appelant qui rend une page : arrête au lieu de mentir."""
    artist_id = _resolve_artist_id_or_none()
    if artist_id is None:
        st.error(t("hypeddit.session_invalid", "Session invalide."))
        st.stop()
    return artist_id


def get_campaigns_list(db):
    artist_id = _resolve_artist_id()
    query = "SELECT campaign_name FROM hypeddit_campaigns WHERE is_active = true AND artist_id = %s ORDER BY created_at DESC"
    df = db.fetch_df(query, (artist_id,))
    return df['campaign_name'].tolist() if not df.empty else []


def get_global_stats(start_date, end_date, db):
    """Récupère les statistiques de TOUTES les campagnes sur la période.

    `db` may be passed in to reuse the caller's connection (rule #9 — one
    connection per view); when None, opens and closes its own.
    """
    artist_id = _resolve_artist_id()
    # `v_hypeddit_daily` (migration 106) porte le grain (locataire, campagne, jour).
    # La table brute peut porter deux lignes pour le même jour — un ré-import — et
    # la vue les additionne une fois pour toutes. Le PDF la lisait déjà ; cette page,
    # non : deux surfaces répondaient au même « combien de visites » par deux chemins.
    query = """
        SELECT campaign_name, day AS date, visits, clicks
        FROM v_hypeddit_daily
        WHERE day >= %s AND day <= %s AND artist_id = %s
        ORDER BY day
    """
    return db.fetch_df(query, (start_date, end_date, artist_id))


def _render_global_stats(db):
    """Section Statistiques Globales (graphique multi-axes + KPIs)."""
    st.header(t("hypeddit.global_stats", "📊 Statistiques globales"))

    # Smart period filter (presets + auto-default on data span) instead of two
    # manual date inputs. The connection is show()'s — this used to open a second
    # one here and close it below, while show()'s stayed open.
    artist_id = _resolve_artist_id()
    window = smart_period_filter(
        db,
        table="hypeddit_daily_stats",
        date_column="date",
        artist_id=artist_id,
        key="hyp_stats",
    )

    df = get_global_stats(window.start, window.end, db=db)

    if df.empty:
        st.info(t("hypeddit.no_data_period", "📭 Aucune donnée trouvée pour la période sélectionnée."))
        return

    # Nettoyage et conversion. PAS de `fillna(0)` : une valeur absente sur une ligne
    # présente est une mesure qu'on n'a pas, et la compter pour zéro tire la moyenne
    # vers le bas tout en dessinant une journée creuse qui n'a pas eu lieu. `NaN`
    # traverse : la moyenne l'ignore, la figure y coupe sa ligne.
    df['visits'] = pd.to_numeric(df['visits'], errors='coerce')
    df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce')
    df['date'] = pd.to_datetime(df['date'])

    # KPIs Moyens — visites/clics seulement (le budget « Hypeddit » était en fait la
    # dépense Meta Ads, retiré de toute la vue ; voir ROI Breakeven pour la dépense pub).
    st.subheader(t("hypeddit.daily_averages", "Moyennes Journalières (Toutes campagnes)"))
    k1, k2 = st.columns(2)
    def _avg(col: str) -> str:
        """La moyenne des jours MESURÉS, ou « — » quand il n'y en a aucun.

        `int(nan)` lève ; afficher « 0 » affirmerait zéro visite là où l'on n'a
        simplement rien mesuré.
        """
        value = df[col].mean()
        return "—" if pd.isna(value) else f"{int(value):,}"

    k1.metric(t("hypeddit.kpi_avg_visits", "👁️ Visites Moy."), _avg('visits'))
    k2.metric(t("hypeddit.kpi_avg_clicks", "🖱️ Clicks Moy."), _avg('clicks'))

    st.markdown("---")

    # Graphique Combiné (visites & clics)
    st.subheader(t("hypeddit.global_performance", "📈 Performance Globale"))

    # `min_count=1` : une somme de rien vaut `NaN`, pas 0. Sans lui, un jour dont
    # toutes les campagnes sont non mesurées ressortait à 0 visite — le zéro inventé
    # que cette page corrige, reconstruit par l'agrégation juste après qu'on l'ait
    # retiré de la lecture.
    df_agg = df.groupby('date')[['visits', 'clicks']].sum(min_count=1).reset_index()
    # Et le calendrier complet, sinon un jour sans AUCUNE ligne sort de l'axe et la
    # courbe des clics le traverse en ligne droite : une interpolation que personne
    # n'a mesurée.
    df_agg = (df_agg.set_index('date')
              .reindex(pd.date_range(df_agg['date'].min(), df_agg['date'].max(),
                                     freq='D'))
              .rename_axis('date').reset_index())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_agg['date'], y=df_agg['visits'],
        name=t("hypeddit.visits", "Visites"), marker_color='rgba(135, 206, 250, 0.5)', yaxis='y'
    ))
    fig.add_trace(go.Scatter(
        x=df_agg['date'], y=df_agg['clicks'], connectgaps=False,
        name='Clicks', mode='lines+markers', line=dict(color='#2ECC71', width=2), yaxis='y'
    ))

    fig.update_layout(
        title=t("hypeddit.chart_title", "Visites & Clicks"),
        xaxis=dict(title=t("common.date", "Date")),
        yaxis=dict(title=t("hypeddit.volume_axis", "Volume"), side='left', showgrid=True),
        margin=dict(r=20),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        height=550
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander(t("hypeddit.data_detail", "Voir le détail des données")):
        st.dataframe(df, width="stretch")


def _render_history(db):
    """Section Historique (50 dernières lignes)."""
    st.header(t("hypeddit.history_header", "📋 Historique"))
    artist_id = _resolve_artist_id()
    df_hist = db.fetch_df("""
        SELECT campaign_name, day AS date, visits, clicks
        FROM v_hypeddit_daily
        WHERE artist_id = %s
        ORDER BY day DESC LIMIT 50
    """, (artist_id,))
    # No `db.close()` here: this helper did not open the connection, `show()` did and
    # closes it in its own `finally`. Closing it mid-page left `_render_entry_form`
    # querying a closed handle, which `PostgresHandler._ensure_connection()` silently
    # repaired by reconnecting — so the page worked, opened TWO connections per
    # render against rule #9, and nothing said so. A leftover from before 2026-08-21,
    # when each helper owned its own connection.

    if not df_hist.empty:
        df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d/%m/%Y')
        st.dataframe(df_hist, width="stretch")
    else:
        st.info(t("hypeddit.empty_history", "Historique vide."))


def _render_entry_form(db):
    """Section Saisie manuelle — placée en bas de page."""
    st.header(t("hypeddit.entry_header", "📝 Saisir les données"))

    with st.form("hypeddit_entry_form"):
        col1, col2 = st.columns(2)

        with col1:
            existing_campaigns = get_campaigns_list(db)
            _existing_lbl = t("hypeddit.type_existing", "Existante")
            _new_lbl = t("hypeddit.type_new", "Nouvelle")
            campaign_type = st.radio(t("hypeddit.type_label", "Type"), [_existing_lbl, _new_lbl], horizontal=True)

            if campaign_type == _existing_lbl and existing_campaigns:
                campaign_name = st.selectbox(t("hypeddit.campaign", "🎯 Campagne"), options=existing_campaigns)
            else:
                campaign_name = st.text_input(t("hypeddit.campaign_name", "🎯 Nom de la campagne"), key="h_new_camp_name")

            entry_date = st.date_input(t("hypeddit.date", "📅 Date"), value=datetime.now().date() - timedelta(days=1))

        with col2:
            visits = st.number_input(t("hypeddit.visits_input", "👁️ Visites"), min_value=0, step=1, key="h_visits")
            clicks = st.number_input(t("hypeddit.clicks_input", "🖱️ Clicks"), min_value=0, step=1, key="h_clicks")

        st.markdown("---")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c2:
            submit = st.form_submit_button(t("hypeddit.save_btn", "💾 Enregistrer"), type="primary")
        with c3:
            # Reset button — side effect via on_click callback; return value unused
            st.form_submit_button(t("hypeddit.reset_btn", "🔄 Réinitialiser"), on_click=clear_form_data)

    if submit:
        if not campaign_name:
            st.error(t("hypeddit.campaign_name_required", "Nom de campagne requis"))
        else:
            success, msg = add_campaign_stats(db, campaign_name, entry_date, visits, clicks)
            if success:
                st.success(msg)
            else:
                st.error(msg)


def show():
    st.title(t("hypeddit.title", "📱 Hypeddit - Gestion & Analyse"))
    st.markdown("---")

    # One connection for the whole page, closed once (rule #9). The five helpers
    # below opened and closed their own until 2026-08-21 — including the write
    # path, which ran on every form submit.
    db = get_db_connection()
    if db is None:
        st.error(t("hypeddit.db_unreachable", "❌ Base de données injoignable."))
        return

    try:
        # Single scrolling page: stats first, history next, manual entry last.
        _render_global_stats(db)
        st.markdown("---")
        _render_history(db)
        st.markdown("---")
        _render_entry_form(db)
    finally:
        db.close()

if __name__ == "__main__":
    show()
