"""Credentials — Streamlit render/form helpers + save handler.

Type: Sub
Uses: streamlit, pandas, requests, _core, _registry, AirflowTrigger
Pure relocation from the former credentials.py — no logic change.
"""
import pandas as pd
import logging

import streamlit as st

from src.dashboard.utils.i18n import t

from src.utils.tenant_identity import (
    PLATFORM_IDENTITIES,
    malformed_identities,
)
from ._core import (
    find_identity_conflict,
    dags_for_save,
    _STATE_ICON,
    PLATFORM_TO_DAGS,
    _decode_row,
    _encrypt_secrets,
    _mask,
    _save_credentials,
    extract_spotify_artist_id,
)
from ._registry import CONNECTION_TESTS

logger = logging.getLogger(__name__)
from src.dashboard.content.credential_guides_st import render_credential_guide_for
from src.utils.tenant_identity import mirrored_columns, write_platform_identity
from src.dashboard.utils.tz import to_local_datetime


def _declared_from_rows(existing: dict) -> set:
    """{platform: row} → the logical platforms carrying a non-empty identity."""
    import json

    from src.utils.tenant_identity import declared_identities

    extra_by_platform = {}
    for platform, row in (existing or {}).items():
        extra = (row or {}).get("extra_config") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        extra_by_platform[platform] = extra if isinstance(extra, dict) else {}
    return declared_identities(extra_by_platform)


# `_render_global_kpi` lived here until 2026-08-22 and was replaced by
# `src/dashboard/utils/status_matrix.render_status_matrix`. Two reasons, both
# measured, and both worth keeping written down so it does not come back:
#
#   * its second axis was `_fetch_dag_last_states()` — the last run of each DAG
#     ACROSS THE FLEET. It could read 🟢 while this particular artist had zero rows,
#     which is precisely the state two beta sessions were spent on.
#   * it iterated `PLATFORMS`, the four form TABS, while five logical platforms
#     exist. Instagram — whose identity is a field of the Meta tab — had no column,
#     so a tenant whose only identity was `ig_user_id` read "à connecter" while
#     `instagram_daily` collected for them.
#
# The per-tab DAG badge below stays: there, the fleet state is what the caption
# claims to show.


def _render_dag_status_badge(platform_key: str, dag_states: dict) -> None:
    """Inline status badge inside a platform tab."""
    dags = PLATFORM_TO_DAGS.get(platform_key, [])
    if not dags or not dag_states:
        return
    for dag_id in dags:
        info = dag_states.get(dag_id, {})
        state = info.get('state')
        icon = _STATE_ICON.get(state, '⚫')
        date = info.get('date', '—')
        state_label = state or t("credentials.dag_state_never", "jamais exécuté")
        st.caption(t("credentials.dag_badge",
                     "DAG `{dag_id}` — {icon} **{state}** — dernier run : {date}").format(
                         dag_id=dag_id, icon=icon, state=state_label, date=date))


