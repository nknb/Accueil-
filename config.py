# config.py
"""Configuration centralisée de l'application"""

from pathlib import Path
from typing import Optional


class AppConfig:
    """Configuration centralisée pour l'application"""

    # Chemins de base
    APP_ROOT = Path(__file__).parent
    DB_PATHS = [
        APP_ROOT / "db.sqlite3",  # Chemin principal
        APP_ROOT.parent / "db.sqlite3",  # Un niveau au-dessus
        Path.cwd() / "db.sqlite3",  # Répertoire courant
    ]

    @classmethod
    def get_db_path(cls) -> Path:
        """Trouve et retourne le chemin vers la BD SQLite
        
        Returns:
            Path: Chemin vers la base de données
        """
        for db_path in cls.DB_PATHS:
            if db_path.exists():
                print(f"✅ Base de données trouvée: {db_path}")
                return db_path

        # Si aucune base n'existe, utiliser le chemin par défaut
        default_path = cls.DB_PATHS[0]
        print(f"⚠️ Aucune base trouvée, utilisation: {default_path}")
        return default_path

    @classmethod
    def get_style_path(cls) -> Optional[Path]:
        """Retourne le chemin vers le fichier de style QSS
        
        Returns:
            Optional[Path]: Chemin vers style.qss si trouvé, None sinon
        """
        style_path = cls.APP_ROOT / "sidebar" / "style.qss"
        if style_path.exists():
            print(f"✅ Style trouvé: {style_path}")
            return style_path
        print(f"⚠️ Style non trouvé: {style_path}")
        return None

    @classmethod
    def get_resource_path(cls, resource_name: str) -> Optional[Path]:
        """Retourne le chemin vers une ressource
        
        Args:
            resource_name: Nom de la ressource (ex: "icon.png")
            
        Returns:
            Optional[Path]: Chemin vers la ressource si trouvée
        """
        resource_path = cls.APP_ROOT / "resources" / resource_name
        if resource_path.exists():
            return resource_path
        return None

    # Configuration de l'application
    APP_NAME = "CNPS - Système de Gestion d'Accueil"
    APP_VERSION = "1.0.0"

    # Configuration de la base de données
    DB_TIMEOUT = 30
    DB_WAL_MODE = True
    DB_FOREIGN_KEYS = True

    # Configuration de l'UI
    MIN_WINDOW_WIDTH = 1400
    MIN_WINDOW_HEIGHT = 800
    REFRESH_INTERVAL = 60000  # en millisecondes

    # Rôles utilisateur
    ROLES = {
        'admin': {'level': 100, 'display': '👑 Administrateur'},
        'manager': {'level': 80, 'display': '📊 Manager'},
        'accueil': {'level': 50, 'display': '🏢 Agent d\'accueil'},
        'preaccueil': {'level': 30, 'display': '🛂 Pré-accueil'},
    }

    # Configuration d'authentification
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 300000  # en millisecondes (5 minutes)

    # Utilisateurs par défaut
    DEFAULT_USERS = [
        {
            'username': 'admin',
            'password': 'admin123',
            'email': 'admin@cnps.ci',
            'role': 'admin',
        },
        {
            'username': 'manager',
            'password': 'manager123',
            'email': 'manager@cnps.ci',
            'role': 'manager',
        },
        {
            'username': 'accueil',
            'password': 'accueil123',
            'email': 'accueil@cnps.ci',
            'role': 'accueil',
        },
        {
            'username': 'preaccueil',
            'password': 'preaccueil123',
            'email': 'preaccueil@cnps.ci',
            'role': 'preaccueil',
        },
    ]
