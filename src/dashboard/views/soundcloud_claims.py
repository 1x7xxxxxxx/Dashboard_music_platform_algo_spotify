"""Déclarer les titres qu'un artiste a sortis sous le compte de quelqu'un d'autre.

Type: Sub
Uses: claimed_tracks (revendications), l'app SoundCloud partagée (resolve)
Depends on: src/utils/claimed_tracks.py, SOUNDCLOUD_CLIENT_ID/SECRET
Persists in: track_platform_link

Pourquoi ce fichier existe séparément
-------------------------------------
Ce panneau a vécu dans l'onglet SoundCloud de la page Credentials jusqu'au
2026-09-04, déplié par défaut. Deux choses n'allaient pas, et la seconde explique
la première.

**Ce n'est pas un identifiant.** La page Credentials répond à « qui es-tu sur cette
plateforme ? » — une valeur, une fois, et on n'y revient plus. Revendiquer des
titres répond à « que manque-t-il à mon catalogue ? », une question qu'on se pose
en REGARDANT ses chiffres et en constatant qu'une sortie n'y est pas. Elle se pose
donc là où les chiffres sont : ☁️ SoundCloud — Performance.

**Déplié par défaut, il passait avant le champ.** Un artiste qui vient coller son
lien de profil rencontrait d'abord un pavé sur les labels et les collectifs — un
cas qui ne concerne pas la majorité, posé au moment où on demande autre chose.

Le mécanisme est inchangé : une URL par ligne, résolue en identifiant numérique de
TITRE, et un titre ne peut être revendiqué que par un seul locataire — sans quoi
deux artistes d'un même label collecteraient chacun les écoutes de l'autre.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t


def render_claimed_tracks(db, artist_id: int) -> None:
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
