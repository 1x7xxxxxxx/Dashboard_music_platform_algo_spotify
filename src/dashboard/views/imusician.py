"""Vue iMusician — saisie manuelle des revenus mensuels et visualisation."""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin


MONTHS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}


def _get_artist_filter():
    """Retourne (artist_id, label) selon le rôle courant."""
    if is_admin():
        return None, "Tous les artistes"
    aid = get_artist_id()
    return aid, f"Artiste {aid}"


def _load_revenues(db, artist_id):
    """Charge les revenus depuis la DB."""
    if artist_id is None:
        query = """
            SELECT r.year, r.month, r.revenue_eur, r.notes, s.name AS artist_name
            FROM imusician_monthly_revenue r
            JOIN saas_artists s ON s.id = r.artist_id
            ORDER BY r.year DESC, r.month DESC
        """
        return db.fetch_df(query)
    else:
        query = """
            SELECT year, month, revenue_eur, notes
            FROM imusician_monthly_revenue
            WHERE artist_id = %s
            ORDER BY year DESC, month DESC
        """
        return db.fetch_df(query, (artist_id,))


def _upsert_revenue(db, artist_id, year, month, revenue_eur, notes):
    """Insère ou met à jour un revenu mensuel."""
    db.execute_query(
        """
        INSERT INTO imusician_monthly_revenue
            (artist_id, year, month, revenue_eur, notes, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (artist_id, year, month)
        DO UPDATE SET
            revenue_eur = EXCLUDED.revenue_eur,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        """,
        (artist_id, year, month, revenue_eur, notes or None)
    )


def _delete_revenue(db, artist_id, year, month):
    """Supprime un enregistrement de revenu."""
    db.execute_query(
        "DELETE FROM imusician_monthly_revenue WHERE artist_id = %s AND year = %s AND month = %s",
        (artist_id, year, month)
    )


