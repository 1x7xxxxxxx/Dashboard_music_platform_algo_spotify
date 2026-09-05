"""Credentials — platform registry + test/guide dispatch.

Type: Sub
Uses: the four _platform_* modules
The single wiring point: PLATFORMS field definitions, CONNECTION_TESTS map,
and the per-platform guide dispatcher. Pure relocation — no logic change.
"""
from ._platform_spotify import _test_spotify
from ._platform_youtube import _test_youtube
from ._platform_soundcloud import _test_soundcloud
from ._platform_meta import _test_meta, _test_instagram


# ─────────────────────────────────────────────
# Platform definitions
# ─────────────────────────────────────────────
# 'secret': True  → stocké dans token_encrypted (Fernet-chiffré)
# 'secret': False → stocké dans extra_config (JSONB, lisible)

# Ordered easiest → hardest so a new artist starts where it's quickest (one identifier,
# no third-party app). SoundCloud (user_id) → Spotify (profile URL) → YouTube (channel id)
# → Meta (ad account + asset-sharing). This dict order drives the tabs (router.py) and the
# global KPI (_render.py).
# `example` : la forme attendue, montrée EN PLACEHOLDER dans le champ et rappelée
# sous lui. Elle vivait au bas du guide, dans un bloc « Les valeurs à coller » —
# c'est-à-dire à deux colonnes de l'endroit où on tape. Demandé le 2026-09-04 :
# « intègre sous le champ ». Un exemple sert au moment de la saisie ou ne sert pas.
# Ce sont des formes FICTIVES mais correctes, jamais un vrai secret.
# `admin_only: True` sur un champ = surcharge d'exploitant, jamais montrée à
# l'artiste. Ces trois-là portaient le libellé « (optionnel — admin) » et
# s'affichaient quand même dans SON formulaire : il lit « admin », ne sait pas si
# c'est à lui, et hésite sur la page où il n'a qu'une valeur à coller.
# Même classe que `guide-addresses-the-wrong-reader` — le premier balayage n'avait
# regardé que les NOTES, pas les CHAMPS.
PLATFORMS = {
    'soundcloud': {
        'label': '☁️ SoundCloud',
        # L'artiste colle le LIEN de son profil ; `_save_credentials` le résout en
        # User ID numérique avant l'écriture, donc la colonne ne contient que des
        # chiffres. Le champ s'est appelé « User ID numérique » jusqu'au 2026-09-04 —
        # il nommait ce que la BASE stocke, pas ce qu'on demande de coller, et le
        # guide juste à côté disait « collez le lien ». Deux consignes contradictoires
        # sur un formulaire à un seul champ.
        # Les app credentials (client_id/client_secret) viennent de l'app partagée.
        # The optional OAuth real-likes path is an admin runbook (mint script),
        # not exposed in the artist form.
        'fields': [
            {'key': 'user_id', 'label': 'Lien de ton profil SoundCloud', 'secret': False,
             'example': 'https://soundcloud.com/ton-nom'},
        ],
    },
    'spotify': {
        'label': '🎵 Spotify',
        # Central model: the client_credentials app is admin-owned (SPOTIFY_CLIENT_ID/
        # SECRET env, one app serves all artists on public catalog data). The artist
        # supplies ONLY their Spotify artist identity; client_id/secret remain as an
        # optional per-artist override. spotify_artist_id is synced to
        # saas_artists.spotify_artist_id on save (the per-tenant collection key).
        'fields': [
            {'key': 'spotify_artist_id', 'label': 'URL profil artiste',
             'secret': False,
             'example': 'https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV'},
            {'key': 'client_id',     'label': 'Client ID (surcharge)',     'secret': False, 'admin_only': True},
            {'key': 'client_secret', 'label': 'Client Secret (surcharge)', 'secret': True, 'admin_only': True},
        ],
    },
    'youtube': {
        'label': '🎬 YouTube',
        # Central model: the Data-API key is admin-owned (YOUTUBE_API_KEY env, one Google
        # Cloud key serves all artists). The artist supplies ONLY their Channel ID; api_key
        # remains an optional per-artist override. The connection test validates the
        # channel resolves (a bad UC… 404s the collector, not the key test).
        'fields': [
            {'key': 'channel_id', 'label': 'Channel ID (UC…)', 'secret': False,
             'example': 'UC_x5XG1OV2P6uZZ5FSM9Ttw'},
            {'key': 'api_key',    'label': 'API Key (surcharge)',         'secret': True, 'admin_only': True},
        ],
    },
    'meta': {
        'label': '📱 Meta / Instagram',
        # Shared System User app (access_token/app_id/app_secret) comes from the
        # platform env; the artist provides their own Ad Account ID and — for
        # Instagram — their Instagram Business Account ID. Stored per-artist app
        # creds still take precedence in the collector if present.
        # ig_user_id is what instagram_daily selects tenants on and what
        # artist_readiness reads as the Instagram identity; it had no form field,
        # so Instagram was unconnectable by the artist (the collector's own error
        # message pointed at a field that did not exist).
        'fields': [
            # Le MÊME geste que Spotify et SoundCloud : on colle un lien, pas un
            # identifiant qu'il faudrait d'abord découper. `_handle_save` extrait
            # `act=` et accepte aussi le numéro nu — mais ce n'est plus une règle à
            # retenir, c'est une tolérance.
            #
            # `show_example: False` : la légende « ex. act_1234567890 » répétait le
            # texte fantôme du champ juste au-dessus d'elle. Demandé le 2026-09-05 —
            # « il est déjà sous-entendu dans le champ de saisie, qui est parfait ».
            {'key': 'account_id', 'label': 'Lien de ton compte publicitaire',
             'secret': False, 'show_example': False,
             'example': 'https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=123456789012345'},
            {'key': 'ig_user_id', 'label': 'Instagram Business Account ID',
             'secret': False, 'show_example': False, 'example': '17841400000000000'},
            # N comptes publicitaires (R53 / ADR-013). Champ SÉPARÉ et facultatif,
            # plutôt qu'une liste dans `account_id` : les 100 % de locataires
            # mono-compte d'aujourd'hui ne voient aucun changement, et le champ
            # principal garde le motif de forme qui l'empêche d'entrer tel quel dans
            # un chemin REST. Une liste dans le champ principal aurait cassé les deux.
            # Replié : ce champ ne concerne que les agences, donc presque personne.
            # Déplié par défaut, il occupait une zone de saisie entière sous les deux
            # champs qui, eux, servent à tout le monde. `collapsed` le met dans un
            # dépliant fermé — il reste à un clic, il ne demande plus rien.
            {'key': 'extra_account_ids',
             'label': 'Comptes ads supplémentaires - pour agence (optionnel)',
             'secret': False, 'multiline': True, 'collapsed': True},
        ],
    },
}


