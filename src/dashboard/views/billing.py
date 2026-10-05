"""Billing page — Brick 21.

Shows the current artist's subscription status, plan comparison,
and upgrade/manage links. Admin sees all artist subscriptions.
"""
import os
from typing import TYPE_CHECKING

import streamlit as st
from src.dashboard.utils import get_db_connection, require_db
from src.dashboard.utils.i18n import t
from src.dashboard.utils.date_format import format_date
from src.dashboard.auth import get_artist_plan, is_admin, tenant_scope
if TYPE_CHECKING:
    import pandas as pd
from src.database.stripe_schema import (
    PLAN_CATALOG, PLAN_RANK, SERVICE_CALENDLY_URL)


def _price_str(plan: str) -> str:
    p = PLAN_CATALOG[plan]['price_eur']
    if p == 0:
        return t("billing.price_free", "0 €/mois")
    return t("billing.price_monthly", "{p} €/mois").format(p=p)


# ── LES CARTES SONT DÉRIVÉES, PLUS RECOPIÉES — 2026-09-21 ───────────────────
#
# Elles étaient écrites à la main ici, une troisième fois après `upgrade.py` et
# `onboarding.py`, et les trois se contredisaient. Deux erreurs mesurées le même
# jour :
#
#   · « 📄 Export PDF du rapport (FR / EN) » figurait en **Free**. Le PDF a quitté
#     Free le 2026-09-04 par une décision explicite (commit 5fdc65a). Cette page
#     l'a donc promis gratuitement pendant DIX-SEPT JOURS, sous un menu qui
#     l'affichait cadenassé.
#   · « 🎬 Génération de créatives vidéo (60+ par campagne) » figurait en
#     **Premium**. Rien dans l'arbre ne génère de vidéo — ni ffmpeg, ni moviepy,
#     ni aucun module de rendu. C'est une prestation HUMAINE : elle descend dans
#     le panneau de service, où elle est vraie.
#
# `utils/plan_pitch` LIT le verrou au lieu de le recopier. Une page qui change de
# plan déplace sa ligne toute seule.
def _plan_cards() -> dict:
    from src.dashboard.utils.plan_pitch import bullets
    return {
        'free': {
            'label': t("billing.plan_free_label", "🆓 Free"),
            'price': _price_str('free'),
            'max_artists': t("billing.one_artist", "1 artiste"),
            'features': bullets('free'),
        },
        'premium': {
            'label': t("billing.plan_premium_label", "💎 Premium"),
            'price': _price_str('premium'),
            'max_artists': t("billing.up_to_10", "Jusqu'à 10 artistes"),
            'features': [t("billing.feat_everything_free",
                           "Tout ce que contient Free")] + bullets('premium'),
        },
    }


_PLAN_ORDER = ['free', 'premium']


def show():
    st.title(t("billing.title", "💳 Facturation / Abonnement"))
    st.markdown("---")

    db = require_db(get_db_connection())
    # `if not admin and artist_id:` below reads a None as falsy and renders an
    # empty page rather than saying anything. tenant_scope() names the state.
    artist_id = tenant_scope()
    admin = is_admin()

    try:
        # R391 (V84-V86, owner's screen review, 2026-10-05): the two plans first,
        # side by side — the inactive one struck through, the active one marked —,
        # then the « Faire piloter » button, then « Nos offres ». It used to read
        # three metric tiles, the offers, and the service pitch last.
        current_plan = None if admin else get_artist_plan()
        if not admin and artist_id:
            _show_current_plan(db, artist_id, current_plan)
        elif admin:
            _show_admin_view(db)

        _render_service_cta(db)
        _render_plan_columns(current_plan)

    finally:
        db.close()


