#!/usr/bin/env python3
"""
Script d'installation de l'intégration Hypeddit
Déploie toutes les composantes nécessaires pour collecter et afficher les données Hypeddit
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Couleurs pour le terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def check_project_structure():
    """Vérifie que la structure du projet est correcte."""
    print_header("🔍 VÉRIFICATION STRUCTURE PROJET")
    
    required_dirs = [
        'src/collectors',
        'src/database',
        'src/dashboard/views',
        'airflow/dags',
        'config'
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print_success(f"Dossier trouvé: {dir_path}")
        else:
            print_error(f"Dossier manquant: {dir_path}")
            all_exist = False
    
    return all_exist


def deploy_collector():
    """Déploie le collector Hypeddit."""
    print_header("📦 DÉPLOIEMENT COLLECTOR HYPEDDIT")
    
    src_file = Path('/home/claude/hypeddit_collector.py')
    dst_file = Path('src/collectors/hypeddit_collector.py')
    
    try:
        if src_file.exists():
            shutil.copy(src_file, dst_file)
            print_success(f"Collector copié: {dst_file}")
            return True
        else:
            print_error("Fichier collector non trouvé")
            return False
    except Exception as e:
        print_error(f"Erreur copie collector: {e}")
        return False


def deploy_schema():
    """Déploie le schéma PostgreSQL Hypeddit."""
    print_header("🗄️  DÉPLOIEMENT SCHÉMA POSTGRESQL")
    
    src_file = Path('/home/claude/hypeddit_schema.py')
    dst_file = Path('src/database/hypeddit_schema.py')
    
    try:
        if src_file.exists():
            shutil.copy(src_file, dst_file)
            print_success(f"Schéma copié: {dst_file}")
            return True
        else:
            print_error("Fichier schéma non trouvé")
            return False
    except Exception as e:
        print_error(f"Erreur copie schéma: {e}")
        return False


def deploy_dag():
    """Déploie le DAG Airflow Hypeddit."""
    print_header("⚙️  DÉPLOIEMENT DAG AIRFLOW")
    
    src_file = Path('/home/claude/hypeddit_daily.py')
    dst_file = Path('airflow/dags/hypeddit_daily.py')
    
    try:
        if src_file.exists():
            shutil.copy(src_file, dst_file)
            print_success(f"DAG copié: {dst_file}")
            return True
        else:
            print_error("Fichier DAG non trouvé")
            return False
    except Exception as e:
        print_error(f"Erreur copie DAG: {e}")
        return False


def deploy_view():
    """Déploie la vue Streamlit Hypeddit."""
    print_header("📊 DÉPLOIEMENT VUE STREAMLIT")
    
    src_file = Path('/home/claude/hypeddit_view.py')
    dst_file = Path('src/dashboard/views/hypeddit.py')
    
    try:
        if src_file.exists():
            shutil.copy(src_file, dst_file)
            print_success(f"Vue copié: {dst_file}")
            return True
        else:
            print_error("Fichier vue non trouvé")
            return False
    except Exception as e:
        print_error(f"Erreur copie vue: {e}")
        return False


def create_tables():
    """Crée les tables PostgreSQL pour Hypeddit."""
    print_header("🔧 CRÉATION TABLES POSTGRESQL")
    
    try:
        sys.path.append(str(Path.cwd()))
        from src.database.hypeddit_schema import create_hypeddit_tables
        
        create_hypeddit_tables()
        print_success("Tables créées avec succès")
        return True
    except Exception as e:
        print_error(f"Erreur création tables: {e}")
        print_warning("Vous pouvez créer les tables manuellement:")
        print_info("python src/database/hypeddit_schema.py")
        return False


def update_dashboard():
    """Met à jour le dashboard principal pour inclure Hypeddit."""
    print_header("🎨 MISE À JOUR DASHBOARD")
    
    app_file = Path('src/dashboard/app.py')
    
    if not app_file.exists():
        print_error("Fichier app.py non trouvé")
        return False
    
    try:
        # Lire le fichier
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si Hypeddit est déjà ajouté
        if '"📱 Hypeddit"' in content:
            print_warning("Hypeddit déjà présent dans le dashboard")
            return True
        
        # Ajouter Hypeddit dans le menu de navigation
        if 'pages = {' in content:
            # Trouver la position après le dernier item du menu
            lines = content.split('\n')
            new_lines = []
            
            for i, line in enumerate(lines):
                new_lines.append(line)
                
                # Ajouter après la ligne "🎵 Spotify & S4A"
                if '"🎵 Spotify & S4A": "spotify_s4a_combined",' in line:
                    new_lines.append('        "📱 Hypeddit": "hypeddit",')
            
            content = '\n'.join(new_lines)
            
            # Ajouter l'import et le elif pour la page
            if 'elif page == "spotify_s4a_combined":' in content:
                import_section = content.find('elif page == "spotify_s4a_combined":')
                insert_pos = content.find('\n', content.find('show()', import_section)) + 1
                
                new_code = '''    
    elif page == "hypeddit":
        from views.hypeddit import show
        show()
'''
                content = content[:insert_pos] + new_code + content[insert_pos:]
            
            # Sauvegarder
            backup_file = app_file.with_suffix('.py.backup')
            shutil.copy(app_file, backup_file)
            print_info(f"Backup créé: {backup_file}")
            
            with open(app_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print_success("Dashboard mis à jour")
            return True
        else:
            print_warning("Structure du dashboard non reconnue")
            print_info("Ajoutez manuellement Hypeddit au menu de navigation")
            return False
            
    except Exception as e:
        print_error(f"Erreur mise à jour dashboard: {e}")
        return False


def update_env_file():
    """Met à jour le fichier .env avec les variables Hypeddit."""
    print_header("🔐 CONFIGURATION VARIABLES D'ENVIRONNEMENT")
    
    env_file = Path('.env')
    
    if not env_file.exists():
        print_warning("Fichier .env non trouvé, création...")
        env_file.touch()
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'HYPEDDIT_API_KEY' in content:
            print_warning("HYPEDDIT_API_KEY déjà présent dans .env")
        else:
            with open(env_file, 'a', encoding='utf-8') as f:
                f.write('\n# Hypeddit API\n')
                f.write('HYPEDDIT_API_KEY=YOUR_API_KEY_HERE\n')
            print_success("Variables Hypeddit ajoutées au .env")
        
        print_info("N'oubliez pas de remplir votre clé API Hypeddit!")
        return True
        
    except Exception as e:
        print_error(f"Erreur mise à jour .env: {e}")
        return False


def update_airflow_trigger():
    """Met à jour le trigger Airflow pour inclure Hypeddit."""
    print_header("🚀 MISE À JOUR AIRFLOW TRIGGER")
    
    trigger_file = Path('src/utils/airflow_trigger.py')
    
    if not trigger_file.exists():
        print_error("Fichier airflow_trigger.py non trouvé")
        return False
    
    try:
        with open(trigger_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "'hypeddit_daily'" in content:
            print_warning("hypeddit_daily déjà dans la liste des DAGs")
            return True
        
        # Trouver la liste des DAGs
        if "dags = [" in content:
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                new_lines.append(line)
                
                # Ajouter après s4a_csv_watcher
                if "'s4a_csv_watcher'," in line:
                    new_lines.append("            'hypeddit_daily',")
            
            content = '\n'.join(new_lines)
            
            # Backup
            backup_file = trigger_file.with_suffix('.py.backup')
            shutil.copy(trigger_file, backup_file)
            
            with open(trigger_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print_success("Airflow trigger mis à jour")
            return True
        else:
            print_warning("Structure du trigger non reconnue")
            return False
            
    except Exception as e:
        print_error(f"Erreur mise à jour trigger: {e}")
        return False


def print_next_steps():
    """Affiche les prochaines étapes."""
    print_header("📝 PROCHAINES ÉTAPES")
    
    print("""
