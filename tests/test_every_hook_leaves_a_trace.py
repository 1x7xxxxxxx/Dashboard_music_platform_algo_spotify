"""Every registered hook leaves one trace line per run, so a SILENT hook is measured (R365).

Measured 2026-10-04: the harness report counted a hook only from the transcript
attachment Claude Code writes when the hook prints. Eight silent hooks read « never
fired » — `pre_compact.py` among them, the night it wrote its session file.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SETTINGS = REPO / ".claude" / "settings.json"
TRACE = REPO / ".claude" / "hooks" / "_hook_trace.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def registered_hooks(settings: dict) -> list[str]:
    """Every Python file a hook command runs, from settings.json — not a glob of a folder."""
    out = set()
    for matchers in settings.get("hooks", {}).values():
        for m in matchers:
            for h in m.get("hooks", []):
                found = re.findall(r"(\.claude/[\w/]+\.py)", h.get("command", ""))
                if found:
                    out.add(found[-1])
    return sorted(out)


def _is_path_setup(value: ast.expr) -> bool:
    """`sys.path.insert(...)` — the import plumbing of the trace block itself, cannot exit."""
    f = getattr(value, "func", None)
    return (isinstance(f, ast.Attribute) and f.attr in ("insert", "append")
            and isinstance(f.value, ast.Attribute) and f.value.attr == "path")


def trace_missing(source: str) -> str | None:
    """Why this hook source would run untraced, or None. Pure."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_exit"):
            return "os._exit skips atexit — the run would leave no line"
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "_trace"):
            return None
        if isinstance(node, (ast.If, ast.Raise, ast.While, ast.For, ast.With, ast.Try)) or (
                isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant)
                and not _is_path_setup(node.value)):
            return f"logic at line {node.lineno} runs before _trace(__file__)"
    return "no top-level _trace(__file__)"


def test_the_hook_list_comes_from_the_settings() -> None:
    hooks = registered_hooks(json.loads(SETTINGS.read_text(encoding="utf-8")))
    assert ".claude/hooks/pre_compact.py" in hooks
    assert ".claude/scripts/promote_rex.py" in hooks, "a hook outside .claude/hooks/ is a hook"


def test_every_registered_hook_traces_before_any_logic() -> None:
    hooks = registered_hooks(json.loads(SETTINGS.read_text(encoding="utf-8")))
    bad = {h: why for h in hooks
           if (why := trace_missing((REPO / h).read_text(encoding="utf-8")))}
    assert not bad, (
        "These hooks can run without leaving a line in hook-runs-*.jsonl, so the harness "
        f"report reads them as never fired: {bad}. Add the R365 block after the imports.")


def test_the_detector_sees_a_hook_without_its_trace() -> None:
    assert trace_missing("import sys\n\ndef main():\n    pass\n") == "no top-level _trace(__file__)"
    late = "import sys\nif True:\n    sys.exit(0)\n_trace(__file__)\n"
    assert "runs before" in trace_missing(late)
    assert "os._exit" in trace_missing("import os\n_trace(__file__)\nos._exit(0)\n")
    assert trace_missing("import sys\n_trace(__file__)\nif True:\n    pass\n") is None
    assert trace_missing("import sys\nsys.path.insert(0, 'x')\n_trace(__file__)\n") is None
    assert "runs before" in trace_missing("import sys\nmain()\n_trace(__file__)\n")


def test_a_hook_run_writes_one_line(tmp_path: Path) -> None:
    env = {**os.environ, "HOOK_TRACE_DIR": str(tmp_path)}
    env.pop("PYTEST_CURRENT_TEST", None)
    subprocess.run([sys.executable, str(REPO / ".claude/hooks/observe.py")], input="{}",
                   text=True, env=env, cwd=REPO, check=False, timeout=60)
    lines = [json.loads(x) for f in tmp_path.glob("hook-runs-*.jsonl")
             for x in f.read_text(encoding="utf-8").splitlines()]
    assert [x["hook"] for x in lines] == [".claude/hooks/observe.py"]
    usage = _load(REPO / ".claude/scripts/usage_report.py", "usage_report_r365")
    assert usage.hook_runs(tmp_path)[".claude/hooks/observe.py"]["n"] == 1


def test_a_test_never_writes_the_real_journal(monkeypatch) -> None:
    trace = _load(TRACE, "hook_trace_r365")
    monkeypatch.delenv("HOOK_TRACE_DIR", raising=False)
    assert trace.trace_dir() is None, "under pytest, only an explicit HOOK_TRACE_DIR is written"
    registered = []
    monkeypatch.setattr(trace.atexit, "register", lambda *a: registered.append(a))
    monkeypatch.setenv("HOOK_TRACE_DIR", "/nonexistent")
    trace.trace(str(REPO / ".claude/hooks/observe.py"))
    assert registered == [], "an IMPORTED hook (not __main__) must not trace"
