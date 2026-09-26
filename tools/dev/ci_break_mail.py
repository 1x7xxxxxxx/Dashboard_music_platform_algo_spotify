#!/usr/bin/env python3
"""Mail the owner when a push turns `main` RED — once per breakage, not once per red push.

Type: Utility
Uses: tools/dev/mail_red_verdict.py (build_message, send, _REQUIRED), GitHub REST API
      (previous CI run on main), env RESULTS (= toJSON(needs)), GITHUB_TOKEN
Triggers: .github/workflows/ci.yml, job `notify` (push to main only)
Persists in: nothing — one mail on a green→red transition, else nothing

`ci.yml` was red on main from 2026-09-22 to 2026-09-25, read by nobody: its red went to
GitHub notifications only. Mailing every red push was rejected when the class was swept
(« le rythme d'un push n'est pas celui d'une panne ») — so this mails the TRANSITION:
the previous completed run on main was green and this one is not. Main that stays red
does not mail again; main that goes green and breaks again does. When the previous run
cannot be read, it mails anyway: a mailer that skips on doubt is the defect it replaces.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mail_red_verdict as mail  # noqa: E402

# `cancelled` is NOT red. `ci.yml` runs with `cancel-in-progress: true`: every push
# cancels the run before it, and `notify` (`always()`) still runs on the cancelled
# one. Counting it as a failure mailed « main vient de passer au ROUGE — job(s) :
# gates, suite » for runs nobody had judged — twice on 2026-09-26, both cancelled.
_FAILED = {"failure"}
# A verdict is a run that FINISHED judging: cancelled or skipped runs say nothing.
_NO_VERDICT = {"cancelled", "skipped", None}


def failed_jobs(needs: dict) -> list[str]:
    return sorted(j for j, v in needs.items() if (v or {}).get("result") in _FAILED)


def should_mail(failed: list[str], previous_conclusion: str | None) -> bool:
    """A red run mails when main was green before it — or when that cannot be known."""
    return bool(failed) and previous_conclusion != "failure"


def previous_conclusion(env: dict) -> str | None:
    """Conclusion of the last completed CI run on main before this one, or None."""
    url = (f"{env.get('GITHUB_API_URL', 'https://api.github.com')}/repos/"
           f"{env['GITHUB_REPOSITORY']}/actions/workflows/ci.yml/runs"
           "?branch=main&event=push&status=completed&per_page=10")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {env['GITHUB_TOKEN']}",
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            runs = json.load(r).get("workflow_runs", [])
    except (OSError, ValueError, KeyError):
        return None
    return last_verdict(runs, str(env.get("GITHUB_RUN_ID", "")))


def last_verdict(runs: list[dict], me: str) -> str | None:
    """Conclusion of the newest OTHER run that reached a verdict (newest first, as the
    API returns them). A cancelled run on top would otherwise read as « main was not
    red » and mail again on a main that never stopped being red. Pure."""
    for run in runs:
        if str(run.get("id")) != me and run.get("conclusion") not in _NO_VERDICT:
            return run.get("conclusion")
    return None


def main() -> int:
    env = dict(os.environ)
    failed = failed_jobs(json.loads(env.get("RESULTS") or "{}"))
    if not failed:
        print("✅ CI verte sur main — pas de mail")
        return 0
    prev = previous_conclusion(env) if env.get("GITHUB_TOKEN") else None
    if not should_mail(failed, prev):
        print(f"main était déjà rouge (run précédent : {prev}) — pas de second mail")
        return 0
    body = (f"main vient de passer au ROUGE — job(s) : {', '.join(failed)}.\n"
            f"Run précédent sur main : {prev or 'illisible'}. Un seul mail par cassure : "
            "tant que main reste rouge, les pushes suivants n'écrivent pas.")
    print(body)
    missing = [k for k in mail._REQUIRED if not env.get(k)]
    if missing:
        print(f"❌ cannot mail: {', '.join(missing)} absent")
        return 1
    mail.send(env, mail.build_message(env, detail=body))
    print("✅ cassure de main envoyée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
