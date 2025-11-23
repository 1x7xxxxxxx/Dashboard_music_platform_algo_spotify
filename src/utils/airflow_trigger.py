"""Utilitaire pour déclencher les DAGs Airflow depuis Streamlit."""
import requests
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class AirflowTrigger:
    """Classe pour déclencher les DAGs Airflow via l'API REST."""
    
    def __init__(self, base_url: str = "http://localhost:8080", 
                 username: str = "admin", password: str = "admin"):
        """
        Initialise le trigger Airflow.
        
        Args:
            base_url: URL de base d'Airflow
            username: Nom d'utilisateur Airflow
            password: Mot de passe Airflow
        """
        self.base_url = base_url.rstrip('/')
        self.auth = (username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
        logger.info(f"✅ AirflowTrigger initialisé: {base_url}")
    
    def trigger_dag(self, dag_id: str, conf: Optional[Dict] = None) -> Dict:
        """
        Déclenche un DAG Airflow.
        
        Args:
            dag_id: ID du DAG à déclencher
            conf: Configuration optionnelle à passer au DAG
            
        Returns:
            Dict avec le résultat (success, message, dag_run_id)
        """
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns"
        
        payload = {
            "conf": conf or {}
        }
        
        try:
            logger.info(f"🚀 Déclenchement du DAG: {dag_id}")
            
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                dag_run_id = data.get('dag_run_id', 'unknown')
                
                logger.info(f"✅ DAG {dag_id} déclenché: {dag_run_id}")
                
                return {
                    'success': True,
                    'dag': dag_id,
                    'dag_run_id': dag_run_id,
                    'message': f"DAG {dag_id} déclenché avec succès"
                }
            
            else:
                error_msg = f"Erreur HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg = error_detail.get('detail', error_msg)
                except:
                    error_msg = response.text[:200]
                
                logger.error(f"❌ Échec déclenchement {dag_id}: {error_msg}")
                
                return {
                    'success': False,
                    'dag': dag_id,
                    'error': error_msg,
                    'message': f"Échec du déclenchement de {dag_id}"
                }
        
        except requests.exceptions.Timeout:
            error_msg = "Timeout de connexion à Airflow"
            logger.error(f"❌ {error_msg}")
            
            return {
                'success': False,
                'dag': dag_id,
                'error': error_msg,
                'message': f"Timeout lors du déclenchement de {dag_id}"
            }
        
        except requests.exceptions.ConnectionError:
            error_msg = "Impossible de se connecter à Airflow"
            logger.error(f"❌ {error_msg}")
            
            return {
                'success': False,
                'dag': dag_id,
                'error': error_msg,
                'message': f"Connexion à Airflow impossible"
            }
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Erreur inattendue pour {dag_id}: {error_msg}")
            
            return {
                'success': False,
                'dag': dag_id,
                'error': error_msg,
                'message': f"Erreur lors du déclenchement de {dag_id}"
            }
    
    def trigger_all_dags(self) -> List[Dict]:
        """
        Déclenche tous les DAGs de production.
        
        Returns:
            Liste de dicts avec les résultats de chaque DAG
        """
        dags = [
            'meta_ads_daily_docker',
            'spotify_api_daily',
            's4a_csv_watcher',
            'apple_music_csv_watcher',
            'youtube_daily',
            'data_quality_check',
        ]
        
        results = []
        
        logger.info(f"🚀 Déclenchement de {len(dags)} DAGs...")
        
        for dag_id in dags:
            result = self.trigger_dag(dag_id)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        logger.info(f"✅ {success_count}/{len(dags)} DAGs déclenchés avec succès")
        
        return results
    
    def get_dag_status(self, dag_id: str) -> Dict:
        """
        Récupère le statut d'un DAG.
        
        Args:
            dag_id: ID du DAG
            
        Returns:
            Dict avec le statut du DAG
        """
        url = f"{self.base_url}/api/v1/dags/{dag_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'success': True,
                    'dag': dag_id,
                    'is_paused': data.get('is_paused', True),
                    'is_active': data.get('is_active', False),
                    'last_parsed_time': data.get('last_parsed_time'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'dag': dag_id,
                    'error': f"HTTP {response.status_code}"
                }
        
        except Exception as e:
            return {
                'success': False,
                'dag': dag_id,
                'error': str(e)
            }
    
    def get_last_dag_run(self, dag_id: str) -> Optional[Dict]:
        """
        Récupère la dernière exécution d'un DAG.
        
        Args:
            dag_id: ID du DAG
            
        Returns:
            Dict avec les infos de la dernière exécution, ou None
        """
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns"
        
        try:
            response = self.session.get(
                url,
                params={'limit': 1, 'order_by': '-execution_date'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                dag_runs = data.get('dag_runs', [])
                
                if dag_runs:
                    last_run = dag_runs[0]
                    
                    return {
                        'dag_run_id': last_run.get('dag_run_id'),
                        'state': last_run.get('state'),
                        'execution_date': last_run.get('execution_date'),
                        'start_date': last_run.get('start_date'),
                        'end_date': last_run.get('end_date')
                    }
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Erreur get_last_dag_run pour {dag_id}: {e}")
            return None
    
    def check_connection(self) -> bool:
        """
        Vérifie la connexion à Airflow.
        
        Returns:
            True si la connexion fonctionne, False sinon
        """
        url = f"{self.base_url}/api/v1/health"
        
        try:
            response = self.session.get(url, timeout=5)
            
            if response.status_code == 200:
                logger.info("✅ Connexion à Airflow OK")
                return True
            else:
                logger.warning(f"⚠️ Airflow répond avec code {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Connexion à Airflow impossible: {e}")
            return False


# Test
if __name__ == "__main__":
    trigger = AirflowTrigger()
    
    # Test de connexion
    print("\n🔍 Test de connexion...")
    if trigger.check_connection():
        print("✅ Connexion OK\n")
        
        # Test déclenchement d'un DAG
        print("🚀 Test déclenchement meta_ads_daily_docker...")
        result = trigger.trigger_dag('meta_ads_daily_docker')
        
        if result['success']:
            print(f"✅ {result['message']}")
            print(f"   DAG Run ID: {result['dag_run_id']}")
        else:
            print(f"❌ {result['message']}")
            print(f"   Erreur: {result['error']}")
    else:
        print("❌ Impossible de se connecter à Airflow")
        print("   Vérifiez que Airflow est démarré sur http://localhost:8080")