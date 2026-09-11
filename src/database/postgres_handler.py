"""Handler pour les interactions avec PostgreSQL - VERSION OPTIMISÉE."""
import os
import re
import threading
import psycopg2
from psycopg2 import sql as pgsql
from psycopg2.extras import execute_batch
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# CRITICAL-02: allowlist of valid table names — any table not in this set is rejected
# before query construction. Prevents SQL injection via table name interpolation.
_ALLOWED_TABLES = frozenset({
    'saas_artists', 'artist_credentials', 'saas_users',
    'artists', 'tracks', 'track_popularity_history', 'artist_history',
    's4a_songs_global', 's4a_song_timeline', 's4a_audience',
    'soundcloud_tracks_daily', 'instagram_daily_stats',
    'instagram_media', 'instagram_media_insights',
    'imusician_monthly_revenue', 'imusician_release_summary', 'imusician_sales_detail',
    'distrokid_monthly_revenue', 'distrokid_sales_detail',
    'ml_song_predictions', 'artist_wrapped',
    'meta_campaigns', 'meta_adsets', 'meta_ads', 'meta_insights',
    'meta_insights_performance', 'meta_insights_performance_day',
    'meta_insights_performance_age', 'meta_insights_performance_country',
    'meta_insights_performance_placement',
    'meta_insights_engagement', 'meta_insights_engagement_day',
    'meta_insights_engagement_age', 'meta_insights_engagement_country',
    'meta_insights_engagement_placement',
    # Ad/adset-level breakdowns (multi-grain Breakdowns view)
    'meta_insights_performance_ad_country', 'meta_insights_performance_ad_placement',
    'meta_insights_performance_ad_age',
    'meta_insights_performance_adset_country', 'meta_insights_performance_adset_placement',
    'meta_insights_performance_adset_age',
    'meta_insights_engagement_ad_country', 'meta_insights_engagement_ad_placement',
    'meta_insights_engagement_ad_age',
    'meta_insights_engagement_adset_country', 'meta_insights_engagement_adset_placement',
    'meta_insights_engagement_adset_age',
    'youtube_channels', 'youtube_channel_history', 'youtube_videos',
    'youtube_video_stats', 'youtube_playlists', 'youtube_comments',
    'apple_songs_performance', 'apple_daily_plays', 'apple_listeners', 'apple_songs_history',
    'hypeddit_campaigns', 'hypeddit_daily_stats',
    'subscription_plans', 'artist_subscriptions',
    'referral_codes', 'referral_events',
    'promo_codes', 'promo_events',
    'etl_run_log', 'etl_circuit_breaker',
    'admin_audit_log',
    's4a_song_playlists',
    's4a_song_playlist_adds',
    'csv_upload_log',
    'active_sessions',
    'subscription_plan_history',
    'track_release_reference',
    's4a_song_saves_daily',
    's4a_song_discovery_mode',
    's4a_song_nonalgo_streams',
    's4a_artist_radio_count',
    's4a_song_algo_outcomes',
    'ml_prediction_outcomes',
    'track_platform_link',
    'campaign_track_mapping',
    'campaign_mapping_rejected',
    'app_operating_costs',
    'sacem_statement',
    # Monitoring ledgers — written by alert_monitor and by the setup matrix.
    'monitoring_run',
    'tenant_platform_probe',
})

_VALID_IDENTIFIER_RE = re.compile(r'^[a-z_][a-z0-9_]*$')


# ── Pool de connexions, OPT-IN ───────────────────────────────────────────────
#
# Activé par les processus qui ouvrent et referment beaucoup de connexions
# courtes — le dashboard (4 par rendu) et l'API (1 par requête). JAMAIS par
# Airflow : ses tâches tiennent une connexion pendant des minutes, un pool n'y
# gagne rien et lui ferait partager des connexions entre opérateurs.
#
# `options` et `connect_timeout` sont posés À LA CRÉATION de chaque connexion du
# pool, exactement comme dans `_connect()`. C'est le piège de cette classe :
# `statement_timeout` voyage dans les options de connexion, donc un pool qui les
# oublierait supprimerait la borne des 15 s **en silence**.
_POOL = None
_POOL_LOCK = threading.Lock()


