"""Guard: the daily production probe must have actually run.

Type: Utility
Uses: requests, the GitHub Actions API (GITHUB_TOKEN, provided automatically in CI)
Triggers: pytest — active only when GITHUB_TOKEN is present, i.e. inside CI
Persists in: nothing

Error class `the-watcher-is-not-watched`.

Measured 2026-08-28. `.github/workflows/prod-health.yml` is scheduled at 06:00 UTC
daily and had held that slot within half an hour for 38 runs — until the gap of 26→27
August, which stretched to **34.6 h**: a whole scheduled slot silently dropped, then a
run at 17:07 instead of 06:00. Nothing anywhere noticed, and nothing would have.

(The first draft of this file said "thirty hours since the last run" at the moment of
writing. That was arithmetic, not measurement: 17:07 → 12:10 is 19 h. The real anomaly
is the 34.6 h gap the day before, and it only appeared once the whole distribution was
pulled. Hence the calibration below rather than a number chosen by feel.)

That workflow carries the sixteen tests of `test_prod_health.py`, and they run **there
and nowhere else**: they are the only surface that looks at production the way a real
client does, THROUGH Cloudflare. Every other check in this repo runs on the box and is
structurally blind to edge, cert, DNS and routing regressions — the 2026-06-14 Bot Fight
Mode 403 on the Stripe webhook is the case that proved it.

So a silent scheduler here is not a missing green tick. It is sixteen probes that stop
existing, on the one layer nothing else covers. Exactly the shape migration 073 exists
for, one level up: **the silence of a monitor IS the incident.**

## Why here, and not another cron

A second scheduled workflow watching the first would share the failure mode being
watched. CI, by contrast, runs on every push — a trigger that does not depend on
GitHub's cron at all — and `GITHUB_TOKEN` is injected there for free, so this costs no
new credential and opens no new surface.

Outside CI it skips loudly rather than pretending: with no token there is no question to
ask, and inventing an answer would be worse than none.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.real_http

_TOKEN = os.getenv("GITHUB_TOKEN")
_REPO = os.getenv("GITHUB_REPOSITORY", "1x7xxxxxxx/Dashboard_music_platform_algo_spotify")
_WORKFLOW = "prod-health.yml"

# Calibrated on the real distribution, not on instinct — 38 scheduled runs between
# 21 July and 27 August:
#
#     min 22.7 h · median 24.0 h · second-largest gap 25.4 h · max 34.6 h
#
# The first number written here was 36 h, and it would have fired **zero times on
# thirty-seven gaps** — a ceiling above the worst thing that ever happened is not a
# ceiling. 30 h fires exactly once, on the single real anomaly, keeping 4.6 h of margin
# over the second-largest gap so ordinary best-effort cron drift stays quiet.
_DEFAULT_MAX_AGE_H = 30


def resolve_ceiling(raw: str | None) -> int:
    """Le plafond en heures, lu à l'appel. Toute valeur douteuse retombe sur le défaut.

    La borne haute (48 h) n'est pas décorative : sans elle, `PROD_HEALTH_MAX_AGE_H=9999`
    désactiverait le garde en passant, et une variable d'environnement qui peut éteindre
    un garde par mégarde est précisément ce que ce fichier surveille un cran plus haut.
    """
    try:
        value = int(str(raw or "").strip())
    except ValueError:
        return _DEFAULT_MAX_AGE_H
    return value if 1 <= value <= 48 else _DEFAULT_MAX_AGE_H


_MAX_AGE_H = resolve_ceiling(os.getenv("PROD_HEALTH_MAX_AGE_H"))

# The measured reality, pinned so the calibration above can be re-checked rather than
# believed. Deliberately the DATA and not the constant: a test that asserts
# `_MAX_AGE_H == 30` restates the code, and would have been just as green at 36.
_MEASURED_GAPS_H = {"median": 24.0, "second_largest": 25.4, "max": 34.6, "samples": 37}


@pytest.mark.skipif(not _TOKEN, reason="no GITHUB_TOKEN — this question only exists in CI")
def test_the_daily_production_probe_ran_recently():
    import requests

    r = requests.get(
        f"https://api.github.com/repos/{_REPO}/actions/workflows/{_WORKFLOW}/runs",
        headers={"Authorization": f"Bearer {_TOKEN}",
                 "Accept": "application/vnd.github+json"},
        params={"per_page": 10}, timeout=20,
    )
    if r.status_code == 404:
        pytest.skip(f"{_WORKFLOW} not found in {_REPO} (fork, or the file was renamed)")
    assert r.status_code == 200, f"GitHub API returned {r.status_code}: {r.text[:200]}"

    runs = [x for x in r.json().get("workflow_runs", []) if x.get("status") == "completed"]
    assert runs, (
        f"{_WORKFLOW} has no completed run at all. The only external, through-Cloudflare "
        "view of production has never executed."
    )

    newest = max(datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")) for x in runs)
    age_h = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    assert age_h < _MAX_AGE_H, (
        f"{_WORKFLOW} last ran {age_h:.0f}h ago (ceiling {_MAX_AGE_H}h). The sixteen "
        f"probes of tests/test_prod_health.py run THERE AND NOWHERE ELSE — they are the "
        f"only check that reaches production through Cloudflare, so edge, cert, DNS and "
        f"routing regressions are currently unobserved.\n"
        f"  → Re-run it now: gh workflow run {_WORKFLOW}\n"
        f"  → If GitHub's cron keeps drifting, move the schedule off the hour "
        f"(minute 17 rather than 00) — the busiest slots are the ones dropped first."
    )


def test_the_ceiling_sits_between_normal_drift_and_the_real_anomaly():
    """The calibration, checked against the measured distribution rather than restated.

    Both bounds come from data, and each rules out one way of being useless:

    * **above 25.4 h** — the second-largest gap in 37 samples. Below it, ordinary
      best-effort cron drift raises a daily false alarm, and a guard that cries wolf is
      deleted within the week.
    * **below 34.6 h** — the one real anomaly, 26→27 August. Above it the guard has
      never fired on anything that ever happened, which is what 36 h would have been.

    Asserting `_MAX_AGE_H == 30` instead would have been just as green at 36: it would
    restate the constant rather than test the choice.
    """
    assert _MEASURED_GAPS_H["second_largest"] < _MAX_AGE_H < _MEASURED_GAPS_H["max"], (
        f"ceiling {_MAX_AGE_H}h is outside the measured window "
        f"({_MEASURED_GAPS_H['second_largest']}h, {_MEASURED_GAPS_H['max']}h). Below it "
        f"normal drift alarms daily; above it the guard never fires on anything "
        f"observed in {_MEASURED_GAPS_H['samples']} gaps."
    )


def test_an_unparseable_ceiling_falls_back_instead_of_disabling_the_guard():
    """A typo in the env var must not silently widen the window to infinity.

    The skip above already means this file says nothing locally. If the ceiling could
    also become absurd from a bad value, it would say nothing in CI either — and a guard
    switchable off by a typo is the exact failure it exists to catch.
    """
    for bad in ("", "   ", "trente", "0", "-5", "1e9", "9999"):
        assert resolve_ceiling(bad) == _DEFAULT_MAX_AGE_H, bad
    # …and a sane explicit value is still honoured, or the fallback would swallow
    # every override and the variable would be decoration.
    assert resolve_ceiling("28") == 28
