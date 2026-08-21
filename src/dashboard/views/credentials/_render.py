"""Credentials — Streamlit render/form helpers + save handler.

Type: Sub
Uses: streamlit, pandas, requests, _core, _registry, AirflowTrigger
Pure relocation from the former credentials.py — no logic change.
"""
import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t

from ._core import (
    find_identity_conflict,
    dags_for_save,
    _STATE_ICON,
    PLATFORM_TO_DAGS,
    _decode_row,
    _encrypt_secrets,
    _mask,
    _save_credentials,
    app_level_configured,
    extract_spotify_artist_id,
)
from ._registry import PLATFORMS, CONNECTION_TESTS
from src.dashboard.content.credential_guides_st import render_credential_guide_for
from src.utils.tenant_identity import mirrored_columns, write_platform_identity


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


def _render_global_kpi(existing: dict, dag_states: dict) -> None:
    """Summary row: one metric per platform showing credentials + last DAG run."""
    cols = st.columns(len(PLATFORMS))
    for col, (platform_key, platform_info) in zip(cols, PLATFORMS.items()):
        # DECLARED, not "a row exists". `platform_key in existing` showed ✅
        # "Connecté — ton compte" for a tab the artist opened and saved blank, while
        # the readiness matrix showed ⚪ for the same tenant on the same data.
        has_db_creds = platform_key in _declared_from_rows(existing)
        # App-level keys (env / config.yaml) count as configured too — the
        # collectors fall back to them, so a missing DB row is not "unconfigured".
        has_app_creds = app_level_configured(platform_key)
        dags = PLATFORM_TO_DAGS.get(platform_key, [])

        # Last run state across all DAGs for this platform (worst state wins)
        states = [dag_states.get(d, {}).get('state') for d in dags]
        if 'failed' in states:
            run_icon = '🔴'
            run_label = t("credentials.kpi.run_failed", "Dernier run : FAILED")
        elif 'running' in states:
            run_icon = '🔵'
            run_label = t("credentials.kpi.run_running", "En cours")
        elif 'success' in states:
            run_icon = '🟢'
            run_label = t("credentials.kpi.run_ok", "Dernier run : OK")
        elif not dag_states:
            run_icon = '⚫'
            run_label = t("credentials.kpi.run_unreachable", "Airflow inaccessible")
        else:
            run_icon = '⚫'
            run_label = t("credentials.kpi.run_never", "Jamais exécuté")

        # Three honest states: only a per-artist row means "you connected your account".
        # The shared platform app being present (env) is NOT "done" — it just means the
        # artist can connect with a single identifier. Conflating the two made the page
        # read "configured" when the artist had done nothing.
        if has_db_creds:
            creds_icon = '✅'
            creds_label = t("credentials.kpi.connected", "Connecté — ton compte")
        elif has_app_creds:
            creds_icon = '🟢'
            creds_label = t("credentials.kpi.app_ready", "App prête — à connecter")
        else:
            creds_icon = '⚪'
            creds_label = t("credentials.kpi.not_configured", "À connecter")

        col.metric(
            label=platform_info['label'],
            value=f"{creds_icon} {creds_label}",
            delta=f"{run_icon} {run_label}",
            delta_color="off",
        )


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
            pd.to_datetime(updated).strftime('%d/%m/%Y %H:%M') if updated else '?'
        )
        # Expiry badge for platforms that use expiring tokens (Meta)
        expires_at = existing_row.get('expires_at')
        if expires_at is not None:
            try:
                exp = pd.to_datetime(expires_at)
                days_left = (exp - pd.Timestamp.utcnow().tz_localize(None)).days
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

    # ── Test de connexion (hors form) ─────────────────────────────────
    if existing_row and platform_key in CONNECTION_TESTS:
        st.markdown("---")
        if st.button(
            t("credentials.test_button", "🔌 Tester la connexion"),
            key=f"test_{platform_key}_{artist_id}",
        ):
            with st.spinner(t("credentials.testing", "Test en cours…")):
                test_fields = _decode_row(existing_row, fields_def)
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

        # Refuse an identity another tenant already claims. Nothing in the schema
        # prevents it, and the consequence is not cosmetic: both accounts would
        # collect the same upstream data, and the Spotify DAG refuses to guess
        # whose catalogue it is. Better a clear "no" now than two wrong dashboards.
        conflict = find_identity_conflict(db, artist_id, platform_key, extra)
        if conflict:
            field, value, _other = conflict
            st.error(t(
                "credentials.identity_taken",
                "❌ **{field} = {value}** est déjà rattaché à un autre compte. "
                "Un identifiant de plateforme ne peut appartenir qu'à un seul "
                "artiste — vérifie que c'est bien le tien. Si tu penses qu'il "
                "s'agit d'une erreur, contacte l'administrateur."
            ).format(field=field, value=value))
            return

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
            except Exception as trigger_err:
                st.warning(t("credentials.dag_trigger_failed",
                             "⚠️ Credentials enregistrés mais déclenchement DAG échoué : {err}").format(
                                 err=trigger_err))

        st.success(t("credentials.save_ok",
                     "✅ Credentials {platform} enregistrés.").format(platform=platform_key))
        st.rerun()

    except Exception as e:
        st.error(t("credentials.save_error",
                   "❌ Erreur lors de la sauvegarde : {err}").format(err=e))
