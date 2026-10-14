"""Where a legend can sit without hiding data: the emptiest corner of the plot (R565).

Type: Utility
Uses: plotly figure objects (read only), pandas (date parsing)
Triggers: charts.apply_defaults
Persists in: nothing

Owner, 2026-10-15: « les légendes sont mal placées partout — un placement optimal
calculé ». R536 had put every legend top-right, on the plot; a rising line or a Pareto's
first bar lives exactly there. This module projects every visible point of every
cartesian trace into the plot's unit square and answers which corner is EMPTY — or None,
and the door then puts the legend below the plot. It returns a corner NAME, never a
position: placing the legend stays the door's job (`tests/test_one_legend_position.py`).
"""
from __future__ import annotations

import math

import pandas as pd

CORNERS = ("top right", "top left", "bottom right", "bottom left")
_CARTESIAN = {"scatter", "scattergl", "bar"}
_STEPS = 12  # points sampled per line segment / bar body


def _visible(tr) -> bool:
    return tr.visible not in (False, "legendonly")


def _numbers(values, kind: str, cats: list) -> list[float | None]:
    out: list[float | None] = []
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None)
        elif kind == "category":
            out.append(float(cats.index(v)) if v in cats else None)
        elif kind == "date":
            out.append(pd.Timestamp(v).value / 1e9)
        elif kind == "log":
            out.append(math.log10(v) if v > 0 else None)
        else:
            out.append(float(v))
    return out


def _kind(axis, values: list) -> str:
    if axis.type in ("log", "date", "category"):
        return axis.type
    sample = next((v for v in values if v is not None), None)
    if isinstance(sample, str):
        try:
            pd.Timestamp(sample)
            return "date"
        except ValueError:
            return "category"
    if hasattr(sample, "year") and hasattr(sample, "month"):
        return "date"
    return "linear"


def _axis_name(tr, letter: str) -> str:
    ref = getattr(tr, f"{letter}axis") or letter
    return f"{letter}axis{ref[1:]}"


def _values(tr, letter: str) -> list:
    raw = getattr(tr, letter)
    if raw is None:
        return list(range(len(tr.y if letter == "x" else tr.x) or ()))
    return list(raw)


def _categories(fig, axis_key: str, letter: str, num_letter: str) -> list:
    """Category order on one axis, honouring the door's Pareto `total …` order."""
    totals: dict = {}
    for tr in fig.data:
        if tr.type in _CARTESIAN and _axis_name(tr, letter) == axis_key:
            for c, v in zip(_values(tr, letter), _values(tr, num_letter)):
                totals[c] = totals.get(c, 0) + (v if isinstance(v, (int, float)) else 0)
    order = fig.layout[axis_key].categoryorder or ""
    if order.startswith("total"):
        return sorted(totals, key=totals.get, reverse=order.endswith("descending"))
    return list(totals)


def _raw_points(tr, fig, xk: str, yk: str, stack: dict) -> list[tuple[float, float]]:
    xs, ys = _values(tr, "x"), _values(tr, "y")
    horiz = tr.type == "bar" and tr.orientation == "h"
    kx = _kind(fig.layout[xk], xs)
    ky = _kind(fig.layout[yk], ys)
    nx = _numbers(xs, kx, _categories(fig, xk, "x", "y") if kx == "category" else [])
    ny = _numbers(ys, ky, _categories(fig, yk, "y", "x") if ky == "category" else [])
    pts = [(x, y) for x, y in zip(nx, ny) if x is not None and y is not None]
    if tr.type == "bar":
        return _bar_body(pts, horiz, (kx if horiz else ky) == "log",
                         fig.layout.barmode in ("stack", "relative"), stack)
    if "lines" in (tr.mode or "lines") and len(pts) > 1:
        return [(a[0] + (b[0] - a[0]) * i / _STEPS, a[1] + (b[1] - a[1]) * i / _STEPS)
                for a, b in zip(pts, pts[1:]) for i in range(_STEPS + 1)]
    return pts


