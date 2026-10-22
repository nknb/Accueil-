"""Tests des utilitaires: mots de passe, validateurs, logger."""
import pytest

from utils.password_manager import PasswordManager
from utils.validators import InputValidator as V


def test_mot_de_passe_trop_long_refuse():
    with pytest.raises(ValueError):
        PasswordManager.hash_password("Aa1" * 30)
    assert PasswordManager.verify_password("Aa1" * 30, "$2b$13$invalide") is False


def test_verify_ne_leve_jamais():
    assert PasswordManager.verify_password("x", "pas-un-hash") is False
    assert PasswordManager.verify_password("é" * 50, "$2b$04$" + "a" * 53) is False


def test_validate_password_limite_72_octets():
    ok, _ = V.validate_password("Aa1" + "é" * 35)
    assert not ok


def test_fullmatch_refuse_retour_ligne():
    assert not V.validate_username("abc\n")[0]
    assert not V.validate_email("a@b.com\n")[0]
    assert not V.validate_email("a..b@x.com")[0]
    assert V.validate_email("a.b@x.com")[0]


def test_logger_dossier_inscriptible():
    from utils.logger import LoggerSetup
    assert LoggerSetup.LOG_DIR is None or LoggerSetup.LOG_DIR.is_dir()


def test_logger_repli_si_dossier_illisible(monkeypatch, tmp_path):
    from pathlib import Path
    from utils.logger import LoggerSetup
    orig = Path.mkdir
    monkeypatch.setattr(Path, "mkdir", lambda self, *a, **k: (_ for _ in ()).throw(PermissionError()) if self.name == "logs" else orig(self, *a, **k))
    assert LoggerSetup._resolve_log_dir().name == "cnps-accueil-logs"
