"""A crash is never credited as a judgement — every verification tool has THREE outcomes.

Type: Sub
Uses: .claude/scripts/judgement.py, .claude/scripts/audit_runner.py,
      .claude/scripts/check_guards_are_env_independent.py, .claude/scripts/check_mermaid.py,
      tools/dev/{mutate_guards,reopen_check,arch_benchmark,schema_drift_check,
      nightly_guard_mutation,probe_error_management}.py,
      tools/scale_check_verdicts.sh, tools/schema_drift_cron.sh, tools/prod_introspect.sh
Depends on: bash; stub `docker` / `gh` written on a scratch PATH — nothing reaches a server

R495, class `a-crash-credited-as-a-judgement`. A verification tool read a non-zero exit —
a traceback, a dead ssh, a pytest ERROR, a renderer that will not launch — as its verdict:
a signature HIT on a NameError, a requirement « RÉGRESSION » on a fixture error, a reopening
trigger « franchi » because ssh died, a p50 nobody measured printed « ✅ sous le seuil », a
drift check whose dump failed reported nothing at all. Each test below calls the REAL
function on a crash and requires the third outcome — and, next to it, a real judgement that
must stay a judgement (an assertion that QUOTES a traceback stays a hit).

Every test name carries « crash »: the catalogue signature selects them with `-k crash`.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))

import judgement  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # a @dataclass looks its module up while it is built
    spec.loader.exec_module(mod)
    return mod


ar = _load("audit_runner_r495", ".claude/scripts/audit_runner.py")
mg = _load("mutate_guards_r495", "tools/dev/mutate_guards.py")
rc_mod = _load("reopen_check_r495", "tools/dev/reopen_check.py")
ab = _load("arch_benchmark_r495", "tools/dev/arch_benchmark.py")
sdc = _load("schema_drift_check_r495", "tools/dev/schema_drift_check.py")
ngm = _load("nightly_guard_mutation_r495", "tools/dev/nightly_guard_mutation.py")
pem = _load("probe_error_management_r495", "tools/dev/probe_error_management.py")
cm = _load("check_mermaid_r495", ".claude/scripts/check_mermaid.py")
env_ind = _load("check_guards_env_r495", ".claude/scripts/check_guards_are_env_independent.py")

_TB = "Traceback (most recent call last):\n  File \"x.py\", line 1\nNameError: name 'x' is not defined\n"


def _stub(bin_dir: Path, name: str, body: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / name).write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    (bin_dir / name).chmod(0o755)


# ── audit_runner.run_signature — the catalogue's signatures ─────────────────────────────

def test_a_signature_that_crashes_is_broken_not_a_hit() -> None:
    verdict, _ = ar.run_signature("python3 -c 'import nosuchmodule_r495'")
    assert verdict == ar.BROKEN, "a traceback was credited as the class being HIT"


def test_a_crash_quoted_inside_an_assertion_is_still_a_judgement() -> None:
    """False-positive side: the assertion wins over the traceback it quotes."""
    sig = ("printf 'E   AssertionError: Traceback (most recent call last) seen in log\\n"
           "Traceback (most recent call last):\\n'; exit 1")
    verdict, _ = ar.run_signature(sig)
    assert verdict == ar.HIT


def test_a_bare_false_is_a_hit_not_a_crash() -> None:
    assert ar.run_signature("false")[0] == ar.HIT
    assert ar.run_signature("true")[0] == ar.CLEAN


def test_a_batched_error_or_nameerror_is_a_crash_rerun_individually() -> None:
    out = ("FAILED tests/test_a.py::test_x - assert 1 == 2\n"
           "ERROR tests/test_b.py::test_y - RuntimeError: No database configuration\n"
           "FAILED tests/test_c.py::test_z - NameError: name 'q' is not defined\n")
    targets = {"a": ["tests/test_a.py"], "b": ["tests/test_b.py"], "c": ["tests/test_c.py"],
               "d": ["tests/test_d.py"]}
    results, again = ar._batched_verdicts(out, targets)
    assert results["a"][0] is True, "a real assertion must stay a hit"
    assert sorted(again) == ["b", "c"], f"crashed classes not re-run alone: {again}"
    assert results["d"][0] is False


# ── the shared classifier, read by mutate_guards and arch_benchmark ─────────────────────

def test_a_pytest_crash_is_not_red() -> None:
    assert judgement.classify_pytest(1, "E   NameError: name 'x' is not defined\n") == judgement.CRASH
    assert judgement.classify_pytest(2, "") == judgement.CRASH        # interrupted collection
    assert judgement.classify_pytest(5, "") == judgement.CRASH        # nothing collected
    assert judgement.classify_pytest(1, "E   assert 503 == 200\n" + _TB) == judgement.RED
    assert mg.is_crash("E   KeyError: 'recent'\n")
    assert not mg.is_crash("E   Failed: no figure drawn\n")


def test_an_arch_proof_that_crashes_is_unreadable_not_a_regression() -> None:
    out = ("PASSED tests/test_ok.py::test_ok\n"
           "ERROR tests/test_err.py::test_err - RuntimeError: no db\n"
           "FAILED tests/test_red.py::test_red - AssertionError: wrong\n"
           "FAILED tests/test_crash.py::test_crash - NameError: name 'x' is not defined\n")
    nodes = {"ok": "tests/test_ok.py::test_ok", "err": "tests/test_err.py::test_err",
             "red": "tests/test_red.py::test_red", "crash": "tests/test_crash.py::test_crash",
             "gone": "tests/test_gone.py::test_gone"}
    got = ab.pytest_proofs(1, out, nodes)
    assert got == {"ok": "vert", "err": ab.UNREADABLE, "red": "rouge",
                   "crash": ab.UNREADABLE, "gone": ab.UNREADABLE}
    assert set(ab.pytest_proofs(2, out, nodes).values()) == {ab.UNREADABLE}
    assert ab.verdict("conforme", ab.UNREADABLE) != "RÉGRESSION"
    assert ab.command_proof("python3 -c 'import nosuchmodule_r495'") == ab.UNREADABLE
    assert ab.command_proof("false") == "rouge"


# ── reopen_check._r114 — the scaling triggers read over ssh ─────────────────────────────

def test_a_crashed_scale_check_is_undecidable_not_a_reopening(monkeypatch) -> None:
    """Case (d): ssh died — exit 255, no « ✅ sous le seuil » in stdout. It used to read MET."""
    dead = subprocess.CompletedProcess([], 255, stdout="▶ Déclencheur 1/2\n",
                                       stderr="ssh: connect to host x port 22: Connection refused\n")
    monkeypatch.setattr(rc_mod.subprocess, "run", lambda *a, **k: dead)
    trig = rc_mod.Trigger("R114", "seuils", "here", rc_mod._r114)
    assert trig.run()[0] == rc_mod.UNKNOWN



def _scale_run(monkeypatch, sessions: tuple[str, str], p50: tuple[str, str]) -> str:
    """`_r114` on a real scale_check stdout: both verdict functions, exit 0 (both readable)."""
    monkeypatch.undo()  # the previous call's fake `run` would answer the verdict scripts too
    out = _verdict("sessions_verdict", *sessions).stdout + _verdict("p50_verdict", *p50).stdout
    done = subprocess.CompletedProcess([], 0, stdout=out, stderr="")
    monkeypatch.setattr(rc_mod.subprocess, "run", lambda *a, **k: done)
    return rc_mod._r114()[0]


def test_each_scale_trigger_reopens_on_its_own(monkeypatch) -> None:
    """R496: trigger 2 alone (p50 crossed, sessions under) read NOT_MET — the literal
    `fired` looked for was trigger 1's « ✅ sous le seuil », present whatever p50 said."""
    assert _scale_run(monkeypatch, ("5", "20"), ("350", "200")) == rc_mod.MET
    assert _scale_run(monkeypatch, ("30", "20"), ("120", "200")) == rc_mod.MET
    assert _scale_run(monkeypatch, ("5", "20"), ("120", "200")) == rc_mod.NOT_MET


