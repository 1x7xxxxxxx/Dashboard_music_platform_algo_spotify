"""R268 — a roadmap row closes on a GREEN CI of its delivering commit, and CLAUDE.md does not
grow without limit.

Type: Test
Uses: tools/dev/roadmap.py (ci_verdict, _close_notes), CLAUDE.md (size)

Measured 2026-09-27 : R254 was closed on a commit whose CI then went red, and « CI de main
verte » was announced to the owner without being read — main stayed red for two commits.
`make roadmap-close` now reads the delivering commit's CI and refuses red, running or
unpushed. And CLAUDE.md, read at every session, weighed 52 935 bytes.

Mutation record (2026-09-27) : `ci_verdict` answering « ok » on a failure → red ; the
running case dropped → red ; the budget set below the file's size → the budget test
went red ; the gh query given the short sha again → red ; the ancestor check of the
replacing run bypassed → red (2026-09-27).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("roadmap_tool", ROOT / "tools/dev/roadmap.py")
roadmap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(roadmap)
_st = importlib.util.spec_from_file_location("suite_timing", ROOT / "tools/dev/suite_timing.py")
suite_timing = importlib.util.module_from_spec(_st)
_st.loader.exec_module(suite_timing)

# 52 926 bytes on 2026-09-27 (52 935 before R268 shortened its own line, 52 933 before R261 rewrote « Adding a New View » step 3). It may only go down — or be raised in the same commit, with
# the reason written here.
CLAUDE_MD_BUDGET = 52_926


def test_a_red_or_running_ci_refuses_the_closure():
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "success"}]) == "ok"
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "failure"}]) == "rouge"
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "failure"},
                               {"status": "completed", "conclusion": "cancelled"}]) == "rouge"
    # cancelled = superseded by a later push: it proves nothing, a descendant run judges
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "cancelled"}]) == "remplacée"
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "success"},
                               {"status": "completed", "conclusion": "cancelled"}]) == "ok"
    assert roadmap.ci_verdict([{"status": "in_progress", "conclusion": ""}]) == "en cours"
    assert roadmap.ci_verdict([]) == "inconnu"


def test_closing_a_row_delivers_its_notes(tmp_path, monkeypatch):
    arch = tmp_path / ".claude" / "dev-docs" / "architecture"
    arch.mkdir(parents=True)
    (arch / "notes-triage.yaml").write_text(
        "# tête\n- ligne: 1\n  statut: ouvert\n  roadmap: R9\n"
        "- ligne: 2\n  statut: ouvert\n  roadmap: R8\n", encoding="utf-8")
    monkeypatch.setattr(roadmap, "ROOT", tmp_path)
    assert roadmap._close_notes("R9", "abc1234") == 1
    text = (arch / "notes-triage.yaml").read_text(encoding="utf-8")
    assert text.startswith("# tête") and "R9 (archivée) — abc1234" in text and "roadmap: R8" in text


def test_claude_md_stays_under_its_budget_not_vacuous():
    size = (ROOT / "CLAUDE.md").stat().st_size
    assert size > 1000, "CLAUDE.md is not read — the budget would hold on nothing"
    assert size <= CLAUDE_MD_BUDGET, (
        f"CLAUDE.md fait {size} octets pour un budget de {CLAUDE_MD_BUDGET} : il est lu à "
        "CHAQUE séance — retirer une règle morte ou déplacer le détail vers dev-docs.")


def test_the_suite_time_is_read_from_the_run_not_written_by_hand():
    log = "noise\n12 passed in 3.2s\n...\n10931 passed, 2 failed, 89 skipped in 372.40s (0:06:12)\n"
    assert suite_timing.parse(log) == {"passed": 10931, "failed": 2, "seconds": 372}
    assert suite_timing.parse("no summary") is None
    with open(ROOT / "Makefile", encoding="utf-8") as fh:
        help_line = next(ln for ln in fh if ln.startswith("test:"))
    assert "test-suite-timing.json" in help_line, "make test's help states a figure by hand again"


def test_the_ci_is_asked_with_the_full_sha(monkeypatch):
    """`gh run list --commit <short>` answers [] — the gate read « inconnu » on every closure."""
    import subprocess
    real, asked = subprocess.run, []

    def fake(cmd, *a, **kw):
        if cmd[0] == "gh":
            asked.append(cmd[cmd.index("--commit") + 1])
            return subprocess.CompletedProcess(cmd, 0, '[{"status":"completed","conclusion":"success"}]', "")
        return real(cmd, *a, **kw)
    monkeypatch.delenv("ROADMAP_SKIP_CI", raising=False)
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(roadmap.shutil if hasattr(roadmap, "shutil") else __import__("shutil"),
                        "which", lambda _: "/usr/bin/gh")
    head = real(["git", "-C", str(ROOT), "rev-parse", "origin/main"], capture_output=True,
                text=True).stdout.strip()
    if not head:
        import pytest
        pytest.skip("no origin/main in this checkout")
    verdict, _ = roadmap._delivery_ci([f"{head[:8]} x"])
    assert asked == [head] and verdict == "ok"


def test_a_superseded_run_is_judged_on_the_run_that_replaced_it(monkeypatch):
    """CI concurrency cancels a commit's run when the next push lands: the delivery is then
    judged on the most recent main run that CONTAINS it, never read as red nor as green."""
    import json
    import subprocess
    real = subprocess.run
    head = real(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                text=True).stdout.strip()
    parent = real(["git", "-C", str(ROOT), "rev-parse", "HEAD~1"], capture_output=True,
                  text=True).stdout.strip()

    def gh(runs):
        def fake(cmd, *a, **kw):
            if cmd[0] == "gh":
                return subprocess.CompletedProcess(cmd, 0, json.dumps(runs), "")
            return real(cmd, *a, **kw)
        return fake
    monkeypatch.setattr(subprocess, "run", gh([
        {"headSha": "0" * 40, "status": "completed", "conclusion": "success"},  # unrelated
        {"headSha": head, "status": "completed", "conclusion": "failure"}]))
    assert roadmap._descendant_ci(parent) == "rouge"
    monkeypatch.setattr(subprocess, "run", gh([
        {"headSha": head, "status": "completed", "conclusion": "cancelled"},
        {"headSha": parent, "status": "completed", "conclusion": "success"}]))
    assert roadmap._descendant_ci(parent) == "ok"