def _render_service_cta(db=None) -> None:
    """L'amorce vers la prestation. Le détail vit sur sa propre page.

    ⚠️ CE PANNEAU PORTAIT TOUTE L'OFFRE JUSQU'AU 2026-09-22 — quatre arguments et
    deux boutons — et il ne chiffrait rien (R150). Elle vit maintenant sur la page
    « 🎯 Faire piloter mes campagnes », avec trois options en colonnes et les prix
    en bas : Enns (*Pricing Creativity* p. 29) demande une proposition d'UNE page,
    et la rendre ici la ferait cohabiter avec la grille d'abonnement à 10 €/mois.
    Deux grilles de prix sur un écran, c'est la confusion outil / humain que ce
    dépôt a payée dix-sept jours.

    ⚠️ **`get_setting` est appelé ICI et le lien est passé au bouton.** Ce n'est pas
    un détail de style : `tests/test_a_setting_is_settable_without_a_redeploy.py:133`
    vérifie par AST que cette page lit le RÉGLAGE plutôt qu'une constante — et la
    propriété qu'il garde est « la surface qui montre le bouton lit le réglage ».
    """
    from src.dashboard.utils.app_settings import get_setting
    from src.dashboard.utils.navigation import goto

    st.markdown("---")
    st.caption(t(
        "billing.service_body",
        "L'outil te dit où va ton argent. Si tu veux que quelqu'un s'occupe **des "
        "campagnes elles-mêmes**, c'est une prestation à part — trois formules, et "
        "un appel avant de commencer."))

    lien = get_setting(db, "service_calendly_url", SERVICE_CALENDLY_URL)
    cols = st.columns(2)
    if cols[0].button(t("billing.service_see", "🎯 Faire piloter mes campagnes"),
                      type="primary", width="stretch"):
        goto("service")
    if lien:
        cols[-1].link_button(t("billing.service_book", "📅 Prendre rendez-vous"),
                             lien, width="stretch")
    elif is_admin():
        st.warning(t(
            "billing.service_no_calendly",
            "⚙️ Aucun lien de prise de rendez-vous : le bouton est masqué. "
            "Pose-le dans **⚙️ Admin → Réglages** — il s'applique tout de suite, "
            "sans redéploiement."))


def status_text(status: str | None) -> str:
    """The subscription status in words, with its colour dot."""
    words = {
        'active': f"🟢 {t('billing.status_active', 'Actif')}",
        'trialing': f"🟡 {t('billing.status_trialing', 'Essai')}",
        'past_due': f"🔴 {t('billing.status_past_due', 'Paiement en retard')}",
        'canceled': f"⚫ {t('billing.status_canceled', 'Résilié')}",
    }
    return words.get(status or 'active', f"⚪ {status}")


def card_header(label: str, active: bool) -> str:
    """An active plan is marked by a green arrow; an inactive one is struck through."""
    return f"### :green[➜] {label}" if active else f"### ~~{label}~~"


def _render_plan_status(current_plan: str, status: str | None) -> None:
    """Free and Premium side by side: which one runs, at what price, in what state."""
    cards = _plan_cards()
    for col, plan_key in zip(st.columns(len(_PLAN_ORDER)), _PLAN_ORDER):
        active = plan_key == current_plan
        with col:
            st.markdown(card_header(cards[plan_key]['label'], active))
            st.markdown(f"**{cards[plan_key]['price']}**")
            st.caption(status_text(status) if active
                       else t("billing.status_inactive", "Non souscrit"))


