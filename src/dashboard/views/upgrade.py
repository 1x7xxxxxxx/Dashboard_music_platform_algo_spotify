"""Plan comparison paywall page — shown when a locked feature is clicked.

Type: Feature
Uses: get_artist_plan, PLAN_FEATURES, PLAN_RANK
Depends on: billing view (Stripe portal CTA)
"""
import os

import streamlit as st

from src.dashboard.utils.navigation import goto

from src.dashboard.auth import get_artist_id, get_artist_plan
from src.dashboard.utils.i18n import t
from src.database.stripe_schema import (
    PLAN_CATALOG, PLAN_RANK,
)


def _price_label(plan: str) -> str:
    p = PLAN_CATALOG[plan]['price_eur']
    if p == 0:
        return t("upgrade.price_free", "0€")
    return t("upgrade.price_monthly", "{p}€/mois").format(p=p)



# `_PAGE_LABELS` a été RETIRÉ le 2026-09-21 avec son unique lecteur. Il servait
# à afficher la liste Free comme des noms de pages triés alphabétiquement ;
# l'argumentaire vit maintenant dans `utils/plan_pitch`, qui nomme des
# DÉCISIONS et lit le verrou plutôt que de le recopier. Garder le dictionnaire
# aurait laissé une seconde liste de libellés à faire diverger.

_PLAN_DISPLAY = {
    'free':    {'label': 'Free',    'color': '#6c757d'},
    'premium': {'label': 'Premium', 'color': '#fd7e14'},
}


def _feature_list(plan: str) -> list[str]:
    """Les mêmes lignes que la page de facturation — source unique.

    ⚠️ Cette fonction écrivait SA propre liste pour Premium, et rangeait Free en
    affichant des NOMS DE PAGES triés alphabétiquement (`_PAGE_LABELS`). Deux
    défauts dans la même dizaine de lignes :
    le texte Premium a divergé de `billing.py` et de `onboarding.py` (trois
    versions le 2026-09-21), et le texte Free énumérait des clés techniques là où
    l'artiste cherche ce qu'il peut FAIRE.
    """
    from src.dashboard.utils.plan_pitch import bullets
    return bullets(plan)


def show() -> None:
    current_plan = get_artist_plan()
    current_rank = PLAN_RANK.get(current_plan, 0)

    st.title(t("upgrade.title", "🔒 Passez à un plan supérieur"))
    st.caption(
        t("upgrade.caption",
          "Votre plan actuel : **{plan}**. "
          "Débloquez plus de fonctionnalités en upgradeant.").format(
              plan=_PLAN_DISPLAY[current_plan]['label'])
    )
    st.markdown("---")

    col_free, col_premium = st.columns(2)

    # ── FREE ──────────────────────────────────────────────
    with col_free:
        is_current = current_plan == 'free'
        st.markdown(
            f"### {_PLAN_DISPLAY['free']['label']}"
            + (t("upgrade.your_plan", " ← *votre plan*") if is_current else "")
        )
        st.markdown(f"**{_price_label('free')}**")
        st.markdown("---")
        for feat in _feature_list('free'):
            st.markdown(f"✅ {feat}")
        if is_current:
            st.success(t("upgrade.current_plan", "Plan actuel"))

    # ── PREMIUM ───────────────────────────────────────────
    with col_premium:
        is_current = current_plan == 'premium'
        can_upgrade = current_rank < PLAN_RANK['premium']
        st.markdown(
            f"### {_PLAN_DISPLAY['premium']['label']}"
            + (t("upgrade.your_plan", " ← *votre plan*") if is_current else "")
        )
        st.markdown(f"**{_price_label('premium')}**")
        st.markdown("---")
        st.markdown(t("upgrade.everything_free", "✅ **Tout le contenu Free, plus :**"))
        for feat in _feature_list('premium'):
            st.markdown(f"✅ {feat}")
        st.markdown("---")
        if is_current:
            st.success(t("upgrade.current_plan", "Plan actuel"))
        elif can_upgrade:
            # Link straight to the Stripe Payment Link (external navigation is correct
            # here). client_reference_id carries the tenant so the webhook provisions
            # the right artist — mirrors billing.py. A relative "/?page=..." would force
            # a full page reload, dropping the in-memory session → bounce to login.
            checkout_url = os.getenv("STRIPE_CHECKOUT_URL", "")
            if checkout_url:
            # Sans `client_reference_id`, le webhook `checkout.session.completed`
            # exécute `if artist_id and customer_id:` et ne fait RIEN : le client paie
            # et n'est jamais provisionné. Un lien de paiement non attribuable est donc
            # pire qu'aucun lien — on ne le rend pas. Mesuré le 2026-08-23 (R40) : les
            # deux surfaces de paiement dégradaient silencieusement vers `checkout_url`
            # nu quand l'identifiant du locataire manquait.
                _aid = get_artist_id()
                if _aid:
                    st.link_button(t("upgrade.go_premium", "Passer à Premium →"),
                                   f"{checkout_url}?client_reference_id={_aid}",
                                   type="primary")
                else:
                    st.button(t("upgrade.go_premium", "Passer à Premium →"),
                              type="primary", disabled=True, key="upgrade_no_tenant")
                    st.error(t("upgrade.no_tenant",
                               "Session incomplète : le paiement ne pourrait pas être "
                               "rattaché à ton compte. Reconnecte-toi puis réessaie."))
            else:
                # Stripe not configured: in-app nav to Billing (no full reload).
                if st.button(t("upgrade.go_premium", "Passer à Premium →"),
                             type="primary", key="_upgrade_to_billing"):
                    st.session_state['_nav_page'] = 'billing'
                    st.rerun()

    st.markdown("---")
    st.caption(
        t("upgrade.stripe_note",
          "Les paiements sont gérés via Stripe. "
          "Annulation possible à tout moment depuis la page Billing.")
    )
    # ⚠️ LA COPIE DÉGRADÉE A ÉTÉ RETIRÉE — 2026-09-22.
    #
    # Cette page portait sa propre version de l'offre : une ligne, sans Calendly, sans
    # les arguments, avec un `subject:` de courriel DIFFÉRENT de celui de Facturation,
    # et le vouvoiement là où l'autre tutoie. Quatre divergences sur une offre écrite
    # deux fois — la classe « un catalogue recopié », que ce dépôt a payée trois fois,
    # la dernière avec dix-sept jours de promesse fausse.
    #
    # L'offre vit maintenant dans `utils/service_offer.py` et se lit sur sa propre
    # page. Ici, une amorce, et rien d'autre.
    st.markdown(t(
        "upgrade.service_cta",
        "🎯 **Tu préfères que quelqu'un s'en occupe ?** Piloter tes campagnes est une "
        "prestation à part — trois formules, et un appel avant de commencer."))
    if st.button(t("upgrade.service_btn", "Voir la prestation")):
        goto("service")
