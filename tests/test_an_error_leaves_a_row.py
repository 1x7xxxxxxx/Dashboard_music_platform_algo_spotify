"""Guards: an application error becomes a countable, closable record — not an e-mail.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Asked on 2026-09-04: « un process automatisé qui intègre en roadmap ou dans un document
qu'on relie automatiquement pour chaque erreur ». What existed was `notify_app_error`:
a log line, a 200-character `usage_events` row, and an e-mail carrying the only copy of
the traceback. An inbox cannot be counted, cannot be closed, and cannot be linked to an
error class — the same defect arrived three times in two days looking like three.

The four things this pins, each of which was a real decision:

1. the row is written BEFORE the mail is attempted (an SMTP outage must not also lose
   the defect);
2. the fingerprint ignores the line number and the message, or a counter restarts at 1
   at every deploy and every occurrence becomes its own row;
3. a new occurrence REOPENS a resolved defect — coming back after being closed is the
   most useful thing the table can say;
4. the machine generates a DOCUMENT and touches the roadmap through one anchored line.
   It never writes a task: `checklist.md` is curated prose under invariants
   (`tests/test_roadmap_two_files.py`) that a machine cannot honour, and forty machine
   rows would bury the two real ones.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
ALERT = REPO / "src" / "dashboard" / "utils" / "error_alert.py"
FP = REPO / "src" / "utils" / "error_fingerprint.py"
REG = REPO / "src" / "utils" / "error_registry.py"
INBOX = REPO / "tools" / "error_inbox.py"
MONITOR = REPO / "airflow" / "dags" / "alert_monitor.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"{path.name} no longer defines {name}()"
    return fn


def _call_lines(fn: ast.AST, name: str) -> list[int]:
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == name) or \
               (isinstance(f, ast.Attribute) and f.attr == name):
                out.append(node.lineno)
    return out


def test_the_row_is_written_before_the_email_is_attempted():
    fn = _fn(ALERT, "notify_app_error")
    record = _call_lines(fn, "_record")
    email = _call_lines(fn, "_maybe_email")
    assert record and email, "notify_app_error no longer both records and mails"
    assert min(record) < min(email), (
        "the e-mail is attempted before the row is written: an SMTP outage would lose "
        "the defect entirely, which is the failure this registry exists to prevent."
    )


def test_the_fingerprint_ignores_the_line_number_and_the_message():
    """Two occurrences of one defect must fold into one row."""
    import sys
    sys.path.insert(0, str(REPO))
    from src.utils.error_fingerprint import fingerprint, origin_frame
    from src.utils import error_fingerprint as ef

    seen = []
    for payload in (None, 12345):          # two different messages, same defect
        try:
            ef._repo_relative(payload)
        except Exception as exc:           # noqa: BLE001 — that is the point
            seen.append((fingerprint(exc), origin_frame(exc)))
    assert len(seen) == 2
    assert seen[0][0] == seen[1][0], (
        f"two occurrences of the same defect got different fingerprints: {seen}. "
        "The message or the line number leaked into the hash."
    )
    assert seen[0][1] and seen[0][1].startswith("src/"), (
        f"the origin frame is not repo-relative: {seen[0][1]!r} — a container path and "
        "a dev-box path would then fingerprint as two different defects."
    )


def test_a_third_party_frame_never_becomes_the_origin():
    """The last frame is almost always a library's; the defect is the deepest OURS."""
    src = FP.read_text(encoding="utf-8")
    assert "site-packages" in src and "dist-packages" in src, (
        "the third-party filter is gone: the origin would become "
        "`streamlit/runtime/state/session_state.py`, which describes Streamlit's "
        "machinery and not our bug."
    )


def test_a_new_occurrence_reopens_a_resolved_defect():
    body = REG.read_text(encoding="utf-8")
    upsert = body[body.index("ON CONFLICT (fingerprint)"):]
    assert "resolved_at = NULL" in upsert.split("\"\"\"")[0], (
        "a new occurrence no longer reopens a closed defect — it would be counted in "
        "silence under an entry nobody reads any more."
    )


def test_closing_an_entry_requires_a_reason():
    src = INBOX.read_text(encoding="utf-8")
    assert "--note est obligatoire" in src, (
        "an entry can be closed with no reason: a closed entry without a reason is a "
        "lost entry, and the registry becomes a delete button."
    )


def test_the_machine_writes_a_document_and_only_ONE_anchored_roadmap_line():
    """It must never author a roadmap task."""
    body = INBOX.read_text(encoding="utf-8")
    assert "error-inbox: open=" in body, (
        "the roadmap pointer lost its anchor — the count in the prose could then "
        "disagree with the table and nothing would notice.")

    # What is WRITTEN, not what the function reads. The first version of this guard
    # asserted over the whole function body and fired on `marker = "## 🙋 En attente
    # de toi"` — a string used to FIND the insertion point. A predicate has to match
    # the question ("what does this emit?"), not a symptom of it.
    tree = ast.parse(body)
    template = next(
        (n.value.value for n in ast.walk(tree)
         if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
         and isinstance(n.value.value, str)
         and any(isinstance(t, ast.Name) and t.id == "_LINK_LINE" for t in n.targets)),
        None)
    assert template, "_LINK_LINE is gone — nothing describes what lands in the roadmap"
    for forbidden in ("- [ ]", "- [x]", "\n## ", "| R"):
        assert forbidden not in template, (
            f"the roadmap line template contains {forbidden!r}: the machine is "
            "authoring roadmap items, which breaks the two-file move invariant and "
            "buries the real tasks."
        )


def test_the_nightly_report_carries_the_open_defects():
    """A registry nobody is told about is a registry nobody reads."""
    body = MONITOR.read_text(encoding="utf-8")
    assert "check_app_errors" in body and "app_errors" in body, (
        "alert_monitor no longer reports open application defects.")
    assert "Erreurs applicatives non triées" in body, (
        "the finding is computed but never rendered into the consolidated mail — the "
        "exact shape of `detector-written-and-never-called`."
    )
    # AST, and the docstring excluded. The first version searched the source text and
    # fired on the docstring sentence that EXPLAINS why no traceback is carried — a
    # guard red on its own comment, for the fifth time in this repo.
    fn = _fn(MONITOR, "check_app_errors")
    stmts = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                            and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    mentions = [n.lineno for stmt in stmts for n in ast.walk(stmt)
                if (isinstance(n, ast.Constant) and n.value == "traceback")
                or (isinstance(n, ast.Name) and n.id == "traceback")
                or (isinstance(n, ast.Attribute) and n.attr == "traceback")]
    assert not mentions, (
        f"the nightly check reads the traceback (line(s) {mentions}): three of them in "
        "one mail and it stops being read, which is how a real finding nearly went "
        "unnoticed. The traceback belongs in `make error-inbox`."
    )
