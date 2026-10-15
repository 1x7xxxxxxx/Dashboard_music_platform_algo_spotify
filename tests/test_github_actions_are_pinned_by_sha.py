"""Every third-party action is pinned by commit SHA, its version written beside it.

Type: Sub
Uses: .github/workflows/*.yml, .github/actions/*/action.yml (read line by line)
Depends on: nothing — no GitHub call

R607 (2026-10-15): `gitleaks/gitleaks-action@v2`, a third-party action on a movable tag,
received `GITHUB_TOKEN`. A tag can be moved by whoever controls the upstream repo; a SHA
cannot. The `# vX.Y.Z` comment is what lets Dependabot and `check_action_drift.py` read
the version — `yaml.safe_load` drops comments, so this guard reads raw lines.

Scope: `uses:` lines of workflows AND composite actions. Not covered: a `docker://` image
(none today) and a reusable workflow called by path (`./…`, local, has no upstream).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
VERSION = re.compile(r"^\s*#\s*v\d")


def uses_lines() -> list[tuple[str, str, str]]:
    files = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    files += sorted((ROOT / ".github" / "actions").glob("*/action.y*ml"))
    out = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = USES.match(line)
            if m and not m.group(1).startswith("./"):
                out.append((f"{f.relative_to(ROOT)}:{n}", m.group(1), m.group(2)))
    return out


def unpinned(lines: list[tuple[str, str, str]]) -> list[str]:
    return [f"{where} {ref}{rest}" for where, ref, rest in lines
            if not PINNED.match(ref) or not VERSION.match(rest)]


def test_the_guard_sees_the_shapes_it_must_refuse() -> None:
    sha = "a" * 40
    assert unpinned([("x:1", "actions/checkout@v6", "")])
    assert unpinned([("x:1", f"actions/checkout@{sha}", "")]), "a SHA without its version"
    assert unpinned([("x:1", f"actions/checkout@{sha[:7]}", "  # v6")]), "a short SHA"
    assert not unpinned([("x:1", f"actions/checkout@{sha}", "  # v6.1.0")])


def test_every_action_is_pinned_by_sha_with_its_version() -> None:
    lines = uses_lines()
    assert len(lines) >= 30, f"only {len(lines)} uses: found — the walker lost its subject"
    bad = unpinned(lines)
    assert not bad, ("pin by full SHA with `# vX.Y.Z` (resolve: gh api "
                     "repos/<o>/<r>/git/ref/tags/<tag>):\n" + "\n".join(bad))
