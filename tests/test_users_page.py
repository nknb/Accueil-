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


def test_dashboard_temps_attente_format_h_mm_ss(qtbot):
    """L'appli écrit 'H:MM:SS' (ex. 0:12:30), pas 'HH:MM:SS': 12 min ne doit pas devenir 2 min."""
    from datetime import date
    from database.models import DemandeAccueil
    from widgets.dashboard.Main import _DashboardWorker
    jour = date(2012, 6, 7)
    db.execute_update("DELETE FROM accueil_demandeaccueil")
    for t in ("0:12:30", "0:45:10", "00:20:00"):
        DemandeAccueil(nom="W", date=jour, temps_attente=t).save()
    res = []
    w = _DashboardWorker("2012-06-07", "2012-06-07")
    w.finished.connect(res.append)
    w.run()
    d = dict(zip(res[0]["wait_labels"], res[0]["wait_counts"]))
    assert d["≤ 15 min"] == 1 and d["15–30 min"] == 1 and d["30–60 min"] == 1
    assert round(res[0]["avg_wait_min"], 1) == 25.7  # (12 + 45 + 20) / 3


def test_helpers_dashboard_attente_et_heure():
    from widgets.dashboard.Main import _minutes_attente, _heure_arrivee
    assert _minutes_attente("0:12:30") == 12 and _minutes_attente("01:05:00") == 65
    assert _minutes_attente("") is None and _minutes_attente("abc") is None
    assert _heure_arrivee("2026-10-23T10:50:03.483938") == 10
    assert _heure_arrivee("09:15:00") == 9 and _heure_arrivee(None) is None


def test_export_excel_pas_de_formule_et_totaux_complets(tmp_path):
    import openpyxl
    from datetime import date
    from database.models import DemandeAccueil
    from widgets.dashboard.Main import _ChartHandler
    db.execute_update("DELETE FROM accueil_demandeaccueil")
    jour = date(2013, 7, 8)
    DemandeAccueil(nom="=1+1", prenom="@x", numero_cnps="=SUM(1,2)", date=jour).save()
    data = {"total_demandes": 12, "motifs_names": ["A"], "motifs_counts": [5],
            "services_names": ["S"], "services_counts": [5]}  # 7 demandes hors top
    out = tmp_path / "r.xlsx"
    _ChartHandler._write_excel(None, str(out), data, "2013-07-08", "2013-07-08")
    wb = openpyxl.load_workbook(out)
    brut = wb["Données brutes"]
    assert all(c.data_type != "f" for row in brut.iter_rows() for c in row)
    assert brut["B3"].value == "=1+1"            # texte conservé, pas évalué
    mot = [[c.value for c in r] for r in wb["Motifs"].iter_rows(min_row=4)]
    assert ["Autres", 7, "58.3 %"] in mot        # 7/12
    assert mot[-1][1] == 12                      # TOTAL = total des demandes


def test_preaccueil_ne_propose_pas_les_services_et_motifs_inactifs(qtbot):
    from widgets.preaccueil import PreAccueilPage
    db.execute_insert("INSERT INTO accueil_service (nom, actif) VALUES ('SvcInactif', 0)")
    db.execute_insert("INSERT INTO accueil_motif (nom, actif) VALUES ('MotifInactif', 0)")
    page = PreAccueilPage()
    qtbot.addWidget(page)
    services = [page.combo_service.itemText(i) for i in range(page.combo_service.count())]
    motifs = [page.combo_motif.itemText(i) for i in range(page.combo_motif.count())]
    assert "SvcInactif" not in services and "MotifInactif" not in motifs
    assert len(services) > 1 and len(motifs) > 1  # les actifs restent proposés
