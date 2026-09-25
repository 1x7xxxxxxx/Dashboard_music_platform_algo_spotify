#!/usr/bin/env python3
"""Prove that every secret leaked in the public git history is REFUSED by its provider.

Type: Utility
Uses: gitleaks (tools/dev/install_gitleaks.sh), git, provider APIs over HTTPS
Triggers: by hand after a rotation (R177, runbook §27) — `python3 tools/dev/prove_old_secrets_dead.py`
Persists in: nothing — values live in memory only; output is a status per secret

« Rotated » is a claim; « the provider refuses the old value » is a measurement. After the
2026-09-25 rotation this script reads each leaked value from history (gitleaks, report on
stdout, captured — never printed, never written), tries it against the provider, and prints
`✓ morte` or `✗ ENCORE VALIDE`. Exit 1 while any old value still works: that finding cannot
go into `.gitleaksignore` yet.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GITLEAKS = next((p for p in ("gitleaks", str(Path.home() / ".local/bin/gitleaks"))
                  if subprocess.run(["sh", "-c", f"command -v {p}"], capture_output=True).returncode == 0),
                 None)
_ASSIGN = re.compile(r"([A-Z][A-Z0-9_]*)\s*[:=]\s*['\"]?([^\s'\"]+)")
DEAD, ALIVE, UNKNOWN = "✓ morte", "✗ ENCORE VALIDE", "? indéterminé"


def _history_values(var: str) -> set[str]:
    """Non-secret companions (client ids) as they appeared anywhere in history."""
    log = subprocess.run(["git", "-C", str(_ROOT), "log", "-p", "--all", "--no-color", "-G", var],
                         capture_output=True, text=True, errors="replace").stdout
    return {m.group(1) for m in re.finditer(
        rf"^[+-].*\b{var}\s*[:=]\s*['\"]?([^\s'\"$]+)", log, re.M)}


def leaked_values() -> dict[str, set[str]]:
    """{VARIABLE: {old values}} from the unredacted gitleaks report, in memory only."""
    if not _GITLEAKS:
        raise SystemExit("❌ gitleaks absent — run: make hooks-install")
    r = subprocess.run([_GITLEAKS, "git", "--no-banner", "-f", "json", "-r", "/dev/stdout",
                        "--exit-code", "0", "--config", str(_ROOT / ".gitleaks.toml"),
                        "--gitleaks-ignore-path", "/dev/null", str(_ROOT)],
                       capture_output=True, text=True)
    out: dict[str, set[str]] = {}
    for f in json.loads(r.stdout or "[]"):
        m = _ASSIGN.search(f.get("Match", ""))
        name = m.group(1) if m else f.get("RuleID", "?")
        out.setdefault(name, set()).add(f["Secret"])
    return out


def classify(provider: str, status: int, body: str) -> str:
    """The provider's answer, read as dead / alive / unknown. Pure: tested without network."""
    if provider == "spotify":
        return ALIVE if status == 200 else DEAD if status in (400, 401) else UNKNOWN
    if provider == "youtube":
        if status == 200:
            return ALIVE
        return DEAD if status in (400, 403) and ("API key" in body or "keyInvalid" in body
                                                 or "API_KEY_INVALID" in body) else UNKNOWN
    if provider == "meta":
        return ALIVE if status == 200 else DEAD if status in (400, 401, 403) else UNKNOWN
    return UNKNOWN


def _call(req: urllib.request.Request) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except OSError:
        return 0, ""


def probe(var: str, value: str) -> tuple[str, str]:
    """(provider, verdict) for one old value."""
    if var.startswith("SPOTIFY"):
        verdicts = []
        for cid in _history_values("SPOTIFY_CLIENT_ID") or {""}:
            auth = base64.b64encode(f"{cid}:{value}".encode()).decode()
            req = urllib.request.Request("https://accounts.spotify.com/api/token",
                                         data=b"grant_type=client_credentials",
                                         headers={"Authorization": f"Basic {auth}"})
            verdicts.append(classify("spotify", *_call(req)))
        return "Spotify", ALIVE if ALIVE in verdicts else DEAD if all(v == DEAD for v in verdicts) else UNKNOWN
    if var.startswith("YOUTUBE") or var == "gcp-api-key":
        q = urllib.parse.urlencode({"part": "id", "id": "dQw4w9WgXcQ", "key": value})
        return "YouTube", classify("youtube", *_call(urllib.request.Request(
            f"https://www.googleapis.com/youtube/v3/videos?{q}")))
    if var == "META_ACCESS_TOKEN":
        q = urllib.parse.urlencode({"access_token": value})
        return "Meta (jeton)", classify("meta", *_call(urllib.request.Request(
            f"https://graph.facebook.com/me?{q}")))
    if var.startswith("META") or var.startswith("FACEBOOK"):
        verdicts = []
        for app in _history_values("META_APP_ID") | {"2200684950508458"}:
            q = urllib.parse.urlencode({"client_id": app, "client_secret": value,
                                        "grant_type": "client_credentials"})
            verdicts.append(classify("meta", *_call(urllib.request.Request(
                f"https://graph.facebook.com/oauth/access_token?{q}"))))
        return "Meta (app)", ALIVE if ALIVE in verdicts else DEAD if all(v == DEAD for v in verdicts) else UNKNOWN
    return var, "— hors d'un fournisseur externe (Airflow interne), non testable ici"


def main() -> int:
    alive = 0
    for var, values in sorted(leaked_values().items()):
        for i, v in enumerate(sorted(values), 1):
            provider, verdict = probe(var, v)
            alive += verdict == ALIVE
            print(f"{verdict:16} {provider:14} {var} (valeur {i}/{len(values)}, {len(v)} car.)")
    print(f"\n{'❌' if alive else '✅'} {alive} ancienne(s) valeur(s) encore acceptée(s)")
    return 1 if alive else 0


if __name__ == "__main__":
    raise SystemExit(main())
