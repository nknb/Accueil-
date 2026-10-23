# database/connection.py
"""Gestionnaire de connexion SQLite robuste — multi-postes réseau.

- journal_mode (WAL local / DELETE sur chemin UNC) appliqué UNE fois à l'initialisation
  (il est persistant dans le fichier); par connexion: busy_timeout, foreign_keys, synchronous
- Retry automatique sur "database is locked / busy" (backoff exponentiel + gigue)
- Écritures dans BEGIN IMMEDIATE; lectures simples sans transaction explicite
- Détection de perte réseau
"""

import sqlite3
import time
import random
import logging
from contextlib import closing, contextmanager
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
_TOKEN_BUSY_MS = 2000       # attente max de change_token (thread UI)
_ERROR_TOKEN  = (-1,)  # jeton renvoyé par change_token si la base est indisponible


_RETRY_MESSAGES = ("database is locked", "database is busy", "database table is locked", "unable to open")


def _retry_on_lock(fn):
    """Décorateur : relance fn jusqu'à _MAX_RETRIES fois si la DB est verrouillée ou occupée."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last_exc = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if any(m in msg for m in _RETRY_MESSAGES):
                    last_exc = exc
                    delay = min(_BASE_DELAY * (2 ** attempt), _MAX_DELAY)
                    delay += random.uniform(0, _JITTER)
                    logger.warning(
                        "DB verrouillée (tentative %d/%d), nouvel essai dans %.2fs — %s",
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

        # Compteur de version incrémenté par des déclencheurs à CHAQUE écriture (demandes, services, motifs):
        # les pages le comparent pour savoir s'il faut recharger. Indépendant de l'horloge des postes.
        version_sql = """
        CREATE TABLE IF NOT EXISTS app_meta (
            cle TEXT PRIMARY KEY,
            valeur INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO app_meta (cle, valeur) VALUES ('version', 0);
        """ + "".join(
            f"""
        CREATE TRIGGER IF NOT EXISTS trg_version_{table}_{evt}
        AFTER {evt.upper()} ON {table}
        BEGIN UPDATE app_meta SET valeur = valeur + 1 WHERE cle = 'version'; END;
        """
            for table in ("accueil_demandeaccueil", "accueil_service", "accueil_motif")
            for evt in ("insert", "update", "delete")
        )

        seed_sql = """
        INSERT INTO accueil_service (nom, description, actif, couleur)
        SELECT 'Service Général', 'Service par défaut', 1, '#417690'
        WHERE NOT EXISTS (SELECT 1 FROM accueil_service);

        INSERT INTO accueil_motif (nom, description, actif, priorite_defaut)
        SELECT 'Information', 'Motif par défaut', 1, 'normale'
        WHERE NOT EXISTS (SELECT 1 FROM accueil_motif);
        """

        try:
            with closing(sqlite3.connect(str(self.db_path), timeout=AppConfig.DB_TIMEOUT)) as conn:
                self._apply_pragmas(conn)
                self._init_journal_mode(conn)
                conn.executescript(schema_sql)
                conn.executescript(version_sql)
                conn.executescript(seed_sql)
                # Bases existantes: ajoute les colonnes de verrouillage si absentes
                cols = {r[1] for r in conn.execute("PRAGMA table_info(auth_user)")}
                for col, ddl in (("echecs", "INTEGER NOT NULL DEFAULT 0"), ("verrouille_jusqua", "TEXT")):
                    if col not in cols:
                        conn.execute(f"ALTER TABLE auth_user ADD COLUMN {col} {ddl}")
                conn.commit()
        except Exception as exc:
            # Non bloquant (poste hors ligne au démarrage), mais visible: les requêtes suivantes échoueront
            logger.error("Initialisation schéma minimal non appliquée: %s", exc)

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
            # Recherche d'usager (fiche dashboard) et requêtes `DATE(date) = ?` (index d'expression)
            "CREATE INDEX IF NOT EXISTS idx_demande_numero_cnps ON accueil_demandeaccueil(numero_cnps)",
            "CREATE INDEX IF NOT EXISTS idx_demande_nom_prenom_norm ON accueil_demandeaccueil(UPPER(TRIM(nom)), UPPER(TRIM(prenom)))",
            "CREATE INDEX IF NOT EXISTS idx_demande_date_created ON accueil_demandeaccueil(date, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_demande_date_jour ON accueil_demandeaccueil(DATE(date))",
        ]

        try:
            with closing(sqlite3.connect(str(self.db_path), timeout=AppConfig.DB_TIMEOUT)) as conn:
                self._apply_pragmas(conn)
                for stmt in index_statements:
                    try:
                        conn.execute(stmt)
                    except Exception as idx_err:
                        logger.warning("Index ignoré (%s): %s", stmt, idx_err)
                conn.commit()
        except Exception as exc:
            logger.warning("Initialisation des index non appliquée: %s", exc)

    # ── Application des PRAGMAs ───────────────────────────────────────────────

    _journal_pending = False  # True tant que le journal_mode voulu n'a pas pu être appliqué (base occupée)

    def _init_journal_mode(self, conn: sqlite3.Connection) -> None:
        """Fixe le journal_mode (WAL local / DELETE réseau) une seule fois: il est persistant dans le fichier.

        Si la base est occupée par un autre poste, on le note et `_connect` réessaiera à la prochaine connexion.
        """
        try:
            conn.execute(f"PRAGMA journal_mode = {self._pragmas['journal_mode']}").fetchone()
            self._journal_pending = False
        except sqlite3.Error as exc:
            self._journal_pending = True
            logger.warning("journal_mode non appliqué (base occupée ?), nouvel essai à la prochaine connexion: %s", exc)

    def _retenter_journal_mode(self, conn: sqlite3.Connection) -> None:
        """Nouvel essai sans attente (busy_timeout 0): ne ralentit jamais une requête normale."""
        try:
            conn.execute("PRAGMA busy_timeout = 0")
            self._init_journal_mode(conn)
        finally:
            conn.execute(f"PRAGMA busy_timeout = {self._pragmas['busy_timeout_ms']}")

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Applique les PRAGMAs propres à chaque connexion (le journal_mode est persistant: voir _init_journal_mode)."""
        p = self._pragmas
        conn.execute(f"PRAGMA busy_timeout = {p['busy_timeout_ms']}")
        conn.execute(f"PRAGMA foreign_keys = {p['foreign_keys']}")
        conn.execute(f"PRAGMA synchronous = {p['synchronous']}")

    # ── Gestionnaire de connexion ─────────────────────────────────────────────

    def _connect(self, busy_ms: Optional[int] = None) -> sqlite3.Connection:
        """Ouvre une connexion en autocommit (transactions gérées à la main) avec les PRAGMAs par connexion."""
        self._assert_network()
        timeout = AppConfig.DB_TIMEOUT if busy_ms is None else busy_ms / 1000
        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            timeout=timeout,
            isolation_level=None,
        )
        try:
            conn.row_factory = sqlite3.Row
            # LIKE/lower() de SQLite ne gèrent la casse que sur l'ASCII: « É » ne serait pas trouvé par « é »
            conn.create_function("PYLOWER", 1, lambda v: v.lower() if isinstance(v, str) else v, deterministic=True)
            self._apply_pragmas(conn)
            if self._journal_pending:
                self._retenter_journal_mode(conn)
            if busy_ms is not None:
                conn.execute(f"PRAGMA busy_timeout = {int(busy_ms)}")
        except Exception:
            conn.close()
            raise
        return conn

    @contextmanager
    def get_connection(self, write: bool = False):
        """Fournit une connexion avec gestion de contexte.

        Args:
            write: Si True, ouvre une transaction BEGIN IMMEDIATE (verrou d'écriture
                   dès l'ouverture, évite les deadlocks en écriture multi-postes).
                   Sinon BEGIN DEFERRED: snapshot cohérent pour plusieurs SELECT
                   successifs (pour une seule lecture, préférer execute_query).
        """
        conn = None
        try:
            conn = self._connect()

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
        """Exécute une requête SELECT et retourne les résultats.

        Un SELECT seul est déjà cohérent (snapshot implicite): pas de BEGIN/COMMIT.
        """
        return self._read(query, params)

    def _read(self, query: str, params: tuple = (), busy_ms: Optional[int] = None) -> List[Dict]:
        with closing(self._connect(busy_ms)) as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

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

    def change_token(self) -> tuple:
        """Empreinte légère des données: change dès qu'une demande, un service ou un motif est écrit.

        Lecture d'une seule ligne (compteur `app_meta.version` tenu par des déclencheurs SQL): coût constant
        quelle que soit la taille de la base, et indépendant de l'horloge de chaque poste. Les pages la
        comparent à la précédente pour ne recharger (et redessiner) que s'il y a du nouveau, au lieu de
        relire toutes les lignes toutes les quelques secondes depuis chaque poste.

        Robustesse (appelée depuis le thread UI, ne lève jamais): si la table est absente, la base
        verrouillée (attente max 2 s, sans retry) ou inaccessible, renvoie le jeton d'erreur constant
        ``(-1,)``. Les pages ne rechargent alors qu'une fois (jeton différent du précédent),
        puis restent stables jusqu'au retour de la base.
        """
        try:
            rows = self._read("SELECT valeur FROM app_meta WHERE cle = 'version'", busy_ms=_TOKEN_BUSY_MS)
        except (sqlite3.Error, OSError, RuntimeError) as exc:
            logger.warning("change_token indisponible: %s", exc)
            return _ERROR_TOKEN
        return (rows[0]["valeur"],) if rows else _ERROR_TOKEN

    def table_exists(self, table_name: str) -> bool:
        """Vérifie si une table existe."""
        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return len(result) > 0

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
