-- Le résumé quotidien porte la DURÉE des DAG — 2026-09-18
--
-- Pourquoi cette colonne, et la question qu'elle sert
-- ---------------------------------------------------
-- La durée d'un DAG n'était exposée NULLE PART : aucune métrique Prometheus, aucune
-- colonne, aucune règle d'alerte. Elle vit dans `airflow_db.dag_run`, que seule
-- `views/airflow_kpi.py` lit — à la volée, sans rien persister. Mesuré le 2026-09-18
-- sur sept jours : `meta_ads_api_daily` 61 s en moyenne / 69 s au pic,
-- `instagram_daily` 37 / 53, les six autres sous 11 s.
--
-- La question qu'elle répond, et c'est la seule qui justifie de l'écrire : **la
-- collecte d'un locataire coûte-t-elle plus cher qu'hier ?** Un DAG dont la durée
-- double est l'indicateur AVANCÉ de la croissance de données que les déclencheurs
-- d'ADR-002 et ADR-007 surveillent — bien avant qu'une lecture devienne lente ou
-- qu'un quota d'API saute. Rien ne l'observait.
--
-- ⚠️ Ce qu'elle NE dit pas, écrit ici pour qu'on ne le déduise pas de travers :
--
--   * une durée courte n'est PAS une collecte réussie. Un DAG qui saute tous ses
--     locataires finit en 2 s et remplit cette colonne comme un succès. La réussite
--     par locataire se lit dans `etl_run_log`, pas ici ;
--   * la valeur est le MAXIMUM du jour, pas une moyenne. Un pic est ce qui approche
--     d'un délai d'expiration ; une moyenne le dilue ;
--   * les jours sans exécution n'écrivent pas `0`, ils n'écrivent pas la clé. Un zéro
--     inventé se lirait comme « instantané » alors qu'il veut dire « jamais parti ».
--
-- Forme : JSONB {dag_id: secondes}, comme `errors_by_page` juste au-dessus. Une
-- colonne par DAG figerait la flotte dans le schéma, et ce dépôt en compte seize.

ALTER TABLE daily_ops_metrics
    ADD COLUMN IF NOT EXISTS dag_durations_s JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN daily_ops_metrics.dag_durations_s IS
    'Durée MAXIMALE de chaque DAG sur 24 h, en secondes : {dag_id: sec}. '
    'Lue depuis airflow_db.dag_run. Une clé absente = le DAG n''est pas parti ce '
    'jour-là — jamais 0, qui se lirait comme « instantané ». Une durée courte n''est '
    'pas une collecte réussie : voir etl_run_log pour le verdict par locataire.';
