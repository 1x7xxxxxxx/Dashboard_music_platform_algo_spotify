#!/usr/bin/env python3
"""
Error-class signature runner — single executable source of truth.

Parses every class in `.claude/dev-docs/error-classes.md`, extracts its
`signature` / `kind` / `status`, and runs each signature.cmd. The catalogue
contract: a signature exits NON-ZERO when the anti-pattern is present (a "hit").

This replaces the hand-synced grep recipes in the Makefile `audit:` target, so
a class added to the catalogue is swept automatically (no catalogue↔Makefile
drift). `kind: deterministic` classes are CI-safe (0 false positives) and may
block; `kind: heuristic` classes run nightly, non-blocking (manual triage).

Usage:
  audit_runner.py --deterministic   # only kind: deterministic; exit 1 on any hit (CI blocking)
  audit_runner.py [--all]           # every class; exit 1 on any hit (nightly; caller tolerates with || true)
  audit_runner.py --list            # list id · kind · status, no run

Type: Utility (Claude Code config)
Uses: error-classes.md, subprocess
Persists in: — (report to stdout + exit code)

---
rex:
  - date: 2026-06-13
    issue: "make audit hardcoded ~6 grep signatures while error-classes.md catalogued 21 → drift; new classes never swept"
    fix: "audit_runner.py parses error-classes.md signatures and runs them; Makefile + CI delegate to it (catalogue = single source of truth)"
    ref: "DEVLOG#2026-06-13-suite22"
    severity: warn
---
"""
import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Best-effort usage telemetry (curator self-improvement loop). Defensive: a broken
# sidecar must never fail the audit / CI sweep.
try:
    from usage_telemetry import record as _telemetry_record
except Exception:  # noqa: BLE001 — telemetry is optional
    def _telemetry_record(*_a, **_k):
        return None

_REPO = Path(__file__).resolve().parents[2]            # .claude/scripts/ -> repo root
_CATALOGUE = _REPO / ".claude/dev-docs/error-classes.md"

# Documentation scaffolding sections that look like a class header but are not runnable.
_SKIP_IDS = {"class-id"}
_KEBAB = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_all_headers(text: str) -> list[dict]:
    """Return one dict per class header (kebab id), signature-bearing OR NOT.

    {id, kind, status, signature|None}. Unlike the old parser this does NOT drop
    signature-less (prose) classes — the `--coverage` meta-guard needs to SEE them
    (a catalogued-but-un-swept class is the exact blind spot that let the 2026-07-07
    Alembic prose REX re-fire). The id is the FIRST token of the header, so a
    date/ADR suffix (`## foo (2026-07-11, ADR-047)`) no longer breaks kebab matching.
    """
    out = []
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = sec.splitlines()
        cid = (lines[0].strip().split() or [""])[0]      # first token → tolerate "(date, ADR)" suffix
        if cid.lower() in _SKIP_IDS or not _KEBAB.match(cid):
            continue
        body = "\n".join(lines[1:])
        # First backtick-delimited span after "- signature:"; tolerate trailing prose
        # after the closing backtick. Signatures never contain an internal backtick.
        # A `—` placeholder (no real command) counts as NO signature.
        sig = re.search(r"^- signature:\s*`([^`]+)`", body, flags=re.M)
        sig_val = sig.group(1).strip() if sig else None
        if sig_val in ("—", "-", ""):
            sig_val = None
        kind = re.search(r"^- kind:\s*([\w-]+)", body, flags=re.M)
        status = re.search(r"^- status:\s*([\w-]+)", body, flags=re.M)
        out.append({
            "id": cid,
            "kind": (kind.group(1) if kind else ("heuristic" if sig_val else "")).lower(),
            "status": (status.group(1) if status else "open").lower(),
            "signature": sig_val,
            "root_cause": _prose_field(body, "root_cause"),
            "long_term_fix": _prose_field(body, "long_term_fix"),
        })
    return out


def _prose_field(body: str, name: str) -> str | None:
    """Value of a free-text `- <name>:` line, or None when absent/empty.

    A bare `—` is None: the schema uses it as "nothing to say here", and counting
    it as an answer would make the field-completeness check pass on the classes it
    exists to find. `— (the guard IS the fix)` is NOT bare — it is a real answer,
    and the commonest legitimate one for a class whose signature is the whole fix.
    """
    m = re.search(rf"^- {name}:\s*(.*)$", body, flags=re.M)
    if not m:
        return None
    val = m.group(1).strip()
    return None if val in ("", "—", "-", "<...>") else val