1️⃣  Configurer votre API key Hypeddit dans .env:
   {OKCYAN}HYPEDDIT_API_KEY=votre_clé_api{ENDC}

2️⃣  Vérifier la documentation de l'API Hypeddit:
   - URL de base de l'API
   - Endpoints disponibles
   - Format des réponses
   - Adapter src/collectors/hypeddit_collector.py si nécessaire

3️⃣  Redémarrer les services Docker:
   {OKGREEN}docker-compose restart{ENDC}

4️⃣  Créer les tables PostgreSQL (si pas déjà fait):
   {OKGREEN}python src/database/hypeddit_schema.py{ENDC}

5️⃣  Tester la collecte:
   {OKGREEN}python src/collectors/hypeddit_collector.py{ENDC}

6️⃣  Lancer la collecte depuis le dashboard Streamlit:
   - Aller sur http://localhost:8501
   - Cliquer sur "🚀 Lancer toutes les collectes"
   - Ou lancer manuellement le DAG Hypeddit

7️⃣  Visualiser les données:
   - Accéder à la page "📱 Hypeddit" dans le dashboard

📚 Ressources:
   - Documentation Hypeddit: https://hypeddit.com/api-docs (à vérifier)
   - Airflow UI: http://localhost:8080
   - Dashboard: http://localhost:8501
    """.format(
        OKCYAN=Colors.OKCYAN,
        ENDC=Colors.ENDC,
        OKGREEN=Colors.OKGREEN
    ))


def main():
    """Fonction principale."""
    print_header("🎵 INSTALLATION INTÉGRATION HYPEDDIT")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Vérifier la structure
    if not check_project_structure():
        print_error("Structure du projet invalide. Arrêt.")
        sys.exit(1)
    
    # Déployer les composants
    success_count = 0
    total_count = 7
    
    if deploy_collector():
        success_count += 1
    
    if deploy_schema():
        success_count += 1
    
    if deploy_dag():
        success_count += 1
    
    if deploy_view():
        success_count += 1
    
    if update_dashboard():
        success_count += 1
    
    if update_env_file():
        success_count += 1
    
    if update_airflow_trigger():
        success_count += 1
    
    # Tentative de création des tables
    # (optionnel, peut échouer si DB pas accessible)
    try:
        create_tables()
    except:
        print_warning("Création tables ignorée (DB non accessible?)")
    
    # Résumé
    print_header("📊 RÉSUMÉ INSTALLATION")
    print(f"✅ {success_count}/{total_count} étapes réussies\n")
    
    if success_count == total_count:
        print_success("🎉 Installation complète réussie!")
        print_next_steps()
    else:
        print_warning(f"⚠️  {total_count - success_count} étape(s) ont échoué")
        print_info("Vérifiez les erreurs ci-dessus et réessayez")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()