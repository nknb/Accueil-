# utils/logger.py
"""Système de logging centralisé pour l'application"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


class LoggerSetup:
    """Classe pour configurer le système de logging"""
    
    # Dossier pour les logs
    LOG_DIR = Path(__file__).parent.parent / "logs"
    
    # Créer le dossier s'il n'existe pas
    LOG_DIR.mkdir(exist_ok=True)
    
    # Fichiers de log
    LOG_FILE = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    ERROR_LOG_FILE = LOG_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"
    
    @classmethod
    def setup_logger(cls, name: str, level=logging.INFO) -> logging.Logger:
        """Configure et retourne un logger
        
        Args:
            name: Nom du logger
            level: Niveau de log (default: INFO)
            
        Returns:
            logging.Logger: Logger configuré
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Éviter les doublons de handlers
        if logger.hasHandlers():
            return logger
        
        # Format du log
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler pour tous les logs
        file_handler = logging.handlers.RotatingFileHandler(
            cls.LOG_FILE,
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Handler pour les erreurs uniquement
        error_handler = logging.handlers.RotatingFileHandler(
            cls.ERROR_LOG_FILE,
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        
        # Handler pour la console (en développement)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger


# Logger global pour l'application
app_logger = LoggerSetup.setup_logger("CNPS-Accueil")
db_logger = LoggerSetup.setup_logger("CNPS-Accueil.Database")
auth_logger = LoggerSetup.setup_logger("CNPS-Accueil.Auth")
ui_logger = LoggerSetup.setup_logger("CNPS-Accueil.UI")
