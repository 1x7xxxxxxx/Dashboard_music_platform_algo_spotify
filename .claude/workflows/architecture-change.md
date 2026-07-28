---
keywords: architecture, adr, refactor, refactoring, migration, migrer, schéma, schema, store, nouveau service, new service, découplage, decoupling, contrat, contract, breaking change, rupture de contrat, topologie, topology, transport, protocole, protocol, versioning, compatibilité, compatibility
strong_keywords: adr, breaking change, migration, rupture de contrat
rex: []
---

# Workflow — architecture change

For a decision that changes STRUCTURE: a store, a contract, a schema, a transport, a deployment
shape. These are the changes that invalidate assumptions silently — nothing errors, the meaning
just quietly stops matching the label.

| # | Step | Carrier | Type |
|---|------|---------|------|
| 1 | State the decision **and the alternatives you are rejecting** | the model — an ADR with one option is a rationalisation | playbook |
| 2 | What does this invalidate? | sweep every consumer of the thing being changed: dashboards, downstream jobs, tests, deployed targets, the client-facing contract | playbook |
| 3 | Challenger | `code-critic` — mandatory for a contract, a gate, or a safety-adjacent path | playbook |
| 4 | Structural review | `code-architecture-reviewer` — diagrams vs actual code drift | playbook |
| 5 | Write the ADR | `/adr <title>` → `.claude/dev-docs/ROADMAP.md`. Rationale + rejected alternatives + the ship rule. | command |
| 6 | Schema? → a forward migration | generated, then reviewed by hand. **Never a manual edit on a deployed target.** | playbook |
| 7 | Guard the new invariant | a test that fails if the structure regresses — then **mutation-verify it** | pytest |
| 8 | Update the diagrams | solid = implemented, dashed = planned | playbook |
| 9 | ROADMAP + DEVLOG | status lives in ROADMAP and nowhere else as prose | playbook |

## The question that catches the silent ones

For every change: **"what reads this, and what will it now believe?"**

Three real cases, none of which produced an error. A byte offset moved and every downstream layer
faithfully propagated the wrong quantity under the right label. A store's type could not express
absence, so a dashboard rendered a confident value for a signal that did not exist. A file
bind-mount resolved an inode, so a rebuilt binary never reached the container executing it. All
three were structural, and all three were found by asking that question rather than by a test.

## Dev↔prod parity

Any structural change ships with its answer to: **does the deployed copy still match the repo?**
The audit is a checksum on both sides. A deployed snapshot is not a checkout — nothing reconciles
itself, and "I redeployed" is not evidence that it did.
