-- 098 — Un rôle applicatif qui n'est pas superutilisateur.
--
-- POURQUOI
-- --------
-- L'application (dashboard, API, DAGs) se connecte en `postgres`, c'est-à-dire en
-- SUPERUTILISATEUR. La conséquence n'est pas « une injection lirait les tables » :
-- un superutilisateur peut `COPY … TO PROGRAM`, donc EXÉCUTER des commandes sur
-- l'hôte, lire `pg_authid` (les empreintes de mots de passe de tous les rôles), et
-- désactiver n'importe quel garde en base. Entre une erreur applicative et la
-- machine entière, il n'y a aujourd'hui aucune couche — et les 0/93 tables sous RLS
-- (choix assumé, ADR) n'en ajoutent pas.
--
-- CE QUE CETTE MIGRATION FAIT, ET CE QU'ELLE NE FAIT PAS
-- ------------------------------------------------------
-- Elle CRÉE le rôle et ses droits. Elle ne bascule RIEN : tant que
-- `DATABASE_USER` n'est pas changé dans l'environnement, l'application continue de
-- se connecter comme avant. Créer un rôle que personne n'utilise ne change aucun
-- comportement — c'est délibéré : la bascule est un geste d'exploitation, avec un
-- redémarrage, et elle se fait quand quelqu'un peut la surveiller.
--
-- Le mot de passe est lu dans `app.streamlytics_app_password`, un paramètre de
-- session posé par `make db-app-role` : écrire un mot de passe en clair dans un
-- fichier versionné est la seule chose que cette migration doit absolument éviter.
-- Sans ce paramètre, le rôle est créé SANS mot de passe et ne peut pas se connecter
-- — un rôle inutilisable est un échec visible, pas un rôle avec un mot de passe
-- deviné.
--
-- Le propriétaire des tables reste `postgres` : le rôle applicatif ne peut donc pas
-- faire de DDL. Les migrations continuent de passer par `make migrate`, en
-- `postgres`, ce qui est exactement la séparation qu'on cherche.

DO $$
DECLARE
    pwd text := current_setting('app.streamlytics_app_password', true);
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'streamlytics_app') THEN
        IF pwd IS NULL OR pwd = '' THEN
            CREATE ROLE streamlytics_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                                         NOINHERIT NOREPLICATION NOBYPASSRLS;
            RAISE NOTICE 'streamlytics_app créé SANS mot de passe — il ne peut pas '
                         'se connecter. Poser app.streamlytics_app_password et rejouer.';
        ELSE
            EXECUTE format(
                'CREATE ROLE streamlytics_app LOGIN NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD %L', pwd);
        END IF;
    ELSIF pwd IS NOT NULL AND pwd <> '' THEN
        EXECUTE format('ALTER ROLE streamlytics_app PASSWORD %L', pwd);
    END IF;
END $$;

-- Ceinture : même si quelqu'un promeut ce rôle par erreur, la migration le redescend
-- à chaque passage. `make migrate` est idempotent et rejoué à chaque déploiement.
ALTER ROLE streamlytics_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

GRANT CONNECT ON DATABASE spotify_etl TO streamlytics_app;
GRANT USAGE ON SCHEMA public TO streamlytics_app;

-- Les DONNÉES, en lecture et en écriture. Pas la structure.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
    TO streamlytics_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO streamlytics_app;

-- Les tables créées par les MIGRATIONS FUTURES. Sans cette ligne, le rôle perdrait
-- l'accès à toute table ajoutée après aujourd'hui, et la panne arriverait des
-- semaines plus tard, sur une surface sans rapport avec la migration fautive.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO streamlytics_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO streamlytics_app;

-- Ce que le rôle n'a explicitement PAS : aucun droit sur `pg_authid` (réservé au
-- superutilisateur par Postgres lui-même), aucun DDL, aucun `COPY … TO PROGRAM`
-- (réservé aux membres de `pg_execute_server_program`, dont il n'est pas membre).
