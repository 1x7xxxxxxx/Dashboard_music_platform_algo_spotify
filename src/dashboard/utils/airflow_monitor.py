import requests
import pandas as pd
from datetime import datetime, timedelta
from src.utils.config_loader import config_loader
import os
from dotenv import load_dotenv

load_dotenv(override=True)

class AirflowMonitor:
    def __init__(self):
        config = config_loader.load()
        airflow_conf = config.get('airflow', {})
        
        raw_url = airflow_conf.get('base_url', 'http://localhost:8080').rstrip('/')
        if '/api/v1' not in raw_url:
            self.base_url = f"{raw_url}/api/v1"
        else:
            self.base_url = raw_url
            
        self.username = os.getenv('AIRFLOW_USERNAME')
        self.password = os.getenv('AIRFLOW_PASSWORD')
        
        # On utilise une session pour garder les cookies/auth
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)

    def get_dag_runs(self, limit=50):
        """Récupère les dernières exécutions de tous les DAGs."""
        try:
            # 1. Lister les DAGs actifs
            dags_resp = self.session.get(f"{self.base_url}/dags", params={'limit': 100})
            
            if dags_resp.status_code != 200:
                print(f"⚠️ Erreur API Liste DAGs: {dags_resp.status_code}")
                return pd.DataFrame()
                
            dags_data = dags_resp.json()
            dags = [d['dag_id'] for d in dags_data.get('dags', []) if not d.get('is_paused')]
            
            all_runs = []
            
            # 2. Récupérer les runs pour chaque DAG
            for dag_id in dags:
                runs_resp = self.session.get(
                    f"{self.base_url}/dags/{dag_id}/dagRuns",
                    params={'limit': 5, 'order_by': '-execution_date'}
                )
                
                if runs_resp.status_code == 200:
                    runs_data = runs_resp.json()
                    runs = runs_data.get('dag_runs', [])
                    
                    for r in runs:
                        # ✅ CORRECTION ICI : On gère les deux noms possibles
                        run_id = r.get('dag_run_id') or r.get('run_id') or 'unknown'
                        
                        start_str = r.get('start_date')
                        end_str = r.get('end_date')
                        state = r.get('state')
                        
                        if start_str:
                            start = pd.to_datetime(start_str)
                            end = pd.to_datetime(end_str) if end_str else datetime.now(start.tzinfo)
                            duration = (end - start).total_seconds()
                        else:
                            start = datetime.now()
                            duration = 0
                        
                        all_runs.append({
                            'dag_id': dag_id,
                            'run_id': run_id,
                            'state': state,
                            'start_date': start,
                            'end_date': r.get('end_date'), # On garde le format brut pour l'affichage si besoin
                            'duration_sec': duration
                        })
            
            return pd.DataFrame(all_runs)
            
        except Exception as e:
            print(f"🔥 Exception Airflow : {e}")
            return pd.DataFrame()

    def get_dag_list(self):
        """Retourne la liste de tous les DAGs (paused ou non)."""
        try:
            resp = self.session.get(f"{self.base_url}/dags", params={'limit': 100})
            if resp.status_code != 200:
                return []
            return sorted([d['dag_id'] for d in resp.json().get('dags', [])])
        except Exception:
            return []

    def get_runs_for_dag(self, dag_id: str, limit: int = 20):
        """Retourne les derniers runs d'un DAG donné."""
        try:
            resp = self.session.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns",
                params={'limit': limit, 'order_by': '-execution_date'}
            )
            if resp.status_code != 200:
                return []
            runs = resp.json().get('dag_runs', [])
            result = []
            for r in runs:
                run_id = r.get('dag_run_id') or r.get('run_id') or 'unknown'
                result.append({
                    'run_id': run_id,
                    'state': r.get('state', '?'),
                    'start_date': r.get('start_date', ''),
                    'end_date': r.get('end_date', ''),
                })
            return result
        except Exception:
            return []

    def get_task_instances(self, dag_id: str, run_id: str):
        """Retourne les task instances d'un dag run."""
        try:
            resp = self.session.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
            )
            if resp.status_code != 200:
                return []
            tasks = resp.json().get('task_instances', [])
            result = []
            for t in tasks:
                result.append({
                    'task_id': t.get('task_id'),
                    'state': t.get('state', '?'),
                    'start_date': t.get('start_date', ''),
                    'end_date': t.get('end_date', ''),
                    'try_number': t.get('try_number', 1),
                    'duration': t.get('duration'),
                })
            return result
        except Exception:
            return []

    def get_task_log(self, dag_id: str, run_id: str, task_id: str, attempt: int = 1):
        """Retourne le log texte d'une task instance."""
        try:
            resp = self.session.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{attempt}",
                headers={'Accept': 'text/plain'}
            )
            if resp.status_code == 200:
                return resp.text
            return f"[Erreur {resp.status_code}] Impossible de récupérer les logs."
        except Exception as e:
            return f"[Exception] {e}"

    def get_kpis(self):
        """Calcule les KPIs globaux."""
        df = self.get_dag_runs()
        
        if df.empty:
            return None
            
        # Sécurisation si la date est manquante
        if 'start_date' in df.columns and not df['start_date'].isnull().all():
            try:
                last_24h = datetime.now(df['start_date'].iloc[0].tzinfo) - timedelta(hours=24)
                df_24h = df[df['start_date'] >= last_24h]
            except:
                df_24h = df # Fallback
        else:
            df_24h = pd.DataFrame()
        
        total = len(df)
        success = len(df[df['state'] == 'success'])
        failed = len(df[df['state'] == 'failed'])
        rate = (success / total * 100) if total > 0 else 0
        
        failures = df[df['state'] == 'failed'].head(5)
        
        return {
            'total_runs_24h': len(df_24h),
            'success_rate': rate,
            'failed_count': failed,
            'recent_failures': failures,
            'raw_data': df
        }