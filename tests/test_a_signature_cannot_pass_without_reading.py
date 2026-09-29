"""A catalogue signature cannot pass without its pattern having been evaluated on content.

Type: Sub
Uses: .claude/dev-docs/error-classes.md (every `- signature:`), the repository tree
Depends on: nothing — the signatures are parsed with shlex, never executed

R324 (2026-09-29), found while dating `seen_red` on fabricated defects — two signatures were
green FOR EVER, by two different routes to the same place:
  * `make-fail-late` used `grep -E "^\\t…"`: GNU ERE reads `\\t` as a literal `t`, so no
    recipe line (they start with a TAB) could match;
  * `operator-guidance-phantom-or-wrong-auth` named `src/dashboard/views/credentials.py`,
    which became a package: grep exits 2 on a missing operand and `! <2>` is 0.
Both looked right when run by hand in this workstation's shell, whose `grep` is rewritten by
an RTK hook — the property is checked here on the TEXT, which no shell rewrites.

Mutation record (2026-09-29): seen red with `credentials/` put back to `credentials.py` in
the catalogue, and with `[[:space:]]+` put back to `\\t` in `make-fail-late`. The first draft
split pipelines on `|` and passed both mutations — see `_grep_segments`.
"""
import glob
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / ".claude/dev-docs/error-classes.md"
_BAD_ESCAPE = re.compile(r"\\[tdDn]")      # not ERE/BRE escapes: `\t` is a `t`, `\d` a `d`


def signatures(text: str) -> dict[str, str]:
    out, cid = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cid = line[3:].strip()
        m = re.match(r"^- signature: `(.+)`\s*$", line)
        if m and cid:
            out[cid] = m.group(1)
    return out


def _grep_segments(sig: str) -> list[list[str]]:
    """The `grep` commands of a pipeline, split by the SHELL's rules: a first draft split
    the text on `|` and cut every quoted alternation in two — the guard then saw no grep
    at all and passed both of its mutations."""
    lex = shlex.shlex(sig, posix=True, punctuation_chars="|&;()")
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return []
    segs, cur = [], []
    for tok in tokens + [";"]:
        if set(tok) <= set("|&;()"):
            if cur and cur[0] == "grep":
                segs.append(cur)
            cur = []
        elif tok != "!":
            cur.append(tok)
    return segs


def problems(sig: str, root: Path = ROOT) -> list[str]:
    found = []
    for tok in _grep_segments(sig):
        opts = [t for t in tok[1:] if t.startswith("-")]
        rest = [t for t in tok[1:] if not t.startswith("-")]
        if "-P" in "".join(opts) or not rest:
            continue
        pattern, operands = rest[0], rest[1:]
        if _BAD_ESCAPE.search(pattern):
            found.append(f"escape GNU grep does not know in {pattern!r}")
        for op in operands:
            if op.startswith(("$", "~")) or "=" in op:
                continue
            hits = glob.glob(str(root / op)) if any(c in op for c in "*?[") else \
                [op] if (root / op).exists() else []
            if not hits:
                found.append(f"operand {op!r} does not exist — grep exits 2, `!` reads 0")
    return found


def test_no_catalogue_signature_can_pass_without_reading() -> None:
    bad = {cid: p for cid, sig in signatures(CATALOGUE.read_text(encoding="utf-8")).items()
           if (p := problems(sig))}
    assert not bad, f"signatures that can pass without evaluating their pattern: {bad}"


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    (tmp_path / "Makefile").write_text("up:\n\tdocker ps\n")
    assert problems('! grep -nE "^\\t.*docker" Makefile', tmp_path)
    assert problems("! grep -rn x src/gone.py Makefile", tmp_path) == [
        "operand 'src/gone.py' does not exist — grep exits 2, `!` reads 0"]
    assert problems('! grep -nE "^[[:space:]]+.*docker" Makefile', tmp_path) == []
    assert problems("cat f | grep -v x", tmp_path) == []          # stdin: no operand
    quoted = '! grep -rnE "a|b (c|d)" src/gone.py'                  # `|` inside the quotes
    assert problems(quoted, tmp_path) == [
        "operand 'src/gone.py' does not exist — grep exits 2, `!` reads 0"]
    assert len(signatures(CATALOGUE.read_text(encoding="utf-8"))) > 300
