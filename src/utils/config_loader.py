"""Utilitaire pour charger la configuration depuis config.yaml"""
import yaml
from pathlib import Path
from typing import Dict, Any, List


class ConfigLoader:
    """Charge et gère la configuration de l'application."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialise le chargeur de configuration.
        
        Args:
            config_path: Chemin vers le fichier de configuration
        """
        self.config_path = Path(config_path)
        self._config = None
    
    def load(self) -> Dict[str, Any]:
        """
        Charge la configuration depuis le fichier YAML.
        
        Returns:
            Dict contenant toute la configuration
            
        Raises:
            FileNotFoundError: Si le fichier config n'existe pas
            yaml.YAMLError: Si le fichier YAML est mal formaté
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Fichier de configuration introuvable: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        return self._config
    
    def get_spotify_config(self) -> Dict[str, str]:
        """Récupère la configuration Spotify."""
        if not self._config:
            self.load()
        return self._config.get('spotify', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Récupère la configuration de la base de données."""
        if not self._config:
            self.load()
        return self._config.get('database', {})
    
    def get_meta_ads_config(self) -> Dict[str, str]:
        """Récupère la configuration Meta Ads."""
        if not self._config:
            self.load()
        return self._config.get('meta_ads', {})

    def get_artists_config(self) -> List[Dict[str, Any]]:
        """Récupère la liste des artistes à suivre."""
        if not self._config:
            self.load()
        return self._config.get('artists', [])
    
    def get_active_artists(self) -> List[Dict[str, Any]]:
        """Récupère uniquement les artistes actifs."""
        artists = self.get_artists_config()
        return [artist for artist in artists if artist.get('active', True)]

# Instance globale pour utilisation facile
config_loader = ConfigLoader()