def _show_current_plan(db, artist_id: int, current_plan: str):
    row = db.fetch_query(
        """
        SELECT sp.name, sp.price_monthly, asub.status,
               asub.current_period_end, asub.cancel_at_period_end,
               asub.stripe_customer_id, asub.stripe_subscription_id
        FROM artist_subscriptions asub
        JOIN subscription_plans sp ON sp.id = asub.plan_id
        WHERE asub.artist_id = %s
        LIMIT 1
        """,
        (artist_id,),
    )

    if not row:
        # No subscription row → free plan, or an active promo trial.
        trial = current_plan != 'free'
        _render_plan_status(current_plan, 'trialing' if trial else 'active')
        if trial:
            st.success(
                t("billing.trial_active",
                  "🎁 Accès **{plan}** actif (essai de bienvenue). "
                  "Voir les offres ci-dessous pour la suite.").format(
                      plan=current_plan.capitalize())
            )
        return

    _, _, status, period_end, cancel_at_end, customer_id, _ = row[0]
    _render_plan_status(current_plan, status)

    free_months_row = db.fetch_query(
        "SELECT referral_free_months FROM saas_artists WHERE id = %s", (artist_id,)
    )
    free_months = free_months_row[0][0] if free_months_row else 0
    # ⚠️ Même correction que sur la page de parrainage, le 2026-09-21, et pour la
    # même raison mesurée : RIEN ne consomme `referral_free_months`. Deux surfaces
    # affichaient un futur passif qui décrit un mécanisme inexistant. Le crédit est
    # réel, son application est manuelle, et l'automatiser est une brique de
    # roadmap (coupons Stripe), pas une retouche de texte.
    if free_months > 0:
        st.success(t("billing.free_months",
                     "🎁 Tu as **{n} mois offert(s)** grâce au parrainage : chacun est "
                     "déduit de ta prochaine facture Stripe, un mois à la fois.").format(
                         n=free_months))

    discount_row = db.fetch_query(
        "SELECT first_month_discount_pct FROM saas_artists WHERE id = %s", (artist_id,)
    )
    discount_pct = discount_row[0][0] if discount_row else 0
    if discount_pct > 0:
        st.info(t("billing.discount",
                  "🏷️ Un **rabais de {pct} %** t'est acquis sur ton premier mois "
                  "payant (parrainage). Signale-le nous au moment de t'abonner : "
                  "il se pose à la main.").format(pct=discount_pct))

    if period_end:
        if cancel_at_end:
            st.warning(
                t("billing.cancel_warning",
                  "⚠️ Votre abonnement sera **résilié le {date}**. "
                  "Réactivez-le via le portail Stripe ci-dessous.").format(
                      date=period_end.strftime('%Y-%m-%d'))
            )
        else:
            st.caption(t("billing.next_renewal", "Prochain renouvellement : {date}").format(
                date=period_end.strftime('%Y-%m-%d')))

    if status == 'past_due':
        st.error(
            t("billing.payment_failed",
              "❌ Votre dernier paiement a échoué. Mettez à jour votre moyen de paiement "
              "pour rétablir l'accès."),
            icon="💳",
        )

    if customer_id:
        stripe_portal_url = os.getenv("STRIPE_PORTAL_URL", "")
        if stripe_portal_url:
            st.link_button(t("billing.manage_sub", "Gérer l'abonnement (portail Stripe)"), stripe_portal_url)
        else:
            st.caption(
                t("billing.portal_unset",
                  "Pour gérer votre abonnement, contactez le support ou définissez "
                  "`STRIPE_PORTAL_URL` dans votre environnement.")
            )

    # Offres rendered by show() → _render_plan_columns (3-column layout).


def _upgrade_cta(target_plan: str, current_plan: str | None) -> None:
    """Render the call-to-action for one plan card.

    Greyed/disabled buttons are avoided: when Stripe checkout is not configured
    we still show an enabled button that explains how to upgrade, instead of a
    dead disabled control.
    """
    # Current plan → badge, no CTA
    if current_plan is not None and target_plan == current_plan:
        st.success(t("billing.current_plan_badge", "✅ Votre plan actuel"))
        return
    # Lower or equal rank than the current plan → already included
    if current_plan is not None and PLAN_RANK[target_plan] <= PLAN_RANK[current_plan]:
        st.caption(t("billing.included", "Inclus dans votre plan"))
        return
    if target_plan == 'free':
        st.caption(t("billing.free_no_action", "Plan gratuit — aucune action requise"))
        return

    checkout_url = os.getenv("STRIPE_CHECKOUT_URL", "")
    label = t("billing.upgrade_to", "Passer à {plan}").format(plan=target_plan.capitalize())
    if checkout_url:
        # Stripe Payment Link: client_reference_id carries the tenant id so the
        # webhook (checkout.session.completed) provisions the right artist. Without
        # it the payment can't be linked to a tenant.
        # Sans `client_reference_id`, le webhook `checkout.session.completed`
        # exécute `if artist_id and customer_id:` et ne fait RIEN : le client paie
        # et n'est jamais provisionné. Un lien de paiement non attribuable est donc
        # pire qu'aucun lien — on ne le rend pas. Mesuré le 2026-08-23 (R40) : les
        # deux surfaces de paiement dégradaient silencieusement vers `checkout_url`
        # nu quand l'identifiant du locataire manquait.
        _aid = tenant_scope()
        if _aid:
            st.link_button(label, f"{checkout_url}?client_reference_id={_aid}",
                           type="primary")
        else:
            st.button(label, type="primary", disabled=True,
                      key=f"upgrade_no_tenant_{target_plan}")
            st.error(t("billing.no_tenant",
                       "Session incomplète : le paiement ne pourrait pas être rattaché "
                       "à ton compte. Reconnecte-toi puis réessaie."))
    else:
        # No Stripe configured: enabled button that surfaces the manual path.
        if st.button(label, type="primary", key=f"upgrade_{target_plan}"):
            st.info(
                t("billing.payment_soon",
                  "💳 Le paiement en ligne arrive bientôt. En attendant, "
                  "contactez-nous pour activer ce plan dès maintenant.")
            )


