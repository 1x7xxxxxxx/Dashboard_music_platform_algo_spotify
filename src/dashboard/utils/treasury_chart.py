"""The artist's treasury — every euro in and out, one figure, one data door.

Type: Utility
Uses: plotly, pandas, src.dashboard.utils.artist_cashflow (monthly_net), i18n
Depends on: v_artist_monthly_cashflow (migration 133)
Triggers: views/revenue_forecast.py, views/imusician.py, views/sacem.py
Persists in: nothing

R212 (2026-09-27). The owner read four figures that each answered a slice of one question —
sales per month (iMusician), « is my ad spend covered » (iMusician), SACEM per quarter, and
the break-even chart — and asked for ONE treasury, readable like a ledger. Those slices also
read their money from different doors: gross revenue from `v_artist_monthly_revenue`, Meta
spend from `v_meta_daily`, while the break-even read the NET cashflow. Two pages could show
two different totals for the same months.

This module is the only place that draws the treasury, and `load_cashflow` is the only way
it reads money. A page that wants the treasury calls both; it never re-queries a revenue or
a spend view on its own.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.i18n import t

# Revenue pulls green, spend pulls warm: the reader who cannot tell hues apart still
# reads the sign from the side of the zero line the bar sits on.
FLUX_COLOURS = {
    "imusician":    "#1DB954",
    "distrokid":    "#57C785",
    "sacem":        "#8E44AD",
    "meta_ads":     "#FF6B35",
    "distribution": "#B07C4F",
    "mastering":    "#C9A227",
    "visuel":       "#C96A9B",
    "promo":        "#E0723C",
    "materiel":     "#9C6B4F",
    "autre":        "#8A8A8A",
}
FLUX_NAMES = {
    "imusician": "iMusician", "distrokid": "DistroKid", "sacem": "SACEM",
    "meta_ads": "Publicité Meta", "distribution": "Distribution",
    "mastering": "Mastering", "visuel": "Visuel", "promo": "Promo",
    "materiel": "Matériel", "autre": "Autre",
}

_COLUMNS = ['year', 'month', 'flux', 'source', 'amount_eur', 'direction']


def load_cashflow(db, artist_id: int | None) -> pd.DataFrame:
    """Every monthly money movement — for one artist, or summed over all (admin view).

    `None` means « all artists », never « artist 1 »: the admin pages that call this with
    `None` show the aggregate, exactly as the tables they replace did.
    """
    if artist_id is not None:
        return db.fetch_df(
            """SELECT year, month, flux, source, amount_eur, direction
               FROM v_artist_monthly_cashflow WHERE artist_id = %s""",
            (artist_id,))
    # R220 — « all artists » means the HUMAN ones: the sandbox (tenant 18) mirrors
    # artist 1 byte for byte, and summing it doubled the admin treasury (−5 906 € for
    # −2 833 €, measured on a prod snapshot 2026-09-27). An inactive human keeps its
    # money history, so the predicate is « not canary, not sandbox », not « active ».
    # R226 — the SQL is shared with the nightly invariant that checks it on prod data.
    from src.utils.fleet_money import FLEET_CASHFLOW_SQL
    return db.fetch_df(FLEET_CASHFLOW_SQL)


def within(cashflow: pd.DataFrame, from_date, to_date) -> pd.DataFrame:
    """The movements whose month starts inside [from_date, to_date], month-granular."""
    if cashflow is None or cashflow.empty or from_date is None:
        return pd.DataFrame(columns=_COLUMNS) if cashflow is None else cashflow
    d = cashflow.copy()
    first = pd.to_datetime(d['year'].astype(int).astype(str) + "-"
                           + d['month'].astype(int).astype(str).str.zfill(2) + "-01")
    lo = pd.Timestamp(from_date).to_period('M').to_timestamp()
    hi = pd.Timestamp(to_date).to_period('M').to_timestamp()
    return d[(first >= lo) & (first <= hi)]


def treasury_figure(cashflow: pd.DataFrame, mensuel: pd.DataFrame,
                    projection: pd.DataFrame | None = None,
                    verdict: str | None = None) -> go.Figure:
    """Monthly flows on top (in above zero, out below, net as a marker), the running
    balance below. `projection` and `verdict` are the premium page's additions."""
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
        row_heights=[0.5, 0.5],
        subplot_titles=[
            t("revenue_forecast.frame_flows", "Ce qui rentre et ce qui sort, chaque mois (€)"),
            t("revenue_forecast.frame_cumul", "Où j'en suis au total (€) — le point mort est à zéro"),
        ])
    d = cashflow.copy()
    d['date'] = pd.to_datetime(
        d['year'].astype(int).astype(str) + "-"
        + d['month'].astype(int).astype(str).str.zfill(2) + "-01")
    d['amount_eur'] = pd.to_numeric(d['amount_eur'], errors='coerce')
    _add_flow_bars(fig, d)
    # The month balance only where money moved: a month without any movement is a true
    # 0 € in the ledger, but a marker on it is noise that hides the months that count.
    moved = mensuel[mensuel['revenus'].abs().gt(0) | mensuel['depenses'].abs().gt(0)]
    fig.add_trace(go.Scatter(
        x=moved['date'], y=moved['net'], mode='markers',
        name=t("revenue_forecast.net_month", "Solde du mois"),
        marker={'symbol': 'diamond', 'size': 9, 'color': "#FFFFFF",
                'line': {'color': "#333", 'width': 1}},
        hovertemplate="%{x|%m/%Y}<br>solde : %{y:+.2f} €<extra></extra>",
    ), row=1, col=1)
    _add_balance(fig, mensuel, projection)
    if verdict:
        fig.add_annotation(
            xref="paper", yref="paper", x=0.99, y=0.30, xanchor="right",
            text=verdict, showarrow=False, align="right",
            bgcolor="rgba(0,0,0,0.55)", bordercolor="#FF6B35", borderwidth=1,
            borderpad=7, font={'size': 13, 'color': "#FFFFFF"})
    fig.update_layout(
        barmode='relative', hovermode='x unified', height=640,
        legend={'orientation': 'h', 'yanchor': 'top', 'y': -0.08,
                'xanchor': 'left', 'x': 0},
        margin={'t': 40, 'b': 90})
    fig.update_yaxes(title_text="€", row=1, col=1)
    fig.update_yaxes(title_text="€", row=2, col=1)
    return fig


