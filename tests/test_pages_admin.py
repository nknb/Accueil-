"""Pages Base de données et Utilisateurs: SQL côté base, jeton de changement, contrôle optimiste, debounce."""
import time

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox

from database.connection import db
from widgets.database import database_page as dp


def _vider():
    db.execute_update("DELETE FROM accueil_demandeaccueil")


def _demandes(n, prefixe="N", statut="en_attente"):
    rows = [(f"t{i}", f"2025-03-{1 + i % 28:02d}", f"{prefixe}{i}", "p", statut,
             f"2025-03-{1 + i % 28:02d}T10:00:00", f"2025-03-{1 + i % 28:02d}T10:00:00") for i in range(n)]
    db.execute_many("INSERT INTO accueil_demandeaccueil (id, date, nom, prenom, statut, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?)", rows)


def _attendre(qtbot, page):
    qtbot.waitUntil(lambda: not page._refresh_in_progress and not page._refresh_pending, timeout=5000)


# ── SQL ──────────────────────────────────────────────────────────────────────

def test_filtres_sql_pagination_dates_et_jokers():
    _vider()
    _demandes(30)
    db.execute_insert("INSERT INTO accueil_demandeaccueil (id, nom, date) VALUES ('x1', '100%_pur', '2025-04-01')")
    r = dp.charger_page(dp._Filtres(per_page=10, page=99))
    assert r["total"] == 31 and r["filtered"] == 31 and r["pages"] == 4
    assert r["page"] == 4 and len(r["rows"]) == 1          # page hors limites ramenée à la dernière
    # date: intervalle ouvert à droite, sans DATE(d.date)
    where, _ = dp._where(dp._Filtres(date_from="2025-04-01", date_to="2025-04-02"))
    assert "DATE(" not in where.upper().replace("UPDATE", "") and "d.date < ?" in where
    assert dp.charger_page(dp._Filtres(date_from="2025-04-01", date_to="2025-04-02"))["filtered"] == 1
    # % et _ saisis sont littéraux
    assert dp.charger_page(dp._Filtres(search="100%_"))["filtered"] == 1
    assert dp.charger_page(dp._Filtres(search="%"))["filtered"] == 1
    assert dp.charger_page(dp._Filtres(cols=(("nom", "n1"),)))["filtered"] == 11  # n1, n10..n19 (insensible à la casse)


def test_tri_liste_blanche_et_injection():
    _vider()
    _demandes(5)
    f = dp._Filtres(sort_col="nom; DROP TABLE accueil_demandeaccueil--", search="'; DROP TABLE x;--",
                    cols=(("nom'--", "v"), ("statut", "' OR 1=1 --")))
    assert dp.charger_page(f)["filtered"] == 0
    assert db.execute_query("SELECT COUNT(*) AS n FROM accueil_demandeaccueil")[0]["n"] == 5
    ids = [r["id"] for r in dp.lire_lignes(dp._Filtres(sort_col="id", sort_asc=True))]
    assert ids == sorted(ids, key=lambda x: int(x[1:]))


# ── Jeton de changement ──────────────────────────────────────────────────────

def test_worker_saute_le_rechargement_si_rien_n_a_change(qtbot):
    _vider()
    _demandes(3)
    res = []
    w = dp._ReloadWorker(dp._Filtres(), db.change_token())
    w.finished.connect(res.append)
    w.run()
    assert res == [{"unchanged": True}]
    db.execute_update("UPDATE accueil_demandeaccueil SET nom='Z', updated_at='2030-01-01T00:00:00' WHERE id='t0'")
    w.run()
    assert "rows" in res[1] and res[1]["token"] == db.change_token()


