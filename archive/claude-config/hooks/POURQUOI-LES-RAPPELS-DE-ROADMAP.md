# Pourquoi `check_roadmap_update.py` et `draft_roadmap.py` sont retirés (2026-09-26, R201)

Deux hooks qui RAPPELAIENT de tenir la roadmap, sans rien garantir :

- `check_roadmap_update.py` (PostToolUse Write|Edit) : un rappel non bloquant quand
  `checklist.md` n'avait pas bougé depuis 5 minutes après une édition de `src/`.
- `draft_roadmap.py` (Stop) : proposait des lignes à partir des « Ouvert : / Reste : » des
  messages de commit. Mesuré : **0 telle ligne dans les 50 commits depuis le 2026-09-01**, et
  sa sortie (`.claude/sessions/pending-roadmap.md`) n'était lue par rien.

Ils sont rendus redondants par les trois barrières de **R196** — l'édition de code produit
refusée sans ligne ouverte (`require_roadmap_entry.py`), le commit refusé sans Rnnn ouvert
AVANT lui (`tools/dev/require_roadmap_id.py`), le job CI `roadmap` — et par la sonde **R197**
(`make roadmap-discipline`, chaque nuit et dans le récap du matin). Un rappel à côté d'un
garde n'ajoute que du bruit, et un rappel qu'on apprend à sauter apprend à sauter les autres.

Retrait réversible : `git mv` depuis `.claude/hooks/`, avec son test
(`test_a_session_action_is_proposed_for_the_roadmap.py`, rangé ici).

**Rouvrir si** la sonde R197 montre des actions de dev sans inscription préalable qui
échappent aux trois barrières (par exemple du travail hors `src/`, `airflow/dags/`,
`migrations/` qui aurait dû être inscrit) — un rappel à la fin de séance redeviendrait alors
le seul filet pour ce périmètre.
