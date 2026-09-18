# Deux skills retirées le 2026-09-18 — et la mesure qui l'a décidé

Ce dépôt a mesuré, sur 23 agents et 8 projets, qu'**un composant nommé dans une règle
impérative est invoqué, et qu'un composant nommé nulle part ne l'est jamais** — 33
spawns contre 0. La même loi vaut pour les skills.

## `systematic-debugging/` (300 lignes)

Nommée **dans un bloc commenté** de `.claude/hooks/inject_context.py` (ligne 188, la
ligne commence par `#`), et nulle part ailleurs. Aucun déclencheur, aucune règle.

Son sujet — reproduire, isoler, corriger — est couvert par
`.claude/workflows/bug-resolution.md`, qui est **auto-injecté** sur 56 mots-clés
(`bug`, `traceback`, `régression`, `silent failure`…) et que CLAUDE.md règle 11 rend
obligatoire. Deux documents pour une discipline, dont un que rien n'atteint.

## `verification/` (129 lignes)

Aucune référence vivante : seulement le DEVLOG (historique) et des archives `.rex.md`.
Son sujet — « ne pas déclarer terminé sans une sortie de commande fraîche » — est
encodé dans les règles transverses de CLAUDE.md et dans la discipline de mutation de la
règle 15.

## Ce que « retirée » veut dire

Elles sont **déplacées, pas supprimées** : `git log --follow` les retrouve, et les
remettre est un `git mv`. Le geste est celui que ce dépôt utilise déjà
(`.claude/.retired/`), et il est réversible à la ligne près.

**Le déclencheur de réouverture, écrit pour ne pas avoir à en rediscuter** : si une
séance a besoin de l'une des deux, c'est que le document qui l'a remplacée ne couvrait
pas le cas — on la remet, et on écrit ce que le remplaçant ratait.
