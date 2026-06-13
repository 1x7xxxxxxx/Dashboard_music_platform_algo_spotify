#!/usr/bin/env python3
"""
Hook UserPromptSubmit — Domain-aware context injection.

Detects keywords in the user prompt and injects the matching skill / rule file
from .claude/skills/ or .claude/rules/ as a system-reminder block before
Claude reads the prompt.

Generic payload ships with an EMPTY DOMAINS dict — projects populate it after
bootstrap to point at their own skills/rules. Two starter examples are kept
commented at the bottom of the file.

Always exits 0 — never blocks.

---
rex: []
---
"""
import glob
import json
import os
import re
import sys

# Best-effort usage telemetry (curator self-improvement loop). Defensive import:
# a missing/broken telemetry module must never break context injection.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from usage_telemetry import record as _telemetry_record
except Exception:  # noqa: BLE001 — telemetry is optional
    def _telemetry_record(*_a, **_k):
        return None


# ── Domain → (keywords, source folder, file) ─────────────────────────────────
#
# Each entry maps a list of trigger keywords (lowercased substring match) to a
# file under .claude/skills/ or .claude/rules/. When ≥2 keywords from a domain
# appear in the prompt, the matching file is injected (capped at _MAX_DOMAINS
# files per prompt to stay within context budget).
#
# AUTO-DISCOVERED from each skill's `keywords:` frontmatter field (see
# _discover_domains below). This hardcoded dict is only the FALLBACK used when no
# skill declares keywords (generic payload / fresh bootstrap).

_FALLBACK_DOMAINS: dict[str, tuple[list[str], str, str]] = {
    "dashboard": (
        ["vue", "view", "dashboard", "streamlit", "page", "sidebar",
         "onglet", "navigation", "widget", "plotly", "chart", "kpi",
         "metric", "st.", "button", "bouton", "filter", "filtre",
         "afficher", "affiche", "render"],
        "skills", "dashboard-view.md",
    ),
    "dag": (
        ["dag", "airflow", "pythonoperator", "sensor",
         "collecte", "pipeline", "orchestr", "watcher",
         "scheduler", "schedule", "cron", "catchup", "backfill", "daily",
         "tâche", "task", "trigger", "retry", "retries"],
        "skills", "airflow-dag.md",
    ),
    "schema": (
        ["schema", "table", "postgres", "postgresql", "migration",
         "create table", "alter table", "init_db",
         "colonne", "column", "constraint", "unique", "index",
         "upsert", "upsert_many", "insert_many",
         "base de données", "postgres_handler"],
        "skills", "db-schema.md",
    ),
    "collector": (
        ["collector", "src/collectors",
         "spotify", "youtube", "meta ads", "instagram", "soundcloud",
         "apple music", "facebook",
         "oauth", "access_token", "api_key", "rate limit",
         "endpoint", "credential",
         "s4a", "spotify for artists", "hypeddit"],
        "skills", "audit-collectors.md",
    ),
}

# ── Path resolution ───────────────────────────────────────────────────────────

_HOOK_DIR    = os.path.dirname(os.path.abspath(__file__))   # .claude/hooks/
_CLAUDE_DIR  = os.path.dirname(_HOOK_DIR)                    # .claude/


def _discover_domains() -> dict[str, tuple[list[str], str, str]]:
    """Build DOMAINS by scanning .claude/skills/*.md for a frontmatter `keywords:`
    line (`keywords: kw1, kw2, …`). A new skill that declares keywords is auto-injected
    with no edit to this hook. Returns {} if no skill declares keywords → fallback."""
    found: dict[str, tuple[list[str], str, str]] = {}
    for path in sorted(glob.glob(os.path.join(_CLAUDE_DIR, "skills", "*.md"))):
        try:
            with open(path, encoding="utf-8") as f:
                head = f.read(2048)   # keywords live in the top frontmatter block
        except OSError:
            continue
        m = re.search(r"^keywords:\s*(.+)$", head, re.M)
        if not m:
            continue
        kws = [k.strip().lower() for k in m.group(1).split(",") if k.strip()]
        if kws:
            fn = os.path.basename(path)
            found[os.path.splitext(fn)[0]] = (kws, "skills", fn)
    return found


DOMAINS: dict[str, tuple[list[str], str, str]] = _discover_domains() or _FALLBACK_DOMAINS

_MAX_DOMAINS = 3     # Max files injected per prompt (context budget)
_MAX_LINES   = 120   # Max lines per file (truncate heavy files)
_MIN_HITS    = 2     # Minimum keyword matches for a domain to trigger

_DOMAIN_PRIORITY: list[str] = list(DOMAINS.keys())


def load_file(folder: str, filename: str, max_lines: int = _MAX_LINES) -> str | None:
    """Read a skill/rule file, truncate to max_lines. Returns None if missing."""
    path = os.path.join(_CLAUDE_DIR, folder, filename)
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            truncated = lines[:max_lines]
            truncated.append(
                f"\n… [truncated at {max_lines} lines — full file at .claude/{folder}/{filename}]\n"
            )
            return "".join(truncated).strip()
        return "".join(lines).strip()
    except OSError:
        return None


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_domains(prompt: str) -> list[str]:
    if not DOMAINS:
        return []
    prompt_lower = prompt.lower()
    matched = []
    for domain, (keywords, _, _) in DOMAINS.items():
        hit_count = sum(1 for kw in keywords if kw in prompt_lower)
        if hit_count >= _MIN_HITS:
            matched.append(domain)
    matched.sort(key=lambda d: _DOMAIN_PRIORITY.index(d) if d in _DOMAIN_PRIORITY else 99)
    return matched[:_MAX_DOMAINS]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    detected = detect_domains(prompt)
    if not detected:
        sys.exit(0)

    blocks: list[str] = []
    for domain in detected:
        _, folder, filename = DOMAINS[domain]
        content = load_file(folder, filename)
        if content:
            blocks.append(content)
            _telemetry_record("skills", domain)  # curator usage signal

    if blocks:
        print("\n".join(blocks))

    sys.exit(0)


if __name__ == "__main__":
    main()


# ── Example DOMAINS entries (delete or adapt) ────────────────────────────────
#
# Web app project:
#
#   DOMAINS = {
#       "api": (
#           ["route", "endpoint", "fastapi", "express", "flask",
#            "request", "response", "status code"],
#           "rules", "api.md",
#       ),
#       "database": (
#           ["postgres", "mysql", "sqlite", "schema", "migration",
#            "query", "table", "column"],
#           "rules", "database.md",
#       ),
#       "debug": (
#           ["debug", "traceback", "stack trace", "exception",
#            "ne fonctionne pas", "broken", "silent fail"],
#           "skills", "systematic-debugging.md",
#       ),
#   }
#
# Data / ML project:
#
#   DOMAINS = {
#       "ml": (
#           ["train", "model", "feature", "scikit", "torch", "shap",
#            "drift", "mlflow", "registry"],
#           "skills", "mlops.md",
#       ),
#       "data": (
#           ["pipeline", "extract", "transform", "load", "etl",
#            "dataset", "schema validation"],
#           "skills", "data-engineering.md",
#       ),
#   }