def _verdict(fn: str, *args: str) -> subprocess.CompletedProcess:
    script = (f'set -euo pipefail\n. "{ROOT}/tools/scale_check_verdicts.sh"\n'
              f'rc=0; {fn} "$@" || rc=$?\necho "rc=$rc"\n')
    return subprocess.run(["bash", "-c", script, "x", *args], capture_output=True, text=True,
                          timeout=30)


def test_an_unmeasured_scale_trigger_is_a_crash_not_under_the_threshold() -> None:
    empty = _verdict("p50_verdict", "", "200")
    assert "rc=2" in empty.stdout and "✅" not in empty.stdout, empty.stdout
    garbage = _verdict("sessions_verdict", "ERROR:", "20")
    assert "rc=2" in garbage.stdout and "✅" not in garbage.stdout, garbage.stdout
    assert "rc=1" in _verdict("p50_verdict", "350", "200").stdout
    ok = _verdict("p50_verdict", "120", "200")
    assert "rc=0" in ok.stdout and "✅ p50 = 120 ms" in ok.stdout


# ── the schema-drift check and its nightly cron ─────────────────────────────────────────

def test_an_empty_schema_dump_is_a_crash_not_a_clean_schema(tmp_path) -> None:
    good = {"col": {"t.a"}, "tbl": {"t"}}
    assert sdc.unreadable_dumps({"p": {"col": set(), "tbl": set()}, "c": good}) == ["p"]
    (tmp_path / "live.tsv").write_text("", encoding="utf-8")
    (tmp_path / "canon.tsv").write_text("t.a\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools/dev/schema_drift_check.py"),
                        str(tmp_path / "live.tsv"), str(tmp_path / "canon.tsv")],
                       capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert r.returncode == 2, f"an empty live dump read as a verdict (exit {r.returncode})"


