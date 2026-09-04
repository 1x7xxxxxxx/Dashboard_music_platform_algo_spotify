-- ============================================================
-- 082 — `saas_users.show_setup_on_login` : la mise en route est l'atterrissage
--       tant qu'elle n'est pas finie, et l'artiste peut en décider autrement
-- ============================================================
--
-- Signalé en test le 2026-09-04, deuxième connexion sur le bac à sable : « je ne suis
-- plus sur étapes 1 2 3 » et « impossible de revenir aux différentes étapes de config ».
--
-- L'aiguillage d'accueil (`_first_run_landing`) ne renvoyait vers l'assistant que si
-- l'artiste n'avait **strictement rien** branché — `all(status == 'todo')`. Une seule
-- identité déclarée, et la deuxième connexion tombait sur l'accueil : un tableau
-- d'état presque vide, sans le chemin qui mène au reste de la configuration. Le seuil
-- était « a-t-il commencé ? » là où la question est « a-t-il fini ? ».
--
-- La complétion est déjà définie ailleurs, et une seule fois : les quatre étapes de
-- `home._section_onboarding` (identifiants, CSV Spotify, CSV Apple, une collecte
-- réussie). Elles vivent désormais dans `src/dashboard/utils/setup_completion.py`,
-- lues par l'accueil ET par l'aiguillage — recopier la règle une deuxième fois est
-- exactement ce qui l'aurait fait diverger.
--
-- Pourquoi une colonne, et pas `st.session_state`
-- ------------------------------------------------
-- Parce que la question posée est « est-ce que je veux **revoir** cette page **à la
-- connexion** », et qu'une préférence de connexion qui ne survit pas à la connexion ne
-- répond à rien. Même raisonnement que `saas_users.lang` (migration 079).
--
-- Pourquoi `NOT NULL DEFAULT TRUE`, et pas NULL = jamais choisi
-- -------------------------------------------------------------
-- `lang` est nullable parce que son défaut peut changer (le français n'est pas une
-- vérité). Ici le défaut est le comportement demandé — montrer la mise en route tant
-- qu'elle n'est pas finie — et la case à cocher est cochée d'avance : « pas encore
-- choisi » et « choisi TRUE » produisent la même chose, aujourd'hui et demain. Une
-- distinction qui ne change aucun comportement est une distinction à ne pas écrire.
--
-- La colonne n'a aucun effet une fois la configuration terminée : l'atterrissage
-- redevient l'accueil, quelle que soit sa valeur.
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS show_setup_on_login BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN saas_users.show_setup_on_login IS
    'TRUE (défaut) = la connexion atterrit sur la mise en route tant que les 4 étapes '
    'ne sont pas faites. FALSE = l''artiste a décroché la case, on va droit à l''app. '
    'Sans effet une fois la configuration terminée.';
