"""🎯 Faire piloter mes campagnes — la proposition, sur une page.

Type: Feature
Uses: streamlit, ._service_offer, utils.app_settings, utils.ui
Depends on: app_settings (les trois prix + le lien Calendly)
Persists in: nothing

Pourquoi une page à elle, et pas un onglet de Facturation
----------------------------------------------------------
Enns (*Pricing Creativity* p. 29) demande une proposition d'**une page** : trois
options en colonnes, les prix en bas. Rendue sous la grille d'abonnement, elle
ferait cohabiter deux grilles de colonnes sur le même écran — l'une à 10 €/mois,
l'autre à plusieurs centaines. C'est très exactement la confusion outil / humain
que ce dépôt a payée dix-sept jours en vendant « génération de créatives vidéo »
dans une carte d'abonnement.

Facturation et Upgrade gardent une **amorce** qui renvoie ici. La donnée, elle,
vit dans `utils/service_offer.py` — une seule source, comme `plan_pitch.py` l'a
fait pour l'abonnement après que la même offre eut divergé sur deux surfaces.

⚠️ Cette page est dans `ALWAYS_ACCESSIBLE` : on ne fait pas payer le droit de lire
une offre.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.service_offer import (
    LEVIERS,
    NOTE_QUI_FAIT_QUOI,
    OPTIONS,
    SUJET_MAIL,
    grille_complete,
    prix,
)

_PASTILLE = {"humain": "🙋", "outil": "⚙️"}


def _rendre_option(col, option, montant: str) -> None:
    """Une colonne. Le prix EN BAS (Enns p. 29), les livrables sans montant."""
    with col:
        st.markdown(f"##### {option.nom}")
        st.caption(t(f"service.opt.{option.cle}.perimetre", option.perimetre))
        for liv in option.livrables:
            st.markdown(f"{_PASTILLE[liv.agent]} {t(liv.cle, liv.texte)}")
        st.caption("— " + t(f"service.opt.{option.cle}.conditions", option.conditions))
        st.markdown(f"### {montant} €")


def show() -> None:
    from src.dashboard.auth import is_admin
    from src.dashboard.utils import project_db
    from src.dashboard.utils.app_settings import get_setting
    from src.database.stripe_schema import SERVICE_CALENDLY_URL, SERVICE_CONTACT_EMAIL

    st.title(t("service.title", "🎯 Faire piloter mes campagnes"))
    st.markdown(t(
        "service.intro",
        "L'outil te dit où va ton argent. Si tu veux que **quelqu'un s'occupe des "
        "campagnes elles-mêmes**, c'est une prestation à part — et on en parle avant "
        "de commencer."))

    with project_db() as db:
        montants = prix(db)
        lien = get_setting(db, "service_calendly_url", SERVICE_CALENDLY_URL)

        if grille_complete(montants):
            cols = st.columns(len(OPTIONS))
            for col, option in zip(cols, OPTIONS):
                _rendre_option(col, option, montants[option.cle_prix])
            st.caption(t(*NOTE_QUI_FAIT_QUOI))
        elif is_admin():
            # ⚠️ L'ARTISTE NE VOIT RIEN D'INCOMPLET. Même doctrine que le bouton
            # Calendly absent : une proposition dont deux colonnes sur trois sont
            # vides ne propose rien, et afficher le seul prix posé ferait de
            # l'option la moins chère la seule visible — l'inverse de ce que trois
            # options servent à faire.
            st.warning(t(
                "service.prices_missing",
                "⚙️ **Les trois prix ne sont pas posés** : la grille est masquée pour "
                "les artistes. Renseigne-les dans **⚙️ Admin → Réglages** — ils "
                "s'appliquent tout de suite, sans redéploiement."))

        st.markdown("---")
        for cle, texte in LEVIERS:
            st.markdown(t(cle, texte))

        if not lien and is_admin():
            st.warning(t(
                "service.no_calendly",
                "⚙️ Aucun lien de prise de rendez-vous : le bouton est masqué. "
                "Pose-le dans **⚙️ Admin → Réglages**."))

        st.markdown("")
        # ⚠️ Les colonnes se comptent sur ce qui sera DESSINÉ, pas sur ce qui
        # pourrait l'être. `st.columns(2)` avec le rendez-vous masqué laissait le
        # courriel dans la moitié droite et un demi-écran vide à sa gauche —
        # invisible en test, la seule façon de le voir était de REGARDER le rendu.
        cols = st.columns(2 if lien else 1)
        if lien:
            cols[0].link_button(t("service.book", "📅 Prendre rendez-vous"), lien,
                                type="primary", width="stretch")
        cols[-1].link_button(
            t("service.mail", "✉️ M'écrire"),
            f"mailto:{SERVICE_CONTACT_EMAIL}?subject={SUJET_MAIL.replace(' ', '%20')}",
            width="stretch")
