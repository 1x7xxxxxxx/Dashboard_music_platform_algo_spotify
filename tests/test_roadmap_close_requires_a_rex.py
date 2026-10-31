"""R676 (REQ-PARC-159, master T552) — a `<!-- défaut -->` row closes only on its REX.

Type: Test
Uses: tools/dev/roadmap.py (cmd_close, require_rex, rex_missing)
Depends on: git — a scratch repository per case
Persists in: nothing

The master refuses to close a defect row without its REX since T552; this repo has its own
close, so it did not receive the guard. Three ways out, each proven here end to end through
`cmd_close`: (1) an entry of error-classes.md citing the id, committed by the delivery;
(2) `rex: <existing class>` in the note (a recurrence); (3) `rex: aucun — <reason ≥ 10>`.

Mutation record (2026-10-31): the gate bypassed in cmd_close → 4 red; the « delivered by the
row's commits » condition dropped → red; the 10-character reason relaxed to 1 → red; an
unknown class accepted as a recurrence → 2 red.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAT = ".claude/dev-docs/error-classes.md"


def _load():
    spec = importlib.util.spec_from_file_location("roadmap_rex", ROOT / "tools/dev/roadmap.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, msg: str, files: dict[str, str]) -> None:
    for rel, body in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    rm = _load()
    _git(tmp_path, "init", "-q")
    road = tmp_path / ".claude/dev-docs/roadmap"
    _commit(tmp_path, "init", {
        ".claude/dev-docs/roadmap/checklist.md":
            "# C\n\n| id | Tâche | P | Mesuré par |\n|---|---|---|---|\n"
            "| R900 | corriger x <!-- défaut --> | P2 | t |\n"
            "| R901 | ajouter y | P3 | t |\n\n<!-- reprise: open=R900, R901 -->\n",
        ".claude/dev-docs/roadmap/archive.md": "# A\n\n---\n",
        CAT: "# Catalogue\n\n## known-class\n\n- root_cause: x\n",
    })
    monkeypatch.setenv("ROADMAP_SKIP_CI", "1")
    monkeypatch.setattr(rm, "ROOT", tmp_path)
    monkeypatch.setattr(rm, "CHECKLIST", road / "checklist.md")
    monkeypatch.setattr(rm, "ARCHIVE", road / "archive.md")
    monkeypatch.setattr(rm, "write_health", lambda: False)
    monkeypatch.setattr(rm, "close_night_unit", lambda *a, **k: False)
    return rm, tmp_path


def _close(rm, tid: str, note: str = "") -> int:
    return rm.cmd_close(argparse.Namespace(id=tid, note=note, force_ci=False))


def _is_open(path: Path, tid: str) -> bool:
    return f"| {tid} |" in (path / ".claude/dev-docs/roadmap/checklist.md").read_text("utf-8")


def test_a_defect_row_without_rex_is_refused(repo, capsys):
    rm, path = repo
    _commit(path, "R900 : fix", {"src.py": "x = 1\n"})
    assert _close(rm, "R900", "livré") == 1
    assert "sans REX" in capsys.readouterr().err
    assert _is_open(path, "R900")


def test_an_entry_citing_the_id_committed_by_the_delivery_closes(repo):
    rm, path = repo
    _commit(path, "R900 : fix + classe", {
        "src.py": "x = 1\n",
        CAT: "# Catalogue\n\n## known-class\n\n- root_cause: x\n\n## new-class\n\n- seen: R900\n"})
    assert _close(rm, "R900", "livré") == 0
    assert not _is_open(path, "R900")


def test_an_entry_citing_the_id_but_not_delivered_is_refused(repo):
    rm, path = repo
    _commit(path, "catalogue seul", {CAT: "# Catalogue\n\n## new-class\n\n- seen: R900\n"})
    _commit(path, "R900 : fix", {"src.py": "x = 1\n"})
    assert _close(rm, "R900", "livré") == 1


def test_a_recurrence_of_an_existing_class_closes_an_unknown_one_does_not(repo, capsys):
    rm, path = repo
    _commit(path, "R900 : fix", {"src.py": "x = 1\n"})
    assert _close(rm, "R900", "livré — rex: no-such-class") == 1
    assert "no-such-class" in capsys.readouterr().err
    assert _close(rm, "R900", "livré — rex: known-class") == 0
    assert not _is_open(path, "R900")


def test_rex_none_needs_a_reason_of_ten_characters(repo):
    rm, path = repo
    _commit(path, "R900 : fix", {"src.py": "x = 1\n"})
    assert _close(rm, "R900", "rex: aucun — court") == 1
    assert _close(rm, "R900", "rex: aucun — faute de frappe isolée, sans motif") == 0
    assert not _is_open(path, "R900")


def test_a_row_not_marked_defect_needs_no_rex(repo):
    rm, path = repo
    _commit(path, "R901 : y", {"y.py": "y = 1\n"})
    assert _close(rm, "R901", "livré") == 0


def test_the_probe_finds_rex_missing_defined_and_require_rex_called_by_close():
    """`~/.fleet-master/tools/hud/rex.py --check` looks for these two names in this file:
    `rex_missing` must be a real definition and `require_rex` a real call inside cmd_close."""
    tree = ast.parse((ROOT / "tools/dev/roadmap.py").read_text(encoding="utf-8"))
    defs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "rex_missing" in defs and "require_rex" in defs
    called = {n.func.id for n in ast.walk(defs["cmd_close"])
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "require_rex" in called
