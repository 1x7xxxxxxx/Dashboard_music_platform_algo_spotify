"""Le CPR de Meta mesure un CLIC SORTANT. La phrase qui le dit vit ici, une fois.

Type: Utility
Uses: src.dashboard.utils.i18n
Triggers: toute surface qui rend un CPR, un « résultat » ou une « conversion » Meta
Persists in: nothing

Pourquoi ce module — R146, 2026-09-22
--------------------------------------

`custom_conversions` est l'évènement que la CAPI d'Hypeddit renvoie **quand
l'auditeur QUITTE le smart link** vers Spotify. Personne ne sait s'il a écouté.
Meta optimise donc la diffusion sur ce clic sortant, et le « coût par résultat »
affiché partout dans l'app est un **coût par clic sortant** portant le nom d'un
résultat final.

*Making Websites Win* (Blanks & Jesson) nomme exactement ce défaut :

    « If you are only able to track when someone clicks away from your website,
      you will optimize your business for click-outs, not for conversions. »

Les deux chiffres déjà au dossier, qui ne parlent pas de la même chose :
**0,130 €** par « résultat » d'un côté, **0,001296 €** par écoute réelle mesurée
chez le distributeur de l'autre. Un facteur cent, et la page ne le disait nulle
part.

La sortie choisie
-----------------
Deux issues étaient possibles. Adosser une conversion à une écoute RÉELLE suppose
une remontée temps réel que Spotify for Artists n'expose pas — le produit reçoit
des CSV, pas un flux. Reste **écrire la limite sur la figure** : une limite nommée
coûte moins cher qu'un chiffre qu'on croit comprendre.

Pourquoi un module et pas une phrase recopiée
----------------------------------------------
Le balayage du 2026-09-22 a trouvé **seize grappes de sites vivants** — vues Meta,
tuile d'accueil, optimiseur de budget, argumentaire d'abonnement, export PDF,
catalogues FR et EN — et **six sites déjà honnêtes**, tous dans le même fichier,
écrits le 2026-09-21. La forme correcte existait donc déjà et n'avait pas voyagé.

C'est le motif exact du DEVLOG du 2026-09-22 : « un catalogue recopié trois fois »,
qui a produit deux promesses fausses tenues pendant dix-sept jours. Une phrase
recopiée seize fois se corrige une fois et ment quinze.

Classe : `a-proxy-rendered-under-the-name-of-the-thing-it-proxies`.
"""
from __future__ import annotations

from src.dashboard.utils.i18n import t

# Le mot qui remplace « résultat » / « conversion » partout où la valeur est un
# compte brut de `custom_conversions`. Court, parce qu'il sert d'en-tête de colonne.
def outbound_label() -> str:
    """« Clics sortants » — le nom de la CHOSE, pas de ce qu'on aimerait mesurer."""
    return t("proxy.outbound_label", "Clics sortants")


def cpr_label() -> str:
    """L'en-tête du coût. Il garde « CPR » — c'est le mot de Meta, et l'artiste le
    retrouvera tel quel dans le Gestionnaire de publicités. Ce qui change, c'est
    qu'il ne voyage plus jamais sans son info-bulle."""
    return t("proxy.cpr_label", "CPR (€) — coût par clic sortant")


def cpr_help() -> str:
    """L'info-bulle canonique. Une seule, pour que sa correction soit une seule."""
    return t(
        "proxy.cpr_help",
        "**Un « résultat » ici est un clic qui QUITTE le smart link** vers Spotify "
        "— l'évènement que Hypeddit renvoie à Meta. Ce n'est pas une écoute : "
        "personne ne sait si l'auditeur a lancé le titre. Meta optimise la "
        "diffusion sur ce clic, donc ce coût est un coût par clic sortant, pas un "
        "coût par écoute. Pour le prix d'une écoute réelle, voir la tuile « Coût "
        "par stream » de la page **Meta × Spotify**.",
    )


def outbound_help() -> str:
    """La même limite, pour un COMPTE brut plutôt que pour un coût."""
    return t(
        "proxy.outbound_help",
        "Clics qui quittent le smart link vers la plateforme, remontés par la CAPI "
        "d'Hypeddit. Une écoute n'est pas garantie derrière chacun.",
    )


def disclosure_caption() -> str:
    """La version longue, pour une page entière ou un bas de figure.

    Rendue par `st.caption` là où il n'y a pas d'info-bulle à accrocher — une
    légende de figure, un tableau, une page d'optimiseur.
    """
    return t(
        "proxy.caption",
        "ℹ️ **« Résultat » = un clic sortant vers la plateforme**, pas une écoute. "
        "Les coûts par résultat de cette page se lisent comme des coûts par clic.",
    )


# La même phrase pour le PDF, qui n'a ni info-bulle ni `st.caption` — et qui se
# traduit avec SON traducteur, hors session Streamlit (`_config._t`). On expose donc
# la clé et le défaut séparément : le texte reste à UN endroit, et chaque surface
# le fait passer par le traducteur qui la concerne.
PDF_DISCLOSURE_KEY = "proxy.pdf"
PDF_DISCLOSURE_DEFAULT = (
    "Un « résultat » est un clic sortant vers la plateforme de streaming "
    "(évènement Hypeddit), pas une écoute confirmée."
)


def pdf_disclosure(translate=None) -> str:
    """La phrase du PDF. `translate` est `_config._t` côté export, `t` par défaut.

    Les deux branches sont écrites en toutes lettres — et pas `(translate or t)(…)`
    — parce que `tests/test_i18n.py` cherche un littéral `t("proxy.pdf"` pour
    savoir que la clé est utilisée. Une clé atteinte par une variable est
    invisible au balayage, donc signalée comme orpheline puis supprimée un jour
    par quelqu'un qui aura raison de se fier au garde.
    """
    if translate is None:
        return t("proxy.pdf", PDF_DISCLOSURE_DEFAULT)
    return translate(PDF_DISCLOSURE_KEY, PDF_DISCLOSURE_DEFAULT)
