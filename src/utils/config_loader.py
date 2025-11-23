"""Utilitaire pour charger la configuration depuis config.yaml"""
import yaml
from pathlib import Path
from typing import Dict, Any, List
import os

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
    
    def load(self) -> Dict[str, Any]:
        """Charge la configuration."""
        if not self.config_path.exists():
            # Fallback: cherche dans le dossier courant si lancé depuis la racine
            local_path = Path("config/config.yaml")
            if local_path.exists():
                self.config_path = local_path
            else:
                raise FileNotFoundError(f"Fichier de configuration introuvable: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
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