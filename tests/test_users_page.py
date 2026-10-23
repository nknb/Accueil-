"""Garde-fous de la page Utilisateurs: dernier admin."""
from database.connection import db


def _add(username, role):
    is_admin = 1 if role == "admin" else 0
    return db.execute_insert(
        "INSERT INTO auth_user (username, password, role, is_active, is_superuser, is_staff, date_joined)"
        " VALUES (?, 'x', ?, 1, ?, ?, '2000-01-01')", (username, role, is_admin, is_admin))


def test_dernier_admin_est_protege():
    from widgets.users.Main import retire_admin_autorise
    db.execute_update("DELETE FROM auth_user")
    a1 = _add("adm1", "admin")
    agent = _add("agent1", "accueil")
    assert retire_admin_autorise(agent)          # pas un admin: libre
    assert not retire_admin_autorise(a1)         # seul admin actif: interdit
    a2 = _add("adm2", "admin")
    assert retire_admin_autorise(a1)             # un autre admin existe
    assert retire_admin_autorise(a2)


def test_dashboard_compte_par_date_de_la_demande_pas_par_modification(qtbot):
    from datetime import date
    from database.models import DemandeAccueil
    from widgets.dashboard.Main import _DashboardWorker
    jour = "2011-05-06"
    DemandeAccueil(nom="DASH", date=date(2011, 5, 6)).save()
    db.execute_update("DELETE FROM accueil_demandeaccueil WHERE date != ?", (jour,))
    db.rollover_pending_to_non_traite()  # réécrit updated_at à maintenant
    res = []
    w = _DashboardWorker(jour, jour)
    w.finished.connect(res.append)
    w.run()
    assert res and res[0]["total_demandes"] == 1
