---
globs: [".claude/**/*.md", ".claude/hooks/*.py", ".claude/scripts/*.py"]
rex: []
---

# REX format — {{PROJECT_NAME}} Claude Code config

Chaque outil Claude Code (hook, agent, skill, slash command, rule) porte son propre historique REX **dans son fichier**. Le REX voyage avec l'outil : quand `tools/setup-claude-code.sh` déploie la config vers un autre projet, l'historique est copié par construction. Plus de fichier REX global — `dev-docs/REX.md` et `archives/retro.md` sont désormais des archives en lecture seule.

## Schéma

Une liste `rex` (éventuellement vide) au niveau racine du frontmatter :

```yaml
rex:
  - date: 2026-04-24            # ISO YYYY-MM-DD, obligatoire
    issue: "..."                 # ≤ 120 chars, obligatoire — ce qui a cassé / surpris
    fix: "..."                   # ≤ 200 chars, obligatoire — ce qui a été fait
    ref: "DEVLOG#2026-04-24"    # optionnel — pointeur PR, DEVLOG, brick
    severity: warn               # optionnel (info | warn | crit), défaut info
```

Règles :

- Entrée immuable une fois promue. Pour corriger, ajouter une nouvelle entrée avec `ref:` pointant l'ancienne.
- `date` en UTC (YYYY-MM-DD). Tri chronologique ascendant (plus récent en bas).
- `issue` décrit le symptôme observé, pas le fix. Ex: « Hook swallowed OSError silently », pas « Added try/except ».
- `fix` décrit l'action concrète. Ex: « Replaced bare except with except OSError as e: logger.error(...) ».

## Emplacement par type d'outil

| Type                  | Fichier             | Bloc REX                                                 |
|-----------------------|---------------------|----------------------------------------------------------|
| Agent                 | `.claude/agents/*.md`        | frontmatter YAML existant (ajouter clé `rex:`)       |
| Slash command         | `.claude/commands/*.md`      | frontmatter YAML (créer le bloc `---...---` si absent) |
| Skill                 | `.claude/skills/*.md`        | frontmatter YAML (créer le bloc si absent)          |
| Rule                  | `.claude/rules/*.md`         | frontmatter YAML existant (ajouter clé `rex:`)      |
| Hook                  | `.claude/hooks/*.py`         | bloc YAML dans la docstring de module (voir ci-dessous) |
| Script utilitaire     | `.claude/scripts/*.py`       | bloc YAML dans la docstring de module                |

### Convention pour les fichiers `.py`

La docstring de module (triple-quoted en tête de fichier) contient un bloc YAML délimité par `---` :

```python
#!/usr/bin/env python3
"""
Hook Stop — Session summary.

(free-form description…)

---
rex:
  - date: 2026-04-24
    issue: "Swallowed OSError in _check_observations masked missing dir"
    fix: "Log OSError explicitly, return None"
    severity: warn
---
"""
```

Le validator parse la docstring, extrait le bloc entre `---` et le charge en YAML.

## Flux opérationnel

1. **Capture automatique (fin de session)** — le hook Stop `draft_rex.py` lit `observations.jsonl` + `git diff` et génère `.claude/sessions/pending-rex.md` avec N propositions pré-remplies (fichier cible, timestamp, diff résumé, `issue: ?` et `fix: ?` vides).
2. **Validation humaine** — l'utilisateur édite `pending-rex.md`, remplit `issue` + `fix`, marque `validated: true` sur les entrées à promouvoir.
3. **Promotion** — slash command `/rex-promote` lit `pending-rex.md`, injecte chaque entrée validée dans le bloc `rex:` de l'outil cible, puis supprime ou archive le fichier pending.
4. **Audit** — `.claude/scripts/validate_rex.py` vérifie que chaque outil expose une clé `rex:` (même vide) ; flag les outils sans REX après modifications répétées.

## Ce qui n'est pas un REX par outil

- Decisions architecturales transverses (ex: « <your time-series DB> + PG dual-store », « Redis Streams pour sync event bus ») → restent dans `ROADMAP.md` comme ADR.
- Problèmes purement business code (ex: « acquisition.py log flooding ») qui n'extraient pas une règle pour un outil Claude Code → restent dans `_archived_REX.md`.
- Bugs ouverts / TODOs → `BRICKS.md` ou issue tracker, pas REX. REX capture un apprentissage après fix.

## Contre-exemple

```yaml
rex:
  - date: 2026-04
    issue: "bug"
    fix: "fixed it"
```

Trois erreurs : date incomplète (YYYY-MM seulement), issue et fix trop vagues pour être utiles six mois plus tard. Le validator `--strict` rejette ces entrées.
