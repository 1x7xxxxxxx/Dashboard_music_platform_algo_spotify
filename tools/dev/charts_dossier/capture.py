"""Render every dashboard view and keep each figure it draws, with the code site that drew it.

Type: Utility
Uses: tests/render_harness.py (VIEWS, SCRIPT), streamlit AppTest, plotly + kaleido (dev extra)
Triggers: tools/dev/charts_dossier/main.py (`make charts-dossier`)
Persists in: <out>/figures/*.png and <out>/capture.json — OUTSIDE the repository (artist data)

R203 (2026-09-26). The owner wants every chart the app can draw, on real data, in one PDF to
review before deploying. The views are rendered with `AppTest` (the R189 harness script, admin
session, artist_id=1) against a LOCAL database restored from a production `pg_dump`:

  ⚠️ never against production itself (code-critic, same day). `PGOPTIONS` read-only would not
  hold — every connection passes its own `options=` (which REPLACES the env), in autocommit —
  and each render inserts a `usage_events` row. The snapshot takes those writes instead.

`st.plotly_chart` / `st.pyplot` are wrapped for the duration: each call records the figure and
TWO sites — the helper that called Streamlit (`src/dashboard/utils/platform_chart.py:…`) and
the VIEW that called the helper — because one helper line draws charts for many views
(code-critic). Only the DEFAULT choice of each selector is rendered; said in the dossier.
"""
from __future__ import annotations

import inspect
import io
import json
import os
import socket
import smtplib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REVIEW_DB = "spotify_etl_review"
_LOCAL = {"127.0.0.1", "localhost", "::1"}


def point_at_snapshot() -> None:
    """DATABASE_URL on the local snapshot, built from the local config — never printed."""
    sys.path.insert(0, str(ROOT))
    from src.utils.pg_connect import resolve_kwargs
    kw = resolve_kwargs()
    host = str(kw.get("host", ""))
    if host not in _LOCAL:
        raise SystemExit(f"❌ refus : la base configurée n'est pas locale ({host!r})")
    from urllib.parse import quote
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(str(kw['user']))}:{quote(str(kw['password']))}"
        f"@{host}:{kw['port']}/{REVIEW_DB}")


