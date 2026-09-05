"""Credentials — Meta / Instagram connection test + setup guide.

Type: Sub
Uses: requests, streamlit, META_GRAPH_BASE_URL
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests

from src.utils.meta_config import META_GRAPH_BASE_URL
from src.dashboard.utils.i18n import t
from src.utils.tenant_identity import identity_is_well_formed, meta_ad_account_ids
from src.utils.meta_graph import MetaGraphError
from src.utils.meta_graph import get as graph_get
from src.utils.platform_probes import (  # la situation que cette sonde nomme
    SHARING_MISSING,
    IDENTITY_MISSING,
    UNREACHABLE,
    tagged,
)


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
        # TOUS les comptes déclarés, pas seulement le premier (R53 / ADR-013).
        # Ne sonder que `account_id` rendrait le test vert alors que le deuxième
        # compte d'une agence n'est pas partagé avec l'app — et ce partage manquant
        # est précisément la panne Meta la plus fréquente (cas Benken, 2026-06-19).
        # Un test vert qui ne prouve qu'un compte sur trois est un vert qui ne veut
        # rien dire, et c'est le seul écran où l'artiste peut encore corriger.
        accounts = meta_ad_account_ids(fields)
        if not accounts:
            return False, tagged(t("credentials.meta.account_missing",
                            "App Meta OK, mais ton **Ad Account ID** n'est pas renseigné — "
                            "sans lui aucune donnée ne peut être collectée. Il se lit dans "
                            "l'URL du Gestionnaire de publicités, après `act=`."), IDENTITY_MISSING)
        names = []
        for act_id in accounts:
            ok, detail = _probe_ad_account(act_id, token)
            if not ok:
                return False, detail
            names.append(detail)
        acc = {'name': " · ".join(names)}
        act_id = accounts[0]
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
        return False, tagged(t("credentials.probe_network_error",
                        "Erreur réseau ({err}) — réessaie dans un instant. Si ça "
                        "persiste, contacte l'administrateur.").format(
                            err=type(e).__name__), UNREACHABLE)



def _probe_ad_account(act_id: str, token: str) -> tuple:
    """(True, display_name) or (False, actionable message) for ONE ad account."""
    # Shape before the network, same reason as ig_user_id below: this lands in the
    # PATH. The forced `act_` prefix blocks the trivial payload but not a traversal,
    # and "probably safe because of a prefix" is not a control.
    if not identity_is_well_formed("meta", act_id):
        return False, t(
            "credentials.meta.account_malformed",
            "Ad Account ID invalide : chiffres uniquement, éventuellement "
            "préfixés par `act_` (ex : 567214713853881)."
        )
    # Par `meta_graph`, la seule porte vers Graph : elle porte la version, résout le
    # jeton une fois et traduit les codes d'erreur au même endroit pour tout le monde.
    # Écrit et gardé le 2026-09-05, il n'avait **aucun appelant** — une couche
    # débranchée pourrit, et son premier branchement est ici.
    detail = ""
    acc: dict = {}
    try:
        acc = graph_get(act_id, token=token, fields="name,account_status")
    except MetaGraphError as exc:
        # `.explanation` traduit le code ; le message brut de Meta est déjà nettoyé
        # de l'URL par le client, donc rien n'expose le jeton ici.
        detail = exc.explanation[:200]
    if not acc.get('id', acc.get('name')):
        # Ce message nommait l'ANCIEN geste — « Apps → ETL_DASHBOARD_SPOTIFY →
        # Business Assets » — pendant que le guide, deux colonnes plus loin, en
        # donnait un autre. Deux surfaces qui se contredisent, et celle-ci décrivait
        # un chemin infaisable : une app n'apparaît que dans le Business Manager qui
        # la possède. Elles disent maintenant la MÊME chose, et une seule constante
        # porte le numéro.
        from src.dashboard.content.credential_guides import META_BUSINESS_ID
        _where = (f"colle **`{META_BUSINESS_ID}`**" if META_BUSINESS_ID
                  else "colle **notre numéro de Business** (demande-le nous)")
        return False, tagged(t(
            "credentials.meta.account_unreachable",
            "Compte publicitaire **{act}** : il ne nous est pas encore partagé. "
            "{detail}\n\n"
            "→ Business Manager → **Comptes publicitaires** → ton compte → "
            "**Partenaires** → **Attribuer un partenaire** → {where} → rôle "
            "**Analyste**."
        ).format(act=act_id, detail=detail, where=_where), SHARING_MISSING)
    return True, str(acc.get('name', act_id))


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
        return False, tagged(t(
            "credentials.meta.ig_id_missing",
            "Instagram Business Account ID manquant — renseigne-le dans l'onglet Meta "
            "(champ « Instagram Business Account ID »). Sans lui, aucune statistique "
            "Instagram ne peut être collectée."
        ), IDENTITY_MISSING)
    token = (fields.get('access_token') or os.getenv('META_ACCESS_TOKEN') or '').strip()
    if not token:
        return False, t(
            "credentials.meta.test_not_configured",
            "App Meta partagée non configurée — contacte l'administrateur."
        )
    try:
        return _probe_instagram(ig_user_id, token)
    except Exception as e:  # noqa: BLE001 — a probe failure is a red verdict, not a crash
        return False, tagged(t("credentials.meta.network_error_probe",
                        "Erreur réseau pendant le test Instagram : {err}").format(err=e), UNREACHABLE)

# ── L'assistant « je colle l'adresse, tu trouves mon numéro » ────────────────

# Le portail, et la page EXACTE où l'adresse porte `act=`. Ouvrir la racine de
# adsmanager laisse l'artiste sur un écran de sélection dont l'URL ne nomme encore
# aucun compte — c'est la moitié du « c'est confus » du 2026-09-04.
ADS_MANAGER_URL = "https://adsmanager.facebook.com/adsmanager/manage/campaigns"
