-- 136 — Effacer un parrain ne détruit plus le parrainage d'un AUTRE artiste.
--
-- Le défaut, trouvé le 2026-09-23
-- --------------------------------
-- `referral_events.referrer_artist_id` référençait `saas_artists(id)` en `NO ACTION`.
-- Effacer (RGPD Art. 17) un artiste X qui avait parrainé Y avait deux issues, toutes
-- deux fausses :
--   * avant ce jour : la ligne restait, et le `DELETE FROM saas_artists` final ÉCHOUAIT —
--     l'effacement mourait à mi-chemin, sans reçu ;
--   * avec une portée d'effacement dérivée du schéma : la ligne était SUPPRIMÉE — donc
--     l'historique de parrainage de Y, qui n'a rien demandé, disparaissait avec X.
--     Trouvé par `code-critic` avant commit.
--
-- La ligne appartient aux deux artistes. Effacer X doit retirer X, pas Y : le parrain
-- devient NULL, la ligne de Y reste. `ON DELETE SET NULL` le fait au moment où la base
-- supprime X, et `_erasure_scope()` laisse ces colonnes à la base.
--
-- Côté filleul, `referred_artist_id` reste `ON DELETE CASCADE` : la ligne n'a pas de
-- sens sans le compte qu'elle a créé, et la contrainte UNIQUE l'attache à lui seul.
--
-- Lecteurs vérifiés : `views/referral.py` filtre `referrer_artist_id = %s` et
-- `views/referral_admin.py` fait un JOIN INTERNE — une ligne au parrain effacé sort
-- simplement de leurs listes, rien ne lève.

ALTER TABLE referral_events ALTER COLUMN referrer_artist_id DROP NOT NULL;

ALTER TABLE referral_events DROP CONSTRAINT IF EXISTS referral_events_referrer_artist_id_fkey;
ALTER TABLE referral_events
    ADD CONSTRAINT referral_events_referrer_artist_id_fkey
    FOREIGN KEY (referrer_artist_id) REFERENCES saas_artists(id) ON DELETE SET NULL;
