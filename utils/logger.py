# utils/logger.py
"""Système de logging centralisé pour l'application"""

import logging
import logging.handlers
import sys
import tempfile
from pathlib import Path


class LoggerSetup:
    """Classe pour configurer le système de logging"""
    
    @staticmethod
    def _resolve_log_dir():
        """Dossier de logs inscriptible, sinon None (console seule)"""
        # Gelé (PyInstaller/Nuitka): __file__ pointe vers un dossier temporaire
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
        for candidate in (base / "logs", Path(tempfile.gettempdir()) / "cnps-accueil-logs"):
            try:
                candidate.mkdir(exist_ok=True)
                with tempfile.TemporaryFile(dir=candidate):
                    pass
                return candidate
            except OSError:
                continue
        return None

    LOG_DIR = _resolve_log_dir.__func__()

    # Fichiers de log (rotation quotidienne: app.log, app.log.AAAA-MM-JJ)
    LOG_FILE = LOG_DIR / "app.log" if LOG_DIR else None
    ERROR_LOG_FILE = LOG_DIR / "error.log" if LOG_DIR else None

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
        
        if cls.LOG_DIR:
            for fichier, niveau in ((cls.LOG_FILE, level), (cls.ERROR_LOG_FILE, logging.ERROR)):
                handler = logging.handlers.TimedRotatingFileHandler(
                    fichier, when='midnight', backupCount=30, encoding='utf-8', delay=True
                )
                handler.setLevel(niveau)
                handler.setFormatter(formatter)
                logger.addHandler(handler)
        
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
