"""Sauvegarde de la base SQLite partagée (copie cohérente en ligne, vérifiée, avec rotation).

Utilise l'API de sauvegarde de SQLite: la copie est un instantané cohérent même si d'autres postes
écrivent pendant ce temps (une simple copie du fichier ne l'est pas). Chaque copie est vérifiée
(`PRAGMA integrity_check`) avant d'être publiée sous son nom définitif.

Usage planifié (Windows): `AccueilCNPS.exe --sauvegarde [--base CHEMIN] [--dossier DOSSIER] [--garder 30]`.
"""
import logging
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("CNPS-Accueil.Sauvegarde")

PREFIXE = "accueil"
GARDER_PAR_DEFAUT = 30
DOSSIER_PAR_DEFAUT = "sauvegardes"   # à côté de la base
_NOM = re.compile(rf"^{PREFIXE}-(\d{{8}})-(\d{{6}})\.sqlite3$")


def sauvegarder_base(chemin_base, dossier=None, garder: int = GARDER_PAR_DEFAUT,
                     maintenant: Optional[datetime] = None) -> Path:
    """Copie la base dans `dossier` (défaut: `sauvegardes/` à côté de la base) et purge les plus anciennes.

    Returns:
        Chemin de la sauvegarde créée.

    Raises:
        FileNotFoundError: la base n'existe pas (rien n'est créé).
        RuntimeError: la copie n'a pas passé la vérification d'intégrité (elle est supprimée).
    """
    source = Path(chemin_base)
    if not source.is_file():
        raise FileNotFoundError(f"Base introuvable: {source}")
    dossier = Path(dossier) if dossier else source.parent / DOSSIER_PAR_DEFAUT
    dossier.mkdir(parents=True, exist_ok=True)
    maintenant = maintenant or datetime.now()
    destination = dossier / f"{PREFIXE}-{maintenant:%Y%m%d-%H%M%S}.sqlite3"
    temporaire = destination.with_suffix(".tmp")
    try:
        with closing(sqlite3.connect(source, timeout=30)) as src, closing(sqlite3.connect(temporaire)) as dst:
            src.backup(dst)
            verdict = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if verdict != "ok":
            raise RuntimeError(f"Sauvegarde corrompue ({verdict}), supprimée")
        temporaire.replace(destination)
    except BaseException:
        temporaire.unlink(missing_ok=True)
        raise
    purger(dossier, garder)
    logger.info("Sauvegarde créée: %s (%.1f Mo)", destination.name, destination.stat().st_size / 1e6)
    return destination


def _sauvegardes(dossier: Path) -> List[Path]:
    """Sauvegardes du dossier, de la plus ancienne à la plus récente (seuls les noms au format géré)."""
    if not dossier.is_dir():
        return []
    return sorted(p for p in dossier.iterdir() if p.is_file() and _NOM.match(p.name))


def purger(dossier, garder: int = GARDER_PAR_DEFAUT) -> List[Path]:
    """Supprime les sauvegardes les plus anciennes au-delà de `garder`; ne touche jamais aux autres fichiers."""
    anciennes = _sauvegardes(Path(dossier))[: max(0, len(_sauvegardes(Path(dossier))) - max(1, garder))]
    for p in anciennes:
        p.unlink(missing_ok=True)
    return anciennes


def derniere_sauvegarde(dossier) -> Optional[datetime]:
    """Date de la sauvegarde la plus récente du dossier, ou None s'il n'y en a pas."""
    existantes = _sauvegardes(Path(dossier))
    if not existantes:
        return None
    jour, heure = _NOM.match(existantes[-1].name).groups()
    return datetime.strptime(jour + heure, "%Y%m%d%H%M%S")


def sauvegarde_cli(argv: List[str]) -> int:
    """Ligne de commande (`--sauvegarde`): code de sortie 0 = réussi, 1 = échec de la sauvegarde, 2 = arguments invalides."""
    options = {"--base": None, "--dossier": None, "--garder": str(GARDER_PAR_DEFAUT)}
    reste = [a for a in argv if a != "--sauvegarde"]
    try:
        while reste:
            cle = reste.pop(0)
            if cle not in options or not reste:
                raise ValueError(f"Argument inconnu: {cle}")
            options[cle] = reste.pop(0)
        garder = int(options["--garder"])
    except ValueError as exc:
        logger.error("Arguments invalides: %s", exc)
        print(f"Arguments invalides: {exc}", file=sys.stderr)
        return 2
    try:
        base = options["--base"]
        if base is None:
            from config import AppConfig   # import tardif: le module reste utilisable sans l'application
            base = AppConfig.get_db_path()
        resultat = sauvegarder_base(base, options["--dossier"], garder)
    except Exception as exc:
        logger.error("Sauvegarde échouée: %s", exc)
        print(f"Sauvegarde échouée: {exc}", file=sys.stderr)
        return 1
    print(f"Sauvegarde créée: {resultat}")
    return 0
