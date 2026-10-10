"""Rule 15ter runs every night: a new guard that no mutation turns red is reported.

Type: Sub
Uses: tools/dev/nightly_guard_mutation.py (verdict), .github/workflows/security-nightly.yml
Depends on: nothing — the verdict is pure
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ngm", _ROOT / "tools/dev/nightly_guard_mutation.py")
ngm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ngm)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Green on every mutation, or red before any, is a suspicion; a red mutation and
    'nothing to mutate' (a guard that fabricates its own defect) are not."""
    assert ngm.verdict({"aucune": 4}), "green on all 4 mutations must be reported"
    assert ngm.verdict({"epuise": 6})
    assert ngm.verdict({"skipped": "…"})
    assert ngm.verdict({"source": "x.py", "cible": "f", "ligne": 3, "essais": 1}) is None
    assert ngm.verdict({"aucune": 0}) is None, "no applicable site proves nothing either way"


def test_the_nightly_runs_it_with_a_database_and_mails_it() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["guard-mutation"]
    assert "nightly_guard_mutation.py" in str(job["steps"])
    assert "postgres" in job.get("services", {}), "a DB guard would read as blind without it"
    assert "guard-mutation" in wf["jobs"]["notify"]["needs"]


def test_a_self_proving_guard_is_credited_and_a_plain_one_is_not(tmp_path) -> None:
    """R238: six guards that all bite were mailed as suspects — three prove themselves."""
    proving = tmp_path / "test_p.py"
    proving.write_text("def test_the_detector_sees_the_defect_it_is_written_for():\n    pass\n")
    plain = tmp_path / "test_q.py"
    plain.write_text("def test_something():\n    '''test_the_detector_sees'''\n")
    assert ngm.self_proving(proving)
    assert not ngm.self_proving(plain), "a docstring naming it is not the test"


def test_every_hand_seen_red_names_its_guard_its_date_and_its_mutation() -> None:
    import re
    for rel, why in ngm.SEEN_RED.items():
        if rel.startswith("make "):                 # a `cmd:` proof (R412) — its target must exist
            target = rel.split()[1]
            assert re.search(rf"^{re.escape(target)}:", (_ROOT / "Makefile").read_text(),
                             re.M), f"`{rel}`: no such make target — drop it from SEEN_RED"
        else:
            assert (_ROOT / rel).is_file(), f"{rel} no longer exists — drop it from SEEN_RED"
        assert re.match(r"\d{4}-\d{2}-\d{2} — .{20,}→", why), (
            f"{rel}: « {why} » — a hand-seen red names the date, the mutation and its reds")


# ── R360 / REQ-HARN-19 — the job dates the reds it sees ──────────────────────────────
_RED = {"source": "src/x.py", "cible": "f", "ligne": 3, "essais": 1}


def test_a_red_mutation_is_written_dated_with_its_mutation_and_a_green_one_is_not(tmp_path) -> None:
    log = tmp_path / "reds.jsonl"
    assert not ngm.record_red("tests/test_g.py", {"aucune": 4}, "2026-10-04", log)
    assert not log.exists(), "a guard nothing turned red must leave no dated record"
    assert ngm.record_red("tests/test_g.py", _RED, "2026-10-04", log)
    assert ngm.record_red("tests/test_g.py", {**_RED, "ligne": 9}, "2026-10-05", log)
    log.write_text(log.read_text() + "not json\n{\"guard\": \"tests/test_h.py\"}\n")
    seen = ngm.reds_seen(log)
    assert set(seen) == {"tests/test_g.py"}, "an undated or malformed line is not a red"
    assert seen["tests/test_g.py"]["date"] == "2026-10-05"
    assert (seen["tests/test_g.py"]["source"], seen["tests/test_g.py"]["line"]) == ("src/x.py", 9)


def test_the_self_proving_backlog_rotates_and_drops_what_was_seen_red(tmp_path) -> None:
    from datetime import date
    (tmp_path / "tests").mkdir()
    for n in "abc":
        (tmp_path / f"tests/test_{n}.py").write_text("")
    cat = "".join(f"- seen_red: self-proving (tests/test_{n}.py::t) — x\n" for n in "abcz")
    backlog = ngm.self_proving_backlog(cat, {"tests/test_b.py": {}}, tmp_path)
    assert backlog == ["tests/test_a.py", "tests/test_c.py"], "seen red, or missing, leaves it"
    nights = {tuple(ngm.tonight(backlog, date(2026, 10, d), 1)) for d in (4, 5)}
    assert len(nights) == 2, "an empty CI log must not mutate the same guard every night"


def test_a_self_proving_class_counts_as_dated_only_once_seen_red() -> None:
    spec = importlib.util.spec_from_file_location("ech", _ROOT / "tools/dev/error_class_health.py")
    ech = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ech)
    classes = {
        "a": {"seen_red": "self-proving", "seen_red_guard": "tests/test_a.py"},
        "b": {"seen_red": "self-proving", "seen_red_guard": "tests/test_b.py"},
        "c": {"seen_red": "2026-09-18", "seen_red_guard": None},
    }
    m = ech.seen_red_by_mutation(classes, {"tests/test_a.py": {"date": "2026-10-04"}})
    assert (m["self_proving"], m["self_proving_seen_red_by_mutation"], m["hand_dated"]) == (2, 1, 1)
    assert m["last_red"] == "2026-10-04"


def test_the_nightly_keeps_its_dated_reds() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    keep = [s for s in wf["jobs"]["guard-mutation"]["steps"] if "upload-artifact" in str(s.get("uses", ""))]
    assert keep and keep[0]["with"]["name"] == "guard-red-log"
    assert keep[0]["with"]["path"].endswith(ngm.RED_LOG.name)


# R493 — three sound guards were mailed as suspects two nights running. Mutating their
# real defect by hand turned each one red; the harness had been mutating views they never import.
mg = ngm.mg


def test_importing_one_view_points_the_harness_at_that_view_only(tmp_path) -> None:
    guard = tmp_path / "test_g.py"
    guard.write_text("from src.dashboard.views import soundcloud as sc\n")
    assert mg.sources_read(guard) == [_ROOT / "src/dashboard/views/soundcloud.py"]


def test_a_crash_is_not_credited_as_a_judgement() -> None:
    """A renamed column fails every call: the line ran, nothing was judged."""
    assert mg.is_crash("E   KeyError: 'recent'\n")
    assert mg.is_crash("E   NameError: name 'x_MUTE' is not defined\n")
    assert mg.is_crash("log: AssertionError mentioned in passing\nE   KeyError: 'x'\n")
    # pytest's rewritten assert prints no « AssertionError » — still a judgement
    assert not mg.is_crash("E   assert [1000, 400, 100] == [100, 400, 1000]\n")
    assert not mg.is_crash("E   AssertionError: l'indice n'a pas ses propres barres\n")
    assert not mg.is_crash("E   Failed: no figure drawn\n")


def test_a_suspect_names_what_it_tried() -> None:
    result = {"epuise": 2, "tried": ["a.py:3 `x`", "a.py:9 `y`"], "crashes": ["a.py:9 `y`"]}
    assert ngm.verdict(result)
    lines = ngm.attempts(result)
    assert len(lines) == 2 and "a.py:3 `x`" in lines[0] and "vert" in lines[0]
    assert "plantage" in lines[1]
