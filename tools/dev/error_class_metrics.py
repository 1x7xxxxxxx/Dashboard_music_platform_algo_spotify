#!/usr/bin/env python3
"""Export the health of the error-class catalogue as Prometheus metrics (textfile).

Type: Utility
Uses: tools/dev/generated_cache.py (error_class_health.build, in memory — R345; needs the
      full git history: tools/deploy.sh unshallows the server's clone)
Triggers: tools/deploy.sh (on the server, after the pull) ; `make error-class-metrics`
Persists in: <dir>/streamlytics_error_classes.prom — read by node_exporter's textfile collector

R264 (owner notes L60-65 : « suivre dans le temps la pertinence et les échecs de chaque
classe »). Critic verdict (critic-2026-09-27.md, R264 b) : NOT a table in the tenants'
database, and NOT a second parser — the payload is the output of the one parser that
defines « récidive », so this only re-reads it. Grafana then draws the series. R345: the
payload is computed for the tree (`generated_cache.health_payload()`), no longer read from
a versioned JSON — which is why `deploy.sh` unshallows the prod clone first.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILENAME = "streamlytics_error_classes.prom"


def render(doc: dict) -> str:
    """The textfile body. Pure. Every sample carries its HELP/TYPE."""
    agg = doc["aggregate"]
    pop, rec, holes = agg["population"], agg["recurrence"], agg["holes"]
    lines = [
        "# HELP streamlytics_error_classes Error classes in the catalogue, by kind.",
        "# TYPE streamlytics_error_classes gauge",
    ]
    for kind, value in sorted(pop.items()):
        lines.append(f'streamlytics_error_classes{{kind="{kind}"}} {float(value)}')
    obs = rec.get("observed") or {}
    lines += [
        "# HELP streamlytics_error_class_recurrence_per_class_month Observed recurrences "
        "per class and per month (catalogue history, error_class_health).",
        "# TYPE streamlytics_error_class_recurrence_per_class_month gauge",
        f"streamlytics_error_class_recurrence_per_class_month {float(obs.get('per_class_month', 0.0))}",
        "# HELP streamlytics_error_class_holes Classes missing a piece of verifiable knowledge.",
        "# TYPE streamlytics_error_class_holes gauge",
    ]
    for hole, value in sorted(holes.items()):
        lines.append(f'streamlytics_error_class_holes{{hole="{hole}"}} {float(value)}')
    return "\n".join(lines) + "\n"


def write(directory: Path, doc: dict) -> Path:
    """Atomic: node_exporter must never read a half-written file."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / FILENAME
    tmp = target.with_suffix(".prom.tmp")
    tmp.write_text(render(doc), encoding="utf-8")
    os.replace(tmp, target)
    return target


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: error_class_metrics.py <textfile-directory>", file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import generated_cache
    target = write(Path(sys.argv[1]), generated_cache.health_payload())
    print(f"écrit : {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
