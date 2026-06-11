"""Vue Distributeur — revenus mensuels iMusician + DistroKid (saisie manuelle, import, ROI)."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import smart_date_range
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.kpi_helpers import get_roi_data, get_monthly_roi_series
from src.database.postgres_handler import validate_table

# Label affiché → table de revenus mensuels (une table par distributeur, pattern iMusician).
DISTRIBUTOR_TABLES = {
    'iMusician': 'imusician_monthly_revenue',
    'DistroKid': 'distrokid_monthly_revenue',
}
_ALL_DISTRIBUTORS = 'Tous'
_DISTRIBUTOR_COLORS = {'iMusician': '#1DB954', 'DistroKid': '#F5C518'}


def _roi_data_span(db, artist_id):
    """Return (min_date, max_date) spanning distributor revenue + Meta spend, or (None, None).

    The ROI filter is bounded to this so the default window always contains data —
    a fixed "last 6 months" returned zero because Meta spend is historical.
    """
    if artist_id is not None:
        rows = db.fetch_query(
            """SELECT MIN(d), MAX(d) FROM (
                   SELECT make_date(year, month, 1) AS d FROM v_artist_monthly_revenue WHERE artist_id = %s
                   UNION ALL
                   SELECT day_date::date FROM meta_insights_performance_day WHERE artist_id = %s
               ) t""",
            (artist_id, artist_id),
        )
    else:
        rows = db.fetch_query(
            """SELECT MIN(d), MAX(d) FROM (
                   SELECT make_date(year, month, 1) AS d FROM v_artist_monthly_revenue
                   UNION ALL
                   SELECT day_date::date FROM meta_insights_performance_day
               ) t"""
        )
    if rows and rows[0][0]:
        return rows[0][0], rows[0][1]
    return None, None


MONTHS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}


def _month_name(m: int) -> str:
    """Translated month name (FR source = MONTHS_FR, EN via common catalog)."""
    return t(f"common.month.{m}", MONTHS_FR[m])


def _default_period(today=None):
    """(year, month) du mois précédent — les relevés distributeurs arrivent en décalé."""
    today = today or date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _get_artist_filter():
    """Retourne (artist_id, label) selon le rôle courant."""
    if is_admin():
        return None, "Tous les artistes"
    aid = get_artist_id()
    return aid, f"Artiste {aid}"


def _load_revenues(db, artist_id, tables):
    """Charge les revenus des distributeurs sélectionnés ({label: table}) en une requête."""
    parts, params = [], []
    for label, table in tables.items():
        validate_table(table)
        if artist_id is None:
            parts.append(
                f"""SELECT %s AS distributor, r.year, r.month, r.revenue_eur, r.notes,
                           s.name AS artist_name
                    FROM {table} r
                    JOIN saas_artists s ON s.id = r.artist_id"""
            )
            params.append(label)
        else:
            parts.append(
                f"""SELECT %s AS distributor, year, month, revenue_eur, notes
                    FROM {table}
                    WHERE artist_id = %s"""
            )
            params.extend([label, artist_id])
    query = " UNION ALL ".join(parts) + " ORDER BY year DESC, month DESC"
    return db.fetch_df(query, tuple(params))


def _delete_revenue(db, table, artist_id, year, month):
    """Supprime un enregistrement de revenu dans la table du distributeur."""
    validate_table(table)
    db.execute_query(
        f"DELETE FROM {table} WHERE artist_id = %s AND year = %s AND month = %s",
        (artist_id, year, month)
    )


def _upsert_revenue(db, table, artist_id, year, month, revenue_eur, notes):
    """Insère ou met à jour un revenu mensuel saisi manuellement."""
    validate_table(table)
    db.upsert_many(
        table,
        [{
            'artist_id': artist_id,
            'year': year,
            'month': month,
            'revenue_eur': revenue_eur,
            'notes': notes or None,
            'source': 'manual',
            'updated_at': datetime.now(timezone.utc),
        }],
        conflict_columns=['artist_id', 'year', 'month'],
        update_columns=['revenue_eur', 'notes', 'source', 'updated_at'],
    )


def _render_entry_form(db, artist_id):
    """Formulaire de saisie manuelle d'un revenu mensuel (par distributeur)."""
    st.markdown("---")
    st.subheader(t("imusician.entry_header", "✍️ Saisie manuelle"))
    st.caption(t(
        "imusician.entry_caption",
        "Renseignez le revenu d'un mois depuis votre relevé distributeur (montant en €). "
        "Une saisie sur un mois déjà renseigné le remplace."
    ))

    artist_opts = None
    if artist_id is None:
        artists_df = db.fetch_df(
            "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
        )
        artist_opts = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        if not artist_opts:
            st.info(t("imusician.no_active_artist", "Aucun artiste actif."))
            return

    def_year, def_month = _default_period()
    with st.form("distributor_revenue_entry"):
        c1, c2 = st.columns(2)
        with c1:
            distributor = st.selectbox(
                t("imusician.distributor", "Distributeur"), list(DISTRIBUTOR_TABLES.keys())
            )
        with c2:
            target_name = None
            if artist_opts is not None:
                target_name = st.selectbox(
                    t("common.artist", "Artiste"), list(artist_opts.keys())
                )

        c3, c4, c5 = st.columns(3)
        with c3:
            year = st.number_input(
                t("common.year", "Année"), min_value=2015, max_value=date.today().year + 1,
                value=def_year, step=1
            )
        with c4:
            month = st.selectbox(
                t("common.month", "Mois"), options=list(MONTHS_FR.keys()),
                format_func=_month_name,
                index=def_month - 1
            )
        with c5:
            revenue = st.number_input(
                t("common.revenue_eur", "Revenus (€)"), min_value=0.0, step=0.01, format="%.2f"
            )
        notes = st.text_input(t("imusician.notes_optional", "Notes (optionnel)"), max_chars=500)

        if st.form_submit_button(t("imusician.save_btn", "💾 Enregistrer"), type="primary"):
            target_id = artist_opts[target_name] if artist_opts is not None else artist_id
            try:
                _upsert_revenue(
                    db, DISTRIBUTOR_TABLES[distributor],
                    target_id, int(year), int(month), float(revenue), notes.strip()
                )
                st.success(t(
                    "imusician.entry_saved",
                    "{distributor} — {month} {year} : {revenue:,.2f} € enregistré."
                ).format(
                    distributor=distributor, month=_month_name(month),
                    year=int(year), revenue=revenue
                ))
                st.rerun()
            except Exception as e:
                st.error(t("common.error", "Erreur : {err}").format(err=e))