def _render_platform_tab(db, platform_key, platform_info, artist_id,
                         existing_row, fernet_ok, dag_states: dict | None = None):
    fields_def = platform_info['fields']

    # ── Statut DAG ────────────────────────────────────────────────────
    if dag_states is not None:
        _render_dag_status_badge(platform_key, dag_states)

    # ── Guide (rich single-source content + screenshots + example values) ──
    render_credential_guide_for(platform_key)

    # ── Statut actuel ──────────────────────────────────────────────────
    if existing_row:
        updated = existing_row.get('updated_at')
        updated_str = (
            to_local_datetime(updated).strftime('%d/%m/%Y %H:%M') if updated else '?'
        )
        # Expiry badge for platforms that use expiring tokens (Meta)
        expires_at = existing_row.get('expires_at')
        if expires_at is not None:
            try:
                # Both sides tz-aware in UTC. The previous form parsed a
                # `timestamptz` (hence AWARE) and subtracted
                # `pd.Timestamp.utcnow().tz_localize(None)` (NAIVE), which raises
                # `TypeError: Cannot subtract tz-naive and tz-aware datetime-like
                # objects` — verified 2026-08-30. It never fired only because no row
                # carries `expires_at` yet: the first Meta token with an expiry would
                # have broken the Credentials page, the one an artist uses to connect.
                exp = to_local_datetime(expires_at)
                days_left = (exp - pd.Timestamp.now(tz="UTC")).days
                if days_left <= 0:
                    st.error(t("credentials.token_expired",
                               "Token **expiré** depuis le {date}. Renouvellement requis.").format(
                                   date=exp.strftime('%d/%m/%Y')))
                elif days_left <= 15:
                    st.warning(t("credentials.token_expiring",
                                 "Token expire dans **{days} jour(s)** ({date}) — renouvellement recommandé.").format(
                                     days=days_left, date=exp.strftime('%d/%m/%Y')))
                else:
                    st.success(t("credentials.creds_saved_valid",
                                 "Credentials enregistrés — mise à jour : {updated} · Token valide jusqu'au {date} ({days}j)").format(
                                     updated=updated_str, date=exp.strftime('%d/%m/%Y'), days=days_left))
            except Exception:
                st.success(t("credentials.creds_saved",
                             "Credentials enregistrés — mise à jour : {updated}").format(updated=updated_str))
        else:
            st.success(t("credentials.creds_saved",
                         "Credentials enregistrés — mise à jour : {updated}").format(updated=updated_str))
        existing_values = _decode_row(existing_row, fields_def)
    else:
        st.info(t("credentials.no_creds_platform",
                  "Aucun credential enregistré pour cette plateforme."))
        existing_values = {}

    st.markdown("---")

    # ── Formulaire standard (toutes plateformes) ─────────────────────
    with st.form(f"cred_{platform_key}_{artist_id}"):
        st.subheader(t("credentials.form.update", "Mettre à jour"))
        st.caption(t(
            "credentials.form.caption",
            "🔒 Champs secrets chiffrés • Laissez vide pour conserver la valeur actuelle"
        ))

        form_values = {}
        pairs = [fields_def[i:i + 2] for i in range(0, len(fields_def), 2)]

        for pair in pairs:
            cols = st.columns(len(pair))
            for col, field in zip(cols, pair):
                key = field['key']
                existing_val = existing_values.get(key, '')
                field_label = t(f"credentials.field.{key}", field['label'])

                if field['secret']:
                    val = col.text_input(
                        field_label,
                        type='password',
                        placeholder=_mask(existing_val) if existing_val
                        else t("credentials.form.undefined", "Non défini"),
                        help=t("credentials.form.secret_help",
                               "🔒 Chiffré en base — laisser vide pour conserver"),
                        key=f"{platform_key}_{artist_id}_{key}",
                    )
                elif field.get('multiline'):
                    val = col.text_area(
                        field_label,
                        value=existing_val or field.get('default', ''),
                        key=f"{platform_key}_{artist_id}_{key}",
                        height=90,
                    )
                else:
                    val = col.text_input(
                        field_label,
                        value=existing_val or field.get('default', ''),
                        key=f"{platform_key}_{artist_id}_{key}",
                    )
                form_values[key] = val

        submitted = st.form_submit_button(
            t("credentials.form.save", "💾 Enregistrer"),
            type="primary",
            disabled=not fernet_ok,
        )

        if submitted and fernet_ok:
            _handle_save(
                db=db,
                platform_key=platform_key,
                fields_def=fields_def,
                artist_id=artist_id,
                form_values=form_values,
                existing_values=existing_values,
            )

    # ── Titres hébergés ailleurs (SoundCloud seulement) ───────────────
    if platform_key == 'soundcloud':
        _render_claimed_tracks(db, artist_id)

    # ── Test de connexion (hors form) ─────────────────────────────────
    if existing_row and platform_key in CONNECTION_TESTS:
        st.markdown("---")
        if st.button(
            t("credentials.test_button", "🔌 Tester la connexion"),
            key=f"test_{platform_key}_{artist_id}",
        ):
            with st.spinner(t("credentials.testing", "Test en cours…")):
                test_fields = _decode_row(existing_row, fields_def)
                # Who is asking — the SoundCloud probe reads this tenant's declared
                # tracks, so that an artist released under a label is not told to fix
                # the one thing that is already correct.
                test_fields["_artist_id"] = artist_id
                ok, msg = CONNECTION_TESTS[platform_key](test_fields)
                if ok:
                    st.success(msg)
                else:
                    st.error(t("credentials.test_failed",
                               "Connexion échouée : {msg}").format(msg=msg))

    # The Meta token refresh UI lived here until 2026-08-22. It is gone, not fixed.
    #
    # It read `app_id` / `app_secret` / `access_token` out of the tenant's saved
    # fields — and the meta tab declares only `account_id` and `ig_user_id`. So the
    # three were always empty strings, the button always answered "App ID ou App
    # Secret manquant — renseigner d'abord ces champs", and it named fields the form
    # does not have. Every artist who pressed it was sent looking for something that
    # does not exist.
    #
    # The right home for that statement is central, not per-artist: under ADR-006 the
    # Meta token is an APP credential read from META_ACCESS_TOKEN, it is a System User
    # token that does not expire, and `src/utils/central_apps.py::check_meta` already
    # calls /debug_token with the app credentials. Putting a CENTRAL failure on a
    # PER-ARTIST page is what made two beta testers read "my credentials are broken".

