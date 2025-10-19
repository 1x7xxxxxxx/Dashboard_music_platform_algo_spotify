"""Collector Selenium semi-automatique pour Spotify for Artists."""
import glob
import time
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ManualS4ACollector:
    """Collecteur semi-automatique avec connexion manuelle."""
    
    def __init__(self, download_dir: str):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def wait_for_new_downloads(self, timeout: int = 300) -> List[str]:
        """
        Attend que l'utilisateur télécharge manuellement les fichiers.
        
        Args:
            timeout: Temps d'attente maximum en secondes (5 min par défaut)
        """
        logger.info("="*60)
        logger.info("📋 INSTRUCTIONS")
        logger.info("="*60)
        logger.info("1. Ouvrez https://artists.spotify.com dans votre navigateur")
        logger.info("2. Connectez-vous manuellement")
        logger.info("3. Allez dans Musique > Titres")
        logger.info("4. Sélectionnez le filtre 'Depuis le début'")
        logger.info("5. Cliquez sur le bouton de téléchargement")
        logger.info(f"6. Le fichier sera détecté automatiquement dans: {self.download_dir}")
        logger.info("="*60)
        logger.info("⏳ Attente du téléchargement... (5 min max)")
        logger.info("="*60)
        
        files_before = set(glob.glob(str(self.download_dir / "*.csv")))
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_files = set(glob.glob(str(self.download_dir / "*.csv")))
            new_files = current_files - files_before
            
            # Vérifier qu'il n'y a plus de téléchargements en cours
            downloading = glob.glob(str(self.download_dir / "*.crdownload"))
            
            if new_files and not downloading:
                logger.info(f"✅ {len(new_files)} fichier(s) détecté(s) !")
                return list(new_files)
            
            time.sleep(2)
        
        logger.warning("⚠️ Timeout - aucun fichier détecté")
        return []
    
    def organize_and_parse(self, files: List[str]) -> Dict[str, pd.DataFrame]:
        """Organise et parse les fichiers."""
        if not files:
            return {}
        
        parsed_data = {}
        current_date = datetime.now().strftime("%Y%m%d_%H%M")
        
        for file_path in files:
            try:
                file_path = Path(file_path)
                
                # Renommer
                new_name = f"s4a_tracks_{current_date}{file_path.suffix}"
                new_path = file_path.parent / new_name
                
                counter = 1
                while new_path.exists():
                    new_name = f"s4a_tracks_{current_date}_{counter}{file_path.suffix}"
                    new_path = file_path.parent / new_name
                    counter += 1
                
                file_path.rename(new_path)
                logger.info(f"📁 Renommé: {new_path.name}")
                
                # Parser
                df = pd.read_csv(new_path, encoding='utf-8')
                df.columns = df.columns.str.strip()
                df['collected_at'] = datetime.now()
                df['source'] = 'spotify_for_artists'
                
                parsed_data[new_path.stem] = df
                logger.info(f"📊 Parsé: {len(df)} lignes, {len(df.columns)} colonnes")
                
            except Exception as e:
                logger.error(f"❌ Erreur: {e}")
        
        return parsed_data
    
    def collect(self) -> Dict[str, pd.DataFrame]:
        """Collecte complète."""
        logger.info("\n🚀 COLLECTEUR SPOTIFY FOR ARTISTS - MODE MANUEL\n")
        
        downloaded_files = self.wait_for_new_downloads()
        
        if not downloaded_files:
            logger.error("❌ Aucun fichier téléchargé")
            return {}
        
        parsed_data = self.organize_and_parse(downloaded_files)
        
        logger.info("\n" + "="*60)
        logger.info(f"✅ SUCCÈS - {len(parsed_data)} fichier(s) traité(s)")
        logger.info("="*60 + "\n")
        
        for name, df in parsed_data.items():
            logger.info(f"📄 {name}")
            logger.info(f"   Colonnes: {', '.join(df.columns.tolist()[:10])}")
        
        return parsed_data


if __name__ == "__main__":
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config_loader import config_loader
    
    config = config_loader.load()
    download_dir = config.get('spotify_for_artists', {}).get('download_dir', 'data/raw/spotify_for_artists')
    
    collector = ManualS4ACollector(download_dir)
    data = collector.collect()
    
    if data:
        print("\n✅ Fichiers prêts pour stockage PostgreSQL !")