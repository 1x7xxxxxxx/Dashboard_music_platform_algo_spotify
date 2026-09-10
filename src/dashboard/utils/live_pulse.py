"""Live activity helpers (Brick 32 — live user counter widget).

Type: Utility
Uses: PostgresHandler (active_sessions, saas_artists)
Persists in: active_sessions (heartbeat upsert)

Two surfaces:
- Admin pulse on home.py — get_live_pulse(db, ttl_minutes=5) -> (live, registered)
- Public trust signal on register.py — get_registered_count_public() (cached 10 min)

The heartbeat write is fire-and-forget : any psycopg2 error is swallowed so a DB
hiccup never blocks the UI. Explicit dérogation to the "no silent failures"
project rule, mirrored on the csv_upload_log pattern in upload_csv.py.
"""
from datetime import datetime, timezone, timedelta
import logging

import psycopg2
import streamlit as st

logger = logging.getLogger(__name__)


def bump_heartbeat(db, artist_id: int) -> None:
    """Refresh the artist's last_heartbeat. Fire-and-forget — never raises."""
    try:
        db.execute_query(
            "INSERT INTO active_sessions (artist_id, last_heartbeat) "
            "VALUES (%s, NOW()) "
            "ON CONFLICT (artist_id) DO UPDATE SET last_heartbeat = NOW()",
            (artist_id,),
        )
    except psycopg2.Error as e:
        # Heartbeat must never block the UI — log and continue (Brick 32 dérogation).
        logger.warning("bump_heartbeat failed for artist_id=%s: %s", artist_id, e)


# Les locataires qui ne sont pas des gens. Le canari (`is_canary`) est un compte
# que NOUS créons pour surveiller la collecte : le compter parmi « les artistes qui
# utilisent streaMLytics » gonfle un signal de confiance public avec nos propres
# robots. `credential_loader.load_all_artists(exclude_canaries=True)` fait déjà
# cette distinction depuis la migration 064 ; les compteurs, non — ils comptaient
# tout ce qui est actif.
# Le prédicat vit dans `src/utils/tenant_kind.py` : il était écrit ici ET dans
# `credential_loader`, et le drapeau `is_sandbox` ajouté le 2026-08-30 aurait dû
# être posé aux deux endroits — dont celui-ci, une f-string dans un compteur
# auquel personne ne pense en ajoutant une colonne.
from src.utils.tenant_kind import HUMAN_TENANTS as _HUMAN_TENANTS


# LE POULS EST UNE AMBIANCE, PAS UN KPI.
#
# Cette requête partait à CHAQUE rerun de la barre latérale — donc à chaque clic de
# tout administrateur — alors que son voisin immédiat dans ce même fichier,
# `get_registered_count_public`, est caché 600 s. Elle compte des sessions dont la
# fenêtre de vivacité est de cinq MINUTES : la rafraîchir plusieurs fois par seconde
# ne rend rien de plus vrai, cela produit seulement deux sous-requêtes de comptage
# par clic.
#
# 30 s : court devant la fenêtre de 5 min qu'elle mesure (donc l'affichage reste
# juste), long devant la cadence des reruns (donc la requête cesse d'être gratuite).
_PULSE_TTL_S = 30


@st.cache_data(ttl=_PULSE_TTL_S, show_spinner=False)
def _pulse_counts(_db, cutoff: datetime) -> tuple[int, int]:
    """La lecture elle-même. `_db` est exclu de la clé de cache (préfixe `_`)."""
    rows = _db.fetch_query(
        "SELECT "
        "  (SELECT COUNT(*) FROM active_sessions WHERE last_heartbeat > %s) AS live, "
        f"  (SELECT COUNT(*) FROM saas_artists WHERE {_HUMAN_TENANTS}) AS registered",
        (cutoff,),
    )
    if not rows:
        return 0, 0
    live, registered = rows[0]
    return int(live), int(registered)


def get_live_pulse(db, ttl_minutes: int = 5) -> tuple[int, int]:
    """Return (live_count, registered_count).

    live_count: distinct artists with a heartbeat newer than ttl_minutes.
    registered_count: real tenants — canaries excluded, see _HUMAN_TENANTS.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
    # La borne est arrondie à la fenêtre de cache : sans cela chaque rerun produit un
    # `cutoff` différent à la microseconde près, donc une clé de cache neuve, donc un
    # cache qui n'a jamais un seul succès. C'est la façon la plus courante de croire
    # avoir mis un cache en place sans en avoir mis un.
    cutoff = cutoff.replace(
        second=(cutoff.second // _PULSE_TTL_S) * _PULSE_TTL_S, microsecond=0)
    return _pulse_counts(db, cutoff)


@st.cache_data(ttl=600)
def get_registered_count_public() -> int:
    """Cached count of registered artists for the public landing widget.

    Cached 10 min to absorb anonymous traffic bursts (SEO/social links).
    No PII — count only.

    **Compte des gens, pas des machines.** Ce nombre s'affiche sur la page
    d'inscription, sous « {n} artistes utilisent streaMLytics » : un canari de
    surveillance compté là est un chiffre faux montré à un visiteur qui n'a aucun
    moyen de le savoir.
    """
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        return 0
    try:
        rows = db.fetch_query(
            f"SELECT COUNT(*) FROM saas_artists WHERE {_HUMAN_TENANTS}"
        )
        return int(rows[0][0]) if rows else 0
    finally:
        db.close()
