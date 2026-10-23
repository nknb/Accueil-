"""Scripts Windows: je ne peux pas les exécuter ici, on vérifie donc leur cohérence avec le reste du projet."""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "installer_windows"


def _texte(nom):
    return (DOSSIER / nom).read_text(encoding="utf-8")


def test_script_de_planification_est_coherent():
    brut = (DOSSIER / "PLANIFIER_SAUVEGARDE.bat").read_bytes()
    assert b"\n" not in brut.replace(b"\r\n", b"")                        # fins de ligne CRLF partout (cmd.exe)
    texte = brut.decode("utf-8")
    assert "schtasks /Create" in texte and "--sauvegarde" in texte
    assert re.search(r"/SC\s+DAILY", texte) and "/RP" in texte             # quotidienne, avec le mot de passe de l'utilisateur
    assert "net session" in texte                                          # exige les droits d'administrateur
    assert "AccueilCNPS.exe" in texte


def test_le_nom_de_tache_est_le_meme_a_l_installation_et_a_la_desinstallation():
    nom = re.search(r'set TACHE=(.+)', _texte("PLANIFIER_SAUVEGARDE.bat")).group(1).strip()
    assert nom and nom in _texte("DESINSTALLER.bat")
    assert "schtasks /Delete" in _texte("DESINSTALLER.bat")


def test_le_script_utilise_une_option_que_l_application_reconnait():
    assert '"--sauvegarde" in sys.argv' in (RACINE / "main.py").read_text(encoding="utf-8")
    assert "--garder" in _texte("PLANIFIER_SAUVEGARDE.bat")
    assert "--garder" in (RACINE / "database" / "sauvegarde.py").read_text(encoding="utf-8")
