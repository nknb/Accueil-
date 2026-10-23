"""Tests de concurrence réels (threads et processus) sur une base temporaire."""
import subprocess
import sys
import textwrap
import threading
from datetime import date
from pathlib import Path

from database import connection
from database.models import DemandeAccueil

RACINE = Path(__file__).resolve().parent.parent


def _vider():
    connection.db.execute_update("DELETE FROM accueil_demandeaccueil")


def test_8_threads_x_40_save_ids_uniques_et_sequentiels():
    _vider()
    erreurs, ids = [], []
    verrou = threading.Lock()

    def travail(k):
        for i in range(40):
            d = DemandeAccueil(nom=f"T{k}", prenom=str(i), date=date.today())
            try:
                ok = d.save()
            except Exception as exc:  # noqa: BLE001
                erreurs.append(repr(exc))
                continue
            if not ok:
                erreurs.append("save() a renvoyé False")
            with verrou:
                ids.append(d.id)

    ths = [threading.Thread(target=travail, args=(k,)) for k in range(8)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert not erreurs, erreurs[:3]
    assert len(ids) == 320 and len(set(ids)) == 320
    en_base = connection.db.execute_query("SELECT id FROM accueil_demandeaccueil")
    nums = sorted(int(r["id"]) for r in en_base)
    assert len(nums) == 320
    assert nums == list(range(nums[0], nums[0] + 320))  # séquentiels, sans trou
    _vider()


def test_lectures_pendant_ecritures_sans_erreur():
    _vider()
    erreurs, stop = [], threading.Event()

    def ecrivain():
        for i in range(60):
            try:
                DemandeAccueil(nom="W", prenom=str(i), date=date.today()).save()
            except Exception as exc:  # noqa: BLE001
                erreurs.append(repr(exc))

    def lecteur():
        while not stop.is_set():
            try:
                connection.db.execute_query("SELECT COUNT(*) AS n FROM accueil_demandeaccueil")
                connection.db.change_token()
            except Exception as exc:  # noqa: BLE001
                erreurs.append(repr(exc))

    ecr = [threading.Thread(target=ecrivain) for _ in range(3)]
    lec = [threading.Thread(target=lecteur) for _ in range(3)]
    [t.start() for t in lec + ecr]
    [t.join() for t in ecr]
    stop.set()
    [t.join() for t in lec]
    assert not erreurs, erreurs[:3]
    assert connection.db.execute_query("SELECT COUNT(*) AS n FROM accueil_demandeaccueil")[0]["n"] == 180
    _vider()


_SCRIPT = textwrap.dedent("""
    import sys
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    from config import AppConfig
    AppConfig.get_db_path = classmethod(lambda cls: Path(sys.argv[2]))
    from database.models import DemandeAccueil
    from datetime import date
    for i in range(30):
        assert DemandeAccueil(nom="P" + sys.argv[3], prenom=str(i), date=date.today()).save()
""")


def test_deux_processus_inserent_en_parallele_sans_doublon():
    _vider()
    chemin = str(connection.db.db_path)
    procs = [
        subprocess.Popen([sys.executable, "-I", "-c", _SCRIPT, str(RACINE), chemin, str(k)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for k in range(2)
    ]
    sorties = [p.communicate(timeout=120) for p in procs]
    assert [p.returncode for p in procs] == [0, 0], sorties
    ids = [r["id"] for r in connection.db.execute_query("SELECT id FROM accueil_demandeaccueil")]
    assert len(ids) == 60 and len(set(ids)) == 60
    _vider()