def cut_egress() -> None:
    """No mail, no third-party call: only loopback sockets may open during the render."""
    real_connect = socket.socket.connect

    def local_only(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in _LOCAL and not host.startswith("127."):
            raise ConnectionRefusedError(f"R203 : sortie réseau coupée pendant le rendu ({host})")
        return real_connect(self, address)

    socket.socket.connect = local_only

    class _NoMail:
        def __init__(self, *a, **k):
            raise ConnectionRefusedError("R203 : SMTP coupé pendant le rendu")
    smtplib.SMTP = smtplib.SMTP_SSL = _NoMail


def _sites() -> tuple[str, str]:
    """(helper site, view site): the first frames under src/dashboard, and under views/."""
    helper = view = ""
    for fr in inspect.stack()[2:]:
        p = fr.filename.replace("\\", "/")
        if "/src/dashboard/" not in p or "/charts_dossier/" in p:
            continue
        rel = p[p.index("src/dashboard/"):] + f":{fr.lineno}"
        helper = helper or rel
        if "/views/" in p:
            view = rel
            break
    return helper, view or helper


def capture(views: list[str], out: Path, script: str) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator
    from streamlit.testing.v1 import AppTest

    figs_dir = out / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    current = {"view": ""}
    orig_plotly, orig_pyplot = DeltaGenerator.plotly_chart, DeltaGenerator.pyplot

    def rec_plotly(self, figure_or_data=None, *a, **k):
        helper, view_site = _sites()
        try:
            spec = figure_or_data.to_json() if hasattr(figure_or_data, "to_json") else None
        except Exception:  # noqa: BLE001 — an unserialisable figure is recorded as such
            spec = None
        records.append({"view": current["view"], "kind": "plotly", "site": helper,
                        "view_site": view_site, "spec": spec})
        return orig_plotly(self, figure_or_data, *a, **k)

    def rec_pyplot(self, fig=None, *a, **k):
        import matplotlib.pyplot as plt
        helper, view_site = _sites()
        buf = io.BytesIO()
        (fig or plt.gcf()).savefig(buf, format="png", dpi=110, bbox_inches="tight")
        records.append({"view": current["view"], "kind": "pyplot", "site": helper,
                        "view_site": view_site, "png": buf.getvalue()})
        return orig_pyplot(self, fig, *a, **k)

    DeltaGenerator.plotly_chart, DeltaGenerator.pyplot = rec_plotly, rec_pyplot
    st.plotly_chart = lambda *a, **k: rec_plotly(st._main, *a, **k)
    st.pyplot = lambda *a, **k: rec_pyplot(st._main, *a, **k)
    errors = {}
    try:
        for v in views:
            current["view"] = v
            at = AppTest.from_string(script.format(root=str(ROOT), view=v))
            at.run(timeout=240)
            if at.exception:
                ex = at.exception[0]
                errors[v] = str(getattr(ex, "value", ex))[:300]
            print(f"  {v}: {sum(r['view'] == v for r in records)} figure(s)"
                  + (f" — ERREUR {errors[v][:80]}" if v in errors else ""), flush=True)
    finally:
        DeltaGenerator.plotly_chart, DeltaGenerator.pyplot = orig_plotly, orig_pyplot
    return _write(records, errors, figs_dir, out)


def _write(records: list[dict], errors: dict, figs_dir: Path, out: Path) -> dict:
    import plotly.io as pio
    manifest, failed = [], []
    for i, r in enumerate(records):
        name = f"{i:03d}_{r['view']}.png"
        try:
            if r["kind"] == "plotly":
                if r["spec"] is None:
                    raise ValueError("figure non sérialisable")
                fig = pio.from_json(r["spec"])
                h = fig.layout.height or 450
                fig.write_image(figs_dir / name, width=1000, height=int(h), scale=1)
                title = fig.layout.title.text if fig.layout.title else ""
            else:
                (figs_dir / name).write_bytes(r["png"])
                title = ""
            manifest.append({"id": i, "view": r["view"], "kind": r["kind"], "site": r["site"],
                             "view_site": r["view_site"], "title": title or "", "png": name})
        except Exception as exc:  # noqa: BLE001 — listed as not rendered, never dropped
            failed.append({"view": r["view"], "site": r["site"], "reason": str(exc)[:200]})
    result = {"figures": manifest, "not_rendered": failed, "view_errors": errors}
    (out / "capture.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    return result


def main(argv: list[str]) -> int:
    out = Path(argv[1]).resolve() if len(argv) > 1 else None
    if out is None or not _outside_git(out):
        print("❌ donner un dossier de sortie HORS du dépôt (le dossier contient des données "
              "d'artiste)", file=sys.stderr)
        return 2
    point_at_snapshot()
    cut_egress()
    from src.database.postgres_handler import PostgresHandler
    db = PostgresHandler.from_env_or_config()
    try:
        name = db.fetch_query("SELECT current_database()")[0][0]
    finally:
        db.close()
    if name != REVIEW_DB:
        print(f"❌ le rendu lirait {name!r}, pas l'instantané {REVIEW_DB!r}", file=sys.stderr)
        return 2
    print(f"base lue : {name} (instantané local de la prod)")
    sys.path.insert(0, str(ROOT))
    from tests.render_harness import SCRIPT, VIEWS
    views = argv[2].split(",") if len(argv) > 2 else VIEWS
    res = capture(views, out, SCRIPT)
    print(f"✅ {len(res['figures'])} figure(s) rendue(s), {len(res['not_rendered'])} non "
          f"rendue(s), {len(res['view_errors'])} vue(s) en erreur → {out}")
    return 0



def _outside_git(out: Path) -> bool:
    """Outside the repository, or inside a folder git IGNORES (`revue/`, .gitignore) — the
    dossier carries real artist data and the repository history is public."""
    import subprocess
    if ROOT not in out.parents and out != ROOT:
        return True
    probe = out / "dossier-graphiques.pdf"
    return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", str(probe)]).returncode == 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
