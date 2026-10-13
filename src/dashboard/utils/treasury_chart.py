"""The artist's treasury — every euro in and out, one figure, one data door.

Type: Utility
Uses: plotly, pandas, src.dashboard.utils.artist_cashflow (monthly_net), i18n
Depends on: v_artist_monthly_cashflow (migration 133)
Triggers: views/revenue_forecast.py, views/imusician.py (breakeven_figure, R488;
          cashflow_figure, R519)
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

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.dashboard.utils.i18n import t
from src.dashboard.utils.semantic_colors import BON, MAUVAIS

# The reader who cannot tell hues apart still reads the sign from the side of the zero
# line a bar sits on; the shades (`INFLOW_RAMP`, `OUTFLOW_RAMP`) differ by LIGHTNESS.
REVENUE_CUMUL = "#1F4E79"   # the same navy as the distributors' cumul (imusician)
# R553 (owner Y1, fiche 25 : « les dépenses en rouge et les revenus en vert ») — the
# semantic pair, separated by LIGHTNESS (ΔE 20,1 in deuteranopia), not by hue alone.
BREAKEVEN_REVENUE, BREAKEVEN_SPEND = BON, MAUVAIS
# The projection is DRAWN on a bounded horizon, never written as « 270 ans » (fiche 25).
PROJECTION_CAP_MONTHS = 24

FLUX_NAMES = {
    "imusician": "iMusician", "distrokid": "DistroKid", "sacem": "SACEM",
    "meta_ads": "Publicité Meta", "distribution": "Distribution",
    "mastering": "Mastering", "visuel": "Visuel", "promo": "Promo",
    "materiel": "Matériel", "autre": "Autre",
}

# R561 (owner, Trésorerie 2026-10-13 evening : « un dégradé de couleur verte pour les
# entrées et un dégradé de couleur rouge pour les sorties ») — the SIDE of the money is
# the hue, the source is the shade: darkest = the biggest source of its side.
INFLOW_RAMP = ("#1B5E20", "#A5D6A7")
OUTFLOW_RAMP = ("#8E1B1B", "#F2A7A7")

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
                     trigger: tuple[str, float] | None = None,
                     projection_months: int = 0) -> go.Figure:
    """Revenue cumulated AGAINST spend cumulated — the point mort and the ROI regression
    in ONE figure (R561, owner Trésorerie 2026-10-13 evening : « fusionner le graphique
    point mort et le graphique ROI régression linéaire en un seul »).

    The owner read the regression (one point per month, spend on x, revenue on y) and not
    the two lines over time. So the months stay points on a spend × revenue plane, but
    each carries the running TOTALS: the diagonal revenue = spend IS the break-even, the
    side of it the path sits on is the answer, and the dotted continuation is the revenue
    and spend trend at the pace `break_even` dates the crossing with. Both axes are LOG
    (R488): 200 € of sales stay readable beside 3 000 € of ads, and y = x stays straight.
    `trigger` is (label, €): what one Discover Weekly trigger would add, as a star."""
    rev, spend = flow_cumuls(cashflow, mensuel['date'])
    p_rev, p_spend = projected_cumuls(rev, spend, projection_months)
    fig = go.Figure()
    values = [*rev, *spend, *p_rev, *p_spend,
              float(rev.iloc[-1]) + float((trigger or (0, 0))[1] or 0)]
    _add_breakeven_zones(fig, values)
    fig.add_trace(go.Scatter(
        x=_positive(spend), y=_positive(rev), mode='lines+markers+text',
        name=t("revenue_forecast.path", "Toi, mois après mois"),
        line={'color': REVENUE_CUMUL, 'width': 3},
        marker={'size': 8, 'color': [BREAKEVEN_REVENUE if r >= s_ else BREAKEVEN_SPEND
                                      for r, s_ in zip(rev, spend)],
                'line': {'color': "#FFFFFF", 'width': 1}},
        text=_ends(rev.index), textposition='top center', cliponaxis=False,
        customdata=[f"{d:%m/%Y}" for d in rev.index],
        hovertemplate=t("revenue_forecast.path_hover",
                        "%{customdata}<br>dépensé depuis le début : %{x:,.0f} €"
                        "<br>rentré depuis le début : %{y:,.0f} €<extra></extra>")))
    _add_projection(fig, p_rev, p_spend)
    _add_trigger(fig, rev, spend, trigger)
    if verdict:
        fig.add_annotation(
            xref="paper", yref="paper", x=0.99, y=0.04, xanchor="right", yanchor="bottom",
            text=verdict, showarrow=False, align="right",
            bgcolor="rgba(0,0,0,0.55)", bordercolor="#FF6B35", borderwidth=1,
            borderpad=7, font={'size': 13, 'color': "#FFFFFF"})
    r, s_ = float(rev.iloc[-1]), float(spend.iloc[-1])
    roi = f"{100 * (r - s_) / s_:+.0f} %" if s_ else "—"
    bounds = _plane_bounds(values)
    if bounds:
        rng = [math.log10(bounds[0]), math.log10(bounds[1])]
        fig.update_xaxes(range=rng, dtick=1, tickformat=",.0f")
        fig.update_yaxes(range=rng, dtick=1, tickformat=",.0f")
    fig.update_layout(
        title=t("revenue_forecast.breakeven_title",
                "Revenus {r} contre dépenses {s} · ROI {roi}"
                ).format(r=f"{r:,.0f} €".replace(",", " "),
                         s=f"{s_:,.0f} €".replace(",", " "), roi=roi),
        hovermode='closest', height=500, margin={'t': 50, 'b': 60}, separators=", ",
        xaxis={'type': 'log', 'title': t("revenue_forecast.axis_spend",
                                         "Dépensé depuis le début (pub + coûts), €")},
        yaxis={'type': 'log', 'title': t("revenue_forecast.axis_revenue",
                                         "Rentré depuis le début (ventes + SACEM), €")})
    return fig


def _ends(index) -> list[str]:
    """The first month written on the path (where it starts), the others on hover only —
    the last point carries the star and the projection's start, a label would collide."""
    return [f"{d:%m/%Y}" if i == 0 else "" for i, d in enumerate(index)]


