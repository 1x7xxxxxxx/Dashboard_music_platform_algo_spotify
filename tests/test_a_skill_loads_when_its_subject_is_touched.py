"""R360 / REQ-HARN-12 — a skill or a rule loads when its subject is touched, not always.

Type: Test
Uses: .claude/hooks/inject_context.py (detect_domains, in-process), .claude/rules/*.md
Depends on: nothing live
Persists in: nothing

Measured on 2026-10-04 (usage_report, 30 days): dashboard-view, airflow-dag, db-schema and
audit-collectors had 0 loads while 21 views and 57 migrations were added — they carried no
`keywords:`, and `inject_context.py` is the only injector. The three rules were loaded in
40 sessions out of 40: their frontmatter said `globs:`, which Claude Code ignores (its key
is `paths:`), so they loaded unconditionally.

Mutation record (2026-10-04): seen red with the `keywords:` line removed from
dashboard-view (test 1), and with `paths:` renamed back to `globs:` in python.md (test 2).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("inject_context",
                                               ROOT / ".claude/hooks/inject_context.py")
ic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ic)

PROMPTS = {
    "dashboard-view": "ajoute une tuile kpi sur la page streamlit avec un filtre",
    "airflow-dag": "le dag airflow a un catchup et un schedule faux",
    "db-schema": "écris une migration qui ajoute une colonne et une contrainte",
    "audit-collectors": "le collecteur youtube rend des données périmées sans lever",
}


@pytest.mark.parametrize("skill", sorted(PROMPTS))
def test_a_prompt_on_its_subject_loads_the_skill(skill: str) -> None:
    folders = {ic.DOMAINS[d][1] + "/" + ic.DOMAINS[d][2] for d in ic.detect_domains(PROMPTS[skill])}
    assert any(skill in f for f in folders), (skill, folders)


@pytest.mark.parametrize("rule", sorted((ROOT / ".claude/rules").glob("*.md")),
                         ids=lambda p: p.name)
def test_a_rule_is_scoped_with_the_key_claude_code_reads(rule: Path) -> None:
    front = yaml.safe_load(rule.read_text(encoding="utf-8").split("---", 2)[1]) or {}
    assert "globs" not in front, f"{rule.name}: `globs:` is ignored — the key is `paths:`"
    assert front.get("paths"), f"{rule.name} loads in every session: give it `paths:`"
