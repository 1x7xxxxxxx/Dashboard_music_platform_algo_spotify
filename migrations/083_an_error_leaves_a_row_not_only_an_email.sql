-- ============================================================
-- 083 — `app_error_log` : une erreur laisse une LIGNE, pas seulement un e-mail
-- ============================================================
--
-- Demandé le 2026-09-04 : « un process automatisé qui intègre en roadmap ou dans un
-- document qu'on relie automatiquement pour chaque erreur ».
--
-- Ce qui existait, et pourquoi ça ne suffit pas
-- --------------------------------------------
-- `notify_app_error` faisait trois choses : un `logger.error`, une ligne
-- `usage_events` de type 'error' (type d'exception + 200 caractères de message), et un
-- e-mail. **La traceback ne vivait QUE dans l'e-mail.** Une boîte mail n'est pas un
-- registre : on ne peut ni compter les occurrences, ni dire « celle-ci est corrigée »,
-- ni savoir si une erreur d'aujourd'hui est la même qu'il y a trois semaines. Et la
-- limitation de débit vivait dans un `dict` de processus : un redémarrage du conteneur
-- renvoyait le même e-mail.
--
-- L'empreinte — la seule décision de conception qui compte ici
-- ------------------------------------------------------------
-- `fingerprint` = SHA1 de (classe d'exception + le PREMIER cadre de pile qui nous
-- appartient, en chemin relatif au dépôt, FONCTION comprise, **sans le numéro de
-- ligne**). Deux occurrences du même défaut doivent tomber sur la même ligne :
--   * le numéro de ligne bouge au premier commit qui touche le fichier au-dessus ;
--   * le message porte souvent une valeur (un id, une clé) qui varie à chaque fois ;
--   * les cadres de `site-packages` décrivent Streamlit, pas notre défaut.
-- Un compteur qui repart à 1 à chaque déploiement ne mesure rien.
--
-- Cycle de vie
-- ------------
-- `resolved_at` + `resolved_note` : une erreur se ferme explicitement, avec la raison.
-- `error_class` fait le lien avec `.claude/dev-docs/error-classes.md` quand la classe
-- existe — c'est ce lien qui transforme une occurrence en connaissance.
--
-- `environment` distingue `local` de `production` : le préfixe `[LOCAL]` de l'e-mail
-- est la seule chose qui les séparait, et il ne survivait pas à la lecture.
CREATE TABLE IF NOT EXISTS app_error_log (
    id              SERIAL PRIMARY KEY,
    fingerprint     VARCHAR(40)  NOT NULL UNIQUE,
    exc_type        VARCHAR(120) NOT NULL,
    message         TEXT,
    page            VARCHAR(120),
    origin          VARCHAR(120),          -- fichier:fonction de notre premier cadre
    artist_id       INTEGER,
    environment     VARCHAR(20)  NOT NULL DEFAULT 'unknown',
    traceback       TEXT,
    first_seen      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    occurrences     INTEGER      NOT NULL DEFAULT 1,
    last_emailed_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_note   TEXT,
    error_class     VARCHAR(120)
);

COMMENT ON TABLE app_error_log IS
    'Une ligne par DÉFAUT (empreinte), pas par occurrence. Alimentée par '
    'notify_app_error ; lue par tools/error_inbox.py et alert_monitor.';
COMMENT ON COLUMN app_error_log.fingerprint IS
    'SHA1(exc_type + premier cadre de pile nous appartenant, sans numéro de ligne). '
    'Stable à travers les déploiements : c''est ce qui permet de compter.';
COMMENT ON COLUMN app_error_log.last_emailed_at IS
    'Remplace le dict de processus : la limitation de débit survit à un redémarrage.';
COMMENT ON COLUMN app_error_log.error_class IS
    'Clé dans .claude/dev-docs/error-classes.md, quand la classe est catalogue.';

-- Le tri de l'inbox : les non résolues, la plus récente d'abord.
CREATE INDEX IF NOT EXISTS idx_app_error_log_open
    ON app_error_log (last_seen DESC) WHERE resolved_at IS NULL;
