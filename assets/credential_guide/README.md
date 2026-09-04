# API-credential guide screenshots

Illustrate the credential-setup steps shown in the "📖 Process — Credentials"
view. Referenced **by filename** from `src/dashboard/content/credential_guides.py`
(`CredStep.screenshot`) and resolved by `screenshot_path()` anywhere under this
directory (flat OR a per-platform subfolder, e.g. `spotify_4_developper/`).

## Contract
- Drop a PNG with the exact referenced name → it appears automatically. No code change.
- Missing file = graceful (the step shows its text only).
- Images render at native width (capped); capture at a readable resolution.

## Provided

Réel au 2026-09-04 — **vérifié par `ls`, pas recopié**. Ce tableau annonçait
`spotify_4_developper/…` et `soundcloud/soundcloud_user_id.png` avec un ✅ alors
qu'aucun des deux n'existait sur le disque : le premier a été supprimé avec le
guide mort qu'il illustrait (passage au modèle central, ADR-006), le second avec
l'étape « lis le code source de la page » que la résolution automatique du lien de
profil a rendue inutile.

| Platform | Files |
|---|---|
| Spotify | `spotify/spotify_share_artist_link.png` — le menu ⋯ → Partager → Copier le lien vers l'artiste |
| YouTube | `youtube/` — GCP_Api_services, GCP_youtube_data_api_v3, GCP_youtube_click, gcp_activated_api_GCP_menu, gcp_create_api_key, youtube_id_channel |
| SoundCloud | *(aucune — l'artiste colle le lien de son profil, il n'y a rien à montrer)* |
| Meta / Instagram | `meta/meta_url_id.png` |

To add a screenshot to a step, set `CredStep(..., screenshot="<name>.png")` in
`credential_guides.py` and drop the PNG here (any subfolder).
