#!/usr/bin/env python3
"""Dead code in src/ and airflow/dags/: vulture's candidates, filtered to what nothing names.

Type: Utility
Uses: vulture (dev extra, pinned exactly), git ls-files, ast
Triggers: tests/test_dead_code_only_shrinks.py (the ratchet) ; by hand —
          `python3 tools/dev/dead_code.py [--json] [--without-tests]`
Persists in: nothing (stdout) — the baseline is tests/dead_code_baseline.json

Why this exists — measured 2026-10-15 (R609)
--------------------------------------------
`vulture src/ airflow/dags/ --min-confidence 60` printed 198 candidates. Read raw, they
are mostly noise: a FastAPI route, a pydantic validator or a view's `show()` is called by
a framework, never by name. Filtered mechanically, the funnel was

    198 raw → 76 unused variables (parameters, locals: out of scope)
            → 87 functions whose name appears in another tracked file (a test, a tool,
               a string route in routes.py, a DAG)
            → 9 behind a FRAMEWORK decorator (routes, exception handler, middleware,
               validators)
            → 26 functions named nowhere — dead. The hand count said 25: it had let
               `iso2_to_iso3` through for its `@lru_cache`, which calls nothing.

What this tool does NOT see (guard_scope)
-----------------------------------------
* A function called ONLY by tests is "named elsewhere" and passes as alive — dead in
  production, invisible here. `--without-tests` measures that bucket: 56 live instead
  of 26 on 2026-10-15, so 30 functions only tests call. Reported, not ratcheted
  (removing those means removing their tests: a decision per site).
* Dispatch by a computed name (`getattr(mod, f"render_{x}")`) — none targets a function
  in src/ on 2026-10-15; the views are imported by module STRING, which the mention
  filter already sees.
* Variables, imports and attributes: only functions, methods, properties and classes.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("src", "airflow/dags")
MIN_CONFIDENCE = 60
KINDS = {"function", "method", "property", "class"}
# The mention corpus: code and configuration, NEVER prose. A name cited in a `.md`
# (a roadmap entry, an error class) is not a caller — counting docs hid 2 of the 26.
CORPUS_SUFFIXES = (".py", ".yml", ".yaml", ".sql", ".html", ".js", ".toml")
CORPUS_NAMES = ("Makefile",)
# Decorators through which a FRAMEWORK calls the function. Listed, not inferred: a
# `@lru_cache` or `@staticmethod` function is still dead if nothing calls it.
FRAMEWORK_DECORATOR = re.compile(
    r"^(?:\w+\.)?(?:router\.(?:get|post|put|patch|delete)|app\.(?:exception_handler|middleware"
    r"|get|post|on_event)|field_validator|model_validator|validator)\b")
CONVENTION_NAMES = {"show"}  # a view's entry point, imported by module string
_LINE = re.compile(r"^(.+?):(\d+): unused (\w+) '([^']+)'")
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Candidate:
    path: str
    line: int
    kind: str
    name: str

    @property
    def key(self) -> str:
        return f"{self.path}::{self.name}"


def parse(vulture_out: str) -> list[Candidate]:
    out = []
    for line in vulture_out.splitlines():
        m = _LINE.match(line)
        if m:
            out.append(Candidate(m.group(1), int(m.group(2)), m.group(3), m.group(4)))
    return out


def decorators(source: str, name: str) -> list[str]:
    """Decorators of every def/class called `name` in `source` (all of them: a name
    defined twice is framework-called if either definition is)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.name == name:
            found += [ast.unparse(d) for d in node.decorator_list]
    return found


def classify(cands: list[Candidate], corpus: dict[str, str],
             ) -> tuple[collections.Counter, list[Candidate]]:
    """The funnel. `corpus` is {path: text} of every file a caller could live in,
    the candidates' own files included (a call in the same file is a mention)."""
    funnel: collections.Counter = collections.Counter(raw=len(cands))
    # One tokenisation of the corpus: an identifier's `\b…\b` matches are exactly its
    # occurrences as a `\w+` token. A regex per candidate cost 25 s; this costs 1.
    mentions = collections.Counter(w for text in corpus.values() for w in _WORD.findall(text))
    live = []
    for c in cands:
        if c.kind not in KINDS:
            funnel[f"unused {c.kind} (hors cliquet)"] += 1
            continue
        if c.name in CONVENTION_NAMES or c.name.startswith("test_"):
            funnel["convention (show, test_)"] += 1
            continue
        if mentions[c.name] > 1:  # its own definition is the one mention
            funnel["nommée ailleurs"] += 1
            continue
        if any(FRAMEWORK_DECORATOR.match(d) for d in decorators(corpus.get(c.path, ""), c.name)):
            funnel["décorateur framework"] += 1
            continue
        funnel["vivants (nommés nulle part)"] += 1
        live.append(c)
    return funnel, live


def run_vulture() -> str:
    r = subprocess.run([sys.executable, "-m", "vulture", *TARGETS,
                        "--min-confidence", str(MIN_CONFIDENCE)],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    if r.returncode not in (0, 3):  # 3 = "dead code found", the expected case
        raise RuntimeError(f"vulture failed (rc={r.returncode}): {r.stderr.strip()[:300]}")
    return r.stdout


def load_corpus(without_tests: bool = False) -> dict[str, str]:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    keep = [f for f in files if (f.endswith(CORPUS_SUFFIXES) or Path(f).name in CORPUS_NAMES)
            and not (without_tests and f.startswith("tests/"))]
    return {f: (ROOT / f).read_text(encoding="utf-8", errors="replace")
            for f in keep if (ROOT / f).is_file()}


def dead_keys(without_tests: bool = False) -> tuple[collections.Counter, list[Candidate]]:
    return classify(parse(run_vulture()), load_corpus(without_tests))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="the live keys, as the baseline stores them")
    ap.add_argument("--without-tests", action="store_true",
                    help="drop tests/ from the corpus: measures the 'called only by its test' blind spot")
    a = ap.parse_args(argv)
    funnel, live = dead_keys(a.without_tests)
    if a.json:
        print(json.dumps(sorted(c.key for c in live), indent=1, ensure_ascii=False))
        return 0
    print(" → ".join(f"{k} {v}" for k, v in funnel.items()))
    for c in sorted(live, key=lambda c: (c.path, c.line)):
        print(f"{c.path}:{c.line} {c.kind} {c.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
