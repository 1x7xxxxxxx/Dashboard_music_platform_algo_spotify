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
MAX_TRACKS = 2  # V63 (R404): two tracks read side by side, five did not


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


NO_COMPARISON = None


def comparison_options(newest_first: list[str], reference: str | None) -> list:
    """The comparison filter's options (R579): « none » first, then every other release,
    newest first — the default index (1) is the release before the reference. Pure."""
    return [NO_COMPARISON] + [s_ for s_ in newest_first if s_ != reference]


def lever_weights(feats_by_track: dict, loader=None) -> dict:
    """{algo: {feature: mean |SHAP|}} over the chosen tracks — R559 (fiches 46, 47, 57).

    The owner asked for « les trois paramètres les plus importants » per playlist, and for
    the levers of fiche 47 in decreasing weight. The weight is the classifier's own SHAP
    contribution on THESE tracks, averaged in absolute value; an algorithm whose model is
    missing is left out, and the figures fall back to the fixed `LEVERS` order. Pure but
    for the loader."""
    from src.utils.ml_inference import FEATURE_COLUMNS
    from src.utils.shap_explain import explain
    if loader is None:
        from ._common._loaders import _load_xgb_model as loader
    if not feats_by_track:
        return {}
    X = pd.DataFrame([[float((f or {}).get(c, 0.0) or 0.0) for c in FEATURE_COLUMNS]
                      for f in feats_by_track.values()], columns=FEATURE_COLUMNS)
    out = {}
    for algo in ALGOS:
        model = loader(f"{algo.lower()}_classifier")
        if model is None:
            continue
        vals = abs(pd.DataFrame(explain(model, X).values)).mean(axis=0)
        out[algo] = {c: float(v) for c, v in zip(FEATURE_COLUMNS, vals)}
    return out


def top_features(weights: dict, algo: str, n: int = 3) -> list[str]:
    """The `n` heaviest features of one playlist, heaviest first. Pure."""
    w = weights.get(algo, {})
    return sorted((f for f in w if w[f] > 0), key=lambda f: -w[f])[:n]


def _lever_weight(weights: dict, algo: str, fid: str) -> float:
    key = ALGO_FEATURE_ZONES.get(algo, {}).get(fid, {}).get("json_key", fid)
    return weights.get(algo, {}).get(key, 0.0)


def _track_title(name: str, stats: dict | None) -> str:
    if not stats:
        return f"<b>{name}</b>"
    # R571 — « 28 j » ends on the last imported day: say it, or a stale import reads
    # as a track that stopped streaming.
    until = stats.get("until")
    span = (t("trigger_algo.rel.window_until", "28 j jusqu'au {d}").format(
                d=until.strftime("%d/%m")) if until is not None else "28 j")
    return (f"<b>{name}</b><br><span style='font-size:11px'>"
            + t("trigger_algo.rel.stats28", "{w} : {s} écoutes · {v} saves · {a} ajouts").format(
                w=span, s=num(stats.get("streams"), 0), v=num(stats.get("saves"), 0),
                a=num(stats.get("adds"), 0)) + "</span>")


def lever_label(feature: str) -> str:
    """A criterion's name on this page — R570: « ajouts en playlist 28 j », not the column."""
    from ._common._explain import _FEATURE_LABELS
    if feature.startswith("PlaylistAddsLast28Days"):
        return t("trigger_algo.rel.adds28", "Ajouts en playlist 28 j")
    return t(f"algo.label.{feature}", _FEATURE_LABELS.get(feature, (feature, True))[0])


def feature_value(key: str, feats: dict | None):
    """A model column's human value: `_log` columns are stored as log1p. Pure."""
    import math
    raw = (feats or {}).get(key)
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return math.expm1(v) if key.endswith("_log") else v


def _value_text(v) -> str:
    if v is None:
        return "—"
    return num(v, 2) if abs(v) < 10 and v != int(v) else num(v, 0)


def shap_share(weights: dict, algo: str, key: str) -> float | None:
    """`key`'s share of the playlist's total mean |SHAP| — « 40 % » of the decision. Pure."""
    w = weights.get(algo, {})
    total = sum(w.values())
    return w.get(key, 0.0) / total if total > 0 else None


