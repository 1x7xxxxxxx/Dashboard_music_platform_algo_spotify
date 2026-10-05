"""Tab 1 of Trigger Algo, redone (R247, fiche 42): your last releases, how close each is to
each algorithm, and the values that would trigger it.

Type: Sub
Uses: src.utils.ml_inference (local_sensitivity), src.dashboard.utils.algo_knowledge
      (ALGO_FEATURE_ZONES, decode_feature_value), plotly
Triggers: views/trigger_algo/_tab_catalogue.py
Persists in: nothing

Owner, 2026-09-27: « le plus simple possible, le plus visuel — les gens ne connaissent pas le
machine learning. Filtre automatique sur les cinq dernières sorties, cinq indicateurs, puis
la valeur de chaque paramètre et le point qui rapprocherait le plus de 100 % de trigger ».

TWO CHOICES, both from code-critic (R247):
- The indicator is NOT the probability. On this catalogue the calibrated probabilities sit
  on the Platt floor and differ by hundredths of a point; side by side they would read as
  a verdict, and one track would show a number next to its neighbour's « pas d'estimation
  fiable » for a rounding difference. The indicator is the SHORTEST ROUTE: for each lever,
  current value ÷ the value where the MODEL itself reaches P ≥ 80 % (other features held),
  and the best of those — « how far along the easiest way to trigger this algorithm ».
- The target comes from the model (a scan of `local_sensitivity`, the same exact calls the
  Pareto prices a lever with), and falls back to the knowledge-base reference only where
  the model never crosses 80 % — said on the figure (« repère »), never passed off as model.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils.algo_knowledge import ALGO_FEATURE_ZONES, decode_feature_value
from src.dashboard.utils.formats import num
from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import ALGO_COLORS
from src.dashboard.utils.labels import unique_short_labels as short_labels  # R209
from src.utils.algo_order import ALGO_NAMES, ALGO_ORDER

LEVERS = ("StreamsLast7Days", "NonAlgoStreams28Days", "SavesLast28Days", "PlaylistAddsLast28Days")
ALGOS = ALGO_ORDER
P_TARGET = 0.80
_OFFSET = (-0.3, 0.0, 0.3)   # one per algorithm, inside a track's slot
MAX_TRACKS = 5


def _curve(algo: str, feature: str, feats: dict, targets: tuple):
    from src.utils.ml_inference import local_sensitivity
    return local_sensitivity(algo, feature, feats, n_points=25, targets=targets)


def model_target(algo: str, fid: str, feats: dict, curve=_curve) -> tuple:
    """(target value, source) for one lever: the lowest value ≥ current where the model's
    calibrated P reaches `P_TARGET`, source « modèle »; else the reference, source
    « repère »; (None, None) when the lever is not the algo's or cannot be read."""
    spec = ALGO_FEATURE_ZONES.get(algo, {}).get(fid)
    if not spec or spec.get("actionable") is False:
        return None, None
    current = decode_feature_value(algo, fid, feats)
    if current is None:
        return None, None
    ref = spec.get("target")
    got = curve(algo, spec["json_key"], feats, (ref,) if ref else ())
    if got:
        for x, p in sorted(zip(got["x_human"], got["probs"])):
            if p is not None and p >= P_TARGET and x >= current:
                return float(x), "modèle"
    return (float(ref), "repère") if ref else (None, None)


def track_levers(feats: dict, curve=_curve) -> dict:
    """{(algo, lever): {current, target, source, progress}} for one track. Pure given `curve`."""
    out = {}
    for algo in ALGOS:
        for fid in LEVERS:
            target, source = model_target(algo, fid, feats, curve)
            if target is None:
                continue
            current = decode_feature_value(algo, fid, feats) or 0.0
            out[(algo, fid)] = {"current": current, "target": target, "source": source,
                                "progress": min(current / target, 1.0) if target > 0 else None}
    return out


def shortest_route(levers: dict, algo: str) -> dict | None:
    """The lever of `algo` closest to its target — the indicator's value. Pure."""
    mine = [(fid, v) for (a, fid), v in levers.items() if a == algo and v["progress"] is not None]
    if not mine:
        return None
    fid, best = max(mine, key=lambda kv: kv[1]["progress"])
    return {"lever": fid, **best}


def by_proximity(tracks: list[str], levers_by_track: dict) -> list[str]:
    """Tracks, the one closest to ANY gate first (R263, critic (b)). Pure.

    The gauges were drawn in release order; the question they answer is « which one do
    I push », so the closest leads. A track with no measurable route goes last.
    """
    def best(song):
        routes = [shortest_route(levers_by_track.get(song, {}), a) for a in ALGOS]
        return max((r["progress"] for r in routes if r), default=-1.0)
    return sorted(tracks, key=best, reverse=True)


