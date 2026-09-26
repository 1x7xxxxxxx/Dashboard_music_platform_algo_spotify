"""Redraw each panel of the Grafana ops dashboard from production Prometheus, as PNG.

Type: Utility
Uses: deploy/grafana/dashboards/streamlytics-ops.json, Prometheus HTTP API (query_range),
      plotly + kaleido (dev extra)
Triggers: tools/dev/charts_dossier/main.py (`make charts-dossier`)
Persists in: <out>/grafana/*.png and <out>/grafana.json — outside the repository

R203 (2026-09-26). Grafana has no image renderer (`GF_INSTALL_PLUGINS` is empty on purpose —
installing a plugin at boot calls grafana.com), and Prometheus listens on the box's
127.0.0.1:9090 only. So each panel's PromQL runs through an SSH tunnel, READ-ONLY HTTP GETs,
and is redrawn with its title, unit and legend format. The panels carry no template variable
and fixed `[5m]` windows, so no `$__rate_interval` substitution is needed (code-critic).

⚠️ A gap stays a gap (`connectgaps=False`): Plotly does not apply Grafana's null handling,
and a line drawn across missing scrapes would read as « nothing happened » — the opposite.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
DASHBOARD = ROOT / "deploy" / "grafana" / "dashboards" / "streamlytics-ops.json"
_UNITS = {"s": "secondes", "percent": "%", "bytes": "octets", "reqps": "requêtes/s",
          "ops": "lignes/s"}


def panels(path: Path = DASHBOARD) -> list[dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for p in d.get("panels", []):
        out.append({"id": p["id"], "title": p.get("title", ""),
                     "unit": (p.get("fieldConfig", {}).get("defaults", {}) or {}).get("unit"),
                     "targets": [(t.get("expr", ""), t.get("legendFormat", ""))
                                 for t in p.get("targets", []) if t.get("expr")]})
    return out


def legend(fmt: str, labels: dict) -> str:
    """Grafana's `{{label}}` substitution; the whole label set when no format."""
    if not fmt:
        return ", ".join(f"{k}={v}" for k, v in sorted(labels.items()) if k != "__name__") or "série"
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(labels.get(m.group(1), "")), fmt)


def query_range(base: str, expr: str, start: float, end: float, step: int) -> list[dict]:
    qs = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    with urllib.request.urlopen(f"{base}/api/v1/query_range?{qs}", timeout=60) as r:
        body = json.load(r)
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "réponse Prometheus invalide"))
    return body["data"]["result"]


def draw(panel: dict, series: list[tuple[str, list]], png: Path) -> None:
    import datetime as dt

    import plotly.graph_objects as go
    fig = go.Figure()
    for name, values in series:
        xs = [dt.datetime.fromtimestamp(float(t)) for t, _ in values]
        ys = [None if v in ("NaN", "+Inf", "-Inf") else float(v) for _, v in values]
        # Markers too: at low traffic a p95 exists only as isolated points between gaps,
        # and a line between two gaps draws nothing — the panel looked empty (seen, R203).
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", marker=dict(size=4),
                                 name=name[:60], connectgaps=False))
    unit = _UNITS.get(panel["unit"] or "", panel["unit"] or "")
    fig.update_layout(title=panel["title"], height=380, yaxis_title=unit,
                      legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
                      margin=dict(t=50, b=110, l=60, r=20), template="plotly_white")
    fig.write_image(png, width=1000, height=380, scale=1)


def render(out: Path, base: str, days: int = 7) -> dict:
    import time
    gdir = out / "grafana"
    gdir.mkdir(parents=True, exist_ok=True)
    end = time.time()
    start = end - days * 86400
    step = max(60, int(days * 86400 / 400))
    rendered, failed = [], []
    for p in panels():
        series = []
        try:
            for expr, fmt in p["targets"]:
                for s in query_range(base, expr, start, end, step):
                    series.append((legend(fmt, s.get("metric", {})), s.get("values", [])))
            png = f"grafana_{p['id']:02d}.png"
            draw(p, series, gdir / png)
            points = sum(1 for _, vals in series for _, v in vals
                         if v not in ("NaN", "+Inf", "-Inf"))
            rendered.append({"id": p["id"], "title": p["title"], "png": f"grafana/{png}",
                             "series": len(series), "points": points,
                             "queries": [e for e, _ in p["targets"]]})
        except Exception as exc:  # noqa: BLE001 — listed as not rendered, never dropped
            from src.utils.safe_error import safe_error
            failed.append({"id": p["id"], "title": p["title"], "reason": safe_error(exc, limit=200)})
    result = {"days": days, "panels": rendered, "not_rendered": failed}
    (out / "grafana.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    return result
