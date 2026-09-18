"""Utilitaire pour déclencher les DAGs Airflow depuis Streamlit."""
import requests
from typing import Dict, List, Optional
import logging
from src.utils.safe_error import safe_error

logger = logging.getLogger(__name__)


def build_airflow_trigger(config: Optional[Dict] = None) -> "AirflowTrigger":
    """LE seul endroit du dépôt qui résout les identifiants de l'API Airflow.

    Pourquoi une fabrique, et pas un objet de module importé depuis `app.py`
    ---------------------------------------------------------------------------
    Au 2026-09-18 il existait **quatre** précédences pour les mêmes identifiants :

    * `app.py:75`          — `AIRFLOW_*` puis `config.yaml`
    * `credentials/_render.py:1116` — `AIRFLOW_ADMIN_*` puis `AIRFLOW_*`, sans `config.yaml`
    * `views/home.py:763`  — **aucune** : les littéraux `admin`/`admin`
    * `dashboard/utils/airflow_monitor.py:50` — environnement seul, et `auth = (None, None)`
      quand rien n'est posé, donc un client NON AUTHENTIFIÉ qui rapporte
      « Aucun DAG trouvé » au lieu d'échouer.

    Importer l'objet d'`app.py` aurait marché (vérifié : pas de cycle) et aurait été
    le mauvais geste — une vue dépendrait alors du module applicatif de 992 lignes
    pour obtenir un identifiant, et l'import exécute ses `RuntimeError` de démarrage,
    qu'un `except Exception` d'appelant transforme en « fonctionnalité indisponible ».

    L'ordre, et ce qui le justifie
    -------------------------------
    1. `AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD` — le nom CÔTÉ APPLICATION. C'est celui
       que `docker-compose.example.yml:271` fabrique pour le service dashboard, que
       `.env.railway.example:16` documente, et que la CI pose.
    2. `AIRFLOW_ADMIN_USERNAME` / `AIRFLOW_ADMIN_PASSWORD` — le nom de PROVISIONNEMENT
       (`docker-compose.yml:51` les donne à `airflow-init` pour CRÉER le compte). Ils
       sont présents dans le `.env` de ce poste, donc les refuser casserait le dev
       local ; ils viennent en second, jamais en premier.
    3. `config.yaml`, section `airflow:`. ⚠️ Elle n'est PAS dans
       `config/config.example.yaml` — elle existe pourtant dans le `config.yaml` de ce
       poste. On la garde et on la documente, au lieu de retirer une source vivante.
    4. Sinon on LÈVE. Jamais de repli littéral.
    """
    import os

    if config is None:
        try:
            from src.utils import config_loader
            config = config_loader.load()
        except Exception:      # noqa: BLE001 — pas de config.yaml : l'env doit suffire
            config = {}
    a = (config or {}).get("airflow", {}) or {}

    base_url = (os.getenv("AIRFLOW_BASE_URL")
                or a.get("base_url") or "http://localhost:8080")
    username = (os.getenv("AIRFLOW_USERNAME") or os.getenv("AIRFLOW_ADMIN_USERNAME")
                or a.get("username"))
    password = (os.getenv("AIRFLOW_PASSWORD") or os.getenv("AIRFLOW_ADMIN_PASSWORD")
                or a.get("password"))
    if not username or not password:
        raise RuntimeError(
            "Identifiants Airflow absents. Poser `AIRFLOW_USERNAME` et "
            "`AIRFLOW_PASSWORD` dans `.env`/`.env.local` (ou `AIRFLOW_ADMIN_*`, ou la "
            "section `airflow:` de `config/config.yaml`). Aucun défaut littéral n'est "
            "servi : il permettrait de déclencher des DAG sans authentification, et "
            "c'est exactement ce qui a rendu le bouton « Lancer les collectes » "
            "inopérant pendant des semaines."
        )
    return AirflowTrigger(base_url=base_url, username=username, password=password)


