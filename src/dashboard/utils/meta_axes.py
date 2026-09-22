"""Où part l'argent des publicités, et ce que ça coûte de le mal placer.

Type: Sub
Uses: rien (pur — ni Streamlit, ni base)
Depends on: utils/meta_confidence.MIN_DEPENSE pour le plancher de fiabilité
Triggers: views/home_meta_advice.py
Persists in: nothing

Pourquoi ce module est PUR
---------------------------
Même raison que `trigger_algo/_reglages.py` : un classement qui décide où mettre de
l'argent doit s'éprouver sur des valeurs, pas au navigateur. Il reçoit des lignes
agrégées, il rend des écarts. Aucun `db`, aucun `st`.

LE RANG SE FAIT SUR LES EUROS, PAS SUR LE FACTEUR
--------------------------------------------------
Un ×3 sur 40 € engagés ne coûte rien ; un ×1,3 sur 1 400 € coûte cher. Classer sur le
rapport des coûts produit un rapport ; classer sur ce que l'écart COÛTE produit une
décision. Mesuré sur le catalogue de l'artiste 1 le 2026-09-22 :

    pays        ×1,92   le rapport le plus spectaculaire
    âge         ×1,67   mais 1 963 € sur 2 340 partis sur les deux tranches les
                        plus chères, et la meilleure n'en a reçu que 167
    placement   ×1,27

⚠️ LE PLANCHER DE FIABILITÉ, ET CE QU'IL M'A ÉVITÉ DE PUBLIER
--------------------------------------------------------------
`MIN_DEPENSE` est importé de `utils/meta_confidence`, pas recopié. Ce n'est pas un seuil de
modèle : c'est « la borne en dessous de laquelle le classement de CE catalogue
s'inverse d'une annonce à l'autre ».

Le 2026-09-22, avant de l'appliquer, j'avais mesuré le « meilleur pays » à **0,0528 €
aux États-Unis** — sur **31 €** dépensés — et j'en avais tiré un titre. Avec le
plancher, le meilleur pays devient l'Allemagne à 0,1016 € et le facteur passe de ×3,7
à ×1,92. **Le plancher inverse le classement**, et il a intercepté un chiffre que
j'allais écrire à l'écran en citant le module qui existe pour l'empêcher.

⚠️ CE QUE LE PLANCHER N'ATTRAPE PAS — le clic qui ne vaut rien
---------------------------------------------------------------
Sur l'axe des placements, la ligne la moins chère est
`audience_network/rewarded_video` à **0,0182 €** — sept fois moins cher que Reels, et
statistiquement solide (818 résultats, confiance 0,73). Mais ce sont des clics posés
pour obtenir une récompense de jeu : **le clic existe, l'intention non.**

Le plancher de dépense l'écarte ici par chance (15 €), pas par construction. C'est
pourquoi la réserve de `proxy_disclosure` — « un résultat est un clic qui QUITTE le
smart link, pas une écoute » — doit voyager avec chaque chiffre de ces axes. Un
classement de coût par clic ne sait pas ce qu'un clic vaut.
"""
from __future__ import annotations

from typing import NamedTuple

from src.dashboard.utils.meta_confidence import MIN_DEPENSE


class Ligne(NamedTuple):
    """Une valeur d'un axe, avec ce qu'elle a coûté et rapporté."""

    valeur: str
    depense: float
    resultats: float


class Ecart(NamedTuple):
    """Ce qu'un axe révèle : son meilleur, son pire, et le prix de l'écart.

    `gaspillage` est la somme, sur les lignes fiables, de ce que chacune a coûté
    AU-DESSUS du meilleur coût constaté. C'est un ordre de grandeur, jamais un
    devis : il suppose que le volume aurait suivi au meilleur coût, ce que rien ne
    garantit. Le mot « environ » n'est pas une politesse.
    """

    dimension: str
    meilleur: str
    cpr_min: float
    pire: str
    cpr_max: float
    facteur: float
    gaspillage: float
    fiables: int


def _cpr(ligne: Ligne) -> float | None:
    """Le coût par résultat, ou `None` quand la division n'a pas de sens."""
    if not ligne.resultats:
        return None
    return ligne.depense / ligne.resultats


def ecart(dimension: str, lignes: list[Ligne],
          plancher: float = MIN_DEPENSE) -> Ecart | None:
    """L'écart de cet axe, ou `None` quand il n'y a rien à en dire.

    Rend `None` — jamais un écart vide — dans deux cas, et les deux sont des
    réponses :

      * moins de DEUX lignes fiables. « Un meilleur sans rival mesuré n'est pas un
        enseignement, c'est la seule chose qu'on ait essayée. »
      * un écart nul : toutes les lignes au même coût, donc rien à déplacer.
    """
    fiables = [(le, c) for le in lignes
               if le.depense >= plancher and (c := _cpr(le)) is not None]
    if len(fiables) < 2:
        return None

    fiables.sort(key=lambda x: x[1])
    (meilleure, cpr_min), (pire, cpr_max) = fiables[0], fiables[-1]
    if cpr_max <= cpr_min:
        return None

    gaspillage = sum(le.depense * (c - cpr_min) / c for le, c in fiables if c > cpr_min)
    return Ecart(dimension=dimension,
                 meilleur=meilleure.valeur, cpr_min=cpr_min,
                 pire=pire.valeur, cpr_max=cpr_max,
                 facteur=cpr_max / cpr_min,
                 gaspillage=gaspillage,
                 fiables=len(fiables))


def classer_axes(axes: dict[str, list[Ligne]],
                 plancher: float = MIN_DEPENSE) -> list[Ecart]:
    """Les axes qui ont quelque chose à dire, le plus COÛTEUX d'abord.

    ⚠️ Le tri est sur `gaspillage`, en euros — jamais sur `facteur`. C'est toute la
    différence entre un rapport et une décision : un rapport de coûts spectaculaire
    sur une poignée d'euros n'appelle aucun geste.
    """
    trouves = [e for nom, lignes in axes.items()
               if (e := ecart(nom, lignes, plancher)) is not None]
    trouves.sort(key=lambda e: -e.gaspillage)
    return trouves