def enable_pool(minconn: int = 1, maxconn: int = 10, **connect_kwargs) -> None:
    """Crée le pool du processus. Idempotent ; sans effet si déjà créé."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is not None:
            return
        from psycopg2.pool import ThreadedConnectionPool
        _POOL = ThreadedConnectionPool(
            minconn, maxconn,
            connect_timeout=5, options="-c statement_timeout=15000",
            **connect_kwargs,
        )
        logger.info("pool de connexions actif (%d-%d)", minconn, maxconn)


def enable_pool_from_env(minconn: int = 1, maxconn: int = 10) -> bool:
    """Active le pool avec la configuration que l'application utilise déjà.

    La précédence `DATABASE_URL` → `DATABASE_*` → `config.yaml` n'est pas
    recopiée ici : elle vit dans `PostgresHandler.from_env_or_config()` et
    `src.utils.pg_connect.resolve_kwargs()`. Une seconde copie dériverait, et ce
    dépôt a déjà payé pour cette forme exacte — la moitié API et la moitié
    Airflow atteignaient la même base par deux mécanismes dont aucun ne
    fonctionnait à la place de l'autre.

    Rend False (sans lever) quand rien n'est configuré : un pool absent est un
    ralentissement, pas une panne.
    """
    try:
        url = os.environ.get("DATABASE_URL")
        if url:
            parsed = urlparse(url)
            kwargs = {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "database": parsed.path.lstrip("/"),
                "user": parsed.username or "postgres",
                "password": parsed.password or "",
            }
        else:
            from src.utils.pg_connect import resolve_kwargs
            kwargs = resolve_kwargs()
        enable_pool(minconn, maxconn, **kwargs)
        return True
    except Exception as exc:      # noqa: BLE001 — sans pool on retombe sur le direct
        logger.warning("pool non activé (%s) — connexions directes", type(exc).__name__)
        return False


def disable_pool() -> None:
    """Ferme le pool et revient aux connexions directes (tests, arrêt propre)."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            return
        try:
            _POOL.closeall()
        finally:
            _POOL = None


def pool_is_enabled() -> bool:
    return _POOL is not None


def _borrow_from_pool():
    """Une connexion du pool, ou None s'il n'y en a pas.

    Une panne du pool ne doit pas rendre l'application indisponible : on retombe
    sur une connexion directe, qui est le comportement d'avant.
    """
    if _POOL is None:
        return None
    try:
        return _POOL.getconn()
    except Exception as exc:      # noqa: BLE001 — le repli direct est correct
        logger.warning("pool indisponible (%s) — connexion directe", type(exc).__name__)
        return None


def _return_to_pool(conn) -> bool:
    """Rend la connexion au pool. True si elle a été rendue.

    Une connexion laissée dans une transaction avortée EMPOISONNE le pool : le
    prochain emprunteur reçoit un `current transaction is aborted`. `_atomic()`
    bascule l'autocommit pour la durée d'un lot, donc le cas est atteignable.
    On annule donc toujours avant de rendre, et on JETTE la connexion si même
    cela échoue.
    """
    if _POOL is None or conn is None:
        return False
    try:
        if not conn.closed:
            conn.rollback()
            conn.autocommit = True
        _POOL.putconn(conn)
        return True
    except Exception as exc:      # noqa: BLE001
        logger.warning("connexion non rendue au pool (%s) — jetée", type(exc).__name__)
        try:
            _POOL.putconn(conn, close=True)
        except Exception:         # noqa: BLE001
            pass
        return True


def validate_table(table: str) -> None:
    """Raise ValueError if table is not in the allowlist."""
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"SQL injection guard: table '{table}' is not in the allowed list")


def validate_columns(columns: List[str]) -> None:
    """Raise ValueError if any column name contains non-identifier characters."""
    for col in columns:
        # Allow functional index expressions like (collected_at::date)
        if col.startswith('('):
            continue
        if not _VALID_IDENTIFIER_RE.match(col):
            raise ValueError(f"SQL injection guard: invalid column name '{col}'")


