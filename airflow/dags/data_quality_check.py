"""
DAG Data Quality Check - Vérification qualité des données
Fréquence : Quotidienne à 22h00 (après toutes les collectes)
Description : Vérifie la fraîcheur et cohérence des données + génère stats
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import logging

# Ajouter le projet au path Python
sys.path.insert(0, '/opt/airflow')

# Charger les variables d'environnement
from dotenv import load_dotenv
load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

# Configuration par défaut du DAG
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,  # Mettre True si vous configurez SMTP
    'email_on_retry': False,
    'email': ['votre_email@example.com'],  # À configurer
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def check_meta_ads_freshness(**context):
    """
    Vérifie que les données Meta Ads ont été collectées récemment (< 48h).
    Lève une exception si données trop anciennes.
    """
    try:
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🔍 VÉRIFICATION FRAÎCHEUR DONNÉES META ADS')
        logger.info('='*70)
        
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Vérifier dernière collecte des campagnes
        query = """
            SELECT 
                MAX(collected_at) as last_collection,
                EXTRACT(EPOCH FROM (NOW() - MAX(collected_at))) / 3600 as hours_ago
            FROM meta_campaigns
        """
        
        result = db.fetch_query(query)
        
        if not result or not result[0][0]:
            logger.error('❌ Aucune donnée Meta Ads trouvée en base')
            db.close()
            raise ValueError('❌ CRITIQUE: Aucune collecte Meta Ads effectuée')
        
        last_collection, hours_ago = result[0]
        
        logger.info(f'📅 Dernière collecte: {last_collection}')
        logger.info(f'⏱️  Il y a: {hours_ago:.1f} heures')
        
        # Seuil d'alerte : 48h (2 jours)
        max_hours = 48
        
        if hours_ago > max_hours:
            logger.error(f'❌ ALERTE: Données trop anciennes ({hours_ago:.1f}h > {max_hours}h)')
            db.close()
            raise ValueError(f'❌ Données Meta Ads obsolètes: {hours_ago:.1f}h')
        
        # Compter les enregistrements récents
        count_query = "SELECT COUNT(*) FROM meta_campaigns WHERE status = 'ACTIVE'"
        active_count = db.fetch_query(count_query)[0][0]
        
        logger.info(f'✅ {active_count} campagne(s) active(s)')
        
        db.close()
        
        logger.info('✅ Données Meta Ads à jour')
        logger.info('='*70 + '\n')
        
        return {
            'last_collection': str(last_collection),
            'hours_ago': round(hours_ago, 2),
            'active_campaigns': active_count
        }
        
    except Exception as e:
        logger.error(f'❌ Erreur vérification Meta Ads: {e}')
        raise


def check_spotify_data_consistency(**context):
    """
    Vérifie la cohérence et qualité des données Spotify.
    Détecte les anomalies et incohérences.
    """
    try:
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🔍 VÉRIFICATION COHÉRENCE DONNÉES SPOTIFY')
        logger.info('='*70)
        
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        issues = []
        warnings = []
        
        # ====== CHECK 1: Artistes sans tracks ======
        logger.info('\n📊 Check 1: Artistes sans tracks...')
        
        query_orphan_artists = """
            SELECT a.artist_id, a.name
            FROM artists a
            LEFT JOIN tracks t ON a.artist_id = t.artist_id
            WHERE t.track_id IS NULL
        """
        
        orphan_artists = db.fetch_query(query_orphan_artists)
        
        if orphan_artists:
            issue = f'⚠️  {len(orphan_artists)} artiste(s) sans tracks'
            warnings.append(issue)
            logger.warning(issue)
            for artist_id, name in orphan_artists[:5]:  # Afficher max 5
                logger.warning(f'   • {name} ({artist_id})')
        else:
            logger.info('✅ Tous les artistes ont des tracks')
        
        # ====== CHECK 2: Cohérence S4A Timeline vs Global ======
        logger.info('\n📊 Check 2: Cohérence S4A Timeline...')
        
        query_missing_songs = """
            SELECT DISTINCT song
            FROM s4a_song_timeline
            WHERE song NOT IN (SELECT song FROM s4a_songs_global)
            LIMIT 10
        """
        
        missing_songs = db.fetch_query(query_missing_songs)
        
        if missing_songs:
            issue = f'⚠️  {len(missing_songs)} chanson(s) dans timeline mais pas dans songs_global'
            warnings.append(issue)
            logger.warning(issue)
            for (song,) in missing_songs[:5]:
                logger.warning(f'   • {song}')
        else:
            logger.info('✅ Cohérence Timeline/Global OK')
        
        # ====== CHECK 3: Valeurs aberrantes S4A ======
        logger.info('\n📊 Check 3: Détection valeurs aberrantes...')
        
        query_suspicious_streams = """
            SELECT song, date, streams
            FROM s4a_song_timeline
            WHERE streams > 1000000  -- Plus de 1M streams en 1 jour
            ORDER BY streams DESC
            LIMIT 5
        """
        
        suspicious = db.fetch_query(query_suspicious_streams)
        
        if suspicious:
            issue = f'ℹ️  {len(suspicious)} jour(s) avec streams très élevés (> 1M)'
            warnings.append(issue)
            logger.info(issue)
            for song, date, streams in suspicious:
                logger.info(f'   • {song} le {date}: {streams:,} streams')
        else:
            logger.info('✅ Pas de valeurs aberrantes détectées')
        
        # ====== CHECK 4: Trous dans timeline S4A ======
        logger.info('\n📊 Check 4: Vérification continuité timeline...')
        
        query_gaps = """
            SELECT song, COUNT(*) as days_count
            FROM s4a_song_timeline
            GROUP BY song
            HAVING COUNT(*) < 7  -- Moins de 7 jours de données
            ORDER BY days_count ASC
            LIMIT 10
        """
        
        gaps = db.fetch_query(query_gaps)
        
        if gaps:
            issue = f'⚠️  {len(gaps)} chanson(s) avec moins de 7 jours de données'
            warnings.append(issue)
            logger.warning(issue)
            for song, days in gaps[:5]:
                logger.warning(f'   • {song}: seulement {days} jour(s)')
        else:
            logger.info('✅ Toutes les chansons ont suffisamment de données')
        
        # ====== CHECK 5: Données dupliquées ======
        logger.info('\n📊 Check 5: Détection doublons...')
        
        query_duplicates = """
            SELECT song, date, COUNT(*) as count
            FROM s4a_song_timeline
            GROUP BY song, date
            HAVING COUNT(*) > 1
            LIMIT 5
        """
        
        duplicates = db.fetch_query(query_duplicates)
        
        if duplicates:
            issue = f'❌ {len(duplicates)} doublon(s) détecté(s) dans timeline'
            issues.append(issue)
            logger.error(issue)
            for song, date, count in duplicates:
                logger.error(f'   • {song} le {date}: {count} entrées')
        else:
            logger.info('✅ Pas de doublons détectés')
        
        db.close()
        
        # ====== RÉSUMÉ ======
        logger.info('\n' + '='*70)
        logger.info('📊 RÉSUMÉ VÉRIFICATION QUALITÉ')
        logger.info('='*70)
        
        if issues:
            logger.error(f'❌ {len(issues)} problème(s) CRITIQUE(S):')
            for issue in issues:
                logger.error(f'   {issue}')
        
        if warnings:
            logger.warning(f'⚠️  {len(warnings)} avertissement(s):')
            for warning in warnings:
                logger.warning(f'   {warning}')
        
        if not issues and not warnings:
            logger.info('✅ Aucun problème de qualité détecté')
        
        logger.info('='*70 + '\n')
        
        # Pousser les résultats dans XCom
        context['task_instance'].xcom_push(
            key='quality_issues',
            value={'issues': issues, 'warnings': warnings}
        )
        
        # Lever une exception si problèmes critiques
        if issues:
            raise ValueError(f'❌ {len(issues)} problème(s) critique(s) détecté(s)')
        
        return {
            'issues_count': len(issues),
            'warnings_count': len(warnings)
        }
        
    except Exception as e:
        logger.error(f'❌ Erreur vérification cohérence: {e}')
        raise


def generate_daily_stats(**context):
    """
    Génère des statistiques quotidiennes globales.
    Synthèse de toutes les données collectées.
    """
    try:
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('📊 GÉNÉRATION STATISTIQUES QUOTIDIENNES')
        logger.info('='*70)
        
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        stats = {}
        
        # ====== META ADS - Stats dernières 24h ======
        logger.info('\n📱 Meta Ads - Dernières 24h:')
        
        query_meta = """
            SELECT 
                COUNT(DISTINCT i.ad_id) as active_ads,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(spend), 0) as total_spend,
                COALESCE(SUM(conversions), 0) as total_conversions,
                CASE 
                    WHEN SUM(impressions) > 0 
                    THEN ROUND((SUM(clicks)::numeric / SUM(impressions)::numeric) * 100, 2)
                    ELSE 0 
                END as ctr
            FROM meta_insights i
            WHERE date >= CURRENT_DATE - INTERVAL '1 day'
        """
        
        meta_result = db.fetch_query(query_meta)
        
        if meta_result and meta_result[0]:
            stats['meta_ads'] = {
                'active_ads': meta_result[0][0] or 0,
                'impressions': int(meta_result[0][1] or 0),
                'clicks': int(meta_result[0][2] or 0),
                'spend': float(meta_result[0][3] or 0),
                'conversions': int(meta_result[0][4] or 0),
                'ctr': float(meta_result[0][5] or 0)
            }
            
            logger.info(f"   • Ads actives: {stats['meta_ads']['active_ads']}")
            logger.info(f"   • Impressions: {stats['meta_ads']['impressions']:,}")
            logger.info(f"   • Clicks: {stats['meta_ads']['clicks']:,}")
            logger.info(f"   • Dépenses: {stats['meta_ads']['spend']:.2f} €")
            logger.info(f"   • CTR: {stats['meta_ads']['ctr']:.2f}%")
        
        # ====== SPOTIFY API - Stats artistes ======
        logger.info('\n🎸 Spotify API - Artistes:')
        
        query_spotify = """
            SELECT 
                COUNT(*) as total_artists,
                COALESCE(SUM(followers), 0) as total_followers,
                ROUND(AVG(popularity), 2) as avg_popularity,
                MAX(followers) as max_followers
            FROM artists
        """
        
        spotify_result = db.fetch_query(query_spotify)
        
        if spotify_result and spotify_result[0]:
            stats['spotify_api'] = {
                'total_artists': spotify_result[0][0] or 0,
                'total_followers': int(spotify_result[0][1] or 0),
                'avg_popularity': float(spotify_result[0][2] or 0),
                'max_followers': int(spotify_result[0][3] or 0)
            }
            
            logger.info(f"   • Artistes suivis: {stats['spotify_api']['total_artists']}")
            logger.info(f"   • Followers totaux: {stats['spotify_api']['total_followers']:,}")
            logger.info(f"   • Popularité moyenne: {stats['spotify_api']['avg_popularity']:.1f}/100")
        
        # Nombre de tracks
        count_tracks = db.fetch_query("SELECT COUNT(*) FROM tracks")[0][0]
        stats['spotify_api']['total_tracks'] = count_tracks
        logger.info(f"   • Tracks collectées: {count_tracks}")
        
        # ====== SPOTIFY FOR ARTISTS - Stats dernières 24h ======
        logger.info('\n🎵 Spotify for Artists - Dernières 24h:')
        
        query_s4a = """
            SELECT 
                COALESCE(SUM(streams), 0) as total_streams,
                COALESCE(SUM(listeners), 0) as total_listeners,
                COALESCE(MAX(followers), 0) as current_followers
            FROM s4a_audience
            WHERE date >= CURRENT_DATE - INTERVAL '1 day'
        """
        
        s4a_result = db.fetch_query(query_s4a)
        
        if s4a_result and s4a_result[0]:
            stats['s4a'] = {
                'streams_24h': int(s4a_result[0][0] or 0),
                'listeners_24h': int(s4a_result[0][1] or 0),
                'current_followers': int(s4a_result[0][2] or 0)
            }
            
            logger.info(f"   • Streams: {stats['s4a']['streams_24h']:,}")
            logger.info(f"   • Listeners: {stats['s4a']['listeners_24h']:,}")
            logger.info(f"   • Followers actuels: {stats['s4a']['current_followers']:,}")
        
        # Nombre de chansons suivies
        count_songs = db.fetch_query("SELECT COUNT(*) FROM s4a_songs_global")[0][0]
        stats['s4a']['total_songs'] = count_songs
        logger.info(f"   • Chansons suivies: {count_songs}")
        
        db.close()
        
        # ====== RÉSUMÉ GLOBAL ======
        logger.info('\n' + '='*70)
        logger.info('✅ STATISTIQUES QUOTIDIENNES GÉNÉRÉES')
        logger.info('='*70)
        
        # Pousser les stats dans XCom
        context['task_instance'].xcom_push(key='daily_stats', value=stats)
        
        return stats
        
    except Exception as e:
        logger.error(f'❌ Erreur génération statistiques: {e}')
        import traceback
        logger.error(traceback.format_exc())
        raise


def send_summary_notification(**context):
    """
    Envoie un résumé quotidien (optionnel, peut être étendu avec email/Slack).
    Pour l'instant, log seulement un résumé.
    """
    try:
        logger.info('='*70)
        logger.info('📧 RÉSUMÉ QUOTIDIEN')
        logger.info('='*70)
        
        # Récupérer les stats depuis XCom
        stats = context['task_instance'].xcom_pull(
            task_ids='generate_daily_stats',
            key='daily_stats'
        )
        
        quality_check = context['task_instance'].xcom_pull(
            task_ids='check_spotify_consistency',
            key='quality_issues'
        )
        
        # Construire le message de résumé
        summary_lines = []
        summary_lines.append('\n🎯 RÉSUMÉ QUOTIDIEN - MUSIC PLATFORM DASHBOARD')
        summary_lines.append(f'📅 Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        summary_lines.append('='*70)
        
        # Meta Ads
        if stats and 'meta_ads' in stats:
            meta = stats['meta_ads']
            summary_lines.append('\n📱 META ADS (24h):')
            summary_lines.append(f'   • Impressions: {meta["impressions"]:,}')
            summary_lines.append(f'   • Clicks: {meta["clicks"]:,}')
            summary_lines.append(f'   • Dépenses: {meta["spend"]:.2f} €')
            summary_lines.append(f'   • CTR: {meta["ctr"]:.2f}%')
        
        # Spotify API
        if stats and 'spotify_api' in stats:
            spotify = stats['spotify_api']
            summary_lines.append('\n🎸 SPOTIFY API:')
            summary_lines.append(f'   • Artistes: {spotify["total_artists"]}')
            summary_lines.append(f'   • Tracks: {spotify["total_tracks"]}')
            summary_lines.append(f'   • Followers totaux: {spotify["total_followers"]:,}')
        
        # Spotify for Artists
        if stats and 's4a' in stats:
            s4a = stats['s4a']
            summary_lines.append('\n🎵 SPOTIFY FOR ARTISTS (24h):')
            summary_lines.append(f'   • Streams: {s4a["streams_24h"]:,}')
            summary_lines.append(f'   • Listeners: {s4a["listeners_24h"]:,}')
            summary_lines.append(f'   • Followers: {s4a["current_followers"]:,}')
        
        # Qualité des données
        if quality_check:
            issues_count = len(quality_check.get('issues', []))
            warnings_count = len(quality_check.get('warnings', []))
            
            summary_lines.append('\n🔍 QUALITÉ DES DONNÉES:')
            if issues_count > 0:
                summary_lines.append(f'   ❌ {issues_count} problème(s) critique(s)')
            if warnings_count > 0:
                summary_lines.append(f'   ⚠️  {warnings_count} avertissement(s)')
            if issues_count == 0 and warnings_count == 0:
                summary_lines.append('   ✅ Aucun problème détecté')
        
        summary_lines.append('\n' + '='*70)
        
        # Afficher le résumé dans les logs
        summary = '\n'.join(summary_lines)
        logger.info(summary)
        
        # TODO: Implémenter l'envoi par email ou Slack ici
        # Exemple avec email (si SMTP configuré):
        # send_email(to=os.getenv('ALERT_EMAIL'), subject='Résumé quotidien', body=summary)
        
        logger.info('✅ Résumé quotidien généré')
        
        return summary
        
    except Exception as e:
        logger.error(f'❌ Erreur génération résumé: {e}')
        # Ne pas faire échouer le DAG pour ça
        return None


# Définition du DAG
with DAG(
    dag_id='data_quality_check',
    default_args=default_args,
    description='🔍 Vérification quotidienne qualité des données + statistiques',
    schedule_interval=None,  # Tous les jours à 22h00 (après collectes)
    start_date=datetime(2025, 1, 20),
    catchup=False,  # Ne pas rattraper les exécutions passées
    tags=['quality', 'monitoring', 'statistics', 'production'],
    max_active_runs=1,  # Une seule exécution à la fois
) as dag:
    
    # Tâche 1: Vérifier fraîcheur Meta Ads (données < 48h)
    check_meta_task = PythonOperator(
        task_id='check_meta_ads_freshness',
        python_callable=check_meta_ads_freshness,
        provide_context=True,
    )
    
    # Tâche 2: Vérifier cohérence données Spotify
    check_spotify_task = PythonOperator(
        task_id='check_spotify_consistency',
        python_callable=check_spotify_data_consistency,
        provide_context=True,
    )
    
    # Tâche 3: Générer statistiques quotidiennes
    generate_stats_task = PythonOperator(
        task_id='generate_daily_stats',
        python_callable=generate_daily_stats,
        provide_context=True,
    )
    
    # Tâche 4: Envoyer résumé quotidien
    send_summary_task = PythonOperator(
        task_id='send_summary_notification',
        python_callable=send_summary_notification,
        provide_context=True,
        trigger_rule='all_done',  # S'exécute même si vérifications échouent
    )
    
    # Définir le flux d'exécution
    # Les checks s'exécutent en parallèle, puis stats, puis résumé
    [check_meta_task, check_spotify_task] >> generate_stats_task >> send_summary_task


    # Dans data_quality_check.py

def send_quality_alert(**context):
    from src.utils.email_alerts import EmailAlert
    
    quality_check = context['task_instance'].xcom_pull(
        task_ids='check_spotify_consistency',
        key='quality_issues'
    )
    
    if quality_check['issues']:
        alert = EmailAlert()
        body = f"""
        <h2>⚠️ Problèmes de qualité détectés</h2>
        <ul>
        {''.join([f'<li>{issue}</li>' for issue in quality_check['issues']])}
        </ul>
        """
        alert.send_alert('Qualité des données', body)