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
        assert (_ROOT / rel).is_file(), f"{rel} no longer exists — drop it from SEEN_RED"
        assert re.match(r"\d{4}-\d{2}-\d{2} — .{20,}→", why), (
            f"{rel}: « {why} » — a hand-seen red names the date, the mutation and its reds")
