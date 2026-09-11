# La matrice mode × pas — ce que chaque cellule CALCULE

> Écrite le 2026-09-12 (R95). Les trois défauts du 2026-09-11 étaient trois cellules
> de ce tableau que personne n'avait énumérées. Parcourue par
> `tests/test_every_way_of_asking_gives_one_answer.py` et
> `tests/test_a_note_describes_the_figure_that_is_shown.py`.

La figure de l'accueil a **quatre modes** et **trois pas**. Ces contrôles ne sont pas
indépendants : chaque combinaison exige une dérivation différente, et la source de la
plateforme change laquelle.

## Les deux régimes de source

| régime | plateformes | ce que la base porte |
|---|---|---|
| **quantité** | Spotify S4A | des écoutes PAR JOUR, toutes les journées présentes |
| **compteur** | YouTube, SoundCloud | un NIVEAU relevé par intermittence (39 % des jours pour YouTube) |

Apple n'est dans aucun des deux : ses exports sont des totaux de PÉRIODE, donc elle
n'apparaît qu'au pas annuel (`STEP_ONLY`).

## La matrice

| mode \ pas | jour | semaine · année |
|---|---|---|
| **Cumulé** | quantité : somme courante · compteur : **niveau reporté en avant** | idem |
| **Par période** | quantité : la valeur du jour · compteur : **écart entre deux jours consécutifs seulement** | quantité : somme du seau · compteur : **niveau(fin) − niveau(fin précédent)** |
| **Part de chaque plateforme** | pourcentages des valeurs ci-dessus | idem |
| **Chacune à son échelle** | mêmes valeurs que « Par période », une facette par plateforme | idem |

**La seule cellule qui perd de l'information est « Par période × jour × compteur »**, et
c'est délibéré : attribuer à une journée précise l'écart observé entre deux relevés
distants de neuf jours inventerait un pic. C'est la seule cellule où la note
« écoutes non traçables » est vraie — partout ailleurs, le niveau les porte.

## Ce que chaque cellule doit garantir

1. **« Par période » sur tout l'historique totalise la croissance du compteur.**
   Sauf au pas du jour. Violé le 2026-09-11 : 124 contre 18 740, facteur 151.
2. **Le dernier point du mode Cumulé égale le total de la tuile.** Violé : 21 contre
   118 219, facteur 5 630.
3. **Une plateforme servie par la couche or est jugée sur la courbe tracée**, pas sur
   la couverture de sa série quotidienne — sinon elle est écartée comme clairsemée
   avant d'être dessinée.
4. **Aucune note ne contredit la figure.** « n'apparaît pas à ce pas » exige aucune
   trace ; « son aire s'interrompt » exige une couverture partielle de l'axe ;
   « écoutes non traçables » n'est vraie qu'en cellule jour × Par période.

## Les erreurs déjà commises, une par cellule

| cellule | défaut | classe |
|---|---|---|
| Cumulé × tous × compteur | somme courante d'écarts troués | `cumulative-counter-drawn-as-its-own-history` |
| Par période × semaine/année × compteur | somme d'écarts au lieu de dérivation | `a-bucket-sums-deltas-instead-of-deriving-the-counter` |
| toutes | la note décrit l'ancienne figure | `a-note-outlives-the-figure-it-explains` |