def show():
    st.title(t("imusician.title", "💰 Distributeur — Revenus mensuels"))
    st.markdown(t(
        "imusician.intro",
        "Visualisation des revenus générés via vos distributeurs (iMusician, DistroKid). "
        "L'import des exports (CSV iMusician, TSV/CSV DistroKid) se fait depuis la page "
        "**📂 Import CSV** ; une saisie manuelle par mois est aussi possible ci-dessous."
    ))

    tab_data, tab_roi = st.tabs([
        t("imusician.tab_data", "📊 Données"),
        t("imusician.tab_roi", "💹 ROI Breakheaven"),
    ])

    db = get_db_connection()
    try:
        artist_id, _ = _get_artist_filter()

        # ── Onglet : Données + graphique ────────────────────────────────────
        with tab_data:
            selected = st.segmented_control(
                t("imusician.distributor", "Distributeur"),
                options=[_ALL_DISTRIBUTORS] + list(DISTRIBUTOR_TABLES.keys()),
                default=_ALL_DISTRIBUTORS,
                format_func=lambda d: t("common.all", "Tous") if d == _ALL_DISTRIBUTORS else d,
                key="distributor_filter",
            ) or _ALL_DISTRIBUTORS
            tables = (
                DISTRIBUTOR_TABLES if selected == _ALL_DISTRIBUTORS
                else {selected: DISTRIBUTOR_TABLES[selected]}
            )

            df = _load_revenues(db, artist_id, tables)

            if df.empty:
                st.info(t(
                    "imusician.no_revenue",
                    "Aucun revenu enregistré pour cette sélection. Importez un export "
                    "iMusician ou DistroKid (page **📂 Import CSV**) ou saisissez un revenu "
                    "manuellement ci-dessous."
                ))
            else:
                # Colonne lisible mois/année
                df['period'] = df.apply(
                    lambda r: f"{_month_name(int(r['month']))} {int(r['year'])}", axis=1
                )
                df['date_sort'] = pd.to_datetime(
                    df.apply(lambda r: f"{int(r['year'])}-{int(r['month']):02d}-01", axis=1)
                )

                # ── Filtres année / mois ─────────────────────────────────────
                available_years = sorted(df['year'].astype(int).unique(), reverse=True)
                available_months = sorted(df['month'].astype(int).unique())

                fcol1, fcol2 = st.columns(2)
                with fcol1:
                    selected_years = st.multiselect(
                        t("common.filter_by_year", "Filtrer par année"),
                        options=available_years,
                        default=available_years,
                        format_func=str,
                    )
                with fcol2:
                    selected_months = st.multiselect(
                        t("common.filter_by_month", "Filtrer par mois"),
                        options=available_months,
                        default=available_months,
                        format_func=_month_name,
                    )

                if not selected_years or not selected_months:
                    st.warning(t("imusician.select_year_month",
                                 "Sélectionnez au moins une année et un mois."))
                else:
                    mask = (
                        df['year'].astype(int).isin(selected_years)
                        & df['month'].astype(int).isin(selected_months)
                    )
                    df = df[mask]

                    if df.empty:
                        st.info(t("common.no_data", "Aucune donnée pour cette sélection."))
                    else:
                        df_sorted = df.sort_values('date_sort')

                        # KPI total
                        total = df['revenue_eur'].sum()
                        avg = df.groupby('date_sort')['revenue_eur'].sum().mean()
                        col1, col2, col3 = st.columns(3)
                        col1.metric(t("imusician.kpi_total", "Total cumulé"), f"{total:,.2f} €")
                        col2.metric(t("imusician.kpi_avg", "Moyenne mensuelle"), f"{avg:,.2f} €")
                        col3.metric(t("imusician.kpi_months", "Mois renseignés"),
                                    df['date_sort'].nunique())

                        st.markdown("---")

                        # Graphique (empilé par distributeur quand "Tous")
                        fig = px.bar(
                            df_sorted, x='date_sort', y='revenue_eur',
                            color='distributor',
                            labels={
                                'date_sort': '',
                                'revenue_eur': t("common.revenue_eur", "Revenus (€)"),
                                'distributor': t("imusician.distributor", "Distributeur"),
                            },
                            color_discrete_map=_DISTRIBUTOR_COLORS,
                            text='revenue_eur'
                        )
                        fig.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
                        fig.update_layout(
                            xaxis_tickformat='%b %Y',
                            yaxis_title=t("common.revenue_eur", "Revenus (€)"),
                            showlegend=(len(tables) > 1),
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig, width="stretch")

                        st.markdown("---")
                        st.subheader(t("imusician.detail_header", "Détail"))

                        # Tableau affiché
                        display_cols = ['period', 'revenue_eur', 'notes']
                        if len(tables) > 1:
                            display_cols = ['distributor'] + display_cols
                        if is_admin() and 'artist_name' in df.columns:
                            display_cols = ['artist_name'] + display_cols
                        st.dataframe(
                            df[display_cols].rename(columns={
                                'artist_name': t("common.artist", "Artiste"),
                                'distributor': t("imusician.distributor", "Distributeur"),
                                'period': t("common.period", "Période"),
                                'revenue_eur': t("common.revenue_eur", "Revenus (€)"),
                                'notes': t("common.notes", "Notes")
                            }),
                            width="stretch",
                            hide_index=True
                        )

                        # Suppression d'une entrée
                        with st.expander(t("imusician.delete_expander", "🗑️ Supprimer une entrée")):
                            del_distributor = st.selectbox(
                                t("imusician.distributor", "Distributeur"),
                                list(DISTRIBUTOR_TABLES.keys()),
                                key="del_distributor"
                            )
                            del_target_id = artist_id
                            if is_admin():
                                artists_df2 = db.fetch_df(
                                    "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
                                )
                                artist_opts2 = {row['name']: row['id'] for _, row in artists_df2.iterrows()}
                                del_name = st.selectbox(t("common.artist", "Artiste"),
                                                        list(artist_opts2.keys()), key="del_artist")
                                del_target_id = artist_opts2[del_name]

                            del_year = st.number_input(
                                t("common.year", "Année"), min_value=2015,
                                max_value=date.today().year + 1,
                                value=date.today().year, step=1, key="del_year"
                            )
                            del_month = st.selectbox(
                                t("common.month", "Mois"), options=list(MONTHS_FR.keys()),
                                format_func=_month_name,
                                index=0, key="del_month"
                            )
                            if st.button(t("common.delete", "🗑️ Supprimer"), type="secondary"):
                                try:
                                    _delete_revenue(
                                        db, DISTRIBUTOR_TABLES[del_distributor],
                                        del_target_id, int(del_year), int(del_month)
                                    )
                                    st.success(t(
                                        "imusician.entry_deleted",
                                        "Entrée supprimée : {distributor} — {month} {year}"
                                    ).format(
                                        distributor=del_distributor,
                                        month=_month_name(del_month), year=del_year
                                    ))
                                    st.rerun()
                                except Exception as e:
                                    st.error(t("common.error", "Erreur : {err}").format(err=e))

            # Saisie manuelle (toujours accessible, même sans données)
            _render_entry_form(db, artist_id)

        # ── Onglet : ROI Breakheaven ────────────────────────────────────────
        with tab_roi:
            st.subheader(t("imusician.roi_header", "💹 ROI Breakheaven"))
            st.caption(t(
                "imusician.roi_caption",
                "Revenus (iMusician + DistroKid + royalties SACEM) vs dépenses Meta Ads "
                "sur la période sélectionnée"
            ))

            span_min, span_max = _roi_data_span(db, artist_id)
            from_date, to_date = smart_date_range(
                t("common.period", "Période"), span_min, span_max, key="imusician_roi")

            if from_date is None:
                st.info(t(
                    "imusician.roi_no_data",
                    "Aucune donnée de revenus distributeur ni de dépenses Meta Ads pour cet artiste. "
                    "Importez un export iMusician (page Import CSV), saisissez un revenu dans "
                    "l'onglet Données, ou lancez la collecte Meta depuis l'accueil."
                ))
            else:
                roi = get_roi_data(db, artist_id, from_date, to_date)

                c1, c2, c3 = st.columns(3)
                c1.metric(t("imusician.roi_revenue", "💰 Revenus (distrib. + SACEM)"),
                          f"{roi['revenue_eur']:,.2f} €")
                c2.metric(t("imusician.roi_spend", "📱 Dépenses Meta"),
                          f"{roi['meta_spend']:,.2f} €")

                if roi['roi_pct'] is not None:
                    roi_label = f"{roi['roi_pct']:.1f} %"
                    roi_delta = (t("imusician.roi_profitable", "✅ Rentable")
                                 if roi['profitable']
                                 else t("imusician.roi_unprofitable", "⚠️ Déficitaire"))
                    c3.metric(
                        "📊 ROI", roi_label, roi_delta,
                        delta_color="normal" if roi['profitable'] else "inverse",
                        help=t("imusician.roi_total_help",
                               "ROI sur la dépense Meta Ads = {total:,.2f} €").format(
                                   total=roi['total_spend'])
                    )
                else:
                    c3.metric("📊 ROI", "—",
                              help=t("imusician.roi_no_spend_help",
                                     "Aucune dépense promo sur la période — élargissez le filtre"))

                df_series = get_monthly_roi_series(db, artist_id, from_date, to_date)
                if not df_series.empty:
                    # Revenue column = distributors (green) + SACEM royalties stacked on
                    # top (purple), beside the Meta-spend column (red).
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=df_series['period_date'], y=df_series['distributor_revenue'],
                        name=t("imusician.dist_revenue_eur", "Revenus distributeurs (€)"),
                        marker_color="#1DB954", offsetgroup='rev'
                    ))
                    fig.add_trace(go.Bar(
                        x=df_series['period_date'], y=df_series['sacem_revenue'],
                        base=df_series['distributor_revenue'],
                        name=t("imusician.sacem_revenue_eur", "Royalties SACEM (€)"),
                        marker_color="#8E44AD", offsetgroup='rev'
                    ))
                    fig.add_trace(go.Bar(
                        x=df_series['period_date'], y=df_series['meta_spend'],
                        name=t("imusician.meta_spend_eur", "Dépenses Meta (€)"),
                        marker_color="#FF4444", offsetgroup='spend'
                    ))
                    fig.update_layout(
                        barmode='group',
                        xaxis_tickformat='%b %Y',
                        yaxis_title=t("imusician.euros_axis", "Euros (€)"),
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info(t("imusician.roi_empty_period",
                              "Aucune donnée de revenus ou dépenses sur cette période."))

    finally:
        db.close()
