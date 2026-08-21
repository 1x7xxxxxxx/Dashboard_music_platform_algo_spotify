---
keywords: nouvelle fonctionnalité, new feature, feature, brique, brick, endpoint, nouvelle route, new route, implémenter, implement, développer, build a, ajouter un module, nouveau module, scoping, cadrage
strong_keywords: nouvelle fonctionnalité, new feature, nouvelle brique
rex: []
---

# Workflow — feature development

For a new capability that is not a bug fix. A playbook the model runs.

| # | Step | Carrier | Type |
|---|------|---------|------|
| 1 | Scope it | `/dev-docs <feature>` → `work-in-progress/<feature>/context.md` + `plan.md` | command |
| 2 | Design | `Plan` agent — step-by-step, trade-offs, critical files. State what you are NOT building. | playbook |
| 3 | Challenger, if high-stakes | `code-critic` on the DESIGN (see `bug-resolution.md` for the surface list) | playbook |
| 4 | Build the smallest slice that is provable | not the whole feature — the smallest thing whose correctness can be demonstrated | playbook |
| 5 | Tests alongside, not after | the real dependency (never mocked where the repo forbids it), error paths as well as happy paths, no hardcoded thresholds | pytest |
| 6 | Review | the repo's language reviewer; `security-specialist` if external-facing; `test-quality-reviewer` on new tests | playbook |
| 7 | Flag-gate anything that touches a proven path | default OFF, measure, then flip. A production-proven path is not where an unmeasured improvement lands. | playbook |
| 8 | Docs | the route/contract doc for an interface, diagrams for a structure, ROADMAP for the status | playbook |
| 9 | DEVLOG | Why / What changed / Tests (the ACTUAL count — never copied from a prior entry) | playbook |

## Rule of thumb

If the feature cannot be described as "X becomes possible, and here is how we would know it broke",
it is not scoped yet. Step 1 is not paperwork; it is the step that prevents building the wrong slice
well.
