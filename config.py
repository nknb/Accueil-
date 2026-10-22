# config.py
"""Configuration centralisée de l'application"""

from pathlib import Path
from typing import Optional
import json
import os
import sys


class AppConfig:
    """Configuration centralisée pour l'application"""

    # Chemins de base
    APP_ROOT = Path(__file__).parent
    DB_PATHS = [
        APP_ROOT / "db.sqlite3",  # Base UNIQUE de l'application (même dossier que main.py)
    ]

    DB_ENV_VAR = "CNPS_DB_PATH"

    # Fichier de configuration persistante (chemin DB personnalisé)
    DB_CONFIG_FILE = APP_ROOT / "db_config.json"

    # Chemin réseau par défaut de production
    DEFAULT_NETWORK_DB = "//srvgagnoa/prod/datagagnoa/accueil/db.sqlite3"

    @classmethod
    def _runtime_dir(cls) -> Path:
        """Retourne le dossier runtime de l'application (source ou exe)."""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return cls.APP_ROOT

    @staticmethod
    def _is_writable_dir(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".cnps_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    @classmethod
    def get_db_path(cls) -> Path:
        """Trouve et retourne le chemin vers la BD SQLite.

        Priorité :
          1. db_config.json (configuré via l'onglet Configuration)
          2. Variable d'environnement CNPS_DB_PATH
          3. Base locale (dossier runtime / APP_ROOT)

        Returns:
            Path: Chemin vers la base de données
        """
        # 1. Chemin configuré manuellement via l'onglet Configuration
        if cls.DB_CONFIG_FILE.exists():
            try:
                data = json.loads(cls.DB_CONFIG_FILE.read_text(encoding="utf-8"))
                custom = data.get("custom_db_path", "").strip()
                if custom:
                    candidate = Path(custom)
                    print(f"[CONFIG] Chemin base de données configuré : {candidate}")
                    return candidate
            except Exception as e:
                print(f"[WARN] Lecture db_config.json échouée : {e}")

        runtime_db = cls._runtime_dir() / "db.sqlite3"

        # Mode exécutable: base strictement locale au dossier de l'application
        # (portable: la donnée suit le dossier dist lors d'une copie sur un autre poste).
        if getattr(sys, "frozen", False):
            if runtime_db.exists():
                print(f"[OK] Base exécutable trouvée: {runtime_db}")
            else:
                print(f"[WARN] Aucune base exécutable, utilisation: {runtime_db}")
            return runtime_db

        env_db_path = os.getenv(cls.DB_ENV_VAR, "").strip().strip('"').strip("'")
        if env_db_path:
            candidate = Path(env_db_path).expanduser()
            if candidate.exists():
                print(f"[OK] Base de données (env {cls.DB_ENV_VAR}) trouvée: {candidate}")
                return candidate
            print(f"[WARN] Chemin env {cls.DB_ENV_VAR} introuvable: {candidate}")

        user_db = Path(os.getenv("LOCALAPPDATA", str(cls.APP_ROOT))) / "CNPSAccueil" / "db.sqlite3"

        for db_path in [runtime_db, *cls.DB_PATHS, user_db]:
            if db_path.exists():
                print(f"[OK] Base de données trouvée: {db_path}")
                return db_path

        # Si aucune base n'existe, choisir un emplacement writable
        runtime_dir = cls._runtime_dir()
        if cls._is_writable_dir(runtime_dir):
            default_path = runtime_db
        else:
            user_dir = user_db.parent
            user_dir.mkdir(parents=True, exist_ok=True)
            default_path = user_db

        print(f"[WARN] Aucune base trouvée, utilisation: {default_path}")
        return default_path

    @staticmethod
    def get_sqlite_pragmas(db_path: Path) -> dict:
        """Retourne les PRAGMA SQLite adaptés au type de stockage.

        - Dossier local: WAL pour de meilleures performances.
        - Partage réseau UNC: DELETE pour éviter les problèmes de WAL sur SMB.
        """
        db_str = str(db_path).replace("\\", "/")
        is_unc_path = db_str.startswith("//") or str(db_path).startswith("\\\\")

        return {
            "journal_mode": "DELETE" if is_unc_path else "WAL",
            "busy_timeout_ms": int(AppConfig.DB_TIMEOUT * 1000),
            "foreign_keys": "ON",
            "synchronous": "NORMAL",
        }

    @classmethod
    def get_style_path(cls) -> Optional[Path]:
        """Retourne le chemin vers le fichier de style QSS
        
        Returns:
            Optional[Path]: Chemin vers style.qss si trouvé, None sinon
        """
        style_path = cls.APP_ROOT / "sidebar" / "style.qss"
        if style_path.exists():
            print(f"[OK] Style trouvé: {style_path}")
            return style_path
        print(f"[WARN] Style non trouvé: {style_path}")
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
    AUTO_REFRESH_INTERVAL_MS = 15000  # refresh discret des pages principales (était 5 s)
    DASHBOARD_KPI_REFRESH_INTERVAL_MS = 60000
    PREACCUEIL_CLOCK_INTERVAL_MS = 1000
    DASHBOARD_DEFAULT_PERIOD_DAYS = 30
    ACCUEIL_CACHE_TTL_SEC = 15
    PREACCUEIL_CACHE_TTL_SEC = 15
    DATABASE_CACHE_TTL_SEC = 20
    DASHBOARD_CACHE_TTL_SEC = 30
    ACCUEIL_DAILY_LIST_LIMIT = 20
    DASHBOARD_TOP_ITEMS_LIMIT = 5
    DASHBOARD_SLA_TOP_LIMIT = 3

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

    # Utilisateurs créés uniquement au PREMIER démarrage si la table est vide.
    # Ils ne sont jamais stockés en clair.
    DEFAULT_USERS = [
        {
            'username': 'admin',
            'email': 'admin@cnps.ci',
            'role': 'admin',
        },
        {
            'username': 'manager',
            'email': 'manager@cnps.ci',
            'role': 'manager',
        },
        {
            'username': 'accueil',
            'email': 'accueil@cnps.ci',
            'role': 'accueil',
        },
        {
            'username': 'preaccueil',
            'email': 'preaccueil@cnps.ci',
            'role': 'preaccueil',
        },
    ]