def _handle_save(db, platform_key, fields_def, artist_id, form_values, existing_values):
    """Prépare et sauvegarde les credentials chiffrés."""
    try:
        secrets = {}
        extra = {}

        for field in fields_def:
            key = field['key']
            new_val = form_values.get(key, '').strip()

            # Secret vide → conserver l'ancienne valeur
            if not new_val and field['secret']:
                new_val = existing_values.get(key, '')

            if field['secret']:
                secrets[key] = new_val
            elif new_val:
                extra[key] = new_val
            else:
                # Do NOT persist an empty identity. `{"user_id": ""}` is falsy, so
                # every consumer that wrote `creds.get('user_id') or os.getenv(...)`
                # silently switched to the ADMIN's env identity. An artist who opens
                # a tab and saves without filling it in must stay "not connected",
                # not inherit someone else's account.
                extra.pop(key, None)

        # Spotify: the artist supplies their profile URL/ID — normalise it and sync to
        # saas_artists.spotify_artist_id, the per-tenant key both spotify_api_daily
        # (collection list) and the track→tenant bridge read. Store the bare ID back in
        # extra_config too so the form round-trips the normalised value.
        if platform_key == 'spotify':
            sp_id = extract_spotify_artist_id(extra.get('spotify_artist_id', ''))
            # Only write it back when there IS one. This assignment used to be
            # unconditional and ran AFTER the empty-pop above, so Spotify was the
            # single platform that could persist `{"spotify_artist_id": ""}` — the
            # exact shape the pop exists to prevent, and a row that reads as
            # "connected" to every surface that counts rows instead of identities.
            if sp_id:
                extra['spotify_artist_id'] = sp_id
            else:
                extra.pop('spotify_artist_id', None)

        # Meta: N comptes publicitaires → une liste canonique (R53 / ADR-013).
        # Fait AVANT le contrôle de forme, pour que celui-ci voie la valeur qui sera
        # réellement écrite : normaliser après aurait validé la saisie et stocké
        # autre chose.
        if platform_key == 'meta':
            import re as _re

            from src.utils.tenant_identity import (
                malformed_meta_accounts,
                with_meta_accounts,
            )
            typed_extra = extra.pop('extra_account_ids', '')
            accounts = [extra.get('account_id', ''),
                        *[p for p in _re.split(r"[,\n;]+", typed_extra)]]
            extra = with_meta_accounts(extra, accounts)
            bad_accounts = malformed_meta_accounts(extra)
            if bad_accounts:
                st.error(t(
                    "credentials.meta.accounts_malformed",
                    "❌ Compte(s) publicitaire(s) au mauvais format : {bad}. "
                    "Chiffres uniquement, éventuellement préfixés par `act_`, "
                    "**un par ligne**."
                ).format(bad=", ".join(bad_accounts)))
                return

        # Refuse a malformed identity BEFORE anything else touches it. These values
        # are interpolated into REST paths and `requests` does not percent-encode
        # `/` in a path you build, so a free-text id is a URL the tenant chooses.
        # Verified 2026-08-22: ig_user_id = "me/accounts" turned the platform probe
        # into a call to /me/accounts carrying the shared System User token.
        bad = malformed_identities({platform_key: extra})
        if bad:
            logical, value = next(iter(bad.items()))
            spec = PLATFORM_IDENTITIES[logical]
            st.error(t(
                "credentials.identity_malformed",
                "❌ **{field}** n'a pas le format attendu. Attendu : `{shape}`. "
                "Copie l'identifiant seul, sans URL ni caractère autour."
            ).format(field=spec.field, shape=spec.pattern))
            return

        # Refuse an identity another tenant already claims. Nothing in the schema
        # prevents it, and the consequence is not cosmetic: both accounts would
        # collect the same upstream data, and the Spotify DAG refuses to guess
        # whose catalogue it is. Better a clear "no" now than two wrong dashboards.
        #
        # Checked for EVERY logical identity this tab carries, not for the tab.
        # Called with the tab key, the meta tab resolved to `account_id` only and
        # `ig_user_id` was never compared against anyone — the uniqueness rule was
        # present, derived, tested, and unreachable from the one call site that
        # matters. The test passed because it called with the logical name, which
        # the save path never does.
        for logical, spec in PLATFORM_IDENTITIES.items():
            if spec.storage != platform_key or not extra.get(spec.field):
                continue
            conflict = find_identity_conflict(db, artist_id, logical, extra)
            if not conflict:
                continue
            # `_other` is the tenant holding it — never rendered, see _core.py.
            field, value, _other = conflict
            st.error(t(
                "credentials.identity_taken",
                "❌ **{field} = {value}** est déjà rattaché à un autre compte. "
                "Un identifiant de plateforme ne peut appartenir qu'à un seul "
                "artiste — vérifie que c'est bien le tien. Si tu penses qu'il "
                "s'agit d'une erreur, contacte l'administrateur."
            ).format(field=field, value=value))
            return

        # `''` means "do not touch the stored secret", NOT "erase it" — see the
        # contract in `_save_credentials`. The soundcloud and meta tabs declare no
        # secret field at all, so they ALWAYS land here with an empty blob while
        # their rows hold a rotated refresh_token / the System User token.
        encrypted_blob = _encrypt_secrets(secrets) if any(secrets.values()) else ''
        _save_credentials(db, artist_id, platform_key, encrypted_blob, extra)

        # Spotify's identity is mirrored on saas_artists.spotify_artist_id, which is
        # what spotify_api_daily reads. The mirror list lives in one module so a second
        # writer cannot miss it — tools/create_canary.py did, and produced a tenant that
        # looked connected everywhere and collected nothing (2026-08-21).
        _mirror = mirrored_columns().get(platform_key)
        if _mirror:
            write_platform_identity(db, artist_id, platform_key, extra)

        # No Meta token expiry probe here — deliberately.
        #
        # It called _fetch_meta_token_expiry(access_token, app_id, app_secret) with
        # three values the meta tab never collects (it declares account_id and
        # ig_user_id only), so the probe returned None every time and the else-branch
        # fired on EVERY save, for EVERY artist: "⚠️ Impossible de récupérer la date
        # d'expiration du token Meta … Le renouvellement automatique ne fonctionnera
        # pas". A permanent warning about a central credential, shown on a per-artist
        # page, is indistinguishable from "your credentials are broken" — which is
        # what two beta testers reported.
        #
        # The token is a System User APP credential (ADR-006) that does not expire;
        # its health is reported by src/utils/central_apps.py::check_meta, which the
        # nightly alert_monitor reads.

        # Auto-trigger the first data pull for every identity this save declared.
        # One tab can carry several: saving the Meta tab with both an ad account and
        # an Instagram business account must start BOTH collections. Keyed on the tab
        # it only ever started meta_ads_api_daily, so an artist who connected
        # Instagram got no first pull at all.
        # Non-blocking: a DAG-trigger failure must NOT invalidate the credential save.
        for dag_id in dags_for_save(platform_key, extra):
            try:
                import os
                from src.utils.airflow_trigger import AirflowTrigger
                # Accept either env naming: the dashboard container exposes the Airflow
                # admin creds as AIRFLOW_USERNAME/AIRFLOW_PASSWORD (docker-compose), while
                # AIRFLOW_ADMIN_* is the .env name. A hard os.environ[...] on the wrong
                # name silently broke every post-save auto-trigger ("credentials OK but
                # no data"). Read both; never KeyError.
                trigger = AirflowTrigger(
                    base_url=os.getenv('AIRFLOW_BASE_URL', 'http://localhost:8080'),
                    username=(os.getenv('AIRFLOW_ADMIN_USERNAME')
                              or os.getenv('AIRFLOW_USERNAME', 'admin')),
                    password=(os.getenv('AIRFLOW_ADMIN_PASSWORD')
                              or os.getenv('AIRFLOW_PASSWORD', '')),
                )
                result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})
                if result.get('success'):
                    st.toast(t("credentials.collect_started",
                               "🚀 Collecte {platform} lancée — données disponibles dans ~2 min").format(
                                   platform=platform_key), icon="✅")
                else:
                    # `trigger_dag` RETURNS {'success': False} on an HTTP error — it
                    # never raises, so the `except` below could not see the most
                    # likely failures (Airflow unreachable, wrong credentials, 403).
                    # The artist read "✅ Credentials enregistrés", no first pull ever
                    # ran, and nothing said so: literally "I connected it and nothing
                    # happened". Same class as `delivery-failure-logged-as-success`,
                    # one layer up.
                    logger.error("post-save trigger of %s failed for artist %s: %s",
                                 dag_id, artist_id, result.get('error'))
                    st.warning(t(
                        "credentials.dag_trigger_refused",
                        "⚠️ Identifiants enregistrés, mais la première collecte "
                        "**{dag}** n'a pas pu démarrer. Tes données arriveront à la "
                        "prochaine collecte automatique (cette nuit). Si rien n'est "
                        "arrivé demain, préviens-nous."
                    ).format(dag=dag_id))
            except Exception as trigger_err:
                logger.error("post-save trigger of %s raised for artist %s: %s",
                             dag_id, artist_id, type(trigger_err).__name__)
                st.warning(t("credentials.dag_trigger_failed",
                             "⚠️ Identifiants enregistrés, mais la première collecte "
                             "n'a pas pu démarrer ({err}). Elle repartira cette nuit."
                             ).format(err=type(trigger_err).__name__))

        st.success(t("credentials.save_ok",
                     "✅ Credentials {platform} enregistrés.").format(platform=platform_key))
        st.rerun()

    except Exception as e:
        st.error(t("credentials.save_error",
                   "❌ Erreur lors de la sauvegarde : {err}").format(err=e))


