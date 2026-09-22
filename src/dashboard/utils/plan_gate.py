"""Un bouton mène à la page, ou au plan qui l'ouvre — jamais à une page vide.

Type: Sub
Uses: streamlit, navigation.goto, stripe_schema.page_is_locked, nav_badges
Depends on: nothing at runtime beyond the plan resolver
Triggers: views/home.py, views/export_pdf.py, views/onboarding.py
Persists in: nothing

Le trou, balayé le 2026-09-22
------------------------------
Trois surfaces verrouillent un BLOC de contenu, et les trois ont recopié le motif à
la main : `home._bouton_rapport_pdf`, `export_pdf.py:176-185`, `onboarding.py:349`.
Aucun helper n'existait.

`auth.require_plan` ne pouvait pas servir : il appelle `st.stop()` et emporte la page
entière. C'est le bon outil pour une PAGE, jamais pour un bloc au milieu d'une autre.

`nav_badges`, de son côté, ne rend que des préfixes d'ENTRÉE DE MENU. Ce module lui
emprunte ses constantes pour que le cadenas du menu et celui d'un bloc soient le même
glyphe — sans quoi on aurait deux vocabulaires pour un seul fait.

⚠️ Ce qui migre, et ce qui NE migre PAS
-----------------------------------------
Sur les trois copies, **une seule** migre entièrement : le raccourci PDF de
l'accueil, qui pose vraiment la question « cette PAGE est-elle ouverte à ce plan ? ».

Les deux autres posent une autre question. `export_pdf` verrouille des SECTIONS d'un
document, `onboarding` compare deux paliers dans un tableau : ni l'une ni l'autre
n'est une page, et leur faire appeler `page_is_locked` répondrait à côté. Elles
empruntent le vocabulaire, pas le prédicat.

Prétendre les trois unifiées serait la quatrième copie, déguisée en abstraction.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.nav_badges import LOCKED, PAID_AND_OPEN
from src.dashboard.utils.navigation import goto
from src.database.stripe_schema import page_is_locked

#: Le glyphe d'un bloc fermé et d'un bloc ouvert-mais-payant. EMPRUNTÉS au menu :
#: un seul vocabulaire pour un seul fait. `.strip()` parce que les constantes du
#: menu portent l'espace qui les sépare du libellé qui suit.
CADENAS_FERME = LOCKED.strip()
CADENAS_OUVERT = PAID_AND_OPEN.strip()


def est_verrouille(page_key: str, *, plan: str | None = None) -> bool:
    """Ce plan interdit-il cette page ? LA question, posée à un seul endroit.

    `plan=None` résout le plan de la session. Le passer explicitement sert aux
    tests et aux surfaces qui l'ont déjà en main — refaire la résolution serait une
    requête de plus sur une page qui n'en a pas les moyens.
    """
    if plan is None:
        from src.dashboard.auth import get_artist_plan
        plan = get_artist_plan()
    return page_is_locked(plan, page_key)


def bouton_vers(page_key: str, *, ouvert: str, ferme: str,
                aide_ouvert: str = "", aide_ferme: str = "",
                key: str | None = None, width: str = "stretch",
                type: str = "secondary", plan: str | None = None) -> bool:
    """Un bouton qui mène à la page, ou au plan qui l'ouvre.

    Rend `True` **uniquement si cliqué ET ouvert** : l'appelant peut alors faire son
    geste. Cliqué et fermé, la navigation vers `upgrade` a déjà eu lieu et rien
    n'est rendu — l'appelant n'a pas à connaître le cas.

    ⚠️ Ce contrat est la raison d'être du module. Un `if st.button(...)` écrit à la
    main mène l'artiste sur une page qu'il ne peut pas voir, et le libellé lui avait
    promis le contraire. Le dépôt vendait ainsi « 🎬 génération de créatives vidéo »
    en Premium pendant dix-sept jours — même forme, autre surface.
    """
    verrouille = est_verrouille(page_key, plan=plan)
    libelle = f"{CADENAS_FERME} {ferme}" if verrouille else ouvert
    aide = aide_ferme if verrouille else aide_ouvert
    clique = st.button(libelle, help=aide or None, key=key,
                       width=width, type=type)
    if not clique:
        return False
    if verrouille:
        goto("upgrade")
        return False
    return True


def note_de_plan(page_key: str, *, plan: str | None = None,
                 ouvert: str = "", ferme: str = "") -> None:
    """Une ligne qui DIT à quel plan appartient ce bloc, sans rien verrouiller.

    Pour les blocs qu'un artiste voit entièrement et dont il doit savoir qu'ils sont
    compris — ou pas — dans son abonnement. Le propriétaire l'a demandé en toutes
    lettres : « indiquer si c'est abo payant ou free : séparer ».

    Une pastille verte sur ce qui est ouvert n'est pas décorative : sans elle, un
    artiste Premium ne sait pas ce qu'il paie, et un artiste gratuit ne sait pas ce
    qu'il gagnerait.
    """
    verrouille = est_verrouille(page_key, plan=plan)
    glyphe = CADENAS_FERME if verrouille else CADENAS_OUVERT
    texte = (ferme or t("plan_gate.ferme", "Compris dans Premium")) if verrouille \
        else (ouvert or t("plan_gate.ouvert", "Compris dans ton plan"))
    st.caption(f"{glyphe} {texte}")