def _playlist_box(algo: str, weights: dict, feats: dict | None = None) -> str:
    """The playlist's name as a pill, then « déclenché par » its three heaviest criteria —
    each with its SHAP share and its current value per title (R580)."""
    tops = top_features(weights, algo)
    if not tops:
        return f"<b>{ALGO_NAMES[algo]}</b>"
    feats = feats or {}
    lines = []
    for i, f in enumerate(tops, start=1):
        share = shap_share(weights, algo, f)
        vals = " / ".join(_value_text(feature_value(f, x)) for x in feats.values())
        lines.append(f"{i}. {lever_label(f)} — <b>{round(100 * share)} %</b>"
                     + (f" · {vals}" if vals else ""))
    head = t("trigger_algo.rel.triggered_by", "déclenché par (poids · valeur) :")
    return (f"<b>{ALGO_NAMES[algo]}</b><br><span style='font-size:11px'><i>{head}</i>"
            f"<br>{'<br>'.join(lines)}</span>")


def streams_gap(levers: dict, algo: str) -> float | None:
    """The 7-day streams still missing to the model's target for `algo` — a GAP. Pure."""
    v = levers.get((algo, "StreamsLast7Days"))
    if not v:
        return None
    return max(float(v["target"]) - float(v["current"] or 0.0), 0.0)


def trigger_value(est: dict | None, algo: str, rate: float | None) -> tuple | None:
    """(streams, €) a triggered playlist usually brings in its first 28 days: the cohort's
    P50 at one month, at the title's own rate. None when refused or unreadable. Pure."""
    cell = ((est or {}).get("estimates") or {}).get(algo.lower(), {}).get("j28") or {}
    if cell.get("refused") or "p50" not in cell:
        return None
    streams = float(cell["p50"])
    return streams, (streams * rate if rate else None)


def money_line(levers: dict, algo: str, money: dict | None, song: str) -> str:
    """Under a gauge (R581): the Meta budget to close the 7-day streams gap at the best
    CPR, and what the playlist would bring once triggered. Pure.

    The gap is a GAP, never a threshold (`test_no_view_buys_streams_up_to_a_threshold`);
    pricing streams with a cost per CLICK assumes one click ≈ one stream — « ≈ »."""
    from src.dashboard.utils.algo_preview_data import budget_pour_streams
    from src.dashboard.utils.formats import eur
    if not money:
        return ""
    parts = []
    gap, cpr = streams_gap(levers, algo), money.get("cpr")
    # The CPR is the same under every gauge: `cpr_note` writes it ONCE, under the figure —
    # repeated per gauge, the line was wider than a gauge and two neighbours overlapped.
    if gap is not None and gap <= 0:
        parts.append(t("trigger_algo.rel.gap_met", "écoutes 7 j : atteint"))
    elif gap is not None:
        cost = budget_pour_streams(gap, cpr)
        parts.append(t("trigger_algo.rel.gap", "manque {n} écoutes 7 j").format(n=num(gap, 0)))
        if cost is not None:
            parts.append(t("trigger_algo.rel.budget", "≈ {b} de pub").format(b=eur(cost, 0)))
    value = trigger_value(money.get("est"), algo, (money.get("rate") or {}).get(song))
    if value:
        parts.append(t("trigger_algo.rel.worth", "si déclenchée :<br>{s} écoutes / 28 j").format(
            s=num(value[0], 0)) + ("" if value[1] is None else f" ≈ {eur(value[1], 0)}"))
    return "<br>".join(parts)


def cpr_note(money: dict | None) -> str:
    """The best CPR the budgets under the gauges are priced at, said once. Pure."""
    cpr = (money or {}).get("cpr")
    if not cpr:
        return ""
    return t("trigger_algo.rel.cpr_note", "budgets de pub au meilleur CPR : {c}").format(
        c=f"{cpr:.3f} €".replace(".", ","))


