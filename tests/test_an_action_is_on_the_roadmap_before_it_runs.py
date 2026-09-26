"""No product code is edited or committed before its action is an OPEN roadmap row (R196).

Type: Sub
Uses: tools/dev/require_roadmap_id.py, .claude/hooks/require_roadmap_entry.py
Depends on: git (a throw-away repository in tmp_path)
Persists in: nothing

Owner, 2026-09-26: « comment peut-on se garantir d'inscrire une action en roadmap avant de
l'exécuter ? ». 41 of the 118 product-code commits since 2026-09-12 cited no roadmap id, 15
wrote it in the same commit as the code. code-critic, same day, before any line: only an
OPEN row counts (an archived id would launder anything), the hook reads the edited file's
own repository, merges and reverts are exempt.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load("require_roadmap_id", _ROOT / "tools" / "dev" / "require_roadmap_id.py")
hook = _load("require_roadmap_entry", _ROOT / ".claude" / "hooks" / "require_roadmap_entry.py")

_INDEX = """# Roadmap

## 📋 Tâches ouvertes (index)

| id | Tâche | P | Mesuré par |
|---|---|---|---|
{rows}
Prose citing R900 is not a row.

## Détail
| R901 | a row of ANOTHER table |
"""


def _checklist(*ids: str, decision: str = "<!-- critic: non — texte seul -->") -> str:
    return _INDEX.format(rows="".join(f"| {i} | action {decision} | P3 | test |\n" for i in ids))


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Each refusal on its exact defect, each pass on its correct form."""
    empty, open_ = _checklist(), _checklist("R196")
    assert gate.open_ids(empty) == set(), "prose or another table read as an open row"
    assert gate.open_ids(open_) == {"R196"}
    no_table = "## 📋 Tâches ouvertes\n\nAucune.\n\n## Détail\n| R901 | another section |\n"
    assert gate.open_ids(no_table) == set(), "the NEXT section's table was read as the index"
    code = ["src/dashboard/views/x.py"]

    assert gate.verdict(code, "Tweak the button", open_), "a commit citing no id passed"
    assert gate.verdict(code, "R150 : tweak", open_), "an id that is not OPEN passed (laundering)"
    assert gate.verdict(code, "R196 : tweak", empty), "an id added in the same commit passed"
    assert gate.verdict(code, "R196 : tweak", open_) is None
    assert gate.verdict(["tests/test_x.py", CHK], "no id", empty) is None, "non-product blocked"
    assert gate.verdict(["migrations/140_x.sql"], "no id", open_), "a migration is product code"
    assert gate.verdict(code, 'Revert "R1 : x"', empty) is None, "a revert was refused"
    assert gate.verdict(code, "Merge branch 'x'", empty, parents=2) is None, "a merge refused"
    assert gate.next_id(_checklist("R196"), "R12 archived") == "R902"  # 901 is in the fixture


def test_a_row_that_does_not_decide_the_critic_is_refused() -> None:
    """R198: the cited open row must decide `critic: requis` or `critic: non — …`; a
    decision written on ANOTHER row is never borrowed."""
    code = ["src/x.py"]
    undecided = _checklist("R196", decision="")
    assert gate.verdict(code, "R196 : tweak", undecided), "an undecided row passed"
    two = _INDEX.format(rows="| R196 | action | P3 | t |\n| R197 | x <!-- critic: requis --> | P3 | t |\n")
    assert gate.verdict(code, "R196 : tweak", two), "R197's decision was borrowed by R196"
    assert gate.verdict(code, "R197 : tweak", two) is None
    assert gate.critic_decision("| R1 | a <!-- critic: requis --> |") == "requis"
    assert gate.critic_decision("| R1 | a <!-- critic: non — texte --> |") == "non"
    assert gate.critic_decision("| R1 | a critic: requis in prose |") is None
    assert gate.requis_ids("R197 : x", two) == ["R197"]


CHK = ".claude/dev-docs/roadmap/checklist.md"


def _repo(tmp: Path, *ids: str) -> Path:
    (tmp / ".claude/dev-docs/roadmap").mkdir(parents=True)
    (tmp / CHK).write_text(_checklist(*ids), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    return tmp


def test_the_edit_hook_reads_the_edited_files_own_repository(tmp_path: Path) -> None:
    """Empty index ⇒ product edit refused with the next id; open row ⇒ allowed; the
    checklist read is the TARGET's repository, not the current directory's."""
    empty = _repo(tmp_path / "a")
    msg = hook.refusal(str(empty / "src/x.py"), cwd=str(_ROOT))
    assert msg and "R902" in msg, msg
    assert hook.refusal(str(empty / "tests/test_x.py"), cwd=str(_ROOT)) is None
    full = _repo(tmp_path / "b", "R196")
    assert hook.refusal(str(full / "src/x.py"), cwd=str(empty)) is None, (
        "the hook judged the file by the checklist of the CURRENT directory")


def test_the_edit_hook_blocks_through_its_real_entry_point(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "c")
    event = {"tool_input": {"file_path": str(repo / "airflow/dags/x.py")}, "cwd": str(repo)}
    run = subprocess.run([sys.executable, str(_ROOT / ".claude/hooks/require_roadmap_entry.py")],
                         input=json.dumps(event), capture_output=True, text=True)
    assert run.returncode == 2 and "R196" in run.stderr, (run.returncode, run.stderr)


def test_the_gates_are_wired() -> None:
    """A gate nothing calls is a note. The hook, the commit-msg stage and the CI step."""
    settings = json.loads((_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    pre = [h["command"] for m in settings["hooks"]["PreToolUse"]
           if "Edit" in (m.get("matcher") or "") for h in m["hooks"]]
    assert any("require_roadmap_entry.py" in c for c in pre), "PreToolUse Edit hook not wired"
    cfg = yaml.safe_load((_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert "commit-msg" in cfg.get("default_install_hook_types", []), (
        "`pre-commit install` would not install the commit-msg hook")
    hooks = [h for r in cfg["repos"] for h in r["hooks"]]
    ours = [h for h in hooks if "require_roadmap_id.py" in h.get("entry", "")]
    assert ours and ours[0].get("stages") == ["commit-msg"], ours
    ci = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "require_roadmap_id.py --range" in ci, "no CI step: --no-verify would pass"
