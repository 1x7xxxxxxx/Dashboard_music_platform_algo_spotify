-- ============================================================
-- 078 — monitoring_run.findings_digest : ne pas redire la même chose chaque nuit
-- ============================================================
-- Mesuré le 2026-08-28 sur les XCom des runs du 25 et du 26 août en production. Les
-- deux nuits portent des constats identiques à DEUX champs près — `age_h` (1945.0 →
-- 1969.0, une source qui vieillit) et `when` (l'horodatage du dernier échec Meta).
-- Mêmes locataires, mêmes plateformes, mêmes gestes à faire : le partage de
-- `act_65390907` dans Business Manager pour Benken, un titre public SoundCloud pour
-- GRiNCH. Deux mails, un seul contenu, et aucun des deux actionnable le soir même.
--
-- Cette colonne porte l'empreinte des constats (src/utils/alert_repetition.py), qui
-- ignore les champs de MESURE et garde les champs d'IDENTITÉ. `send_consolidated_alert`
-- la compare à celle du dernier envoi RÉELLEMENT délivré : identique et récent ⇒ la
-- nuit est enregistrée sans envoi.
--
-- Ce que cette colonne ne fait pas, et c'est délibéré :
--
--   * elle ne peut pas taire un constat NOUVEAU, disparu ou modifié — l'empreinte
--     change et le mail part la nuit même ;
--   * elle ne peut pas se taire indéfiniment — au-delà de ALERT_REPEAT_SILENCE_DAYS
--     (7 par défaut) le même constat repart. Un silence permanent est indiscernable
--     d'un moniteur mort, et c'est la panne que la migration 073 existe pour rendre
--     visible.
--
-- La nuit supprimée s'écrit `delivery_expected = FALSE`, exactement comme une nuit
-- calme : `tools/infra_health_cron.sh` lit la dernière ligne et n'a rien à changer —
-- il voit une ligne fraîche dont aucune livraison n'était due. Sans ce FALSE, chaque
-- suppression se lirait comme « des constats existaient et personne ne les a reçus »,
-- soit exactement le contraire de ce qui s'est passé.

ALTER TABLE monitoring_run
    ADD COLUMN IF NOT EXISTS findings_digest TEXT;

-- Le lecteur pose toujours la même question : « quelle est l'empreinte du dernier mail
-- effectivement PARTI ? ». L'index partiel ne porte donc que les lignes délivrées —
-- une suppression ne doit jamais servir de point de comparaison, sinon la fenêtre de
-- silence se réarmerait toute seule chaque nuit et ne se refermerait jamais.
CREATE INDEX IF NOT EXISTS idx_monitoring_run_delivered_recent
    ON monitoring_run (run_at DESC)
    WHERE delivered;

COMMENT ON COLUMN monitoring_run.findings_digest IS
    'Empreinte SHA-256 des constats de la nuit, champs de mesure exclus '
    '(src/utils/alert_repetition.py). Deux nuits de même empreinte disent la même '
    'chose ; la seconde n''est pas envoyée avant ALERT_REPEAT_SILENCE_DAYS.';