def _mini_chart(fig, algo: str, row: int, col: int, est: dict, readings: dict) -> None:
    """R583 — « ce qu'un déclenchement rapporte » beside the playlist: the cohort's 28-day
    streams by age, dotted over its P25–P75 band, and each title's readings."""
    from . import _tab_algo_streams as ests
    cells = (est.get("estimates") or {}).get(algo.lower()) or {}
    # R586 — no legend: beside the pills and the gauges it had no free corner and sat on
    # a gauge. The column's header names the dotted median, the band and the two marks.
    first = False
    ests.cohort_traces(fig, cells, ALGO_COLORS[algo], row=row, col=col, first=first)
    for song, symbol in zip(readings, ("circle", "square")):
        ests.reading_trace(fig, readings[song], algo, song=song, symbol=symbol,
                           row=row, col=col, first=first)
    limit = ests.x_max(est.get("estimates") or {}, list(readings.values()))
    ests.refused_notes(fig, cells, limit, row=row, col=col)
    vals, text = ests.age_ticks(limit)
    fig.update_xaxes(tickvals=vals, ticktext=text, range=[0, round(limit * 1.18)],
                     tickfont=dict(size=10), row=row, col=col)
    fig.update_yaxes(rangemode="tozero", tickfont=dict(size=10), row=row, col=col)