def _bar_body(pts, horiz: bool, log: bool, stacked: bool, stack: dict) -> list:
    """A bar from its base to its value; stacked bars start where the previous one ended."""
    if log:
        return pts
    out = []
    for x, y in pts:
        cat, val = (y, x) if horiz else (x, y)
        key = (cat, val >= 0)  # `relative`: negatives stack downward from zero
        base = stack.get(key, 0.0) if stacked else 0.0
        if stacked:
            stack[key] = base + val
        out += [(base + val * i / _STEPS, cat) if horiz else (cat, base + val * i / _STEPS)
                for i in range(_STEPS + 1)]
    return out


def _axis_kind(fig, key: str, letter: str) -> str:
    """The kind of one axis, read from the first visible trace drawn on it."""
    for tr in fig.data:
        if tr.type in _CARTESIAN and _visible(tr) and _axis_name(tr, letter) == key:
            return _kind(fig.layout[key], _values(tr, letter))
    return fig.layout[key].type or "linear"


def _range(axis, kind: str) -> list[float] | None:
    """The axis's fixed range in point units — a date range arrives as dates (R565)."""
    if not axis.range or kind == "category" or None in axis.range:
        return None
    if kind == "date":
        return [pd.Timestamp(v).value / 1e9 for v in axis.range]
    return [float(v) for v in axis.range]  # a log range is already in log10


def _unit(vals: list[float], axis, kind: str = "linear") -> list[float]:
    rng = _range(axis, kind)
    lo, hi = (rng if rng else (min(vals), max(vals)))
    span = (hi - lo) or 1.0
    dom = axis.domain or (0, 1)
    return [dom[0] + (dom[1] - dom[0]) * (v - lo) / span for v in vals]


def paper_points(fig) -> list[tuple[float, float]]:
    """Every visible cartesian point of `fig`, in the plot's unit square. Pure."""
    by_axes: dict[tuple[str, str], list[tuple[float, float]]] = {}
    stacks: dict[tuple[str, str], dict] = {}
    for tr in fig.data:
        if tr.type not in _CARTESIAN or not _visible(tr):
            continue
        xk, yk = _axis_name(tr, "x"), _axis_name(tr, "y")
        by_axes.setdefault((xk, yk), []).extend(
            _raw_points(tr, fig, xk, yk, stacks.setdefault((xk, yk), {})))
    out: list[tuple[float, float]] = []
    for (xk, yk), pts in by_axes.items():
        if not pts:
            continue
        # a bar's zero belongs to its VALUE axis only — on a time axis it is 1970
        bars = [tr for tr in fig.data if tr.type == "bar" and _visible(tr)
                and (_axis_name(tr, "x"), _axis_name(tr, "y")) == (xk, yk)]
        zero_x = any(tr.orientation == "h" for tr in bars) and fig.layout[xk].type != "log"
        zero_y = any(tr.orientation != "h" for tr in bars) and fig.layout[yk].type != "log"
        xs = [p[0] for p in pts] + ([0.0] if zero_x else [])
        ys = [p[1] for p in pts] + ([0.0] if zero_y else [])
        ux = _unit(xs, fig.layout[xk], _axis_kind(fig, xk, "x"))
        uy = _unit(ys, fig.layout[yk], _axis_kind(fig, yk, "y"))
        out += list(zip(ux[:len(pts)], uy[:len(pts)]))
    return out


def box(corner: str, entries: int) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) the legend covers in that corner, growing with its entries."""
    w, h = 0.32, min(0.6, 0.08 * entries + 0.06)
    x0, x1 = (1 - w, 1.0) if corner.endswith("right") else (0.0, w)
    y0, y1 = (1 - h, 1.0) if corner.startswith("top") else (0.0, h)
    return x0, x1, y0, y1


def empty_corner(fig, entries: int) -> str | None:
    """The first corner (top right first) no data point falls in, or None. Pure."""
    pts = paper_points(fig)
    if not pts and any(tr.type not in _CARTESIAN for tr in fig.data):
        return "top right"
    for corner in CORNERS:
        x0, x1, y0, y1 = box(corner, entries)
        if not any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in pts):
            return corner
    return None
