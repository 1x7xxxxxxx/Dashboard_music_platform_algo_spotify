"""`classify` reads the log once, and still says what the per-fingerprint passes said (R700).

Type: Sub
Uses: tools/dev/defect_log.py, .claude/sessions/defects.jsonl when this machine has one
Depends on: nothing — the real log is gitignored, so the synthetic one carries the guard in CI
Persists in: nothing

Baseline T382/DK-12: SessionStart spent 3.2 s of its 3.9 s in `classify`, because `_closers` and
`_answer` walked every event for each of 672 fingerprints (1.6 M `_covers` calls). `_closers_oracle`
below IS that walk, kept as the definition of the right answer.
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import defect_log as dl  # noqa: E402

BUDGET_S = 0.4  # measured 0.05 s indexed, 1 s for the quadratic walk on the same size


def _closers_oracle(fp: str, seen: list[dict], events: list[dict], greens: list,
                    touched: dict[str, str]) -> list[tuple[str, str, str]]:
    kind = seen[0]["kind"]
    out = [(e["ts"], e["session"], "closed") for e in events
           if e["kind"] == "closed" and e["fingerprint"] == fp]
    if kind == "test_red":
        node = fp.removeprefix("test:").split("::", 1)[0]
        out += [(g[0], g[1], "green") for g in greens if not g[2] or node in g[2]]
    elif kind == "ci_step":
        out += [(g[0], g[1], "green") for g in greens if g[1].startswith("ci:")]
    elif kind == "cron_red":
        out += [(e["ts"], e["session"], "green") for e in events
                if e["kind"] == "cron_ok" and e["fingerprint"] == fp]
    elif kind == "traceback" and touched.get(fp.partition("@")[2], "") > seen[-1]["ts"]:
        fixed_at = touched[fp.partition("@")[2]]
        out += [(g[0], g[1], "fixed") for g in greens
                if g[1].startswith("ci:") and g[0] > fixed_at]
    return sorted(out)


def _oracle_rows(events: list[dict], touched: dict[str, str]) -> dict[str, tuple]:
    """fingerprint → (closers, latest ticket), each read by walking the whole log."""
    greens = dl._greens(events)
    reds: dict[str, list[dict]] = {}
    for e in events:
        if e["kind"] in dl.RED_KINDS:
            reds.setdefault(e["fingerprint"], []).append(e)
    return {fp: (_closers_oracle(fp, seen, events, greens, touched),
                 [e for e in events if e["kind"] == "ticket" and e["fingerprint"] == fp])
            for fp, seen in reds.items()}


def _log(fingerprints: int, greens: int, seed: int = 7) -> tuple[list[dict], dict[str, str]]:
    """Every event kind `classify` reads, on a log the size of the real one."""
    rng = random.Random(seed)

    def ts() -> str:
        return f"2026-{rng.randint(9, 11):02d}-{rng.randint(10, 28):02d}T10:00:00.000+00:00"

    def event(kind: str, fp: str, **kw: object) -> dict:
        return {"kind": kind, "fingerprint": fp, "ts": ts(), "excerpt": "x",
                "session": rng.choice(("s1", "s2", "ci:1", "ci:2")), **kw}

    files = [f"tests/test_{i}.py" for i in range(60)]
    prints = [rng.choice((f"test:{rng.choice(files)}::t{i}", f"cron:job{i}:step",
                          f"ci-step:job/{i}", f"ValueError@src/m{i}.py"))
              for i in range(fingerprints)]
    kinds = {"te": "test_red", "cr": "cron_red", "ci": "ci_step", "Va": "traceback"}
    events = [event(kinds[fp[:2]], fp, tree=rng.choice(("clean", "dirty")))
              for fp in prints for _ in range(rng.randint(1, 3))]
    events += [event("test_green", "green", scope=rng.choice(("files", "files", "suite")),
                     files=rng.sample(files, rng.randint(1, 3)) if rng.random() < .8 else [])
               for _ in range(greens)]
    for fp in prints:
        if rng.random() < .3:
            events.append(event(rng.choice(("closed", "cron_ok")), fp))
        if rng.random() < .3:
            events.append(event("ticket", fp, verdict="distinct"))
    touched = {f"src/m{i}.py": ts() for i in range(fingerprints) if rng.random() < .5}
    return sorted(events, key=lambda e: e["ts"]), touched


def _assert_same_answers(events: list[dict], touched: dict[str, str]) -> None:
    idx = dl._index(events)
    rows = {r["fingerprint"]: r for r in dl.classify(events, touched)}
    oracle = _oracle_rows(events, touched)
    assert rows.keys() == oracle.keys()
    for fp, (closers, tickets) in oracle.items():
        seen = [e for e in events if e["kind"] in dl.RED_KINDS and e["fingerprint"] == fp]
        assert dl._closers(fp, seen, idx, touched) == closers, fp
        assert list(idx.marks.get(("ticket", fp), ())) == tickets, fp


def test_the_index_closes_what_the_full_walk_closes() -> None:
    _assert_same_answers(*_log(300, 800))


def test_the_real_log_reads_the_same() -> None:
    events = dl.load()
    if not events:
        pytest.skip("no local defect log (gitignored): the synthetic log carries the guard")
    _assert_same_answers(events, dl.touched_files(events))


def test_seven_hundred_fingerprints_cost_no_session_start() -> None:
    events, touched = _log(700, 2500)
    best = min(_timed(events, touched) for _ in range(3))
    assert best < BUDGET_S, f"classify took {best:.2f} s on ~700 fingerprints"


def _timed(events: list[dict], touched: dict[str, str]) -> float:
    start = time.perf_counter()
    dl.classify(events, touched)
    return time.perf_counter() - start