def test_worker_recharge_si_le_jeton_est_en_erreur(monkeypatch):
    _vider()
    res = []
    monkeypatch.setattr(db, "change_token", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    w = dp._ReloadWorker(dp._Filtres(), (0, "", ""))
    w.finished.connect(res.append)
    w.run()
    assert "rows" in res[0]


# ── Page Base de données ─────────────────────────────────────────────────────

@pytest.fixture
def page(qtbot):
    _vider()
    _demandes(120)
    p = dp.DatabasePage()
    qtbot.addWidget(p)
    _attendre(qtbot, p)
    return p


def test_page_ne_charge_qu_une_page_et_recherche_avec_debounce(page, qtbot):
    assert len(page.page_records) == 50 and page.total_count == 120 and page.total_pages == 3
    page._goto_next()
    _attendre(qtbot, page)
    assert page.current_page == 2
    page._search_edit.setText("N11")
    assert page._filter_timer.isActive() and page.filtered_count == 120   # pas encore interrogé
    qtbot.waitUntil(lambda: page.filtered_count == 11 and not page._refresh_in_progress, timeout=3000)
    assert page.current_page == 1


def test_refresh_auto_saute_si_inchange_et_bouton_force(page, qtbot, monkeypatch):
    appels = []
    monkeypatch.setattr(dp, "charger_page", lambda f: appels.append(1) or {})
    page._refresh_auto()
    time.sleep(0.05)
    qtbot.wait(100)
    assert appels == []                                     # jeton identique: aucune lecture
    page._invalidate_and_reload()
    qtbot.waitUntil(lambda: len(appels) == 1, timeout=2000)  # action manuelle: relit toujours
    qtbot.wait(100)


def _accepter(monkeypatch, **champs):
    monkeypatch.setattr(dp._RecordDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    orig = dp._RecordDialog.payload
    monkeypatch.setattr(dp._RecordDialog, "payload", lambda self: {**orig(self), **champs})


def test_modification_concurrente_n_ecrase_pas(page, qtbot, monkeypatch):
    page.table.selectRow(0)
    rec = page.page_records[0]
    # un autre poste modifie la ligne après la lecture
    db.execute_update("UPDATE accueil_demandeaccueil SET nom='AUTRE', updated_at='2031-01-01T00:00:00' WHERE id=?",
                      (rec["id"],))
    _accepter(monkeypatch, nom="MOI")
    msgs = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: msgs.append(a[2]))
    page._on_update()
    assert msgs and "autre poste" in msgs[0]
    assert db.execute_query("SELECT nom FROM accueil_demandeaccueil WHERE id=?", (rec["id"],))[0]["nom"] == "AUTRE"
    _attendre(qtbot, page)


def test_modification_sans_conflit_et_suppression_deja_faite(page, qtbot, monkeypatch):
    page.table.selectRow(0)
    rid = page.page_records[0]["id"]
    _accepter(monkeypatch, nom="NOUVEAU")
    page._on_update()
    assert db.execute_query("SELECT nom FROM accueil_demandeaccueil WHERE id=?", (rid,))[0]["nom"] == "NOUVEAU"
    _attendre(qtbot, page)
    page.table.selectRow(0)
    rid = page.page_records[0]["id"]
    db.execute_update("DELETE FROM accueil_demandeaccueil WHERE id=?", (rid,))   # supprimée ailleurs
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: infos.append(a[2]))
    page._on_delete()                                       # ne doit pas lever
    assert infos and "déjà été supprimée" in infos[0]
    _attendre(qtbot, page)


def test_fermeture_arrete_timers_et_threads(page, qtbot):
    page._request_load(auto=False)
    page.close()
    assert not page._auto_timer.isActive() and not page._filter_timer.isActive()
    qtbot.waitUntil(lambda: not page._live, timeout=3000)


# ── Page Utilisateurs ────────────────────────────────────────────────────────

@pytest.fixture
def users_tab(qtbot):
    from widgets.users.Main import _UsersTab
    db.execute_update("DELETE FROM auth_user")
    for u, r in (("adm1", "admin"), ("adm2", "admin"), ("agent1", "accueil")):
        db.execute_insert("INSERT INTO auth_user (username, password, role, is_active, date_joined)"
                          " VALUES (?, 'x', ?, 1, '2000-01-01')", (u, r))
    t = _UsersTab()
    qtbot.addWidget(t)
    return t


