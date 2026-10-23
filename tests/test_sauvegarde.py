"""Sauvegarde de la base (API de sauvegarde en ligne de SQLite) et PRAGMA optimize au démarrage."""
import re
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

from database import connection
from database.sauvegarde import PREFIXE, derniere_sauvegarde, purger, sauvegarder_base, sauvegarde_cli


def _base(tmp_path, n=5, nom="source.sqlite3"):
    d = connection.DatabaseConnection(str(tmp_path / nom))
    for i in range(n):
        d.execute_insert("INSERT INTO accueil_demandeaccueil (id, nom, date) VALUES (?, ?, '2026-01-01')", (str(i), f"N{i}"))
    return d


def _compte(chemin):
    with closing(sqlite3.connect(chemin)) as c:
        return c.execute("SELECT COUNT(*) FROM accueil_demandeaccueil").fetchone()[0]


def test_sauvegarde_copie_complete_et_verifiee(tmp_path):
    d = _base(tmp_path, n=7)
    sauvegarde = sauvegarder_base(d.db_path, maintenant=datetime(2026, 10, 23, 22, 5, 9))
    assert sauvegarde.parent == tmp_path / "sauvegardes"
    assert sauvegarde.name == f"{PREFIXE}-20261023-220509.sqlite3"
    assert _compte(sauvegarde) == 7 and _compte(d.db_path) == 7           # copie fidèle, source intacte
    assert [p.name for p in sauvegarde.parent.iterdir()] == [sauvegarde.name]   # aucun fichier temporaire


def test_sauvegarde_pendant_des_ecritures_est_coherente(tmp_path):
    d = _base(tmp_path, n=3)
    stop = threading.Event()
    def ecrire():
        i = 1000
        while not stop.is_set():
            d.execute_insert("INSERT INTO accueil_demandeaccueil (id, nom, date) VALUES (?, 'W', '2026-01-01')", (str(i),))
            i += 1
    t = threading.Thread(target=ecrire)
    t.start()
    try:
        sauvegardes = [sauvegarder_base(d.db_path, maintenant=datetime(2026, 1, 1, 0, 0, s)) for s in range(3)]
    finally:
        stop.set()
        t.join()
    for s in sauvegardes:
        with closing(sqlite3.connect(s)) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert c.execute("SELECT COUNT(*) FROM accueil_demandeaccueil").fetchone()[0] >= 3


def test_purge_garde_les_plus_recentes_et_ignore_les_autres_fichiers(tmp_path):
    dossier = tmp_path / "sauv"
    dossier.mkdir()
    for jour in range(1, 6):
        (dossier / f"{PREFIXE}-2026010{jour}-020000.sqlite3").write_text("x")
    (dossier / "notes.txt").write_text("à garder")
    (dossier / f"{PREFIXE}-manuelle.sqlite3").write_text("à garder aussi")   # nom hors format: jamais supprimé
    supprimes = purger(dossier, garder=2)
    assert len(supprimes) == 3
    restants = sorted(p.name for p in dossier.iterdir())
    assert restants == sorted([f"{PREFIXE}-20260104-020000.sqlite3", f"{PREFIXE}-20260105-020000.sqlite3",
                               "notes.txt", f"{PREFIXE}-manuelle.sqlite3"])


def test_sauvegarde_base_absente_ne_cree_rien(tmp_path):
    with pytest.raises(FileNotFoundError):
        sauvegarder_base(tmp_path / "absente.sqlite3", dossier=tmp_path / "s")
    assert not (tmp_path / "s").exists() or not any((tmp_path / "s").iterdir())


def test_sauvegarde_purge_apres_succes(tmp_path):
    d = _base(tmp_path)
    for s in range(4):
        sauvegarder_base(d.db_path, garder=2, maintenant=datetime(2026, 1, 1, 0, 0, s))
    assert len(list((tmp_path / "sauvegardes").iterdir())) == 2


def test_derniere_sauvegarde(tmp_path):
    d = _base(tmp_path)
    assert derniere_sauvegarde(d.db_path.parent / "sauvegardes") is None
    sauvegarder_base(d.db_path, maintenant=datetime(2026, 3, 4, 5, 6, 7))
    sauvegarder_base(d.db_path, maintenant=datetime(2026, 3, 5, 5, 6, 7))
    assert derniere_sauvegarde(d.db_path.parent / "sauvegardes") == datetime(2026, 3, 5, 5, 6, 7)


def test_commande_sauvegarde_codes_de_sortie(tmp_path, capsys):
    d = _base(tmp_path)
    cible = tmp_path / "dest"
    assert sauvegarde_cli(["--base", str(d.db_path), "--dossier", str(cible), "--garder", "3"]) == 0
    assert len(list(cible.iterdir())) == 1
    assert sauvegarde_cli(["--base", str(tmp_path / "absente.sqlite3"), "--dossier", str(cible)]) == 1
    assert sauvegarde_cli(["--garder", "zéro"]) == 2                     # argument invalide


def test_optimize_au_demarrage_remplit_les_statistiques(tmp_path):
    d = _base(tmp_path, n=300)
    with closing(sqlite3.connect(d.db_path)) as c:
        c.execute("DELETE FROM sqlite_stat1") if c.execute("SELECT name FROM sqlite_master WHERE name='sqlite_stat1'").fetchone() else None
        c.commit()
    connection.DatabaseConnection(str(d.db_path))                       # réouverture = démarrage d'un autre poste
    with closing(sqlite3.connect(d.db_path)) as c:
        tables = {r[0] for r in c.execute("SELECT DISTINCT tbl FROM sqlite_stat1")}
    assert "accueil_demandeaccueil" in tables


def test_bouton_sauvegarder_de_l_onglet_configuration(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    from config import AppConfig
    from widgets.users.Main import _ConfigTab
    d = _base(tmp_path)
    monkeypatch.setattr(AppConfig, "get_db_path", classmethod(lambda c: d.db_path))
    messages = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: messages.append(a[2])))
    onglet = _ConfigTab()
    qtbot.addWidget(onglet)
    assert "Aucune" in onglet._lbl_sauvegarde.text()
    onglet._sauvegarder_maintenant()
    assert len(list((tmp_path / "sauvegardes").iterdir())) == 1
    assert messages and "sauvegarde" in messages[0].lower()
    assert "Aucune" not in onglet._lbl_sauvegarde.text()
