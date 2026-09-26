"""The GitHub half of the nightly recap mail — CI, security nightly, production health.

Type: Utility
Uses: urllib (public GitHub Actions API, no token — the repository is public)
Triggers: airflow/dags/alert_monitor.py (`send_consolidated_alert`)
Persists in: nothing

R181 (2026-09-26). The owner reads none of the four automated mail sources, so ONE mail a
night carries everything: the production findings `alert_monitor` already computes, and the
state of the three GitHub workflows, read here. A red GitHub workflow already sent its own
mail when it broke (`ci_break_mail.py`, the nightly `notify` job); the recap says so instead
of announcing it again as new.

Rules carried from the mailers that learned them:
- `cancelled` / `skipped` are not verdicts (`ci.yml` runs with `cancel-in-progress`) —
  `tools/dev/ci_break_mail.py`, 2026-09-26;
- GitHub unreachable is said as « illisible », never rendered as green.
"""
from __future__ import annotations

import html
import json
import os
import urllib.request

REPO = os.environ.get("STREAMLYTICS_GITHUB_REPO",
                      "1x7xxxxxxx/Dashboard_music_platform_algo_spotify")
WORKFLOWS = (("ci.yml", "CI (main)", "main"),
             ("security-nightly.yml", "Sécurité — nuit", None),
             ("prod-health.yml", "Santé prod", None))
_NO_VERDICT = {"cancelled", "skipped", None, ""}


def fetch_runs(workflow: str, branch: "str | None", repo: str = REPO,
               opener=urllib.request.urlopen) -> "list[dict] | None":
    """Completed runs of `workflow`, newest first, or None when GitHub cannot be read."""
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
           f"?status=completed&per_page=15" + (f"&branch={branch}" if branch else ""))
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "streamlytics-recap"})
    try:
        with opener(req, timeout=20) as r:
            return json.load(r).get("workflow_runs", [])
    except Exception:  # noqa: BLE001 — any failure is « unreadable », said as such
        return None


def verdict(runs: "list[dict] | None") -> dict:
    """{state: green|red|unreadable|unknown, since, url} from runs newest first. Pure.

    `since` is the date of the FIRST red run of the current red streak — the day the
    break mail went out.
    """
    if runs is None:
        return {"state": "unreadable", "since": None, "url": None}
    judged = [r for r in runs if r.get("conclusion") not in _NO_VERDICT]
    if not judged:
        return {"state": "unknown", "since": None, "url": None}
    newest = judged[0]
    if newest.get("conclusion") == "success":
        return {"state": "green", "since": None, "url": newest.get("html_url")}
    since = newest.get("created_at")
    for r in judged:
        if r.get("conclusion") == "success":
            break
        since = r.get("created_at")
    return {"state": "red", "since": (since or "")[:10], "url": newest.get("html_url")}


def github_section(verdicts: dict) -> "tuple[str, bool]":
    """(HTML section, any red) for {label: verdict}. Pure."""
    icons = {"green": "✅", "red": "🔴", "unreadable": "⚠️", "unknown": "⚪"}
    rows, red = [], False
    for label, v in verdicts.items():
        state = v["state"]
        red = red or state == "red"
        text = {"green": "vert",
                "red": f"ROUGE depuis le {v['since']} — un mail l'a signalé à la cassure",
                "unreadable": "GitHub illisible cette nuit — état INCONNU, pas vert",
                "unknown": "aucune exécution jugée"}[state]
        link = f' — <a href="{html.escape(v["url"])}">dernier run</a>' if v.get("url") else ""
        rows.append(f"<li>{icons[state]} <b>{html.escape(label)}</b> : {text}{link}</li>")
    return "<h3>GitHub</h3><ul>" + "".join(rows) + "</ul>", red


def github_verdicts(opener=urllib.request.urlopen) -> dict:
    """{label: verdict} for the three workflows — three unauthenticated requests."""
    return {label: verdict(fetch_runs(wf, branch, opener=opener))
            for wf, label, branch in WORKFLOWS}


def short_recap(now_str: str, headline: str, github_html: str) -> "tuple[str, str]":
    """(subject, HTML body) of the recap sent when there is nothing NEW to report — a
    quiet night, or findings unchanged since the last full mail. Pure."""
    subject = f"📋 Récap de la nuit — {headline}"
    body = (f"<p>{html.escape(headline)} ({html.escape(now_str)}).</p>{github_html}"
            "<p style='color:#666'>Un mail chaque nuit : son absence veut dire que le "
            "moniteur lui-même ne tourne plus.</p>")
    return subject, body