def _plane_bounds(values) -> tuple[float, float] | None:
    """(lo, hi) of the log plane: three decades at most under the biggest total, so a
    first month of 0,04 € does not stretch the axis over six decades. Pure."""
    pos = [float(v) for v in values if pd.notna(v) and float(v) > 0]
    if not pos:
        return None
    hi = max(pos) * 1.4
    return max(min(pos) * 0.7, hi / 1000), hi


def _add_breakeven_zones(fig: go.Figure, values) -> None:
    """The diagonal revenue = spend, the half-plane above it green, below it red."""
    bounds = _plane_bounds(values)
    if bounds is None:
        return
    lo, hi = bounds
    for xs, ys, colour, name in (
            ([lo, hi, lo], [lo, hi, hi], "rgba(39,117,26,0.08)",
             t("revenue_forecast.zone_paid", "au-dessus : ta pub est remboursée")),
            ([lo, hi, hi], [lo, hi, lo], "rgba(236,121,121,0.10)",
             t("revenue_forecast.zone_short", "en dessous : il te manque de l'argent"))):
        fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines', fill='toself', fillcolor=colour,
                                 line={'width': 0}, name=name, hoverinfo='skip'))
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode='lines', hoverinfo='skip',
        name=t("revenue_forecast.diagonal", "Point mort : rentré = dépensé"),
        line={'color': "#555555", 'width': 2, 'dash': 'dash'}))


def projection_horizon(pm: dict) -> int:
    """How many months to draw ahead: up to the crossing (+3) when it falls inside the
    cap, the cap otherwise — the scale stays readable whatever the date (fiche 25)."""
    if pm.get('etat') == 'atteint' and pm.get('mois') is not None \
            and pm['mois'] + 3 <= PROJECTION_CAP_MONTHS:
        return max(6, int(pm['mois']) + 3)
    return PROJECTION_CAP_MONTHS if pm.get('etat') in ('atteint', 'jamais', 'deja') else 0


