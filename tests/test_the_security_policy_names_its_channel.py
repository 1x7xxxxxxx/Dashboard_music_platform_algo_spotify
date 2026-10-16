"""The public repo tells a researcher where to report, privately (R608).

Type: Hook
Uses: SECURITY.md
Persists in: nothing

Measured 2026-10-15: a PUBLIC repo with no reporting channel — a researcher had only the
public issue tracker. Private vulnerability reporting was enabled on 2026-10-16
(`{"enabled":true}`); the file went in only after that, as code-critic required: a policy
pointing at a missing button sends the reader to a public issue.

guard_scope: the file's presence, its pointer to GitHub's private report, its ban on a
public issue, and the absence of any e-mail address (one inbox, personal). NOT covered:
the GitHub setting itself — the CI `GITHUB_TOKEN` cannot read it; check by hand with
`gh api repos/<owner>/<repo>/private-vulnerability-reporting`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _policy() -> str:
    return (ROOT / "SECURITY.md").read_text(encoding="utf-8")


def test_policy_points_to_the_private_report() -> None:
    text = _policy()
    assert "Report a vulnerability" in text
    assert re.search(r"do \*\*not\*\*:\s*\n\s*\n?- open a public issue", text)


def test_policy_carries_no_email_address() -> None:
    assert not _EMAIL.search(_policy()), "the channel is GitHub's private report, not an inbox"
