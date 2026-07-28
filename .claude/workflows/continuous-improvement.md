---
keywords: amélioration continue, continuous improvement, meta-loop, self-audit, auto-audit, améliorer la config, improve the config, config self-improvement, nettoyer la config, simplifier la config, curator, dette technique, tech debt, agent roster, agent inutilisé, unused agent, façade agent, télémétrie, telemetry, inject_context, hook, skill, slash command
strong_keywords: améliorer la config, agent roster, façade agent, curator
rex: []
---

# Workflow — continuous improvement (the meta-loop)

How the config improves itself, honest about what is automatic and what is not.

| # | Step | Carrier | Type |
|---|------|---------|------|
| 1 | Observe | `observe.py` (PostToolUse) appends to `observations.jsonl` | hook |
| 2 | Weekly review | `/curator` — consolidate REX, flag stale tools (report-only, it proposes) | command |
| 3 | Coverage meta-guard | `audit_runner.py --coverage` — no catalogued class may be un-swept | signature |
| 4 | Promote the lessons | `/retro` or `/rex-promote` — REX lives in the tool's own frontmatter, so it travels with the tool | command + human |
| 5 | Prune | delete what is unused. A tool nobody invokes is not neutral: it is a claim that something is covered. | playbook |

## Prefer a DETECTOR over an AGENT

Measured rather than assumed, in the one repo of this fleet with real telemetry: of 30 declared
agents, **26 were never invoked** — its own CLAUDE.md calls them "measured theater". What earned its
place was a small live set (`code-critic`, `Explore`, `strategic-plan-architect`,
`security-reviewer`, `build-error-resolver`, `web-research-specialist`) plus **deterministic
detectors**.

Before adding an agent, ask what it does that a grep, a test, or a signature cannot. If the answer
is "it interprets the output of a script", write the script and read it yourself: an agent that
wraps a command is a façade with a token bill.

## Measure the EFFECT, never the artifact

The recurring failure of this whole configuration effort, in one line. A file that exists, a hook
that exits 0, a chain reported "present", a server that is registered — none of those is the thing
working. Every one of them has shipped green while the capability was absent:

- a sensor wrote 735 rows that nothing read;
- four repos carried an error-class catalogue with no runner;
- an MCP server was registered, perfectly described, and failed to connect in 52 % of sessions;
- a probe harness built its payload and then dropped it, so every hook was tested on empty input;
- an injector discovered zero domains and exited 0, in six repos at once.

So: when adding a check, write down what the component is supposed to *do*, then run that and read
the output. `exit 0` is not an output.

## The golden rule — HOOK ≠ ORCHESTRATOR

| A **hook** | **The model / CLAUDE.md** |
|---|---|
| observes an event, collects context, injects text | decides which agent to spawn, runs the playbook |
| can block a tool call (exit 2) | can reason about whether a finding is real |
| **cannot** spawn an agent or run a workflow | executes the workflow that was injected |

So `inject_context.py` self-wiring `bug-resolution.md` is the maximum automation the harness allows:
a hook emits the playbook, the model runs it. Any doc claiming a hook "launches the pipeline" is
lying about its own machinery — and that lie is what makes people stop trusting the machinery.
