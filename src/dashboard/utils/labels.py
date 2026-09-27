"""Short axis labels that stay distinct.

Type: Utility
Uses: nothing
Triggers: views/meta_ads_overview.py, views/trigger_algo/_tab_catalogue.py,
          utils/s4a_entry_insight.py, utils/pdf_charts.py (_hbar)
Persists in: nothing

R209 (2026-09-27). A label cut to a fixed length is used as the CATEGORY of a bar axis;
two names that share their first N characters then become ONE category, and the chart
draws two bars on one row — their numbers overlap (PDF: « 305 » inside the bar of 422, a
title and its remix) or ten bars stack on one line (YouTube: ten titles sharing « DJ Set
multicamera Hardtechno… »). Class `a-truncated-label-that-merges-two-categories`.
"""
from __future__ import annotations


def unique_short_labels(names, n: int = 34) -> list[str]:
    """Each name cut to `n` characters — and still DISTINCT from the others.

    The plain cut keeps the start (« Qui a sali mon slip… »). When two plain cuts clash,
    those names are cut in the MIDDLE instead, which keeps their tail (« … (Remix) »);
    a clash that survives even that gets its rank. Names that do not clash keep the
    plain cut, so a chart without collisions looks exactly as before."""
    names = [str(x) if x is not None else "—" for x in names]

    def plain(x: str) -> str:
        return x if len(x) <= n else x[: n - 1] + "…"

    def middle(x: str) -> str:
        return x if len(x) <= n else x[: n // 2 - 1] + "…" + x[-(n // 2 - 1):]

    short = [plain(x) for x in names]
    out: list[str] = []
    for i, x in enumerate(names):
        label = short[i] if short.count(short[i]) == 1 else middle(x)
        out.append(label if label not in out else f"{label} ({i + 1})")
    return out
