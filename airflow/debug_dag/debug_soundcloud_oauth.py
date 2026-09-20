"""
🐛 SPIKE — SoundCloud OAuth user-token vs likes_count

Go/no-go feasibility probe for B2 (real per-track likes). The production
collector uses `grant_type=client_credentials`, which returns likes_count=0
for third-party reads. This script tries `grant_type=refresh_token` (user
context) and prints whether likes_count is non-zero on the owner's own tracks.

Read-only. No DB writes. Runnable directly:
    SOUNDCLOUD_CLIENT_ID=... SOUNDCLOUD_CLIENT_SECRET=... \
    SOUNDCLOUD_USER_ID=... SOUNDCLOUD_REFRESH_TOKEN=... \
    python airflow/debug_dag/debug_soundcloud_oauth.py

Decision rule: proceed to B2 P2 ONLY if this prints "✅ GO" (likes_count > 0
on a real owned account). SoundCloud app registration is closed/intermittent —
a missing refresh_token or failed token grant means the path is non-startable.
"""
import logging
import os
import sys

import requests

# La rédaction doit survivre à l'échec de TOUT le reste : la ligne qui journalise un
# `ImportError` s'exécute précisément quand le bloc d'import a échoué. Un
# `safe_error` importé là-dedans y serait indéfini — un `NameError` à la place du
# message d'erreur qu'on venait chercher.

# ⚠️ `redact` en plus de `safe_error` : ce sont deux questions différentes.
# `safe_error(e)` traite une EXCEPTION ; le corps d'une réponse HTTP n'en est pas une,
# et ces sondes l'écrivent tel quel. `debug_soundcloud.py:116` lit le corps d'un POST
# qui portait `client_secret`, et `debug_instagram.py:165` est la branche `else` de la
# fonction dont les branches 401/400 n'affichent que `err.get('message')` — le
# balayage du 2026-09-18 avait converti les gestionnaires d'exception et laissé la
# branche du corps entier.
try:
    from src.utils.safe_error import redact, safe_error
except ImportError:  # pragma: no cover - le repli ne dit que le TYPE, qui ne fuit pas
    def safe_error(exc):  # type: ignore[misc]
        return type(exc).__name__

    def redact(text):  # type: ignore[misc]
        # Le repli n'essaie PAS de reproduire les motifs : il efface. Sans le
        # module, on ne sait pas ce qui est un secret — rendre le corps entier
        # serait choisir la lisibilité contre la confidentialité, dans le seul
        # cas où on ne peut pas trancher.
        return '<corps non rédigeable — src/ inatteignable>'

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("SC-OAuth-Spike")

load_dotenv()

_TOKEN_ENDPOINT = "https://api.soundcloud.com/oauth2/token"
_API_BASE = "https://api.soundcloud.com"


def _get_user_token(client_id: str, client_secret: str,
                    refresh_token: str) -> tuple[str, str]:
    """Returns (access_token, effective_refresh_token).

    SoundCloud rotates the refresh_token on every refresh grant — the input
    `refresh_token` is now spent. The CALLER must store the returned effective
    one (the rotated value if any), else the next run is dead-on-arrival.
    """
    r = requests.post(
        _TOKEN_ENDPOINT,
        data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
        },
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"refresh_token grant failed: HTTP {r.status_code} — {redact(r.text[:200])}")
    data = r.json()
    effective = data.get('refresh_token') or refresh_token
    if effective != refresh_token:
        logger.warning("🔁 SoundCloud ROTATED the refresh_token — the one you "
                       "minted is now SPENT. Store the rotated value printed below.")
    return data['access_token'], effective


def main() -> int:
    # strip("<>") + whitespace: tolerate placeholder-pasted creds (a literal
    # "<secret>" reaches SoundCloud as invalid_client otherwise).
    def _clean(v):
        return (v or "").strip().strip("<>").strip()

    cid = _clean(os.getenv("SOUNDCLOUD_CLIENT_ID"))
    csec = _clean(os.getenv("SOUNDCLOUD_CLIENT_SECRET"))
    uid = _clean(os.getenv("SOUNDCLOUD_USER_ID"))
    rtok = _clean(os.getenv("SOUNDCLOUD_REFRESH_TOKEN"))

    if not all([cid, csec, uid, rtok]):
        logger.error("❌ NO-GO — missing one of SOUNDCLOUD_CLIENT_ID/CLIENT_SECRET/"
                     "USER_ID/REFRESH_TOKEN. App registration likely closed; path "
                     "non-startable. Do NOT proceed to B2 P2.")
        return 1

    try:
        token, effective_rt = _get_user_token(cid, csec, rtok)
        logger.info("✅ User token obtained via refresh_token grant.")
    except Exception as e:
        logger.error(f"❌ NO-GO — token grant failed: {safe_error(e)}")
        return 1

    r = requests.get(
        f"{_API_BASE}/users/{uid}/tracks",
        headers={'Authorization': f"OAuth {token}"},
        params={'limit': 20, 'linked_partitioning': 1},
        timeout=15,
    )
    if r.status_code != 200:
        logger.error(f"❌ NO-GO — tracks fetch failed: HTTP {r.status_code} — {redact(r.text[:200])}")
        return 1

    tracks = r.json().get('collection', r.json()) if r.content else []
    likes = [(t.get('title'), t.get('likes_count') or t.get('favoritings_count') or 0)
             for t in tracks]
    for title, lk in likes[:10]:
        logger.info(f"   • {lk:>6}  {title}")

    max_likes = max((lk for _, lk in likes), default=0)
    # ── LE JETON NE S'IMPRIME QUE SI ON LE DEMANDE — 2026-09-20 (R140 §16.5) ──
    #
    # L'impression est délibérée : le runbook OAuth frappe le jeton et demande de le
    # coller dans le dashboard, et l'opérateur le détient déjà. Ce n'est donc pas une
    # escalade de privilège.
    #
    # ⚠️ Ce qui la rend inconfortable est ailleurs : **les deux crons de ce dépôt
    # capturent la sortie standard d'un sous-processus dans un fichier de log ET dans un
    # corps de mail** (`tools/schema_drift_cron.sh`, `tools/infra_health_cron.sh`). Si ce
    # script y est un jour enveloppé — et rien ne l'interdit — le jeton est persisté sur
    # disque et posté par courrier.
    #
    # Le drapeau coûte une ligne et retire ce risque sans rien casser du runbook : la
    # procédure dit désormais `--print-token`, et une invocation automatique qui ne le
    # passe pas n'imprime rien.
    print("\n" + "=" * 64)
    print("🔑 STORE THIS refresh_token in Dashboard → Credentials → SoundCloud")
    print("   (the one you minted is now SPENT — SoundCloud rotates on use):")
    if "--print-token" in sys.argv:
        print(f"\n   {effective_rt}\n")
    else:
        print("\n   (masqué — relancer avec `--print-token` pour l'afficher)")
        print("   Raison : les crons de ce dépôt capturent stdout dans un log ET un")
        print("   e-mail ; un jeton imprimé sans qu'on l'ait demandé s'y retrouverait.\n")
    print("=" * 64)
    if max_likes > 0:
        logger.info(f"✅ GO — max likes_count = {max_likes} (> 0). User token exposes "
                    "real likes. Paste the token above into the dashboard.")
        return 0
    logger.error("❌ NO-GO — all likes_count still 0 even with a user token. "
                 "The OAuth path does not solve it; do NOT proceed to B2 P2.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
