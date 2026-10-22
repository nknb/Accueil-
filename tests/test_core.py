"""Tests du coeur: mots de passe, ids de demandes, permissions, passage en non_traite.

Lancer: python -m unittest discover tests
"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Base temporaire: doit être fixée AVANT l'import de database.* (qui crée `db` à l'import)
_TMP = tempfile.TemporaryDirectory()
from config import AppConfig  # noqa: E402

AppConfig.get_db_path = classmethod(lambda cls: Path(_TMP.name) / "test.sqlite3")

from database.connection import db  # noqa: E402
from database.models import DemandeAccueil, Permission, Role  # noqa: E402
from utils.password_manager import PasswordManager  # noqa: E402


class TestMotDePasse(unittest.TestCase):
    def test_mauvais_mot_de_passe_refuse(self):
        h = PasswordManager.hash_password("Secret@123")
        self.assertTrue(PasswordManager.verify_password("Secret@123", h))
        self.assertFalse(PasswordManager.verify_password("autre", h))

    def test_hash_sha256_ancien_refuse(self):
        sha = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
        self.assertFalse(PasswordManager.verify_password("password", sha))


class TestDemandes(unittest.TestCase):
    def test_deux_save_donnent_deux_ids_croissants(self):
        a, b = DemandeAccueil(nom="A"), DemandeAccueil(nom="B")
        self.assertTrue(a.save())
        self.assertTrue(b.save())
        self.assertGreaterEqual(int(a.id), 944)
        self.assertEqual(int(b.id), int(a.id) + 1)

    def test_modification_garde_le_meme_id(self):
        d = DemandeAccueil(nom="C")
        d.save()
        id_avant = d.id
        d.nom = "C2"
        self.assertTrue(d.save())
        self.assertEqual(d.id, id_avant)
        self.assertEqual(DemandeAccueil.get_by_id(id_avant).nom, "C2")

    def test_rollover_passe_hier_en_non_traite(self):
        hier = (datetime.now() - timedelta(days=1)).date().isoformat()
        d = DemandeAccueil(nom="Hier", date=hier)
        d.save()
        db.rollover_pending_to_non_traite()
        self.assertEqual(DemandeAccueil.get_by_id(d.id).statut, "non_traite")


class TestPermissions(unittest.TestCase):
    def test_suppression_reservee_admin_manager(self):
        self.assertTrue(Permission.can_delete(Role.ADMIN))
        self.assertTrue(Permission.can_delete(Role.MANAGER))
        self.assertFalse(Permission.can_delete(Role.ACCUEIL))
        self.assertFalse(Permission.can_delete(Role.PRE_ACCUEIL))


if __name__ == "__main__":
    unittest.main()
