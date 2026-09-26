"""The roadmap-discipline probe counts what it claims, and says what it cannot see (R197).

Type: Sub
Uses: tools/dev/roadmap_discipline.py, tools/dev/require_roadmap_id.py
Depends on: git (a throw-away repository in tmp_path)
Persists in: nothing

Owner, 2026-09-26: « intégrer des sondes de mesures pour monitorer combien de tâches de dev se
font sans inscription en roadmap ». Every category is FABRICATED here and must land in its
counter; the critic half without transcripts is `None`, never 0 (code-critic, same day).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools" / "dev"))
import roadmap_discipline as probe  # noqa: E402

CHK = ".claude/dev-docs/roadmap/checklist.md"


def _text(path: Path) -> str:
    """A Makefile or a workflow — this file never reads Python source."""
    with open(path, encoding="utf-8") as fh:
        return fh.read()
_HEAD = "# Roadmap\n\n## 📋 Tâches ouvertes\n\n| id | Tâche | P | M |\n|---|---|---|---|\n"


def _commit(repo: Path, files: dict[str, str], message: str) -> None:
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--no-verify", "-m", message], check=True)


def _repo(tmp: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    import shutil
    (tmp / "tools/dev").mkdir(parents=True)
    shutil.copy(_ROOT / "tools/dev/require_roadmap_id.py", tmp / "tools/dev/")
    rows = ("| R10 | fait <!-- critic: non — texte --> | P3 | t |\n"
            "| R11 | risqué <!-- critic: requis --> | P3 | t |\n"
            "| R12 | sans décision | P3 | t |\n")
    _commit(tmp, {CHK: _HEAD + rows},
            "Roadmap : R10 R11 R12 inscrites (et le garde)")
    _commit(tmp, {"src/a.py": "a = 1\n"}, "R10 : ok")                 # ok
    _commit(tmp, {"src/b.py": "b = 1\n"}, "sans identifiant")         # bypass: no_id
    _commit(tmp, {"src/c.py": "c = 1\n"}, "R99 : jamais inscrite")    # bypass: not_open
    _commit(tmp, {"src/d.py": "d = 1\n"}, "R12 : ligne muette")       # bypass: undecided
    _commit(tmp, {"src/e.py": "e = 1\n"}, "R11 : a besoin d'un critic")
    _commit(tmp, {CHK: _HEAD + "| R10 | fait <!-- critic: non — t --> | P3 | t |\n"},
            "Roadmap : sans code")                                    # not product: ignored
    return tmp


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "r")
    report = probe.measure(days=30, root=repo, calls=None)
    g = report["git"]
    assert g["product"] == 5 and g["ok"] == 2, g
    assert g["bypass"] == 3, f"the three commits past the gate were not counted: {g}"
    assert {b.split("(")[-1].rstrip(")") for b in g["bypasses"]} == {"no_id", "not_open",
                                                                       "undecided"}
    assert report["critic"]["with_critic"] is None, (
        "without transcripts the critic half must say « not measured », never a number")
    assert report["critic"]["requis"] == 1
    assert probe.failing(report), "a bypass did not make the probe fail"


def test_the_critic_half_counts_a_critic_only_before_the_code(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "r")
    rows = probe.commits(30, repo)
    ts = max(c["ts"] for c in rows)
    before = [{"ts": ts - 100, "text": '{"prompt": "review R11 design"}'}]
    after = [{"ts": ts + 100, "text": '{"prompt": "review R11 design"}'}]
    other = [{"ts": ts - 100, "text": '{"prompt": "review R110 and R1"}'}]
    assert probe.critic_half(rows, before)["without_critic"] == 0
    assert probe.critic_half(rows, after)["missing"] == ["R11"], "a critic AFTER the code counted"
    assert probe.critic_half(rows, other)["missing"] == ["R11"], "R110 was read as R11"


def test_a_commit_is_judged_by_the_rules_of_its_parent() -> None:
    """Before R198 an undecided row was the norm: the baseline must not call it a fault."""
    chk = _HEAD + "| R5 | x | P3 | t |\n"
    assert probe.classify(["src/x.py"], "R5 : x", chk, 1, gated=True,
                          critic_gated=False) == "ok"
    assert probe.classify(["src/x.py"], "R5 : x", chk, 1, gated=True) == "bypass:undecided"
    assert probe.classify(["src/x.py"], "x", chk, 1, gated=False) == "no_id"
    assert probe.classify(["tests/t.py"], "x", chk, 1, gated=True) is None


def test_a_stale_open_row_fails_the_probe() -> None:
    report = {"git": {"bypass": 0, "bypasses": []}, "open_rows_age_days": {"R1": 20},
              "stale": ["R1"]}
    assert probe.failing(report) and "R1 (20 j)" in probe.failing(report)[0]


def test_the_probe_is_wired_where_it_is_read() -> None:
    """A probe nothing runs is a note: make target, night-status, nightly job + its mail
    line, the daily recap."""
    mk = _text(_ROOT / "Makefile")
    assert "roadmap-discipline:" in mk and "roadmap_discipline.py" in mk
    night = mk[mk.index("\nnight-status:"):].split("\n\n")[0]
    assert "roadmap_discipline.py" in night or "roadmap-discipline" in night, (
        "`make night-status` does not show the discipline")
    wf = yaml.safe_load(_text(_ROOT / ".github/workflows/security-nightly.yml"))
    assert "dev-discipline" in wf["jobs"], "no nightly job"
    assert "dev-discipline" in wf["jobs"]["notify"]["needs"], "the nightly red reaches nobody"
    import nightly_verdict
    body = nightly_verdict.verdict({"dev-discipline": {"outputs": {"outcome": "failure"}}})
    assert body and "make roadmap-discipline" in body, (
        "a red dev-discipline job mails nothing that says what to do")
    # The recap carrying the numbers is proven by behaviour, below (build → « Roadmap »).


def test_the_recap_mail_says_red_on_a_bypass_and_unreadable_when_unmeasured() -> None:
    import datetime as dt
    import github_nightly_recap as recap
    bad = {"git": {"ok": 2, "product": 5, "bypass": 3, "bypasses": ["abc1234 x (no_id)"]},
           "open_rows_age_days": {"R1": 1}, "stale": []}
    html_bad, red = recap.discipline_section(bad)
    assert red and "abc1234" in html_bad and "🔴" in html_bad
    html_none, red_none = recap.discipline_section(None)
    assert not red_none and "illisible" in html_none, "an unreadable probe read as a verdict"
    subject, body, red_all = recap.build({}, {"state": "green", "detail": "HTTP 200"},
                                         dt.datetime(2026, 9, 26), bad)
    assert red_all and "Roadmap" in body, "a bypass did not turn the recap red"


def test_an_old_open_row_is_found_stale_in_a_real_history(tmp_path: Path) -> None:
    """The age comes from the first commit carrying the row — here dated 30 days ago."""
    import os
    import time
    repo = tmp_path / "old"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".claude/dev-docs/roadmap").mkdir(parents=True)
    (repo / CHK).write_text(_HEAD + "| R7 | ancienne <!-- critic: non — t --> | P3 | t |\n",
                            encoding="utf-8")
    old = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 30 * 86400))
    env = {**os.environ, "GIT_AUTHOR_DATE": old, "GIT_COMMITTER_DATE": old}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--no-verify", "-m", "Roadmap : R7"], check=True, env=env)
    report = probe.measure(days=60, root=repo, calls=None)
    assert report["open_rows_age_days"]["R7"] >= 29 and report["stale"] == ["R7"], report
    assert probe.failing(report), "a 30-day-old open row did not fail the probe"
