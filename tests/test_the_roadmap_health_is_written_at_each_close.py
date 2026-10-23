"""docs/ROADMAP-HEALTH.md: one state per open row, the actual of each closure, rewritten by close (R644).

Type: Guard
Uses: tools/dev/roadmap_health.py, tools/dev/roadmap.py (write_health)
Depends on: git (citing commits) — read on a throwaway repo here

Baseline REQ-PARC-138 (owner's review « Master puis parc », 2026-10-22): the roadmap's health,
regenerated at each close. Adapted to this repo: no proof ledger, no `est:` — a row is `échec`
when its « Mesuré par » names nothing executable, `avertissement` when it is old.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

CHECKLIST = """# x

## 📋 Tâches ouvertes (index)

| id | Tâche | P | Mesuré par |
|---|---|---|---|
| R901 | une tâche mesurée <!-- critic: non --> | P2 | `make test` |
| R902 | une tâche sans mesure | P3 | le propriétaire regardera |

## 🔖 REPRISE

<!-- reprise: open=R901, R902 -->
"""
ARCHIVE = """# a

---

- [x] **R900 — livrée** (P3) ✅ (2026-10-01, abc)
- [x] **R899 — plus ancienne** (P3) ✅ (2026-09-01, def)
- [x] **R900 — citée deux fois** (P3)
"""


def _repo(tmp_path: Path, monkeypatch):
    d = tmp_path / ".claude" / "dev-docs" / "roadmap"
    d.mkdir(parents=True)
    (d / "checklist.md").write_text(CHECKLIST, encoding="utf-8")
    (d / "archive.md").write_text(ARCHIVE, encoding="utf-8")
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    for msg in ("R900 : début", "R900 : fin", "R901 : ouverte"):
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", msg], check=True)
    monkeypatch.setenv("ROADMAP_ROOT", str(tmp_path))
    import roadmap_health
    return importlib.reload(roadmap_health)


def test_each_open_row_gets_one_state_and_a_closure_its_actual(tmp_path, monkeypatch):
    rh = _repo(tmp_path, monkeypatch)
    h = rh.collect()
    states = {r["id"]: r["state"] for r in h["open"]}
    assert states == {"R901": "ok", "R902": "échec"}
    assert [c["id"] for c in h["closed"]] == ["R900", "R899"]      # newest first, each once
    assert h["closed"][0]["commits"] == 2 and h["closed"][1]["commits"] == 0
    assert rh.main(["--check"]) == 1                                  # R902 has no measure


def test_an_old_row_is_a_warning_not_ok():
    import roadmap_health as rh
    row = {"measured": "`make test`"}
    assert rh.row_state(row, rh.AGE_WARN + 1)[0] == "avertissement"
    assert rh.row_state(row, 1.0)[0] == "ok"
    assert rh.row_state({"measured": "à l'œil"}, 1.0)[0] == "échec"


def test_close_rewrites_the_report(tmp_path, monkeypatch):
    _repo(tmp_path, monkeypatch)
    (tmp_path / "f.txt").write_text("x")
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git + ["add", "f.txt"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "R901 : livrée"], check=True)
    monkeypatch.setenv("ROADMAP_SKIP_CI", "1")
    import argparse

    import roadmap
    roadmap = importlib.reload(roadmap)
    assert roadmap.cmd_close(argparse.Namespace(id="R901", note="", force_ci=False)) == 0
    md = (tmp_path / "docs" / "ROADMAP-HEALTH.md").read_text(encoding="utf-8")
    assert "| R902 | P3 |" in md and "échec" in md
    assert "| R901 |" in md.split("dernières clôtures")[1]     # the closure it just wrote
