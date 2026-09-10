# Le dossier d'architecture et de qualité des données

Génère `docs/streamlytics-architecture-et-qualite-des-donnees.pdf` — 26 pages,
20 schémas.

**Le PDF n'est pas versionné**, et c'est délibéré : il pèse ~1,1 Mo, au-dessus du
plafond de 1 Mo que `check-added-large-files` fait respecter sur ce dépôt. Un binaire
dérivé qui grossit à chaque régénération est exactement ce que ce plafond existe pour
tenir à distance. Le générateur, lui, est petit et se relit.

## Générer

```bash
cd tools/dev/architecture_dossier
python3 main.py ../../../docs/streamlytics-architecture-et-qualite-des-donnees.pdf
```

`main.py` est l'entrée — **pas `build.py`**, qui ne définit que le rendu mermaid et sort
en silence avec le code 0 si on l'exécute seul. Le 2026-09-10 j'ai lancé `build.py`, vu
`rc=0`, et cru le dossier régénéré : il datait de quatre heures. Un script qui sort 0 en
n'ayant rien fait est indiscernable d'un script qui a réussi, et ce README ne portait
aucune commande — c'est ce qui a rendu la confusion possible.

Sans argument, `main.py` écrit `dossier.pdf` à côté de lui. Il laisse aussi
`dossier.html` : c'est là qu'on vérifie ce qui a été rendu, l'extraction de texte d'un
PDF à polices sous-ensemblées ne le dit pas de façon fiable.

## Ce que la chaîne apprend, et qu'il faut savoir avant d'y toucher

Cinq défauts de rendu ont été trouvés **en regardant les pages**, jamais en lisant le
code — c'est pourquoi ils sont écrits ici plutôt que découverts une deuxième fois.

| Symptôme | Cause | Ce qu'on fait |
|---|---|---|
| Les boîtes des schémas sortent **vides** | mermaid pose ses libellés dans un `foreignObject` HTML, que WeasyPrint ignore | `htmlLabels: false` — les libellés deviennent du `<text>` SVG |
| `<i>` et `<b>` s'impriment **littéralement** | conséquence du point précédent : sans libellés HTML, les balises sont du texte | aucune balise dans un libellé mermaid ; `<br/>` reste géré |
| Un diagramme de Gantt sort en **bande écrasée illisible** | dix tâches courtes sur dix-neuf heures donnent un SVG très large et très plat, qui s'écrase à l'échelle de la colonne | la frise horaire est construite en CSS |
| Les libellés d'axe vertical sortent **en miroir** | `writing-mode: vertical-rl` n'est pas rendu correctement | libellés d'axe à plat, au-dessus et au-dessous |
| Un repère positionné en `left: %` se colle à **l'origine** | `position:absolute; left:%` ne se résout pas dans un élément de ligne | décalage par `margin-left: %` |
| Un émoji sort **blanc ou disparaît** | aucune police emoji dans la chaîne — l'image de base n'embarque aucune police | pas d'émoji dans le document |

La dernière ligne vaut aussi pour le rapport client, et elle y a été corrigée le même
jour : le rapport portait vingt-neuf émojis dont un seul s'imprimait.