class AirflowTrigger:
    """Classe pour déclencher les DAGs Airflow via l'API REST."""

    def __init__(self, base_url: str, username: str, password: str):
        """Initialise le trigger Airflow. Les trois arguments sont OBLIGATOIRES.

        ⚠️ **Il n'y a plus de valeur par défaut, et c'est le correctif.** Jusqu'au
        2026-09-18 les trois paramètres en portaient une, celle de l'administrateur
        Airflow par convention, et `home.py:763` construisait `AirflowTrigger()` nu — donc
        avec ces trois littéraux. Mesuré contre l'instance vivante : les identifiants
        réels ne valent pas `admin`/`admin`, et `curl -u admin:admin …/api/v1/dags`
        rend **HTTP 401**. Le bouton « Lancer les collectes » de l'étape 4 de la mise
        en route échouait pour tout le monde.

        ⚠️ **Et c'est une RÉCIDIVE.** `archive.md:1958` (HIGH-05, juin 2026) annonce
        exactement ce correctif — « RuntimeError raised if AIRFLOW_PASSWORD is falsy ».
        Il avait été écrit dans un APPELANT (`app.py`) et non dans la classe : la
        classe a gardé son défaut, et trois autres appelants sont nés depuis. **Une
        vérification d'identifiant qui vit dans un appelant sur quatre n'est pas une
        vérification.**

        On lève sur une valeur FAUSSE, pas seulement absente : `_render.py:1121`
        passait `os.getenv('AIRFLOW_PASSWORD', '')`, une chaîne vide — un appel non
        authentifié déguisé en appel configuré.
        """
        manquants = [n for n, v in (("username", username), ("password", password))
                     if not v]
        if manquants:
            raise ValueError(
                f"AirflowTrigger : {', '.join(manquants)} vide ou absent. Passer par "
                "`build_airflow_trigger()`, qui résout `AIRFLOW_USERNAME` / "
                "`AIRFLOW_PASSWORD` (ou `AIRFLOW_ADMIN_*`, ou `config.yaml`) au seul "
                "endroit du dépôt qui a le droit de les lire. Un identifiant qui a une "
                "valeur par défaut est un identifiant qu'on oublie de passer."
            )
        # Un `http://user:pass@hote/` porterait le mot de passe dans TOUTE trace  # pragma: allowlist secret
        # `requests`, et `safe_error.redact()` ne retire que les paramètres de requête
        # `nom=valeur`, jamais l'« userinfo » d'une URL. On refuse la forme plutôt que
        # d'élargir le rédacteur : l'authentification passe par l'en-tête, ici.
        if "@" in base_url.split("//", 1)[-1].split("/", 1)[0]:
            raise ValueError(
                "AirflowTrigger : `base_url` porte des identifiants dans l'URL "
                "— la forme avec un « userinfo » avant l'arobase. Ils fuiraient "
                "dans les journaux et dans "
                "les messages d'erreur, que `redact()` ne nettoie pas sur cette forme. "
                "Passer par `username`/`password`, qui partent en en-tête."
            )
        self.base_url = base_url.rstrip('/')
        self.auth = (username, password)
        self.session = requests.Session()
        self.session.auth = self.auth

        logger.info(f"✅ AirflowTrigger initialisé: {self.base_url}")

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
                except Exception:
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
                'message': "Connexion à Airflow impossible"
            }

        except Exception as e:
            error_msg = safe_error(e)
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
        # ⚠️ `meta_ads_api_daily`, pas `meta_ads_daily_docker`. Le second nom ne designe
        # aucun DAG de `airflow/dags/` — mesure le 2026-09-18 : les `dag_id` declares ne
        # le contiennent pas. Un declenchement sur ce nom rend 404 et la collecte Meta ne
        # part jamais. Remonte la chaine : cette methode n'a aucun appelant dans le depot,
        # donc le defaut etait INERTE ici — il ne l'etait pas dans le bloc __main__.
        dags = [
            'meta_ads_api_daily',
            'spotify_api_daily',
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
                'error': safe_error(e)
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
            logger.error(f"❌ Erreur get_last_dag_run pour {dag_id}: {safe_error(e)}")
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
            logger.error(f"❌ Connexion à Airflow impossible: {safe_error(e)}")
            return False


# Test
if __name__ == "__main__":
    trigger = build_airflow_trigger()   # la démo documente le chemin RÉEL

    # Test de connexion
    print("\n🔍 Test de connexion...")
    if trigger.check_connection():
        print("✅ Connexion OK\n")

        # Test déclenchement d'un DAG
        print("🚀 Test déclenchement meta_ads_api_daily...")
        result = trigger.trigger_dag('meta_ads_api_daily')

        if result['success']:
            print(f"✅ {result['message']}")
            print(f"   DAG Run ID: {result['dag_run_id']}")
        else:
            print(f"❌ {result['message']}")
            print(f"   Erreur: {result['error']}")
    else:
        print("❌ Impossible de se connecter à Airflow")
        print("   Vérifiez que Airflow est démarré sur http://localhost:8080")
