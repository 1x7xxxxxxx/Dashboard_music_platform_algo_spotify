-- 125 — daily_ops_metrics : la traçabilité LONGUE, en base
--
-- POURQUOI DEUX STOCKAGES. Prometheus garde 30 jours à haute fréquence : c'est ce qu'il
-- fait bien, et c'est ce que Grafana lit. Mais sa base meurt avec le conteneur, et rien
-- n'y est interrogeable en SQL à côté des données métier. Une question comme « nos
-- rendus se sont-ils dégradés depuis qu'on a trois locataires de plus ? » se pose sur
-- des MOIS et croise `saas_artists` — Prometheus ne sait répondre ni à l'un ni à l'autre.
--
-- POURQUOI PAS TOUT EN POSTGRES. Écrire chaque point sur le chemin chaud coûterait une
-- écriture par rendu, et ferait de Postgres une base de séries temporelles qu'il n'est
-- pas. Le résumé QUOTIDIEN donne la traçabilité sans le coût.
--
-- LA SOURCE est l'API de Prometheus, pas une seconde instrumentation. Deux chemins de
-- mesure pour la même grandeur divergeraient, et personne ne saurait lequel croire —
-- c'est la classe `deux-surfaces-deux-nombres`, que ce dépôt a déjà payée sur cinq
-- surfaces affichant deux totaux différents au même instant (ADR-019).
--
-- ÉCRITE PAR la tâche `write_daily_ops_metrics` du DAG `alert_monitor`, qui tourne déjà
-- à 23 h UTC. Pas de nouvel ordonnanceur.

CREATE TABLE IF NOT EXISTS daily_ops_metrics (
    day               DATE PRIMARY KEY,
    -- Rendu, vu du SERVEUR. La séparation chrome/vue est le fond du sujet : le rendu
    -- par vue est de 61 ms quand la page complète est à 468-538 ms.
    p50_render_ms     INTEGER,
    p95_render_ms     INTEGER,
    p95_chrome_ms     INTEGER,
    p95_view_ms       INTEGER,
    -- Charge réelle. `peak_sessions` exclut les canaris et le bac à sable : les compter
    -- rapprochait artificiellement un seuil de son déclencheur (320 des 1 043 événements
    -- d'une journée venaient du locataire `sandbox`, c'est-à-dire de nous).
    peak_sessions     INTEGER,
    reruns_total      BIGINT,
    -- Le pool. `pool_direct_fallbacks` est le compteur qui manquait : une saturation
    -- retombe sur une connexion DIRECTE en silence, et rien ne la distingue du
    -- fonctionnement normal. Toute valeur > 0 est un signal.
    pool_high_water   INTEGER,
    pool_direct_fallbacks INTEGER,
    -- Machine.
    cpu_max_pct       NUMERIC(5,2),
    ram_max_pct       NUMERIC(5,2),
    disk_pct          NUMERIC(5,2),
    -- Erreurs, par page, en JSON : la forme change plus vite qu'une colonne.
    errors_by_page    JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- La provenance. Un résumé dont on ignore la source est un chiffre orphelin : le
    -- jour où Prometheus est indisponible, la ligne doit dire qu'elle est partielle
    -- plutôt que de laisser croire à des zéros mesurés.
    source            TEXT NOT NULL DEFAULT 'prometheus',
    complete          BOOLEAN NOT NULL DEFAULT TRUE,
    written_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_daily_ops_metrics_day ON daily_ops_metrics (day DESC);

COMMENT ON TABLE daily_ops_metrics IS
    'TÉLÉMÉTRIE AGRÉGÉE — un résumé par jour, écrit par alert_monitor depuis l''API de '
    'Prometheus. RÉTENTION : garde tout. C''est le seul endroit où la performance se lit '
    'sur des mois et se croise en SQL avec les données métier ; une ligne par jour ne '
    'grossit que de 365 lignes par an, il n''y a rien à purger. '
    'Prometheus garde les 30 derniers jours à haute fréquence ; cette table garde la '
    'forme longue.';

COMMENT ON COLUMN daily_ops_metrics.complete IS
    'FALSE quand Prometheus n''a pas répondu à toutes les requêtes du jour. Une ligne '
    'incomplète vaut mieux qu''une absence — l''absence se lit comme « la surveillance '
    'n''a pas tourné », ce qui est un autre problème.';
