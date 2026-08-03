#!/usr/bin/env python3
"""Flag configuration that names a `.claude/` file which does not exist. A signature, not a review.

This is the class the fleet keeps re-finding by hand. Measured 2026-08-03 on the n8n round-trip:
`roadmap-keeper`'s description routed to `error-class-writer` (retired by the same deployment),
`sweep.md` cited `.claude/rules/makefile-fail-fast.md` and `promote_rex.py` (neither ever shipped),
and `suggest_sweep.py` PRINTED `.claude/skills/impact-analysis.md` to the user on every bugfix
session — months after that skill moved to `impact-analysis/SKILL.md`. Five dangling references,
all in shipped configuration, none detectable by `piece-installed-without-a-rule`: that class asks
whether a present file is NAMED, this one asks whether a name POINTS at something. They are
inverses, and the fleet only had the first half.

WHY A SIGNATURE AND NOT A READER. A dangling reference is invisible by construction: the file
reads perfectly, and only resolving the path against the disk shows the hole. That is a `test`,
not a `judgement` — and the fleet's own numbers say a check that needs someone to remember it is
a check that does not run (4 of 6 declared agents: 0 invocations).

SCOPE, and it is deliberately narrow. Only **explicit** `.claude/...` paths ending in `.py` or
`.md` are resolved. A bare relative mention (`skills/foo.md` inside CLAUDE.md) is NOT checked:
disambiguating it needs a guess, and a signature that guesses is a signature that goes red on
something correct — after which nobody trusts the red. The limit is real and it is the price of
`kind: deterministic`.

    python3 .claude/scripts/check_config_refs.py       # exit != 0 = a name points at nothing

---
rex: []
---
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]

# Where configuration lives. `dev-docs/` is excluded: it is the catalogue and the ROADMAP, which
# talk ABOUT the work — the same split `audit_runner.py --prose` draws.
_ROOTS = ("agents", "commands", "rules", "hooks", "scripts", "skills")

# `(?<![~/\w])` : un chemin de la config UTILISATEUR (`~/.claude/RTK.md`) n'est pas
# un chemin du dépôt, et le résoudre contre la racine du dépôt le déclare toujours
# manquant. Trouvé sur streamlytics le 2026-08-03, sur une ligne qui disait
# elle-même « user-global config, not in this repo » — le garde contredisait le
# texte qu'il lisait. Sans le `/` dans la classe, `~/.claude/…` passait quand même
# parce que le `~` n'est pas collé au point.
_REF = re.compile(r"(?<![~/\w])\.claude/[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|md)")

# Paths a correct repo may legitimately lack: they are produced at runtime, not installed.
# `sessions/` is written by draft_rex.py, `archives/` accumulates over time. Listing them here
# rather than widening the regex keeps every OTHER miss a genuine hit.
_RUNTIME = (".claude/sessions/", ".claude/dev-docs/archives/")


def _is_archived(path: pathlib.Path) -> bool:
    """Does this file sit in a retirement directory?

    `.retired/` and `.migrated/` are how this fleet takes a component out of
    service without deleting it — a dotdir, so the loaders ignore it and the move
    is reversible with one `mv`. Their contents are therefore NOT live
    configuration, and resolving their paths reports defects in files that were
    deliberately switched off. Measured on n8n 2026-08-03: 3 of the 6 hits were
    `skills/.migrated/work-brick.md`, a flat skill superseded months ago — noise
    that makes the other 3, which are real, harder to see.
    """
    return any(part.startswith(".") for part in path.parts)


def _candidates() -> list[pathlib.Path]:
    base = _REPO / ".claude"
    files = [p for root in _ROOTS for p in sorted((base / root).rglob("*"))
             if p.is_file() and p.suffix in {".py", ".md", ".json"}
             and not _is_archived(p.relative_to(base))]
    root_md = _REPO / "CLAUDE.md"
    if root_md.exists():
        files.append(root_md)
    return files


def _prose_cutoff(path: pathlib.Path, text: str) -> int:
    """Last line of a Python module docstring — everything up to it DESCRIBES, it does not act.

    Without this the guard fires on its own explanation: the first run flagged lines 6-7 of THIS
    file, where the dangling paths it exists to find are quoted as evidence. That is the failure
    mode `audit_runner.py --prose` was written for, reproduced inside the fix for another class.
    A deterministic signature must read code, so a `.py` file is scanned from the end of its
    docstring onward, and `#` comment lines never count.
    """
    if path.suffix != ".py":
        return 0
    try:
        mod = ast.parse(text)
    except SyntaxError:
        return 0
    first = mod.body[0] if mod.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
            and isinstance(first.value.value, str):
        return first.end_lineno or 0
    return 0


def main() -> int:
    dangling = []
    for path in _candidates():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        cutoff = _prose_cutoff(path, text)
        for num, line in enumerate(lines, 1):
            if num <= cutoff:
                continue          # module docstring — prose about the code, not the code
            if path.suffix == ".py" and line.lstrip().startswith("#"):
                continue          # a comment describing a defect is not the defect
            if "{{" in line:
                continue          # unsubstituted template — a different class owns that
            for match in _REF.finditer(line):
                target = match.group(0)
                if target.startswith(_RUNTIME):
                    continue
                if not (_REPO / target).exists():
                    dangling.append(f"{path.relative_to(_REPO)}:{num}:{target}")

    # Hits go to stdout as bare `path:line:target`, nothing else. `audit_runner.py --prose`
    # reads this output to decide whether a signature fires on real config or on the text
    # describing it, and it parses `path:line:body`. A decorative "  ❌ " prefix makes the
    # path group start with the glyph, which stops matching `.claude/` — and every hit is
    # then misfiled as prose, failing the meta-guard on a signature that is in fact correct.
    for hit in dangling:
        print(hit)
    if dangling:
        print(f"{len(dangling)} dangling reference(s) — configuration names a file that is not there",
              file=sys.stderr)
        return 1
    print("every .claude/ path named in configuration resolves", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
