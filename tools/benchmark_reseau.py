"""Mesure la latence SQLite d'un dossier (typiquement le partage réseau de la base), sans toucher à la vraie base.

Usage:
    python tools/benchmark_reseau.py                       # dossier de la base configurée
    python tools/benchmark_reseau.py \\\\serveur\\partage\\accueil

Crée un fichier temporaire `benchmark_<pid>.sqlite3` dans ce dossier, mesure, puis le supprime.
Lancez-le sur 2 ou 3 postes en même temps pour voir l'effet de la concurrence (comparez les p95).
Repères: ouverture+lecture < 20 ms et écriture < 100 ms (p95) = confortable; > 200 ms = partage lent.
"""
import os
import sqlite3
import statistics
import sys
import time
from contextlib import closing
from pathlib import Path


def _stats(valeurs_ms):
    t = sorted(valeurs_ms)
    return {"p50": statistics.median(t), "p95": t[min(len(t) - 1, int(len(t) * 0.95))], "max": t[-1]}


def mesurer(dossier, n=50):
    """Latences (ms) d'une ouverture+lecture et d'une écriture, chacune sur sa propre connexion comme l'application."""
    dossier = Path(dossier)
    if not dossier.is_dir():
        raise FileNotFoundError(f"Dossier introuvable: {dossier}")
    base = dossier / f"benchmark_{os.getpid()}.sqlite3"
    reseau = str(dossier).startswith(("\\\\", "//"))
    mode = "DELETE" if reseau else "WAL"          # même règle que config.get_sqlite_pragmas
    lectures, ecritures = [], []
    try:
        with closing(sqlite3.connect(base, timeout=30)) as c:
            c.execute(f"PRAGMA journal_mode = {mode}")
            c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
            c.commit()
        for _ in range(n):
            t0 = time.perf_counter()
            with closing(sqlite3.connect(base, timeout=30)) as c:
                c.execute("PRAGMA busy_timeout = 30000")
                c.execute("SELECT COUNT(*) FROM t").fetchone()
            lectures.append((time.perf_counter() - t0) * 1000)
        for i in range(n):
            t0 = time.perf_counter()
            with closing(sqlite3.connect(base, timeout=30, isolation_level=None)) as c:
                c.execute("PRAGMA busy_timeout = 30000")
                c.execute("BEGIN IMMEDIATE")
                c.execute("INSERT INTO t (v) VALUES (?)", (str(i),))
                c.execute("COMMIT")
            ecritures.append((time.perf_counter() - t0) * 1000)
    finally:
        for suffixe in ("", "-journal", "-wal", "-shm"):
            Path(str(base) + suffixe).unlink(missing_ok=True)
    return {"ouverture_lecture": _stats(lectures), "ecriture": _stats(ecritures), "journal_mode": mode}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cible = Path(sys.argv[1])
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from config import AppConfig
        cible = AppConfig.get_db_path().parent
    r = mesurer(cible)
    print(f"Dossier: {cible}  (journal_mode {r['journal_mode']})")
    for cle, titre in (("ouverture_lecture", "Ouverture + lecture"), ("ecriture", "Écriture")):
        s = r[cle]
        print(f"  {titre:20s} p50 {s['p50']:7.1f} ms   p95 {s['p95']:7.1f} ms   max {s['max']:7.1f} ms")
