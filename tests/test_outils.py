"""Outil de mesure réseau: ne laisse aucun fichier et ne touche pas à la base réelle."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))


def test_benchmark_reseau_mesure_puis_nettoie(tmp_path):
    from benchmark_reseau import mesurer
    (tmp_path / "db.sqlite3").write_text("vraie base: ne doit pas être touchée")
    r = mesurer(tmp_path, n=5)
    assert set(r) == {"ouverture_lecture", "ecriture", "journal_mode"}
    for cle in ("ouverture_lecture", "ecriture"):
        assert r[cle]["p50"] >= 0 and r[cle]["p95"] >= r[cle]["p50"] and r[cle]["max"] >= r[cle]["p95"]
    assert [p.name for p in tmp_path.iterdir()] == ["db.sqlite3"]            # fichiers temporaires supprimés
    assert (tmp_path / "db.sqlite3").read_text().startswith("vraie base")


def test_benchmark_refuse_un_dossier_inexistant(tmp_path):
    import pytest
    from benchmark_reseau import mesurer
    with pytest.raises(FileNotFoundError):
        mesurer(tmp_path / "absent", n=2)
