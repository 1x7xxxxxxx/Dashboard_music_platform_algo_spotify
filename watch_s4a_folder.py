"""Watcher pour détecter automatiquement les nouveaux CSV S4A."""
import time
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

# Importer directement le processeur au lieu d'utiliser subprocess
sys.path.append(str(Path(__file__).parent))
from process_s4a_csv import S4ACSVProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CSVHandler(FileSystemEventHandler):
    """Gestionnaire d'événements pour les nouveaux CSV."""
    
    def __init__(self):
        self.processing = set()
        self.processor = None
    
    def on_created(self, event):
        """Appelé quand un nouveau fichier est créé."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Vérifier que c'est un CSV
        if file_path.suffix.lower() != '.csv':
            return
        
        # Éviter de traiter plusieurs fois
        if str(file_path) in self.processing:
            return
        
        self.processing.add(str(file_path))
        
        logger.info(f"\n🆕 Nouveau fichier détecté: {file_path.name}")
        
        # Attendre que le fichier soit complètement écrit
        time.sleep(2)
        
        # Lancer le traitement
        try:
            logger.info("🔄 Lancement du traitement automatique...")
            
            # Créer une instance du processeur
            if not self.processor:
                self.processor = S4ACSVProcessor()
            
            # Traiter le fichier spécifique
            success = self.processor.process_file(file_path)
            
            if success:
                logger.info("✅ Traitement terminé avec succès")
            else:
                logger.error("❌ Échec du traitement")
        
        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        finally:
            self.processing.discard(str(file_path))


def watch_folder():
    """Surveille le dossier pour les nouveaux CSV."""
    watch_dir = Path("data/raw/spotify_for_artists")
    watch_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("\n" + "="*70)
    logger.info("👁️ SURVEILLANCE AUTOMATIQUE CSV SPOTIFY FOR ARTISTS")
    logger.info("="*70)
    logger.info(f"📁 Dossier surveillé: {watch_dir.absolute()}")
    logger.info("⏳ En attente de nouveaux fichiers CSV...")
    logger.info("   (Appuyez sur Ctrl+C pour arrêter)")
    logger.info("="*70 + "\n")
    
    event_handler = CSVHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Arrêt de la surveillance...")
        observer.stop()
        
        # Fermer le processeur proprement
        if event_handler.processor:
            event_handler.processor.close()
    
    observer.join()
    logger.info("✅ Surveillance terminée")


if __name__ == "__main__":
    watch_folder()