def last_releases(df: pd.DataFrame, n: int = MAX_TRACKS) -> list[str]:
    """The `n` most recent songs by days since release (unknown age last). Pure."""
    if df is None or df.empty:
        return []
    d = df.assign(_age=pd.to_numeric(df["days_since_release"], errors="coerce"))
    return d.sort_values("_age", na_position="last")["song"].head(n).tolist()


def indicators_figure(tracks: list[str], levers_by_track: dict):
    """One gauge per (algorithm, track): the shortest route, 0-100 %. Pure."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    cols = max(len(tracks), 1)
    names = dict(zip(tracks, short_labels(tracks, 24)))
    fig = make_subplots(rows=len(ALGOS), cols=cols,
                        specs=[[{"type": "indicator"}] * cols] * len(ALGOS),
                        vertical_spacing=0.12, horizontal_spacing=0.04)
    for r, algo in enumerate(ALGOS, start=1):
        for c, song in enumerate(tracks, start=1):
            route = shortest_route(levers_by_track.get(song, {}), algo)
            value = None if route is None else round(100 * route["progress"])
            fig.add_trace(go.Indicator(
                mode="gauge+number", value=value, number={"suffix": " %", "font": {"size": 18}},
                title={"text": (f"<b>{ALGO_NAMES[algo]}</b><br>" if c == 1 else "")
                       + (f"<span style='font-size:11px'>{names[song]}</span>" if r == 1 else ""),
                       "font": {"size": 11}},
                gauge={"axis": {"range": [0, 100], "visible": False},
                       "bar": {"color": ALGO_COLORS[algo]},
                       "threshold": {"line": {"color": "#333", "width": 2}, "value": 100}}),
                row=r, col=c)
    fig.update_layout(height=150 * len(ALGOS) + 40, margin=dict(t=40, b=10, l=10, r=10))
    return fig


def values_figure(tracks: list[str], levers_by_track: dict):
    """One small panel per lever: each track's current value (bar) and, per algorithm, the
    value that would trigger it (marker) — full « modèle », faded « repère ». Pure."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    labels = {fid: next((z[fid]["label"] for z in ALGO_FEATURE_ZONES.values() if fid in z), fid)
              for fid in LEVERS}
    fig = make_subplots(rows=1, cols=len(LEVERS), subplot_titles=[labels[f] for f in LEVERS],
                        horizontal_spacing=0.06)
    shown, xs = set(), short_labels(tracks, 18)
    pos = list(range(len(tracks)))
    for c, fid in enumerate(LEVERS, start=1):
        cur = [next((v["current"] for (a, f), v in levers_by_track.get(s, {}).items() if f == fid),
                    None) for s in tracks]
        # The current value is often a few dozen against a target in thousands: the bar
        # alone is a sliver (render, 2026-09-27), so its number is WRITTEN on it.
        fig.add_trace(go.Bar(x=pos, y=cur, width=0.85, hovertext=xs, marker_color="#c8ced6", cliponaxis=False,
                             text=[None if v is None else num(v, 0)
                                   for v in cur], textposition="outside",
                             name=t("trigger_algo.rel.current", "Ta valeur"),
                             showlegend=c == 1, legendgroup="cur"), row=1, col=c)
        for k, algo in enumerate(ALGOS):
            pts = [levers_by_track.get(s, {}).get((algo, fid)) for s in tracks]
            if not any(pts):
                continue
            fig.add_trace(go.Scatter(
                x=[i + _OFFSET[k] for i in pos], y=[p["target"] if p else None for p in pts],
                customdata=[[x, p["source"] if p else ""] for x, p in zip(xs, pts)],
                mode="markers", name=ALGO_NAMES[algo], legendgroup=algo,
                showlegend=algo not in shown,
                # One symbol, drawn by its LINE colour; a « repère » is the same stroke,
                # faded — the first render used « line-ew-open », which Plotly strokes with
                # `marker.color` (unset → black), and read identical to the model's target.
                marker=dict(symbol="line-ew", size=11, color=ALGO_COLORS[algo],
                            opacity=[0.35 if p and p["source"] == "repère" else 1.0 for p in pts],
                            line=dict(width=4, color=ALGO_COLORS[algo])),
                hovertemplate="%{customdata[0]} — " + ALGO_NAMES[algo]
                              + " : %{y:,.0f} (%{customdata[1]})<extra></extra>"),
                row=1, col=c)
            shown.add(algo)
    # Three algorithms often aim at the SAME value (2 000 streams): each sits at its own
    # offset inside the track's slot instead of hiding the others. A numeric axis, because
    # Plotly's `scattermode="group"` made the bars disappear (render, 2026-09-27).
    fig.update_xaxes(tickvals=pos, ticktext=xs, range=[-0.6, len(tracks) - 0.4])
    fig.update_layout(height=400, legend=dict(orientation="h", y=-0.3), margin=dict(t=50))
    return fig
