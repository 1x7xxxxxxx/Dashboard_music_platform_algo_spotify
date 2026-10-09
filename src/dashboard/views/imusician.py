"""Vue Distributeur — revenus mensuels iMusician + DistroKid (saisie manuelle, import, ROI)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection, charts, require_db
from src.dashboard.utils.i18n import t
from src.dashboard.utils import filters
from src.dashboard.utils.ui import flash
from src.dashboard.utils.cache_invalidation import purge_after_write
from src.dashboard.auth import is_admin, tenant_scope
from src.database.postgres_handler import validate_table

# Label affiché → table de revenus mensuels (une table par distributeur, pattern iMusician).
DISTRIBUTOR_TABLES = {
    'iMusician': 'imusician_monthly_revenue',
    'DistroKid': 'distrokid_monthly_revenue',
}
_ALL_DISTRIBUTORS = 'Tous'
_CUMUL = "#1F4E79"   # the running total — navy, apart from the distributors' greens


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
    # Not get_artist_id(): a None here would flow into _load_revenues' `artist_id is
    # None` branch, which joins across saas_artists with no filter at all (R25).
    aid = tenant_scope()
    return aid, f"Artiste {aid}"


_SOURCE_LABELS = {'imusician': 'iMusician', 'distrokid': 'DistroKid'}

_REVENUES_SQL = """
    SELECT source, year, month, revenue_eur
      FROM v_artist_monthly_revenue
     WHERE source = ANY(%s) AND (%s::int IS NULL OR artist_id = %s)