def _drift_tree(tmp: Path, check_body: str, prod_dump_fails: bool = False) -> dict:
    (tmp / "tools" / "dev").mkdir(parents=True)
    (tmp / "migrations").mkdir()
    (tmp / "init_db.sql").write_text("", encoding="utf-8")
    (tmp / "migrations" / "001.sql").write_text("", encoding="utf-8")
    cron = tmp / "tools" / "schema_drift_cron.sh"
    cron.write_text((ROOT / "tools/schema_drift_cron.sh").read_text(encoding="utf-8"),
                    encoding="utf-8")
    (tmp / "tools" / "dev" / "schema_drift_check.py").write_text(check_body, encoding="utf-8")
    (tmp / "tools" / "notify_schema_drift.py").write_text(
        "import sys, pathlib\npathlib.Path(sys.argv[0]).with_name('NOTIFIED')"
        ".write_text(sys.argv[2], encoding='utf-8')\n", encoding="utf-8")
    fail = 'if [[ "$*" == *postgres_spotify_x*-tAc* ]]; then exit 1; fi\n' if prod_dump_fails else ""
    _stub(tmp / "bin", "docker",
          'if [ "$1" = ps ]; then echo postgres_spotify_x; exit 0; fi\n' + fail
          + 'if [[ "$*" == *-tAc* ]]; then echo t.a; fi\nexit 0\n')
    _stub(tmp / "bin", "sleep", "exit 0\n")
    return {**os.environ, "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}",
            "LOG": str(tmp / "drift.log")}


