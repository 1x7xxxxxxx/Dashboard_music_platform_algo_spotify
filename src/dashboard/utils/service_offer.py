"""L'offre de prestation : trois options, et QUI fait le travail sur chaque ligne.

Type: Sub
Uses: rien à l'exécution (données pures + une résolution de prix)
Depends on: src.dashboard.utils.app_settings (les trois prix sont des réglages)
Triggers: views/service.py, views/billing.py, views/upgrade.py
Persists in: nothing

Pourquoi ce module — et pourquoi il ressemble à `plan_pitch.py`
---------------------------------------------------------------
L'offre vivait à DEUX endroits qui divergeaient déjà : `views/billing.py` (quatre
puces, deux boutons, tutoiement) et `views/upgrade.py` (une ligne, pas de Calendly,
pas de puces, vouvoiement, et un `subject:` de mail différent). C'est la classe
« un catalogue recopié », que ce dépôt a payée trois fois — la dernière le
2026-09-22, avec deux promesses fausses tenues dix-sept jours.

`plan_pitch.py` a réglé le même problème pour l'abonnement : la donnée descend dans
un module, les surfaces la LISENT. Celui-ci est son jumeau pour la prestation.

LA DISTINCTION QUI TIENT TOUT LE FICHIER
-----------------------------------------
Chaque livrable déclare son **agent** :

    "humain"  ce que le propriétaire fait lui-même — n'a rien à prouver dans le code
    "outil"   ce que le logiciel fait — DOIT exister dans l'arbre

Ce n'est pas une nuance de rédaction, c'est la règle déjà écrite dans
`database/stripe_schema.py:104-108`, et c'est elle qui rend légitime de vendre des
créatives vidéo ici alors que `tests/test_the_plan_pitch_matches_the_gate.py:215`
l'interdit dans un plan : rien dans l'arbre ne produit de vidéo, mais un humain,
lui, en produit.

⚠️ Mesuré le 2026-09-22 avant d'écrire une ligne de cette offre :

    envoi automatique de CSV périodique   N'EXISTE PAS — aucun DAG n'envoie de CSV
    génération de créatives               N'EXISTE PAS — ni ffmpeg, ni moviepy
    rapport PDF périodique                EXISTE, mais UNE FOIS par artiste
                                          (`airflow/dags/onboarding_report.py:97-108`)

D'où la formulation : un livrable humain s'écrit **à la première personne**. « Chaque
lundi, je t'envoie ton export commenté » est vrai et tenable ; « CSV envoyé
automatiquement chaque semaine » serait faux, et sonnerait comme une fonction du
produit. C'est l'écart valeur promise / valeur livrée de Bush (*Product-Led Growth*
p. 89), fermé en **nommant qui livre**.

CE QUE LE CORPUS IMPOSE À LA STRUCTURE
---------------------------------------
Blair Enns, *Pricing Creativity* p. 16 : « keep your value drivers **bundled and not
à la carte** » — découper un service en parties tarifées permet la comparaison
directe et tire les prix vers le bas. **Aucun livrable ne porte de prix** : seule
l'option en a un. C'est une propriété du schéma, pas une consigne de style, et un
garde le vérifie.

p. 29 : trois options en colonnes, les prix en bas, sur une page. p. 23 : la moins
chère à gauche, et la troisième existe pour faire paraître la deuxième raisonnable —
même si elle ne se vend jamais.
"""
from __future__ import annotations

from typing import NamedTuple

#: L'ordre d'affichage, gauche → droite. Le moins cher d'abord (Enns p. 23).
CLES_PRIX = ("service_price_essentiel", "service_price_standard",
             "service_price_accompagnement")


class Livrable(NamedTuple):
    """Une ligne d'une option. **Sans prix** — voir la règle « bundled ».

    `agent` vaut `"humain"` ou `"outil"`. `ancre` nomme la page ou la capacité du
    produit pour un livrable `"outil"`, et vaut `None` pour un livrable humain.
    """

    agent: str
    ancre: str | None
    cle: str
    texte: str


class Option(NamedTuple):
    cle: str
    nom: str
    perimetre: str
    conditions: str
    cle_prix: str
    livrables: tuple[Livrable, ...]


# ── Les livrables communs, écrits une fois ───────────────────────────────────
#
# ⚠️ Chaque texte « humain » commence par « Je » ou « Chaque … je » : un engagement
# sans sujet se lit comme une fonction du logiciel, et c'est exactement ainsi que
# « 🎬 Génération de créatives vidéo (60+) » avait fini dans une carte d'abonnement.
_CREATIVES = Livrable(
    "humain", None, "service.liv.creatives",
    "Je produis les créatives et je les décline par hook et par accroche")
