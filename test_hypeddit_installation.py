#!/usr/bin/env python3
"""
Script de test et validation de l'installation Hypeddit
Vérifie que tous les composants sont correctement installés et fonctionnels
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Couleurs pour output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.BLUE}{Colors.BOLD}🧪 Test: {name}{Colors.ENDC}")

def print_success(msg):
    print(f"  {Colors.GREEN}✅ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"  {Colors.RED}❌ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"  {Colors.BLUE}ℹ️  {msg}{Colors.ENDC}")


class HypedditValidator:
    """Validateur complet de l'installation Hypeddit."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def run_all_tests(self):
        """Lance tous les tests."""
        print(f"\n{Colors.BOLD}{'='*70}")
        print("🔍 VALIDATION INSTALLATION HYPEDDIT")
        print(f"{'='*70}{Colors.ENDC}\n")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Tests de structure
        self.test_file_structure()
        self.test_python_files()
        self.test_environment_variables()
        
        # Tests de base de données
        self.test_database_connection()
        self.test_database_tables()
        
        # Tests de collecte
        self.test_collector_import()
        self.test_api_connection()
        
        # Tests Airflow
        self.test_airflow_dag()
        
        # Tests Dashboard
        self.test_dashboard_integration()
        
        # Résumé
        self.print_summary()
        
        # Code de sortie
        return 0 if self.failed == 0 else 1
    
    def test_file_structure(self):
        """Vérifie que tous les fichiers sont présents."""
        print_test("Structure des fichiers")
        
        files_to_check = {
            'src/collectors/hypeddit_collector.py': 'Collector Hypeddit',
            'src/database/hypeddit_schema.py': 'Schéma PostgreSQL',
            'airflow/dags/hypeddit_daily.py': 'DAG Airflow',
            'src/dashboard/views/hypeddit.py': 'Vue Streamlit',
        }
        
        all_present = True
        for file_path, description in files_to_check.items():
            if Path(file_path).exists():
                print_success(f"{description}: {file_path}")
                self.passed += 1
            else:
                print_error(f"{description} manquant: {file_path}")
                self.failed += 1
                all_present = False
        
        if all_present:
            print_info("Tous les fichiers sont présents")
    
    def test_python_files(self):
        """Vérifie que les fichiers Python sont valides."""
        print_test("Validation syntaxe Python")
        
        python_files = [
            'src/collectors/hypeddit_collector.py',
            'src/database/hypeddit_schema.py',
            'airflow/dags/hypeddit_daily.py',
            'src/dashboard/views/hypeddit.py',
        ]
        
        for file_path in python_files:
            if not Path(file_path).exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), file_path, 'exec')
                print_success(f"Syntaxe OK: {file_path}")
                self.passed += 1
            except SyntaxError as e:
                print_error(f"Erreur syntaxe dans {file_path}: {e}")
                self.failed += 1
    
    def test_environment_variables(self):
        """Vérifie les variables d'environnement."""
        print_test("Variables d'environnement")
        
        # Vérifier .env
        env_file = Path('.env')
        if not env_file.exists():
            print_error("Fichier .env non trouvé")
            self.failed += 1
            return
        
        print_success("Fichier .env trouvé")
        self.passed += 1
        
        # Vérifier HYPEDDIT_API_KEY
        with open(env_file, 'r') as f:
            content = f.read()
        
        if 'HYPEDDIT_API_KEY' in content:
            print_success("Variable HYPEDDIT_API_KEY présente")
            self.passed += 1
            
            # Vérifier si elle est configurée
            api_key = os.getenv('HYPEDDIT_API_KEY', '')
            if api_key and api_key != 'YOUR_API_KEY_HERE':
                print_success("API key configurée")
                self.passed += 1
            else:
                print_warning("API key non configurée (valeur par défaut)")
                print_info("Configurez votre vraie clé API dans .env")
                self.warnings += 1
        else:
            print_error("Variable HYPEDDIT_API_KEY absente du .env")
            self.failed += 1
    
    def test_database_connection(self):
        """Teste la connexion à PostgreSQL."""
        print_test("Connexion PostgreSQL")
        
        try:
            sys.path.append(str(Path.cwd()))
            from src.database.postgres_handler import PostgresHandler
            from src.utils.config_loader import config_loader
            
            config = config_loader.load()
            db_config = config['database']
            
            db = PostgresHandler(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['user'],
                password=db_config['password']
            )
            
            print_success("Connexion PostgreSQL réussie")
            self.passed += 1
            
            db.close()
            
        except FileNotFoundError:
            print_error("Fichier config/config.yaml non trouvé")
            self.failed += 1
        except Exception as e:
            print_error(f"Erreur connexion PostgreSQL: {e}")
            print_info("Vérifiez que Docker est lancé: docker-compose ps")
            self.failed += 1
    
    def test_database_tables(self):
        """Vérifie que les tables Hypeddit existent."""
        print_test("Tables PostgreSQL Hypeddit")
        
        try:
            sys.path.append(str(Path.cwd()))
            from src.database.postgres_handler import PostgresHandler
            from src.utils.config_loader import config_loader
            
            config = config_loader.load()
            db_config = config['database']
            
            db = PostgresHandler(**db_config)
            
            tables = [
                'hypeddit_campaigns',
                'hypeddit_daily_stats',
                'hypeddit_track_mapping'
            ]
            
            all_exist = True
            for table in tables:
                if db.table_exists(table):
                    count = db.get_table_count(table)
                    print_success(f"Table {table} existe ({count} enregistrement(s))")
                    self.passed += 1
                else:
                    print_error(f"Table {table} n'existe pas")
                    self.failed += 1
                    all_exist = False
            
            if not all_exist:
                print_info("Créez les tables: python src/database/hypeddit_schema.py")
            
            db.close()
            
        except Exception as e:
            print_error(f"Erreur vérification tables: {e}")
            self.failed += 1
    
    def test_collector_import(self):
        """Teste l'import du collector."""
        print_test("Import du collector Hypeddit")
        
        try:
            sys.path.append(str(Path.cwd()))
            from src.collectors.hypeddit_collector import HypedditCollector
            
            print_success("Collector importé avec succès")
            self.passed += 1
            
            # Vérifier les méthodes principales
            methods = [
                'get_campaigns',
                'get_campaign_stats',
                'get_campaign_daily_breakdown',
                'get_all_campaigns_with_stats'
            ]
            
            for method in methods:
                if hasattr(HypedditCollector, method):
                    print_success(f"Méthode {method} présente")
                    self.passed += 1
                else:
                    print_error(f"Méthode {method} manquante")
                    self.failed += 1
            
        except ImportError as e:
            print_error(f"Erreur import collector: {e}")
            self.failed += 1
        except Exception as e:
            print_error(f"Erreur inattendue: {e}")
            self.failed += 1
    
    def test_api_connection(self):
        """Teste la connexion à l'API Hypeddit."""
        print_test("Connexion API Hypeddit")
        
        api_key = os.getenv('HYPEDDIT_API_KEY', '')
        
        if not api_key or api_key == 'YOUR_API_KEY_HERE':
            print_warning("API key non configurée - test ignoré")
            self.warnings += 1
            return
        
        try:
            sys.path.append(str(Path.cwd()))
            from src.collectors.hypeddit_collector import HypedditCollector
            
            collector = HypedditCollector(api_key=api_key)
            
            print_success("Collector initialisé")
            self.passed += 1
            
            # Tentative de collecte (non bloquant si échec)
            try:
                campaigns = collector.get_campaigns()
                if campaigns:
                    print_success(f"API fonctionnelle - {len(campaigns)} campagne(s) trouvée(s)")
                    self.passed += 1
                else:
                    print_warning("API contactée mais aucune campagne trouvée")
                    self.warnings += 1
            except Exception as e:
                print_warning(f"Erreur API (peut être normal): {e}")
                print_info("Vérifiez la documentation de l'API Hypeddit")
                print_info("Le collector devra peut-être être adapté")
                self.warnings += 1
            
        except Exception as e:
            print_error(f"Erreur initialisation collector: {e}")
            self.failed += 1
    
    def test_airflow_dag(self):
        """Vérifie que le DAG Airflow est valide."""
        print_test("DAG Airflow")
        
        dag_file = Path('airflow/dags/hypeddit_daily.py')
        
        if not dag_file.exists():
            print_error("Fichier DAG non trouvé")
            self.failed += 1
            return
        
        print_success("Fichier DAG présent")
        self.passed += 1
        
        # Vérifier la syntaxe DAG
        try:
            with open(dag_file, 'r') as f:
                content = f.read()
            
            # Vérifications basiques
            if 'from airflow import DAG' in content:
                print_success("Import DAG présent")
                self.passed += 1
            else:
                print_error("Import DAG manquant")
                self.failed += 1
            
            if 'collect_hypeddit_campaigns' in content:
                print_success("Fonction collect_campaigns présente")
                self.passed += 1
            else:
                print_error("Fonction collect_campaigns manquante")
                self.failed += 1
            
            if 'collect_hypeddit_stats' in content:
                print_success("Fonction collect_stats présente")
                self.passed += 1
            else:
                print_error("Fonction collect_stats manquante")
                self.failed += 1
            
            if "dag_id='hypeddit_daily'" in content or 'dag_id="hypeddit_daily"' in content:
                print_success("DAG ID correct")
                self.passed += 1
            else:
                print_warning("DAG ID introuvable ou incorrect")
                self.warnings += 1
                
        except Exception as e:
            print_error(f"Erreur vérification DAG: {e}")
            self.failed += 1
    
    def test_dashboard_integration(self):
        """Vérifie l'intégration dans le dashboard."""
        print_test("Intégration Dashboard")
        
        app_file = Path('src/dashboard/app.py')
        
        if not app_file.exists():
            print_error("Fichier app.py non trouvé")
            self.failed += 1
            return
        
        try:
            with open(app_file, 'r') as f:
                content = f.read()
            
            # Vérifier présence dans le menu
            if '"📱 Hypeddit"' in content or "'📱 Hypeddit'" in content:
                print_success("Hypeddit présent dans le menu")
                self.passed += 1
            else:
                print_warning("Hypeddit absent du menu dashboard")
                print_info("Ajoutez manuellement ou relancez install_hypeddit.py")
                self.warnings += 1
            
            # Vérifier import de la vue
            if 'from views.hypeddit import show' in content:
                print_success("Import de la vue Hypeddit présent")
                self.passed += 1
            else:
                print_warning("Import de la vue Hypeddit manquant")
                self.warnings += 1
            
            # Vérifier elif page
            if 'elif page == "hypeddit"' in content or "elif page == 'hypeddit'" in content:
                print_success("Route page Hypeddit présente")
                self.passed += 1
            else:
                print_warning("Route page Hypeddit manquante")
                self.warnings += 1
                
        except Exception as e:
            print_error(f"Erreur vérification dashboard: {e}")
            self.failed += 1
        
        # Vérifier Airflow trigger
        trigger_file = Path('src/utils/airflow_trigger.py')
        
        if trigger_file.exists():
            try:
                with open(trigger_file, 'r') as f:
                    content = f.read()
                
                if "'hypeddit_daily'" in content or '"hypeddit_daily"' in content:
                    print_success("DAG Hypeddit dans Airflow trigger")
                    self.passed += 1
                else:
                    print_warning("DAG Hypeddit absent d'Airflow trigger")
                    self.warnings += 1
            except Exception as e:
                print_error(f"Erreur vérification trigger: {e}")
                self.failed += 1
    
    def print_summary(self):
        """Affiche le résumé des tests."""
        print(f"\n{Colors.BOLD}{'='*70}")
        print("📊 RÉSUMÉ DES TESTS")
        print(f"{'='*70}{Colors.ENDC}\n")
        
        total = self.passed + self.failed + self.warnings
        
        print(f"  {Colors.GREEN}✅ Réussis   : {self.passed}{Colors.ENDC}")
        print(f"  {Colors.RED}❌ Échoués   : {self.failed}{Colors.ENDC}")
        print(f"  {Colors.YELLOW}⚠️  Warnings  : {self.warnings}{Colors.ENDC}")
        print(f"  📊 Total     : {total}")
        
        print()
        
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 Installation VALIDÉE !{Colors.ENDC}\n")
            print("Prochaines étapes:")
            print("  1. Configurer HYPEDDIT_API_KEY dans .env")
            print("  2. Adapter le collector selon l'API Hypeddit")
            print("  3. Lancer une collecte de test")
            print("  4. Visualiser les données dans le dashboard")
        elif self.warnings > 0 and self.failed == 0:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Installation OK avec warnings{Colors.ENDC}\n")
            print("Actions recommandées:")
            print("  - Vérifier les warnings ci-dessus")
            print("  - Configurer l'API key Hypeddit")
            print("  - Tester la collecte")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ Installation INCOMPLÈTE{Colors.ENDC}\n")
            print("Actions requises:")
            print("  - Corriger les erreurs ci-dessus")
            print("  - Relancer install_hypeddit.py si nécessaire")
            print("  - Consulter HYPEDDIT_INTEGRATION_DOC.md")
        
        print(f"\n{'='*70}\n")


def main():
    """Point d'entrée principal."""
    validator = HypedditValidator()
    exit_code = validator.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()