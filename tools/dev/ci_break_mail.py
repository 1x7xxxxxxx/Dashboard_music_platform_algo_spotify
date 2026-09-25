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

_FAILED = {"failure", "cancelled"}


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
    me = str(env.get("GITHUB_RUN_ID", ""))
    for run in runs:
        if str(run.get("id")) != me:
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
