---
globs: [".claude/**/*.md", ".claude/hooks/*.py", ".claude/scripts/*.py"]
rex:
  - date: 2026-05-14
    issue: "Schema doc still mandated manual issue/fix fill after /rex-promote was rewritten\
  \ to auto-generate them"
    fix: "Added \xA7 'Auto-fill via /rex-promote' documenting the 4 context sources and the\
  \ lifted rule; renumbered flow (auto-promote \u2192 manual fallback \u2192 audit)"
    severity: "info"
    ref: "DEVLOG#2026-05-14"
  - date: 2026-05-14
    issue: "Strict 'human owns content' rule contradicted the new /rex-promote auto-fill flow\
  \ introduced same session"
    fix: "Added '\xA7 Auto-fill via /rex-promote' documenting lifted contract; format constraints\
  \ (date, char limits, severity, target dirs) still enforced by validate_rex.py"
    severity: "info"
    ref: "DEVLOG#2026-05-14"
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
2. **Promotion automatique** — slash command `/rex-promote` (depuis 2026-05-14) auto-remplit `issue` + `fix` à partir du contexte de session puis injecte dans le bloc `rex:` de l'outil cible en un seul appel. Voir § « Auto-fill via /rex-promote » ci-dessous.
3. **Fallback manuel** — éditer `pending-rex.md` à la main (remplir `issue`/`fix`, marquer `validated: true`) puis appeler `python3 .claude/scripts/promote_rex.py` directement. Le script (aussi câblé au Stop hook chain) refuse les entrées avec stubs `?` ou `validated: false`.
4. **Audit** — `.claude/scripts/validate_rex.py` vérifie que chaque outil expose une clé `rex:` (même vide) ; flag les outils sans REX après modifications répétées.

### Auto-fill via `/rex-promote`

Depuis 2026-05-14, le slash command `/rex-promote` peut générer lui-même `issue` + `fix` (+ `severity`, + `ref` optionnel) à partir de 4 sources de contexte :

1. Snippets `edit.old` / `edit.new` (80 chars chacun) capturés dans `.claude/homunculus/<repo>/observations.jsonl`
2. `git log --since=<session_start>` et `git diff HEAD` du fichier cible
3. Relecture intégrale du fichier post-edit
4. Dernière entrée de `.claude/dev-docs/DEVLOG.md` (pour la `ref:` si la date du jour matche un header)

Le command promeut ensuite avec `validated: true` sans intervention humaine. Cela lève la règle historique « the human owns the content » pour ce flux automatique, tout en conservant :

- l'immutabilité post-promotion (corrections = nouvelle entrée avec `ref:` pointant l'ancienne)
- les contraintes de format (date ISO `YYYY-MM-DD`, `issue` ≤ 120 chars, `fix` ≤ 200 chars, `severity ∈ {info, warn, crit}`) — enforced par `validate_rex.py`
- l'allowlist de dossiers cibles (`.claude/{agents,skills,commands,rules,hooks,scripts}`)

Si une suggestion auto-générée viole les contraintes, le command reformule 1× ; sinon skip avec `reason: schema violation after 1 retry` (l'humain corrige manuellement). Pour conserver le contrat strict d'origine (zéro auto-fill), utiliser le fallback manuel décrit au point 3.

## Ce qui n'est pas un REX par outil

- Decisions architecturales transverses → vont dans `docs/adr/` comme fichiers ADR-0NN (il n'y a pas de `ROADMAP.md` dans ce repo ; la source unique est `.claude/dev-docs/roadmap/checklist.md`).
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