def _union_columns(data: List[Dict[str, Any]]) -> List[str]:
    """Toutes les colonnes présentes dans AU MOINS une ligne, dans l'ordre de rencontre.

    Prendre `data[0].keys()` — ce que faisaient les deux écritures de masse jusqu'au
    2026-09-06 — signifie qu'une colonne absente de la PREMIÈRE ligne n'est écrite
    pour AUCUNE, sans erreur ni journal : les valeurs suivantes disparaissent en
    silence. Un lot hétérogène est la norme dès qu'un parseur n'émet un champ que
    lorsqu'il le trouve.

    L'ordre de rencontre plutôt qu'un tri : il garde la lisibilité de la requête et
    reste déterministe pour un même lot.
    """
    seen: Dict[str, None] = {}
    for row in data:
        for key in row:
            seen.setdefault(key, None)
    return list(seen)


class PostgresHandler:
    """Gestionnaire de connexion et opérations PostgreSQL."""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        """
        Initialise la connexion PostgreSQL.

        Args:
            host: Hôte PostgreSQL
            port: Port PostgreSQL
            database: Nom de la base de données
            user: Utilisateur
            password: Mot de passe
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
        self.cursor = None
        self._from_pool = False

        self._connect()

    @classmethod
    def from_url(cls, url: str) -> "PostgresHandler":
        """
        Instantiate from a DATABASE_URL string.

        Accepts both ``postgresql://`` and ``postgres://`` schemes (Railway uses the latter).
        Example: ``postgres://user:pass@host:5432/dbname``
        """
        parsed = urlparse(url)
        # Normalise scheme so psycopg2 accepts it
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")
        return cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            user=parsed.username or "postgres",
            password=parsed.password or "",
        )

    @classmethod
    def from_env_or_config(cls) -> "PostgresHandler":
        """Instantiate from whichever of the three sources is configured.

        ``DATABASE_URL`` → the ``DATABASE_*`` variables → ``config.yaml``. The middle
        step was added 2026-08-21 (R33) and it is not cosmetic: production runs the
        two halves differently — the api and dashboard containers get DATABASE_URL
        and no DATABASE_HOST, Airflow gets DATABASE_HOST and no DATABASE_URL. Without
        the middle step this method simply did not work inside Airflow, which is why
        three collectors each hand-rolled the same five ``os.getenv`` calls to fill
        the constructor themselves — all three defaulting the host to ``localhost``,
        wrong in the very place they run.

        The precedence itself lives in ``src.utils.pg_connect``; this is a second
        door onto it, not a second copy. Raises when nothing is configured, rather
        than letting ``config['database']`` KeyError on an empty config.
        """
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            return cls.from_url(database_url)

        from src.utils.pg_connect import resolve_kwargs
        return cls(**resolve_kwargs())

    def _connect(self) -> None:
        """Établit la connexion à PostgreSQL, en l'empruntant au pool s'il existe.

        MESURÉ, parce que la décision inverse avait été prise sur la mauvaise
        grandeur. Le 2026-08-30, le pooling est écarté au motif que « SQL sur les
        42 vues : 755 ms pour 372 requêtes = 2 ms la requête ». C'est le coût des
        REQUÊTES, et il est juste. Le coût d'une CONNEXION n'avait pas été pris :
        mesuré depuis le conteneur de production le 2026-09-11, **p50 13 ms**,
        dont ~8,5 ms de poignée de main SCRAM — et un rendu de page en ouvre
        **4**, soit 52 ms sur un rendu de 287 ms, 18 %.

        Le pool est OPT-IN et personne ne l'active par défaut : `enable_pool()`
        est appelé par le dashboard et l'API, jamais par Airflow, dont les tâches
        tiennent une connexion pendant des minutes et n'y gagneraient rien.
        """
        pool = _borrow_from_pool()
        if pool is not None:
            self.conn, self._from_pool = pool, True
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()
            return
        self._from_pool = False
        try:
    # DÉLAIS D'ATTENTE — une base qui PEND est pire qu'une base qui refuse.
    #
    # Sans `connect_timeout`, une partition réseau ou un `max_connections` atteint fait
    # attendre le délai TCP du système (~2 min). L'API tourne en un seul processus avec
    # des endpoints synchrones : quarante requêtes suffisent alors à épuiser le pool de
    # threads, et `/health` — synchrone lui aussi — cesse de répondre. La sonde externe
    # conclut que l'API est morte alors que seule la base pend.
    #
    # `statement_timeout` borne la requête elle-même : une table verrouillée ne peut
    # plus retenir un thread indéfiniment. 15 s est très au-dessus de l'agrégat le plus
    # lourd du produit, mesuré à 39 ms.
            self.conn = psycopg2.connect(
            connect_timeout=5, options="-c statement_timeout=15000",
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )

            # ✅ AUTOCOMMIT : Chaque requête est committée immédiatement
            self.conn.autocommit = True

            self.cursor = self.conn.cursor()
            logger.info(f"✅ Connecté à PostgreSQL: {self.database}")
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            raise

    def _ensure_connection(self) -> None:
        """Reconnecte automatiquement si la connexion est perdue."""
        try:
            if self.conn is None or self.conn.closed:
                logger.warning("⚠️ Connexion PostgreSQL perdue — reconnexion automatique...")
                self._connect()
                return
            # Test léger de connexion via poll()
            self.conn.poll()
        except psycopg2.OperationalError:
            logger.warning("⚠️ Connexion PostgreSQL interrompue — reconnexion automatique...")
            self._connect()

    @contextmanager
    def _atomic(self):
        """UN lot, UNE transaction — au lieu d'une transaction par ligne.

        La connexion est en `autocommit = True`, ce qui est le bon défaut pour une
        lecture ou une écriture isolée. Sur un LOT, il produit deux effets, et le
        second est le vrai défaut :

        * chaque ligne est sa propre transaction, donc son propre fsync — 1 500
          titres pour un locataire font 1 500 transactions ;
        * surtout, un échec à la ligne 900 laisse **899 lignes committées**. La
          collecte est appliquée à moitié, et rien en base ne dit laquelle des deux
          moitiés on regarde. C'est la forme silencieuse d'une donnée fausse : pas
          une erreur visible, un état partiel indiscernable d'un état complet.

        Ce contexte suspend l'autocommit le temps du lot, valide en bloc, et
        RESTAURE l'état précédent quoi qu'il arrive — y compris si la connexion a
        été rouverte entre-temps.
        """
        conn = getattr(self, "conn", None)
        if conn is None:
            # Pas de connexion réelle : une doublure de test, qui enregistre l'appel
            # au curseur sans rien committer. On exécute le corps tel quel plutôt que
            # de lever — mais on ne PRÉTEND pas avoir ouvert une transaction : en
            # production ce chemin est inatteignable, `_ensure_connection()` ayant
            # été appelé juste avant par les deux seuls appelants.
            yield
            return
        previous = conn.autocommit
        conn.autocommit = False
        try:
            yield
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 — une connexion morte ne se rollback pas
                pass
            raise
        finally:
            try:
                conn.autocommit = previous
            except Exception:  # noqa: BLE001 — idem : on ne masque pas l'erreur d'origine
                pass

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> None:
        """
        Exécute une requête SQL (INSERT, UPDATE, DELETE, CREATE).

        Args:
            query: Requête SQL
            params: Paramètres de la requête
        """
        self._ensure_connection()
        try:
            self.cursor.execute(query, params)
            # ✅ Pas de commit nécessaire avec autocommit = True
            logger.debug("✅ Requête exécutée")
        except Exception as e:
            logger.error(f"❌ Erreur exécution requête: {e}")
            logger.error(f"   Query: {query[:200]}...")
            raise

    def fetch_query(self, query: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """
        Exécute une requête SELECT et retourne les résultats.

        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête

        Returns:
            Liste de tuples avec les résultats
        """
        self._ensure_connection()
        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            logger.debug(f"✅ Fetch query retourné {len(results)} lignes")
            return results
        except Exception as e:
            logger.error(f"❌ Erreur fetch requête: {e}")
            logger.error(f"   Query: {query[:200]}...")
            raise

    def fetch_df(self, query: str, params: Optional[Tuple] = None):
        """
        Exécute une requête SELECT et retourne un DataFrame pandas.

        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête

        Returns:
            DataFrame pandas
        """
        self._ensure_connection()
        try:
            import pandas as pd
            self.cursor.execute(query, params)
            columns = [desc[0] for desc in self.cursor.description]
            data = self.cursor.fetchall()
            df = pd.DataFrame(data, columns=columns)
            logger.debug(f"✅ Fetch DataFrame retourné {len(df)} lignes")
            return df
        except Exception as e:
            logger.error(f"❌ Erreur fetch DataFrame: {e}")
            logger.error(f"   Query: {query[:200]}...")
            raise

    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> int:
        """
        Insert multiple rows efficacement.

        Args:
            table: Nom de la table
            data: Liste de dictionnaires {colonne: valeur}

        Returns:
            Nombre de lignes insérées
        """
        if not data:
            logger.warning(f"⚠️ insert_many appelé avec data vide pour {table}")
            return 0

        validate_table(table)
        # `upsert_many` le fait depuis toujours, `insert_many` non : une connexion
        # perdue entre deux lots faisait échouer l'écriture au lieu de se rouvrir.
        self._ensure_connection()
        try:
            columns = _union_columns(data)
            validate_columns(columns)
            values = [[row.get(col) for col in columns] for row in data]

            query = pgsql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                pgsql.Identifier(table),
                pgsql.SQL(', ').join(map(pgsql.Identifier, columns)),
                pgsql.SQL(', ').join(pgsql.Placeholder() * len(columns)),
            )

            # `execute_batch`, comme `upsert_many` — et non `executemany`, qui envoyait
            # une instruction ET une transaction PAR LIGNE.
            #
            # `execute_values` serait plus rapide encore (une seule instruction pour
            # tout le lot) et il a été essayé : il exige un vrai curseur psycopg2 pour
            # rendre les identifiants, ce qui rend le garde
            # `test_a_bulk_write_sees_every_column` inexécutable — or ce garde tient
            # une classe déjà payée (`bulk-write-reads-only-the-first-row`). On ne
            # désarme pas un garde pour gagner des millisecondes sur un lot nocturne.
            # Le défaut à retirer était la transaction par ligne, et le contexte
            # ci-dessous la retire.
            with self._atomic():
                execute_batch(self.cursor, query, values, page_size=500)

            logger.info(f"✅ {len(data)} ligne(s) insérée(s) dans {table}")
            return len(data)
        except Exception as e:
            logger.error(f"❌ Erreur insert_many sur {table}: {e}")
            raise

    def upsert_many(self, table: str, data: List[Dict[str, Any]],
                    conflict_columns: List[str], update_columns: List[str]) -> int:
        """
        Upsert (INSERT ... ON CONFLICT UPDATE) multiple rows.

        Args:
            table: Nom de la table
            data: Liste de dictionnaires
            conflict_columns: Colonnes pour détection conflit
            update_columns: Colonnes à mettre à jour si conflit

        Returns:
            Nombre de lignes affectées
        """
        if not data:
            logger.warning(f"⚠️ upsert_many appelé avec data vide pour {table}")
            return 0

        # Deduplicate by conflict_columns before sending to PostgreSQL.
        # PostgreSQL raises CardinalityViolation if the same constraint key
        # appears twice in a single execute_values batch.
        # Only skip columns that are plain names (not SQL expressions like
        # '(collected_at::date)') so functional-index conflicts still work.
        plain_conflict_cols = [c for c in conflict_columns if not c.startswith('(')]
        if plain_conflict_cols:
            seen: dict = {}
            for row in data:
                key = tuple(str(row.get(c, '')).strip() for c in plain_conflict_cols)
                seen[key] = row          # last write wins (same semantics as DO UPDATE)
            if len(seen) < len(data):
                logger.warning(
                    f"upsert_many({table}): deduplicated {len(data)} → {len(seen)} rows "
                    f"on {plain_conflict_cols}"
                )
            data = list(seen.values())

        validate_table(table)
        self._ensure_connection()
        try:
            columns = _union_columns(data)
            validate_columns(columns)
            validate_columns([c for c in conflict_columns if not c.startswith('(')])
            validate_columns(update_columns)
            values = [[row.get(col) for col in columns] for row in data]

            # Build INSERT ... ON CONFLICT ... DO UPDATE using psycopg2.sql to
            # prevent any SQL injection via table/column name interpolation.
            plain_conflict = [c for c in conflict_columns if not c.startswith('(')]
            expr_conflict  = [c for c in conflict_columns if c.startswith('(')]

            conflict_parts = (
                [pgsql.Identifier(c) for c in plain_conflict]
                + [pgsql.SQL(c) for c in expr_conflict]
            )

            query = pgsql.SQL(
                "INSERT INTO {tbl} ({cols}) VALUES ({vals}) "
                "ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
            ).format(
                tbl=pgsql.Identifier(table),
                cols=pgsql.SQL(', ').join(map(pgsql.Identifier, columns)),
                vals=pgsql.SQL(', ').join(pgsql.Placeholder() * len(columns)),
                conflict=pgsql.SQL(', ').join(conflict_parts),
                updates=pgsql.SQL(', ').join(
                    pgsql.SQL("{} = EXCLUDED.{}").format(
                        pgsql.Identifier(c), pgsql.Identifier(c)
                    )
                    for c in update_columns
                ),
            )

            # `execute_batch` groupe les allers-retours par paquets de 100 ; sans le
            # contexte ci-dessous, CHAQUE paquet restait sa propre transaction, donc
            # un échec au 12ᵉ paquet laissait 1 100 lignes en base et 400 dehors.
            with self._atomic():
                execute_batch(self.cursor, query, values)
            # cursor.rowcount after execute_batch reflects the last batch only — not the total.
            # Return len(data) (post-deduplication) as the canonical row count.
            rows_affected = len(data)

            logger.info(f"✅ {rows_affected} ligne(s) affectée(s) dans {table}")
            return rows_affected
        except Exception as e:
            logger.error(f"❌ Erreur upsert_many sur {table}: {e}")
            logger.error(f"   Data sample: {data[0] if data else 'empty'}")
            raise

    def table_exists(self, table_name: str) -> bool:
        """Vérifie si une table existe."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
        """
        result = self.fetch_query(query, (table_name,))
        return result[0][0] if result else False

    def get_table_count(self, table_name: str) -> int:
        """Retourne le nombre de lignes dans une table."""
        try:
            query = pgsql.SQL("SELECT COUNT(*) FROM {}").format(
                pgsql.Identifier(table_name)
            )
            result = self.fetch_query(query)
            count = result[0][0] if result else 0
            logger.debug(f"📊 Table {table_name}: {count} lignes")
            return count
        except Exception as e:
            logger.error(f"❌ Erreur get_table_count pour {table_name}: {e}")
            return 0

    def close(self) -> None:
        """Ferme la connexion — ou la REND au pool si elle en vient.

        Sans cette distinction le pool ne servirait à rien : chaque `close()`
        détruirait la connexion empruntée, et le pool en rouvrirait une au
        suivant. Le curseur est toujours fermé, lui : une connexion rendue avec
        un curseur ouvert emporte son état chez l'emprunteur d'après.
        """
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:      # noqa: BLE001 — un curseur mort est déjà fermé
                pass
            self.cursor = None
        if getattr(self, "_from_pool", False) and _return_to_pool(self.conn):
            self.conn = None
            return
        if self.conn:
            self.conn.close()
        logger.info("🔒 Connexion PostgreSQL fermée")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
