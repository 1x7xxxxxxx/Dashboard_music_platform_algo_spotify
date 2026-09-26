"""The figures of the artist career PDF, rendered on the snapshot — for the charts dossier.

Type: Utility
Uses: src/dashboard/utils/pdf_exporter/_report.py (collect_report_data → 'charts' data URIs)
Triggers: tools/dev/charts_dossier/main.py
Persists in: <out>/pdf/*.png and <out>/pdf_figures.json — outside the repository

R203 (2026-09-26). These are matplotlib re-drawings, not the on-screen Plotly figures, so they
are reviewed as their own surface. A chart key whose builder returns None (no data for the
period, or a section absent for this tenant) is listed as not rendered, with that reason.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def render(out: Path, artist_id: int = 1, since: dt.date = dt.date(2024, 1, 1)) -> dict:
    from src.dashboard.utils.pdf_exporter._report import collect_report_data
    from src.database.postgres_handler import PostgresHandler
    pdir = out / "pdf"
    pdir.mkdir(parents=True, exist_ok=True)
    db = PostgresHandler.from_env_or_config()
    try:
        data = collect_report_data(db, artist_id, since, dt.date.today())
    finally:
        db.close()
    rendered, missing = [], []
    for key, uri in (data.get("charts") or {}).items():
        if not uri or not str(uri).startswith("data:image/png;base64,"):
            missing.append({"key": key, "reason": "pas de données pour cette période ou ce locataire"})
            continue
        name = f"pdf_{key}.png"
        (pdir / name).write_bytes(base64.b64decode(str(uri).split(",", 1)[1]))
        rendered.append({"key": key, "png": f"pdf/{name}"})
    result = {"since": since.isoformat(), "figures": rendered, "not_rendered": missing}
    (out / "pdf_figures.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    return result
