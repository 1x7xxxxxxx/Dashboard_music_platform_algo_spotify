"""Credentials — Meta / Instagram connection test + setup guide.

Type: Sub
Uses: requests, streamlit, META_GRAPH_BASE_URL
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests
import streamlit as st

from src.utils.meta_config import META_GRAPH_BASE_URL
from src.dashboard.utils.i18n import t
from src.utils.tenant_identity import identity_is_well_formed


def _test_meta(fields: dict) -> tuple:
    # Shared System User token comes from the platform env; the artist only
    # provides their account_id. A stored per-artist token (if any) wins.
    token = fields.get('access_token', '').strip() or os.getenv('META_ACCESS_TOKEN', '')
    if not token:
        return False, t("credentials.meta.test_not_configured",
                        "App Meta non configurée côté plateforme (META_ACCESS_TOKEN) — "
                        "contactez l'administrateur.")
    try:
        r = requests.get(
            f'{META_GRAPH_BASE_URL}/me',
            params={'access_token': token, 'fields': 'id,name'},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        data = r.json()
        if not (r.status_code == 200 and data.get('id')):
            msg = data.get('error', {})
            if isinstance(msg, dict):
                msg = msg.get('message', 'réponse inattendue de Meta')
        # Never the raw body: it is whatever the requested path returned.
            return False, str(msg)

        # /me only proves the PLATFORM's System User token works — it is identical for
        # every tenant and says nothing about this artist. Green here while the ad
        # account was never shared is exactly the Benken meta=🔴 case (asset sharing
        # missing) discovered only a day later, at collection time. Validate the
        # artist's own account_id now.
        raw_id = fields.get('account_id', '').strip()
        if not raw_id:
            return False, t("credentials.meta.account_missing",
                            "App Meta OK, mais ton **Ad Account ID** n'est pas renseigné — "
                            "sans lui aucune donnée ne peut être collectée. Il se lit dans "
                            "l'URL du Gestionnaire de publicités, après `act=`.")
        # Shape before the network, same reason as ig_user_id below: this lands in
        # the PATH. The forced `act_` prefix blocks the trivial payload but not a
        # traversal, and "probably safe because of a prefix" is not a control.
        if not identity_is_well_formed("meta", raw_id):
            return False, t(
                "credentials.meta.account_malformed",
                "Ad Account ID invalide : chiffres uniquement, éventuellement "
                "préfixés par `act_` (ex : 567214713853881)."
            )
        act_id = raw_id if raw_id.startswith('act_') else f"act_{raw_id}"
        ra = requests.get(
            f'{META_GRAPH_BASE_URL}/{act_id}',
            params={'access_token': token, 'fields': 'name,account_status'},
            timeout=10,
            allow_redirects=False,
        )
        acc = ra.json()
        if ra.status_code != 200 or not acc.get('id', acc.get('name')):
            err = acc.get('error', {})
            detail = str(err.get('message', 'réponse inattendue de Meta'))[:200] if isinstance(err, dict) else ''
            return False, t(
                "credentials.meta.account_unreachable",
                "Compte publicitaire **{act}** inaccessible avec l'app partagée : {detail}\n\n"
                "→ Cause la plus fréquente : le compte n'a pas été **partagé** avec l'app "
                "(Business Manager → Paramètres → Apps → ETL_DASHBOARD_SPOTIFY → Business "
                "Assets → Ajouter des assets → Compte publicitaire, permission Annonceur)."
            ).format(act=act_id, detail=detail)
        # Instagram rides the same System User token but a different asset. It is
        # optional HERE — an artist may run ads without connecting IG — so a blank id
        # only skips the suffix. `_test_instagram` below is the standalone probe, and
        # there a blank id is a FAILURE, never a pass.
        ig_user_id = fields.get('ig_user_id', '').strip()
        ig_suffix = ""
        if ig_user_id:
            ok, msg = _probe_instagram(ig_user_id, token)
            if not ok:
                return False, msg
            ig_suffix = msg
        return True, t("credentials.meta.test_ok_account",
                       "Connecté : {name} — compte publicitaire « {acc} » accessible ✅{ig}").format(
                           name=data.get('name', data['id']),
                           acc=acc.get('name', act_id), ig=ig_suffix)
    except Exception as e:
        # NEVER str(e). This probe passes the shared credential as a QUERY
        # PARAMETER, so a ConnectionError's message embeds the full prepared URL —
        # credential included — and _render.py renders it to the tenant with
        # st.error. A DNS blip was enough to show a non-admin the platform-wide
        # token (Meta, never expires) or the billable API key (YouTube).
        return False, t("credentials.probe_network_error",
                        "Erreur réseau ({err}) — réessaie dans un instant. Si ça "
                        "persiste, contacte l'administrateur.").format(
                            err=type(e).__name__)


def _guide_meta():
    with st.expander(t("credentials.meta.guide_title",
                       "📱 Où trouver chaque champ Meta / Instagram ?"), expanded=False):
        st.info(t(
            "credentials.meta.guide_info",
            "Ce dashboard utilise un **System User token** — jamais de token personnel. "
            "Les tokens System User n'expirent pas (sauf révocation manuelle). "
            "Tous les artistes utilisent la même app Meta : **ETL_DASHBOARD_SPOTIFY** — "
            "ne crée pas ta propre app."
        ))

        st.markdown(t("credentials.meta.steps_header", "### Étapes — Meta Ads"))
        st.markdown(t(
            "credentials.meta.steps_body",
            "Un seul identifiant est à toi : l'Ad Account ID. Tout le reste — le jeton "
            "d'accès et les identifiants d'application — appartient à la plateforme et "
            "n'apparaît nulle part dans ce formulaire.\n\n"
            "1. **Business Manager → Paramètres → Comptes publicitaires** → relever l'ID "
            "numérique (ex : `123456789`). **Ne pas ajouter le préfixe `act_`** — le "
            "dashboard l'ajoute automatiquement. *(C'est le champ **Ad Account ID** "
            "ci-dessus.)*\n"
            "2. **Paramètres → Apps → ETL_DASHBOARD_SPOTIFY → Business Assets → "
            "Ajouter des assets → Compte publicitaire** → sélectionner ton compte → "
            "permission Annonceur. *(Obligatoire — sans ça l'API renvoie \"Object does not "
            "exist\", et le test de connexion te le dira.)*\n"
            "3. Cliquer sur **Tester la connexion**. S'il est vert, il n'y a rien d'autre "
            "à faire."
        ))

        st.markdown(t("credentials.meta.ig_header", "### Étapes supplémentaires — Instagram"))
        st.markdown(t(
            "credentials.meta.ig_body",
            "Si tu veux les stats Instagram, renseigne ton Instagram Business Account ID "
            "ci-dessous. Le token partagé de la plateforme porte déjà les scopes requis "
            "(`instagram_basic`, `instagram_manage_insights`, `pages_show_list`) — demande "
            "à l'administrateur si le test de connexion dit le contraire.\n\n"
            "Le DAG `meta_token_refresh` (hebdo) ne tente **pas** de renouveler les System User tokens "
            "(ils n'expirent pas) — aucune action périodique requise."
        ))

        st.markdown(t("credentials.meta.ig_id_header",
                      "### Instagram Business Account ID (optionnel)"))
        st.code(
            "https://graph.facebook.com/v24.0/me/accounts?access_token=TON_TOKEN\n"
            "# → noter l'id de ta Page Facebook\n"
            "https://graph.facebook.com/v24.0/PAGE_ID?fields=instagram_business_account&access_token=TON_TOKEN\n"
            "# → instagram_business_account.id",
            language="text"
        )

        st.markdown(t(
            "credentials.meta.table",
            "| À saisir ici | Où le trouver |\n"
            "|---|---|\n"
            "| **Ad Account ID** | Business Manager → Comptes publicitaires "
            "(numérique uniquement, sans `act_`) |\n"
            "| **Instagram Business Account ID** *(optionnel)* | Appel Graph API ci-dessus |\n"
            "\nCe tableau listait autrefois cinq lignes, dont trois que ce formulaire "
            "n'a jamais acceptées. Elles appartiennent à la plateforme.\n"
        ))

        st.warning(t(
            "credentials.meta.warning",
            "⚠️ **Erreurs fréquentes** : "
            "(1) Token personnel depuis Graph API Explorer → expire en 60 jours, utiliser System User. "
            "(2) Préfixe `act_` dans Ad Account ID → supprimer, le dashboard l'ajoute. "
            "(3) Scope `read_insights` uniquement → relancer avec `ads_read` + `ads_management`."
        ))


def _probe_instagram(ig_user_id: str, token: str):
    """(ok, message) for one Instagram Business Account against the shared token.

    Extracted so the platform has a probe of its own. Inlined inside `_test_meta` it
    could only ever run as an optional suffix of another platform's test — Instagram
    was the one logical platform with no entry in `CONNECTION_TESTS`, so
    `tools/artist_preflight.py` step 3 silently skipped it and no artist ever got a
    verdict on it.
    """
    # Shape first, network second. This id lands in the PATH, and `requests` does
    # not percent-encode `/` there: `me/accounts` would make this call /me/accounts
    # with the platform System User token, whose response carries Page tokens.
    if not identity_is_well_formed("instagram", ig_user_id):
        return False, t(
            "credentials.meta.ig_id_malformed",
            "Instagram Business Account ID invalide : il doit être une suite de "
            "chiffres uniquement (ex : 17841400000000000)."
        )
    ri = requests.get(
        f'{META_GRAPH_BASE_URL}/{ig_user_id}',
        params={'access_token': token, 'fields': 'username,followers_count'},
        timeout=10,
        allow_redirects=False,
    )
    ig = ri.json()
    if ri.status_code != 200 or not ig.get('username'):
        err = ig.get('error', {})
        # NEVER `ri.text`. On a 200 with no `username` the error dict is empty, so
        # the fallback used to echo the raw Graph body straight to the tenant —
        # which is how a chosen path returned other people's access tokens.
        detail = err.get('message', 'réponse inattendue de Meta') if isinstance(err, dict) else ''
        detail = str(detail)[:200]
        return False, t(
            "credentials.meta.ig_unreachable",
            "Compte publicitaire OK, mais le compte **Instagram {ig}** est "
            "inaccessible : {detail}\n\n→ Vérifie que c'est bien un compte "
            "**Business/Créateur** relié à une Page, et que la Page a été "
            "partagée avec le Business Manager de la plateforme."
        ).format(ig=ig_user_id, detail=detail)
    return True, t("credentials.meta.ig_ok_suffix",
                   " · Instagram @{user} ✅").format(user=ig['username'])


def _test_instagram(fields: dict):
    """Standalone Instagram connection test — proves the TENANT, not the shared app.

    A blank `ig_user_id` returns False. Never True: a test that passes on a missing
    identity is the `connection-test-proves-app-not-tenant` class, and the artist
    reads it as "connected" while nothing can ever collect.
    """
    import os

    ig_user_id = (fields.get('ig_user_id') or '').strip()
    if not ig_user_id:
        return False, t(
            "credentials.meta.ig_id_missing",
            "Instagram Business Account ID manquant — renseigne-le dans l'onglet Meta "
            "(champ « Instagram Business Account ID »). Sans lui, aucune statistique "
            "Instagram ne peut être collectée."
        )
    token = (fields.get('access_token') or os.getenv('META_ACCESS_TOKEN') or '').strip()
    if not token:
        return False, t(
            "credentials.meta.test_not_configured",
            "App Meta partagée non configurée — contacte l'administrateur."
        )
    try:
        return _probe_instagram(ig_user_id, token)
    except Exception as e:  # noqa: BLE001 — a probe failure is a red verdict, not a crash
        return False, t("credentials.meta.network_error_probe",
                        "Erreur réseau pendant le test Instagram : {err}").format(err=e)
