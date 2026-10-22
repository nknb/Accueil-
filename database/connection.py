# database/connection.py
"""Gestionnaire de connexion SQLite robuste — multi-postes réseau.

Améliorations vs version précédente :
- PRAGMAs adaptatifs (WAL local / DELETE sur chemin UNC)
- Retry automatique sur OperationalError "database is locked" (backoff exponentiel)
- Toutes les écritures dans BEGIN IMMEDIATE (isolement strict)
- Détection de perte réseau avec reconnexion gracieuse
"""

import sqlite3
import time
import random
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from config import AppConfig

logger = logging.getLogger("db")


# ── Constantes retry ──────────────────────────────────────────────────────────

_MAX_RETRIES  = 5           # nombre maximum de tentatives
_BASE_DELAY   = 0.1         # délai initial en secondes
_MAX_DELAY    = 3.0         # délai maximum en secondes
_JITTER       = 0.05        # gigue aléatoire pour éviter les convois


def _retry_on_lock(fn):
    """Décorateur : relance fn jusqu'à _MAX_RETRIES fois si la DB est verrouillée."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last_exc = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "database is locked" in msg or "unable to open" in msg:
                    last_exc = exc
                    delay = min(_BASE_DELAY * (2 ** attempt), _MAX_DELAY)
                    delay += random.uniform(0, _JITTER)
                    logger.warning(
                        "DB locked (tentative %d/%d), retry dans %.2fs — %s",
                        attempt + 1, _MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)
                else:
                    raise
        raise sqlite3.OperationalError(
            f"Base inaccessible après {_MAX_RETRIES} tentatives"
        ) from last_exc

    return wrapper


# ── Gestionnaire principal ────────────────────────────────────────────────────

class DatabaseConnection:
    """Gestionnaire de connexion SQLite optimisé pour un accès multi-postes réseau."""

    def __init__(self, db_path: str = None):
        self.db_path = self._resolve_db_path(db_path)
        self._pragmas = AppConfig.get_sqlite_pragmas(self.db_path)
        self._ensure_minimum_schema()
        self._ensure_performance_indexes()

    # ── Résolution du chemin ──────────────────────────────────────────────────

    def _resolve_db_path(self, db_path: Optional[str]) -> Path:
        if db_path:
            return Path(db_path)
        return AppConfig.get_db_path()

    # ── Vérification réseau ───────────────────────────────────────────────────

    def _check_network(self) -> bool:
        """Retourne True si le chemin parent de la DB est accessible."""
        parent = self.db_path.parent
        try:
            return parent.exists()
        except OSError:
            return False

    def _assert_network(self):
        """Lève une RuntimeError si le partage réseau est inaccessible."""
        db_str = str(self.db_path)
        is_network = db_str.startswith("\\\\") or "//" in db_str
        if is_network and not self._check_network():
            raise RuntimeError(
                f"Partage réseau inaccessible : {self.db_path.parent}\n"
                "Vérifiez la connexion réseau ou montez le partage manuellement."
            )

    # ── Helpers statiques ─────────────────────────────────────────────────────

    def _has_table(self, db_path: Path, table_name: str) -> bool:
        """Vérifie l'existence d'une table via la connexion gérée (sans rouvrir)."""
        try:
            rows = self.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return len(rows) > 0
        except Exception:
            return False

    # ── Schéma minimal ────────────────────────────────────────────────────────

    def _ensure_minimum_schema(self):
        """Crée le schéma minimal requis (idempotent)."""
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(150) NOT NULL UNIQUE,
            password VARCHAR(128) NOT NULL,
            email VARCHAR(254) NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            is_superuser BOOLEAN NOT NULL DEFAULT 0,
            is_staff BOOLEAN NOT NULL DEFAULT 0,
            date_joined DATETIME NOT NULL,
            last_login DATETIME,
            role VARCHAR(20) DEFAULT 'preaccueil',
            echecs INTEGER NOT NULL DEFAULT 0,
            verrouille_jusqua TEXT
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
            conn = sqlite3.connect(str(self.db_path), timeout=AppConfig.DB_TIMEOUT)
            self._apply_pragmas(conn)
            conn.executescript(schema_sql)
            conn.executescript(seed_sql)
            # Bases existantes: ajoute les colonnes de verrouillage si absentes
            cols = {r[1] for r in conn.execute("PRAGMA table_info(auth_user)")}
            for col, ddl in (("echecs", "INTEGER NOT NULL DEFAULT 0"), ("verrouille_jusqua", "TEXT")):
                if col not in cols:
                    conn.execute(f"ALTER TABLE auth_user ADD COLUMN {col} {ddl}")
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Initialisation schéma minimal non appliquée: %s", exc)

    # ── Index de performance ──────────────────────────────────────────────────

    def _ensure_performance_indexes(self):
        """Crée les index SQLite utiles aux écrans principaux (idempotent)."""
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
            conn = sqlite3.connect(str(self.db_path), timeout=AppConfig.DB_TIMEOUT)
            self._apply_pragmas(conn)
            for stmt in index_statements:
                try:
                    conn.execute(stmt)
                except Exception as idx_err:
                    logger.debug("Index ignoré (%s): %s", stmt, idx_err)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Initialisation des index non appliquée: %s", exc)

    # ── Application des PRAGMAs ───────────────────────────────────────────────

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Applique les PRAGMAs adaptés au type de stockage (local / réseau UNC)."""
        p = self._pragmas
        conn.execute(f"PRAGMA journal_mode = {p['journal_mode']}")
        conn.execute(f"PRAGMA busy_timeout = {p['busy_timeout_ms']}")
        conn.execute(f"PRAGMA foreign_keys = {p['foreign_keys']}")
        conn.execute(f"PRAGMA synchronous = {p['synchronous']}")

    # ── Gestionnaire de connexion ─────────────────────────────────────────────

    @contextmanager
    def get_connection(self, write: bool = False):
        """Fournit une connexion avec gestion de contexte.

        Args:
            write: Si True, ouvre une transaction BEGIN IMMEDIATE (verrou exclusif
                   dès l'ouverture, évite les deadlocks en écriture multi-postes).
        """
        self._assert_network()
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                timeout=AppConfig.DB_TIMEOUT,
                isolation_level=None,   # autocommit — on gère les transactions manuellement
            )
            conn.row_factory = sqlite3.Row
            self._apply_pragmas(conn)

            if write:
                conn.execute("BEGIN IMMEDIATE")
            else:
                conn.execute("BEGIN DEFERRED")

            yield conn

            conn.execute("COMMIT")
        except Exception as exc:
            if conn:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
            raise exc
        finally:
            if conn:
                conn.close()

    # ── API publique ──────────────────────────────────────────────────────────

    @_retry_on_lock
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Exécute une requête SELECT et retourne les résultats."""
        with self.get_connection(write=False) as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @_retry_on_lock
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Exécute un INSERT dans une transaction IMMEDIATE et retourne lastrowid."""
        with self.get_connection(write=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid

    @_retry_on_lock
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Exécute un UPDATE/DELETE dans une transaction IMMEDIATE."""
        with self.get_connection(write=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount

    @_retry_on_lock
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Exécute plusieurs écritures dans une transaction IMMEDIATE unique."""
        with self.get_connection(write=True) as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount

    def table_exists(self, table_name: str) -> bool:
        """Vérifie si une table existe."""
        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return len(result) > 0

    @_retry_on_lock
    def rollover_pending_to_non_traite(self) -> int:
        """Passe en 'non_traite' les demandes 'en_attente' des jours précédents."""
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
