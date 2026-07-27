# Claude Code Deployment Guide

> Generated stub — fill in project-specific deployment steps.

## Step 1 — Run setup script

```bash
bash tools/setup-claude-code.sh --project-name "YourProject"
```

## Step 2 — Fill in CLAUDE.md

Replace every `[TODO]` with actual project content. Priority: Commands section (exact test/run/build commands).

## Step 3 — Configure inject_context.py domains

Edit `.claude/hooks/inject_context.py`:
- Replace `domain_1/domain_2/domain_3` with your module names
- Wire to real skill files

## Step 4 — Fill domain skill files

`.claude/skills/domain_{1,2,3}.md` → 50–120 lines of architectural context per domain.

## Step 5 — Adapt agents

- `python-reviewer.md`: add project-specific CRITICAL checks
- `silent-failure-hunter.md`: rename target files to your async modules

## Step 6 — Add guard patterns

`.claude/hooks/guard_destructive.py` → `_BLOCK_PATTERNS` TODO section.

## Step 7 — Verify

```bash
echo '{"prompt": "debug the connection issue"}' | python3 .claude/hooks/inject_context.py
python3 -c "import json; json.load(open('.claude/settings.json')); print('settings OK')"
```
