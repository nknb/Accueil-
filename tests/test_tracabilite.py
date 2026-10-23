"""Traçabilité: quel agent a traité chaque demande (agent_accueil_id) et à quel moment (traite_le)."""
import uuid
from datetime import date

import pytest

pytest.importorskip("PyQt6.QtCharts")

from database.connection import db  # noqa: E402
from database.models import DemandeAccueil  # noqa: E402
from widgets.accueil.accueil_page import agent_du_traitement, marquer_traitee  # noqa: E402

VALEURS = ("10:30:00", 4, "RAS", "0:12:00", 1, "2026-10-23T10:30:00")   # réception, satisfaction, commentaire, attente, objectif, maj


def _agent(nom, role="accueil"):
    return db.execute_insert(
        "INSERT INTO auth_user (username, password, role, is_active, date_joined) VALUES (?, 'x', ?, 1, '2000-01-01')",
        (f"{nom}_{uuid.uuid4().hex[:6]}", role),
    )


def _demande(statut="en_attente"):
    did = uuid.uuid4().hex
    db.execute_update("INSERT INTO accueil_demandeaccueil (id, nom, date, statut) VALUES (?, 'N', '2026-10-23', ?)", (did, statut))
    return did


def _ligne(did):
    return db.execute_query("SELECT statut, agent_accueil_id, traite_le FROM accueil_demandeaccueil WHERE id = ?", (did,))[0]


def test_le_traitement_enregistre_l_agent_et_l_heure():
    marie, did = _agent("marie"), _demande()
    assert marquer_traitee(did, VALEURS, "accueil", marie) == 1
    ligne = _ligne(did)
    assert (ligne["statut"], ligne["agent_accueil_id"], ligne["traite_le"]) == ("traite", marie, "2026-10-23T10:30:00")


def test_un_second_agent_ne_peut_pas_s_approprier_une_demande_deja_traitee():
    marie, yao, did = _agent("marie"), _agent("yao"), _demande()
    assert marquer_traitee(did, VALEURS, "accueil", marie) == 1
    assert marquer_traitee(did, VALEURS, "accueil", yao) == 0          # refusé: la demande est déjà traitée
    assert _ligne(did)["agent_accueil_id"] == marie                    # l'agent d'origine est conservé


def test_un_manager_qui_corrige_devient_l_agent_enregistre():
    marie, chef, did = _agent("marie"), _agent("chef", "manager"), _demande()
    marquer_traitee(did, VALEURS, "accueil", marie)
    assert marquer_traitee(did, VALEURS, "manager", chef) == 1
    assert _ligne(did)["agent_accueil_id"] == chef


def test_sans_agent_connu_l_agent_existant_n_est_pas_efface():
    marie, did = _agent("marie"), _demande()
    marquer_traitee(did, VALEURS, "accueil", marie)
    marquer_traitee(did, VALEURS, "admin")                              # appel ancien sans agent
    assert _ligne(did)["agent_accueil_id"] == marie


def test_agent_du_traitement_nomme_l_agent_ou_rien():
    marie, did = _agent("marie"), _demande()
    assert agent_du_traitement(did) is None                            # pas encore traitée
    marquer_traitee(did, VALEURS, "accueil", marie)
    assert agent_du_traitement(did).startswith("marie_")
    db.execute_update("DELETE FROM auth_user WHERE id = ?", (marie,))
    assert agent_du_traitement(did) is None                            # compte supprimé depuis


def test_modele_marquer_traite_enregistre_l_agent():
    marie = _agent("marie")
    d = DemandeAccueil(nom="MODELE", date=date.today())
    assert d.save()
    assert d.marquer_traite(agent_id=marie)
    ligne = _ligne(d.id)
    assert ligne["agent_accueil_id"] == marie and ligne["traite_le"]


def test_la_page_accueil_retient_l_agent_connecte(qtbot):
    from widgets.accueil import AccueilPage
    page = AccueilPage()
    qtbot.addWidget(page)
    page.set_current_user({"id": 42, "username": "marie", "role": "accueil"})
    assert page.current_user_id == 42
    page.set_current_user(None)
    assert page.current_user_id is None


def test_page_base_de_donnees_affiche_et_filtre_par_agent():
    from widgets.database import database_page as dp
    marie = _agent("zorro")                                    # nom unique: la base de test est partagée entre les tests
    nom = db.execute_query("SELECT username FROM auth_user WHERE id = ?", (marie,))[0]["username"]
    did, orphelin = _demande(), _demande("traite")
    marquer_traitee(did, VALEURS, "accueil", marie)
    db.execute_update("UPDATE accueil_demandeaccueil SET agent_accueil_id = 987654 WHERE id = ?", (orphelin,))   # compte disparu

    def charger(**kw):
        w = dp._ReloadWorker(dp._Filtres(per_page=500, **kw), None)
        out = []
        w.finished.connect(out.append)
        w.run()
        return {r["id"]: r for r in out[0]["rows"]}

    tout = charger()
    assert tout[did]["agent"] == nom
    assert tout[orphelin]["agent"] == "(compte supprimé)"
    assert set(charger(cols=(("agent", nom.upper()),))) == {did}      # filtre insensible à la casse
    assert "agent" in dp._COL_KEYS and dict(zip(dp._COL_KEYS, dp._COL_LABELS))["agent"] == "Traité par"
