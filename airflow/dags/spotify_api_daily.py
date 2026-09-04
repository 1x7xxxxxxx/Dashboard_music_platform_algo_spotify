"""DAG Spotify API - Collecte quotidienne artistes et tracks.

Brick 6 : supporte artist_id dans dag_run.conf.
  - conf.artist_id fourni → credentials depuis DB pour cet artiste.
  - conf absent           → fallback sur env vars (comportement historique).
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, date  # ✅ AJOUT de 'date'
import sys
import os
import logging

# Ajouter le projet au path
sys.path.insert(0, '/opt/airflow')

# Redact credentials out of any exception this module logs: an HTTP
# exception message embeds the prepared URL, and several upstream APIs take
# their credential as a QUERY PARAMETER. stdlib-only, safe at DAG parse time.
from src.utils.safe_error import safe_error
from src.utils.dag_timeouts import dagrun_timeout_for


logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {safe_error(e)}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def collect_spotify_artists(**context):
    """Collecte les statistiques des artistes via API Spotify."""

    try:
        from src.collectors.spotify_api import SpotifyCollector
        from src.database.postgres_handler import PostgresHandler
        from src.utils.credential_loader import load_platform_credentials

        logger.info('🎸 Collecte Spotify - Artistes...')

        from src.utils.credential_loader import get_active_artists
        from src.utils.dag_run_logger import (
            record_tenant_failure, record_tenant_skip, record_tenant_success,
        )

        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')
        run_id = context.get('run_id', '') if context else ''

        active_artists = get_active_artists(include_artist_id=artist_id_conf)
        if not active_artists and os.getenv('LEGACY_SINGLE_TENANT') == '1':
            active_artists = [(1, 'default')]

        # App credentials: the CENTRAL admin-owned app (ADR-006). The previous code
        # read them from `active_artists[0]` — i.e. ONE tenant's stored override was
        # silently used to collect for the whole fleet, putting everyone's calls on
        # that tenant's quota. A per-artist override is honoured only on a run that
        # is scoped to that very artist.
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if artist_id_conf:
            creds = load_platform_credentials(artist_id_conf, 'spotify')
            if creds.get('client_id') and creds.get('client_secret'):
                client_id = creds['client_id']
                client_secret = creds['client_secret']
                logger.info(f'  Spotify app override from DB (artist_id={artist_id_conf})')

        # Initialiser collector
        collector = SpotifyCollector(
            client_id=client_id,
            client_secret=client_secret
        )

        # Share credentials with next task via XCom (avoids second DB lookup + auth)
        context['task_instance'].xcom_push(
            key='spotify_creds',
            value={'client_id': client_id, 'client_secret': client_secret}
        )

        # ✅ Connexion à la base spotify_etl
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            #database='spotify_etl',  # ✅ Base correcte, mais on vient la récupérer dynamiquement via .env
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )

        # ── Liste des artistes Spotify à suivre (par tenant) ───────────────
        # Central model: each tenant supplies their Spotify artist identity, stored in
        # saas_artists.spotify_artist_id and collected under one admin app. The legacy
        # global env SPOTIFY_ARTIST_IDS is merged (backward-compat / admin-pinned IDs).
        # The tenant travels WITH its Spotify id. The loop below used to carry only the
        # VARCHAR Spotify identifier, so no per-tenant outcome could be recorded — the
        # ledger cannot say "collection ran for this tenant" from an id it cannot map.
        if artist_id_conf:
            rows = db.fetch_query(
                "SELECT id, spotify_artist_id FROM saas_artists "
                "WHERE id = %s AND spotify_artist_id IS NOT NULL AND spotify_artist_id <> ''",
                (artist_id_conf,),
            )
            artist_ids = [(r[0], r[1]) for r in rows]  # tenant-scoped: do NOT fold in the global env
        else:
            rows = db.fetch_query(
                "SELECT id, spotify_artist_id FROM saas_artists "
                "WHERE active = TRUE AND spotify_artist_id IS NOT NULL AND spotify_artist_id <> ''"
            )
            # SPOTIFY_ARTIST_IDS is the ADMIN's own artist list. Folding it into every
            # fleet run collected the admin alongside the tenants and, downstream,
            # produced rows no tenant owns. Opt-in only, for a genuinely legacy
            # single-tenant deployment.
            env_ids = []
            if os.getenv('LEGACY_SINGLE_TENANT') == '1':
                # No tenant owns an env-pinned id — recorded as (None, <spotify id>) so
                # the ledger never attributes it to somebody.
                env_ids = [(None, a.strip())
                           for a in os.getenv('SPOTIFY_ARTIST_IDS', '').split(',') if a.strip()]
            seen, artist_ids = set(), []
            for tenant, sp_id in [(r[0], r[1]) for r in rows] + env_ids:
                if sp_id not in seen:
                    seen.add(sp_id)
                    artist_ids.append((tenant, sp_id))

        # A tenant with no Spotify identity never appears in the query above, so for
        # Spotify — and only Spotify — "declared nothing" was invisible to the ledger
        # while every other platform recorded it as `skipped`. Record it here, so the
        # question "did collection run for this tenant?" has an answer for all five.
        declared = {tid for tid, _ in artist_ids if tid is not None}
        for (tid,) in db.fetch_query(
                "SELECT id FROM saas_artists WHERE active = TRUE "
                "AND COALESCE(spotify_artist_id, '') = ''"):
            if tid not in declared:
                record_tenant_skip('spotify_api_daily', tid, 'spotify',
                                   'no Spotify artist id declared', run_id)

        if not artist_ids:
            logger.warning('⚠️ Aucun Spotify Artist ID configuré '
                           '(saas_artists.spotify_artist_id / SPOTIFY_ARTIST_IDS)')
            db.close()
            return 0

        artists_collected = 0

        for saas_artist_id, artist_id in artist_ids:
            artist_id = (artist_id or '').strip()
            if not artist_id:
                # Defensive: the query filters empty ids, so this can only fire for a
                # blank env-pinned entry (legacy, no tenant). Recorded anyway when a
                # tenant IS attached — a loop exit that writes nothing is exactly what
                # made a stopped tenant indistinguishable from one never looked at.
                if saas_artist_id is not None:
                    record_tenant_skip('spotify_api_daily', saas_artist_id, 'spotify',
                                       'Spotify artist id is blank', run_id)
                continue

            logger.info(f'📊 Collecte artiste: {artist_id}')

            try:
                # Récupérer infos artiste
                artist_info = collector.get_artist_info(artist_id)

                if artist_info:
                    # Stocker dans table artists
                    db.upsert_many(
                        table='artists',
                        data=[artist_info],
                        conflict_columns=['artist_id'],
                        update_columns=['name', 'followers', 'popularity', 'collected_at']
                    )

                    # Stocker historique
                    db.execute_query("""
                        INSERT INTO artist_history (artist_id, followers, popularity, collected_at)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        artist_info['artist_id'],
                        artist_info['followers'],
                        artist_info['popularity'],
                        artist_info['collected_at']
                    ))

                    artists_collected += 1
                    logger.info(f'✅ Artiste {artist_id} collecté')
                    if saas_artist_id is not None:
                        record_tenant_success('spotify_api_daily', saas_artist_id,
                                              'spotify', 1, run_id)
            except Exception as e:
                # Per-artist isolation: a single bad Spotify ID must not abort the fleet.
                logger.error(f'  Spotify collect failed for {artist_id}: {safe_error(e)}')
                if saas_artist_id is not None:
                    record_tenant_failure('spotify_api_daily', saas_artist_id,
                                          'spotify', e, run_id)
                continue

        db.close()

        if artist_ids and artist_ids != [''] and artists_collected == 0:
            raise ValueError(
                f"Spotify API collected 0 artists from {len(artist_ids)} configured IDs. "
                "Check SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET validity."
            )

        logger.info(f'✅ Total: {artists_collected} artistes collectés')
        return artists_collected

    except Exception as e:
        logger.error(f'❌ Erreur collecte artistes: {safe_error(e)}')
        import traceback
        traceback.print_exc()
        raise


