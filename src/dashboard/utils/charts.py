"""Shared Plotly chart builders for Meta Ads views.

Type: Utility
Uses: plotly, pandas
Persists in: nothing

Factors the dual-axis Pareto (spend bars + CPR line) reused across the overview
and breakdowns views. Coerces Postgres NUMERIC (Decimal) to float so Plotly/Altair
never mis-type the columns.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def pareto_spend_cpr(df, dim_col: str, title: str, *, top_n: int = 15):
    """Bar (spend) + line (CPR) dual-axis Pareto, sorted by spend desc, top N.

    `df` must expose `dim_col`, `spend`, `results`. CPR = spend/results (None when
    no result → the line gaps, never a fake 0). Returns a go.Figure or None if empty.
    """
    if df is None or df.empty:
        return None
    df = df.copy()
    df['spend'] = pd.to_numeric(df['spend'], errors='coerce').fillna(0.0)
    df['results'] = pd.to_numeric(df['results'], errors='coerce').fillna(0.0)
    df['cpr'] = (df['spend'] / df['results'].where(df['results'] != 0)).astype(float)
    df = df.sort_values('spend', ascending=False).head(top_n)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[dim_col], y=df['spend'], name='Dépense (€)',
        marker_color='rgba(0, 63, 92, 0.6)', yaxis='y',
    ))
    fig.add_trace(go.Scatter(
        x=df[dim_col], y=df['cpr'], name='CPR (€)', mode='lines+markers',
        line={'color': '#ff6361', 'width': 3}, yaxis='y2',
    ))
    fig.update_layout(
        title=title,
        yaxis={'title': 'Dépense (€)', 'showgrid': False},
        yaxis2={'title': 'CPR (€)', 'overlaying': 'y', 'side': 'right', 'showgrid': False},
        showlegend=False, height=400, margin={'t': 50},
    )
    return fig