def _render_claimed_tracks(db, artist_id: int) -> None:
    """Declare tracks released under someone else's account.

    For an artist signed to a label or part of a collective, their own profile is
    empty and always will be — GRiNCH's has `track_count=0`. Telling them to check
    their User ID is telling them to fix the one thing that is already right. The
    collectable unit for them is the TRACK: `GET /tracks/{id}` returns the play count
    whatever profile hosts the upload.

    One URL per line, resolved to a numeric track id and stored in
    `track_platform_link`. A track already claimed by another tenant is refused with
    a message — two artists on one label would otherwise each collect the other's
    plays under their own id.
    """
    from src.utils.claimed_tracks import (
        TrackAlreadyClaimedError, claim_track, claimed_track_ids,
        is_soundcloud_track_url, release_claim,
    )

    with st.expander(t("credentials.soundcloud.claimed_header",
                       "🎵 Mes titres hébergés sur d'autres comptes (label, collectif…)"),
                     expanded=False):
        st.caption(t(
            "credentials.soundcloud.claimed_help",
            "Si tes sorties paraissent sous le compte d'un label ou d'un collectif, ton "
            "propre profil est vide et le restera. Colle ici l'URL de CHAQUE titre qui "
            "est à toi — une par ligne. On collectera leurs écoutes même s'ils sont "
            "hébergés ailleurs. Un titre ne peut être revendiqué que par un seul compte."
        ))

        existing = claimed_track_ids(db, artist_id, 'soundcloud')
        if existing:
            st.markdown(t("credentials.soundcloud.claimed_current",
                          "**{n} titre(s) déclaré(s)** :").format(n=len(existing)))
            for ref in existing:
                cols = st.columns([5, 1])
                cols[0].code(f"track {ref}", language=None)
                if cols[1].button(t("common.remove", "Retirer"),
                                  key=f"unclaim_{artist_id}_{ref}"):
                    release_claim(db, artist_id, 'soundcloud', ref)
                    st.rerun()

        urls = st.text_area(
            t("credentials.soundcloud.claimed_input", "URLs SoundCloud (une par ligne)"),
            placeholder="https://soundcloud.com/le-label/mon-titre",
            key=f"claimed_input_{artist_id}",
        )
        if st.button(t("credentials.soundcloud.claimed_add", "➕ Déclarer ces titres"),
                     key=f"claim_btn_{artist_id}"):
            _handle_claims(db, artist_id, urls, claim_track,
                           is_soundcloud_track_url, TrackAlreadyClaimedError)


