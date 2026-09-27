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
went red.
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

# 52 933 bytes on 2026-09-27 (52 935 before R268 shortened its own line). It may only go down — or be raised in the same commit, with
# the reason written here.
CLAUDE_MD_BUDGET = 52_933


def test_a_red_or_running_ci_refuses_the_closure():
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "success"}]) == "ok"
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "failure"}]) == "rouge"
    assert roadmap.ci_verdict([{"status": "completed", "conclusion": "success"},
                               {"status": "completed", "conclusion": "cancelled"}]) == "rouge"
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
