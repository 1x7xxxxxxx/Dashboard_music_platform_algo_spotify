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
             ("prod-health.yml", "Santé prod", None),
             # The recap watches itself (code-critic, 2026-09-26): a night whose own send
             # failed shows up red in the next recap and in the 23:00 production mail.
             ("nightly-recap.yml", "Récap de la nuit (GitHub)", None))
_NO_VERDICT = {"cancelled", "skipped", None, ""}


def fetch_runs(workflow: str, branch: "str | None", repo: str = REPO,
               opener=urllib.request.urlopen) -> "list[dict] | None":
    """Completed runs of `workflow`, newest first, or None when GitHub cannot be read.

    R316 (2026-09-29): the recap of 09-28 14:32 said « Santé prod : ROUGE » on a green
    workflow and nothing it had read was kept. The completed filter now runs HERE, on the
    runs themselves, not as `?status=completed` (served by a search index that can lag —
    cause inferred, not proven), and an answer without `workflow_runs` (a rate-limit or
    error body) is « unreadable », never an empty — hence « unknown » — list.
    """
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
           f"?per_page=30" + (f"&branch={branch}" if branch else ""))
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "streamlytics-recap"})
    try:
        with opener(req, timeout=20) as r:
            runs = json.load(r).get("workflow_runs")
    except Exception:  # noqa: BLE001 — any failure is « unreadable », said as such
        return None
    if not isinstance(runs, list):
        return None
    if branch and not is_fresh(runs, fetch_head(branch, repo, opener)):
        return None
    return [run for run in runs if run.get("status") == "completed"]


def fetch_head(branch: str, repo: str = REPO, opener=urllib.request.urlopen) -> "str | None":
    """The sha at the tip of `branch`, or None when it cannot be read."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/commits/{branch}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "streamlytics-recap"})
    try:
        with opener(req, timeout=20) as r:
            sha = json.load(r).get("sha")
    except Exception:  # noqa: BLE001 — an unknown head makes the runs unreadable
        return None
    return sha if isinstance(sha, str) and sha else None


def is_fresh(runs: list, head_sha: "str | None") -> bool:
    """Do the runs include one for the branch's head commit? Pure.

    R407 (2026-10-05): the runs list is served by an index that can lag by DAYS — the
    15:18 recap said « CI (main) ROUGE depuis le 2026-09-20 » from a page whose newest
    run was weeks old, and `gh run list --branch main` returned 2026-09-04 as newest the
    same evening. Every push to main starts CI, so a list without the head's run is a
    stale list: « unreadable », never a verdict. Any status counts — the head's run may
    still be running; the completed filter comes after.
    """
    return bool(head_sha) and any(r.get("head_sha") == head_sha for r in runs)


def describe(runs: "list[dict] | None", n: int = 3) -> str:
    """What a verdict was judged on, for the run's log: the newest runs read. Pure."""
    if runs is None:
        return "illisible"
    return " · ".join(f"{r.get('id')} {str(r.get('created_at'))[:16]} {r.get('event')} "
                      f"{r.get('conclusion')}" for r in runs[:n]) or "aucun run terminé"


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
        return {"state": "green", "since": None, "url": newest.get("html_url"),
                "id": newest.get("id")}
    since = newest.get("created_at")
    for r in judged:
        if r.get("conclusion") == "success":
            break
        since = r.get("created_at")
    return {"state": "red", "since": (since or "")[:10], "url": newest.get("html_url")}


# R493 — `security-nightly.yml` puts `continue-on-error` on its observational jobs (all but
# pip-audit and gitleaks, blocking since R267), so the run, such a job and its steps all read
# `success` on GitHub even when its `notify` job mails red (measured on run 38040290890,
# 2026-10-10: guard-mutation failed, every API field green).
# `notify` therefore publishes the failed jobs as an annotation with this title, and the
# recap reads it. The title is the contract — tools/dev/nightly_verdict.py writes it.
FAILED_JOBS_TITLE = "nightly-failed-jobs"
NIGHTLY_WORKFLOW = "security-nightly.yml"


