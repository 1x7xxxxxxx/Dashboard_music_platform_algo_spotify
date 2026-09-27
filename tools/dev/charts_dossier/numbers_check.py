#!/usr/bin/env python3
"""Is each chart's number right? — a verdict per fiche, and the checks it rests on (R241).

Type: Utility
Uses: <out>/capture.json (traces), <out>/inventory.json (layer, sources),
      tools/dev/metric_registry.py (the SENSE of each gold object),
      src/utils/gold_invariants.py + src/utils/metric_bounds.py (run on the snapshot)
Triggers: `make charts-dossier` (writes <out>/checks.json), main.py (reads it)
Persists in: <out>/checks.json — OUTSIDE the repository

Owner, 2026-09-27: « vérifie tout, que les chiffres ne sont pas faux ». A chart is « vérifié »
only when THREE things hold, because each one alone has already let a wrong number through:

1. it reads the gold layer only — one definition per metric (ADR-019);
2. the nightly checks that cover what it reads are green ON THIS SNAPSHOT — two definitions
   that must agree do agree (`gold_invariants`), a sum stays under its lifetime total
   (`metric_bounds`);
3. what it DRAWS keeps the shape of what it reads — a rate never above 100 %, a cumul never
   going down. Reading gold is necessary, not sufficient: home once drew 23 251 over a
   window holding 8 490 while reading a correct helper (`metric_bounds.py`), and a CTR was
   multiplied by 100 twice after a correct read (code-critic, R241).

The snapshot is a `pg_dump` of production, so its views are the ones production runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VERDICTS = {"verifie": "✅ Chiffre vérifié", "ecart": "❌ Écart trouvé",
            "non-garanti": "⚠️ Non garanti", "non-rendu": "— Pas de rendu"}
_RATE_HINTS = ("%", "ctr", "taux", "rate")


def _is_rate(trace: dict) -> bool:
    text = f"{trace.get('name', '')} {trace.get('unit', '')}".lower()
    return any(h in text for h in _RATE_HINTS)


_SIGNED = ("net", "solde", "résultat", "resultat", "balance", "trésorerie")
# A cumul that falls by more than this share of its peak is the « absence written as zero »
# class (a counter back to 0 — `value_monitor.is_zero_reset`), not a correction. Measured on
# the snapshot 2026-09-27: the legitimate dips are iMusician adjustments (negative months)
# and YouTube removing invalid views — a few percent, never half.
MAX_CUMUL_DROP = 0.5


def _is_cumul(trace: dict) -> bool:
    """A cumul of a non-negative quantity. A signed balance (« Cumul net ») may go down."""
    text = f"{trace.get('name', '')} {trace.get('unit', '')}".lower()
    return "cumul" in text and not any(w in text for w in _SIGNED)


def verdict(traces: list[dict] | None, layer: str, sources: list[str],
            findings: list[str]) -> tuple[str, str]:
    """(verdict key, the reason in words). Pure."""
    if traces is None:
        return "non-rendu", "pas d'image : rien à vérifier tant qu'elle n'est pas rendue"
    hit = [f for f in findings if any(s and s in f for s in sources)]
    if hit:
        return "ecart", hit[0][:220]
    for tr in traces:
        if tr.get("dup_labels"):
            return "ecart", (f"« {tr['name'] or tr['unit'] or 'barres'} » : {tr['dup_labels']} "
                             "étiquette(s) portent deux barres — deux lignes lues sous un seul nom")
        # R252 — an INDEX axis (`charts.to_base100`, « Indice (100 = première valeur) »)
        # keeps the series' own name, « CTR (%) » : 218 there is +118 %, not a 218 % rate.
        if (tr.get("type") != "pie" and _is_rate(tr) and tr["max"] > 100
                and not str(tr.get("unit", "")).lower().startswith("indice")):
            return "ecart", f"« {tr['name'] or tr['unit']} » atteint {tr['max']:,.0f} — un taux ne dépasse pas 100 %"
        if tr.get("type") == "scatter" and _is_cumul(tr) and tr.get("max_drop", 0) > MAX_CUMUL_DROP:
            return "ecart", (f"« {tr['name'] or tr['unit']} » perd {tr['max_drop']:.0%} de son "
                             "pic — un cumul qui retombe vers zéro est une absence écrite comme 0")
    if layer != "or":
        raw = [s for s in sources if not s.startswith(("v_", "gold_"))]
        return "non-garanti", ("lit hors de la couche or : " + ", ".join(raw[:4])
                               if raw else f"couche « {layer} »")
    return "verifie", "lu en couche or, contrôles du soir verts sur l'instantané, forme cohérente"


def run_checks(out: Path) -> dict:
    """Run the nightly equalities and bounds on the SNAPSHOT; write <out>/checks.json."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(HERE))
    import capture
    capture.point_at_snapshot()
    from src.database.postgres_handler import PostgresHandler
    from src.utils import gold_invariants, metric_bounds
    db = PostgresHandler.from_env_or_config()
    try:
        assert db.fetch_query("SELECT current_database()")[0][0] == capture.REVIEW_DB
        inv, inv_n = gold_invariants.run(db)
        bnd, bnd_n = metric_bounds.run(db)
    finally:
        db.close()
    res = {"findings": [*inv, *bnd], "pairs": inv_n, "bounds": bnd_n}
    (out / "checks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    return res


if __name__ == "__main__":
    r = run_checks(Path(sys.argv[1]).resolve())
    print(f"✅ {len(r['findings'])} écart(s) sur {r['pairs']} couples et {r['bounds']} bornes")
