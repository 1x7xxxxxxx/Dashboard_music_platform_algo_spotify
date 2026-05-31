"""Credentials — Streamlit render/form helpers + save handler.

Type: Sub
Uses: streamlit, pandas, requests, _core, _registry, AirflowTrigger
Pure relocation from the former credentials.py — no logic change.
"""
import requests
import pandas as pd
import streamlit as st

from src.utils.meta_config import META_GRAPH_BASE_URL

from ._core import (
    _PLATFORM_DAG_MAP,
    _STATE_ICON,
    META_TOKEN_NEVER_EXPIRES,
    PLATFORM_TO_DAGS,
    _decode_row,
    _encrypt_secrets,
    _fetch_meta_token_expiry,
    _mask,
    _save_credentials,
    app_level_configured,
)
from ._registry import PLATFORMS, CONNECTION_TESTS, _render_platform_guide


def _render_global_kpi(existing: dict, dag_states: dict) -> None:
    """Summary row: one metric per platform showing credentials + last DAG run."""
    cols = st.columns(len(PLATFORMS))
    for col, (platform_key, platform_info) in zip(cols, PLATFORMS.items()):
        has_db_creds = platform_key in existing
        # App-level keys (env / config.yaml) count as configured too — the
        # collectors fall back to them, so a missing DB row is not "unconfigured".
        has_app_creds = app_level_configured(platform_key)
        has_creds = has_db_creds or has_app_creds
        dags = PLATFORM_TO_DAGS.get(platform_key, [])

        # Last run state across all DAGs for this platform (worst state wins)
        states = [dag_states.get(d, {}).get('state') for d in dags]
        if 'failed' in states:
            run_icon = '🔴'
            run_label = 'Dernier run : FAILED'
        elif 'running' in states:
            run_icon = '🔵'
            run_label = 'En cours'
        elif 'success' in states:
            run_icon = '🟢'
            run_label = 'Dernier run : OK'
        elif not dag_states:
            run_icon = '⚫'
            run_label = 'Airflow inaccessible'
        else:
            run_icon = '⚫'
            run_label = 'Jamais exécuté'

        creds_icon = '✅' if has_creds else '❌'
        if has_db_creds:
            creds_label = 'Connecté'
        elif has_app_creds:
            creds_label = 'Configuré (clé plateforme)'
        else:
            creds_label = 'Non configuré'

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
        st.caption(f"DAG `{dag_id}` — {icon} **{state or 'jamais exécuté'}** — dernier run : {date}")