_PARAMETRAGE = Livrable(
    "humain", None, "service.liv.parametrage",
    "Je règle tout : audiences, placements, budgets, itérations")
_LUNDI = Livrable(
    "humain", None, "service.liv.lundi",
    "Chaque lundi, je t'envoie ton export commenté — ce que j'ai changé, et pourquoi")
_CURATION = Livrable(
    "humain", None, "service.liv.curation",
    "Je place tes titres : curateur de playlists depuis deux ans, je sais ce qui passe")
_BILAN = Livrable(
    "humain", None, "service.liv.bilan",
    "Je te fais un bilan écrit en fin de cycle : ce qui a marché, ce qu'on refait")
_RAPPORT = Livrable(
    "outil", "export_pdf", "service.liv.rapport",
    "Ton rapport PDF à la demande, compris dans ton abonnement")
_DIGEST = Livrable(
    "outil", "weekly_digest", "service.liv.digest",
    "Ton récapitulatif hebdomadaire par e-mail, compris dans ton abonnement")

OPTIONS: tuple[Option, ...] = (
    Option(
        "essentiel", "Essentiel",
        "Une campagne, une sortie, sur une fenêtre définie",
        "100 % à la commande",
        "service_price_essentiel",
        (_CREATIVES, _PARAMETRAGE, _BILAN, _RAPPORT),
    ),
    Option(
        "standard", "Standard",
        "Le cycle complet d'une sortie : plusieurs angles, et j'itère sur toute la fenêtre",
        "50 % à la commande, 50 % à la livraison",
        "service_price_standard",
        (_CREATIVES, _PARAMETRAGE, _LUNDI, _BILAN, _RAPPORT, _DIGEST),
    ),
    Option(
        "accompagnement", "Accompagnement",
        "Le cycle Standard répété, sortie après sortie — et je suis là entre deux",
        "Mensualisé, ou douze mois d'avance avec 10 % de remise",
        "service_price_accompagnement",
        (_CREATIVES, _PARAMETRAGE, _LUNDI, _CURATION, _BILAN, _RAPPORT, _DIGEST),
    ),
)

# ── Les leviers qui ne coûtent rien à produire (Enns p. 16) ──────────────────
LEVIERS: tuple[tuple[str, str], ...] = (
    ("service.levier.prix_fixe",
     "💶 **Le prix est fixe.** Pas d'heures comptées, pas de dépassement."),
    ("service.levier.garantie",
     "🛡️ **Après la première semaine, tu peux arrêter.** Ce qui n'a pas été engagé "
     "en média te revient, et tu gardes les créatives déjà produites."),
    ("service.levier.budget_exclu",
     "📣 **Le budget publicitaire n'est pas dans ce prix** — il va à Meta, pas à moi."),
    ("service.levier.appel",
     "📞 **Un appel d'abord**, et ce n'est pas une formalité : je regarde ton projet, "
     "ce que tes chiffres disent déjà, et le budget qui a du sens. Si ça ne colle "
     "pas, je le dis."),
)

#: La phrase qui lève l'ambiguïté outil / humain, sous la grille.
NOTE_QUI_FAIT_QUOI = (
    "service.qui_fait_quoi",
    "ℹ️ **L'outil te donne l'export CSV en un clic, quand tu veux.** L'envoi du "
    "lundi, commenté, c'est **moi** qui le fais — ce n'est pas une fonction du "
    "logiciel.")

#: L'objet du courriel, ÉCRIT UNE FOIS. Les trois surfaces l'utilisaient avec deux
#: formulations différentes avant le 2026-09-22.
SUJET_MAIL = "Optimisation campagnes marketing - streaMLytics"


def prix(db) -> dict[str, str]:
    """Les trois prix réglés, par clé. Une clé absente vaut la chaîne vide."""
    from src.dashboard.utils.app_settings import get_setting

    return {c: get_setting(db, c, "") for c in CLES_PRIX}


def grille_complete(valeurs: dict[str, str]) -> bool:
    """Les trois prix sont-ils posés ?

    ⚠️ Tant que la réponse est non, la grille **ne s'affiche pas à un artiste**.
    Même doctrine que le bouton Calendly absent (`views/billing.py:127-139`) : une
    proposition dont deux colonnes sur trois sont vides ne propose rien, et
    montrer un prix sur la seule colonne remplie ferait de l'option la moins
    chère la seule visible — l'inverse exact de ce que trois options servent à
    faire.
    """
    return all((valeurs or {}).get(c, "").strip() for c in CLES_PRIX)