"""


def _load_revenues(db, artist_id, tables):
    """Monthly distributor revenue, read from the gold view (R388).

    `v_artist_monthly_revenue` is the one definition the treasury and the forecast
    read too; the raw tables are only ever unioned there. `tables` ({label: table})
    names the distributors kept; SACEM, also in the view, is not a distributor.
    """
    wanted = [src for src, label in _SOURCE_LABELS.items() if label in tables]
    df = db.fetch_df(_REVENUES_SQL, (wanted, artist_id, artist_id))
    df['distributor'] = df['source'].map(_SOURCE_LABELS)
    return df


def _delete_revenue(db, table, artist_id, year, month):
    """Supprime un enregistrement de revenu dans la table du distributeur."""
    validate_table(table)
    db.execute_query(
        f"DELETE FROM {table} WHERE artist_id = %s AND year = %s AND month = %s",
        (artist_id, year, month)
    )
    purge_after_write(artist_id=artist_id)


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
    purge_after_write(artist_id=artist_id)


def _render_entry_form(db, artist_id):
    """Formulaire de saisie manuelle d'un revenu mensuel (par distributeur)."""
    st.subheader(t("imusician.entry_header", "✍️ Saisie manuelle"))

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
        # R488 (W11 « à quoi servent les notes ? sinon supprimer ») : no reader ever
        # read a manual note — not the page, the PDF, the CSV export nor a DAG. The
        # column stays (the DistroKid rollup writes its FX trace there); the field goes.

        if st.form_submit_button(t("imusician.save_btn", "💾 Enregistrer"), type="primary"):
            target_id = artist_opts[target_name] if artist_opts is not None else artist_id
            try:
                _upsert_revenue(
                    db, DISTRIBUTOR_TABLES[distributor],
                    target_id, int(year), int(month), float(revenue), None
                )
                flash(t(
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
    # R388 (V75-V78, 2026-10-05, retour d'écran) : UNE page lue de haut en bas — la
    # saisie en tête (c'est le geste qu'on vient faire ici), puis l'évolution des ventes,
    # puis le point mort. Les onglets « Données » / « ROI » cachaient l'un à l'autre deux
    # lectures d'une même question : est-ce que ça rapporte ?
    st.title(t("imusician.title", "💰 Distributeur iMusician DistroKid + SACEM"))
    # R488 (W11) : the import is a BUTTON at the top, like SACEM's — not a sentence
    # naming another page.
    if st.button(t("imusician.import_btn", "📂 Importer un export iMusician / DistroKid"),
                 key="distributor_import", type="primary"):
        from src.dashboard.views.credentials.router import CSV_TAB_KEY, goto_tab
        goto_tab(CSV_TAB_KEY)
    db = require_db(get_db_connection())
    try:
        artist_id, _ = _get_artist_filter()
        _render_entry_form(db, artist_id)
        st.markdown("---")
        _render_evolution(db, artist_id)
        # R476 (W11) : the break-even moved to the cross view, section « Revenus ».
        # R461 (owner, 2026-10-07): the SACEM page merged here, on the SAME connection.
        st.markdown("---")
        from src.dashboard.views.sacem import render_section
        render_section(db, artist_id)
    finally:
        db.close()


def _revenue_filters(db, artist_id):
    """Distributor · the app's common period selector (R478), whole history by default."""
    c_dist, c_period = st.columns([2, 5])
    with c_dist:
        selected = st.segmented_control(
            t("imusician.distributor", "Distributeur"),
            options=[_ALL_DISTRIBUTORS] + list(DISTRIBUTOR_TABLES.keys()),
            default=_ALL_DISTRIBUTORS,
            format_func=lambda d: t("common.all", "Tous") if d == _ALL_DISTRIBUTORS else d,
            key="distributor_filter",
        ) or _ALL_DISTRIBUTORS
    tables = (DISTRIBUTOR_TABLES if selected == _ALL_DISTRIBUTORS
              else {selected: DISTRIBUTOR_TABLES[selected]})
    df = _load_revenues(db, artist_id, tables)
    if df.empty:
        return df
    starts = _month_starts(df)
    with c_period:
        window = filters.span(starts.min().date(), starts.max().date(),
                              key="imusician_period", artist_id=artist_id,
                              latest_release_resolver=lambda: filters.latest_release_date(
                                  db, artist_id))
    return df[months_in_window(starts, window.start, window.end)]


def _month_starts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(dict(year=df['year'].astype(int),
                               month=df['month'].astype(int), day=1))


def months_in_window(month_starts: pd.Series, start: date, end: date) -> pd.Series:
    """A revenue month belongs to the window when the window touches it. Pure.

    Revenues are monthly: a window starting mid-month (« semaine en cours ») must keep
    that month, not drop it because its first day is before the start."""
    first = pd.Timestamp(start).replace(day=1)
    return (month_starts >= first) & (month_starts <= pd.Timestamp(end))


def evolution_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly revenue per distributor, plus the running total across distributors."""
    out = df.assign(month_start=pd.to_datetime(
        dict(year=df['year'].astype(int), month=df['month'].astype(int), day=1)))
    out = (out.groupby(['month_start', 'distributor'], as_index=False)['revenue_eur']
              .sum().sort_values('month_start'))
    totals = out.groupby('month_start')['revenue_eur'].sum().cumsum()
    return out.merge(totals.rename('cumulative').reset_index(), on='month_start',
                     validate='many_to_one')


FORECAST_MONTHS = 6
FORECAST_BASIS = 12   # the rate is the mean of the last 12 months that have a figure


def revenue_forecast(evo: pd.DataFrame, months: int = FORECAST_MONTHS,
                     basis: int = FORECAST_BASIS) -> pd.DataFrame:
    """The running total carried `months` ahead at the recent monthly rate. Pure.

    Empty under three months of history: no rate reads from one or two points."""
    monthly = evo.groupby('month_start')['revenue_eur'].sum().sort_index()
    if len(monthly) < 3:
        return pd.DataFrame(columns=['month_start', 'cumulative'])
    rate = float(monthly.tail(basis).mean())
    ahead = pd.date_range(monthly.index.max() + pd.offsets.MonthBegin(1),
                          periods=months, freq='MS')
    return pd.DataFrame({'month_start': ahead,
                         'cumulative': float(monthly.sum()) + rate * (pd.RangeIndex(months) + 1)})


def _evolution_figure(evo: pd.DataFrame, forecast: pd.DataFrame | None = None) -> go.Figure:
    """€ per month, € cumulated and the forecast on ONE frame (R488, W11).

    One euro axis: the bars are months, the area is their sum — both totals, so a
    second axis is refused (two totals never share a frame on two scales). The
    totals ride in the title, where the summary sentence under the chart used to be."""
    from src.dashboard.utils.treasury_chart import FLUX_COLOURS
    cum = evo.drop_duplicates('month_start')
    monthly = evo.groupby('month_start')['revenue_eur'].sum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum['month_start'], y=cum['cumulative'], mode='lines',
        name=t("imusician.cumulative", "€ cumulés"),
        line=dict(color=_CUMUL, width=2.5), fill='tozeroy',
        fillcolor="rgba(31,78,121,0.12)",
        hovertemplate="%{x|%m/%Y}<br>%{y:,.2f} €<extra></extra>"))
    for name, grp in evo.groupby('distributor', sort=False):
        fig.add_trace(go.Bar(
            x=grp['month_start'], y=grp['revenue_eur'],
            name=t("imusician.monthly_of", "{d} — € par mois").format(d=name),
            marker_color=FLUX_COLOURS.get(str(name).lower(), "#8A8A8A"),
            hovertemplate="%{x|%m/%Y}<br>%{y:,.2f} €<extra></extra>"))
    if forecast is not None and not forecast.empty:
        fig.add_trace(go.Scatter(
            x=[cum['month_start'].iloc[-1], *forecast['month_start']],
            y=[cum['cumulative'].iloc[-1], *forecast['cumulative']],
            mode='lines', line=dict(color=_CUMUL, width=2, dash='dash'),
            name=t("imusician.forecast", "prévision ({n} mois au rythme récent)"
                   ).format(n=len(forecast)),
            hovertemplate="%{x|%m/%Y}<br>%{y:,.2f} €<extra></extra>"))
    fig.update_layout(
        title=t("imusician.evolution_title",
                "Ventes : {total} au total · {avg} par mois · {n} mois").format(
            total=f"{monthly.sum():,.2f} €".replace(",", " "),
            avg=f"{monthly.mean():,.2f} €".replace(",", " "), n=len(monthly)),
        barmode='relative', hovermode='x unified', height=460, yaxis_title="€",
        legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='left', x=0),
        margin=dict(t=50, b=90))
    return fig


def _render_evolution(db, artist_id):
    """What the distributors paid, month by month — a chart, not a ledger (V77)."""
    st.subheader(t("imusician.evolution_header", "📈 Évolution des ventes"))
    df = _revenue_filters(db, artist_id)
    if df.empty:
        st.info(t(
            "imusician.no_revenue",
            "Aucun revenu enregistré pour cette sélection. Importez un export "
            "iMusician ou DistroKid (page **📂 Ajouter mes chiffres Spotify for Artists & Apple**) "
            "ou saisissez un revenu manuellement ci-dessus."
        ))
        return
    evo = evolution_frame(df)
    # R488 (W11) : the totals are in the figure's title, and no line under it.
    charts.plotly_chart(_evolution_figure(evo, revenue_forecast(evo)), width="stretch",
                        decision=False)
    _render_delete(db, artist_id)


def _render_delete(db, artist_id):
    """Remove one month of one distributor — the correction a wrong entry needs."""
    with st.expander(t("imusician.delete_expander", "🗑️ Supprimer une entrée")):
        del_distributor = st.selectbox(
            t("imusician.distributor", "Distributeur"),
            list(DISTRIBUTOR_TABLES.keys()), key="del_distributor")
        del_target_id = artist_id
        if is_admin():
            artists_df2 = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name")
            artist_opts2 = {row['name']: row['id'] for _, row in artists_df2.iterrows()}
            del_name = st.selectbox(t("common.artist", "Artiste"),
                                    list(artist_opts2.keys()), key="del_artist")
            del_target_id = artist_opts2[del_name]
        del_year = st.number_input(
            t("common.year", "Année"), min_value=2015, max_value=date.today().year + 1,
            value=date.today().year, step=1, key="del_year")
        del_month = st.selectbox(
            t("common.month", "Mois"), options=list(MONTHS_FR.keys()),
            format_func=_month_name, index=0, key="del_month")
        if st.button(t("common.delete", "🗑️ Supprimer"), type="secondary"):
            try:
                _delete_revenue(db, DISTRIBUTOR_TABLES[del_distributor],
                                del_target_id, int(del_year), int(del_month))
                flash(t("imusician.entry_deleted",
                        "Entrée supprimée : {distributor} — {month} {year}").format(
                    distributor=del_distributor, month=_month_name(del_month),
                    year=del_year))
                st.rerun()
            except Exception as e:
                st.error(t("common.error", "Erreur : {err}").format(err=e))


def render_break_even(db, artist_id: int) -> None:
    """The break-even: revenue against every spend, on one treasury.

    R476 (owner W11 : « point mort / revenu net → vue croisée, renommée … × Revenus ») —
    rendered by the cross view's « Revenus » section only. Its redesign is R488.
    """
    st.subheader(t("imusician.roi_header", "💹 Point mort"))
    span_min, span_max = _roi_data_span(db, artist_id)
    if span_min is None or span_max is None:
        st.info(t(
            "imusician.roi_no_data",
            "Aucune donnée de revenus distributeur ni de dépenses Meta Ads pour cet artiste. "
            "Importez un export iMusician (page Import CSV), saisissez un revenu "
            "ci-dessus, ou lancez la collecte Meta depuis l'accueil."
        ))
        return
    # R259/R478 — the shared selector (same presets, whole history by default).
    window = filters.span(span_min, span_max, key="imusician_roi",
                          artist_id=artist_id,
                          latest_release_resolver=lambda: filters.latest_release_date(
                              db, artist_id))
    # R488 (W11 « redesign (échelle) ») : the three tiles and the captions are gone —
    # revenue, spend and ROI ride in the title — and the figure reads revenue against
    # spend on a log axis, where 200 € of sales no longer flatten under 3 000 € of ads.
    from src.dashboard.utils.artist_cashflow import break_even, monthly_net
    from src.dashboard.utils.treasury_chart import (
        breakeven_figure, breakeven_text, load_cashflow, within)
    cashflow = within(load_cashflow(db, artist_id), window.start, window.end)
    mensuel = monthly_net(cashflow)
    if mensuel.empty:
        st.info(t("imusician.roi_empty_period",
                  "Aucune donnée de revenus ou dépenses sur cette période."))
        return
    fig = breakeven_figure(cashflow, mensuel, verdict=breakeven_text(break_even(mensuel)),
                           trigger=_trigger_point(db, artist_id))
    charts.plotly_chart(fig, width="stretch", decision=False)


def _trigger_point(db, artist_id: int):
    """(label, €) — what a Discover Weekly trigger is worth at THIS artist's rate, or None.

    The value is an order of magnitude (the median of tracks that triggered, times the
    artist's measured €/stream), never a promised gain — the label says « vaut ».
    """
    from src.dashboard.utils.artist_cashflow import stream_rate, trigger_value
    try:
        taux = stream_rate(db, artist_id)
        if not taux:
            return None
        valeurs = trigger_value(db, taux['eur_par_stream'])
    except Exception:      # noqa: BLE001 — the point is optional, the curve is not
        return None
    if valeurs is None or valeurs.empty or 'algo' not in valeurs.columns:
        return None
    dw = valeurs[valeurs['algo'] == 'DW']
    if dw.empty or not float(dw['valeur_eur'].iloc[0] or 0):
        return None
    return (t("imusician.trigger_point", "Un déclenchement Discover Weekly vaut"),
            float(dw['valeur_eur'].iloc[0]))
