"""Fixtures communes: base SQLite temporaire, jamais db.sqlite3."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Doit être fixé AVANT l'import de database.* (qui crée `db` à l'import)
TMP = tempfile.TemporaryDirectory()
from config import AppConfig  # noqa: E402

AppConfig.get_db_path = classmethod(lambda cls: Path(TMP.name) / "test.sqlite3")
