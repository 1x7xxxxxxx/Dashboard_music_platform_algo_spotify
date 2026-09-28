# `strategic-plan-architect` retiré le 2026-09-25 — et la mesure qui l'a décidé

## Ce qui a été mesuré

`.venv/bin/python .claude/scripts/usage_report.py`, lancé le 2026-09-25 depuis le dépôt
principal, lit **51 sessions** et rend :

    strategic-plan-architect   0   🔴 DECLARED, NEVER INVOKED
    1/8 declared agents never invoked

Dans la même lecture : `sibling-sweeper` 39, `roadmap-keeper` 27, `code-critic` 20.

⚠️ **La fenêtre.** Ces 51 transcriptions couvrent 2026-08-26 → 2026-09-25 ; aucune
transcription de l'époque `/mnt/c` n'a survécu. « 0 » vaut pour ces 51 sessions, pas
pour toute l'histoire : la docstring de `usage_report.py` relevait **6** appels le
2026-07-17, dans des transcriptions purgées depuis.

## Pourquoi rien ne le lançait

La règle 5 de `CLAUDE.md` disait : « Spawn `strategic-plan-architect` only after ≥3
files changed in one session. Not after single-file edits. » C'est une **restriction**
(« seulement après », « pas après »), pas un déclencheur : pas de flèche, pas d'évènement
qu'un hook émette. C'était la seule règle d'agent à enfreindre la forme que `CLAUDE.md`
impose lui-même aux règles 12-13 — une flèche, un déclencheur vérifiable mécaniquement,
le verbe `Spawn`, un contrat de sortie. Aucun hook de `.claude/hooks/` ne le nommait.

## Ses quatre devoirs ont chacun un propriétaire vivant

| devoir | propriétaire | preuve |
|---|---|---|
| `checklist.md` / `archive.md` | `roadmap-keeper` | règle 17, forme fléchée ; 27 appels dans la même fenêtre |
| DEVLOG | `.claude/hooks/draft_devlog.py` (Stop) | déterministe, au MÊME seuil de ≥3 fichiers — mais sur le code (`src/`, `airflow/`, `migrations/`, `tests/`, `docs/`), pas sur l'outillage `.claude/` |
| REX colocalisé | `.claude/hooks/draft_rex.py` + `/retro` + `/rex-promote` | hook Stop enregistré dans `.claude/settings.json` |
| diagrammes Mermaid | `code-architecture-reviewer` | règle 18, forme fléchée |

## Ce que ses instructions auraient fait aujourd'hui

- **Mermaid** (ligne 22 du fichier) : « update `architecture/macro_architecture.md` » —
  ce chemin n'existe plus dans l'arbre vivant ; le fichier vit sous
  `.claude/.retired/dev-docs/architecture/`. Une invocation aurait visé un fichier absent.
- **Suite de tests** (ligne 26) : « run `python3 -m pytest tests/ -q` » — la forme nue,
  sérielle, que `CLAUDE.md` interdit (1 146 s mesurés sur `/mnt/c`).
- **REX** (ligne 21) : **pas un défaut**. Le texte dit déjà « do NOT write to
  `archives/retro.md` (frozen) » et renvoie à `/retro`. Il est juste, et redondant avec
  `draft_rex.py`.

## Pourquoi le retrait plutôt qu'un déclencheur

- **Un hook qui imprimerait « Spawn strategic-plan-architect » à ≥3 fichiers** doublerait
  exactement `draft_devlog.py` : deux voix pour un évènement, et un agent ranimé avec des
  instructions fausses.
- **Fondre son devoir DEVLOG dans `roadmap-keeper`** élargirait le contrat d'un agent qui
  marche, pour un devoir qu'un hook fait déjà de façon déterministe.
- **Le retrait** ne coûte aucune couverture et retire une fausse affirmation de
  couverture — « un outil que rien n'invoque n'est pas neutre : c'est une affirmation
  qu'une chose est couverte » (`.claude/workflows/continuous-improvement.md`).

## Le garde qui manquait

`usage_report.py` annonçait que `tests/test_claude_config.py` « échoue désormais sur un
agent déclaré et inutilisé ». Ce fichier a été renommé, et le test n'a jamais existé.
Il existe maintenant :
`tests/test_claude_config_floor.py::test_every_declared_agent_has_a_trigger_that_can_fire`
— tout agent de `.claude/agents/` doit être nommé dans une règle fléchée de `CLAUDE.md`
(`→ … Spawn <nom>`, lue sur le texte ENTIER de la règle, retours à la ligne compris) ou
comme `subagent_type`/`agentType` d'un workflow `.claude/workflows/*.js`. Il prouve que
l'arête est DESSINÉE, pas qu'elle LIE : la preuve d'exécution reste
`usage_report.py --check`, branché dans `make config-check`.

## Ce que « retiré » veut dire

Déplacé, pas supprimé : `git log --follow` le retrouve, et le remettre est un `git mv`.

**Déclencheur de réouverture** : un devoir de documentation qu'aucun hook ni aucune
règle fléchée ne possède. Si on le remet, on lui écrit d'abord une règle fléchée — et on
corrige ses lignes 22 et 26.
