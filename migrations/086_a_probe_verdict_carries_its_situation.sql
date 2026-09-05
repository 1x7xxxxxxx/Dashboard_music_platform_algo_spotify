-- ============================================================
-- 086 — un verdict de sonde porte SA SITUATION, pas seulement un bit
-- ============================================================
--
-- `tenant_platform_probe.ok` est un booléen, et l'écran le traduisait par une
-- phrase unique : « ❌ {plateforme} : enregistré, mais la plateforme ne répond pas
-- encore. » Or `ok = false` recouvre huit situations réparties sur cinq
-- plateformes, et AUCUNE ne veut dire « ne répond pas » :
--
--   * SoundCloud : HTTP 200, mais zéro titre public sur ce profil
--   * YouTube    : chaîne TROUVÉE mais vide ; handle RÉSOLU avec succès
--   * Spotify / Meta / Instagram : l'app répond, c'est l'identité qui manque
--
-- Le 2026-09-05, un artiste a lu simultanément « ✅ Répond · 🟢 Données » et
-- « ❌ … ne répond pas encore. User ID 377065610 JOIGNABLE, mais aucun titre
-- public ». Les trois étaient vraies dans leur référentiel ; seule la phrase du
-- titre était fausse — elle affirmait une cause que la sonde n'avait pas mesurée.
--
-- La colonne est NULLABLE et sans valeur par défaut : une ligne écrite avant cette
-- migration, ou par une sonde qui ne se prononce pas, garde `NULL` et retombe sur
-- le libellé neutre. Rien à rétro-remplir — les verdicts sont réécrits à chaque
-- sonde (`save_probe` fait un ON CONFLICT DO UPDATE), donc la colonne se remplit
-- d'elle-même au premier passage.
--
-- Idempotente : `make migrate` rejoue tous les fichiers de `migrations/`.
-- ============================================================

ALTER TABLE tenant_platform_probe
    ADD COLUMN IF NOT EXISTS category TEXT;

COMMENT ON COLUMN tenant_platform_probe.category IS
    'Situation nommée du verdict : unreachable | refused | not_found | '
    'identity_missing | nothing_to_collect | resolved. NULL = la sonde ne se '
    'prononce pas, l''écran retombe sur un libellé neutre.';
