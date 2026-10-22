"""Tests de la couche connexion / config (base temporaire uniquement)."""
import importlib.util
import json
import sqlite3
from pathlib import Path
from unittest import mock

from config import AppConfig
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
