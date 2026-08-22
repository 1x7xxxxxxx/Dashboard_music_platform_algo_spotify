-- ============================================================
-- 073 — monitoring_run : la preuve que l'alerte est bien partie
-- ============================================================
-- R du 2026-08-22. `alert_monitor` calcule ses constats correctement et les rend
-- correctement dans le corps du mail. Ce que rien n'enregistrait, c'est si le mail
-- est PARTI.
--
-- Mesuré dans les journaux de production : les nuits des 16, 17 et 18 août, la tâche
-- a écrit « Consolidated alert sent » juste après que `email_alerts` a averti
-- « Email alerts non configurées ». Trois nuits de constats évaporées, tâche verte.
-- La valeur de retour de `send_alert()` était simplement jetée.
--
-- Le correctif de code (`deliver_or_raise`) fait échouer la tâche. Cette table est
-- l'autre moitié : un état PERSISTANT que quelqu'un d'autre peut lire — le cron hôte
-- `infra_health_cron.sh`, qui passe par Brevo et non par le SMTP de l'app, donc qui
-- survit exactement à la panne qui a rendu l'alerte muette.
--
-- Une ligne par exécution de `send_consolidated_alert`, écrite AVANT la tentative
-- d'envoi puis mise à jour après. L'ordre compte : si la tentative lève, la ligne
-- existe déjà avec `delivered = FALSE`, et le lecteur externe voit la panne. Écrire
-- après l'envoi ne laisserait aucune trace du seul cas qui nous intéresse.

CREATE TABLE IF NOT EXISTS monitoring_run (
    id                BIGSERIAL PRIMARY KEY,
    run_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    subject           TEXT,
    issues_count      INTEGER     NOT NULL DEFAULT 0,
    -- FALSE quand il n'y avait rien à signaler : une nuit calme ne doit pas se lire
    -- comme une livraison manquée.
    delivery_expected BOOLEAN     NOT NULL DEFAULT FALSE,
    delivered         BOOLEAN     NOT NULL DEFAULT FALSE,
    delivery_error    TEXT
);

-- Le lecteur externe ne demande qu'une chose : « la dernière exécution, elle date de
-- quand et est-elle arrivée ? ». Un index sur run_at DESC suffit et reste utile quand
-- la table aura des milliers de lignes.
CREATE INDEX IF NOT EXISTS idx_monitoring_run_recent ON monitoring_run (run_at DESC);

COMMENT ON TABLE monitoring_run IS
    'Un enregistrement par exécution de alert_monitor.send_consolidated_alert. '
    'delivery_expected=TRUE + delivered=FALSE est une panne du canal d''alerte : '
    'des constats existaient et personne ne les a reçus.';
COMMENT ON COLUMN monitoring_run.delivery_expected IS
    'TRUE seulement s''il y avait des constats. Une nuit sans constat n''envoie rien '
    'et ce n''est pas une panne.';
