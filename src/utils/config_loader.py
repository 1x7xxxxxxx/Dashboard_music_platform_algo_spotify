"""Utilitaire pour charger la configuration depuis config.yaml"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Charge et gère la configuration de l'application."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialise le chargeur.
        Le chemin est calculé par rapport à la racine du projet pour être robuste.
        """
        # On cherche la racine du projet (2 niveaux au-dessus de ce fichier utils/)
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.config_path = self.project_root / config_path
        self._config = None

    def load(self, *, force: bool = False) -> Dict[str, Any]:
        """Load configuration from YAML file.

        Falls back to ``config/config.yaml`` relative to the working directory.
        If neither path exists (e.g. Railway deployment without a mounted config),
        returns an empty dict and logs a warning instead of raising.

        ⚠️ MÉMOÏSÉ depuis le 2026-09-17, et la correction est petite parce que le mémo
        EXISTAIT DÉJÀ : `self._config` était écrit à chaque appel et **jamais relu** par
        la fonction qui l'écrit. Seuls les trois `get_*_config()` le consultaient. Un
        champ de mémoïsation écrit et jamais lu se lit comme un cache ; il n'en est pas
        un, et rien ne le disait.

        Ce que ça coûtait, mesuré : **4,92 ms par appel** (médiane de 30, min 4,42, max
        8,34) pour parser **2 424 octets** de YAML. Le fichier est minuscule ; le coût
        est celui de l'ouverture — le dépôt vit sur `/mnt/c`, monté par `drvfs`, où
        chaque `open()` est un message 9P à travers la frontière VM/hôte. C'est le même
        fait que R117 mesure à ×69 sur l'écriture de petits fichiers.

        Sur l'accueil, `load()` pèse **12,5 ms cumulés** d'un `show()` mesuré à 80 ms —
        **15 %**, pour relire un fichier qui n'a pas changé.

        `force=True` relit depuis le disque. Personne n'édite `config.yaml` sous un
        processus vivant — les conteneurs n'en embarquent même pas — mais un appelant
        qui en aurait besoin ne doit pas avoir à toucher à un attribut privé.
        """
        if self._config is not None and not force:
            return self._config
        if not self.config_path.exists():
            local_path = Path("config/config.yaml")
            if local_path.exists():
                self.config_path = local_path
            else:
                logger.warning(
                    "config/config.yaml not found — falling back to environment variables only. "
                    "Set DATABASE_URL for the DB connection and API_SECRET_KEY for the REST API."
                )
                self._config = {}
                return self._config

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f) or {}

        return self._config

    # Helpers pour accès rapide
    def get_database_config(self) -> Dict[str, Any]:
        if not self._config: self.load()
        return self._config.get('database', {})

    def get_spotify_config(self) -> Dict[str, Any]:
        if not self._config: self.load()
        return self._config.get('spotify', {})

    def get_meta_ads_config(self) -> Dict[str, Any]:
        if not self._config: self.load()
        return self._config.get('meta_ads', {})

# Instance globale
config_loader = ConfigLoader()
