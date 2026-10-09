"""The artist's treasury — every euro in and out, one figure, one data door.

Type: Utility
Uses: plotly, pandas, src.dashboard.utils.artist_cashflow (monthly_net), i18n
Depends on: v_artist_monthly_cashflow (migration 133)
Triggers: views/revenue_forecast.py, views/imusician.py (breakeven_figure, R488)
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
from src.dashboard.utils.semantic_colors import BON

# Revenue pulls green, spend pulls warm: the reader who cannot tell hues apart still
# reads the sign from the side of the zero line the bar sits on.
REVENUE_CUMUL = "#1F4E79"   # the same navy as the distributors' cumul (imusician)

FLUX_COLOURS = {
    "imusician":    BON,          # R260 — the semantic « good » green, not Spotify's
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


def _dated(cashflow: pd.DataFrame) -> pd.DataFrame:
    d = cashflow.copy()
    d['date'] = pd.to_datetime(
        d['year'].astype(int).astype(str) + "-"
        + d['month'].astype(int).astype(str).str.zfill(2) + "-01")
    d['amount_eur'] = pd.to_numeric(d['amount_eur'], errors='coerce')
    return d


def flow_cumuls(cashflow: pd.DataFrame, months) -> tuple[pd.Series, pd.Series]:
    """(revenue, spend) running totals over `months`, both POSITIVE. Pure (R488)."""
    d = _dated(cashflow)
    idx = pd.DatetimeIndex(pd.to_datetime(months))
    out = []
    for flux in ("revenu", "depense"):
        serie = d[d['flux'] == flux].groupby('date')['amount_eur'].sum(min_count=1)
        out.append(serie.reindex(idx).fillna(0).cumsum())
    return out[0], out[1]


def _positive(s: pd.Series) -> list:
    """A log axis cannot draw 0 or a negative: those months are left blank, not faked."""
    return [float(v) if v > 0 else None for v in s.values]


def breakeven_figure(cashflow: pd.DataFrame, mensuel: pd.DataFrame,
                     verdict: str | None = None,
                     trigger: tuple[str, float] | None = None) -> go.Figure:
    """Revenue cumulated against spend cumulated, on a LOG axis — the break-even is
    where the two lines cross (R488, owner W11 « redesign (échelle) »).

    The net-balance figure drew 200 € of sales as a flat line under 3 000 € of ads:
    on a linear axis two magnitudes fifteen times apart cannot both be read. On a log
    axis the gap between the lines IS the ratio, and a crossing stays a crossing —
    the transform is monotone. `trigger` is (label, €): what one Discover Weekly
    trigger would add to the revenue total, as a point, never a line."""
    rev, spend = flow_cumuls(cashflow, mensuel['date'])
    fig = go.Figure()
    for serie, name, colour in (
            # Navy, not the « good » green: against Meta's orange it is ΔE 9.5 in protan.
            (rev, t("revenue_forecast.rev_cumul", "Revenus cumulés (ventes + SACEM)"),
             REVENUE_CUMUL),
            (spend, t("revenue_forecast.spend_cumul", "Dépenses cumulées (Meta + coûts)"),
             FLUX_COLOURS["meta_ads"])):
        fig.add_trace(go.Scatter(
            x=serie.index, y=_positive(serie), mode='lines', name=name,
            line={'color': colour, 'width': 3}, connectgaps=False,
            hovertemplate="%{x|%m/%Y}<br>%{fullData.name} : %{y:,.2f} €<extra></extra>"))
    if trigger and trigger[1]:
        label, value = trigger
        y = float(rev.iloc[-1]) + float(value)
        fig.add_trace(go.Scatter(
            x=[rev.index[-1]], y=[y], mode='markers+text', name=label,
            marker={'color': "#FF6B35", 'size': 11, 'symbol': 'star'},
            text=[f"+{value:,.0f} €".replace(",", " ")], textposition='top center',
            hovertemplate=f"{label}<br>revenus atteints : %{{y:,.2f}} €<extra></extra>"))
    if verdict:
        fig.add_annotation(
            xref="paper", yref="paper", x=0.99, y=0.04, xanchor="right", yanchor="bottom",
            text=verdict, showarrow=False, align="right",
            bgcolor="rgba(0,0,0,0.55)", bordercolor="#FF6B35", borderwidth=1,
            borderpad=7, font={'size': 13, 'color': "#FFFFFF"})
    r, s_ = float(rev.iloc[-1]), float(spend.iloc[-1])
    roi = f"{100 * (r - s_) / s_:+.0f} %" if s_ else "—"
    fig.update_layout(
        title=t("revenue_forecast.breakeven_title",
                "Revenus {r} contre dépenses {s} · ROI {roi} — point mort au croisement"
                ).format(r=f"{r:,.0f} €".replace(",", " "),
                         s=f"{s_:,.0f} €".replace(",", " "), roi=roi),
        hovermode='x unified', height=460, yaxis={'type': 'log', 'title': "€"},
        legend={'orientation': 'h', 'yanchor': 'top', 'y': -0.12,
                'xanchor': 'left', 'x': 0},
        margin={'t': 50, 'b': 90})
    return fig


def source_cumuls(d: pd.DataFrame, months) -> dict[str, pd.Series]:
    """{source: signed running total over `months`}: revenue climbs, spending falls. Pure.

    A month without movement carries the total forward — a cumul never drops back."""
    out = {}
    idx = pd.DatetimeIndex(pd.to_datetime(months))
    for flux, sign in (("revenu", 1), ("depense", -1)):
        part = d[d['flux'] == flux]
        for source in sorted(part['source'].unique()):
            serie = part[part['source'] == source].groupby('date')['amount_eur'].sum(min_count=1)
            out[source] = (serie.reindex(idx).fillna(0) * sign).cumsum()
    return out


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


# ── R262 — the break-even sentence, ONE definition for every page that draws the treasury
# (it lived in revenue_forecast only; the Distributeurs page drew the same curve mute).
def breakeven_short(pm: dict) -> str:
    """La même vérité en trois mots, pour une tuile."""
    if pm['etat'] == 'deja':
        return t("revenue_forecast.be_short_done", "atteint")
    if pm['etat'] == 'jamais':
        return t("revenue_forecast.be_short_never", "jamais à ce rythme")
    if pm['etat'] == 'trop_court':
        return t("revenue_forecast.be_short_too_short", "trop tôt pour dater")
    if pm['etat'] == 'inconnu' or pm.get('mois') is None:
        return "—"
    if pm['mois'] < 24:
        return t("revenue_forecast.be_short_months", "{n} mois").format(n=pm['mois'])
    return t("revenue_forecast.be_short_years", "{a:,.0f} ans").format(
        a=pm['mois'] / 12.0).replace(",", " ")


def breakeven_text(pm: dict) -> str:
    """La phrase du point mort — et les quatre états qu'elle doit savoir dire."""
    if pm['etat'] == 'deja':
        return t("revenue_forecast.be_done",
                 "✅ Tu es rentré dans tes frais<br>cumul : {c:+,.0f} €"
                 ).format(c=pm['cumul']).replace(",", " ")
    if pm['etat'] == 'inconnu':
        return t("revenue_forecast.be_unknown", "Pas encore d'historique")
    if pm['etat'] == 'trop_court':
        return t("revenue_forecast.be_too_short",
                 "⏳ Il manque {c:,.0f} € — {n} mois connus seulement :<br>"
                 "trop tôt pour dater le point mort").format(
                     c=-pm['cumul'], n=pm.get('mois_connus', 0)).replace(",", " ")
    if pm['etat'] == 'jamais':
        return t("revenue_forecast.be_never",
                 "⚠️ Point mort JAMAIS atteint à ce rythme<br>"
                 "il manque {c:,.0f} € et le rythme est de {r:+.2f} €/mois"
                 ).format(c=-pm['cumul'], r=pm['rythme']).replace(",", " ")
    ans = pm['mois'] / 12.0
    duree = (t("revenue_forecast.be_months", "{n} mois").format(n=pm['mois'])
             if pm['mois'] < 24
             else t("revenue_forecast.be_years", "{n:,.0f} mois — {a:,.0f} ans"
                    ).format(n=pm['mois'], a=ans).replace(",", " "))
    date = (f" ({pm['date']:%m/%Y})" if pm['date'] else "")
    return t("revenue_forecast.be_reached",
             "⏳ Point mort dans <b>{d}</b>{q}<br>"
             "il manque {c:,.0f} € au rythme de {r:+.2f} €/mois"
             ).format(d=duree, q=date, c=-pm['cumul'], r=pm['rythme']).replace(",", " ")
