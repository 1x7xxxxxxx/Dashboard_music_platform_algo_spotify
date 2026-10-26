---
rex: []
---

# Déclencheurs des agents — écrit par fleet_apply (agent-triggers, T148)

Un agent de `.claude/agents/` qu'aucune autre règle ne nomme n'est jamais invoqué. Écrire sa règle dans CLAUDE.md le retire d'ici au passage suivant.

1. **Un design de correctif à juger HORS de la boucle d'ingénierie — une trouvaille seule qui touche un
   garde, un installeur ou une frontière irréversible, ou un refactor de plus de 3 fichiers → `Spawn
   code-critic` sur le DESIGN, avant la première ligne.** Il rend `BUILD`, `BUILD-MODIFIED` ou
   `DO-NOT-BUILD`, avec la raison ; dans la boucle, c'est elle qui le lance (phase Critic).
