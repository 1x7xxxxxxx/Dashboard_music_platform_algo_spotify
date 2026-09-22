-- 135 — La connexion Google : une clé stable, et un mot de passe qui devient facultatif.
--
-- Pourquoi `google_sub` et pas l'e-mail
-- -------------------------------------
-- Google le dit sans ambiguïté dans sa consigne d'intégration : le claim `sub` du
-- jeton d'identité est l'identifiant unique et jamais réutilisé d'un compte, et c'est
-- LUI qui sert de clé. L'adresse e-mail d'un compte Google PEUT CHANGER — un artiste
-- qui renomme son adresse deviendrait, pour nous, quelqu'un d'autre, et se verrait
-- proposer de créer un second compte sur ses propres données.
--
-- L'e-mail reste stocké : il sert à écrire aux gens, et à LIER un compte existant la
-- première fois. Il ne sert jamais de clé après ça.
--
-- Pourquoi `password_hash` devient NULLABLE
-- ------------------------------------------
-- Un compte créé par Google n'a pas de mot de passe, et lui en inventer un serait pire
-- que de ne pas en avoir : un secret que personne ne connaît et que rien ne fait
-- tourner. La colonne était `NOT NULL` depuis la migration 007.
--
-- ⚠️ CETTE COLONNE NULLABLE A UNE CONSÉQUENCE SUR LE CHEMIN MOT DE PASSE, et elle a
-- été trouvée par la critique du design AVANT écriture, pas après :
-- `verify_password(mot_de_passe, NULL)` fait `NULL.encode('utf-8')` et lève
-- `AttributeError` — vérifié en l'exécutant. Un visiteur anonyme qui saisit l'e-mail
-- d'un compte Google et n'importe quel mot de passe fait donc planter la page. Le
-- correctif vit dans `src/dashboard/auth.py::_authenticate_user`, et il PART AVEC
-- cette migration : appliquer l'une sans l'autre ouvre le défaut.
-- Garde : `tests/test_a_google_account_has_no_password_to_guess.py`.
--
-- Ce que cette migration ne fait PAS
-- -----------------------------------
-- Elle ne touche pas `email_verified`, `active`, `totp_enabled` ni `token_version` :
-- la connexion Google passe par les MÊMES contrôles que le mot de passe, elle n'en
-- contourne aucun. Trois trous exactement de cette forme ont été refusés au design :
-- un TOTP jamais redemandé, un compte désactivé qui rentre quand même, et un compte
-- inactif qui retombe dans le parcours d'inscription.

ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS google_sub TEXT;

-- UNIQUE et non PRIMARY : deux comptes ne peuvent pas partager une identité Google,
-- mais un compte peut n'en avoir aucune (les 8 comptes existants au 2026-09-22).
-- Partiel, parce qu'un index UNIQUE ordinaire sur une colonne pleine de NULL
-- fonctionne en PostgreSQL mais indexe pour rien des lignes qu'on ne cherchera jamais.
CREATE UNIQUE INDEX IF NOT EXISTS idx_saas_users_google_sub
    ON saas_users (google_sub)
    WHERE google_sub IS NOT NULL;

-- La date de liaison : elle répond à « depuis quand ce compte entre-t-il par Google ? »
-- lors d'un incident, ce que la seule présence de `google_sub` ne dit pas.
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS google_linked_at TIMESTAMPTZ;

-- Le mot de passe devient facultatif. `DROP NOT NULL` est idempotent en PostgreSQL :
-- le rejouer sur une colonne déjà nullable ne lève pas.
ALTER TABLE saas_users
    ALTER COLUMN password_hash DROP NOT NULL;

-- ⚠️ ET LE GARDE QUI REMPLACE CELUI QU'ON VIENT DE RETIRER. Sans lui, la migration
-- autorise une ligne SANS mot de passe ET SANS identité Google — un compte dans lequel
-- personne ne peut entrer, créé par un chemin d'inscription bogué, et que rien ne
-- signalerait. `NOT NULL` portait cette promesse sans le dire ; on la réécrit en clair.
ALTER TABLE saas_users
    DROP CONSTRAINT IF EXISTS saas_users_has_a_way_in;
ALTER TABLE saas_users
    ADD CONSTRAINT saas_users_has_a_way_in
    CHECK (password_hash IS NOT NULL OR google_sub IS NOT NULL);

COMMENT ON COLUMN saas_users.google_sub IS
    'Claim `sub` du jeton d''identite Google — la cle STABLE. Jamais l''e-mail : '
    'une adresse Google peut changer, `sub` non.';
COMMENT ON COLUMN saas_users.google_linked_at IS
    'Date de liaison de l''identite Google, pour la lecture d''un incident.';
