"""Script pour afficher les logs du DAG youtube_daily."""
import subprocess
import sys
from datetime import datetime

print("\n" + "="*70)
print("📋 LOGS AIRFLOW - youtube_daily")
print("="*70 + "\n")

# Commande pour lister les dossiers de logs
list_cmd = [
    'docker', 'exec', 'airflow_scheduler',
    'ls', '-lt', '/opt/airflow/logs/youtube_daily/collect_youtube_data/'
]

try:
    print("🔍 Recherche des exécutions...")
    result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        
        # Trouver la dernière exécution
        dirs = [line.split()[-1] for line in lines[1:] if line.strip()]
        
        if dirs:
            latest_run = dirs[0]
            print(f"✅ Dernière exécution: {latest_run}\n")
            print("="*70)
            print("📄 CONTENU DU LOG:")
            print("="*70 + "\n")
            
            # Lire le log
            log_cmd = [
                'docker', 'exec', 'airflow_scheduler',
                'cat', f'/opt/airflow/logs/youtube_daily/collect_youtube_data/{latest_run}/1.log'
            ]
            
            log_result = subprocess.run(log_cmd, capture_output=True, text=True, timeout=10)
            
            if log_result.returncode == 0:
                print(log_result.stdout)
            else:
                print(f"❌ Impossible de lire le log: {log_result.stderr}")
        else:
            print("⚠️  Aucune exécution trouvée")
    else:
        print(f"❌ Erreur lors de la liste des logs: {result.stderr}")

except subprocess.TimeoutExpired:
    print("❌ Timeout - Le container ne répond pas")
except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n" + "="*70)
print("💡 COMMANDE MANUELLE:")
print("="*70)
print("\ndocker exec -it airflow_scheduler bash")
print("cd /opt/airflow/logs/youtube_daily/collect_youtube_data")
print("ls -lt")
print("cat [date]/1.log")
print("\n" + "="*70 + "\n")