def indicators_figure(tracks: list[str], levers_by_track: dict, weights: dict | None = None,
                      stats: dict | None = None, *, feats: dict | None = None,
                      money: dict | None = None, readings: dict | None = None):
    """One row per playlist: its pill, one gauge per track, and what a trigger brings. Pure.

    R477 (W14) — the pill is drawn in the playlist's colour. R559 — it names « déclenché
    par » the three heaviest criteria; each track's title carries its 28-day figures.
    R580 (owner, 2026-10-15) — each criterion carries its SHAP share and its value per
    title. R581 — under each gauge, the Meta budget at the best CPR to close the 7-day
    streams gap, and what the playlist brings once triggered. R583 — with `money["est"]`,
    a last column draws the cohort's 28-day streams by age beside the gauges.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    weights, stats, money = weights or {}, stats or {}, money or {}
    est, readings = money.get("est") or {}, readings or {}
    mini = bool(est.get("estimates"))
    cols = max(len(tracks), 1)
    names = dict(zip(tracks, short_labels(tracks, 24)))
    gauge_w = (0.46 if mini else 0.72) / cols
    widths = [0.28] + [gauge_w] * cols + ([0.26] if mini else [])
    spec_row = [None] + [{"type": "indicator"}] * cols + ([{"type": "xy"}] if mini else [])
    fig = make_subplots(rows=len(ALGOS), cols=len(widths), column_widths=widths,
                        specs=[spec_row] * len(ALGOS), vertical_spacing=0.12,
                        horizontal_spacing=0.03)
    for r, algo in enumerate(ALGOS, start=1):
        for c, song in enumerate(tracks, start=2):
            route = shortest_route(levers_by_track.get(song, {}), algo)
            value = None if route is None else round(100 * route["progress"])
            fig.add_trace(go.Indicator(
                mode="gauge+number", value=value, number={"suffix": " %", "font": {"size": 30}},
                title={"text": _track_title(names[song], stats.get(song)) if r == 1 else "",
                       "font": {"size": 15}},
                gauge={"axis": {"range": [0, 100], "visible": False},
                       "bar": {"color": ALGO_COLORS[algo]},
                       "threshold": {"line": {"color": "#333", "width": 2}, "value": 100}}),
                row=r, col=c)
            line = money_line(levers_by_track.get(song, {}), algo, money, song)
            if line:
                x0, x1 = fig.data[-1].domain.x
                fig.add_annotation(x=(x0 + x1) / 2, y=fig.data[-1].domain.y[0], xref="paper",
                                   yref="paper", yanchor="top", showarrow=False, text=line,
                                   font={"size": 10, "color": "#555"})
        y0, y1 = fig.data[-1].domain.y
        fig.add_annotation(x=0.0, y=(y0 + y1) / 2, xref="paper", yref="paper",
                           xanchor="left", align="left", showarrow=False,
                           text=_playlist_box(algo, weights, {s_: (feats or {}).get(s_)
                                                              for s_ in tracks}),
                           font={"size": 13, "color": "white"}, bordercolor=ALGO_COLORS[algo],
                           borderwidth=2, borderpad=6, bgcolor=ALGO_COLORS[algo])
        if mini:
            _mini_chart(fig, algo, r, len(widths), est, readings)
    note = cpr_note(money)
    if note:
        fig.add_annotation(x=0.0, y=0.0, xref="paper", yref="paper", xanchor="left",
                           yanchor="top", yshift=-48, showarrow=False, text=note,
                           font={"size": 11, "color": "#555"})
    if mini:
        fig.add_annotation(x=1.0, y=1.0, xref="paper", yref="paper", xanchor="right",
                           yanchor="bottom", showarrow=False, font={"size": 12},
                           text=t("trigger_algo.rel.mini_head",
                                  "<b>Ce qu'un déclenchement rapporte</b> — écoutes / 28 j")
                           + "<br>" + t("trigger_algo.rel.mini_key",
                                        "┄ médiane (P50) · bande P25–P75 · ● ■ tes titres"))
    fig.update_layout(height=240 * len(ALGOS) + 120, margin=dict(t=80, b=70, l=10, r=10))
    return fig


def values_figure(tracks: list[str], levers_by_track: dict, weights: dict | None = None):
    """One panel per playlist, DW → Radio → RR: each lever's progress toward the value that
    would trigger it, one bar per track, levers in decreasing SHAP weight. Pure.

    R559 (fiche 47, owner 2026-10-13 : « pas mal comme info, par contre très moche ») —
    the four panels of raw values put a few dozen saves beside a target in thousands, and
    three markers per slot. Each bar is now a share of ITS target (100 % = triggers), the
    two numbers are written on it, and a target the model never reached says « repère ».
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    weights = weights or {}
    labels = {fid: (lever_label(fid) if fid.startswith("PlaylistAdds") else
                    next((z[fid]["label"] for z in ALGO_FEATURE_ZONES.values() if fid in z), fid))
              for fid in LEVERS}
    algos = [a for a in ALGOS if any((a, f) in levers_by_track.get(s, {})
                                     for s in tracks for f in LEVERS)]
    if not algos:
        return None
    fids = {a: sorted((f for f in LEVERS
                       if any((a, f) in levers_by_track.get(s, {}) for s in tracks)),
                      key=lambda f: (-_lever_weight(weights, a, f), LEVERS.index(f)))
            for a in algos}
    fig = make_subplots(rows=len(algos), cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=[ALGO_NAMES[a] for a in algos],
                        row_heights=[len(fids[a]) for a in algos])
    xs = short_labels(tracks, 18)
    for r, algo in enumerate(algos, start=1):
        for k, (song, name) in enumerate(zip(tracks, xs)):
            pts = [levers_by_track.get(song, {}).get((algo, f)) for f in fids[algo]]
            fig.add_trace(go.Bar(
                y=[labels[f] for f in fids[algo]], orientation="h", name=name,
                x=[None if p is None or p["progress"] is None else 100 * p["progress"]
                   for p in pts],
                text=[None if p is None else f"{num(p['current'], 0)} / {num(p['target'], 0)}"
                      + (" (repère)" if p["source"] == "repère" else "") for p in pts],
                textposition="outside", cliponaxis=False, legendgroup=name,
                showlegend=r == 1, marker_color=ALGO_COLORS[algo],
                marker_pattern_shape="" if k == 0 else "/",
                hovertemplate=name + " · %{y}<br>%{text}<extra></extra>"),
                row=r, col=1)
        fig.add_vline(x=100, line_dash="dash", line_color="#666", row=r, col=1)
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(range=[0, 135], ticksuffix=" %", showticklabels=False)
    fig.update_layout(barmode="group", height=90 + 60 * sum(len(v) for v in fids.values()),
                      margin=dict(t=50, l=10, r=10, b=20))
    return fig
