import requests
from concurrent.futures import ThreadPoolExecutor
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

        # Env-first (prod containers have no config.yaml): the dashboard reaches Airflow
        # via the compose service name (AIRFLOW_BASE_URL=http://airflow-webserver:8080),
        # NOT localhost — localhost in the dashboard container is not the Airflow box, so
        # the config.yaml-only default silently failed in prod ("Aucun DAG trouvé").
        raw_url = (
            os.getenv('AIRFLOW_BASE_URL')
            or airflow_conf.get('base_url', 'http://localhost:8080')
        ).rstrip('/')
        if '/api/v1' not in raw_url:
            self.base_url = f"{raw_url}/api/v1"
        else:
            self.base_url = raw_url

        self.username = os.getenv('AIRFLOW_USERNAME')
        self.password = os.getenv('AIRFLOW_PASSWORD')

        # On utilise une session pour garder les cookies/auth
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)

    def _runs_per_dag(self, dag_ids: list[str], limit: int) -> dict:
        """`{dag_id: [raw dag_run, ...]}` — one request per DAG, run concurrently.

        The single place that knows how to ask Airflow for runs across many DAGs, so
        the next caller inherits both the correctness and the concurrency instead of
        re-deriving them. Measured against production on 2026-08-30: 16 DAGs in
        **440 ms at 8 workers**, against 1315 ms sequentially.

        8 workers, not 16: past 8 it gets slower (475 ms), because the Airflow
        webserver runs `webserver.workers = 4` gunicorn processes and the extra
        threads only queue behind them.

        A DAG whose request fails yields `[]` rather than aborting the other fifteen —
        a monitoring view degrades per row, never as a whole.
        """
        def _one(dag_id: str):
            # One Session per thread: requests.Session is not thread-safe.
            session = requests.Session()
            session.auth = (self.username, self.password)
            try:
                resp = session.get(
                    f"{self.base_url}/dags/{dag_id}/dagRuns",
                    params={'limit': limit, 'order_by': '-execution_date'},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return dag_id, []
                return dag_id, (resp.json().get('dag_runs') or [])
            except Exception:
                return dag_id, []
            finally:
                session.close()

        if not dag_ids:
            return {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            return dict(pool.map(_one, dag_ids))

    def get_dag_runs(self, limit=50):
        """Les dernières exécutions de tous les DAGs actifs, en DataFrame.

        Les requêtes par DAG partent en parallèle via `_runs_per_dag`. Mesuré en
        production le 2026-08-30 : **1541 ms en séquentiel** (16 allers-retours à
        ~90 ms) pour la seule vue `airflow_kpi`, dont c'était la totalité des 2195 ms
        de Python.
        """
        try:
            dags_resp = self.session.get(f"{self.base_url}/dags", params={'limit': 100})
            if dags_resp.status_code != 200:
                print(f"⚠️ Erreur API Liste DAGs: {dags_resp.status_code}")
                return pd.DataFrame()

            dags_data = dags_resp.json()
            dags = [d['dag_id'] for d in dags_data.get('dags', []) if not d.get('is_paused')]

            all_runs = []
            for dag_id, runs in self._runs_per_dag(dags, limit=5).items():
                for r in runs:
                    # Les deux noms de champ coexistent selon la version d'API.
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
                        'end_date': r.get('end_date'),
                        'duration_sec': duration,
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

    def get_all_dags_last_state(self, fetch_limit: int = 200) -> dict:
        """Latest run for EVERY DAG. Returns {dag_id: {..., duration_sec}}.

        Correct by construction: one request per DAG, issued concurrently. That is a
        deliberate step BACK from the batch endpoint, and the measurement is why.

        The previous implementation POSTed once to `/dags/~/dagRuns/list` with a
        `page_limit` window and took whatever came back. Its docstring stated the
        assumption — "with daily schedules each DAG's latest run sits well within
        200" — and production broke it: measured 2026-08-30, **392 dag runs in 24 h,
        of which 384 belong to the four CSV watchers** (96 each, every 15 min). The
        window therefore covered ~12 h and 98 % of it was four DAGs.

            batch, page_limit=200   254 ms   1 call    **4 of 16 DAGs**
            batch + dag_ids filter  194 ms   1 call    **4 of 16 DAGs** (the API
                                                       caps page_limit at 100, so
                                                       filtering does not help)
            per-DAG, sequential    1315 ms  16 calls   16 of 16
            per-DAG, 8 threads    **440 ms** 16 calls  **16 of 16**
            per-DAG, 16 threads     475 ms  16 calls   16 of 16

        `home` renders DAG health from this. With the window it showed **12 of 16
        DAGs as "no run"** — indistinguishable, on screen, from a DAG that genuinely
        had not run. A page that is fast and wrong is worse than one that is correct
        and 190 ms slower, so this trades those 190 ms back.

        8 workers, not 16: past 8 it gets slower, because the Airflow webserver runs
        `webserver.workers = 4` gunicorn processes and the extra threads only queue.

        `fetch_limit` is kept in the signature for callers that still pass it; it no
        longer selects a window and is ignored.
        """
        dag_ids = self.get_dag_list()
        latest = {}
        for dag_id, runs in self._runs_per_dag(dag_ids, limit=1).items():
            if runs:
                latest[dag_id] = self._run_summary(runs[0])
        return latest

    def _run_summary(self, r: dict) -> dict:
        """Normalise a raw dag_run JSON object into the monitor's run dict."""
        start_str = r.get('start_date')
        end_str = r.get('end_date')
        duration_sec = None
        if start_str:
            start = pd.to_datetime(start_str)
            end = pd.to_datetime(end_str) if end_str else datetime.now(start.tzinfo)
            duration_sec = (end - start).total_seconds()
        return {
            'run_id': r.get('dag_run_id') or r.get('run_id') or 'unknown',
            'state': r.get('state', '?'),
            'start_date': start_str or '',
            'end_date': end_str or '',
            'duration_sec': duration_sec,
        }

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
            except Exception:
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
