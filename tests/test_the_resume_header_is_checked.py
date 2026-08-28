"""Guard: the file `/resume` reads first cannot contradict itself or bloat.

Type: Utility
Uses: pathlib, re
Triggers: pytest
Persists in: nothing

Error classes `resume-header-claims-what-the-index-denies` and
`state-file-accumulates-its-own-history`.

Measured 2026-08-28, both in the same file on the same morning.

**The header named three closed tasks.** `## 🔖 REPRISE` opened with "ne restent que des
gestes humains : R1, R13, R17, R54, R55". R13 closed 22 Aug, R17 on the 21st, R55 on the
26th. The body of the file already said so — the `🙋` table listed two rows, not five.
Only the header had not followed, and it is the one part `/resume` copies out without
re-reading.

**And 72 % of the file was history.** 88 KB, ~22 600 tokens read at every session start,
holding seven dated REPRISE/Historique blocks going back to 21 August — **two of which
both carried "à lire EN PREMIER au `/resume`"**, which cannot be true of both — plus two
sections duplicated word for word.

## Why an anchor, and not prose matching

The first defect is not detectable in prose. "Ne restent que R1, R13, R17" and "R13 est
close" are the same tokens in a different claim, and a guard that greps ids either fires
on every honest retrospective sentence or misses the defect entirely — the trap this repo
has walked into six times (`a-guards-scope-is-the-defect`).

So the claim is given a structured form instead:

    <!-- reprise: open=R1 -->

one line, the same assertion as the paragraph, in a shape that can be compared to the two
index tables. **A prose claim cannot be verified; an anchored one can.** The anchor is
cheap to update and impossible to leave stale silently — which is the whole difference.
"""
from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
ACTIVE = REPO / ".claude" / "dev-docs" / "roadmap" / "checklist.md"

_ANCHOR = re.compile(r"^<!--\s*reprise:\s*open=([^>]*?)\s*-->\s*$", re.M)
_ROW = re.compile(r"^\| (R\d+) \|", re.M)
_ACTIONABLE_H = "## 📋 Tâches ouvertes"
_WAITING_H = "## 🙋 En attente de toi"

# 50 KB is roughly 12 000 tokens — comfortably above today's 34 KB and far below the
# 88 KB that triggered this guard. A ceiling, not a target: it exists to make the next
# accumulation fail loudly rather than to shave bytes.
_MAX_BYTES = 50 * 1024


def _text() -> str:
    return ACTIVE.read_text(encoding="utf-8")


def _section_ids(heading: str) -> set[str]:
    text = _text()
    m0 = re.search(rf"^{re.escape(heading)}", text, re.M)
    assert m0, f"heading {heading!r} not found at the start of a line"
    rest = text[m0.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return set(_ROW.findall(rest[: nxt.start()] if nxt else rest))


def _open_ids() -> set[str]:
    return _section_ids(_ACTIONABLE_H) | _section_ids(_WAITING_H)


# ── The header must not claim what the index denies ──────────────────────────

def test_the_anchor_exists():
    """Without it there is nothing to check, and the prose goes back to being trusted."""
    assert _ANCHOR.search(_text()), (
        "the `<!-- reprise: open=… -->` line is gone from checklist.md. It is the only "
        "machine-readable form of what the REPRISE paragraph asserts; removing it puts "
        "the header back to being an unverifiable claim, which is how R13, R17 and R55 "
        "survived in it for up to a week after closing."
    )


def test_the_anchor_matches_the_open_index():
    m = _ANCHOR.search(_text())
    assert m, "anchor missing (see the test above)"
    claimed = {i.strip() for i in m.group(1).split(",") if i.strip()}
    actual = _open_ids()
    assert claimed == actual, (
        f"the REPRISE header claims {sorted(claimed) or '∅'} is open; the index tables "
        f"say {sorted(actual) or '∅'}. Extra in the header: "
        f"{sorted(claimed - actual) or '∅'} — closed work presented as remaining. "
        f"Missing from it: {sorted(actual - claimed) or '∅'} — open work the first "
        "thing read at /resume does not mention."
    )


def test_the_index_is_not_empty_of_both_sections():
    """Non-vacuity: two empty tables would make the comparison above trivially true."""
    text = _text()
    assert _ACTIONABLE_H in text and _WAITING_H in text
    assert _ROW.search(text), (
        "no `| Rxx |` row anywhere in checklist.md. Either every task is genuinely "
        "gone — delete this test — or the row pattern stopped matching and the "
        "comparison above is passing on two empty sets."
    )


# ── The state file must not accumulate its own history ───────────────────────

def test_only_one_resume_block():
    """Seven blocks, two both saying « à lire EN PREMIER ». Both cannot be true."""
    blocks = re.findall(r"^## 🔖 REPRISE.*$", _text(), re.M)
    assert len(blocks) == 1, (
        f"{len(blocks)} REPRISE blocks in checklist.md:\n  "
        + "\n  ".join(b[:90] for b in blocks)
        + "\nOne is the current state; the others are archive wearing its clothes. "
        "Move them to archive.md — moving, never deleting "
        "(tests/test_roadmap_two_files.py fails if the sum shrinks)."
    )


def test_no_history_block_remains_in_the_active_file():
    stale = re.findall(r"^## 🔖 Historique.*$", _text(), re.M)
    assert not stale, (
        f"{len(stale)} « Historique » block(s) still in the ACTIVE roadmap:\n  "
        + "\n  ".join(s[:90] for s in stale)
        + "\nA block explicitly labelled history belongs in archive.md by its own name."
    )


def test_the_active_file_stays_readable_in_one_sitting():
    size = ACTIVE.stat().st_size
    assert size <= _MAX_BYTES, (
        f"checklist.md is {size // 1024} KB (~{size // 4} tokens) — over the "
        f"{_MAX_BYTES // 1024} KB ceiling. This is the file /resume reads BEFORE "
        "anything else, every session, so weight here is paid on every start. On "
        "2026-08-28 it reached 88 KB of which 72 % was dated history. Rotate the "
        "oldest sections into archive.md rather than raising this number."
    )
