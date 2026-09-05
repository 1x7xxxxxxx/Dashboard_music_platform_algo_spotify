-- ============================================================
-- 087 — l'inscription porte les liens de profil, la vérification les matérialise
-- ============================================================
--
-- Demandé le 2026-09-05 : « ajouter des champs pour saisir le profil Spotify +
-- SoundCloud + YouTube dans la page de création, et les rentrer dans credentials à un
-- moment pertinent ».
--
-- Pourquoi une colonne d'attente plutôt qu'une écriture directe dans
-- `artist_credentials` : une identité écrite avant la vérification de l'e-mail serait
-- une identité NON vérifiée, et `find_identity_conflict` la traiterait comme prise —
-- de quoi permettre à une inscription jamais confirmée de squatter le profil Spotify
-- de quelqu'un d'autre. Les liens attendent donc ici, sans effet, jusqu'à ce que le
-- compte soit confirmé ; ils passent ALORS par le même chemin de normalisation et de
-- contrôle d'unicité que la saisie manuelle.
--
-- JSONB et non trois colonnes : la liste des plateformes concernées bougera (Apple,
-- Instagram…) et une colonne par plateforme demanderait une migration à chaque fois.
-- Rien n'indexe ce champ — il est lu une seule fois, par identifiant d'artiste.
--
-- NULLABLE, sans défaut : une inscription qui ne remplit rien reste exactement ce
-- qu'elle est aujourd'hui. Idempotente — `make migrate` rejoue tous les fichiers.
-- ============================================================

ALTER TABLE saas_artists
    ADD COLUMN IF NOT EXISTS pending_profile_links JSONB;

COMMENT ON COLUMN saas_artists.pending_profile_links IS
    'Liens de profil saisis à l''inscription, en attente de la vérification de '
    'l''e-mail : {"spotify": "...", "soundcloud": "...", "youtube": "..."}. '
    'Vidé une fois matérialisé dans artist_credentials.';
