"""Une date lisible sans ambiguïté dans la langue du lecteur.

Type: Utility
Uses: src.dashboard.utils.i18n.get_lang (import PARESSEUX — voir plus bas)
Triggers: les vues, les légendes de figure, le PDF
Persists in: nothing

LE DÉFAUT QUE CE MODULE FERME — mesuré le 2026-09-22
-----------------------------------------------------
`%d/%m/%Y` était la convention du dépôt : **49 sites, 28 fichiers**. En mode français
elle se lit sans peine. En mode anglais — livré depuis le 2026-06-10, `i18n._LANGS`
porte `en` — elle se lit **à l'envers** :

    04/03/2025   →   4 mars      pour un lecteur français
                 →   3 avril     pour un lecteur anglais

Le même écran, le même pixel, deux dates à un mois d'écart, et **rien ne permet de
trancher**. Le cas ne saute aux yeux que pour un jour au-dessus de 12 — c'est-à-dire
que **deux tiers des dates de l'année sont lues correctement par accident**, ce qui est
la pire fréquence possible : assez rare pour qu'on ne le remarque pas, assez fréquent
pour que ça arrive.

LE REMÈDE : UN MOIS QUI PORTE SON NOM
--------------------------------------
Passer l'anglais en `%m/%d/%Y` ne ferait que déplacer l'ambiguïté — un lecteur qui ne
sait pas dans quelle langue il est reste perdu. **Un nom de mois la supprime**, parce
qu'aucun nombre ne peut être confondu avec « Sep ».

    fr   30/09/2024
    en   30 Sep 2024

⚠️ **L'ORDRE DES CHAMPS EST LE MÊME DANS LES DEUX LANGUES**, et c'est délibéré. La forme
américaine « Sep 30, 2024 » est tout aussi correcte ; celle-ci garde la silhouette
jour-mois-année de la version française, donc quelqu'un qui bascule de langue reconnaît
la même donnée au même endroit au lieu de la relire.

⚠️ **LES NOMS DE MOIS SONT ÉCRITS ICI, PAS DEMANDÉS AU SYSTÈME.** `%b` dépend de la
locale du processus — celle du conteneur, pas celle du lecteur — donc il rendrait
« sept. » à un anglophone sur une image française, et il n'y a aucun moyen de le savoir
avant de le voir. Douze chaînes valent mieux qu'une dépendance invisible à
l'environnement.

⚠️ **L'IMPORT DE `i18n` EST PARESSEUX**, dans le corps des fonctions. `i18n` importe
Streamlit ; ce module est lu par le PDF, qui tourne aussi dans un DAG. Un module partagé
qui importe le tableau de bord est la violation de couche que ce dépôt a payée le
2026-09-22 — `meta_axes` → une vue, **1 073 ms** au premier rendu pour un budget de
287 ms.

CE QUE CE MODULE NE FAIT PAS
-----------------------------
* **Il ne PARSE pas.** `src/transformers/sacem_parser.py` lit `%d/%m/%Y` avec
  `strptime` parce que c'est le format du fichier SACEM : une propriété de la source, pas
  une décision d'affichage. Le garde de R160 l'écarte nommément.
* **Il ne touche pas aux fuseaux.** `to_local_datetime` reste la porte pour ça, et il
  s'applique AVANT ce formateur.
* **Il ne couvre pas les phrases non traduites.** `freshness_monitor` écrit son alerte
  en français en dur ; son format de date est cohérent avec sa langue. Traduire cette
  phrase est un autre travail, porté en roadmap.
"""
from __future__ import annotations

from datetime import datetime

#: Les douze abréviations anglaises. Écrites, pas déduites d'une locale : voir le
#: docstring. L'index 0 est un trou pour que `_MOIS_EN[d.month]` se lise sans -1.
_MOIS_EN = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _lang() -> str:
    """La langue du lecteur, ou le français si rien ne répond.

    Import PARESSEUX de `i18n` : il tire Streamlit, et ce module est lu par le PDF, qui
    tourne aussi dans un DAG. Hors session Streamlit, `get_lang()` lève ou rend son
    défaut ; dans les deux cas on retombe sur `fr`, la langue du produit.
    """
    try:
        from src.dashboard.utils.i18n import get_lang  # noqa: PLC0415
        return get_lang() or "fr"
    except Exception:       # noqa: BLE001 — une date doit s'afficher même sans session
        return "fr"


def format_date(valeur, *, lang: str | None = None, vide: str = "—") -> str:
    """La date, lisible sans ambiguïté, ou `vide` quand il n'y a rien à montrer.

    Accepte un `date`, un `datetime`, un `pandas.Timestamp` — tout ce qui porte
    `.year`, `.month`, `.day`. `None` et les valeurs illisibles rendent `vide` plutôt
    que de lever : une date manquante n'est pas une panne d'écran.
    """
    if valeur is None:
        return vide
    try:
        an, mois, jour = valeur.year, valeur.month, valeur.day
    except AttributeError:
        try:
            v = datetime.fromisoformat(str(valeur)[:19])
        except (ValueError, TypeError):
            return vide
        an, mois, jour = v.year, v.month, v.day
    if not 1 <= mois <= 12:
        return vide
    if (lang or _lang()) == "en":
        return f"{jour:02d} {_MOIS_EN[mois]} {an}"
    return f"{jour:02d}/{mois:02d}/{an}"


def format_datetime(valeur, *, lang: str | None = None, vide: str = "—") -> str:
    """La même date, suivie de l'heure. Le séparateur suit la langue.

    ⚠️ L'heure reste en 24 h dans les DEUX langues. Un `2:05 PM` anglais serait plus
    naturel, et il introduirait une seconde ambiguïté — celle de l'heure — là où ce
    module en ferme une. Le 24 h n'est ambigu nulle part.
    """
    jour = format_date(valeur, lang=lang, vide=vide)
    if jour == vide:
        return vide
    try:
        h, m = valeur.hour, valeur.minute
    except AttributeError:
        return jour
    if (lang or _lang()) == "en":
        return f"{jour} at {h:02d}:{m:02d}"
    return f"{jour} à {h:02d}:{m:02d}"


def format_serie(serie, *, lang: str | None = None, vide: str = "—"):
    """La même chose pour une colonne pandas, sans importer pandas ici.

    ⚠️ La langue est résolue UNE SEULE FOIS, pas par ligne : `get_lang()` lit
    `st.session_state`, et le faire dix mille fois dans un `.map` est un coût qu'aucune
    colonne ne justifie.
    """
    resolue = lang or _lang()
    return serie.map(lambda v: format_date(v, lang=resolue, vide=vide))


__all__ = ["format_date", "format_datetime", "format_serie"]
