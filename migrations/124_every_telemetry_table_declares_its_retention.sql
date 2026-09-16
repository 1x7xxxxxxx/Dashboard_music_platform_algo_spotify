-- 124 — chaque table de TÉLÉMÉTRIE déclare ce qu'il advient de ses vieilles lignes
--
-- POURQUOI. Inventaire du 2026-09-16, fait avant d'adopter Prometheus (ADR-026) :
-- **13 tables de télémétrie, UNE SEULE purgée**. `rate_limit_hits` est la seule, et elle
-- ne l'est que parce que `code-critic` avait posé la purge en condition bloquante. Les
-- autres croissent indéfiniment, sans qu'aucune rétention soit écrite nulle part.
--
-- Rien n'échoue jamais. Le jour où un tableau ralentit ou où le disque se remplit, la
-- cause a des mois d'avance sur le symptôme.
--
-- LE DISTINGUO, qui est tout le sujet :
--   * une table MÉTIER garde tout — ADR-018, « rien de ce qui est écrasé n'est perdu ».
--     La purger serait une perte de donnée.
--   * une table de TÉLÉMÉTRIE est un journal, et un journal se rogne.
-- Les confondre fait soit perdre de la donnée, soit garder des traces pour toujours.
--
-- POURQUOI UNE MIGRATION NEUVE et pas une correction des anciennes : `schema_migrations`
-- détecte au checksum tout fichier modifié après coup, et `tools/migrate.sh` refuse de le
-- rejouer. Un `COMMENT ON TABLE` est idempotent et ne touche pas le schéma.
--
-- Ce fichier ne fait que DÉCLARER. Les purges correspondantes vivent dans
-- `src/utils/telemetry_retention.py`, appelé par le DAG `alert_monitor` — au même endroit
-- que celle de `rate_limit_hits`, pour qu'il n'y ait qu'un seul endroit à lire.

-- ── Celles qui CROISSENT et qu'on rogne ──────────────────────────────────────

COMMENT ON TABLE usage_events IS
    'TÉLÉMÉTRIE. Une ligne par interaction ; c''est la table qui grossit le plus vite. '
    'RÉTENTION : 180 jours, purgée par alert_monitor (telemetry_retention.py). '
    'Au-delà, la question à laquelle elle répond (« qui a utilisé quoi, quand ») se pose '
    'sur des agrégats, pas sur l''événement. Les seuils de charge qui la lisent '
    '(tools/scale_check.sh) regardent une fenêtre d''une minute.';

COMMENT ON TABLE etl_run_log IS
    'TÉLÉMÉTRIE. Une ligne par exécution de collecte. RÉTENTION : 180 jours, purgée par '
    'alert_monitor. Ses lecteurs (etl_logs, alerts, airflow_kpi, check_collection_outcomes) '
    'travaillent tous sur 7 à 30 jours ; le reste n''est lu par personne.';

COMMENT ON TABLE monitoring_run IS
    'TÉLÉMÉTRIE. La preuve qu''une alerte nocturne est partie — lue par '
    'tools/infra_health_cron.sh sur 48 h. RÉTENTION : 365 jours, purgée par alert_monitor. '
    'Un an plutôt que six mois à dessein : c''est le registre qui prouve que la '
    'surveillance a tourné, et une année permet de répondre « avons-nous été aveugles en '
    'mars ? ».';

COMMENT ON TABLE csv_upload_log IS
    'TÉLÉMÉTRIE. Dépôts de CSV acceptés et refusés. RÉTENTION : 365 jours, purgée par '
    'alert_monitor. Un artiste peut revenir sur un import de la saison précédente.';

-- ── Celles qui NE grossissent pas, et pourquoi ───────────────────────────────

COMMENT ON TABLE active_sessions IS
    'TÉLÉMÉTRIE bornée par construction : la clé primaire est artist_id, donc UNE LIGNE '
    'PAR ARTISTE, écrasée à chaque battement. Elle ne grossit pas — aucune purge requise, '
    'et en écrire une serait du code mort.';

COMMENT ON TABLE tenant_platform_probe IS
    'TÉLÉMÉTRIE bornée par construction : clé primaire (artist_id, platform), la ligne est '
    'ÉCRASÉE à chaque sonde. Pas d''historique, donc rien à purger. Si un jour on veut la '
    'série, ce sera une autre table — et elle déclarera sa rétention.';

COMMENT ON TABLE etl_circuit_breaker IS
    'TÉLÉMÉTRIE bornée par construction : UNIQUE (platform, artist_id). '
    '⚠️ ET VIDE EN PRATIQUE — aucune collecte ne l''écrit aujourd''hui, alors que deux vues '
    'l''affichent (etl_logs.py, alerts.py). Un panneau qui ne peut rien montrer se lit '
    'comme « tout va bien ». C''est un défaut ouvert, pas une rétention.';

-- ── Celles qui gardent TOUT, et pourquoi c'est correct ───────────────────────

COMMENT ON TABLE admin_audit_log IS
    'JOURNAL D''AUDIT — garde tout, AUCUNE purge. Une action d''administration doit rester '
    'attribuable sans limite de temps ; effacer une trace d''audit est précisément ce '
    'qu''un journal d''audit existe pour empêcher.';

COMMENT ON TABLE gdpr_erasure_log IS
    'JOURNAL LÉGAL — garde tout, AUCUNE purge. C''est la preuve qu''un effacement demandé a '
    'eu lieu. Purger cette table détruirait la preuve de conformité, ce qui est l''inverse '
    'de son objet.';

COMMENT ON TABLE subscription_plan_history IS
    'HISTORIQUE MÉTIER (ADR-018, « rien de ce qui est écrasé n''est perdu ») — garde tout. '
    'Append-only : c''est la seule source qui dise ce qu''un client payait à une date '
    'donnée, et une question de facturation peut remonter loin.';

COMMENT ON TABLE app_error_log IS
    'TÉLÉMÉTRIE à rétention CONDITIONNELLE, et la condition est le point : une ligne par '
    'DÉFAUT (empreinte), pas par occurrence. RÉTENTION : les défauts RÉSOLUS depuis plus de '
    '365 jours sont purgés ; un défaut OUVERT n''est JAMAIS purgé, quel que soit son âge. '
    'Un défaut ouvert depuis deux ans est le plus intéressant du registre, pas le moins.';

-- ── La table morte, nommée comme telle ───────────────────────────────────────

COMMENT ON TABLE etl_daily_metrics IS
    '⚠️ TABLE MORTE — 2 lignes, rétro-inscrite dans une migration « dans le seul but de '
    'faire taire make schema-check » (schema-drift-2026-06-13.md). Rien ne l''écrit, et '
    'airflow_kpi.py a été repointé sur etl_run_log. Aucune rétention : il faut la '
    'SUPPRIMER, pas la purger. Laisser une table morte dans le schéma fait croire qu''une '
    'source existe.';
