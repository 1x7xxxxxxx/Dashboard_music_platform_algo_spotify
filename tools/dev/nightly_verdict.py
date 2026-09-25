#!/usr/bin/env python3
"""Mail the owner when a job of `security-nightly.yml` failed — the workflow itself stays green.

Type: Utility
Uses: tools/dev/mail_red_verdict.py (build_message, send, _REQUIRED), env RESULTS (= toJSON(needs))
Triggers: .github/workflows/security-nightly.yml, job `notify`
Persists in: nothing — one mail, or nothing on a clean night

Measured 2026-09-25: every nightly job carries `continue-on-error`, so the workflow was
always green; `gitleaks` had failed 5 nights out of 5 and the random-order suite 4 out of
5, read by nobody. A job FAILURE triggers the mail. The pip-audit and audit counters —
present every night, known false positives among them — ride in the body only: a mail that
leaves every night is a mail nobody reads.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mail_red_verdict as mail  # noqa: E402

_FAILED = {"failure", "cancelled"}


def verdict(needs: dict) -> str | None:
    """The mail body when a job failed, else None."""
    # `result` alone LIES: a job under `continue-on-error` reports `success` to `needs` even
    # when it failed (measured on the first dispatch, 2026-09-25). A job that can fail
    # publishes its step's real `outcome`; that wins over `result`.
    def _state(v: dict) -> str:
        v = v or {}
        return (v.get("outputs") or {}).get("outcome") or v.get("result") or ""
    failed = sorted(j for j, v in needs.items() if _state(v) in _FAILED)
    if not failed:
        return None
    out = lambda j, k: ((needs.get(j) or {}).get("outputs") or {}).get(k, "?")  # noqa: E731
    lines = [f"Job(s) en échec : {', '.join(failed)}.", ""]
    if "gitleaks" in failed:
        lines.append("gitleaks : des secrets RÉELS de l'historique public attendent leur "
                     "rotation (runbook §27) — ce mail repart chaque nuit tant qu'ils ne "
                     "sont pas tournés et inscrits dans .gitleaksignore.")
    lines += [f"pip-audit : {out('pip-audit', 'vulns')} avis · audit du catalogue : "
              f"{out('error-class-audit', 'hits')} HIT(s) — pour information, ils ne "
              "déclenchent pas ce mail seuls."]
    return "\n".join(lines)


def main() -> int:
    needs = json.loads(os.environ.get("RESULTS") or "{}")
    body = verdict(needs)
    if body is None:
        print("✅ aucun job du nightly en échec — pas de mail")
        return 0
    print(body)
    missing = [k for k in mail._REQUIRED if not os.environ.get(k)]
    if missing:
        print(f"❌ cannot mail: {', '.join(missing)} absent")
        return 1
    env = dict(os.environ)
    mail.send(env, mail.build_message(env, detail=body))
    print("✅ verdict du nightly envoyé")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
