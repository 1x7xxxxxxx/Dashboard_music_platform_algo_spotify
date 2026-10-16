"""The empty-roadmap chime never sounds between 01:00 and 09:20, and rings once on the transition.

Type: Hook test
Uses: .claude/hooks/roadmap_empty_beep.py (copied from the baseline `governance` preset)
"""
from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "roadmap_empty_beep.py"


def _hook():
    spec = importlib.util.spec_from_file_location("roadmap_empty_beep", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_chime_waits_for_morning_and_rings_once() -> None:
    b = _hook()
    night, morning = datetime(2026, 10, 16, 3, 0), datetime(2026, 10, 16, 9, 20)
    assert b.decide(2, 0, night) == (False, None)      # pending, not recorded
    assert b.decide(2, 0, morning) == (True, 0)        # rings at 09:20
    assert b.decide(0, 0, morning) == (False, 0)       # never twice
    assert b.decide(None, 0, morning) == (False, 0)    # install is silent
    assert b.allowed(datetime(2026, 10, 16, 0, 59)) and not b.allowed(datetime(2026, 10, 16, 1, 0))
    assert not b.allowed(datetime(2026, 10, 16, 9, 19)) and b.allowed(datetime(2026, 10, 16, 9, 20))
