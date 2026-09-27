"""The error-class health document dates itself by its SOURCE, not by HEAD.

Type: Test
Uses: tools/dev/error_class_health.py, .claude/dev-docs/error-class-health.json

2026-09-28 : CI red on bc971878 — a routing change — because `head_date` read HEAD's
commit date, and that commit was made after midnight. The catalogue had not moved; the
gate said the document « no longer describes the catalogue ». Any generated field must
depend only on what the document describes.

Mutation record (2026-09-28) : the `-- CAT_REL` path filter removed → red on the first
commit of a new day that does not touch the catalogue (here: the working tree's HEAD).
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ".claude/dev-docs/error-classes.md"


def test_head_date_is_the_last_catalogue_commit_date():
    doc = json.loads((ROOT / ".claude/dev-docs/error-class-health.json").read_text(encoding="utf-8"))
    got = doc["aggregate"]["generated_from"]["head_date"]
    want = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cI", "--", CAT],
                          capture_output=True, text=True).stdout.strip()[:10]
    assert got == want, f"head_date {got} ≠ date du dernier commit du catalogue {want}"


def test_the_generator_filters_its_date_by_the_catalogue():
    src = (ROOT / "tools/dev/error_class_health.py").read_text(encoding="utf-8")
    import ast
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "_git"
             and any(isinstance(a, ast.Constant) and a.value == "--format=%cI" for a in n.args)]
    assert calls and all(any(getattr(a, "id", "") == "CAT_REL" for a in c.args) for c in calls)
