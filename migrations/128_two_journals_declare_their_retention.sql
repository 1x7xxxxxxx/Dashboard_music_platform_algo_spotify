-- Deux journaux déclarent enfin leur rétention — 2026-09-20 (R140 §16.13)
--
-- Ce que la migration 124 a manqué, et pourquoi
-- ---------------------------------------------
-- `124_every_telemetry_table_declares_its_retention.sql` a fait l'inventaire des tables
-- de télémétrie et leur a donné une rétention déclarée. Deux y ont échappé, pour deux
-- raisons SYMÉTRIQUES — et c'est la symétrie qui rend la classe intéressante :
--
--   * `data_revisions` est **ni déclarée ni purgée**. Elle est écrite par un DÉCLENCHEUR
--     SQL (`log_value_revision()`), jamais par du code applicatif — et l'inventaire de
--     124 a été fait sur les ÉCRIVAINS PYTHON. Une table qu'aucun `INSERT` Python ne
--     touche était invisible à la question posée.
--
--   * `rate_limit_hits` est l'inverse : **purgée sans être déclarée**. Son commentaire
--     nomme bien son purgeur (`alert_monitor.purge_rate_limit_hits`), mais pas dans la
--     forme `RÉTENTION : N jours` que `telemetry_retention.declared_retentions()` lit.
--     Donc `undeclared_tables()` ne peut pas la juger : le prochain inventaire la
--     comptera comme non purgée, ou retirera sa purge sans rien casser d'apparent.
--
-- ⚠️ **La rétention est DÉRIVÉE du commentaire.** `telemetry_retention.py:62` lit
-- `RÉTENTION : (\d+) jours` dans `obj_description()`, et `purge_telemetry` agit dessus.
-- Déclarer ici ne documente donc pas : cela CÂBLE la purge. C'est la raison pour
-- laquelle ce geste est une migration et pas un commentaire de code.
--
-- Les durées, et d'où elles viennent
-- -----------------------------------
-- **365 jours pour `data_revisions`**, comme `monitoring_run` et `csv_upload_log` — les
-- deux autres tables de PREUVE de ce dépôt. La question qu'elle répond (« quelle valeur
-- a été écrasée, quand, par quoi ») se pose rétrospectivement, sur une saison : un
-- artiste qui conteste un chiffre de mars le fait en novembre. Six mois seraient trop
-- courts pour ça, et l'illimité ferait grossir sans borne une table qu'aucune surface
-- ne lit en routine.
--
-- **30 jours pour `rate_limit_hits`**, et c'est BEAUCOUP plus que nécessaire : ses
-- fenêtres glissantes anti-force-brute se comptent en minutes, et `request_throttle.py`
-- ne regarde jamais au-delà. Trente jours laissent de quoi enquêter sur une campagne de
-- force brute après coup, ce que quelques heures interdiraient.
--
-- Idempotente : `COMMENT ON TABLE` remplace, il n'ajoute pas.

COMMENT ON TABLE data_revisions IS
    'TÉLÉMÉTRIE. Journal append-only : une ligne par VALEUR écrasée. Alimenté par le '
    'déclencheur log_value_revision(), jamais par du code applicatif — c''est pourquoi '
    'l''inventaire de la migration 124, fait sur les écrivains Python, ne l''a pas vue. '
    'Ne sert jamais de source de vérité : c''est une trace, pas un état. '
    'RÉTENTION : 365 jours, purgée par alert_monitor (telemetry_retention.py). '
    'Un an comme monitoring_run et csv_upload_log, les deux autres tables de PREUVE : '
    'la question « quelle valeur a été écrasée, quand » se pose rétrospectivement, sur '
    'une saison.';

COMMENT ON TABLE rate_limit_hits IS
    'TÉLÉMÉTRIE. Coups des fenêtres glissantes anti-force-brute, partagés entre '
    'instances. Écrit par src/utils/request_throttle.py:PostgresHitStore sous verrou '
    'consultatif. RÉTENTION : 30 jours, purgée par alert_monitor '
    '(telemetry_retention.py). Bien plus que nécessaire — les fenêtres se comptent en '
    'MINUTES et request_throttle ne regarde jamais au-delà — mais trente jours laissent '
    'de quoi enquêter sur une campagne de force brute après coup. '
    'Elle était purgée SANS être déclarée : son commentaire nommait son purgeur, pas '
    'dans la forme que declared_retentions() lit, donc undeclared_tables() ne pouvait '
    'pas la juger.';
