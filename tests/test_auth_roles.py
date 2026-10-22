"""Connexion (verrouillage) et matrice de permissions par rôle."""
import sqlite3
from contextlib import closing

import pytest

from database.models import Permission, Role

# rôle -> (permissions attendues, permissions interdites)
MATRICE = {
    Role.ADMIN: ({Permission.MANAGE_USERS, Permission.DELETE_DEMANDE, Permission.VIEW_STATS}, set()),
    Role.MANAGER: ({Permission.DELETE_DEMANDE, Permission.VIEW_STATS}, {Permission.MANAGE_USERS}),
    Role.ACCUEIL: ({Permission.PROCESS_DEMANDE}, {Permission.MANAGE_USERS, Permission.DELETE_DEMANDE, Permission.VIEW_STATS}),
    Role.PRE_ACCUEIL: ({Permission.CREATE_DEMANDE}, {Permission.MANAGE_USERS, Permission.DELETE_DEMANDE, Permission.PROCESS_DEMANDE}),
}


@pytest.mark.parametrize("role", list(MATRICE))
def test_permissions_par_role(role):
    permis, interdits = MATRICE[role]
    for p in permis:
        assert Permission.has_permission(role, p), (role, p)
    for p in interdits:
        assert not Permission.has_permission(role, p), (role, p)


@pytest.fixture
def login(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    import main

    mots_de_passe = {}

    def capture(_parent, _titre, texte):
        for ligne in texte.splitlines()[2:]:
            nom, mdp = ligne.split(" : ")
            mots_de_passe[nom] = mdp

    monkeypatch.setattr(QMessageBox, "information", staticmethod(capture))
    # Table vide: chaque test repart avec des comptes par défaut neufs
    from database.connection import db
    db.execute_update("DELETE FROM auth_user")
    fenetre = main.LoginApp()
    qtbot.addWidget(fenetre)
    fenetre.mots_de_passe = mots_de_passe
    return fenetre


def _verrou(login, username):
    with closing(sqlite3.connect(login.db_path)) as c:
        return c.execute(
            "SELECT echecs, verrouille_jusqua FROM auth_user WHERE username = ?", (username,)
        ).fetchone()


def test_comptes_par_defaut_ont_un_mot_de_passe_aleatoire(login):
    assert set(login.mots_de_passe) == {"admin", "manager", "accueil", "preaccueil"}
    assert len(set(login.mots_de_passe.values())) == 4
    assert all(len(m) >= 12 for m in login.mots_de_passe.values())


def test_cinq_echecs_verrouillent_meme_avec_bon_mot_de_passe(login):
    for _ in range(5):
        login.verifier_db("manager", "mauvais")
    echecs, verrou = _verrou(login, "manager")
    assert verrou is not None
    login.verifier_db("manager", login.mots_de_passe["manager"])
    assert login.utilisateur is None  # refusé tant que le compte est verrouillé
