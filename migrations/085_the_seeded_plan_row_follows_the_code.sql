-- ============================================================
-- 085 — `subscription_plans.features` suit `PLAN_FEATURES`
-- ============================================================
--
-- Le gating réel se fait dans `PLAN_FEATURES` (`src/database/stripe_schema.py`) ;
-- la colonne `features` n'est lue par AUCUN code — vérifié le 2026-09-04. C'est
-- précisément pourquoi elle a divergé sans que rien ne le dise : `export_pdf` est
-- passé Premium dans le code, et la ligne semée en base l'annonçait toujours en Free.
--
-- Une donnée que personne ne lit et que personne ne met à jour est la forme la plus
-- durable de documentation fausse : le jour où quelqu'un l'interroge — un export, un
-- tableau d'admin, une future page de prix — il obtient la réponse d'avant-hier.
--
-- Deux issues possibles : supprimer la colonne, ou la faire suivre. On la fait suivre,
-- parce qu'elle décrit une OFFRE (ce qu'on vend, à quel prix) et que ce catalogue a sa
-- place en base le jour où les plans se gèrent ailleurs que dans un fichier Python.
-- `tests/test_plan_catalog_matches_the_gating` échoue désormais si les deux repartent
-- chacune de leur côté.
UPDATE subscription_plans
   SET features = '["home","spotify_s4a_combined","youtube","meta_ads_overview",'
                  '"instagram","soundcloud","apple_music","hypeddit","imusician",'
                  '"upload_csv","credentials","export_csv","data_wrapped",'
                  '"meta_mapping","referral"]'::jsonb
 WHERE name = 'free';
