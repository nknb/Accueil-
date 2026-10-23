"""Parcours de bout en bout avec de vrais widgets et une vraie base temporaire: pré-accueil -> accueil -> base,
navigation selon le rôle et connexion."""
import uuid
from datetime import date

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox

pytest.importorskip("PyQt6.QtCharts")

from database.connection import db  # noqa: E402
from utils.password_manager import PasswordManager  # noqa: E402


@pytest.fixture
def messages(monkeypatch):
    """Capture les boîtes de dialogue (une boîte modale bloquerait le test)."""
    vus = {"information": [], "warning": [], "critical": [], "question": []}
    for nom in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, nom, staticmethod(lambda *a, _n=nom, **k: vus[_n].append(a[2] if len(a) > 2 else "")))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: vus["question"].append(a[2]) or QMessageBox.StandardButton.Yes))
    return vus


def _utilisateur(role, mot_de_passe="Valide#Mdp2024"):
    nom = f"{role}_{uuid.uuid4().hex[:6]}"
    uid = db.execute_insert(
        "INSERT INTO auth_user (username, password, role, is_active, is_superuser, date_joined) VALUES (?, ?, ?, 1, ?, '2000-01-01')",
        (nom, PasswordManager.hash_password(mot_de_passe), role, 1 if role == "admin" else 0),
    )
    return {"id": uid, "username": nom, "email": "", "role": role, "role_display": role}


# ── Parcours d'une demande ────────────────────────────────────────────────────

def test_parcours_complet_preaccueil_accueil_base(qtbot, messages, monkeypatch):
    from widgets.accueil import AccueilPage
    from widgets.accueil import accueil_page as ap
    from widgets.database import database_page as dp
    from widgets.preaccueil import PreAccueilPage

    db.execute_update("DELETE FROM accueil_demandeaccueil")
    agent = _utilisateur("accueil")

    # 1. Pré-accueil: l'agent enregistre un visiteur
    pre = PreAccueilPage()
    qtbot.addWidget(pre)
    pre.input_nom.setText("koné")
    pre.input_prenom.setText("aminata")
    pre.input_cnps.setText("202300010005")
    pre.input_contact.setText("07 00 11 22 33")
    pre.combo_service.setCurrentIndex(1)
    pre.combo_motif.setCurrentIndex(1)
    pre.enregistrer_demande()
    ligne = db.execute_query("SELECT id, nom, prenom, statut, date FROM accueil_demandeaccueil")[0]
    assert (ligne["nom"], ligne["prenom"], ligne["statut"], ligne["date"]) == ("KONÉ", "Aminata", "en_attente", date.today().isoformat())
    assert messages["information"] and "enregistrée" in messages["information"][0]

    # 2. Accueil: la demande apparaît, l'agent la traite
    page = AccueilPage()
    qtbot.addWidget(page)
    page.set_current_user(agent)
    qtbot.waitUntil(lambda: page.ui.tableWidget.rowCount() == 1, timeout=10000)
    assert page.ui.tableWidget.item(0, 0).text() == "KONÉ"
    page.ui.tableWidget.setCurrentCell(0, 0)

    class DialogueAccepte:
        def __init__(self, *_a, **_k): pass
        def exec(self): return QDialog.DialogCode.Accepted
        def payload(self): return {"heure_reception": "23:59:00", "satisfaction": 5, "commentaire_satisfaction": "Très bien"}
    monkeypatch.setattr(ap, "TraitementDialog", DialogueAccepte)
    page.open_selected_demande()

    traitee = db.execute_query("SELECT statut, satisfaction, agent_accueil_id, traite_le, temps_attente FROM accueil_demandeaccueil")[0]
    assert (traitee["statut"], traitee["satisfaction"], traitee["agent_accueil_id"]) == ("traite", 5, agent["id"])
    assert traitee["traite_le"]

    # 3. L'agent « accueil » ne peut plus modifier une demande traitée (verrou de l'interface)
    qtbot.waitUntil(lambda: page.ui.tableWidget.item(0, 0) is not None and page.ui.tableWidget.rowCount() == 1, timeout=10000)
    qtbot.waitUntil(lambda: page.ui.tableWidget.item(0, 10) is not None and page.ui.tableWidget.item(0, 10).text() == "traite", timeout=10000)
    page.ui.tableWidget.setCurrentCell(0, 0)
    ouvert = []
    monkeypatch.setattr(ap, "TraitementDialog", lambda *a, **k: ouvert.append(1))
    page.open_selected_demande()
    assert not ouvert and any("traitee" in m.lower() or "traité" in m.lower() for m in messages["information"])

    # 4. La page Base de données montre qui l'a traitée
    w = dp._ReloadWorker(dp._Filtres(per_page=50), None)
    sortie = []
    w.finished.connect(sortie.append)
    w.run()
    ligne_bd = sortie[0]["rows"][0]
    assert ligne_bd["statut"] == "traite" and ligne_bd["agent"] == agent["username"]