def _handle_claims(db, artist_id, urls, claim_track, is_track_url, AlreadyClaimed):
    """Resolve each pasted URL and record the claim. Reports every line by name."""
    from src.utils.platform_probes import probe  # noqa: F401 — keeps the seam honest

    lines = [ln.strip() for ln in (urls or "").splitlines() if ln.strip()]
    if not lines:
        st.warning(t("credentials.soundcloud.claimed_empty",
                     "Colle au moins une URL de titre."))
        return

    resolved, failed = 0, []
    for line in lines:
        if not is_track_url(line):
            # The obvious mistake for someone who was just told their profile is not
            # the answer: pasting the profile.
            failed.append((line, t("credentials.soundcloud.claimed_not_a_track",
                                   "ce n'est pas une URL de TITRE (il faut "
                                   "…/compte/nom-du-titre)")))
            continue
        try:
            track_id, title = _resolve_soundcloud_track(line)
        except Exception as e:  # noqa: BLE001 — one bad line must not lose the others
            failed.append((line, f"introuvable ({type(e).__name__})"))
            continue
        if track_id is None:
            failed.append((line, t("credentials.soundcloud.claimed_unresolved",
                                   "introuvable ou privé")))
            continue
        try:
            claim_track(db, artist_id, 'soundcloud', track_id, title or line)
            resolved += 1
        except AlreadyClaimed:
            # Our own sentence, not the exception's. A view must not render an
            # exception object even when we wrote its message — the next person to
            # raise here may not be us (`test_credentials_security`).
            failed.append((line, t(
                "credentials.soundcloud.claimed_taken",
                "ce titre est déjà revendiqué par un autre compte. Un titre "
                "n'appartient qu'à un artiste — contacte-nous si c'est une erreur.")))

    if resolved:
        st.success(t("credentials.soundcloud.claimed_ok",
                     "✅ {n} titre(s) déclaré(s). Ils seront collectés à la prochaine "
                     "exécution.").format(n=resolved))
    for line, why in failed:
        st.error(f"{line} — {why}")
    if resolved:
        st.rerun()


def _resolve_soundcloud_track(url: str):
    """(track_id, title) for a public SoundCloud track URL, via the shared app."""
    import os

    import requests

    cid = os.getenv('SOUNDCLOUD_CLIENT_ID', '')
    sec = os.getenv('SOUNDCLOUD_CLIENT_SECRET', '')
    if not cid or not sec:
        raise RuntimeError("app SoundCloud partagée non configurée (admin)")
    tok = requests.post(
        "https://api.soundcloud.com/oauth2/token",
        data={'grant_type': 'client_credentials', 'client_id': cid,
              'client_secret': sec},
        timeout=15, allow_redirects=False).json().get('access_token')
    r = requests.get("https://api.soundcloud.com/resolve",
                     headers={'Authorization': f'OAuth {tok}'},
                     params={'url': url}, timeout=15, allow_redirects=True)
    if r.status_code != 200:
        return None, None
    d = r.json()
    # `/resolve` happily returns a USER for a profile URL. Claiming one would store a
    # user id in a column that means "track id" — silently, and forever.
    if d.get('kind') != 'track':
        return None, None
    return str(d.get('id')), d.get('title')
