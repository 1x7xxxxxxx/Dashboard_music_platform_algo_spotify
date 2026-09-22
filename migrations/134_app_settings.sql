-- ═══════════════════════════════════════════════════════════════════════════
-- 134 — Les réglages que l'exploitant pose depuis l'application
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Demandé le 2026-09-21 : « mettre un lien calendly pour prise de rdv ».
--
-- ⚠️ POURQUOI UNE TABLE ET PAS SEULEMENT UNE VARIABLE D'ENVIRONNEMENT.
--
-- Le premier jet lisait `SERVICE_CALENDLY_URL` dans l'environnement, sans valeur
-- par défaut — correct sur le fond (une URL inventée afficherait un bouton menant
-- à une page morte, soit un rendez-vous qu'on croit pris), mais la conséquence
-- était que la fonctionnalité restait ÉTEINTE : la poser demandait d'éditer
-- `.env.local`, de rebâtir l'environnement du conteneur en production, et de
-- redémarrer. C'est-à-dire un geste que le propriétaire de l'outil ne fait pas
-- pour changer un lien de rendez-vous.
--
-- Le réglage descend donc en base, éditable depuis la page Admin. L'environnement
-- reste PRIORITAIRE quand il est posé : c'est la règle des douze facteurs, et
-- elle permet d'imposer une valeur en production sans toucher aux données.
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE app_settings IS
    'Réglages d''EXPLOITATION éditables depuis l''admin (lien de prise de '
    'rendez-vous, etc.). Sans locataire : ce sont les réglages de l''outil, pas '
    'ceux d''un artiste — ne pas y mettre de donnée scopée `artist_id`.';