def notify_annotations_url(jobs: "dict | None") -> "str | None":
    """The annotations URL of the run's completed `notify` job, or None. Pure."""
    for job in (jobs or {}).get("jobs") or []:
        if job.get("name") == "notify" and job.get("status") == "completed":
            url = job.get("check_run_url")
            return f"{url}/annotations" if url else None
    return None


def failed_jobs(annotations: object) -> "list[str] | None":
    """The jobs `notify` declared failed: [] on a clean night, None when unreadable. Pure."""
    if not isinstance(annotations, list):
        return None
    for a in annotations:
        if isinstance(a, dict) and a.get("title") == FAILED_JOBS_TITLE:
            return [j.strip() for j in str(a.get("message", "")).split(",") if j.strip()]
    return []


def _get_json(url: str, opener) -> object:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "streamlytics-recap"})
    with opener(req, timeout=20) as r:
        return json.load(r)


def fetch_failed_jobs(run_id: object, repo: str = REPO,
                      opener=urllib.request.urlopen) -> "list[str] | None":
    """The failed jobs of a nightly run, read from its `notify` annotation; None = unreadable."""
    if not run_id:
        return None
    try:
        url = notify_annotations_url(_get_json(
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs", opener))
        return failed_jobs(_get_json(url, opener)) if url else None
    except Exception:  # noqa: BLE001 — any failure is « unreadable », said as such
        return None


def github_section(verdicts: dict) -> "tuple[str, bool]":
    """(HTML section, any red) for {label: verdict}. Pure."""
    icons = {"green": "✅", "red": "🔴", "unreadable": "⚠️", "unknown": "⚪"}
    rows, red = [], False
    for label, v in verdicts.items():
        state = v["state"]
        red = red or state == "red"
        text = {"green": "vert",
                "red": f"ROUGE depuis le {v['since']} — le mail de cassure devait partir ce jour-là (sa livraison n'est pas vérifiée ici)",
                "unreadable": "GitHub illisible cette nuit — état INCONNU, pas vert",
                "unknown": "aucune exécution jugée"}[state]
        if state == "green" and "jobs" in v:
            # Amber, not red (R493 critic): the run did not fail, the owner already has the
            # nightly's own mail — but the recap must not say plain « vert » beside it.
            if v["jobs"] is None:
                text = "run vert — détail des jobs ILLISIBLE, leur état est inconnu"
            elif v["jobs"]:
                text = ("run vert, mais à relire — job(s) en échec : "
                        + html.escape(", ".join(v["jobs"])))
            icon = "🟠" if v["jobs"] else ("⚠️" if v["jobs"] is None else icons[state])
        else:
            icon = icons[state]
        link = f' — <a href="{html.escape(v["url"])}">dernier run</a>' if v.get("url") else ""
        rows.append(f"<li>{icon} <b>{html.escape(label)}</b> : {text}{link}</li>")
    return "<h3>GitHub</h3><ul>" + "".join(rows) + "</ul>", red


def github_verdicts(opener=urllib.request.urlopen) -> dict:
    """{label: verdict} for the three workflows — three unauthenticated requests."""
    out = {}
    for wf, label, branch in WORKFLOWS:
        runs = fetch_runs(wf, branch, opener=opener)
        out[label] = verdict(runs)
        if wf == NIGHTLY_WORKFLOW and out[label]["state"] == "green":
            out[label]["jobs"] = fetch_failed_jobs(out[label].get("id"), opener=opener)
        print(f"   {label} → {out[label]['state']} — lu : {describe(runs)}")
    return out


def short_recap(now_str: str, headline: str, github_html: str) -> "tuple[str, str]":
    """(subject, HTML body) of the recap sent when there is nothing NEW to report — a
    quiet night, or findings unchanged since the last full mail. Pure."""
    subject = f"📋 Récap de la nuit — {headline}"
    body = (f"<p>{html.escape(headline)} ({html.escape(now_str)}).</p>{github_html}"
            "<p style='color:#666'>Un mail chaque nuit : son absence veut dire que le "
            "moniteur lui-même ne tourne plus.</p>")
    return subject, body
