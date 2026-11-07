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
11. **Donne à chaque graphique et à chaque page pour titre ce qu'on veut prédire ou la valeur
    ajoutée** (« La purge rend 11 Go dimanche », jamais « Cache images »), **et dis son état en
    vert, orange ou rouge** : vert tenu, orange à surveiller, rouge à traiter. Cette règle vaut
    pour les PDF ; la barre d'état garde ses trois couleurs d'état (REQ-PARC-75).
12. **Mets le minimum de texte** : un chiffre et son graphique plutôt qu'un paragraphe.
13. **Dépose le PDF sur le Bureau pour validation, jamais ailleurs.** Validé par le propriétaire
    (bouton Valider du panneau, ou `python3 ~/.fleet-master/tools/dev/validation_pdf.py validate
    <pdf>`), il porte la mention validé, part dans le dossier d'archive du dépôt et quitte le Bureau.
    Aucun test unitaire n'écrit sur le contenu ou la mise en page d'un PDF : le propriétaire juge.
14. **À la demande d'un PDF, recueille le besoin avant d'écrire, et pose d'un coup tout ce que seul
    le propriétaire sait** : la décision attendue, qui la prend et pour quand ; ce qui est dedans,
    dehors et déjà tranché ; le contexte de départ (matériel possédé, contraintes, budget) ; le
    format de lecture ; ce qui doit être sourcé ; ce que le lecteur connaît déjà. Écris-le dans le
    PDF, section `Cadrage de la demande` : Problème, Besoin, Contexte, Hors périmètre, Impact,
    Critique, Vérification, Reste à demander. Sur 28 révisions dont la cause est connue, 16 étaient
    évitables (`~/.fleet-master/docs/decisions/PDF-REVISIONS.md`).
15. **À chaque révision, écris dans la roadmap ce qui a manqué, avec la phrase du propriétaire.**
    Un seul rendu par jeu de retours.
16. **PDF d'achats** : deux URL par article, la conseillée en gras selon la note du vendeur, le
    rapport qualité-prix et le prix. Vise le prix total du panier, TVA et port compris, en
    regroupant sur une plateforme quand le stock le permet. Deux propositions pour un même besoin
    forment un bloc à part, avec une seule case et le conseil écrit. Un composant suivi porte un
    prix cible et un relevé daté sur un an ; ne nomme une fenêtre d'achat qu'après un an lu.
    Vérifie l'occasion entre particuliers pour chaque article, sauf si le dépôt a écrit que ses
    équipements s'achètent neufs. Choisis la plateforme de batteries avant les appareils.
