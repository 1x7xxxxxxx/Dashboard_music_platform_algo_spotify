---
keywords: modulaire, modularité, scalable, scalabilité, scalability, modular, exigence, exigences, requirement, domaine micro, référentiel, benchmark d'architecture, une seule définition, même filtre, mêmes filtres, mêmes légendes, même format, couche or, couche argent, bronze argent or
strong_keywords: exigence d'architecture, arch-benchmark, référentiel d'architecture
rex: []
---

# Workflow — une exigence d'architecture

Injecté quand la demande parle de modularité, de scalabilité ou d'une règle transverse
(« mêmes filtres partout », « une seule définition par KPI »). **Le lire, puis l'exécuter.**

| # | Étape | Porteur | Type |
|---|------|---------|------|
| 1 | Trouver le domaine touché | `.claude/dev-docs/architecture/domains.yaml` — fichiers, gardes, mesures | playbook |
| 2 | Lire ses exigences et leur verdict du jour | `requirements.yaml` + `make arch-benchmark` (ou `NO_RUN=1`) | commande |
| 3 | La demande est-elle une exigence nouvelle ? | oui → entrée au catalogue : source (note `Lnnn`, ADR, livre + page), statut, UNE preuve ciblée ou `a_ecrire` | playbook |
| 4 | Une note du propriétaire ? | `notes-triage.yaml` : statut vérifié dans le code, ligne de roadmap réelle | playbook |
| 5 | Le livrable | ligne Rnnn AVANT le code (R196), critic si structure (verdicts : `critic-2026-09-27.md`), test muté rouge | hook + pytest |
| 6 | Relancer le benchmark | une preuve rouge sur un « conforme » s'imprime RÉGRESSION | commande |

La preuve se rejoue sur une ligne précise : lancer le nœud pytest seul, appliquer la
`mutation` déclarée sur SA ligne, voir la preuve rougir, restaurer (`git status` propre).
