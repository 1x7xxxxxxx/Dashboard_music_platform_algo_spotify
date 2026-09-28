#!/usr/bin/env python3
"""Every document and every script of the repository, with its readers and a decision — on demand.

Type: Utility
Uses: git (ls-files, log), .claude/scripts/audit_unreachable_tools.py (the execution surfaces
      and the catalogue signatures — ONE definition of « who runs a script »)
Triggers: `make inventory`
Persists in: revue/inventaire.md (gitignored) — generated when asked, never kept up to date

R305 (2026-09-28). The owner no longer wants documentation kept current to understand the repo:
explanations are regenerated on demand. This is the deliverable that lists everything and says,
for each file, keep / archive — and WHY.

⚠️ THE CRITERION IS THE PATH CITED, NEVER THE TITLE (code-critic, 2026-09-28). Six documents
that LOOKED frozen were still read: GANTT (rewritten by a tool), migration-hetzner (deployment.md),
token-management-bilan (ADR-006), prod-health-monitoring (CLAUDE.md), schema-drift-2026-06-13
(`airflow_kpi.py`), refactor-audit-dashboard (`credentials/__init__.py`). A document is an archive
candidate only when NO live file names it. History does not count as a reader: DEVLOG, the
roadmap archive and `.test_durations` cite a file because it once existed, not because anyone
opens it (the DEVLOG itself is archived since R311).

    python3 tools/dev/repo_inventory.py [out.md]
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Files that cite others as HISTORY, not as readers.
HISTORY = {".claude/dev-docs/roadmap/archive.md",
           ".test_durations", ".claude/dev-docs/architecture/notes-triage.yaml"}
DOC_SUFFIXES = (".md",)
SCRIPT_ROOTS = ("tools/", ".claude/scripts/", ".claude/hooks/", "airflow/debug_dag/", "scripts/")
#: Directories whose files are loaded by the harness or injected by a hook — alive by location.
LOADED = (".claude/agents/", ".claude/commands/", ".claude/skills/", ".claude/rules/",
          ".claude/workflows/", ".claude/dev-docs/work-in-progress/")


def _git_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return [f for f in out.stdout.splitlines() if (ROOT / f).is_file()]


def _unreachable():
    spec = importlib.util.spec_from_file_location(
        "audit_unreachable_tools", ROOT / ".claude" / "scripts" / "audit_unreachable_tools.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_archived(rel: str) -> bool:
    return rel.startswith(("archive/", ".claude/.retired/")) or "/.migrated/" in rel


def readers_of(rel: str, texts: dict[str, str]) -> list[str]:
    """The live files that name `rel` — by its path, by its basename when unambiguous, or, for a
    Python module, by an `import <stem>` of a sibling. Pure.

    A basename shared by several files (README.md, SKILL.md, hook.md) only counts as a path:
    matching it bare would make every README a reader of every other. The import form was
    missed by the first run: `architecture_dossier/main.py` loads `part1` … `part6` by module
    name, and all six came out « rien ne le lance »."""
    import re
    name = rel.rsplit("/", 1)[-1]
    generic = name in {"README.md", "SKILL.md", "hook.md", "context.md", "plan.md"}
    imp = (re.compile(rf"^\s*(?:from|import)\s+{re.escape(name[:-3])}\b", re.M)
           if name.endswith(".py") else None)
    folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
    out = []
    for other, text in texts.items():
        if other == rel or other in HISTORY or is_archived(other):
            continue
        if rel in text or (not generic and name in text):
            out.append(other)
        elif imp and other.startswith(folder + "/") and imp.search(text):
            out.append(other)
    return out


FROZEN_DAYS = 21


def decide_doc(rel: str, readers: list[str], age_days: int = 0,
               describes_folder: bool = False) -> tuple[str, str]:
    """(decision, reason) for a document. Pure.

    A document frozen for more than FROZEN_DAYS that only OTHER DOCUMENTS cite is archived
    too: the owner reads nothing to understand the repo any more, and a pointer between two
    documents is repointed, not a reason to keep both current. Code, tests, CLAUDE.md or the
    Makefile citing it keep it — that is a reader that runs."""
    if is_archived(rel):
        return "archivé", "déjà dans une archive"
    if describes_folder:
        return "garder", "décrit le dossier de fichiers où il vit"
    if rel.startswith(LOADED):
        return "garder", "chargé par Claude Code ou injecté par un hook"
    if rel.startswith("docs/adr/"):
        return "garder", "ADR — une décision de configuration"
    tests = [r for r in readers if r.startswith("tests/")]
    # A command, skill or workflow the model EXECUTES, and an ADR, read a document as surely
    # as code does: `/resume` opens `_archived_retro.md` at every restart.
    code = [r for r in readers if r.endswith((".py", ".sh", ".yml", ".yaml", ".json", ".js"))
            or r in ("Makefile", "CLAUDE.md") or r.startswith((*LOADED, "docs/adr/"))]
    if tests:
        return "garder", f"lu par un test ({tests[0].rsplit('/', 1)[-1]})"
    if code:
        return "garder", f"nommé par {code[0]}"
    if readers and age_days > FROZEN_DAYS:
        return "archiver", (f"figé depuis {age_days} j, cité seulement par des documents "
                            f"({readers[0]}) — pointeurs à repointer")
    if readers:
        return "garder", f"cité par un document vivant ({readers[0]})"
    return "archiver", "aucun fichier vivant ne le cite"


def decide_script(rel: str, callers: list[str], instrument: bool) -> tuple[str, str]:
    """(decision, reason) for a script. Pure."""
    if is_archived(rel):
        return "archivé", "déjà dans une archive"
    if instrument:
        return "archiver", "outil de mesure à usage ponctuel (déclaré dans son en-tête)"
    runners = [c for c in callers if not c.endswith(".md")]
    if runners:
        return "garder", f"lancé ou importé par {runners[0]}"
    if callers:
        return "archiver", f"seulement cité en prose ({callers[0]})"
    return "archiver", "rien ne le lance ni ne le cite"


def build() -> str:
    files = _git_files()
    text_files = [f for f in files if f.endswith((".md", ".py", ".sh", ".yml", ".yaml", ".json",
                                                  ".js", ".toml", ".cfg", ".txt", ".sql"))
                  or f in ("Makefile", ".test_durations")]
    texts = {}
    for f in text_files:
        try:
            texts[f] = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    uat = _unreachable()
    sigs = uat._signatures()
    docs = [f for f in files if f.endswith(DOC_SUFFIXES) and not f.startswith("tests/")]
    scripts = [f for f in files if f.startswith(SCRIPT_ROOTS) and f.endswith((".py", ".sh"))
               and not f.endswith("__init__.py")]
    rows_d, rows_s = [], []
    import datetime as dt
    today = dt.date.today()
    dates = {}
    log = subprocess.run(["git", "log", "--format=@%cs", "--name-only", "--", *docs], cwd=ROOT,
                         capture_output=True, text=True).stdout
    cur = None
    for line in log.splitlines():
        if line.startswith("@"):
            cur = dt.date.fromisoformat(line[1:])
        elif line and line not in dates:
            dates[line] = cur
    tracked = set(files)
    for d in docs:
        folder = d.rsplit("/", 1)[0] if "/" in d else ""
        describes = (d.endswith("README.md") and folder and not folder.startswith(".claude")
                     and any(f.startswith(folder + "/") and not f.endswith(".md")
                             for f in tracked))
        age = (today - dates[d]).days if dates.get(d) else 0
        dec, why = decide_doc(d, readers_of(d, texts), age, describes)
        rows_d.append((dec, d, why))
    for s in scripts:
        callers = readers_of(s, texts)
        if s.rsplit("/", 1)[-1] in sigs:
            callers = [".claude/dev-docs/error-classes.md (signature lancée par audit_runner)",
                       *callers]
        dec, why = decide_script(s, callers, uat.est_instrument(texts.get(s, "")))
        rows_s.append((dec, s, why))
    order = {"archiver": 0, "garder": 1, "archivé": 2}
    lines = ["# Inventaire du dépôt — documents et scripts (R305)", "",
             "Généré à la demande par `make inventory` ; jamais tenu à jour. Critère : le CHEMIN "
             "cité par un fichier vivant (l'historique — archive de roadmap, "
             "`.test_durations` — ne compte pas comme lecteur).", ""]
    for title, rows in (("Documents", rows_d), ("Scripts", rows_s)):
        n = {k: sum(1 for r in rows if r[0] == k) for k in order}
        lines += [f"## {title} — {len(rows)} ({', '.join(f'{k} {v}' for k, v in n.items())})",
                  "", "| décision | fichier | pourquoi |", "|---|---|---|"]
        lines += [f"| {d} | `{f}` | {w} |" for d, f, w in sorted(rows, key=lambda r: (order[r[0]], r[1]))]
        lines.append("")
    lines += ["## Refactor, latence, scalabilité — les pistes mesurées le 2026-09-28", "",
              "Dans la roadmap : R307 (outillage de dev), R309 (contrôle de contamination "
              "nocturne), R310 (crontab de prod, produit qui importe `tools/`).", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "revue" / "inventaire.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"écrit : {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
