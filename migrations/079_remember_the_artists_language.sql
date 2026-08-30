-- ============================================================
-- 079 — saas_users.lang : la langue choisie survit à la déconnexion
-- ============================================================
-- Signalé en test le 2026-08-30 : « on doit stocker quelque part si on appuie sur le
-- bouton anglais, ça le mémorise et ça propose automatiquement pour l'artiste en
-- question la langue ».
--
-- Aujourd'hui le choix vit dans `st.session_state['lang']` et est recopié dans le
-- paramètre d'URL `?lang=` — parce que le login appelle `session_state.clear()`
-- (correctif de fixation de session MEDIUM-01) et effacerait sinon un choix fait
-- AVANT de se connecter. Cela le fait survivre à la connexion, pas à la fermeture de
-- l'onglet ni au changement d'appareil.
--
-- NULL = l'artiste n'a jamais choisi. C'est distinct de 'fr' : le défaut peut changer
-- un jour, un choix explicite non. Aucune valeur n'est rétro-remplie pour la même
-- raison — supposer que les comptes existants ont « choisi » le français serait
-- inventer une décision qu'ils n'ont pas prise.
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS lang VARCHAR(5);

COMMENT ON COLUMN saas_users.lang IS
    'Langue choisie explicitement par l''utilisateur (fr|en). NULL = jamais choisi, '
    'l''app applique son défaut.';