def projected_cumuls(rev: pd.Series, spend: pd.Series, months: int
                     ) -> tuple[pd.Series, pd.Series]:
    """Both cumuls prolonged `months` ahead at their mean monthly step over the last
    `FENETRE_RYTHME` months. Pure; each projection starts ON the last measured point."""
    from dateutil.relativedelta import relativedelta
    from src.dashboard.utils.artist_cashflow import FENETRE_RYTHME
    if months <= 0 or rev.empty:
        empty = pd.Series(dtype=float)
        return empty, empty
    last = pd.Timestamp(rev.index[-1])
    idx = pd.DatetimeIndex([last + relativedelta(months=i) for i in range(months + 1)])
    out = []
    for serie in (rev, spend):
        step = float(serie.diff().fillna(serie.iloc[0]).tail(FENETRE_RYTHME).mean())
        out.append(pd.Series([float(serie.iloc[-1]) + step * i for i in range(months + 1)],
                             index=idx))
    return out[0], out[1]


def _add_projection(fig: go.Figure, p_rev: pd.Series, p_spend: pd.Series) -> None:
    """The path continued, dotted, at the pace of the last `FENETRE_RYTHME` months."""
    if p_rev.empty:
        return
    fig.add_trace(go.Scatter(
        x=_positive(p_spend), y=_positive(p_rev), mode='lines+text',
        name=t("revenue_forecast.projection", "Tendance prévue au rythme des 12 derniers mois"),
        line={'color': REVENUE_CUMUL, 'width': 2, 'dash': 'dot'},
        text=[""] * (len(p_rev) - 1) + [f"{p_rev.index[-1]:%m/%Y}"],
        textposition='bottom right', cliponaxis=False,
        customdata=[f"{d:%m/%Y}" for d in p_rev.index],
        hovertemplate=t("revenue_forecast.projection_hover",
                        "%{customdata} (prévu)<br>dépensé : %{x:,.0f} €"
                        "<br>rentré : %{y:,.0f} €<extra></extra>")))


def _add_trigger(fig: go.Figure, rev: pd.Series, spend: pd.Series, trigger) -> None:
    if not (trigger and trigger[1]):
        return
    label, value = trigger
    y = float(rev.iloc[-1]) + float(value)
    fig.add_trace(go.Scatter(
        x=[float(spend.iloc[-1])], y=[y], mode='markers+text', name=label,
        marker={'color': "#FF6B35", 'size': 13, 'symbol': 'star'},
        text=[f"+{value:,.0f} €".replace(",", " ")], textposition='top center',
        cliponaxis=False,
        hovertemplate=f"{label}<br>rentré : %{{y:,.2f}} €<extra></extra>"))


def _ramp(ends: tuple[str, str], n: int) -> list[str]:
    """`n` hex colours from the dark end to the light end, evenly spaced. Pure."""
    a, b = ([int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)] for h in ends)
    steps = [i / (n - 1) if n > 1 else 0.0 for i in range(n)]
    return ["#" + "".join(f"{round(x + (y - x) * k):02X}" for x, y in zip(a, b))
            for k in steps]


def flux_shades(cashflow: pd.DataFrame) -> dict[tuple[str, str], str]:
    """{(flux, source): colour} — revenue on the green ramp, spending on the red one,
    each side ranked by its total (biggest = darkest). Pure (R561)."""
    d = _dated(cashflow)
    out = {}
    for flux, ends in (("revenu", INFLOW_RAMP), ("depense", OUTFLOW_RAMP)):
        totals = (d[d['flux'] == flux].groupby('source')['amount_eur'].sum()
                  .abs().sort_values(ascending=False))
        out.update({(flux, src): c for src, c in zip(totals.index, _ramp(ends, len(totals)))})
    return out


def _flux_order(d: pd.DataFrame) -> list[tuple[str, str]]:
    """Revenue first, then spending; inside each side, biggest total first."""
    totals = d.groupby(['flux', 'source'])['amount_eur'].sum().abs()
    return sorted(totals.index, key=lambda k: (k[0] != 'revenu', -totals[k]))