def collect_spotify_top_tracks(**context):
    """Collecte les top tracks des artistes et stocke l'historique de popularité."""
    try:
        from src.collectors.spotify_api import SpotifyCollector
        from src.database.postgres_handler import PostgresHandler

        logger.info('🎵 Collecte Spotify - Top Tracks...')

        # Reuse credentials pushed by collect_artists task (avoids second auth call)
        creds_xcom = context['task_instance'].xcom_pull(
            task_ids='collect_artists', key='spotify_creds'
        ) or {}
        client_id = creds_xcom.get('client_id') or os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = creds_xcom.get('client_secret') or os.getenv('SPOTIFY_CLIENT_SECRET')

        collector = SpotifyCollector(
            client_id=client_id,
            client_secret=client_secret
        )

        # ✅ Connexion à la base spotify_etl
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database='spotify_etl',  # ✅ Base correcte
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )

        # Honour the requested scope. `collect_spotify_artists` reads
        # `dag_run.conf['artist_id']`; this task did not, so a dashboard trigger
        # meaning "collect for artist 12" scoped the first task and ran the SECOND
        # over the entire catalogue — every tenant's top tracks fetched from the
        # Spotify API on every per-tenant click. The rows were attributed
        # correctly (each carries its tenant), so nothing leaked; what was wrong
        # is that the conf was carried and half-ignored, against the contract in
        # CLAUDE.md ("un déclenchement de DAG depuis le dashboard porte
        # conf={'artist_id': …}").
        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')
        # Import DANS la tâche (règle du repo : les DAGs n'importent rien de lourd au
        # parsing) et `run_id` pris ici, comme dans `collect_spotify_artists` — sans
        # eux, la branche « ce locataire n'a rien remonté » ci-dessous lèverait un
        # NameError au lieu de journaliser, c'est-à-dire remplacerait une alerte
        # inexacte par un plantage.
        from src.utils.dag_run_logger import record_tenant_failure
        run_id = context.get('run_id', '') if context else ''

        if artist_id_conf:
            artists = db.fetch_query(
                "SELECT spotify_artist_id FROM saas_artists "
                "WHERE id = %s AND active = TRUE "
                "AND spotify_artist_id IS NOT NULL AND spotify_artist_id <> ''",
                (artist_id_conf,)
            )
            if not artists:
                # Not an error worth failing the task: an active tenant that has
                # not declared a Spotify id simply has nothing to collect. Saying
                # WHICH tenant is what turns this into an actionable line.
                logger.warning(
                    f'⚠️ artist_id={artist_id_conf} : aucun spotify_artist_id déclaré '
                    '(ou artiste inactif) — rien à collecter pour ce locataire.'
                )
                db.close()
                return 0
        else:
            artists = db.fetch_query("SELECT artist_id FROM artists")

        if not artists:
            logger.warning('⚠️ Aucun artiste trouvé en base. Lancez d\'abord collect_artists.')
            db.close()
            return 0

        total_tracks = 0
        popularity_records = []

        # ✅ CORRECTION : Utiliser date() depuis datetime
        current_datetime = datetime.now()
        current_date = date.today()  # ✅ Changement ici

        for (artist_id,) in artists:
            logger.info(f'🎵 Top tracks pour artiste: {artist_id}')

            try:
                # Récupérer top tracks
                tracks = collector.get_artist_top_tracks(artist_id)

                if tracks:
                    # Resolve the SaaS tenant for this Spotify artist (migration 039).
                    # Stamp every track so dashboard readers can filter by tenant.
                    # Le run SCOPÉ tranche la propriété à lui seul : on collecte
                    # POUR ce locataire, il n'y a rien à deviner. Sans cette
                    # branche, un run scopé sur le bac à sable était refusé pour
                    # « propriété ambiguë » alors que l'appelant venait de nommer
                    # le propriétaire.
                    if artist_id_conf:
                        saas_artist_id = artist_id_conf
                    else:
                        # Les bacs à sable sont EXCLUS du calcul d'ambiguïté.
                        #
                        # Défaut de prod du 2026-09-04, remonté par une alerte : le
                        # bac à sable (locataire 18) porte, par construction,
                        # l'identifiant Spotify de l'exploitant — c'est sa raison
                        # d'être (migration 080), et `find_identity_conflict`
                        # l'exempte explicitement pour qu'il le puisse. Ici, ce même
                        # partage était lu comme « deux locataires revendiquent cet
                        # id », la ligne était sautée, le compteur restait à zéro, et
                        # la tâche échouait en réveillant l'admin.
                        #
                        # Deux gardes écrits séparément se contredisaient : l'un
                        # autorise le partage, l'autre le refuse. C'est la classe
                        # `exempt-row-hides-others-conflict` du même jour, à
                        # l'envers — une exemption posée d'un côté et ignorée de
                        # l'autre. Un id porté par un vrai locataire ET un bac à
                        # sable n'est pas ambigu : le propriétaire est le vrai
                        # locataire.
                        #
                        # L'ambiguïté entre deux VRAIS locataires reste refusée : ce
                        # garde a été écrit parce que prendre le premier attribuait
                        # silencieusement un catalogue entier au mauvais compte.
                        _sa = db.fetch_query(
                            "SELECT id FROM saas_artists WHERE spotify_artist_id = %s "
                            "AND COALESCE(is_sandbox, FALSE) = FALSE ORDER BY id",
                            (artist_id,)
                        )
                        if len(_sa) > 1:
                            logger.error(
                                f'⚠️ Spotify id {artist_id} is claimed by {len(_sa)} tenants '
                                f'({[r[0] for r in _sa]}) — skipping, ownership is ambiguous. '
                                'Fix saas_artists.spotify_artist_id for the wrong one.'
                            )
                            continue
                        saas_artist_id = _sa[0][0] if _sa else None
                    if saas_artist_id is None:
                        logger.warning(
                            f'⚠️ No SaaS artist bridged to Spotify id {artist_id} '
                            '(saas_artists.spotify_artist_id) — tracks.saas_artist_id will be NULL.'
                        )
                    for track in tracks:
                        track['saas_artist_id'] = saas_artist_id

                    # Stocker dans DB
                    count = db.upsert_many(
                        table='tracks',
                        data=tracks,
                        conflict_columns=['track_id'],
                        # saas_artist_id excluded: a track collected by two tenants
                        # (a collab, or the same Spotify id entered twice) was being
                        # re-assigned to whichever ran last, emptying the other's view.
                        update_columns=[
                            'track_name', 'popularity', 'duration_ms',
                            'album_name', 'release_date', 'collected_at'
                        ]
                    )

                    total_tracks += count
                    logger.info(f'✅ {count} tracks collectées')

                    # Préparer l'historique de popularité.
                    # artist_id est EXPLICITE : `track_popularity_history.artist_id`
                    # porte `DEFAULT 1`, et upsert_many dérive les colonnes de
                    # l'INSERT des clés du payload (postgres_handler.py). Omettre la
                    # clé faisait donc écrire l'historique de CHAQUE locataire sous
                    # l'artiste 1 (l'admin), tous les jours, sans erreur ni alerte.
                    if saas_artist_id is None:
                        # Aucun locataire n'est rattaché à cet artiste Spotify : la
                        # ligne n'a pas de propriétaire. On ne l'invente pas — c'est
                        # exactement ce que faisait le DEFAULT 1.
                        logger.warning(
                            f'⚠️ Historique popularité ignoré pour Spotify id {artist_id} '
                            '— aucun locataire rattaché (saas_artists.spotify_artist_id).'
                        )
                    else:
                        for track in tracks:
                            popularity_records.append({
                                'artist_id': saas_artist_id,
                                'track_id': track['track_id'],
                                'track_name': track['track_name'],
                                'popularity': track['popularity'],
                                'collected_at': current_datetime,
                                'date': current_date
                            })
            except Exception as e:
                # Per-artist isolation: a single bad Spotify ID / API error must not abort
                # top-tracks collection for the other tenants.
                logger.error(f'  Spotify top-tracks failed for {artist_id}: {safe_error(e)}')
                continue

        # Stocker l'historique de popularité
        if popularity_records:
            logger.info(f'📊 Stockage historique popularité: {len(popularity_records)} enregistrements...')

            try:
                pop_count = db.upsert_many(
                    table='track_popularity_history',
                    data=popularity_records,
                    conflict_columns=['artist_id', 'track_id', 'date'],
                    update_columns=['track_name', 'popularity', 'collected_at']
                )

                logger.info(f'✅ {pop_count} enregistrements d\'historique stockés')
                logger.info(f'📅 Date enregistrée: {current_date}')

            except Exception as e:
                logger.error(f'❌ Erreur stockage historique popularité: {safe_error(e)}')
                import traceback
                logger.error(traceback.format_exc())
                raise
        else:
            logger.warning('⚠️ Aucun enregistrement de popularité à stocker')

        db.close()

        if artists and total_tracks == 0:
            # Le message nommait `SPOTIFY_ARTIST_IDS`, et c'était deux fois faux.
            #
            # 1. Cette variable DOIT être vide en multi-locataire — `tools/
            #    check_env_parity.py::_MUST_BE_EMPTY` la surveille pour cette raison :
            #    renseignée, elle réarme la fuite de locataire du 2026-08-20. L'alerte
            #    envoyait donc son lecteur remplir un champ dont le remplissage est le
            #    défaut. Une alerte doit nommer un symptôme ET une action (ADR-011) ;
            #    celle-ci nommait une action nuisible.
            # 2. Elle ne disait NI quel locataire NI quel identifiant Spotify, alors
            #    que la boucle vient de les parcourir. « 0 tracks from 1 artist(s) »
            #    n'est actionnable par personne.
            #
            # Et la sévérité dépend de la PORTÉE du run, ce que le code ignorait :
            #   * run de flotte, zéro titre partout ⇒ c'est l'API ou l'app centrale,
            #     donc une vraie panne d'infrastructure : on lève, l'admin est alerté.
            #   * run scopé sur UN locataire (le cas d'un enregistrement de
            #     credentials depuis le dashboard) ⇒ c'est SON identifiant qui ne rend
            #     rien. Faire échouer la tâche transforme le problème d'un artiste en
            #     alerte d'infra, et le seul destinataire utile — l'artiste — n'en voit
            #     rien. On journalise son échec, qu'il lit dans sa matrice d'état.
            _ids = ", ".join(str(a[0]) for a in artists[:5])
            detail = (f"Spotify n'a renvoyé aucun titre pour : {_ids}"
                      + (" …" if len(artists) > 5 else ""))
            if artist_id_conf:
                logger.warning(
                    "⚠️ %s — locataire %s. Identifiant d'artiste probablement faux, "
                    "profil sans titre public, ou artiste inconnu de Spotify. "
                    "La tâche n'échoue pas : c'est le réglage de CE locataire.",
                    detail, artist_id_conf)
                record_tenant_failure(
                    'spotify_api_daily', artist_id_conf, 'spotify',
                    'ValueError',
                    "Spotify ne renvoie aucun titre pour cet identifiant d'artiste — "
                    "vérifie le lien de ta page Spotify Artist.",
                    run_id)
                db.close()
                return 0
            raise ValueError(
                f"{detail}. Aucun titre pour AUCUN des {len(artists)} artistes : "
                "c'est l'app Spotify centrale ou l'API qui ne répond pas, pas un "
                "identifiant d'artiste. Vérifier SPOTIFY_CLIENT_ID / "
                "SPOTIFY_CLIENT_SECRET et l'état de l'API Spotify."
            )

        logger.info(f'✅ Total: {total_tracks} tracks collectées')
        logger.info(f'✅ Total: {len(popularity_records)} enregistrements de popularité créés')
        return total_tracks

    except Exception as e:
        logger.error(f'❌ Erreur collecte tracks: {safe_error(e)}')
        import traceback
        traceback.print_exc()
        raise


with DAG(
    'spotify_api_daily',
    default_args=default_args,
    description='Collecte quotidienne Spotify API (artistes + tracks + historique popularité)',
    schedule='0 7 * * *',  # Daily 07:00 UTC (09:00 Paris)
    start_date=datetime(2025, 1, 20),
    catchup=False,
    dagrun_timeout=dagrun_timeout_for('spotify_api_daily'),
    max_active_runs=1,  # serialize external-API collection to avoid rate limits
    tags=['spotify', 'api', 'production'],
) as dag:

    # Tâche 1: Collecter les artistes
    collect_artists_task = PythonOperator(
        task_id='collect_artists',
        python_callable=collect_spotify_artists,
    )

    # Tâche 2: Collecter les top tracks + historique popularité
    collect_tracks_task = PythonOperator(
        task_id='collect_top_tracks',
        python_callable=collect_spotify_top_tracks,
    )

    # Définir l'ordre d'exécution
    collect_artists_task >> collect_tracks_task
