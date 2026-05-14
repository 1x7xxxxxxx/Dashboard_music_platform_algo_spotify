---
name: continuous-learning
description: "Capture patterns discovered during sessions and persist them as reusable skills. Prevents rediscovering the same patterns session after session."
origin: ECC continuous-learning-v2 (generic)
rex: []
---

# Continuous Learning

## When to Use

- At the end of a session where you discovered a non-obvious pattern (recipe, library quirk, config trick, performance gotcha)
- When the same fix or workaround appears for the second time
- When a constraint or anti-pattern needs to be remembered across sessions
- When `/retro` reveals a recurring blocker

## How to Save a Pattern

When a non-obvious pattern is confirmed (the fix works, the user did not push back):

1. Determine the scope:
   - **Project-specific** → save under `.claude/skills/learned/`
   - **Universal across projects** → save under `~/.claude/skills/learned/`

2. Write the pattern file:

```markdown
---
trigger: "<when this situation occurs>"
confidence: 0.7
domain: "<your-domain — pick a stable label, e.g. python|docker|postgres|api>"
discovered: "YYYY-MM-DD"
---

## Pattern
<one sentence>

## Evidence
- <what happened that revealed this>

## Action
<exactly what to do>

## Anti-pattern avoided
<what NOT to do>
```

3. Name the file descriptively. Examples:
   - `postgres-pool-leak-under-threaded-uvicorn.md`
   - `docker-compose-bind-mount-tz-leak.md`
   - `nextjs-hydration-mismatch-on-locale.md`

## Pattern Library

(Empty at bootstrap — populate as patterns emerge from real sessions.)

## Anti-promotion criteria

Do NOT promote a pattern to a learned skill when:
- It is a one-off bug specific to a single file (belongs in a code comment, not a skill)
- It is already documented in an existing rule (`.claude/rules/*.md`) or framework / library doc
- It restates an obvious behaviour from a tool's manual
- The "fix" is just "read the docs more carefully" — link the doc instead
