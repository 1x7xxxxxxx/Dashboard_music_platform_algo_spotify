"""An old secret counts as dead only when its provider REFUSES it — never on a doubt.

Type: Sub
Uses: tools/dev/prove_old_secrets_dead.py (classify — pure, no network)
Depends on: nothing

R177 (2026-09-25): « rotated » is a claim. The first run found the leaked YouTube key
still ACCEPTED after the owner believed the rotation done.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "posd", Path(__file__).resolve().parents[1] / "tools/dev/prove_old_secrets_dead.py")
posd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(posd)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A 200 is ALIVE for every provider; a refusal is DEAD; a network failure is not DEAD."""
    for provider in ("spotify", "youtube", "meta"):
        assert posd.classify(provider, 200, "{}") == posd.ALIVE, provider
        assert posd.classify(provider, 0, "") == posd.UNKNOWN, f"{provider}: no answer is not a death"
    assert posd.classify("spotify", 400, '{"error":"invalid_client"}') == posd.DEAD
    assert posd.classify("youtube", 400, '{"reason":"API_KEY_INVALID"}') == posd.DEAD
    assert posd.classify("youtube", 403, '{"reason":"quotaExceeded"}') == posd.UNKNOWN, \
        "a quota refusal says the key WORKS enough to be counted — never read it as dead"
    assert posd.classify("meta", 400, '{"error":{"code":1}}') == posd.DEAD
