"""Tests de la couche connexion / config (base temporaire uniquement)."""
import importlib.util
import json
import sqlite3
from pathlib import Path
from unittest import mock

from database import connection
from database.connection import db


def test_rollover_ne_cumule_pas_les_retries():
    """Un verrou persistant ne doit pas provoquer 5x5 tentatives."""
    with mock.patch.object(connection.time, "sleep"), mock.patch.object(
        db, "get_connection", side_effect=sqlite3.OperationalError("database is locked")
    ) as gc:
        try:
            db.rollover_pending_to_non_traite()
        except sqlite3.OperationalError:
            pass
    assert gc.call_count == connection._MAX_RETRIES


def test_rollover_ignore_date_nulle_ou_mal_formee():
    db.execute_update("DELETE FROM accueil_demandeaccueil")
    for i, d in enumerate([None, "n'importe quoi", "2000-01-01"]):
        db.execute_insert(
            "INSERT INTO accueil_demandeaccueil (id, date, statut) VALUES (?, ?, 'en_attente')",
            (f"T{i}", d),
        )
    assert db.rollover_pending_to_non_traite() == 1
    db.execute_update("DELETE FROM accueil_demandeaccueil")


def test_chemin_relatif_db_config_resolu_depuis_runtime(tmp_path, monkeypatch):
    # conftest remplace AppConfig.get_db_path: on recharge une copie vierge de config.py
    spec = importlib.util.spec_from_file_location(
        "config_fresh", Path(__file__).resolve().parent.parent / "config.py"
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    cfg = tmp_path / "db_config.json"
    cfg.write_text(json.dumps({"custom_db_path": "data/x.sqlite3"}), encoding="utf-8")
    monkeypatch.setattr(fresh.AppConfig, "DB_CONFIG_FILE", cfg)
    monkeypatch.chdir(tmp_path)  # le résultat ne doit pas dépendre du dossier courant
    assert fresh.AppConfig.get_db_path() == fresh.AppConfig.APP_ROOT / "data/x.sqlite3"


def test_change_token_change_a_chaque_ecriture_sur_les_demandes():
    from datetime import date
    from database.connection import db
    from database.models import DemandeAccueil
    t0 = db.change_token()
    assert db.change_token() == t0                      # stable sans écriture
    d = DemandeAccueil(nom="TOKEN", date=date(2014, 1, 2))
    d.save()
    t1 = db.change_token()
    assert t1 != t0                                     # insertion
    d.statut = "traite"
    d.save()
    t2 = db.change_token()
    assert t2 != t1                                     # modification (updated_at)
    db.execute_update("DELETE FROM accueil_demandeaccueil WHERE id = ?", (d.id,))
    assert db.change_token() != t2                      # suppression (compte)


# ── Backend: PRAGMA, retry, index, change_token ──────────────────────────────

import threading
import time

import pytest


def _db_temp(tmp_path, busy_ms=50):
    d = connection.DatabaseConnection(str(tmp_path / "t.sqlite3"))
    d._pragmas["busy_timeout_ms"] = busy_ms
    return d


def _espion(journal):
    """Patche sqlite3.connect pour enregistrer les SQL passés à Connection.execute."""
    reel = sqlite3.connect

    class Spy(sqlite3.Connection):
        def execute(self, sql, *a):
            journal.append(sql)
            return super().execute(sql, *a)

    return mock.patch.object(connection.sqlite3, "connect", lambda *a, **k: reel(*a, **{**k, "factory": Spy}))


def test_journal_mode_applique_une_fois_pas_par_connexion(tmp_path):
    d = _db_temp(tmp_path)
    appels = []
    with _espion(appels):
        d.execute_query("SELECT 1")
        d.execute_insert("INSERT INTO accueil_service (nom) VALUES ('x')")
    assert not [s for s in appels if "journal_mode" in s]
    assert any("busy_timeout" in s for s in appels)
    with sqlite3.connect(d.db_path) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_lecture_sans_transaction_explicite(tmp_path):
    d = _db_temp(tmp_path)
    vus = []
    with _espion(vus):
        d.execute_query("SELECT * FROM accueil_service")
    assert not [s for s in vus if s.strip().upper().startswith(("BEGIN", "COMMIT"))]


@pytest.mark.parametrize("msg", ["database is locked", "database is busy", "database table is locked"])
def test_retry_couvre_locked_et_busy(msg):
    n = {"i": 0}

    @connection._retry_on_lock
    def f():
        n["i"] += 1
        if n["i"] < 3:
            raise sqlite3.OperationalError(msg)
        return "ok"

    with mock.patch.object(connection.time, "sleep") as sl:
        assert f() == "ok"
    assert n["i"] == 3 and sl.call_count == 2


def test_retry_backoff_croissant_avec_gigue():
    @connection._retry_on_lock
    def f():
        raise sqlite3.OperationalError("database is busy")

    with mock.patch.object(connection.time, "sleep") as sl:
        with pytest.raises(sqlite3.OperationalError):
            f()
    delais = [c.args[0] for c in sl.call_args_list]
    base = [connection._BASE_DELAY * 2 ** i for i in range(len(delais))]
    assert all(b <= x <= b + connection._JITTER for b, x in zip(base, delais))


def test_retry_ne_masque_pas_les_autres_erreurs():
    @connection._retry_on_lock
    def f():
        raise sqlite3.OperationalError("no such table: x")

    with mock.patch.object(connection.time, "sleep") as sl, pytest.raises(sqlite3.OperationalError):
        f()
    assert sl.call_count == 0


def test_verrou_temporaire_reel_est_rejoue(tmp_path):
    """Un autre connecteur tient le verrou d'écriture ~0,4 s: l'INSERT réussit après retry."""
    d = _db_temp(tmp_path, busy_ms=50)
    bloqueur = sqlite3.connect(d.db_path, isolation_level=None, check_same_thread=False)
    bloqueur.execute("BEGIN IMMEDIATE")
    t = threading.Timer(0.4, lambda: bloqueur.execute("COMMIT"))
    t.start()
    try:
        d.execute_insert("INSERT INTO accueil_service (nom) VALUES ('apres-verrou')")
    finally:
        t.join()
        bloqueur.close()
    assert d.execute_query("SELECT nom FROM accueil_service WHERE nom='apres-verrou'")


def test_index_attendus_et_utilises(tmp_path):
    d = _db_temp(tmp_path)
    d._ensure_performance_indexes()  # idempotent
    def plan(q, p=()):
        return " ".join(r["detail"] for r in d.execute_query("EXPLAIN QUERY PLAN " + q, p))
    assert "idx_demande_date_jour" in plan("SELECT * FROM accueil_demandeaccueil d WHERE DATE(d.date)=?", ("x",))
    assert "idx_demande_numero_cnps" in plan("SELECT * FROM accueil_demandeaccueil WHERE numero_cnps=?", ("x",))
    assert "idx_demande_nom_prenom_norm" in plan(
        "SELECT * FROM accueil_demandeaccueil WHERE UPPER(TRIM(nom))=? AND UPPER(TRIM(prenom))=?", ("x", "y"))
    assert "idx_demande_created_at" in plan("SELECT * FROM accueil_demandeaccueil ORDER BY created_at DESC LIMIT 5")
    assert "idx_demande_date_created" in plan(
        "SELECT * FROM accueil_demandeaccueil WHERE date=? ORDER BY created_at DESC", ("x",))


def test_change_token_est_une_lecture_unique_sans_balayage(tmp_path):
    d = _db_temp(tmp_path)
    plan = " ".join(r["detail"] for r in d.execute_query(
        "EXPLAIN QUERY PLAN SELECT valeur FROM app_meta WHERE cle = 'version'"))
    assert "SCAN accueil_demandeaccueil" not in plan
    t = d.change_token()
    assert len(t) == 1 and t[0] >= 0 and d.change_token() == t  # jeton valide et stable sans écriture


def test_change_token_ne_depend_pas_de_l_horloge_des_postes(tmp_path):
    """Un poste à l'heure en retard écrit un updated_at plus ancien: les autres doivent quand même voir le changement."""
    d = _db_temp(tmp_path)
    d.execute_insert("INSERT INTO accueil_demandeaccueil (id, statut, updated_at, created_at) VALUES ('1', 'en_attente', '2026-10-23T10:00:00', '2026-10-23T10:00:00')")
    d.execute_insert("INSERT INTO accueil_demandeaccueil (id, statut, updated_at, created_at) VALUES ('2', 'en_attente', '2026-10-23T10:10:00', '2026-10-23T10:01:00')")
    t0 = d.change_token()
    d.execute_update("UPDATE accueil_demandeaccueil SET statut = 'traite', nom = 'X', updated_at = '2026-10-23T10:05:00' WHERE id = '1'")
    assert d.change_token() != t0


def test_change_token_voit_les_changements_de_services_et_motifs(tmp_path):
    d = _db_temp(tmp_path)
    t0 = d.change_token()
    d.execute_update("UPDATE accueil_service SET nom = 'Renommé' WHERE id = 1")
    t1 = d.change_token()
    assert t1 != t0
    d.execute_insert("INSERT INTO accueil_motif (nom) VALUES ('Nouveau')")
    assert d.change_token() != t1


def test_change_token_table_absente_ne_plante_pas(tmp_path):
    d = _db_temp(tmp_path)
    d.execute_update("DROP TABLE app_meta")
    assert d.change_token() == connection._ERROR_TOKEN


def test_change_token_base_verrouillee_ne_plante_pas(tmp_path):
    d = _db_temp(tmp_path)
    d.execute_insert("INSERT INTO accueil_demandeaccueil (id) VALUES ('1')")
    # DELETE + EXCLUSIVE: même les lecteurs sont bloqués
    c = sqlite3.connect(d.db_path, isolation_level=None)
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("BEGIN EXCLUSIVE")
    try:
        with mock.patch.object(connection, "_TOKEN_BUSY_MS", 50):
            t0 = time.perf_counter()
            assert d.change_token() == connection._ERROR_TOKEN
            assert time.perf_counter() - t0 < 10  # attente bornée (50 ms réglées), marge pour machine lente
    finally:
        c.execute("ROLLBACK")
        c.close()


def test_journal_mode_non_applique_au_demarrage_est_retente(tmp_path, monkeypatch):
    """Un autre poste connecté au démarrage bloque PRAGMA journal_mode: il doit être réappliqué ensuite."""
    chemin = tmp_path / "occupee.sqlite3"
    boot = sqlite3.connect(chemin)
    boot.execute("CREATE TABLE t (x)")
    boot.commit()
    boot.close()
    autre = sqlite3.connect(chemin, isolation_level=None)
    autre.execute("BEGIN")
    autre.execute("SELECT * FROM sqlite_master").fetchall()      # verrou partagé: bloque le passage en WAL
    monkeypatch.setattr(connection.AppConfig, "DB_TIMEOUT", 0.05)
    monkeypatch.setattr(
        connection.AppConfig, "get_sqlite_pragmas",
        staticmethod(lambda p: {"journal_mode": "WAL", "busy_timeout_ms": 50, "foreign_keys": "ON", "synchronous": "NORMAL"}),
    )
    d = connection.DatabaseConnection(str(chemin))
    assert d._journal_pending                                   # échec constaté, pas ignoré
    autre.execute("ROLLBACK")
    autre.close()
    d.execute_query("SELECT 1")                                 # la prochaine connexion réessaie
    assert not d._journal_pending
    with sqlite3.connect(chemin) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_base_ancienne_sans_app_meta_est_mise_a_niveau(tmp_path):
    """Une base créée avant le compteur de version doit recevoir app_meta + déclencheurs au démarrage, données intactes."""
    chemin = tmp_path / "ancienne.sqlite3"
    with sqlite3.connect(chemin) as c:
        c.execute("CREATE TABLE accueil_demandeaccueil (id TEXT PRIMARY KEY, date TEXT, nom TEXT, prenom TEXT, numero_cnps TEXT,"
                  " service_demande_id INTEGER, motif_id INTEGER, priorite TEXT, statut TEXT, satisfaction INTEGER,"
                  " commentaire_satisfaction TEXT, heure_arrivee TEXT, heure_reception TEXT, temps_attente TEXT,"
                  " delai_objectif INTEGER, contacts TEXT, agent_accueil_id INTEGER, observations TEXT,"
                  " created_at TEXT, updated_at TEXT, traite_le TEXT)")
        c.execute("INSERT INTO accueil_demandeaccueil (id, nom, date) VALUES ('944', 'ANCIEN', '2025-01-01')")
    d = connection.DatabaseConnection(str(chemin))
    t0 = d.change_token()
    assert t0 != connection._ERROR_TOKEN
    assert d.execute_query("SELECT nom FROM accueil_demandeaccueil")[0]["nom"] == "ANCIEN"
    d.execute_update("UPDATE accueil_demandeaccueil SET nom = 'MAJ' WHERE id = '944'")
    assert d.change_token() != t0
