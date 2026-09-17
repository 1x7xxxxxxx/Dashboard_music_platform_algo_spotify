---
rex:
- date: 2026-05-14
  issue: 'Deliverable #2 listed retro.md as append target, contradicting rex-format.md which marks it
    deprecated'
  fix: Replaced 'append to retro.md' with 'append to per-tool REX block per rex-format.md'
  severity: info
  ref: DEVLOG#2026-05-14
---

# Archive REX — skill `response-protocol`

Créée le 2026-09-17. Le frontmatter d'un `SKILL.md` est relu par le harnais à
CHAQUE session : une clé hors spec s'y paie à chaque fois, pour une histoire que
rien ne lit au runtime. `validate_rex.py:160-172` l'écrit depuis des semaines et
aucune archive n'existait.