def _add_flow_bars(fig: go.Figure, d: pd.DataFrame) -> None:
    """One bar series per source; the SIGN carries the direction, the colour the source."""
    for flux, sign in (("revenu", 1), ("depense", -1)):
        part = d[d['flux'] == flux]
        for source in sorted(part['source'].unique()):
            serie = part[part['source'] == source].groupby('date')['amount_eur'].sum(min_count=1)
            fig.add_trace(go.Bar(
                x=serie.index, y=serie.values * sign,
                name=t(f"revenue_forecast.source.{source}", FLUX_NAMES.get(source, source)),
                marker={'color': FLUX_COLOURS.get(source, "#8A8A8A")},
                hovertemplate="%{x|%m/%Y}<br>%{fullData.name} : %{y:.2f} €<extra></extra>",
            ), row=1, col=1)


def _add_balance(fig: go.Figure, mensuel: pd.DataFrame,
                 projection: pd.DataFrame | None) -> None:
    """The running balance — the only curve that answers « am I back in my costs »."""
    positive = mensuel['cumul'].iloc[-1] >= 0
    fig.add_trace(go.Scatter(
        x=mensuel['date'], y=mensuel['cumul'], mode='lines',
        name=t("revenue_forecast.line_cumul", "Cumul net"),
        line={'color': "#1DB954" if positive else "#C0392B", 'width': 3},
        fill='tozeroy',
        fillcolor="rgba(29,185,84,0.12)" if positive else "rgba(192,57,43,0.10)",
        hovertemplate="%{x|%m/%Y}<br>cumul : %{y:.2f} €<extra></extra>",
    ), row=2, col=1)
    if projection is not None and not projection.empty:
        fig.add_trace(go.Scatter(
            x=[mensuel['date'].iloc[-1], *projection['date']],
            y=[mensuel['cumul'].iloc[-1], *projection['cumul']],
            mode='lines', name=t("revenue_forecast.line_proj", "Projection"),
            line={'color': "#FF6B35", 'width': 2, 'dash': 'dash'},
            hovertemplate="%{x|%m/%Y}<br>projeté : %{y:.2f} €<extra></extra>",
        ), row=2, col=1)
    fig.add_hline(y=0, line={'color': "#888", 'width': 1, 'dash': 'dot'}, row=2, col=1)
    fig.add_annotation(
        xref="x2 domain", yref="y2", x=0.01, y=0,
        text=t("revenue_forecast.breakeven_line", "point mort"),
        showarrow=False, yshift=9, font={'size': 11, 'color': "#888"})


def ledger_summary(cashflow: pd.DataFrame, mensuel: pd.DataFrame,
                   streams_total: float | None) -> dict:
    """The one-line ledger above the treasury (R236): money in, money out (ads apart),
    the result, and what the ads bought in streams. Pure.

    `streams_total` is every platform's streams from the start (`platform_totals`); the
    cost per stream divides ad spend by ALL streams, organic included — it is a ceiling
    on what ads cost per stream, not an attribution, and the page says so."""
    d = cashflow.copy() if cashflow is not None else pd.DataFrame(columns=['flux', 'source', 'amount_eur'])
    d['amount_eur'] = pd.to_numeric(d.get('amount_eur'), errors='coerce')
    rev = d.loc[d['flux'] == 'revenu', 'amount_eur'].sum(min_count=1)
    out = d.loc[d['flux'] == 'depense', 'amount_eur'].sum(min_count=1)
    ads = d.loc[(d['flux'] == 'depense') & (d['source'] == 'meta_ads'), 'amount_eur'].sum(min_count=1)
    cumul = float(mensuel['cumul'].iloc[-1]) if mensuel is not None and not mensuel.empty else None
    def val(v):
        return None if pd.isna(v) else float(v)
    ads_v = val(ads)
    return {
        'revenue': val(rev), 'spend': val(out), 'ads': ads_v,
        'other': (val(out) - (ads_v or 0.0)) if val(out) is not None else None,
        'result': cumul, 'streams': streams_total,
        'cost_per_stream': (ads_v / streams_total) if ads_v and streams_total else None,
    }
