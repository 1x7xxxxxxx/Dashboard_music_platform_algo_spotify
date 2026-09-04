-- ============================================================
-- 084 — `saas_users.trial_reminder_sent_at` : un rappel d'essai, jamais deux
-- ============================================================
--
-- L'offre de bienvenue annonce la bascule en Free au bout d'un mois, sur l'écran
-- d'onboarding — lu une fois, le premier jour, par quelqu'un qui n'a pas encore vu un
-- seul graphique. Rien ne le redisait ensuite, alors que la décision se prend dans les
-- derniers jours.
--
-- Pourquoi une COLONNE et pas un calcul
-- --------------------------------------
-- « A-t-on déjà prévenu ce compte ? » ne se déduit d'aucun état existant. On pourrait
-- s'en approcher — « l'essai finit dans exactement 3 jours » ne se produit qu'une fois
-- — mais cette égalité est vraie une fois par EXÉCUTION, pas une fois par compte : un
-- rattrapage, un second run manuel ou un décalage d'horaire renverraient le même
-- message. Un rappel d'essai envoyé deux fois ne se lit pas comme une information, il
-- se lit comme de la pression.
--
-- NULL = jamais prévenu. On n'écrit l'horodatage qu'APRÈS un envoi confirmé : si la
-- porte d'audience (`STREAMLYTICS_ALLOW_ARTIST_EMAIL`) est fermée, le compte reste
-- NULL et le rappel repart le lendemain — J-2 vaut mieux que jamais.
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS trial_reminder_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN saas_users.trial_reminder_sent_at IS
    'Horodatage du rappel J-3 de fin d''essai. NULL = jamais envoyé. Écrit seulement '
    'après un envoi confirmé, pour qu''une porte fermée ne consomme pas le rappel.';

-- Le DAG ne lit que les lignes NULL, chaque jour : l'index partiel est exactement sa
-- question.
CREATE INDEX IF NOT EXISTS idx_saas_users_trial_reminder_pending
    ON saas_users (artist_id) WHERE trial_reminder_sent_at IS NULL;
