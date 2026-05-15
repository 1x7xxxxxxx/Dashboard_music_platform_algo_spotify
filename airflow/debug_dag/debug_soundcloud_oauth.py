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
        raise RuntimeError(f"refresh_token grant failed: HTTP {r.status_code} — {r.text[:200]}")
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
        logger.error(f"❌ NO-GO — token grant failed: {e}")
        return 1

    r = requests.get(
        f"{_API_BASE}/users/{uid}/tracks",
        headers={'Authorization': f"OAuth {token}"},
        params={'limit': 20, 'linked_partitioning': 1},
        timeout=15,
    )
    if r.status_code != 200:
        logger.error(f"❌ NO-GO — tracks fetch failed: HTTP {r.status_code} — {r.text[:200]}")
        return 1

    tracks = r.json().get('collection', r.json()) if r.content else []
    likes = [(t.get('title'), t.get('likes_count') or t.get('favoritings_count') or 0)
             for t in tracks]
    for title, lk in likes[:10]:
        logger.info(f"   • {lk:>6}  {title}")

    max_likes = max((lk for _, lk in likes), default=0)
    print("\n" + "=" * 64)
    print("🔑 STORE THIS refresh_token in Dashboard → Credentials → SoundCloud")
    print("   (the one you minted is now SPENT — SoundCloud rotates on use):")
    print(f"\n   {effective_rt}\n")
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