# Keyed on the LOGICAL platform, so it has five entries for four tabs. Instagram is
# not a tab — its id is a field of the Meta tab — but it is a platform everywhere
# else (readiness, the alert monitor, the canary), and it had no probe of its own:
# it was tested only as an optional suffix inside `_test_meta`, skipped when the id
# was blank. `tools/artist_preflight.py` step 3 iterates this dict, so Instagram was
# silently absent from the gate that runs before an artist test session.
CONNECTION_TESTS = {
    'spotify':    _test_spotify,
    'youtube':    _test_youtube,
    'soundcloud': _test_soundcloud,
    'meta':       _test_meta,
    'instagram':  _test_instagram,
}


# `_render_platform_guide` et les quatre `_guide_*` des modules plateforme ont été
# SUPPRIMÉS le 2026-08-23. Ils n'avaient aucun appelant depuis le passage au modèle
# central (ADR-006) : ce qui s'affiche vient de `content/credential_guides.py`, via
# `credential_guides_st.render_credential_guide_for`.
#
# Ce n'était pas du code mort inoffensif. Il CONTREDISAIT le guide vivant : sur Spotify,
# le vivant dit « tu n'as rien à créer, colle le lien de ta page artiste » et le mort
# disait « va sur developers.spotify.com, crée une app, copie le Client ID et le
# Secret ». Un artiste en test a suivi le mauvais, et ses notes le disent
# (« web api pas cochée », « uri non bonne »). Du texte maintenu et traduit que rien
# n'affiche finit par ressortir ailleurs — ici dans la tête de celui qui le lit en
# ouvrant le fichier.
