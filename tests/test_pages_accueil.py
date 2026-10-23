"""Pages Accueil / Pré-accueil: plage de dates, concurrence, doublons, jeton de changement, login asynchrone."""
import uuid

import pytest

pytest.importorskip("PyQt6.QtCharts")  # widgets/__init__ charge le Dashboard

from database.connection import db  # noqa: E402
from widgets.accueil.accueil_page import AccueilDemandesWorker, marquer_traitee, plage_jour  # noqa: E402
from widgets.preaccueil.preaccueil_page import PreAccueilDemandesWorker, demande_en_double, valider_champs  # noqa: E402

JOUR = "2031-05-10"


def _ajouter(date, statut="en_attente", cnps="", service=1, motif=1):
    did = uuid.uuid4().hex
    db.execute_update(
        "INSERT INTO accueil_demandeaccueil (id, date, nom, prenom, numero_cnps, service_demande_id, motif_id,"
        " statut, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (did, date, "N", "P", cnps, service, motif, statut, date, date),
    )
    return did


def _lancer(worker):
    res = {}
    worker.finished.connect(lambda r: res.setdefault("rows", r))
    worker.unchanged.connect(lambda: res.setdefault("unchanged", True))
    worker.run()
    return res


def test_plage_jour_meme_resultat_pour_les_deux_formats():
    a = _ajouter(JOUR)
    b = _ajouter(JOUR + "T14:30:00")
    _ajouter("2031-05-11")
    _ajouter("2031-05-09T23:59:59")
    debut, fin = plage_jour(JOUR)
    ids = {r["id"] for r in db.execute_query(
        "SELECT id FROM accueil_demandeaccueil WHERE date >= ? AND date < ?", (debut, fin))}
    assert ids == {a, b}
    rows = _lancer(AccueilDemandesWorker(JOUR))["rows"]
    assert {r["id"] for r in rows} == {a, b}
    assert len(_lancer(PreAccueilDemandesWorker(JOUR))["rows"]) == 2


def test_marquer_traitee_atomique_pour_accueil():
    did = _ajouter("2031-06-01")
    v = ("10:00:00", 5, "", "00:05:00", 1, "2031-06-01T10:00:00")
    assert marquer_traitee(did, v, "accueil") == 1
    assert marquer_traitee(did, v, "accueil") == 0  # déjà traitée depuis un autre poste
    assert marquer_traitee(did, v, "manager") == 1
    assert marquer_traitee(did, v, "admin") == 1


def test_valider_champs():
    assert valider_champs("A", "B", None, None) is None
    assert valider_champs("A", "B", "12-AB", "0102") is None
    assert valider_champs("A" * 101, "B", None, None)
    assert valider_champs("A", "B" * 101, None, None)
    assert valider_champs("A", "B", "12 34", None)
    assert valider_champs("A", "B", "1" * 31, None)
    assert valider_champs("A", "B", None, "0" * 101)


def test_demande_en_double():
    from datetime import date
    auj = date.today().isoformat()
    _ajouter(auj, cnps="DUP1", service=2, motif=3)
    assert demande_en_double("DUP1", 2, 3, auj)
    assert not demande_en_double("DUP1", 2, 4, auj)
    assert not demande_en_double(None, 2, 3, auj)
    assert not demande_en_double("DUP1", 2, 3, "2031-01-01")


def test_worker_saute_le_rechargement_si_jeton_identique():
    _ajouter("2031-07-01")
    jeton = db.change_token()
    assert _lancer(AccueilDemandesWorker("2031-07-01", previous_token=jeton)).get("unchanged")
    _ajouter("2031-07-01")
    res = _lancer(PreAccueilDemandesWorker("2031-07-01", previous_token=jeton))
    assert len(res["rows"]) == 2
    assert "unchanged" not in _lancer(AccueilDemandesWorker("2031-07-01", previous_token=None))


def test_worker_repli_si_jeton_en_erreur(monkeypatch):
    _ajouter("2031-08-01")
    monkeypatch.setattr(db, "change_token", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert len(_lancer(AccueilDemandesWorker("2031-08-01", previous_token=(1, "", "")))["rows"]) == 1


def test_login_asynchrone_verifie_hors_thread_ui(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    import main

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    db.execute_update("DELETE FROM auth_user")
    fenetre = main.LoginApp()
    qtbot.addWidget(fenetre)
    fenetre.ui.lineEdit.setText("manager")
    fenetre.ui.lineEdit_2.setText("mauvais")
    fenetre.se_connecter()
    assert not fenetre.ui.pushButton.isEnabled()
    qtbot.waitUntil(lambda: fenetre.ui.pushButton.isEnabled(), timeout=10000)
    assert "Tentatives restantes: 4" in fenetre.tentative_label.text()


def test_login_double_entree_ne_lance_qu_une_verification(qtbot, monkeypatch):
    """Deux Entrée pendant la vérification (returnPressed ne regarde pas le bouton) ne doivent compter qu'un échec."""
    from PyQt6.QtWidgets import QMessageBox
    import main

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    db.execute_update("DELETE FROM auth_user")
    fenetre = main.LoginApp()
    qtbot.addWidget(fenetre)
    fenetre.ui.lineEdit.setText("manager")
    fenetre.ui.lineEdit_2.setText("mauvais")
    fenetre.se_connecter()
    fenetre.se_connecter()          # seconde Entrée avant la fin du premier contrôle
    qtbot.waitUntil(lambda: fenetre.ui.pushButton.isEnabled(), timeout=10000)
    assert "Tentatives restantes: 4" in fenetre.tentative_label.text()


def test_login_quitter_attend_la_verification_en_cours(qtbot, monkeypatch):
    """Fermer la fenêtre pendant le contrôle ne doit pas détruire un QThread encore actif (abort Qt)."""
    from PyQt6.QtWidgets import QMessageBox
    import main

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    db.execute_update("DELETE FROM auth_user")
    fenetre = main.LoginApp()
    qtbot.addWidget(fenetre)
    fenetre.ui.lineEdit.setText("manager")
    fenetre.ui.lineEdit_2.setText("mauvais")
    fenetre.se_connecter()
    fenetre.attendre_verification()  # bloque jusqu'à la fin du thread
    assert not fenetre._verification_en_cours or not fenetre._verif_thread_actif()