def cashflow_figure(cashflow: pd.DataFrame) -> go.Figure:
    """Every euro, month by month, on ONE frame (R519, owner X11 II « Trésorerie »), and
    beside it ONE circle of where the euros came from and went (R561).

    Revenue (distributors, SACEM) stacks ABOVE zero in shades of green, spending (Meta
    Ads, entered costs) BELOW it in shades of red; the running balance is the line. The
    circle splits everything that moved — in AND out — so the full turn is 100 % and the
    green arc reads as the share of the money that came in."""
    d = _dated(cashflow)
    d['signed'] = d['amount_eur'] * pd.to_numeric(d['direction'], errors='coerce')
    months = pd.date_range(d['date'].min(), d['date'].max(), freq='MS')
    shades = flux_shades(cashflow)
    fig = make_subplots(rows=1, cols=2, column_widths=[0.72, 0.28], horizontal_spacing=0.05,
                        specs=[[{"type": "xy"}, {"type": "domain"}]])
    order = _flux_order(d)
    for flux, source in order:
        part = d[(d['flux'] == flux) & (d['source'] == source)]
        serie = part.groupby('date')['signed'].sum(min_count=1).reindex(months)
        fig.add_trace(go.Bar(
            x=months, y=serie.values, name=FLUX_NAMES.get(source, source),
            legendgroup=source, marker_color=shades[(flux, source)],
            hovertemplate="%{x|%m/%Y}<br>%{fullData.name} : %{y:+,.2f} €<extra></extra>"),
            row=1, col=1)
    balance = d.groupby('date')['signed'].sum().reindex(months).fillna(0).cumsum()
    fig.add_trace(go.Scatter(
        x=months, y=balance.values, mode='lines+markers',
        name=t("imusician.balance", "Solde cumulé"),
        line={'color': REVENUE_CUMUL, 'width': 3}, marker={'size': 5},
        hovertemplate="%{x|%m/%Y}<br>%{fullData.name} : %{y:+,.2f} €<extra></extra>"),
        row=1, col=1)
    money_in = float(d.loc[d['signed'] > 0, 'signed'].sum())
    money_out = float(-d.loc[d['signed'] < 0, 'signed'].sum())
    _add_share_circle(fig, d, order, shades, money_in, money_out)
    eur = lambda v, sign="": f"{v:{sign},.0f} €".replace(",", " ")   # noqa: E731
    fig.update_layout(
        title=t("imusician.cashflow_title", "Solde {b} — {i} entrés, {o} sortis").format(
            b=eur(float(balance.iloc[-1]), "+"), i=eur(money_in), o=eur(money_out)),
        barmode='relative', hovermode='x unified', height=460,
        yaxis={'title': "€", 'zeroline': True, 'zerolinewidth': 2},
        margin={'t': 50, 'b': 90})
    return fig


def share_of_total(d: pd.DataFrame, order) -> list[float]:
    """Each (flux, source)'s share of everything that moved, in %, summing to 100. Pure."""
    totals = [float(d[(d['flux'] == f) & (d['source'] == s)]['amount_eur'].abs().sum())
              for f, s in order]
    whole = sum(totals)
    return [100.0 * v / whole if whole else 0.0 for v in totals]


def _add_share_circle(fig: go.Figure, d: pd.DataFrame, order, shades,
                      money_in: float, money_out: float) -> None:
    shares = share_of_total(d, order)
    whole = money_in + money_out
    fig.add_trace(go.Pie(
        labels=[FLUX_NAMES.get(s, s) for _, s in order], values=shares, hole=0.55,
        sort=False, direction='clockwise', showlegend=False,
        marker={'colors': [shades[k] for k in order], 'line': {'color': "#FFFFFF", 'width': 1}},
        textinfo='percent', textposition='inside', insidetextorientation='horizontal',
        title={'text': t("imusician.circle_centre", "{p} %<br>entrés").format(
            p=f"{100 * money_in / whole:.0f}" if whole else "—"), 'font': {'size': 14}},
        hovertemplate="%{label} : %{percent} du total<extra></extra>"),
        row=1, col=2)


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
    # R553 (fiche 25 : « pas avec 270 ans en toutes lettres ») — beyond the drawn
    # horizon the sentence says « beyond », the dotted lines say how far apart.
    if pm['mois'] > PROJECTION_CAP_MONTHS:
        duree = t("revenue_forecast.be_beyond", "plus de {n} ans").format(
            n=PROJECTION_CAP_MONTHS // 12)
        date = ""
    else:
        duree = t("revenue_forecast.be_months", "{n} mois").format(n=pm['mois'])
        date = (f" ({pm['date']:%m/%Y})" if pm['date'] else "")
    return t("revenue_forecast.be_reached",
             "⏳ Point mort dans <b>{d}</b>{q}<br>"
             "il manque {c:,.0f} € au rythme de {r:+.2f} €/mois"
             ).format(d=duree, q=date, c=-pm['cumul'], r=pm['rythme']).replace(",", " ")
