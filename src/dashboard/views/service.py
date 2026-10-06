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

🔒 Page FIGÉE (R434, 2026-10-07) : son rendu est comparé à
`tests/fixtures/service_snapshot.json` ; une nouvelle photo exige une ligne de roadmap
portant `<!-- service: oui -->` (`make service-snapshot`).

⚠️ Cette page est dans `ALWAYS_ACCESSIBLE` : on ne fait pas payer le droit de lire
une offre.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.service_offer import (
    QUESTIONS, SUJET_MAIL, compose_mail, mailto_url,
)

_OPEN = "service_mail_open"
_SENT = "service_mail_sent"
_HEADLINE = ('<p style="font-size:1.9rem;font-weight:700;margin:.2rem 0 .6rem">'
             '<span style="background:rgba(255,165,0,.35);text-decoration:underline;'
             'padding:0 .3rem;border-radius:.2rem">{}</span></p>')


def show() -> None:
    from src.dashboard.auth import is_admin
    from src.dashboard.utils import project_db
    from src.dashboard.utils.app_settings import get_setting
    from src.database.stripe_schema import SERVICE_CALENDLY_URL, SERVICE_CONTACT_EMAIL

    st.title(t("service.title", "🎯 Faire piloter mes campagnes"))
    # R387 (V52-V54, owner 2026-10-05): the offer in one sentence — no price, no
    # duration. The three-column grid and its levers left the page; their data stays
    # in `utils/service_offer.py`, which the admin pricing page still edits.
    # R433 (owner, 2026-10-06): the value as bullets, « toute la plus-value qu'on a ».
    # R434 (owner, 2026-10-07): the algorithm goal FIRST, « en gros, surligné et
    # souligné » — Markdown has no underline, hence the one HTML line (text is ours).
    st.markdown(t("service.pitch",
                  "Je gère tes campagnes **de A à Z**, selon ton budget et tes objectifs :"))
    st.markdown(_HEADLINE.format(t("service.headline", "🚀 Déclenchement des algos Spotify")),
                unsafe_allow_html=True)
    st.markdown(t("service.bullets",
                  "- Optimisation des campagnes Meta Ads\n"
                  "- Optimisation des streams Spotify\n"
                  "- Génération de créatives\n"
                  "- Bilan quotidien"))

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
    # R429: short buttons, content-wide — no longer half the page each.
    cols = st.columns([1, 1, 3] if lien else [1, 4])
    if cols[0].button(t("service.mail", "✉️ M'écrire"), type="primary", width="stretch"):
        st.session_state[_OPEN] = True
    if lien:
        cols[1].link_button(t("service.book", "📅 Prendre rendez-vous"), lien,
                            width="stretch")
    if st.session_state.get(_OPEN):
        _questionnaire_and_mail(SERVICE_CONTACT_EMAIL)


def _ask(q) -> str:
    """One question's widget, pre-filled (R430); its answer as text, '' when unanswered."""
    label = t(q.key, q.label)
    shown = {slug: t(f"{q.key}.{slug}", txt) for slug, txt in q.options}
    slugs = list(shown)
    key = f"service_q_{q.qid}"
    if q.kind in ("select", "yesno"):
        index = slugs.index(q.default) if q.default in shown else None
        if q.kind == "yesno":  # R430: two boxes to tick, not a list to open and read
            pick = st.radio(label, slugs, index=index, key=key, format_func=shown.get,
                            horizontal=True)
        else:
            pick = st.selectbox(label, slugs, index=index, key=key,
                                format_func=shown.get, placeholder="—")
        return shown.get(pick, "")
    if q.kind == "multi":
        st.session_state.setdefault(key, list(q.default or ()))  # pre-ticked, once
        picks = st.multiselect(label, slugs, key=key, format_func=shown.get,
                               placeholder="—")
        return ", ".join(shown[p] for p in picks)
    if q.kind == "area":
        return st.text_area(label, key=key, height=90).strip()
    return st.text_input(label, key=key).strip()


def _questionnaire_and_mail(to: str) -> None:
    """R429 — the questions a first call would ask, then the mail they make, on the page.

    R430 — the mail leaves FROM the app: one request, one mail in the owner's inbox,
    countable. The artist's mail app is only the fallback when the send fails.
    """
    st.markdown(t("service.survey_intro",
                  "**Quelques questions** — tes réponses remplissent le mail en dessous."))
    answers, labels = {}, {}
    with st.container(border=True):
        halves = st.columns(2)
        short = [q for q in QUESTIONS if q.kind != "area"]
        for i, q in enumerate(short):
            with halves[i % 2]:
                answers[q.qid] = _ask(q)
        for q in QUESTIONS:
            if q.kind == "area":  # full width, under the two columns
                answers[q.qid] = _ask(q)
            labels[q.qid] = t(q.key, q.label)
    # `name` holds the account's e-mail (auth._hydrate_session) — there is no "email".
    who = str(st.session_state.get("name") or "")
    body = compose_mail(
        answers,
        t("service.mail_intro",
          "Bonjour,\n\nJe voudrais te confier mes campagnes. Voici où j'en suis :"),
        t("service.mail_closing", "Merci !") + (f"\n{who}" if who else ""),
        labels)
    st.markdown(t("service.mail_preview", "**📨 Ton mail, prêt à partir**"))
    st.code(body, language=None, wrap_lines=True)
    if st.session_state.get(_SENT) == body:
        st.success(t("service.mail_sent", "✅ C'est parti ! Je te réponds par mail."))
        return
    if st.button(t("service.mail_send", "📨 Envoyer"), type="primary"):
        _send(to, who, body)


def _send(to: str, who: str, body: str) -> None:
    from src.dashboard.utils.throttle import service_mail_consume
    from src.utils.service_request_mail import send_service_request

    artist = str(st.session_state.get("username") or "")
    wait = service_mail_consume(st.session_state.get("user_id"))
    if wait is not None:
        st.warning(t("service.mail_throttled",
                     "⏳ Tu viens déjà de m'écrire — réessaie dans {m} min.").format(
                         m=max(1, wait // 60)))
        return
    if send_service_request(to, artist, who, body):
        st.session_state[_SENT] = body
        st.rerun()
    st.error(t("service.mail_failed",
               "❌ L'envoi n'est pas parti. Tu peux me l'envoyer toi-même :"))
    st.link_button(t("service.mail_fallback", "📨 L'ouvrir dans ma messagerie"),
                   mailto_url(to, SUJET_MAIL, body))
