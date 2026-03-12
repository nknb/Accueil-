# database/connection.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from config import AppConfig

class DatabaseConnection:
    """Gestionnaire de connexion SQLite optimisé"""
    
    def __init__(self, db_path: str = None):
        self.db_path = self._resolve_db_path(db_path)
        self._ensure_minimum_schema()
        self._ensure_performance_indexes()

    def _resolve_db_path(self, db_path: Optional[str]) -> Path:
        """Résout le meilleur fichier DB disponible.

        Priorité:
        1) chemin explicite fourni
        2) base locale de l'application (même dossier que main.py)
        """
        if db_path:
            return Path(db_path)
        return AppConfig.get_db_path()

    @staticmethod
    def _has_table(db_path: Path, table_name: str) -> bool:
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            row = cur.fetchone()
            conn.close()
            return row is not None
        except Exception:
            return False

    def _ensure_minimum_schema(self):
        """Crée le schéma minimal requis pour éviter les erreurs de sync."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS accueil_service (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            description TEXT DEFAULT '',
            actif INTEGER DEFAULT 1,
            couleur TEXT DEFAULT '#417690'
        );

        CREATE TABLE IF NOT EXISTS accueil_motif (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            description TEXT DEFAULT '',
            actif INTEGER DEFAULT 1,
            priorite_defaut TEXT DEFAULT 'normale'
        );

        CREATE TABLE IF NOT EXISTS accueil_demandeaccueil (
            id TEXT PRIMARY KEY,
            date TEXT,
            nom TEXT,
            prenom TEXT,
            numero_cnps TEXT,
            service_demande_id INTEGER,
            motif_id INTEGER,
            priorite TEXT DEFAULT 'normale',
            statut TEXT DEFAULT 'en_attente',
            satisfaction INTEGER,
            commentaire_satisfaction TEXT,
            heure_arrivee TEXT,
            heure_reception TEXT,
            temps_attente TEXT,
            delai_objectif INTEGER DEFAULT 0,
            contacts TEXT,
            agent_accueil_id INTEGER,
            observations TEXT,
            created_at TEXT,
            updated_at TEXT,
            traite_le TEXT
        );

        CREATE TABLE IF NOT EXISTS auth_user (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'preaccueil',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_superuser INTEGER NOT NULL DEFAULT 0,
            is_staff INTEGER NOT NULL DEFAULT 0,
            last_login TEXT,
            date_joined TEXT,
            nom TEXT,
            prenom TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """

        seed_sql = """
        INSERT INTO accueil_service (nom, description, actif, couleur)
        SELECT 'Service Général', 'Service par défaut', 1, '#417690'
        WHERE NOT EXISTS (SELECT 1 FROM accueil_service);

        INSERT INTO accueil_motif (nom, description, actif, priorite_defaut)
        SELECT 'Information', 'Motif par défaut', 1, 'normale'
        WHERE NOT EXISTS (SELECT 1 FROM accueil_motif);
        """

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            conn.executescript(schema_sql)
            conn.executescript(seed_sql)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Initialisation schéma minimal non appliquée: {e}")

    def _ensure_performance_indexes(self):
        """Crée les index SQLite utiles aux écrans principaux."""
        if not self._has_table(self.db_path, "accueil_demandeaccueil"):
            return

        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_demande_date ON accueil_demandeaccueil(date)",
            "CREATE INDEX IF NOT EXISTS idx_demande_statut ON accueil_demandeaccueil(statut)",
            "CREATE INDEX IF NOT EXISTS idx_demande_service_demande_id ON accueil_demandeaccueil(service_demande_id)",
            "CREATE INDEX IF NOT EXISTS idx_demande_motif_id ON accueil_demandeaccueil(motif_id)",
            "CREATE INDEX IF NOT EXISTS idx_demande_created_at ON accueil_demandeaccueil(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_demande_updated_at ON accueil_demandeaccueil(updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_demande_delai_objectif ON accueil_demandeaccueil(delai_objectif)",
            "CREATE INDEX IF NOT EXISTS idx_demande_date_statut ON accueil_demandeaccueil(date, statut)",
        ]

        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            for statement in index_statements:
                try:
                    conn.execute(statement)
                except Exception as idx_error:
                    print(f"⚠️ Index ignoré ({statement}): {idx_error}")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Initialisation des index non appliquée: {e}")
    
    @contextmanager
    def get_connection(self):
        """Fournit une connexion avec gestion de contexte"""
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                timeout=AppConfig.DB_TIMEOUT
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(f"PRAGMA busy_timeout = {int(AppConfig.DB_TIMEOUT * 1000)}")
            conn.execute("PRAGMA synchronous = NORMAL")
            
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

    def rollover_pending_to_non_traite(self) -> int:
        """Passe automatiquement en 'non_traite' les demandes 'en_attente' des jours précédents."""
        today_str = datetime.now().date().isoformat()
        query = """
            UPDATE accueil_demandeaccueil
            SET statut = 'non_traite',
                updated_at = ?
            WHERE statut = 'en_attente'
              AND DATE(date) < DATE(?)
        """
        return self.execute_update(query, (datetime.now().isoformat(), today_str))

# Instance globale UNIQUE
db = DatabaseConnection()