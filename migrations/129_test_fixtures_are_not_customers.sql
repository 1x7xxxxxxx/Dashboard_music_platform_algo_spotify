-- Les locataires fabriqués par des tests sortent du compte public — 2026-09-20 (§16.9d)
--
-- Ce que le compteur disait, et ce qui était vrai
-- -----------------------------------------------
-- `live_pulse.py:71` — une page PUBLIQUE — comptait **10 artistes**. Mesuré le
-- 2026-09-20 : **9 sont des artefacts de test**, et un seul est réel.
--
--     8 × « Oracle Probe »   créés le 2026-09-15 entre 18h32 et 18h34
--     1 × « Smoke smoke-… »  créé le 2026-09-06
--     1 × « 1x7xxxxxxx »     le seul vrai locataire
--
-- Les huit portent tous `created_at` dans un intervalle de DEUX MINUTES : c'est une
-- seule exécution de `tests/test_registration_is_not_an_oracle.py`, dont les
-- inscriptions passent par le vrai formulaire et n'étaient donc marquées d'aucun
-- drapeau. `tests/test_views_render_smoke.py` nettoie normalement derrière lui ; la
-- ligne restante est une exécution morte en route.
--
-- ⚠️ **Pourquoi MARQUER et non EFFACER.** Effacer est irréversible, et surtout ne règle
-- rien : la prochaine exécution des mêmes tests recréerait des lignes identiques. Les
-- deux fixtures posent désormais `is_sandbox` à la création (`test_views_render_smoke`)
-- ou après coup (`test_registration_is_not_an_oracle`), et cette migration ne fait que
-- rattraper les lignes déjà là.
--
-- `tenant_kind.py` déclare exactement ce vocabulaire : « un locataire que NOUS opérons —
-- jamais un client, jamais dans les comptes publics ». Un artefact de test en est un.
--
-- ⚠️ **Le prédicat est une FORME, et c'est assumé pour une réparation ponctuelle.**
-- Il vise des noms littéraux, ce que ce dépôt refuse normalement — mais il s'agit ici
-- de rattraper des lignes CONNUES et déjà présentes, pas de reconnaître les futures.
-- Les futures sont marquées à la source, ce qui est le vrai correctif. Le garde
-- `tests/test_the_public_counter_counts_customers.py` vérifie les deux.
--
-- Idempotente : `WHERE COALESCE(is_sandbox, FALSE) = FALSE` ne repasse pas sur une ligne
-- déjà marquée.

UPDATE saas_artists
   SET is_sandbox = TRUE
 WHERE COALESCE(is_sandbox, FALSE) = FALSE
   AND (name = 'Oracle Probe' OR name LIKE 'Smoke smoke-%');