# ── Navigation selon le rôle ──────────────────────────────────────────────────

VUES = {"accueil": 0, "dashboard": 1, "preaccueil": 2, "database": 3, "users": 4}
ATTENDU = {
    "preaccueil": ({"preaccueil"}, 2),
    "accueil": ({"accueil", "preaccueil"}, 0),
    "manager": ({"accueil", "preaccueil", "dashboard"}, 1),
    "admin": ({"accueil", "preaccueil", "dashboard", "database", "users"}, 0),
}


@pytest.fixture
def fenetre(qtbot):
    from sidebar.main_windows import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    return w


@pytest.mark.parametrize("role", list(ATTENDU))
def test_navigation_selon_le_role(fenetre, role):
    vues, vue_defaut = ATTENDU[role]
    fenetre.set_current_user({"id": 1, "username": "u", "email": "", "role": role, "role_display": role})
    assert fenetre.allowed_views == vues
    boutons = {"accueil": fenetre.ui.home_btn_2, "dashboard": fenetre.ui.dashborad_btn_2, "preaccueil": fenetre.ui.orders_btn_2,
               "database": fenetre.ui.products_btn_2, "users": fenetre.ui.customers_btn_2}
    for vue, bouton in boutons.items():
        assert bouton.isHidden() == (vue not in vues), (role, vue)
    assert fenetre.ui.stackedWidget.currentIndex() == vue_defaut
    # une vue interdite ne s'ouvre pas, même demandée directement
    for vue, index in VUES.items():
        if vue not in vues:
            avant = fenetre.ui.stackedWidget.currentIndex()
            fenetre._go_to_view(vue)
            assert fenetre.ui.stackedWidget.currentIndex() == avant, (role, vue)
            fenetre.ui.stackedWidget.setCurrentIndex(index)           # tentative de contournement
            assert fenetre.ui.stackedWidget.currentIndex() != index, (role, vue)
            assert fenetre.ui.stackedWidget.currentIndex() in {VUES[v] for v in vues}


def test_les_pages_reservees_a_l_admin_ne_sont_pas_construites_pour_les_autres(fenetre):
    fenetre.set_current_user({"id": 1, "username": "u", "email": "", "role": "manager", "role_display": "manager"})
    fenetre._go_to_view("database")
    fenetre._go_to_view("users")
    assert fenetre.database_page is None and fenetre.users_page is None       # chargement paresseux: jamais créées


# ── Connexion ─────────────────────────────────────────────────────────────────

def test_connexion_reussie_donne_l_utilisateur_et_remet_le_compteur_a_zero(qtbot, messages, monkeypatch):
    import main
    manager = _utilisateur("manager")
    db.execute_update("UPDATE auth_user SET echecs = 3 WHERE id = ?", (manager["id"],))
    fenetre = main.LoginApp()
    qtbot.addWidget(fenetre)
    ouvertures = []
    monkeypatch.setattr(fenetre, "ouvrir_fenetre_principale", lambda: ouvertures.append(1))
    fenetre.verifier_db(manager["username"], "Valide#Mdp2024")
    assert ouvertures == [1]
    assert fenetre.utilisateur["id"] == manager["id"] and fenetre.utilisateur["role"] == "manager"
    ligne = db.execute_query("SELECT echecs, verrouille_jusqua, last_login FROM auth_user WHERE id = ?", (manager["id"],))[0]
    assert ligne["echecs"] == 0 and ligne["verrouille_jusqua"] is None and ligne["last_login"]


def test_connexion_refuse_un_compte_desactive(qtbot, messages, monkeypatch):
    import main
    inactif = _utilisateur("accueil")
    db.execute_update("UPDATE auth_user SET is_active = 0 WHERE id = ?", (inactif["id"],))
    fenetre = main.LoginApp()
    qtbot.addWidget(fenetre)
    ouvertures = []
    monkeypatch.setattr(fenetre, "ouvrir_fenetre_principale", lambda: ouvertures.append(1))
    fenetre.verifier_db(inactif["username"], "Valide#Mdp2024")
    assert not ouvertures and fenetre.utilisateur is None