def parse_classes(text: str) -> list[dict]:
    """Runnable classes only (those carrying a real `- signature:` command)."""
    return [c for c in parse_all_headers(text) if c["signature"]]


def run_signature(sig: str) -> tuple[bool, str]:
    """Run one signature from the repo root. Returns (hit, output)."""
    proc = subprocess.run(
        sig, shell=True, cwd=_REPO,
        capture_output=True, text=True, timeout=300,
    )
    hit = proc.returncode != 0
    return hit, (proc.stdout + proc.stderr).strip()


def _venv_python() -> str:
    """Path to the project interpreter, resolved from the MAIN worktree.

    Every signature names `python/.venv/bin/python`, but `python/.venv` is
    gitignored — so a linked worktree (the engineering loop runs its Fix phase in
    one) has no interpreter at that path. The signature then either errors out or
    silently falls back to the system python, which cannot import ~21 of the test
    modules; either way the guard reports something unrelated to the code.

    `--git-common-dir` points at the shared .git of the main worktree, whose
    parent is the main checkout, which is where the venv actually lives.
    """
    local = _REPO / "python" / ".venv" / "bin" / "python"
    if local.exists():
        return str(local)
    try:
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                                cwd=_REPO, capture_output=True, text=True,
                                timeout=30, check=True).stdout.strip()
        main_root = (_REPO / common).resolve().parent
        candidate = main_root / "python" / ".venv" / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    except (subprocess.SubprocessError, OSError):
        pass
    return sys.executable          # last resort; loud because the run will fail visibly


_SHELL_OPS = re.compile(r"[|;&><]|\$\(")


def pytest_targets(sig: str) -> list[str] | None:
    """Node-ids a *simple* pytest signature targets, or None if it is not batchable.

    Conservative on purpose: anything carrying a shell operator keeps its own
    subprocess. Measured on this catalogue: 40/40 pytest signatures are simple,
    resolving to 42 unique node-ids across 32 files.
    """
    if "pytest" not in sig or _SHELL_OPS.search(sig):
        return None
    try:
        toks = shlex.split(sig)
    except ValueError:
        return None
    if "pytest" not in toks:
        return None
    after = toks[toks.index("pytest") + 1:]
    targets = [t for t in after if not t.startswith("-") and ".py" in t]
    return targets or None


def _failed_nodes(output: str) -> set[str]:
    """Node-ids pytest reported as FAILED or ERROR in its short summary."""
    return set(re.findall(r"^(?:FAILED|ERROR)\s+(\S+?)(?:\s+-.*)?$", output, re.M))


def run_batched(classes: list[dict]) -> tuple[dict[str, tuple[bool, str]], list[dict]]:
    """Run every batchable pytest class in ONE pytest invocation.

    40 separate invocations pay pytest startup and collection 40 times; on a 9p
    mount that was ~7 s each before a single assertion ran. One invocation over
    the union of node-ids pays it once (measured: 45.7 s of collection for the
    whole set).

    Returns ({class_id: (hit, output)}, [classes to run individually]).
    Falls back wholesale when pytest reports anything other than pass/fail —
    a collection error cannot be attributed to one class, and guessing would be
    worse than being slow.
    """
    targets: dict[str, list[str]] = {}
    rest: list[dict] = []
    for c in classes:
        t = pytest_targets(c["signature"])
        if t:
            targets[c["id"]] = t
        else:
            rest.append(c)

    if len(targets) < 2:
        return {}, classes

    union = sorted({t for ts in targets.values() for t in ts})
    print(f"▶ batching {len(targets)} pytest signature(s) → 1 invocation "
          f"({len(union)} node-ids)\n")
    proc = subprocess.run(
        [_venv_python(), "-m", "pytest", *union, "-q", "--tb=no", "-rfE"],
        cwd=_REPO, capture_output=True, text=True, timeout=1800,
    )
    out = proc.stdout + proc.stderr
    if proc.returncode not in (0, 1):
        print(f"  batch inconclusive (pytest exit {proc.returncode}) — "
              f"falling back to one run per signature")
        return {}, classes

    failed = _failed_nodes(out)
    results: dict[str, tuple[bool, str]] = {}
    for cid, ts in targets.items():
        hit_nodes = [f for f in failed
                     if any(f == t or f.startswith(t + "::") for t in ts)]
        detail = "\n".join(hit_nodes) if hit_nodes else ""
        results[cid] = (bool(hit_nodes), detail)
    return results, rest