def test_a_crashed_drift_check_is_broken_not_a_drift(tmp_path) -> None:
    env = _drift_tree(tmp_path, f"import sys\nsys.stderr.write({_TB!r})\nsys.exit(1)\n")
    r = subprocess.run(["bash", str(tmp_path / "tools/schema_drift_cron.sh")], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "BROKEN" in r.stdout and "DRIFT DETECTED" not in r.stdout
    assert (tmp_path / "tools" / "NOTIFIED").is_file(), "a broken check must still mail"


def test_a_failed_prod_dump_is_a_crash_not_silence(tmp_path) -> None:
    env = _drift_tree(tmp_path, "import sys\nsys.exit(0)\n", prod_dump_fails=True)
    r = subprocess.run(["bash", str(tmp_path / "tools/schema_drift_cron.sh")], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "prod dump failed" in r.stdout, r.stdout + r.stderr


def test_a_real_drift_is_mailed_not_lost_to_set_e_like_a_crash(tmp_path) -> None:
    """`OUT=$(…); RC=$?` under `set -e` aborted on the drift itself: no alert, no mail."""
    env = _drift_tree(tmp_path, "print('⚠ schema drift found — 1 column')\nraise SystemExit(1)\n")
    r = subprocess.run(["bash", str(tmp_path / "tools/schema_drift_cron.sh")], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "SCHEMA DRIFT DETECTED" in r.stdout, r.stdout + r.stderr
    assert (tmp_path / "tools" / "NOTIFIED").is_file()


# ── the mermaid renderer, the env-independence replay, the nightly fetch ────────────────

def test_a_renderer_that_cannot_launch_is_a_crash_not_a_bad_diagram() -> None:
    launch = "Error: Failed to launch the browser process!\n"
    assert cm.renderer_unavailable([launch, launch], 2)
    # One launch error out of 3 blocks: only the launch branch can say so — the
    # same-last-line fallback needs every block to fail, and masks it above.
    assert cm.renderer_unavailable([launch], 3)
    same = "Error: spawn ENOENT\n"
    assert cm.renderer_unavailable([same, same, same], 3)
    assert not cm.renderer_unavailable(["Parse error on line 2\n"], 4)
    assert not cm.renderer_unavailable(["Parse error on line 2\n", "Lexical error\n"], 2)


def test_a_suite_that_did_not_run_is_a_crash_not_an_env_dependent_guard() -> None:
    assert env_ind.suite_did_not_run(4, "usage: pytest [options]\n")
    assert env_ind.suite_did_not_run(5, "no tests ran\n")
    assert not env_ind.suite_did_not_run(1, "FAILED tests/test_x.py::t - KeyError\n")
    assert not env_ind.suite_did_not_run(2, "ERROR tests/test_x.py - ImportError\n")


def test_a_failed_artifact_download_is_a_crash_not_a_quiet_night(tmp_path, monkeypatch) -> None:
    assert ngm.download_outcome(1, "no valid artifacts found to download", False) == "none"
    assert ngm.download_outcome(
        1, "no artifact matches any of the names or patterns provided", False) == "none"
    assert ngm.download_outcome(1, "HTTP 401: Bad credentials", False) == "broken"
    assert ngm.download_outcome(0, "", False) == "broken"
    assert ngm.download_outcome(0, "", True) == "ok"
    _stub(tmp_path / "bin", "gh",
          'if [ "$2" = list ]; then echo 42; exit 0; fi\necho "HTTP 401: Bad credentials" >&2; exit 1\n')
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    assert ngm.fetch(tmp_path / "red.log") == 1


def test_an_absent_container_is_a_crash_not_missing_env(tmp_path) -> None:
    _stub(tmp_path / "bin", "docker",
          'if [ "$1" = inspect ]; then echo "Error: No such object" >&2; exit 1; fi\nexit 1\n')
    script = (f'set -euo pipefail\n. "{ROOT}/tools/prod_introspect.sh"\n'
              'run_remote() { bash -c "$*"; }\naudit_env\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}"})
    assert "⊘ conteneur absent ou arrêté" in r.stdout, r.stdout + r.stderr
    assert "FERNET_KEY" not in r.stdout, "a dead container read as « variable missing »"


# ── the error-management probe ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("label, rc, out, want", [
    ("admission", 2, "  ⊘  cid\n       no ticket\n", pem.REFUSED),
    ("admission", 2, "❌ catalogue not found\n", pem.CRASH),
    ("admission", 1, _TB, pem.CRASH),
    ("sweep-verdict", 1, "❌ 1 balayage(s) sans verdict lisible :\n", pem.REFUSED),
    ("sweep-verdict", 1, _TB, pem.CRASH),
    ("health --check", 1, "`x` n'est pas rangé (classes dormantes)\n", pem.REFUSED),
    ("health --check", 1, _TB, pem.CRASH),
    ("catalogue tests", 1, "E   AssertionError: hole counter grew\n", pem.REFUSED),
    ("catalogue tests", 1, "E   ModuleNotFoundError: No module named 'yaml'\n", pem.CRASH),
    ("catalogue tests", 4, "ERROR: file or directory not found\n", pem.CRASH),
    ("admission", 0, "✅\n", pem.GREEN),
])
def test_a_crashed_gate_is_not_a_refusal(label, rc, out, want) -> None:
    assert pem.gate_outcome(label, rc, out) == want


def test_a_probe_with_a_crashed_gate_is_not_refused() -> None:
    assert pem.probe_refused({"admission": pem.REFUSED, "sweep-verdict": pem.GREEN})
    assert not pem.probe_refused({"admission": pem.REFUSED, "health --check": pem.CRASH})
    assert not pem.probe_refused({"admission": pem.CRASH})
    assert pem.hook_refused(2, "🚫 BLOCKED — no sweeper")
    assert not pem.hook_refused(2, "python3: can't open file\n")
    assert pem.commit_refused(1, "🚫 catalogue-sweep —")
    assert not pem.commit_refused(1, "ruff....Failed\n")