def _render_plan_columns(current_plan: str | None) -> None:
    """« Nos offres »: what each plan contains, with its call to action."""
    st.markdown("---")
    st.subheader(t("billing.offers_header", "Nos offres"))
    plan_cards = _plan_cards()
    cols = st.columns(len(_PLAN_ORDER))
    for col, plan_key in zip(cols, _PLAN_ORDER):
        card = plan_cards[plan_key]
        with col:
            is_current = current_plan is not None and plan_key == current_plan
            header = f"### {card['label']}"
            if is_current:
                header += " ✅"
            st.markdown(header)
            st.markdown(f"**{card['price']}**  ·  {card['max_artists']}")
            st.markdown("\n".join(f"- {f}" for f in card['features']))
            st.markdown("")
            _upgrade_cta(plan_key, current_plan)


def _admin_frame(rows: list) -> "pd.DataFrame":
    """The subscriptions table. A NULL period end is NaT in pandas, and NaT is TRUTHY:
    `x.strftime(...) if x` raised on it (R397) — format_date renders it « — »."""
    import pandas as pd
    df = pd.DataFrame(rows, columns=["Artist", "Tier", "Plan", "Status", "Period End", "Stripe Customer"])
    df["Period End"] = df["Period End"].apply(format_date)
    df["Stripe Customer"] = df["Stripe Customer"].apply(lambda x: x[:8] + "…" if x else "—")
    return df


def _show_admin_view(db):
    st.subheader(t("billing.admin_header", "Tous les abonnements artistes"))

    rows = db.fetch_query(
        """
        SELECT sa.name, sa.tier, sp.name AS plan, asub.status,
               asub.current_period_end, asub.stripe_customer_id
        FROM saas_artists sa
        LEFT JOIN artist_subscriptions asub ON asub.artist_id = sa.id
        LEFT JOIN subscription_plans sp ON sp.id = asub.plan_id
        WHERE sa.active = TRUE
        ORDER BY sa.id
        """
    )

    if not rows:
        st.info(t("billing.no_artists", "Aucun artiste trouvé."))
        return

    df = _admin_frame(rows)
    df.columns = [
        t("common.artist", "Artiste"),
        t("billing.col_tier", "Tier"),
        t("billing.col_plan", "Plan"),
        t("billing.col_status", "Statut"),
        t("billing.col_period_end", "Fin de période"),
        t("billing.col_stripe", "Client Stripe"),
    ]
    st.dataframe(df, width="stretch", hide_index=True)

    # Revenue summary
    # LA MÊME DÉFINITION QU'`admin.py` — 2026-09-20 (R140 §16.6). Les deux pages
    # affichaient « MRR total » sous le même mot pour deux nombres différents dès qu'un
    # abonnement était `trialing`.
    # Read BY NAME (R369): R140 inserted `price_monthly` at index 1, and the positional
    # reads that stayed here took the price for the artist count and the count for the
    # MRR, then raised on a 3-name DataFrame. `float()`/`int()`: psycopg2 returns
    # Decimal for `numeric`, and Decimal / numpy.int64 raises.
    from src.utils.mrr import MRR_LABEL, mrr_by_plan_sql, mrr_params
    rev = db.fetch_df(mrr_by_plan_sql(), mrr_params())

    if not rev.empty:
        st.markdown("---")
        st.subheader(t("billing.mrr_header", "Répartition du MRR"))
        col1, col2, col3 = st.columns(3)
        total_mrr = float(rev["mrr"].fillna(0).sum())
        total_artists = int(rev["artists"].sum())
        col1.metric(t("billing.total_mrr", MRR_LABEL), f"{total_mrr:.2f} €")
        col2.metric(t("billing.paying_artists", "Artistes payants"), total_artists)
        col3.metric("ARPU", f"{(total_mrr / total_artists):.2f} €" if total_artists else "—")

        df_mrr = rev[["plan", "artists", "mrr"]].astype({"artists": int, "mrr": float})
        df_mrr.columns = [
            t("billing.col_plan", "Plan"),
            t("billing.col_artists", "Artistes"),
            t("billing.col_mrr", "MRR (€)"),
        ]
        st.dataframe(df_mrr, width="stretch", hide_index=True)
