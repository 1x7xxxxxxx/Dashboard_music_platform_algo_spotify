"""Auth module — Streamlit Authenticator (Brick 2).

Gère le login, la session et l'injection d'artist_id.
Config dans config/config.yaml sous la clé 'auth'.

Génération d'un hash bcrypt :
    python -c "import streamlit_authenticator as stauth; \
               print(stauth.Hasher(['monmotdepasse']).generate()[0])"
"""
import sys
from pathlib import Path
from typing import Optional
import streamlit as st
import streamlit_authenticator as stauth

# Garantit que la racine du projet est dans sys.path (chemin absolu)
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.utils.config_loader import config_loader


def _load_auth_config() -> Optional[dict]:
    config = config_loader.load()
    return config.get('auth', None)


def require_login() -> bool:
    """Affiche le formulaire de login si non authentifié.

    Stocke dans st.session_state :
        - authenticated (bool)
        - username     (str)
        - name         (str)
        - artist_id    (int | None)  — None = admin (voit tout)
        - role         (str)         — 'admin' | 'artist'

    Retourne True si l'utilisateur est connecté, False sinon (→ st.stop()).
    """
    auth_config = _load_auth_config()

    if auth_config is None:
        # Development mode: no 'auth' section in config.yaml → auto-login as admin.
        # SECURITY: this bypass must never reach production.
        st.warning(
            "**DEV MODE** — Authentication disabled (no `auth` section in config.yaml). "
            "All sessions are logged in as admin.",
            icon="⚠️",
        )
        st.session_state.setdefault('authenticated', True)
        st.session_state.setdefault('artist_id', 1)
        st.session_state.setdefault('role', 'admin')
        st.session_state.setdefault('name', 'Dev')
        return True

    credentials = auth_config.get('credentials', {'usernames': {}})
    cookie = auth_config.get('cookie', {})

    authenticator = stauth.Authenticate(
        credentials,
        cookie.get('name', 'music_dashboard'),
        cookie.get('key', 'changeme_32_chars_min'),
        cookie.get('expiry_days', 30),
    )
    # Garder l'authenticator en session pour le logout
    st.session_state['_authenticator'] = authenticator

    # API 0.4.x : login() sans titre, retourne None — statut dans session_state
    # API 0.3.x : login('title', 'location') retourne (name, status, username)
    try:
        result = authenticator.login(location='main')
        # 0.3.x retourne un tuple
        if isinstance(result, tuple):
            name, auth_status, username = result
        else:
            # 0.4.x : lire depuis session_state
            auth_status = st.session_state.get('authentication_status')
            name = st.session_state.get('name', '')
            username = st.session_state.get('username', '')
    except TypeError:
        # Fallback 0.3.x si location= non accepté
        result = authenticator.login('Connexion', 'main')
        name, auth_status, username = result

    if auth_status:
        user_data = credentials.get('usernames', {}).get(username, {})
        st.session_state['authenticated'] = True
        st.session_state['username'] = username
        st.session_state['name'] = name or user_data.get('name', username)
        st.session_state['artist_id'] = user_data.get('artist_id', 1)
        st.session_state['role'] = user_data.get('role', 'artist')
        return True

    if auth_status is False:
        st.error("Nom d'utilisateur ou mot de passe incorrect.")
    else:
        st.info("Entrez vos identifiants pour accéder au tableau de bord.")
    return False


def show_user_sidebar():
    """Affiche le nom d'utilisateur et le bouton logout dans la sidebar."""
    name = st.session_state.get('name', '')
    role = st.session_state.get('role', 'artist')
    artist_id = st.session_state.get('artist_id')

    role_label = '👑 Admin' if role == 'admin' else '🎤 Artist'
    st.sidebar.markdown(f"**{role_label}** — {name}")
    if artist_id is not None:
        st.sidebar.caption(f"artist_id = {artist_id}")
    else:
        st.sidebar.caption("Accès global (tous artistes)")

    authenticator = st.session_state.get('_authenticator')
    if authenticator:
        try:
            # 0.4.x : logout(button_name=..., location=...)
            authenticator.logout(button_name='Déconnexion', location='sidebar')
        except TypeError:
            # 0.3.x : logout('label', 'location')
            authenticator.logout('Déconnexion', 'sidebar')
    else:
        if st.sidebar.button('Déconnexion'):
            for key in ['authenticated', 'username', 'name', 'artist_id', 'role', '_authenticator']:
                st.session_state.pop(key, None)
            st.rerun()


def get_artist_id() -> Optional[int]:
    """Retourne l'artist_id de la session (None = admin, voit tout)."""
    return st.session_state.get('artist_id', 1)


def is_admin() -> bool:
    return st.session_state.get('role') == 'admin'


def get_artist_plan() -> str:
    """Return the current artist's plan name: 'free' | 'basic' | 'premium'.

    Reads artist_subscriptions from DB; falls back to saas_artists.tier.
    Returns 'premium' for admin sessions (unrestricted access).
    """
    if is_admin():
        return 'premium'

    artist_id = get_artist_id()
    if artist_id is None:
        return 'premium'

    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return 'free'
        row = db.fetch_query(
            """
            SELECT sp.name
            FROM artist_subscriptions asub
            JOIN subscription_plans sp ON sp.id = asub.plan_id
            WHERE asub.artist_id = %s AND asub.status IN ('active', 'trialing')
            LIMIT 1
            """,
            (artist_id,),
        )
        db.close()
        if row:
            return row[0][0]
        # Fallback to saas_artists.tier
        db2 = get_db_connection()
        tier_row = db2.fetch_query(
            "SELECT tier FROM saas_artists WHERE id = %s", (artist_id,)
        )
        db2.close()
        if tier_row:
            return tier_row[0][0]
    except Exception:
        pass
    return 'free'


def require_plan(min_plan: str) -> bool:
    """Show a paywall banner if the current artist's plan is below min_plan.

    Returns True if access is allowed, False if blocked.

    Usage at the top of a view:
        from src.dashboard.auth import require_plan
        if not require_plan('premium'):
            return
    """
    from src.database.stripe_schema import PLAN_RANK
    current_plan = get_artist_plan()
    if PLAN_RANK.get(current_plan, 0) >= PLAN_RANK.get(min_plan, 0):
        return True

    plan_labels = {'basic': 'Basic (9.90€/mo)', 'premium': 'Premium (29.90€/mo)'}
    st.warning(
        f"🔒 This feature requires the **{plan_labels.get(min_plan, min_plan)}** plan. "
        f"Your current plan: **{current_plan}**. Upgrade via the **Billing** page.",
        icon="⚠️",
    )
    return False


def artist_id_sql_filter(table_alias: str = '') -> tuple:
    """Retourne (fragment_sql, params) pour filtrer par artist_id.

    Retourne ('', ()) si admin (pas de filtre → voit tout).
    Retourne ('AND artist_id = %s', (1,)) pour un artiste.

    Usage :
        sql_frag, params = artist_id_sql_filter()
        query = f"SELECT * FROM s4a_song_timeline WHERE 1=1 {sql_frag}"
        df = db.fetch_df(query, params)
    """
    artist_id = get_artist_id()
    if artist_id is None:
        return "", ()
    prefix = f"{table_alias}." if table_alias else ""
    return f"AND {prefix}artist_id = %s", (artist_id,)
