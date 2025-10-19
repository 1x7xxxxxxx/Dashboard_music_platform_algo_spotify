"""Collector Selenium pour Spotify for Artists."""
import os
import time
import glob
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpotifyForArtistsCollector:
    """Collecte les données depuis Spotify for Artists via Selenium."""
    
    def __init__(self, email: str, password: str, download_dir: str, headless: bool = False):
        """
        Initialise le collector Selenium.
        
        Args:
            email: Email Spotify for Artists
            password: Mot de passe
            download_dir: Répertoire de téléchargement
            headless: Mode sans interface graphique
        """
        self.email = email
        self.password = password
        self.download_dir = Path(download_dir)
        self.headless = headless
        self.driver = None
        self.wait = None
        
        # Créer le dossier de téléchargement
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Dossier de téléchargement: {self.download_dir}")
    
    def _configure_chrome_options(self) -> Options:
        """Configure les options du navigateur Chrome."""
        chrome_options = Options()
        
        # Préférences de téléchargement
        preferences = {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", preferences)
        
        # Options anti-détection
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Désactiver les logs inutiles
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument('--log-level=3')
        
        # Mode headless si activé
        if self.headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=1920,1080")
            logger.info("🔇 Mode headless activé")
        
        return chrome_options
    
    def initialize_driver(self) -> None:
        """Initialise le driver Selenium."""
        logger.info("🚀 Initialisation du driver Chrome...")
        
        try:
            service = Service(ChromeDriverManager().install())
            chrome_options = self._configure_chrome_options()
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.set_page_load_timeout(60)
            self.wait = WebDriverWait(self.driver, 30)
            
            logger.info("✅ Driver Chrome initialisé")
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation driver: {e}")
            raise
    
    def login(self, max_retries: int = 2) -> bool:
        """
        Se connecte à Spotify for Artists avec retry.
        
        Args:
            max_retries: Nombre de tentatives maximum
            
        Returns:
            True si connexion réussie, False sinon
        """
        for attempt in range(1, max_retries + 1):
            logger.info(f"🔐 Connexion à Spotify for Artists (tentative {attempt}/{max_retries})...")
            
            try:
                # Navigation
                self.driver.get("https://artists.spotify.com/")
                time.sleep(4)
                
                # Cliquer sur "Log in"
                try:
                    login_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log in') or contains(text(), 'Se connecter')]"))
                    )
                    login_button.click()
                    logger.info("🔄 Redirection vers la page de connexion...")
                    time.sleep(4)
                except TimeoutException:
                    logger.warning("⚠️ Bouton 'Log in' non trouvé, tentative navigation directe...")
                    self.driver.get("https://accounts.spotify.com/login")
                    time.sleep(4)
                
                # ÉTAPE 1: Saisir l'email
                logger.info("📧 Saisie de l'email...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                email_field = WebDriverWait(self.driver, 15).until(
                    EC.visibility_of_element_located((By.XPATH, "//input[@type='text' or @type='email'][1]"))
                )
                
                self.driver.execute_script("arguments[0].scrollIntoView(true);", email_field)
                time.sleep(1)
                email_field.click()
                time.sleep(0.5)
                email_field.clear()
                time.sleep(0.5)
                email_field.send_keys(self.email)
                logger.info("✅ Email saisi")
                time.sleep(2)
                
                # ÉTAPE 2: Cliquer sur "Continuer"
                logger.info("🔄 Recherche du bouton 'Continuer'...")
                time.sleep(2)
                
                all_buttons = self.driver.find_elements(By.XPATH, "//button")
                continue_button = None
                
                for button in all_buttons:
                    try:
                        if button.is_displayed() and button.is_enabled():
                            button_text = button.text.strip()
                            if button_text in ["Continuer", "Continue", "Next"]:
                                button_html = button.get_attribute("outerHTML")
                                if not any(oauth in button_html.lower() for oauth in ['google', 'facebook', 'apple']):
                                    continue_button = button
                                    logger.info(f"✅ Bouton '{button_text}' trouvé")
                                    break
                    except:
                        continue
                
                if continue_button:
                    continue_button.click()
                    logger.info("✅ Bouton 'Continuer' cliqué")
                    time.sleep(5)
                
                # ÉTAPE 3: Option "Connexion avec un mot de passe"
                logger.info("🔑 Recherche option 'Connexion avec un mot de passe'...")
                try:
                    password_option = WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Connexion avec un mot de passe') or contains(text(), 'password')]"))
                    )
                    password_option.click()
                    logger.info("✅ Option 'Connexion avec un mot de passe' sélectionnée")
                    time.sleep(5)
                except TimeoutException:
                    logger.info("ℹ️ Option mot de passe non nécessaire")
                
                # ÉTAPE 4: Vérifier champ email
                try:
                    email_field_2 = WebDriverWait(self.driver, 5).until(
                        EC.visibility_of_element_located((By.ID, "login-username"))
                    )
                    current_value = email_field_2.get_attribute("value")
                    if not current_value or current_value.strip() == "":
                        email_field_2.clear()
                        time.sleep(0.5)
                        email_field_2.send_keys(self.email)
                        time.sleep(2)
                except:
                    pass
                
                # ÉTAPE 5: Saisir mot de passe
                logger.info("🔑 Saisie du mot de passe...")
                password_field = WebDriverWait(self.driver, 15).until(
                    EC.visibility_of_element_located((By.ID, "login-password"))
                )
                
                password_field.clear()
                time.sleep(0.5)
                password_field.send_keys(self.password)
                logger.info("✅ Mot de passe saisi")
                time.sleep(2)
                
                # ÉTAPE 6: Se connecter
                logger.info("🔐 Clic sur le bouton de connexion...")
                submit_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "login-button"))
                )
                submit_button.click()
                logger.info("⏳ Connexion en cours...")
                
                # Attendre redirection
                try:
                    WebDriverWait(self.driver, 30).until(
                        lambda driver: "artists.spotify.com" in driver.current_url and "login" not in driver.current_url.lower()
                    )
                    time.sleep(5)
                    logger.info("✅ Connexion réussie !")
                    return True
                except TimeoutException:
                    current_url = self.driver.current_url
                    if "artists.spotify.com" in current_url and "login" not in current_url.lower():
                        logger.info("✅ Connexion réussie !")
                        return True
                    raise
                
            except Exception as e:
                logger.error(f"❌ Erreur connexion (tentative {attempt}): {str(e)[:100]}")
                self._save_screenshot(f"login_error_attempt_{attempt}")
                
                if attempt < max_retries:
                    logger.info("🔄 Nouvelle tentative...")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    time.sleep(5)
                    self.initialize_driver()
                    continue
        
        return False
    
    def _get_files_before_download(self) -> set:
        """Récupère les fichiers CSV avant téléchargement."""
        return set(glob.glob(str(self.download_dir / "*.csv")))
    
    def _wait_for_download_complete(self, files_before: set, timeout: int = 60) -> List[str]:
        """Attend la fin du téléchargement."""
        logger.info("⏳ Attente du téléchargement...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_files = set(glob.glob(str(self.download_dir / "*.csv")))
            new_files = current_files - files_before
            
            downloading_files = glob.glob(str(self.download_dir / "*.crdownload"))
            
            if not downloading_files and new_files:
                logger.info(f"✅ Téléchargement terminé: {len(new_files)} fichier(s)")
                return list(new_files)
            
            time.sleep(2)
        
        logger.warning("⚠️ Timeout du téléchargement")
        return []
    
    def download_music_tracks_csv(self) -> List[str]:
        """
        Télécharge les CSV depuis Musique > Titres avec filtre "Depuis le début".
        
        Returns:
            Liste des fichiers téléchargés
        """
        downloaded_files = []
        
        try:
            logger.info("\n🎵 Navigation vers la section Musique...")
            time.sleep(5)
            
            # ÉTAPE 1: Cliquer sur "Musique" dans le menu
            logger.info("📊 Recherche du menu 'Musique'...")
            
            music_selectors = [
                "//a[contains(text(), 'Musique') or contains(text(), 'Music')]",
                "//button[contains(text(), 'Musique') or contains(text(), 'Music')]",
                "//span[contains(text(), 'Musique') or contains(text(), 'Music')]/parent::a"
            ]
            
            music_clicked = False
            for selector in music_selectors:
                try:
                    music_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    music_element.click()
                    logger.info("✅ Section 'Musique' cliquée")
                    music_clicked = True
                    time.sleep(5)
                    break
                except TimeoutException:
                    continue
            
            if not music_clicked:
                logger.info("🔄 Tentative navigation directe vers Musique...")
                self.driver.get("https://artists.spotify.com/c/music")
                time.sleep(5)
            
            # ÉTAPE 2: Cliquer sur l'onglet "Titres"
            logger.info("🎵 Recherche de l'onglet 'Titres'...")
            
            titles_selectors = [
                "//button[contains(text(), 'Titres') or contains(text(), 'Tracks')]",
                "//a[contains(text(), 'Titres') or contains(text(), 'Tracks')]",
                "//*[contains(text(), 'Titres') and (name()='button' or name()='a')]"
            ]
            
            for selector in titles_selectors:
                try:
                    titles_tab = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    titles_tab.click()
                    logger.info("✅ Onglet 'Titres' cliqué")
                    time.sleep(3)
                    break
                except TimeoutException:
                    continue
            
            # ÉTAPE 3: Ouvrir le menu des filtres
            logger.info("🔍 Ouverture du menu de filtrage...")
            
            filter_selectors = [
                "//button[contains(text(), 'Filtrer') or contains(text(), 'Filter') or contains(@aria-label, 'filter')]",
                "//button[contains(text(), 'Filtres') or contains(text(), 'Filters')]",
                "//button[contains(@class, 'filter')]"
            ]
            
            filter_opened = False
            for selector in filter_selectors:
                try:
                    filter_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    filter_button.click()
                    logger.info("✅ Menu de filtrage ouvert")
                    filter_opened = True
                    time.sleep(2)
                    break
                except (TimeoutException, ElementClickInterceptedException):
                    continue
            
            if not filter_opened:
                logger.warning("⚠️ Impossible d'ouvrir les filtres, tentative sans filtre...")
            else:
                # ÉTAPE 4: Sélectionner "Depuis le début"
                logger.info("📅 Sélection du filtre 'Depuis le début'...")
                
                depuis_debut_selectors = [
                    "//label[contains(text(), 'Depuis le début')]/preceding-sibling::input",
                    "//span[contains(text(), 'Depuis le début')]/parent::label",
                    "//*[contains(text(), 'Depuis le début')]"
                ]
                
                for selector in depuis_debut_selectors:
                    try:
                        depuis_debut = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        depuis_debut.click()
                        logger.info("✅ Filtre 'Depuis le début' sélectionné")
                        time.sleep(2)
                        
                        # Fermer le menu de filtrage si nécessaire
                        try:
                            close_filter = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'close') or contains(@aria-label, 'fermer')]")
                            close_filter.click()
                            time.sleep(1)
                        except:
                            pass
                        
                        break
                    except (TimeoutException, ElementClickInterceptedException):
                        continue
            
            # ÉTAPE 5: Télécharger le CSV
            logger.info("📥 Recherche du bouton de téléchargement...")
            
            files_before = self._get_files_before_download()
            
            # Sélecteurs pour le bouton de téléchargement
            download_selectors = [
                "//button[@aria-label='Télécharger' or @aria-label='Download']",
                "//button[contains(@title, 'Télécharger') or contains(@title, 'Download')]",
                "//button[.//svg[contains(@class, 'download')]]",
                "//*[name()='svg' and contains(@class, 'download')]/ancestor::button",
                "//button[contains(@data-testid, 'download')]"
            ]
            
            download_found = False
            for i, selector in enumerate(download_selectors):
                try:
                    logger.info(f"🔍 Test sélecteur téléchargement {i+1}/{len(download_selectors)}...")
                    download_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # Scroll vers le bouton
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                    time.sleep(1)
                    
                    download_button.click()
                    logger.info("✅ Bouton téléchargement cliqué")
                    
                    new_files = self._wait_for_download_complete(files_before, timeout=90)
                    if new_files:
                        downloaded_files.extend(new_files)
                        download_found = True
                        logger.info(f"🎉 {len(new_files)} fichier(s) téléchargé(s) !")
                        break
                        
                except (TimeoutException, ElementClickInterceptedException) as e:
                    logger.warning(f"⚠️ Sélecteur {i+1} échoué: {str(e)[:50]}")
                    continue
            
            if not download_found:
                logger.error("❌ Aucun bouton de téléchargement trouvé")
                self._save_screenshot("music_tracks_no_download_button")
            
        except Exception as e:
            logger.error(f"❌ Erreur dans download_music_tracks_csv: {e}")
            self._save_screenshot("music_tracks_error")
        
        return downloaded_files
    
    def parse_csv_files(self, csv_files: List[str]) -> Dict[str, pd.DataFrame]:
        """Parse les fichiers CSV téléchargés."""
        parsed_data = {}
        
        for csv_file in csv_files:
            try:
                filename = Path(csv_file).stem
                logger.info(f"📊 Parsing {filename}...")
                
                df = pd.read_csv(csv_file, encoding='utf-8')
                df.columns = df.columns.str.strip()
                df['collected_at'] = datetime.now()
                df['source_file'] = filename
                
                parsed_data[filename] = df
                logger.info(f"✅ {filename}: {len(df)} lignes, {len(df.columns)} colonnes")
                
            except Exception as e:
                logger.error(f"❌ Erreur parsing {csv_file}: {e}")
        
        return parsed_data
    
    def organize_files(self, downloaded_files: List[str]) -> List[str]:
        """Renomme les fichiers avec la date."""
        if not downloaded_files:
            return []
        
        logger.info(f"\n📁 Organisation de {len(downloaded_files)} fichier(s)...")
        organized_files = []
        current_date = datetime.now().strftime("%Y%m%d_%H%M")
        
        for file_path in downloaded_files:
            try:
                file_path = Path(file_path)
                name = file_path.stem
                ext = file_path.suffix
                
                new_filename = f"music_tracks_{name}_{current_date}{ext}"
                new_path = file_path.parent / new_filename
                
                counter = 1
                while new_path.exists():
                    new_filename = f"music_tracks_{name}_{current_date}_{counter}{ext}"
                    new_path = file_path.parent / new_filename
                    counter += 1
                
                file_path.rename(new_path)
                organized_files.append(str(new_path))
                logger.info(f"✅ Renommé: {file_path.name} → {new_path.name}")
                
            except Exception as e:
                logger.error(f"❌ Erreur renommage {file_path}: {e}")
                organized_files.append(str(file_path))
        
        return organized_files
    
    def _save_screenshot(self, name: str) -> None:
        """Sauvegarde une capture d'écran."""
        try:
            if self.driver and self.driver.session_id:
                screenshot_path = self.download_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(str(screenshot_path))
                logger.info(f"📷 Capture d'écran: {screenshot_path.name}")
        except Exception as e:
            logger.error(f"❌ Erreur capture d'écran: {e}")
    
    def close(self) -> None:
        """Ferme le driver."""
        if self.driver:
            try:
                logger.info("🔄 Fermeture du driver...")
                self.driver.quit()
                logger.info("✅ Driver fermé")
            except Exception as e:
                logger.warning(f"⚠️ Erreur fermeture driver: {e}")
    
    def collect(self) -> Tuple[bool, Dict[str, pd.DataFrame]]:
        """
        Collecte complète: login + téléchargement + parsing.
        
        Returns:
            (success, parsed_data)
        """
        try:
            self.initialize_driver()
            
            if not self.login():
                logger.error("❌ Échec de la connexion")
                return False, {}
            
            downloaded_files = self.download_music_tracks_csv()
            
            if not downloaded_files:
                logger.warning("⚠️ Aucun fichier téléchargé")
                return False, {}
            
            organized_files = self.organize_files(downloaded_files)
            parsed_data = self.parse_csv_files(organized_files)
            
            logger.info(f"\n🎉 Collecte terminée: {len(parsed_data)} fichier(s) parsé(s)")
            
            return True, parsed_data
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la collecte: {e}")
            return False, {}
        finally:
            self.close()


# Test du module
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config_loader import config_loader
    
    config = config_loader.load()
    s4a_config = config.get('spotify_for_artists', {})
    
    if not s4a_config:
        print("❌ Configuration 'spotify_for_artists' manquante")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("🚀 SPOTIFY FOR ARTISTS - COLLECTEUR MUSIQUE/TITRES")
    print("="*60)
    print(f"📧 Email: {s4a_config['email']}")
    print(f"📁 Destination: {s4a_config['download_dir']}")
    print("="*60 + "\n")
    
    collector = SpotifyForArtistsCollector(
        email=s4a_config['email'],
        password=s4a_config['password'],
        download_dir=s4a_config['download_dir'],
        headless=s4a_config.get('headless', False)
    )
    
    success, data = collector.collect()
    
    print("\n" + "="*60)
    if success:
        print("✅ SUCCÈS")
        print("="*60)
        for filename, df in data.items():
            print(f"\n📄 {filename}")
            print(f"   └─ {len(df)} lignes × {len(df.columns)} colonnes")
            print(f"   └─ Colonnes: {', '.join(df.columns.tolist()[:10])}")
    else:
        print("❌ ÉCHEC")
    print("="*60 + "\n")