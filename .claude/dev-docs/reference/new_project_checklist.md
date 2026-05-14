# New Project Checklist — Claude Code

## Bootstrap
- [ ] Run `setup-claude-code.sh --project-name "YourProject"`
- [ ] Verify: `10/10 hooks`, `agents/7`, settings.json valid

## CLAUDE.md
- [ ] Commands section filled (test, run, build)
- [ ] Architecture table accurate
- [ ] Sub-agent triggers match actual workflow

## Hooks
- [ ] `inject_context.py` — domain_1/2/3 renamed to real modules
- [ ] `guard_destructive.py` — project-specific block patterns added
- [ ] `pre_commit_scan.py` — project-specific secret patterns added
- [ ] `session_summary.py` — TESTS_DIR set to real test path

## Skills
- [ ] 3 domain skill files filled (50–120 lines each)
- [ ] Antigravity skills installed (or stubs accepted)

## Agents
- [ ] python-reviewer.md — CRITICAL checks updated
- [ ] silent-failure-hunter.md — target files renamed
- [ ] ml-model-evaluator.md — metric thresholds set (if ML project)

## First session
- [ ] Run `/check-env` to verify prerequisites
- [ ] Run `/sprint` to confirm ROADMAP state
- [ ] Confirm test suite passes: `python3 -m pytest tests/ -q`