def show():
    st.title("💰 Distributeur — Revenus mensuels")
    st.markdown("Saisie manuelle des revenus générés via votre distributeur.")

    tab_form, tab_data, tab_import = st.tabs(["✏️ Saisie", "📊 Données", "📂 Import CSV"])

    db = get_db_connection()
    try:
        artist_id, _ = _get_artist_filter()

        # ── Onglet 1 : Formulaire de saisie ─────────────────────────────────
        with tab_form:
            st.subheader("Ajouter / modifier un revenu mensuel")

            # Si admin, sélection de l'artiste
            target_artist_id = artist_id
            if is_admin():
                artists_df = db.fetch_df(
                    "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
                )
                if artists_df.empty:
                    st.warning("Aucun artiste actif trouvé.")
                    return
                artist_options = {row['name']: row['id'] for _, row in artists_df.iterrows()}
                selected_name = st.selectbox("Artiste cible", list(artist_options.keys()))
                target_artist_id = artist_options[selected_name]

            col1, col2 = st.columns(2)
            with col1:
                year = st.number_input(
                    "Année", min_value=2015, max_value=datetime.now().year + 1,
                    value=datetime.now().year, step=1
                )
            with col2:
                month_label = st.selectbox(
                    "Mois",
                    options=list(MONTHS_FR.keys()),
                    format_func=lambda m: MONTHS_FR[m],
                    index=datetime.now().month - 1
                )

            revenue = st.number_input(
                "Revenu total (€)", min_value=0.0, max_value=999999.0,
                value=0.0, step=0.01, format="%.2f"
            )
            notes = st.text_input("Notes (optionnel)", placeholder="Ex: reversal Q1, promo release…")

            if st.button("💾 Enregistrer", type="primary"):
                if target_artist_id is None:
                    st.error("Impossible de déterminer l'artiste cible.")
                else:
                    try:
                        _upsert_revenue(db, target_artist_id, int(year), int(month_label), revenue, notes)
                        st.success(f"✅ {MONTHS_FR[month_label]} {year} — {revenue:.2f} € enregistré.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur d'enregistrement : {e}")

        # ── Onglet 2 : Données + graphique ──────────────────────────────────
        with tab_data:
            df = _load_revenues(db, artist_id)

            if df.empty:
                st.info("Aucun revenu enregistré. Utilisez l'onglet Saisie pour commencer.")
            else:
                # Colonne lisible mois/année
                df['period'] = df.apply(
                    lambda r: f"{MONTHS_FR[int(r['month'])]} {int(r['year'])}", axis=1
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
                        "Filtrer par année",
                        options=available_years,
                        default=available_years,
                        format_func=str,
                    )
                with fcol2:
                    selected_months = st.multiselect(
                        "Filtrer par mois",
                        options=available_months,
                        default=available_months,
                        format_func=lambda m: MONTHS_FR[m],
                    )

                if not selected_years or not selected_months:
                    st.warning("Sélectionnez au moins une année et un mois.")
                else:
                    mask = (
                        df['year'].astype(int).isin(selected_years)
                        & df['month'].astype(int).isin(selected_months)
                    )
                    df = df[mask]

                    if df.empty:
                        st.info("Aucune donnée pour cette sélection.")
                    else:
                        df_sorted = df.sort_values('date_sort')

                        # KPI total
                        total = df['revenue_eur'].sum()
                        avg = df['revenue_eur'].mean()
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Total cumulé", f"{total:,.2f} €")
                        col2.metric("Moyenne mensuelle", f"{avg:,.2f} €")
                        col3.metric("Mois renseignés", len(df))

                        st.markdown("---")

                        # Graphique
                        fig = px.bar(
                            df_sorted, x='date_sort', y='revenue_eur',
                            labels={'date_sort': '', 'revenue_eur': 'Revenus (€)'},
                            color_discrete_sequence=['#1DB954'],
                            text='revenue_eur'
                        )
                        fig.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
                        fig.update_layout(
                            xaxis_tickformat='%b %Y',
                            yaxis_title="Revenus (€)",
                            showlegend=False,
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig, width="stretch")

                        st.markdown("---")
                        st.subheader("Détail")

                        # Tableau affiché
                        display_cols = ['period', 'revenue_eur', 'notes']
                        if is_admin() and 'artist_name' in df.columns:
                            display_cols = ['artist_name'] + display_cols
                        st.dataframe(
                            df[display_cols].rename(columns={
                                'artist_name': 'Artiste',
                                'period': 'Période',
                                'revenue_eur': 'Revenus (€)',
                                'notes': 'Notes'
                            }),
                            width="stretch",
                            hide_index=True
                        )

                        # Suppression d'une entrée
                        with st.expander("🗑️ Supprimer une entrée"):
                            del_target_id = artist_id
                            if is_admin():
                                artists_df2 = db.fetch_df(
                                    "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
                                )
                                artist_opts2 = {row['name']: row['id'] for _, row in artists_df2.iterrows()}
                                del_name = st.selectbox("Artiste", list(artist_opts2.keys()), key="del_artist")
                                del_target_id = artist_opts2[del_name]

                            del_year = st.number_input(
                                "Année", min_value=2015, max_value=datetime.now().year + 1,
                                value=datetime.now().year, step=1, key="del_year"
                            )
                            del_month = st.selectbox(
                                "Mois", options=list(MONTHS_FR.keys()),
                                format_func=lambda m: MONTHS_FR[m],
                                index=0, key="del_month"
                            )
                            if st.button("🗑️ Supprimer", type="secondary"):
                                try:
                                    _delete_revenue(db, del_target_id, int(del_year), int(del_month))
                                    st.success(f"Entrée supprimée : {MONTHS_FR[del_month]} {del_year}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erreur : {e}")

        # ── Onglet 3 : Import CSV iMusician ─────────────────────────────────
        with tab_import:
            st.subheader("Import CSV iMusician")
            st.markdown(
                "Importez un fichier exporté depuis iMusician. "
                "Deux formats sont supportés :\n"
                "- **Résumé par sortie** (`Statement date`, `Release title`, `Total revenue`, …)\n"
                "- **Rapport de vente** (`Sales date`, `ISRC`, `Shop`, `Country`, …)"
            )

            imp_artist_id = artist_id
            if is_admin():
                imp_artists_df = db.fetch_df(
                    "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
                )
                if imp_artists_df.empty:
                    st.warning("Aucun artiste actif.")
                else:
                    imp_opts = {row['name']: row['id'] for _, row in imp_artists_df.iterrows()}
                    imp_sel = st.selectbox("Artiste cible", list(imp_opts.keys()), key="imp_artist")
                    imp_artist_id = imp_opts[imp_sel]

            uploaded_csv = st.file_uploader(
                "Fichier CSV iMusician",
                type=["csv"],
                key="imusician_csv_upload",
                help="Glissez le fichier exporté depuis iMusician (Résumé ou Rapport de vente).",
            )

            if uploaded_csv:
                import io
                from src.transformers.imusician_csv_parser import IMusicianCSVParser

                uploaded_csv.seek(0)
                try:
                    raw_df = pd.read_csv(io.BytesIO(uploaded_csv.read()))
                except Exception as e:
                    st.error(f"❌ Impossible de lire le fichier : {e}")
                else:
                    parser = IMusicianCSVParser()
                    detected = parser.detect_csv_type(raw_df)

                    if detected == 'release_summary':
                        badge = "✅ **Résumé par sortie** détecté"
                        table_name = 'imusician_release_summary'
                        conflict_cols = ['artist_id', 'barcode', 'year', 'month']
                        update_cols = [
                            'release_title', 'track_downloads', 'track_streams',
                            'release_downloads', 'track_downloads_revenue',
                            'track_streams_revenue', 'release_downloads_revenue',
                            'total_revenue', 'collected_at',
                        ]
                    elif detected == 'sales_detail':
                        badge = "✅ **Rapport de vente** détecté"
                        table_name = 'imusician_sales_detail'
                        conflict_cols = [
                            'artist_id', 'isrc', 'sales_year', 'sales_month',
                            'statement_year', 'statement_month', 'shop', 'country',
                            'transaction_type',
                        ]
                        update_cols = ['quantity', 'revenue_eur', 'collected_at']
                    else:
                        badge = None

                    if badge is None:
                        st.error(
                            "❌ Format non reconnu. Vérifiez que le fichier correspond "
                            "à un export iMusician (colonnes attendues : "
                            "`Release title` / `Total revenue` pour le résumé, "
                            "ou `Sales date` / `ISRC` / `Shop` pour le rapport de vente)."
                        )
                    else:
                        st.markdown(badge)

                        if detected == 'release_summary':
                            parsed_rows = parser.parse_release_summary(raw_df, artist_id=imp_artist_id)
                        else:
                            parsed_rows = parser.parse_sales_detail(raw_df, artist_id=imp_artist_id)

                        if not parsed_rows:
                            st.warning("Aucune ligne valide extraite du fichier.")
                        else:
                            st.dataframe(
                                pd.DataFrame(parsed_rows).head(10),
                                width="stretch",
                                hide_index=True,
                            )
                            if len(parsed_rows) > 10:
                                st.caption(f"… et {len(parsed_rows) - 10} ligne(s) non affichées.")

                            st.markdown("---")
                            if st.button("✅ Confirmer l'import", type="primary", key="imusician_confirm"):
                                try:
                                    db.upsert_many(
                                        table=table_name,
                                        data=parsed_rows,
                                        conflict_columns=conflict_cols,
                                        update_columns=update_cols,
                                    )
                                    st.success(
                                        f"✅ {len(parsed_rows)} ligne(s) importée(s) "
                                        f"dans `{table_name}` pour l'artiste #{imp_artist_id}."
                                    )
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de l'insertion : {e}")
                                    st.exception(e)

    finally:
        db.close()
