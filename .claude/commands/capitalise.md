---
description: "Transforme un défaut corrigé en classe d'erreur durable, avec une signature shell qui la détecte."
rex: []
---

# /capitalise

Un défaut corrigé une fois revient. Une classe écrite avec une signature qui la
détecte ne revient pas sans qu'on le sache.

## Ce que je fais

J'écris une entrée au schéma du catalogue, et je **valide sa signature par
exécution** avant de la livrer :

| Champ | Ce que j'y mets |
|---|---|
| `status` | `open` → `reported` → `guarded` → `resolved` |
| `kind` | `deterministic` si la signature n'a pas de faux positif, sinon `heuristic` |
| `signature` | une commande shell, **sortie ≠ 0 quand la classe est touchée** |
| `root_cause` | une ligne, `fichier:ligne` quand ça se lit dans le code |
| `long_term_fix` | le changement qui rend la classe *impossible*, ou `— (le garde EST le fix)` |
| `guard` | le test ou le hook qui bloque, ou `—` |
| `history` | daté, ce qui s'est passé |

## La seule étape non négociable

**Je lance la signature deux fois avant de l'écrire :**

- sur un arbre où le défaut est **présent** (`git stash`, une copie, ou en le
  remettant à la main) — elle doit sortir **≠ 0** ;
- sur l'arbre corrigé — elle doit sortir **0**.

Une signature qui n'a jamais été vue rouge n'a pas été testée : elle garde
peut-être, ou elle ne peut simplement pas échouer, et rien dans son texte ne
permet de trancher. Si je ne peux pas produire les deux exécutions, je livre la
classe en `kind: manual` **sans** signature plutôt qu'avec une signature non
vérifiée — une fausse garantie coûte plus cher qu'une absence de garantie.

**Et elle lit du code, pas du texte.** Une signature `deterministic` restreint sa
recherche aux fichiers de code (`--include`) et ne doit pas pouvoir matcher un
commentaire — sinon **écrire sur le défaut le fait rougir**, y compris le
commentaire qui explique le correctif. Vu le 2026-08-03 : une classe passait au
rouge sur les commentaires de son propre fix, donc la seule façon de garder la CI
verte était d'arrêter de documenter. Une deterministic bloque la CI par contrat ;
une qui bloque sur un commentaire apprend que le rouge peut être du bruit, et la
leçon est appliquée aux autres. Contrôle : `audit_runner.py --prose`.

## Ce que je ne fais pas

- Je ne recopie pas un narratif dans un champ structuré : la prose contient des
  causes **rétractées trois lignes plus bas**, et la structure les blanchirait en
  faits. Je lis, je tranche, et je dis quand je ne suis pas sûr.
- Je ne touche ni à la ROADMAP, ni au code.
