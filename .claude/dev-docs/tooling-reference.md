# Référence outillage — blocs sortis de CLAUDE.md

Déplacés le 2026-08-21. Raison mesurée par ce dépôt lui-même : **un agent nommé
dans une règle impérative est invoqué ; nommé dans un tableau, il ne l'est jamais**
— 33 invocations contre 0 sur 23. Ces tableaux coûtaient donc du contexte à chaque
session sans produire un seul déclenchement (axe F de `audit_fleet.py` : CLAUDE.md
> 400 lignes = −3 points).

Ce qui est resté dans CLAUDE.md : tout ce qui **déclenche** — les 17 règles
transverses, les playbooks auto-injectés, la règle de la boucle d'ingénierie.
Ce qui est ici : ce qui **documente**.

---

### Agents (`.claude/agents/`)
| Agent | Role |
|---|---|
| `strategic-plan-architect` | Background: updates architecture.md, checklist.md, DEVLOG.md + per-tool REX blocks |
| `code-architecture-reviewer` | Cold audit of modified code vs project patterns |
| `build-error-resolver` | Diagnoses pytest failures when Stop hook signals ≥5 errors |
| `web-research-specialist` | Recherche web — rend un résumé ≤500 mots. **À la demande uniquement** : aucun déclencheur automatique, et c'est assumé — inventer une règle pour lui ferait monter un score sans rien changer à son usage réel. |

---

### Slash Commands
| Command | Purpose |
|---|---|
| `/review-db-schema` | Audit schema coherence (UNIQUE, upsert_many, artist filter) |
| `/review-dag` | Audit DAG conformity (sys.path, default_args, debug_dag coverage) |
| `/review-architecture` | Audit Mermaid diagrams vs current codebase state |
| `/logs-airflow` | Read + analyze recent Airflow container logs |
| `/dev-docs <name>` | Generate plan/context/checklist trio for a large feature |
| `/run-tests` | Execute pytest suite and analyze failures |
| `/roadmap-done <id>` | Tick a roadmap task + retire its row from the top `## 📋 Tâches ouvertes` index into `## Completed` (run on every task completion) |

---

### Required setup before first use

1. **Export env vars** in `~/.bashrc` or `.env.local` (see `.env.example` § MCP Servers) :
   ```bash
   export DB_PASSWORD='<see config/config.yaml>'
   export GITHUB_TOKEN='<PAT scopes: repo, read:org>'   # github.com/settings/tokens
   export AIRFLOW_ADMIN_USERNAME='<see docker-compose.yml — _AIRFLOW_WWW_USER_USERNAME>'
   export AIRFLOW_ADMIN_PASSWORD='<see docker-compose.yml — _AIRFLOW_WWW_USER_PASSWORD>'
   ```
2. **Chromium / Chrome auto-downloaded** by `chrome-devtools-mcp` on first run via puppeteer (no `apt install` needed). On WSL2 Ubuntu 24.04, the `chromium-browser` apt package is a snap shim that doesn't work — rely on puppeteer's bundled Chrome for Testing instead.
3. **Install `uv`** if missing (for `airflow` MCP) : `pip install uv`
4. **Restart Claude Code** so it re-reads `.mcp.json`.

---

### Verification
- `claude mcp` lists active servers and start-up errors
- Each MCP can be tested by asking Claude an obvious query (e.g. "list spotify_etl tables", "list open PRs", "list DAGs and their status")

---

### MCP selection rationale (May 2026)
- **Postgres MCP** : official Anthropic server, read-only by default — safer than `crystaldba/postgres-mcp-pro` for exploratory use
- **GitHub MCP** : official GitHub (Go-based) — supersedes the legacy TS `@modelcontextprotocol/server-github`
- **Chrome DevTools MCP** : official Google server — supersedes the older `@modelcontextprotocol/server-puppeteer`
- **Airflow MCP** : community `yangkyeongmo/mcp-server-apache-airflow` — no official Apache/Astronomer equivalent yet

---

### Out-of-scope (intentionally excluded)
- MLflow / Sentry MCPs : aucune dépendance détectée dans le repo
- Filesystem / Sequential-thinking MCPs : redondants avec les outils natifs de Claude Code
- Notion / Gmail / Drive : déjà disponibles côté Claude.ai (deferred tools)
- Spotify Web API MCP : redondant avec `src/collectors/spotify_collector.py`

---

### RTK (Rust Token Killer) — user-level proxy

If you see `rtk read`, `rtk pytest`, `rtk grep` in transcripts, that's the
**RTK** utility (user-level binary, not a project dependency) filtering and
compressing Bash output to save tokens (60-90 % typical, ~95 % at peak on this
machine). Transparent — no install or config needed on this repo.

- Pass-through any command : `rtk proxy <cmd>` (skip filtering, useful for
  debugging an output that RTK might have truncated).
- Inspect savings : `rtk gain` (global) / `rtk gain --history` (per-command).
- Identify missed opportunities : `rtk discover` (scans Claude Code history).

Reference: `~/.claude/RTK.md` (user-global config, not in this repo).
