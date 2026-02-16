# database/connection.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Importer la configuration centralisée
from config import AppConfig


class DatabaseConnection:
    """Gestionnaire de connexion SQLite optimisé"""
    
    def __init__(self, db_path: str = None):
        """Initialise la connexion à la base de données
        
        Args:
            db_path: Chemin personnalisé vers la BD (optionnel)
        """
        if db_path is None:
            self.db_path = AppConfig.get_db_path()
        else:
            self.db_path = Path(db_path)
    
    @contextmanager
    def get_connection(self):
        """Fournit une connexion SQLite avec gestion de contexte
        
        Yields:
            sqlite3.Connection: Connexion à la base de données
        """
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                timeout=AppConfig.DB_TIMEOUT
            )
            conn.row_factory = sqlite3.Row
            
            if AppConfig.DB_FOREIGN_KEYS:
                conn.execute("PRAGMA foreign_keys = ON")
            if AppConfig.DB_WAL_MODE:
                conn.execute("PRAGMA journal_mode = WAL")
            
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Exécute une requête et retourne les résultats"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Exécute une insertion et retourne l'ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Exécute une mise à jour et retourne le nombre de lignes affectées"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Exécute plusieurs requêtes"""
        with self.get_connection() as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
    
    def table_exists(self, table_name: str) -> bool:
        """Vérifie si une table existe"""
        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return len(result) > 0

# Instance globale UNIQUE
db = DatabaseConnection()