def test_recherche_utilisateurs_est_temporisee(users_tab, qtbot):
    appels = []
    users_tab._search_timer.timeout.disconnect()
    users_tab._search_timer.timeout.connect(lambda: appels.append(1))
    for c in "adm":
        users_tab.search_edit.setText(users_tab.search_edit.text() + c)
    assert appels == []
    qtbot.waitUntil(lambda: appels == [1], timeout=1000)    # une seule exécution pour 3 frappes


def _selectionner(tab, nom):
    for r in range(tab.table.rowCount()):
        if nom in tab.table.item(r, 1).text():
            tab.table.selectRow(r)
            return
    raise AssertionError(nom)


def test_suppression_d_un_utilisateur_deja_supprime(users_tab, monkeypatch):
    _selectionner(users_tab, "agent1")
    db.execute_update("DELETE FROM auth_user WHERE username='agent1'")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    msgs = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: msgs.append(a[2]))
    users_tab._on_delete()
    assert msgs and "supprimé depuis un autre poste" in msgs[0]
    assert users_tab.table.rowCount() == 2                  # liste rechargée


def test_modification_utilisateur_concurrente_et_dernier_admin(users_tab, monkeypatch):
    from widgets.users import Main as um
    _selectionner(users_tab, "agent1")
    msgs = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: msgs.append(a[2]))

    def dialogue(self):  # un autre poste change le rôle pendant que le dialogue est ouvert
        db.execute_update("UPDATE auth_user SET role='manager' WHERE username='agent1'")
        self.username_edit.setText("agent1b")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(um.UserFormDialog, "exec", dialogue)
    users_tab._on_edit()
    assert msgs and "modifié depuis un autre poste" in msgs[0]
    assert db.execute_query("SELECT 1 FROM auth_user WHERE username='agent1b'") == []
    # garde-fou atomique: le dernier admin ne peut pas être supprimé même si la pré-vérification est contournée
    db.execute_update("UPDATE auth_user SET is_active=0 WHERE username='adm2'")
    n = db.execute_update(f"DELETE FROM auth_user WHERE username='adm1' AND {um._GARDE_DERNIER_ADMIN}")
    assert n == 0


def test_recherche_ignore_la_casse_des_caracteres_accentues():
    """Régression: LIKE de SQLite ne compare la casse que sur l'ASCII (« é » ne trouvait pas « É »)."""
    from database.connection import db
    from widgets.database.database_page import _SQL_FROM, _Filtres, _where
    db.execute_update("DELETE FROM accueil_demandeaccueil")
    db.execute_insert("INSERT INTO accueil_demandeaccueil (id, nom, prenom, date) VALUES ('900', 'KONE', 'ÉLODIE', '2026-05-01')")
    for saisie in ("élodie", "Élodie", "éLODIE"):
        clause, params = _where(_Filtres(search=saisie))
        n = db.execute_query(f"SELECT COUNT(*) AS n {_SQL_FROM}{clause}", tuple(params))[0]["n"]
        assert n == 1, saisie
        clause, params = _where(_Filtres(cols=(("prenom", saisie),)))
        n = db.execute_query(f"SELECT COUNT(*) AS n {_SQL_FROM}{clause}", tuple(params))[0]["n"]
        assert n == 1, saisie


def test_liste_utilisateurs_se_rafraichit_au_retour_sur_l_onglet(qtbot):
    """Un compte créé depuis un autre poste doit apparaître quand on revient sur l'onglet."""
    from database.connection import db
    from widgets.users.Main import _UsersTab
    db.execute_update("DELETE FROM auth_user")
    tab = _UsersTab()
    qtbot.addWidget(tab)
    tab.show()
    avant = tab.table.rowCount()
    db.execute_insert("INSERT INTO auth_user (username, password, role, date_joined) VALUES ('autre_poste', 'x', 'accueil', '2000-01-01')")
    tab.hide()
    tab.show()
    assert tab.table.rowCount() == avant + 1
