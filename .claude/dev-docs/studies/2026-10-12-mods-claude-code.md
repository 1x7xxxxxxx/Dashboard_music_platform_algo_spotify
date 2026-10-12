# Étude M1–M6 — les mods de Claude Code contre notre configuration (2026-10-12)

Question du propriétaire : les « mods » valent-ils une intégration, au vu de trois idées —
un panneau de revue / erreurs / tests dans la séance, un garde contre l'agent qui affirme
« résolu » parce qu'il a modifié du code, et un *Engineering HUD* (tests, erreurs
persistantes, fichiers touchés, tentatives, temps, dépense, CI + commit).

**Critère fixé AVANT la lecture** : intégrer seulement si ça ferme un trou MESURÉ de
l'inventaire ci-dessous, ET qu'un hook ou une statusline ne le fait pas aussi bien. Une
intégration retenue devient une ligne Rnnn ; tant qu'elle n'en a pas, elle n'existe pas.

## Ce que sont les mods — vérifié

Source : doc officielle `code.claude.com/docs/en/plugins/mods/*`. Le corpus
`knowledge-rag` (domaine `claude-code`) ne les mentionne pas : il s'arrête aux plugins et
aux hooks.

- Un mod est un plugin **JavaScript/TypeScript exécuté dans le processus** de Claude Code,
  disponible depuis 2.1.287 (ce poste : 2.1.296). Événements : `tool.call` (peut rendre
  `{deny}`), `turn.start` / `turn.step` / `turn.complete`, `ui.render`. Surfaces : un
  panneau (*Pane*), une bande, une ligne. `/diff` est lui-même un mod livré.
- Limites : **non sandboxé**, 10 s par gestionnaire, **invisible en `claude -p` et en
  séance cloud** — donc invisible des séances de nuit et de CI.
- **`turn.complete` observe, il ne refuse pas** : un mod ne peut pas obliger l'agent à
  continuer. Un hook `Stop` le peut (`{"decision":"block","reason":…}`, borné par
  `stop_hook_active` et un plafond de 8 continuations).

## Inventaire — ce que la configuration fait déjà

- 8 hooks `PreToolUse` en Python, testés, dont `guard_destructive.py` (gestes
  irréversibles, à état) et `require_roadmap_entry.py` (R196) : c'est ce que ferait
  `tool.call`.
- Aucun garde ne comparait la dernière édition au dernier verdict : `session_summary.py`
  (`red_run_hint`) ne lit que le COMPTE de rouges d'un journal de moins d'une heure.
- Aucune statusline.
- Aucune télémétrie OTel de l'agent : ADR-026 adopte Prometheus pour l'APP et refuse
  OTel ; `usage_report.py` lit déjà les transcriptions (appels d'outils, agents, hooks).

## Verdicts

| # | Sujet | Question | Verdict | Pourquoi / déclencheur |
|---|---|---|---|---|
| M1 | Panneau de revue des changements | Faut-il un panneau de revue dans la séance ? | **Rien à construire** | `/diff` est déjà un mod livré, et il fait exactement ça. Rouvrir sur un besoin que `/diff` ne couvre pas, NOMMÉ. |
| M2 | Garde « résolu sans tests » | Un mod peut-il empêcher l'agent d'affirmer « résolu » sur du code non vérifié ? | **Intégrer — hook Stop, pas un mod** → R549 | Un mod ne peut pas refuser une fin de tour ; un hook Stop le peut. C'était le seul trou mesuré : rien ne comparait l'édition au verdict. Décision du propriétaire : bloquer UNE fois par édition. |
| M3 | Engineering HUD | Un panneau mod pour tests / temps / dépense / CI ? | **Intégrer — statusline** → R550 ; panneau mod **plus tard** | La statusline reçoit déjà coût, durée, lignes +/−, contexte ; elle est en Python comme le reste, testable, et visible dans toutes les surfaces interactives. Rouvrir le panneau mod si la barre manque de lignes, ou s'il faut de l'interaction (clic). |
| M4 | Interception `tool.call` en mod | Remplacer des hooks PreToolUse ? | **Rien à prendre** | Les 8 hooks couvrent l'interception et sont testés. Un mod non sandboxé dans le processus serait un risque de plus pour rien. Rouvrir sur un état à garder ENTRE appels qu'un hook commande ne peut pas tenir. |
| M5 | Télémétrie OTel de l'agent | Exporter `claude_code.cost.usage`, `token.usage`… ? | **Plus tard** | ADR-026 ; un seul développeur, et `usage_report.py` lit les transcriptions. Rouvrir à un 2ᵉ développeur, ou sur une question de coût par séance que les transcriptions ne tranchent pas. |
| M6 | État CI/CD « pour une équipe » | Montrer la CI et le commit prêt à livrer ? | **Couvert par M3** (CI du HEAD) ; équipe : **plus tard** | Pour un développeur seul, la CI du HEAD dans la barre suffit. Rouvrir à un 2ᵉ développeur. |

## Suivi — comment la pertinence se mesure

- **R549 (garde Stop)** : chaque blocage est une ligne de
  `.claude/sessions/stop-gate.jsonl` (fichier, état, horodatage). Critère de maintien :
  sur 14 jours, chaque blocage est classé *vrai* (une édition réellement non testée) ou
  *bruit* ; **retrait si le bruit dépasse ⅓**.
- **R550 (statusline)** : le propriétaire dit à la revue si la barre a servi ; sinon
  retrait. Elle ne coûte rien à retirer (une clé de `.claude/settings.json`).
- **La revue est datée et calculée** : la condition `revue des mods` de
  `tools/dev/reopen_check.py` compte les blocages des 14 derniers jours et passe
  **ROUVRIR le 2026-10-26**. `make reopen-check` la montre chaque nuit.
- À la revue : garder / retirer R549 et R550, et relire M1, M3-mod, M5, M6 contre leur
  déclencheur.
