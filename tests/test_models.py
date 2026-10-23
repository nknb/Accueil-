"""Tests de database/models.py: stats, filtres, N+1, cas bord des temps d'attente."""
import logging
import unittest
from datetime import date, time

from database.connection import db  # noqa: E402 (base temporaire: conftest.py)
from database.models import DemandeAccueil, Service, StatistiquesQuotidiennes  # noqa: E402


class TestStatistiques(unittest.TestCase):
    def test_init_sans_date_ne_plante_pas(self):
        self.assertEqual(StatistiquesQuotidiennes().date, date.today())

    def test_get_for_date_compte_plus_de_100_demandes(self):
        jour = date(2001, 2, 3)
        for i in range(105):
            self.assertTrue(DemandeAccueil(nom=f"S{i}", date=jour).save())
        self.assertEqual(StatistiquesQuotidiennes.get_for_date(jour).total_demandes, 105)


class TestGetAll(unittest.TestCase):
    def test_filtre_dates_et_limite(self):
        jour = date(2002, 3, 4)
        for i in range(3):
            DemandeAccueil(nom=f"F{i}", date=jour).save()
        f = {'date_debut': jour, 'date_fin': jour}
        self.assertEqual(len(DemandeAccueil.get_all(f)), 3)
        self.assertEqual(len(DemandeAccueil.get_all(f, limit=2)), 2)
        self.assertEqual(len(DemandeAccueil.get_all({'date_debut': '2002-03-04', 'date_fin': '2002-03-04'})), 3)

    def test_service_precharge_sans_requete_par_ligne(self):
        sid = db.execute_insert("INSERT INTO accueil_service (nom, actif) VALUES ('SvcTest', 1)")
        jour = date(2003, 4, 5)
        for i in range(5):
            DemandeAccueil(nom=f"P{i}", date=jour, service_demande_id=sid).save()
        demandes = DemandeAccueil.get_all({'date_debut': jour, 'date_fin': jour})
        appels = []
        original = Service.get_by_id
        Service.get_by_id = classmethod(lambda cls, i: appels.append(i))
        try:
            self.assertTrue(all(d.service.nom == "SvcTest" for d in demandes))
        finally:
            Service.get_by_id = original
        self.assertEqual(appels, [])


class TestTempsAttente(unittest.TestCase):
    def test_minutes_valeur_corrompue(self):
        self.assertIsNone(DemandeAccueil(temps_attente="abc:de:fg").temps_attente_minutes)
        self.assertEqual(DemandeAccueil(temps_attente="0:20:30").temps_attente_minutes, 20)

    def test_reception_avant_arrivee_inchange_et_journalise(self):
        d = DemandeAccueil(heure_arrivee=time(23, 50), heure_reception=time(0, 10), temps_attente="0:05:00")
        with self.assertLogs("CNPS-Accueil.Models", level=logging.WARNING):
            d.calculer_temps_attente()
        self.assertEqual(d.temps_attente, "0:05:00")

    def test_calcul_normal(self):
        d = DemandeAccueil(heure_arrivee=time(9, 0), heure_reception=time(9, 10))
        d.calculer_temps_attente()
        self.assertEqual(d.temps_attente, "0:10:00")
        self.assertEqual(d.delai_objectif, 1)

    def test_date_invalide_journalisee_et_date_iso_avec_heure_acceptee(self):
        with self.assertLogs("CNPS-Accueil.Models", level=logging.WARNING):
            DemandeAccueil(date="pas-une-date")
        self.assertEqual(DemandeAccueil(date="2020-01-02T10:00:00").date, date(2020, 1, 2))


class TestSave(unittest.TestCase):
    def test_id_numerique_inexistant_est_insere_tel_quel(self):
        d = DemandeAccueil(id="99999", nom="X")
        self.assertTrue(d.save())
        self.assertEqual(DemandeAccueil.get_by_id("99999").nom, "X")


class TestStatutEnum(unittest.TestCase):
    def test_tous_les_statuts_ecrits_en_base_sont_dans_l_enum(self):
        """Le rollover écrit 'non_traite': l'UI fait Statut(valeur) et ne doit pas lever."""
        from database.models import Statut
        self.assertEqual(Statut("non_traite").value, "non_traite")
        self.assertIn("Non traité", str(Statut("non_traite")))
