"""The three load alerts take their threshold from history, not from a number (R131).

Type: Test
Uses: docker, prom/prometheus:v2.51.0 (promtool)
Depends on: deploy/prometheus/rules/streamlytics.yml (group `streamlytics-load`),
            deploy/prometheus/rules/streamlytics.test.yml
Persists in: nothing (a temp dir)

R131 waited from 2026-09-17 for 30 days of `daily_ops_metrics` so that a session could
derive three thresholds by hand. The rules now compare each value with the maximum of
the previous 28 days, and stay silent while that history does not exist. This test
plays them in promtool: silent under 28 days, silent at an equal value, firing on a
new maximum.

Mutation record — 2026-10-12: with the history gate (`and on() (count_over_time…)`)
removed from `SessionsHigh`, case 1 fires and the test is red; with `>` turned into
`>=`, the equal-value case fires and the test is red.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_RULES = Path(__file__).resolve().parent.parent / "deploy/prometheus/rules"
_IMAGE = "prom/prometheus:v2.51.0"


def _image_present() -> bool:
    if not shutil.which("docker"):
        return False
    r = subprocess.run(["docker", "image", "inspect", _IMAGE], capture_output=True)
    return r.returncode == 0


def test_the_load_group_writes_no_threshold() -> None:
    groups = yaml.safe_load((_RULES / "streamlytics.yml").read_text())["groups"]
    load = next(g for g in groups if g["name"] == "streamlytics-load")
    assert {r["alert"] for r in load["rules"]} == {"SessionsHigh", "ErrorRateHigh",
                                                   "LogErrorBurst"}
    for rule in load["rules"]:
        assert "max_over_time(" in rule["expr"], rule["alert"]
        assert "offset 28d" in rule["expr"], f"{rule['alert']}: no history gate"


@pytest.mark.skipif(not _image_present(), reason=f"{_IMAGE} not pulled — promtool absent")
def test_promtool_proves_silence_equality_and_record(tmp_path: Path) -> None:
    groups = yaml.safe_load((_RULES / "streamlytics.yml").read_text())["groups"]
    load = dict(next(g for g in groups if g["name"] == "streamlytics-load"), interval="1h")
    # promtool compares annotations exactly; their presence is ADR-011's test, not this one.
    load["rules"] = [{k: v for k, v in r.items() if k != "annotations"} for r in load["rules"]]
    (tmp_path / "load-only.yml").write_text(yaml.safe_dump({"groups": [load]},
                                                           allow_unicode=True))
    shutil.copy(_RULES / "streamlytics.test.yml", tmp_path / "streamlytics.test.yml")
    tmp_path.chmod(0o755)
    r = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "promtool", "-v", f"{tmp_path}:/r:ro",
         "-w", "/r", _IMAGE, "test", "rules", "streamlytics.test.yml"],
        capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
