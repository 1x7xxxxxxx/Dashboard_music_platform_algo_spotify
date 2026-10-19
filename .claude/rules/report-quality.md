---
description: Exigences de tout rapport ou PDF produit dans ce dépôt (norme RQ du parc)
paths: ["**/*report*", "**/*rapport*", "**/*pdf*", "**/*livrable*", "**/reports/**"]
rex: []
---

# Rapports et PDF — la norme RQ

Le propriétaire refuse le « blabla » : un rapport ne contient que ce qui sert une décision ou la
compréhension du problème. Norme complète et sources : `~/.fleet-master/presets/report-quality/README.md`.

**Avant d'écrire ou de régénérer un rapport, un dossier, une revue ou un PDF, applique ces règles :**

1. **Écris la page 1 en premier : `Décision 1 : <geste attendu du lecteur> avant <date>`, puis
   `Recommandation : <option>, parce que <un chiffre>`.** Un document qui ne demande aucune
   décision est un guide : sa page 1 dit ce que le lecteur va faire, ce qu'il obtient et la durée.
2. **Pose le problème sur au moins 4 axes QQOQCP** (Qui, Quoi, Où, Quand, Comment, Combien),
   en tableau, chaque case chiffrée : écart attendu / constaté.
3. **Construis l'arbre des causes 5M** — Matière (données d'entrée), Matériel (machine, infra),
   Méthode (procédure, code), Main-d'œuvre (geste humain), Milieu (environnement, tiers). Examine
   les cinq branches ; écarte une branche par écrit avec sa raison. **Retiens une cause racine**,
   avec sa preuve (mesure, commande, log) et la chaîne des 5 pourquoi.
4. **Classe les solutions : d'abord celles qui suppriment la cause durablement, puis les
   palliatives, marquées « palliatif » avec leur date de fin.** Chaque ligne porte coût (€, h),
   effort, délai, porteur. Fixe les critères de choix avant de lister les options.
5. **Mets au moins un graphique par décision, et donne-lui pour titre son message** (« Le disque
   sature en 6 semaines », jamais « Espace disque »). Charge la skill `dataviz` avant d'écrire le
   code du graphique ; barres plutôt que camembert, pas de 3D, retire tout ce qui n'ôte aucun sens.
6. **Cite la source de chaque chiffre non mesuré et de chaque règle de méthode** : passage
   `mcp__knowledge-rag__search_books` (livre + page), commande de mesure + date, ou lien.
7. **Tiens le budget : ≤ 2 500 mots, ≤ 450 mots par page.** Le détail technique part dans une
   annexe séparée.
8. **Supprime toute phrase sans fait, décision ou action** : pas d'introduction qui annonce le
   plan, pas d'historique de la séance, pas de récapitulatif, pas de « il convient de noter ».
   Pour chaque section, demande-toi quelle décision elle éclaire ; si aucune, supprime-la.
9. **Écris ce qu'on ne sait pas** : hypothèses et risques, une ligne chacun, avec la mesure qui
   trancherait.
10. **Avant de livrer le PDF, lance `python3 ~/.fleet-master/tools/dev/report_quality.py <pdf>
    --strict`** (`--kind guide` pour un mode d'emploi) **et corrige jusqu'à l'exit 0.** Une règle
    que tu juges inapplicable se dit au propriétaire, avec sa raison ; elle ne se tait pas.