def _render_platform_tab(db, platform_key, platform_info, artist_id,
                         existing_row, fernet_ok, dag_states: dict | None = None):
    fields_def = platform_info['fields']

    # ── Statut DAG ────────────────────────────────────────────────────
    if dag_states is not None:
        _render_dag_status_badge(platform_key, dag_states)

    # ── Guide ──────────────────────────────────────────────────────────
    _render_platform_guide(platform_key)

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
                    st.error(f"Token **expiré** depuis le {exp.strftime('%d/%m/%Y')}. Renouvellement requis.")
                elif days_left <= 15:
                    st.warning(f"Token expire dans **{days_left} jour(s)** ({exp.strftime('%d/%m/%Y')}) — renouvellement recommandé.")
                else:
                    st.success(f"Credentials enregistrés — mise à jour : {updated_str} · Token valide jusqu'au {exp.strftime('%d/%m/%Y')} ({days_left}j)")
            except Exception:
                st.success(f"Credentials enregistrés — mise à jour : {updated_str}")
        else:
            st.success(f"Credentials enregistrés — mise à jour : {updated_str}")
        existing_values = _decode_row(existing_row, fields_def)
    else:
        st.info("Aucun credential enregistré pour cette plateforme.")
        existing_values = {}

    st.markdown("---")

    # ── Formulaire standard (toutes plateformes) ─────────────────────
    with st.form(f"cred_{platform_key}_{artist_id}"):
        st.subheader("Mettre à jour")
        st.caption(
            "🔒 Champs secrets chiffrés • Laissez vide pour conserver la valeur actuelle"
        )

        form_values = {}
        pairs = [fields_def[i:i + 2] for i in range(0, len(fields_def), 2)]

        for pair in pairs:
            cols = st.columns(len(pair))
            for col, field in zip(cols, pair):
                key = field['key']
                existing_val = existing_values.get(key, '')

                if field['secret']:
                    val = col.text_input(
                        field['label'],
                        type='password',
                        placeholder=_mask(existing_val) if existing_val else 'Non défini',
                        help="🔒 Chiffré en base — laisser vide pour conserver",
                        key=f"{platform_key}_{artist_id}_{key}",
                    )
                else:
                    val = col.text_input(
                        field['label'],
                        value=existing_val or field.get('default', ''),
                        key=f"{platform_key}_{artist_id}_{key}",
                    )
                form_values[key] = val

        submitted = st.form_submit_button(
            "💾 Enregistrer",
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
            "🔌 Tester la connexion",
            key=f"test_{platform_key}_{artist_id}",
        ):
            with st.spinner("Test en cours…"):
                test_fields = _decode_row(existing_row, fields_def)
                ok, msg = CONNECTION_TESTS[platform_key](test_fields)
                if ok:
                    st.success(msg)
                else:
                    st.error(f"Connexion échouée : {msg}")

    # ── Meta : bouton renouvellement automatique du token ─────────────
    if platform_key == 'meta' and existing_row:
        st.markdown("---")
        st.markdown("#### Renouvellement automatique du token")
        st.caption(
            "Échange le token actuel contre un nouveau token de 60 jours via l'API Meta. "
            "Le token doit être encore valide pour pouvoir être échangé. "
            "Le DAG fait ce renouvellement automatiquement quand il reste ≤ 15 jours."
        )
        if st.button("🔄 Rafraîchir le token Meta", key=f"meta_refresh_{artist_id}", type="primary"):
            with st.spinner("Échange du token en cours…"):
                fields_def_meta = PLATFORMS['meta']['fields']
                current = _decode_row(existing_row, fields_def_meta)
                app_id = current.get('app_id', '')
                app_secret = current.get('app_secret', '')
                access_token = current.get('access_token', '')

                if not app_id or not app_secret:
                    st.error("App ID ou App Secret manquant — renseigner d'abord ces champs.")
                elif not access_token:
                    st.error("Access Token manquant — impossible d'effectuer l'échange.")
                else:
                    try:
                        r = requests.get(
                            f'{META_GRAPH_BASE_URL}/oauth/access_token',
                            params={
                                'grant_type': 'fb_exchange_token',
                                'client_id': app_id,
                                'client_secret': app_secret,
                                'fb_exchange_token': access_token,
                            },
                            timeout=10,
                            allow_redirects=False,
                        )
                        data = r.json()
                        if r.status_code == 200 and data.get('access_token'):
                            new_token = data['access_token']
                            # System User tokens come back with expires_in == 0 (never expire).
                            # Default to 0 (not 60 days) so we don't stamp a false expiry.
                            expires_in = data.get('expires_in', 0)
                            # Save new token (expires_at handled below)
                            secrets = {f['key']: current.get(f['key'], '') for f in fields_def_meta if f['secret']}
                            secrets['access_token'] = new_token
                            encrypted_blob = _encrypt_secrets(secrets)
                            _save_credentials(db, artist_id, 'meta', encrypted_blob,
                                              {f['key']: current.get(f['key'], '') for f in fields_def_meta if not f['secret']})
                            if expires_in and expires_in > 0:
                                new_expires = pd.Timestamp.utcnow() + pd.Timedelta(seconds=expires_in)
                                db.execute_query(
                                    "UPDATE artist_credentials SET expires_at = %s WHERE artist_id = %s AND platform = 'meta'",
                                    (new_expires.to_pydatetime(), artist_id)
                                )
                                st.success(f"✅ Token renouvelé — expire le {new_expires.strftime('%d/%m/%Y')} ({expires_in // 86400} jours)")
                            else:
                                db.execute_query(
                                    "UPDATE artist_credentials SET expires_at = NULL WHERE artist_id = %s AND platform = 'meta'",
                                    (artist_id,)
                                )
                                st.success("✅ Token enregistré — n'expire pas (System User).")
                            st.rerun()
                        else:
                            err = data.get('error', {})
                            st.error(f"Échec : {err.get('message', data)} — si le token est expiré, générer un nouveau token manuellement via Graph API Explorer.")
                    except Exception as e:
                        st.error(f"Erreur réseau : {e}")


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
            else:
                extra[key] = new_val

        encrypted_blob = _encrypt_secrets(secrets) if any(secrets.values()) else ''
        _save_credentials(db, artist_id, platform_key, encrypted_blob, extra)

        # Auto-populate expires_at for Meta tokens so the weekly refresh DAG
        # and proactive refresh in the collector can function without manual input.
        if platform_key == 'meta':
            expiry = _fetch_meta_token_expiry(
                secrets.get('access_token', ''),
                extra.get('app_id', ''),
                secrets.get('app_secret', ''),
            )
            if expiry == META_TOKEN_NEVER_EXPIRES:
                # System User token — never expires. NULL so meta_token_refresh skips it
                # (Brick 24) instead of attempting a pointless fb_exchange_token.
                db.execute_query(
                    "UPDATE artist_credentials SET expires_at = NULL "
                    "WHERE artist_id = %s AND platform = 'meta'",
                    (artist_id,),
                )
                st.info("ℹ️ Token System User détecté — n'expire pas, aucun renouvellement requis.")
            elif expiry:
                db.execute_query(
                    "UPDATE artist_credentials SET expires_at = %s "
                    "WHERE artist_id = %s AND platform = 'meta'",
                    (expiry, artist_id),
                )
            else:
                st.warning(
                    "⚠️ Impossible de récupérer la date d'expiration du token Meta "
                    "(app_id / app_secret manquants ou API inaccessible). "
                    "Le renouvellement automatique ne fonctionnera pas jusqu'au prochain save."
                )

        # Auto-trigger first data pull for this artist on this platform.
        # Non-blocking: a DAG-trigger failure must NOT invalidate the credential save.
        dag_id = _PLATFORM_DAG_MAP.get(platform_key)
        if dag_id:
            try:
                import os
                from src.utils.airflow_trigger import AirflowTrigger
                trigger = AirflowTrigger(
                    base_url=os.getenv('AIRFLOW_BASE_URL', 'http://localhost:8080'),
                    username=os.getenv('AIRFLOW_ADMIN_USERNAME', 'admin'),
                    password=os.environ['AIRFLOW_ADMIN_PASSWORD'],
                )
                result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})
                if result.get('success'):
                    st.toast(f"🚀 Collecte {platform_key} lancée — données disponibles dans ~2 min", icon="✅")
            except Exception as trigger_err:
                st.warning(f"⚠️ Credentials enregistrés mais déclenchement DAG échoué : {trigger_err}")

        st.success(f"✅ Credentials {platform_key} enregistrés.")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Erreur lors de la sauvegarde : {e}")
