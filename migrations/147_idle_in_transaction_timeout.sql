-- 147 — a session left idle inside an open transaction is ended after 5 minutes (R468).
--
-- Why: an open transaction holds back the xmin horizon for as long as it lives, so
-- vacuum can no longer remove dead rows anywhere in the database. Lesson taken from
-- the msdr catalogue (`pg-idle-in-tx-no-timeout`). Prod had no bound (`SHOW` = 0,
-- read 2026-10-08); no session was idle in a transaction that day, and every path that
-- opens a non-autocommit connection (pg_connect.connect callers, PostgresHandler._atomic,
-- request_throttle) runs SQL only between BEGIN and COMMIT — none waits on the network.
--
-- Lever: ALTER DATABASE, not ALTER ROLE — it covers both `postgres` and
-- `streamlytics_app` (migration 098). The database name comes from current_database()
-- because tools/migrate.sh honours PGDATABASE.
--
-- Applies to NEW sessions only: pooled API/dashboard connections and running Airflow
-- workers keep no bound until they reconnect. A manual BEGIN in psql is also ended
-- after 5 minutes of inactivity. Idempotent: replaying it sets the same value.

DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET idle_in_transaction_session_timeout = %L',
                   current_database(), '5min');
END
$$;