_OPTOUT_KINDS = {"manual", "runtime-manual"}  # acknowledged as intentionally NOT auto-swept


def _coverage(headers: list[dict]) -> int:
    """Meta-guard: every catalogued class must be GUARDED (has a runnable `- signature:`) OR
    carry an explicit opt-out `- kind:` ∈ {manual (needs host access), runtime-manual (no static
    footprint)}. A class with NEITHER (prose with no kind, or a kind that implies auto-sweep like
    `deterministic` but no signature) is UNGUARDED — the catalogue silently accreting un-swept
    prose is the structural blind spot. Exit 1 on any unguarded class."""
    unguarded = [h for h in headers if h["signature"] is None and h["kind"] not in _OPTOUT_KINDS]
    guarded = [h for h in headers if h["signature"]]
    optout = [h for h in headers if h["signature"] is None and h["kind"] in _OPTOUT_KINDS]
    total = len(headers)
    pct = (100 * len(guarded) // total) if total else 0
    print(f"▶ coverage: {total} classes — {len(guarded)} guarded ({pct}%) · "
          f"{len(optout)} manual/runtime opt-out · {len(unguarded)} UNGUARDED")
    if unguarded:
        print("\n❌ UNGUARDED classes (add a `- signature:` OR `- kind: runtime-manual`):")
        for h in unguarded:
            print(f"      {h['id']}  [kind={h['kind'] or '∅'}/{h['status']}]")
        return 1
    print("\n✅ coverage complete — every class is guarded or explicitly runtime-manual")
    return 0


def _fields(headers: list[dict]) -> int:
    """Schema completeness: does every class say WHY it happened and WHAT ends it?

    Why this is a separate gate from `--coverage`, and not folded into it.
    `--coverage` asks "is this class swept?" — a question about the signature.
    This asks "is this class UNDERSTOOD?" — a question about the two fields the
    signature cannot answer. They fail independently and are fixed by different
    work, so one exit code for both would hide whichever came second.

    Why it exists at all (found 2026-08-03, on the n8n deployment). `/capitalise`
    writes `root_cause` and `long_term_fix`; the catalogue shipped in the payload
    declared neither in its per-class schema; and `--coverage` checked only for a
    signature. So the producer wrote two fields nothing read, into a file whose
    own schema did not list them — and every class in the target repo had 0 of 2,
    while the sweep still reported 9/9 guarded. A field no command checks is not
    filled. This is that command.

    `long_term_fix` is the one that carries the weight: a signature says the class
    is *detectable*, only the fix says it can *stop happening*. `— (the guard IS
    the fix)` is a legitimate answer; a blank is not an answer.
    """
    missing = [(h, [f for f in ("root_cause", "long_term_fix") if not h[f]])
               for h in headers]
    missing = [(h, f) for h, f in missing if f]
    total = len(headers)
    complete = total - len(missing)
    pct = (100 * complete // total) if total else 0
    print(f"▶ fields: {total} classes — {complete} complete ({pct}%) · "
          f"{len(missing)} incomplete")
    if missing:
        print("\n❌ classes missing a schema field "
              "(`/capitalise` writes both; backfill by hand or re-run it):")
        for h, fields in missing:
            print(f"      {h['id']}  [manque: {', '.join(fields)}]")
        print("\n   A class with no `long_term_fix` is a class nobody decided how "
              "to end.\n   It will recur, and its signature will faithfully "
              "report it recurring.")
        return 1
    print("\n✅ fields complete — every class states its root cause and its long-term fix")
    return 0


# File kinds that can only ever DESCRIBE a defect, and the comment markers that
# do the same job inside code. A hit landing on one of these is a hit on prose.
#
# ⚠️ An extension is NOT enough, and the first version of this guard got it
# wrong in the way it exists to prevent. It marked every `.md` hit as prose and
# went red on three repos over `.claude/commands/sprint.md` and
# `.claude/rules/rex-format.md` — which are CONFIGURATION. An unsubstituted
# `{{PLACEHOLDER}}` in a command file is a real defect, and the guard was calling
# it noise. In this fleet markdown is the language configuration is written in;
# only `.claude/dev-docs/` (the catalogue, the ROADMAP) and markdown OUTSIDE
# `.claude/` describe rather than act.
_PROSE_EXT = {".md", ".rst", ".txt", ".adoc", ".org"}
_MARKERS = {
    ".py": ("#",), ".sh": ("#",), ".bash": ("#",), ".rb": ("#",), ".pl": ("#",),
    ".yml": ("#",), ".yaml": ("#",), ".toml": ("#",), ".cfg": ("#",), ".ini": (";", "#"),
    ".js": ("//", "/*", "*"), ".ts": ("//", "/*", "*"), ".jsx": ("//", "/*", "*"),
    ".tsx": ("//", "/*", "*"), ".java": ("//", "/*", "*"), ".c": ("//", "/*", "*"),
    ".h": ("//", "/*", "*"), ".cpp": ("//", "/*", "*"), ".go": ("//",), ".rs": ("//",),
    ".sql": ("--",), ".lua": ("--",), ".hs": ("--",),
}
_GREP_LIKE = re.compile(r"\b(grep|rg|ack|ag)\b")
_HIT_LINE = re.compile(r"^(?P<path>[^:]+):(?P<num>\d+):(?P<body>.*)$")
# `-q`/`--quiet` prints nothing; `-c` prints counts. Either way the signature
# answers yes/no and refuses to say WHERE — see `_silent` below.
# Short flags CLUSTER: the fleet writes `-rqi`, not `-q -r -i`. Matching a
# cluster and testing membership is the only form that sees it.
_SHORT_CLUSTER = re.compile(r"(?<![\w-])-([a-zA-Z]+)(?![\w-])")
_LONG_SILENT = re.compile(r"--(quiet|silent|count)\b")


def _hit_is_prose(line: str) -> bool | None:
    """Does this hit land on text that merely DESCRIBES the defect?

    Two output shapes are understood, because both occur in the fleet:
      * `path:line:content` (plain grep) — the line itself is read;
      * a bare `path` (`grep -l`) — only the file kind can be judged, so a
        markdown hit is prose and a code hit is left undecided. Half an answer
        is still an answer; guessing the other half would not be.

    Returns None when nothing can be concluded. Unclassifiable is a distinct
    verdict from "fine", and it is reported as such.
    """
    line = line.strip()
    m = _HIT_LINE.match(line)
    if m:
        if _est_doc(m.group("path")):
            return True
        ext = Path(m.group("path")).suffix.lower()
        marqueurs = _MARKERS.get(ext)
        if not marqueurs:               # kind we cannot read: say so, do not guess
            return None
        body = m.group("body").strip()
        return any(body.startswith(mk) for mk in marqueurs)
    # `grep -l` — a path and nothing else. Only the file kind can be judged;
    # a config file hit stays undecided rather than being called noise.
    if line and ":" not in line:
        return True if _est_doc(line) else None
    return None


def _est_doc(chemin: str) -> bool:
    """Is this file DESCRIBING, as opposed to being the thing itself?

    Markdown is this fleet's configuration language, so the extension decides
    nothing on its own. Two places describe: `.claude/dev-docs/` — the catalogue
    and the ROADMAP, which talk *about* the work — and prose files outside
    `.claude/` entirely. Everything else under `.claude/` is an agent, a command
    or a rule: it acts, and a defect in it is a defect.
    """
    # `lstrip("./")` retire un JEU de caractères, donc il mange le point de
    # `.claude` et classe toute la configuration comme documentation. C'est le
    # défaut qui a fait rougir trois dépôts à tort.
    q = chemin.replace("\\", "/")
    while q.startswith("./"):
        q = q[2:]
    if Path(q).suffix.lower() not in _PROSE_EXT:
        return False
    return q.startswith(".claude/dev-docs/") or not q.startswith(".claude/")


def _silent(sig: str) -> bool:
    """Does this signature refuse, by construction, to say what it matched?

    `grep -q` exits 0/1 and prints nothing; `grep -c` prints a count. Both answer
    « is the class touched » and neither answers « on what ». That is not a
    detail: a class going red then becomes unreviewable — nobody can tell a real
    defect from a comment describing one without re-running the command by hand
    and re-deriving what it was supposed to mean.

    Found on the fleet, 2026-08-03: 6 classes across 5 repos, including the two
    that motivated this guard. Their signatures had been narrowed to code
    (`--include=*.py`), which was the right fix, and stayed silent, which keeps
    the fix unverifiable. Reported, never failed — a silent signature is a real
    guard, just one nobody can audit.
    """
    if not _GREP_LIKE.search(sig):
        return False
    if _LONG_SILENT.search(sig):
        return True
    return any(set(m.group(1)) & {"q", "c"} for m in _SHORT_CLUSTER.finditer(sig))


def _prose(classes: list[dict]) -> int:
    """Meta-guard: is a signature catching the DEFECT, or its own description?

    Why this exists (found 2026-08-03, on the n8n deployment). A `deterministic`
    class went red on the comments that explained its own fix. Writing about a
    defect made the guard fire — so the only way to keep CI green was to stop
    documenting, which is the opposite of what a catalogue is for.

    The damage is not one wrong verdict. A deterministic class is CI-blocking by
    contract; one that blocks on a comment teaches everyone that a red audit may
    be noise, and that lesson is applied to the other eight signatures too. This
    guard exists so the catalogue can say which is which, with evidence.

    It only judges signatures that HIT — a green one exposes nothing to classify
    — and only grep-family ones, whose output locates its matches. pytest
    signatures are reported as out of scope rather than silently counted as fine.

    Fails only when EVERY locatable hit of a class is prose: that signature is
    reporting nothing but talk about the defect. A mixed class is reported and
    not failed — it has caught something real, and narrowing it is a judgement
    call about which hits matter, not a verdict this guard can reach.
    """
    detm = [c for c in classes if c["kind"] == "deterministic"]
    scoped = [c for c in detm if _GREP_LIKE.search(c["signature"])]
    out_of_scope = [c for c in detm if c not in scoped]

    all_prose, mixed, unlocatable, muettes = [], [], [], []
    for c in scoped:
        hit, output = run_signature(c["signature"])
        if not hit:
            continue
        if _silent(c["signature"]):
            muettes.append(c["id"])
            continue
        verdicts = [_hit_is_prose(ln) for ln in output.splitlines()]
        placed = [v for v in verdicts if v is not None]
        if not placed:
            unlocatable.append(c["id"])
        elif all(placed):
            all_prose.append((c["id"], sum(placed), output.splitlines()[:3]))
        elif any(placed):
            mixed.append((c["id"], sum(placed), len(placed)))

    print(f"▶ prose: {len(detm)} deterministic — {len(scoped)} locatable (grep-family) · "
          f"{len(out_of_scope)} out of scope (pytest: their output locates nothing)")
    for cid, n, total in mixed:
        print(f"  ⚠  {cid}: {n}/{total} hits land on comments or docs — "
              f"narrow it to code, or say why those hits count")
    if muettes:
        print(f"  ⊘  SILENT and red — say yes/no, never where: {', '.join(muettes)}\n"
              f"     Drop -q/-c so the class can be triaged without re-deriving the command.")
    if unlocatable:
        print(f"  ?  unclassifiable output (not path:line:text): {', '.join(unlocatable)}")
    if all_prose:
        print("\n❌ signature(s) reporting ONLY prose — they fire on the text that "
              "DESCRIBES the defect, not on the defect:")
        for cid, n, sample in all_prose:
            print(f"      {cid}  ({n} hits, all prose)")
            for ln in sample:
                print(f"        {ln}")
        print("\n   A deterministic class blocks CI by contract. One that blocks on a "
              "comment\n   teaches that a red audit may be noise — and that lesson is "
              "applied to\n   the others. Read code, not text: `--include`, a language-aware "
              "matcher,\n   or at minimum exclude comment lines.")
        return 1
    print("\n✅ prose-clean — no deterministic signature fires on its own description")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Run error-class signatures from the catalogue")
    ap.add_argument("--deterministic", action="store_true",
                    help="Run only kind: deterministic classes; exit 1 on any hit (CI-safe)")
    ap.add_argument("--static", action="store_true",
                    help="Run deterministic classes whose signature is grep-only (no pytest) — "
                         "for the IPC daily sweep (no PG / test env)")
    ap.add_argument("--coverage", action="store_true",
                    help="Meta-guard: fail if any class lacks a signature AND isn't runtime-manual")
    ap.add_argument("--fields", action="store_true",
                    help="Schema completeness: fail if any class lacks root_cause or long_term_fix")
    ap.add_argument("--prose", action="store_true",
                    help="Meta-guard: fail if a deterministic signature fires only on comments/docs "
                         "— i.e. on the text that describes the defect instead of the defect")
    ap.add_argument("--all", action="store_true", help="Run every class (default)")
    ap.add_argument("--list", action="store_true", help="List classes and exit")
    ap.add_argument("--no-batch", action="store_true",
                    help="Run each pytest signature in its own invocation (the pre-batching\n                         behaviour). Slower by ~10x; use it to attribute a suspicious batch result.")
    args = ap.parse_args()

    if not _CATALOGUE.exists():
        print(f"❌ catalogue not found: {_CATALOGUE}", file=sys.stderr)
        sys.exit(2)

    text = _CATALOGUE.read_text(encoding="utf-8")
    headers = parse_all_headers(text)
    classes = [c for c in headers if c["signature"]]
    if not headers:
        # « zero classe » et « fichier malforme » sont deux etats DIFFERENTS, et
        # les confondre casse la CI d'un depot neuf des le premier jour : le
        # catalogue y est vide par construction, ce qui n'est pas une erreur.
        # On les distingue par la presence du CONTRAT en tete du gabarit — un
        # fichier qui le porte est bien forme, il n'a simplement rien a dire
        # encore. Trouve le 2026-08-02 en testant la config assemblee sur un
        # depot vierge, avant de la recommander en CI.
        # Le gabarit existe en deux langues — `config-optimale/` en francais,
        # celui du payload en anglais. Ne reconnaitre que la sentinelle francaise
        # faisait sortir 2 (« fichier malforme ») sur un catalogue anglais vide,
        # c'est-a-dire exactement le cas que ce bloc existe pour ne pas confondre.
        if re.search(r"^## (Sch[ée]ma par classe|Per-class schema)", text, re.M):
            print("catalogue vide : 0 classe capitalisée pour l'instant. "
                  "Rien à vérifier, et ce n'est pas une erreur.")
            sys.exit(0)
        print("❌ no classes parsed — check error-classes.md format", file=sys.stderr)
        sys.exit(2)

    if args.coverage:
        sys.exit(_coverage(headers))

    if args.fields:
        sys.exit(_fields(headers))

    if args.prose:
        sys.exit(_prose(classes))

    if args.list:
        skipped = [h for h in headers if not h["signature"]]
        for c in classes:
            print(f"  {c['id']:<44} {c['kind']:<15} {c['status']}")
        print(f"\n{len(classes)} runnable classes "
              f"({sum(c['kind'] == 'deterministic' for c in classes)} deterministic) · "
              f"{len(skipped)} without a signature")
        if skipped:
            print("  no-signature (coverage-tracked): "
                  + ", ".join(f"{h['id']}[{h['kind'] or '∅'}]" for h in skipped))
        sys.exit(0)

    # kind: manual / runtime-manual = never auto-run (need host access, or no static footprint).
    if args.static:
        selected = [c for c in classes
                    if c["kind"] == "deterministic" and "pytest" not in c["signature"]]
        mode = "static"
    elif args.deterministic:
        selected = [c for c in classes if c["kind"] == "deterministic"]
        mode = "deterministic"
    else:
        selected = [c for c in classes if c["kind"] not in ("manual", "runtime-manual")]
        mode = "all"
    print(f"▶ audit_runner ({mode}): {len(selected)} signatures\n")

    batched: dict[str, tuple[bool, str]] = {}
    individual = selected
    if not args.no_batch:
        batched, individual = run_batched(selected)

    hits = []
    for c in selected:
        if c["id"] in batched:
            hit, output = batched[c["id"]]
        else:
            hit, output = run_signature(c["signature"])
        _telemetry_record("error_classes", c["id"], hit=hit)  # curator usage signal
        mark = "⚠ HIT" if hit else "✅"
        print(f"  {mark}  {c['id']}  [{c['kind']}/{c['status']}]")
        if hit:
            hits.append(c["id"])
            for line in output.splitlines()[:6]:
                print(f"        {line}")

    if hits:
        print(f"\n⚠ {len(hits)} class(es) with hits: {', '.join(hits)}")
        if args.deterministic or args.static:
            print("  (deterministic → CI-blocking: these are real, fix or re-triage the signature)")
        else:
            print("  (heuristic sweep → manual triage; nightly non-blocking)")
        sys.exit(1)
    print("\n✅ audit clean")
    sys.exit(0)


if __name__ == "__main__":
    main()
