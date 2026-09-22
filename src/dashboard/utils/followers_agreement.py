"""Les deux sources d'abonnés disent-elles la même chose ?

Type: Sub
Uses: rien (pur — ni Streamlit, ni base)
Triggers: views/spotify_s4a_combined.py
Persists in: nothing

POURQUOI UNE SEULE COURBE, ET POURQUOI UN DÉTECTEUR AVEC
---------------------------------------------------------
La figure traçait DEUX séries d'abonnés — le CSV Spotify for Artists et l'API — jamais
raboutées, avec une légende qui expliquait pourquoi. Demandé le 2026-09-23 : « ne mets
pas 2 sources pour abonnés, mets en place un garde qui nous confirme que les 2 sont
bien les mêmes sinon alerte ».

**La mesure donne raison à la demande**, relevée sur l'artiste 1 le 2026-09-23 :

    s4a_csv        889 jours    2024-01-01 → 2026-06-07
    spotify_api     48 jours    2025-11-23 → 2026-09-20
    jours COMMUNS   32
    jours qui divergent          5
    écart MAXIMUM                1 abonné   (sur ~684, soit 0,15 %)

Deux sources qui se recouvrent sur 32 jours et ne s'écartent jamais de plus d'un
abonné mesurent la même chose. Les tracer séparément demandait au lecteur de faire un
travail — décider si l'écart compte — dont la réponse est toujours « non ».

⚠️ MAIS « ELLES S'ACCORDENT AUJOURD'HUI » N'EST PAS « ELLES S'ACCORDERONT ». C'est
exactement ce que la demande a vu : raccorder deux sources sans rien qui surveille le
raccord, c'est fabriquer une courbe qui mentira le jour où l'une des deux dérivera, et
qui mentira EN SILENCE. Le détecteur est donc la condition de la fusion, pas un
supplément.

LE SEUIL, ET POURQUOI IL EST RELATIF
-------------------------------------
`TOLERANCE_ABSOLUE = 2` et `TOLERANCE_RELATIVE = 0.005`, le plus permissif des deux
gagnant. Deux raisons, et la seconde est la vraie :

  * l'écart mesuré vaut **1**, donc 2 laisse exactement un cran de marge pour un
    décalage d'heure de relevé — le CSV est un instantané d'export, l'API lit à son
    heure de cron ;
  * un compte d'abonnés CROÎT. Un seuil purement absolu qui convient à 684 abonnés
    serait absurde à 68 000 : 0,5 % vaut 3 aujourd'hui et 340 demain. Un seuil fixe
    sur une grandeur qui change d'ordre est un seuil qui se périme sans le dire —
    `un-seuil-écrit-d-instinct`, neuf classes au catalogue.

⚠️ CE QUE CE MODULE NE FAIT PAS
--------------------------------
* **Il ne choisit pas la source.** Il compare ; c'est l'appelant qui décide laquelle
  garder là où les deux existent.
* **Il ne voit pas une dérive LENTE.** Deux sources qui s'écartent d'un abonné par mois
  restent sous le seuil pendant des années. Le détecteur attrape une RUPTURE, pas un
  glissement — et le dire est le point, parce qu'un détecteur dont on croit qu'il voit
  tout est pire qu'un détecteur absent.
* **Il ne dit rien des jours NON communs.** Si les deux sources cessent de se recouvrir,
  il n'a plus rien à comparer et rend « aucun jour commun ». L'appelant doit traiter ce
  cas, qui n'est pas « elles s'accordent ».
"""
from __future__ import annotations

from typing import NamedTuple

#: L'écart toléré en valeur absolue. Mesuré à 1 le 2026-09-23 ; 2 laisse un cran.
TOLERANCE_ABSOLUE = 2

#: L'écart toléré en part du niveau. C'est LUI qui porte la règle quand le compte
#: d'abonnés change d'ordre de grandeur.
TOLERANCE_RELATIVE = 0.005


class Accord(NamedTuple):
    """Ce que la comparaison a trouvé — et de quoi elle n'a rien pu dire."""

    jours_communs: int
    jours_divergents: int
    ecart_max: int
    jour_pire: object | None
    niveau_pire: int
    #: `True` quand tout écart observé tient dans la tolérance. ⚠️ `jours_communs == 0`
    #: rend `False` ici : « on n'a rien pu comparer » n'est pas « elles s'accordent ».
    accord: bool

    @property
    def tolerance_au_pire(self) -> float:
        return max(TOLERANCE_ABSOLUE, TOLERANCE_RELATIVE * self.niveau_pire)


def comparer(lignes) -> Accord:
    """Compare les deux sources sur les jours où les DEUX ont une valeur.

    `lignes` : un itérable de `(jour, source, abonnés)`. Pur, donc testable sans base.
    Une source dont le nom contient `csv` est le CSV ; toute autre est l'API.
    """
    par_jour: dict = {}
    for jour, source, n in lignes:
        if n is None:
            continue
        cle = "csv" if "csv" in str(source).lower() else "api"
        par_jour.setdefault(jour, {})[cle] = int(n)

    communs = [(j, v["csv"], v["api"]) for j, v in par_jour.items()
               if "csv" in v and "api" in v]
    if not communs:
        return Accord(0, 0, 0, None, 0, False)

    divergents = [(j, c, a) for j, c, a in communs if c != a]
    pire = max(communs, key=lambda x: abs(x[1] - x[2]))
    ecart = abs(pire[1] - pire[2])
    niveau = max(pire[1], pire[2])
    seuil = max(TOLERANCE_ABSOLUE, TOLERANCE_RELATIVE * niveau)
    return Accord(len(communs), len(divergents), ecart, pire[0], niveau, ecart <= seuil)
