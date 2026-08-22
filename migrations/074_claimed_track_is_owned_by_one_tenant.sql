-- ============================================================
-- 074 — un titre revendiqué n'appartient qu'à un locataire
-- ============================================================
-- 2026-08-22. Cas GRiNCH : sa musique sort sous d'autres comptes, donc son profil
-- SoundCloud a `track_count=0` et il n'y aura jamais rien à y collecter. La réponse
-- est de collecter les TITRES qu'il déclare, où qu'ils soient hébergés — `GET
-- /tracks/{id}` rend les statistiques quel que soit le profil propriétaire (vérifié :
-- 1027 écoutes sur un titre hébergé par un tiers).
--
-- `track_platform_link` porte déjà exactement ce qu'il faut : `platform_ref_id`,
-- « l'id de ce titre sur cette plateforme ». Rien à créer.
--
-- Ce qui manque est la garde. La contrainte existante est
--   UNIQUE (artist_id, platform, platform_title, match_key)
-- qui empêche un locataire de déclarer deux fois le même titre — et n'empêche PAS
-- deux locataires de revendiquer le MÊME titre. Deux artistes du même label le
-- feraient le premier jour, chacun collecterait les écoutes de l'autre sous son
-- propre `artist_id`, et la contamination reviendrait par la porte de service — la
-- classe `identity-claimed-by-two-tenants`, appliquée au titre au lieu du profil.
--
-- Index PARTIEL, sur les seules revendications manuelles confirmées. Le moteur de
-- suggestion (`track_mapping_suggest.py`) propose légitimement le même titre à
-- plusieurs artistes avant arbitrage, et `status='rejected'` doit pouvoir coexister ;
-- seule une revendication tranchée est exclusive.

CREATE UNIQUE INDEX IF NOT EXISTS uniq_claimed_track_per_platform
    ON track_platform_link (platform, platform_ref_id)
    WHERE status = 'confirmed'
      AND method = 'manual'
      AND platform_ref_id IS NOT NULL
      AND platform_ref_id <> '';

COMMENT ON INDEX uniq_claimed_track_per_platform IS
    'Un titre revendiqué manuellement n''appartient qu''à un locataire. Partiel : le '
    'moteur de suggestion propose le même titre à plusieurs artistes avant arbitrage, '
    'et seul un arbitrage rend la revendication exclusive.';
