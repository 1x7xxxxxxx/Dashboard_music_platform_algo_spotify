"""Module pour déclencher les DAGs Airflow depuis Streamlit via CLI Docker."""
import subprocess
import logging
from typing import Dict, List
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AirflowTrigger:
    """Classe pour déclencher des DAGs Airflow via CLI Docker."""
    
    def __init__(self, container_name: str = "dashboard_music_platform_algo_spotify-airflow-scheduler-1"):
        """
        Initialise le trigger Airflow.
        
        Args:
            container_name: Nom du container Airflow scheduler
        """
        self.container_name = container_name
        
        # Vérifier que le container existe
        self._verify_container()
    
    def _verify_container(self) -> bool:
        """Vérifie que le container Airflow existe."""
        try:
            cmd = ["docker", "ps", "--format", "{{.Names}}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if self.container_name in result.stdout:
                logger.info(f"✅ Container Airflow trouvé: {self.container_name}")
                return True
            else:
                logger.warning(f"⚠️  Container {self.container_name} introuvable")
                logger.info("Containers disponibles:")
                for line in result.stdout.split('\n'):
                    if 'airflow' in line.lower():
                        logger.info(f"   • {line}")
                return False
        except Exception as e:
            logger.error(f"❌ Erreur vérification container: {e}")
            return False
    
    def trigger_dag(self, dag_id: str, wait: bool = False) -> Dict:
        """
        Déclenche un DAG Airflow via CLI.
        
        Args:
            dag_id: Identifiant du DAG à déclencher
            wait: Si True, attend la fin de l'exécution (non implémenté pour CLI)
            
        Returns:
            Dict avec le résultat du déclenchement
        """
        try:
            logger.info(f"🚀 Déclenchement du DAG: {dag_id}")
            
            # Commande Docker pour déclencher le DAG
            cmd = [
                "docker", "exec",
                self.container_name,
                "airflow", "dags", "trigger", dag_id
            ]
            
            # Exécuter la commande
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                logger.info(f"✅ DAG {dag_id} déclenché avec succès")
                
                # Extraire le dag_run_id de la sortie
                dag_run_id = None
                for line in result.stdout.split('\n'):
                    if 'dag_run_id' in line.lower() or 'created' in line.lower():
                        dag_run_id = line.strip()
                        break
                
                return {
                    'success': True,
                    'dag_id': dag_id,
                    'dag_run_id': dag_run_id,
                    'message': 'DAG déclenché avec succès',
                    'output': result.stdout.strip()
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                logger.error(f"❌ Erreur déclenchement DAG {dag_id}")
                logger.error(f"   Code retour: {result.returncode}")
                logger.error(f"   Erreur: {error_msg}")
                
                return {
                    'success': False,
                    'dag_id': dag_id,
                    'error': error_msg,
                    'return_code': result.returncode
                }
        
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️  Timeout lors du déclenchement de {dag_id}")
            return {
                'success': False,
                'dag_id': dag_id,
                'error': 'Timeout (15s dépassé)'
            }
        except Exception as e:
            logger.error(f"❌ Exception lors du déclenchement de {dag_id}: {e}")
            return {
                'success': False,
                'dag_id': dag_id,
                'error': str(e)
            }
    
    def trigger_all_dags(self, wait: bool = False, delay: float = 1.0) -> Dict:
        """
        Déclenche tous les DAGs de collecte.
        
        Args:
            wait: Si True, attend la fin de chaque exécution
            delay: Délai en secondes entre chaque déclenchement
            
        Returns:
            Dict avec les résultats de tous les déclenchements
        """
        dags = [
            'meta_ads_daily_docker',
            'spotify_api_daily',
            's4a_csv_watcher',
        ]
        
        results = {}
        
        logger.info(f"🚀 Déclenchement de {len(dags)} DAGs...")
        
        for i, dag_id in enumerate(dags, 1):
            logger.info(f"\n[{i}/{len(dags)}] Traitement de {dag_id}...")
            
            result = self.trigger_dag(dag_id, wait=wait)
            results[dag_id] = result
            
            # Pause entre chaque déclenchement
            if i < len(dags):
                time.sleep(delay)
        
        # Résumé
        success_count = sum(1 for r in results.values() if r.get('success'))
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Résumé: {success_count}/{len(dags)} DAGs déclenchés avec succès")
        logger.info(f"{'='*60}")
        
        return results
    
    def list_dags(self) -> List[str]:
        """
        Liste tous les DAGs disponibles.
        
        Returns:
            Liste des IDs de DAGs
        """
        try:
            cmd = [
                "docker", "exec",
                self.container_name,
                "airflow", "dags", "list"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parser la sortie pour extraire les DAG IDs
                dags = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    # Ignorer les lignes vides et les headers
                    if line and not line.startswith('dag_id') and '---' not in line:
                        # Le premier mot est le dag_id
                        dag_id = line.split()[0] if line.split() else None
                        if dag_id:
                            dags.append(dag_id)
                
                logger.info(f"📋 {len(dags)} DAGs disponibles")
                return dags
            else:
                logger.error(f"❌ Erreur listage DAGs: {result.stderr}")
                return []
        
        except Exception as e:
            logger.error(f"❌ Exception listage DAGs: {e}")
            return []


# Instance globale pour utilisation facile
airflow_trigger = AirflowTrigger()


# Fonction helper pour Streamlit
def trigger_data_collection(show_progress: bool = True):
    """
    Déclenche la collecte de toutes les données.
    
    Args:
        show_progress: Afficher les messages de progression
        
    Returns:
        Dict avec les résultats
    """
    if show_progress:
        logger.info("🚀 Démarrage de la collecte de données...")
    
    results = airflow_trigger.trigger_all_dags(wait=False, delay=1.0)
    
    # Compter les succès
    success_count = sum(1 for r in results.values() if r.get('success'))
    total_count = len(results)
    
    if show_progress:
        if success_count == total_count:
            logger.info(f"🎉 Toutes les collectes lancées avec succès!")
        else:
            logger.warning(f"⚠️  {success_count}/{total_count} DAGs lancés")
    
    return {
        'success': success_count == total_count,
        'results': results,
        'summary': f"{success_count}/{total_count} DAGs lancés"
    }


# Script de test
if __name__ == "__main__":
    print("="*60)
    print("🧪 TEST AIRFLOW TRIGGER")
    print("="*60)
    
    # Test 1: Lister les DAGs
    print("\n1️⃣  Listage des DAGs disponibles...")
    dags = airflow_trigger.list_dags()
    if dags:
        print(f"✅ {len(dags)} DAGs trouvés:")
        for dag in dags:
            print(f"   • {dag}")
    else:
        print("❌ Aucun DAG trouvé")
    
    # Test 2: Déclencher un DAG
    print("\n2️⃣  Test déclenchement d'un DAG...")
    test_dag = input("Entrez le nom d'un DAG à tester (ou Entrée pour passer): ").strip()
    
    if test_dag:
        result = airflow_trigger.trigger_dag(test_dag)
        if result['success']:
            print(f"✅ DAG {test_dag} déclenché avec succès!")
        else:
            print(f"❌ Échec: {result.get('error')}")
    
    print("\n" + "="*60)
    print("✅ Tests terminés")
    print("="*60)