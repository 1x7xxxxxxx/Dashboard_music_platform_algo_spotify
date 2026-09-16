-- 122 — rate_limit_hits : les compteurs anti-force-brute quittent la mémoire du processus
--
-- POURQUOI. Les budgets de `register`, `totp`, `login` et `/auth/token` étaient exacts
-- uniquement parce qu'il y avait UN processus par surface. Une seconde réplique les
-- multiplie par N sans qu'une ligne des limiteurs ne change — sur des chemins
-- d'authentification, en silence. Cette table est la sortie choisie : un magasin partagé
-- dans la base qui porte déjà le verrouillage par compte (`saas_users.locked_until`),
-- plutôt qu'un Redis de plus à exploiter, sauvegarder et sécuriser.
--
-- FORME. `ts` est un ÉPOQUE en secondes, pas un `timestamptz`, et c'est délibéré : la
-- fenêtre glissante est arithmétique, ses tests injectent un `now=` synthétique, et un
-- aller-retour par `to_timestamp()` / `extract(epoch …)` à chaque tentative n'achèterait
-- que de la conversion. `created_at` existe pour l'humain qui lit la table et pour la
-- purge, jamais pour le calcul.
--
-- PAS d'index partiel `WHERE ts > now() - interval '...'` : le prédicat d'un index
-- partiel doit être IMMUTABLE et `now()` ne l'est pas — l'index serait refusé à la
-- création. L'index composite ci-dessous couvre les trois requêtes du magasin (purge de
-- fenêtre, comptage, insertion) parce que toutes portent `bucket` en égalité.
--
-- PURGE. Le magasin supprime les coups hors fenêtre de la clé qu'il touche, donc une clé
-- vivante ne grossit pas. Ce sont les clés ABANDONNÉES qui restent : la tâche
-- `purge_rate_limit_hits` d'`alert_monitor` les efface chaque nuit.

CREATE TABLE IF NOT EXISTS rate_limit_hits (
    id          BIGSERIAL PRIMARY KEY,
    bucket      TEXT             NOT NULL,
    ts          DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_bucket_ts
    ON rate_limit_hits (bucket, ts);

-- Pour la purge quotidienne, qui balaie par âge et non par clé.
CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_created_at
    ON rate_limit_hits (created_at);

COMMENT ON TABLE rate_limit_hits IS
    'Coups des fenêtres glissantes anti-force-brute, partagés entre instances. '
    'Écrit par src/utils/request_throttle.py:PostgresHitStore sous verrou consultatif. '
    'Purgé par alert_monitor.purge_rate_limit_hits.';
