"""🎯 Faire piloter mes campagnes — la proposition, sur une page.

Type: Feature
Uses: streamlit, ._service_offer, utils.app_settings, utils.ui
Depends on: app_settings (le lien de rendez-vous)
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
from src.dashboard.utils.service_offer import SUJET_MAIL



def show() -> None:
    from src.dashboard.auth import is_admin
    from src.dashboard.utils import project_db
    from src.dashboard.utils.app_settings import get_setting
    from src.database.stripe_schema import SERVICE_CALENDLY_URL, SERVICE_CONTACT_EMAIL

    st.title(t("service.title", "🎯 Faire piloter mes campagnes"))
    # R387 (V52-V54, owner 2026-10-05): the offer in one sentence — no price, no
    # duration. The three-column grid and its levers left the page; their data stays
    # in `utils/service_offer.py`, which the admin pricing page still edits.
    st.markdown(t("service.pitch",
                  "Je gère tes campagnes **de A à Z**, selon ton budget et tes objectifs : "
                  "Meta Ads, créatives, bilan PDF, fichiers quotidiens."))

    with project_db() as db:
        lien = get_setting(db, "service_calendly_url", SERVICE_CALENDLY_URL)

    if not lien and is_admin():
        st.warning(t(
            "service.no_calendly",
            "⚙️ Aucun lien de prise de rendez-vous : le bouton est masqué. "
            "Pose-le dans **⚙️ Admin → Réglages**."))

    # ⚠️ Les colonnes se comptent sur ce qui sera DESSINÉ, pas sur ce qui
    # pourrait l'être. `st.columns(2)` avec le rendez-vous masqué laissait le
    # courriel dans la moitié droite et un demi-écran vide à sa gauche —
    # invisible en test, la seule façon de le voir était de REGARDER le rendu.
    cols = st.columns(2 if lien else 1)
    cols[0].link_button(
        t("service.mail", "✉️ M'écrire"),
        f"mailto:{SERVICE_CONTACT_EMAIL}?subject={SUJET_MAIL.replace(' ', '%20')}",
        type="primary", width="stretch")
    if lien:
        cols[1].link_button(t("service.book", "📅 Prendre rendez-vous"), lien,
                            width="stretch")
