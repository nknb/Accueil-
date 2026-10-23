"""Page Base de données — design moderne avec filtres colonnes, export Excel et couleurs statut."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

_CAL_ICON_DB = os.path.join(os.path.dirname(__file__), "icons", "calendar.svg").replace("\\", "/")

import openpyxl
from openpyxl.styles import PatternFill, Font as XlFont, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont, QBrush
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QMessageBox,
    QFrame,
    QHeaderView,
    QDateEdit,
    QProgressBar,
    QFileDialog,
)

from config import AppConfig
from database.connection import db
from database.models import DemandeAccueil

_LOG = logging.getLogger(__name__)

# Délai avant d'interroger la base après une frappe (évite une requête par caractère)
_DEBOUNCE_MS = 250
# Threads de rechargement encore actifs à la fermeture (gardés en vie jusqu'à leur fin)
_THREADS_ORPHELINS: list = []


# ── Colonnes visibles ─────────────────────────────────────────────────────────
# On masque les champs techniques (IDs FK, timestamps, etc.) et on résout
# service_demande_id / motif_id avec des JOINs dans le worker.

_VISIBLE_COLS = [
    ("id",           "ID",             80,  False),  # (col_sql, label, width, stretch)
    ("date",         "Date",           90,  False),
    ("nom",          "Nom",            110, True),
    ("prenom",       "Prénom",         110, True),
    ("numero_cnps",  "N° CNPS",        110, False),
    ("service",      "Service",        130, True),
    ("motif",        "Motif",          130, True),
    ("priorite",     "Priorité",       90,  False),
    ("statut",       "Statut",         100, False),
    ("heure_arrivee","Heure arrivée",  100, False),
    ("temps_attente","Temps attente",  100, False),
    ("satisfaction", "Satisfaction",   90,  False),
    ("contacts",     "Contact",        120, True),
]

_COL_KEYS    = [c[0] for c in _VISIBLE_COLS]
_COL_LABELS  = [c[1] for c in _VISIBLE_COLS]
_COL_WIDTHS  = [c[2] for c in _VISIBLE_COLS]
_COL_STRETCH = [c[3] for c in _VISIBLE_COLS]


# ── Styles ────────────────────────────────────────────────────────────────────

_BTN_PRIMARY = (
    "QPushButton { background:#1e3a5f; color:white; border-radius:5px;"
    " padding:5px 12px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#2a4f80; }"
    "QPushButton:pressed { background:#16294a; }"
    "QPushButton:disabled { background:#9ca3af; }"
)
_BTN_SUCCESS = (
    "QPushButton { background:#15803d; color:white; border-radius:5px;"
    " padding:5px 12px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#16a34a; }"
)
_BTN_DANGER = (
    "QPushButton { background:#b91c1c; color:white; border-radius:5px;"
    " padding:5px 12px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#dc2626; }"
)
_BTN_NEUTRAL = (
    "QPushButton { background:#64748b; color:white; border-radius:5px;"
    " padding:5px 12px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#475569; }"
)
_BTN_EXPORT = (
    "QPushButton { background:#0d9488; color:white; border-radius:5px;"
    " padding:5px 12px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#0f766e; }"
    "QPushButton:pressed { background:#0d6b63; }"
)
_INPUT_STYLE = (
    "QLineEdit, QComboBox, QDateEdit {"
    " border:1px solid #d1d5db; border-radius:4px;"
    " padding:4px 7px; font-size:12px; background:white; color:#1f2937; }"
    "QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color:#1e3a5f; border-width:2px; }"
)
_TABLE_STYLE = (
    "QTableWidget { border:1px solid #e2e8f0; border-radius:8px; font-size:12px; }"
    "QTableWidget::item { padding:4px 7px; border:none; }"
    "QTableWidget::item:selected { background:#bfdbfe; color:#1e3a5f; }"
    "QHeaderView::section {"
    " background:#1e3a5f; color:white; font-weight:700;"
    " font-size:11px; padding:6px 8px; border:none;"
    " border-right:1px solid #2a4f80; border-bottom:2px solid #3b82f6; }"
    "QHeaderView::section:last { border-right:none; }"
    "QHeaderView::section:hover { background:#2a4f80; cursor:pointer; }"
)
_FILTER_ROW_STYLE = (
    "QLineEdit { border:1px solid #cbd5e1; border-radius:3px;"
    " padding:3px 6px; font-size:11px; background:#f8fafc; color:#374151; }"
    "QLineEdit:focus { border-color:#3b82f6; background:white; }"
    "QComboBox { border:1px solid #cbd5e1; border-radius:3px;"
    " padding:2px 4px; font-size:11px; background:#f8fafc; color:#374151; }"
    "QComboBox:focus { border-color:#3b82f6; }"
)

# Couleurs des lignes par statut
_ROW_COLORS = {
    "traite":     (QColor(220, 252, 231), QColor(21, 128, 61)),    # vert
    "en_attente": (QColor(254, 226, 226), QColor(185, 28, 28)),    # rouge
    "en_cours":   (QColor(219, 234, 254), QColor(30, 64, 175)),    # bleu
    "non_traite": (QColor(254, 243, 199), QColor(146, 64, 14)),    # orange
}

# Couleurs des badges priorité
_PRIO_COLORS = {
    "haute":   ("#dc2626", "#ffffff"),
    "urgente": ("#7c3aed", "#ffffff"),
    "moyenne": ("#d97706", "#ffffff"),
    "normale": ("#6b7280", "#ffffff"),
}


# ── Requêtes SQL (filtre, tri et pagination côté base) ────────────────────────
# Aucune valeur saisie n'entre dans le SQL: les noms de colonnes viennent de ces
# dictionnaires fixes (liste blanche), les valeurs sont toujours des paramètres `?`.

_SQL_FROM = (
    "FROM accueil_demandeaccueil d"
    " LEFT JOIN accueil_service s ON d.service_demande_id = s.id"
    " LEFT JOIN accueil_motif   m ON d.motif_id = m.id"
)
_SQL_SELECT = {
    "id": "d.id", "date": "d.date", "nom": "d.nom", "prenom": "d.prenom",
    "numero_cnps": "d.numero_cnps", "service": "COALESCE(s.nom, '—')",
    "motif": "COALESCE(m.nom, '—')", "priorite": "d.priorite", "statut": "d.statut",
    "heure_arrivee": "d.heure_arrivee", "temps_attente": "d.temps_attente",
    "satisfaction": "d.satisfaction", "contacts": "d.contacts",
}
_SQL_TEXT = dict(_SQL_SELECT, satisfaction="CAST(d.satisfaction AS TEXT)")  # pour LIKE
_SQL_ORDER = dict(_SQL_SELECT, id="CAST(d.id AS INTEGER)")                  # tri numérique
_SQL_NUMERIC = frozenset({"id", "satisfaction"})
_SQL_EXACT = frozenset({"statut", "priorite", "service", "motif"})          # listes déroulantes
_LIKE = " LIKE ? ESCAPE '\\'"


def _like(valeur: str) -> str:
    """Motif LIKE « contient », jokers % _ \\ de la saisie neutralisés."""
    return "%" + valeur.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@dataclass(frozen=True)
class _Filtres:
    """Instantané immuable des filtres, du tri et de la page demandés."""

    date_from: str | None = None        # AAAA-MM-JJ inclus
    date_to: str | None = None          # AAAA-MM-JJ EXCLU (lendemain du dernier jour)
    search: str = ""
    cols: tuple = ()                    # ((colonne, valeur), ...)
    sort_col: str = "date"
    sort_asc: bool = False
    page: int = 1
    per_page: int = 50


def _where(f: _Filtres) -> tuple[str, list]:
    """Clause WHERE paramétrée. Dates en intervalle ouvert à droite pour rester indexables."""
    cond: list[str] = []
    params: list = []
    if f.date_from:
        cond.append("d.date >= ?")
        params.append(f.date_from)
    if f.date_to:
        cond.append("d.date < ?")
        params.append(f.date_to)
    if f.search:
        champs = " || ' ' || ".join(f"COALESCE({_SQL_TEXT[k]}, '')" for k in _COL_KEYS)
        cond.append(f"PYLOWER({champs}){_LIKE}")
        params.append(_like(f.search))
    for key, val in f.cols:
        if key not in _SQL_TEXT or not val:
            continue
        if key in _SQL_EXACT:
            cond.append(f"{_SQL_TEXT[key]} = ?")
            params.append(val)
        else:
            cond.append(f"PYLOWER({_SQL_TEXT[key]}){_LIKE}")
            params.append(_like(val))
    return (" WHERE " + " AND ".join(cond)) if cond else "", params


def _order(f: _Filtres) -> str:
    """ORDER BY sur colonne de la liste blanche; d.rowid départage de façon stable (et reste indexable)."""
    col = f.sort_col if f.sort_col in _SQL_ORDER else "date"
    sens = "ASC" if f.sort_asc else "DESC"
    nocase = "" if col in _SQL_NUMERIC else " COLLATE NOCASE"
    return f" ORDER BY {_SQL_ORDER[col]}{nocase} {sens}, d.rowid {sens}"


def lire_lignes(f: _Filtres, limit: int | None = None, offset: int = 0) -> list[dict]:
    """Lignes filtrées/triées; `_maj` = updated_at lu (contrôle optimiste à la modification)."""
    where, params = _where(f)
    select = ", ".join(f"{expr} AS {k}" for k, expr in _SQL_SELECT.items())
    return db.execute_query(
        f"SELECT {select}, COALESCE(d.updated_at, '') AS _maj {_SQL_FROM}{where}{_order(f)} LIMIT ? OFFSET ?",
        tuple(params) + (-1 if limit is None else limit, offset),
    )


def charger_page(f: _Filtres) -> dict:
    """Une page de résultats + totaux (demandes, filtrées, traitées, en attente) + listes de filtres."""
    where, params = _where(f)
    filtered = db.execute_query(f"SELECT COUNT(*) AS n {_SQL_FROM}{where}", tuple(params))[0]["n"]
    pages = max(1, -(-filtered // f.per_page))
    page = max(1, min(f.page, pages))
    rows = lire_lignes(f, f.per_page, (page - 1) * f.per_page)
    tot = db.execute_query(
        "SELECT COUNT(*) AS n, COALESCE(SUM(statut = 'traite'), 0) AS t,"
        " COALESCE(SUM(statut = 'en_attente'), 0) AS a FROM accueil_demandeaccueil"
    )[0]
    return {
        "rows": rows, "filtered": filtered, "page": page, "pages": pages,
        "total": tot["n"], "traite": tot["t"], "attente": tot["a"],
        "services": [r["nom"] for r in db.execute_query(
            "SELECT nom FROM accueil_service WHERE actif=1 ORDER BY nom")],
        "motifs": [r["nom"] for r in db.execute_query(
            "SELECT nom FROM accueil_motif WHERE actif=1 ORDER BY nom")],
    }


# ── Worker de rechargement ────────────────────────────────────────────────────

class _ReloadWorker(QObject):
    """Charge une page en tâche de fond; saute la lecture si `last_token` est toujours à jour."""

    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, filtres: _Filtres, last_token: tuple | None = None) -> None:
        super().__init__()
        self._filtres = filtres
        self._last_token = last_token

    def run(self) -> None:
        try:
            try:
                token = db.change_token()  # lu AVANT les données: une écriture concurrente relancera un tour
            except Exception:
                _LOG.warning("change_token indisponible, rechargement complet", exc_info=True)
                token = None
            if token is not None and token == self._last_token:
                self.finished.emit({"unchanged": True})
                return
            payload = charger_page(self._filtres)
            payload["token"] = token
            self.finished.emit(payload)
        except Exception as exc:
            _LOG.exception("Rechargement de la page Base de données impossible")
            self.failed.emit(str(exc))

_PRIORITES = ("normale", "moyenne", "haute")


def valider_demande(p: dict) -> Optional[str]:
    """Message d'erreur si la saisie est invalide, sinon None (date ISO, nom, satisfaction 1-5, priorité connue)."""
    if not p.get("nom"):
        return "Le nom est obligatoire."
    try:
        datetime.strptime(p.get("date") or "", "%Y-%m-%d")
    except ValueError:
        return "La date est obligatoire, au format AAAA-MM-JJ."
    heure = p.get("heure_arrivee")
    if heure:
        try:
            datetime.strptime(heure, "%H:%M:%S" if heure.count(":") == 2 else "%H:%M")
        except ValueError:
            return "L'heure d'arrivée doit être au format HH:MM:SS."
    sat = p.get("satisfaction")
    if sat and (not sat.isdigit() or not 1 <= int(sat) <= 5):
        return "La satisfaction doit être un entier de 1 à 5."
    if p.get("priorite") and p["priorite"] not in _PRIORITES:
        return "Priorité inconnue."
    return None


# ── Dialogue CRUD (champs sélectifs) ─────────────────────────────────────────

class _RecordDialog(QDialog):
    """Formulaire léger create/update — uniquement les champs métier utiles."""

    def __init__(self, initial: dict | None = None, mode: str = "create", parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.initial = initial or {}
        self.setWindowTitle("Créer une demande" if mode == "create" else "Modifier la demande")
        self.resize(540, 480)
        self._build_ui()

    def _v(self, key: str, default: str = "") -> str:
        v = self.initial.get(key)
        return default if v is None else str(v)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _le(key, default=""):
            w = QLineEdit(self._v(key, default))
            w.setStyleSheet(_INPUT_STYLE)
            return w

        def _cb(key, items):
            w = QComboBox()
            w.addItems(items)
            w.setStyleSheet(_INPUT_STYLE)
            idx = w.findText(self._v(key, items[0]))
            if idx >= 0:
                w.setCurrentIndex(idx)
            return w

        self._date     = _le("date", datetime.now().date().isoformat())
        self._nom      = _le("nom")
        self._prenom   = _le("prenom")
        self._cnps     = _le("numero_cnps")
        self._contacts = _le("contacts")
        self._arrivee  = _le("heure_arrivee", datetime.now().strftime("%H:%M:%S"))
        self._statut   = _cb("statut",   ["en_attente", "en_cours", "traite", "non_traite"])
        self._priorite = _cb("priorite", list(_PRIORITES))
        self._sat      = _le("satisfaction", "")

        form.addRow("Date *",          self._date)
        form.addRow("Nom *",           self._nom)
        form.addRow("Prénom",          self._prenom)
        form.addRow("N° CNPS",         self._cnps)
        form.addRow("Contact",         self._contacts)
        form.addRow("Heure arrivée",   self._arrivee)
        form.addRow("Statut",          self._statut)
        form.addRow("Priorité",        self._priorite)
        form.addRow("Satisfaction",    self._sat)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setStyleSheet(_BTN_PRIMARY)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(_BTN_NEUTRAL)
        buttons.accepted.connect(self._valider)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _valider(self) -> None:
        erreur = valider_demande(self.payload())
        if erreur:
            QMessageBox.warning(self, "Saisie invalide", erreur)
            return
        self.accept()

    def payload(self) -> dict:
        def _val(w):
            if isinstance(w, QComboBox):
                return w.currentText().strip() or None
            return w.text().strip() or None

        return {
            "date":         _val(self._date),
            "nom":          _val(self._nom),
            "prenom":       _val(self._prenom),
            "numero_cnps":  _val(self._cnps),
            "contacts":     _val(self._contacts),
            "heure_arrivee":_val(self._arrivee),
            "statut":       _val(self._statut),
            "priorite":     _val(self._priorite),
            "satisfaction": _val(self._sat),
        }


# ── Page principale ───────────────────────────────────────────────────────────

class DatabasePage(QMainWindow):
    """Page Base de données — filtres colonnes, export CSV, couleurs statut, tri en-tête."""

    TABLE = "accueil_demandeaccueil"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Base de données")
        # Tri courant : (col_key, ascending) — instance pour éviter partage entre fenêtres
        self._sort_col: str  = "date"
        self._sort_asc: bool = False

        self.page_records: list[dict] = []   # lignes de la page affichée (le reste reste en base)
        self.total_count = 0
        self.filtered_count = 0
        self.current_page  = 1
        self.items_per_page = 50
        self.total_pages    = 1

        self._services: list[str] = []
        self._motifs:   list[str] = []

        # Filtres date et recherche globale
        self._date_from: QDate | None = None
        self._date_to:   QDate | None = None
        self._global_search: str = ""

        self._refresh_in_progress = False
        self._refresh_pending     = False
        self._pending_manual      = False
        self._closing             = False
        self._last_token: tuple | None = None   # db.change_token() de la dernière lecture
        self._live: list[tuple[QThread, _ReloadWorker]] = []   # chargements en cours
        self._filter_timer = QTimer(self)       # debounce de la recherche et des filtres texte
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(_DEBOUNCE_MS)
        self._filter_timer.timeout.connect(lambda: self._apply_filters(reset_page=True))

        self._build_ui()
        self._load_data()
        self._init_auto_refresh()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_date_filter_bar())
        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_table(), 1)
        root.addWidget(self._build_pagination())

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1e3a5f, stop:1 #2a4f80); }"
        )
        hb = QHBoxLayout(header)
        hb.setContentsMargins(20, 12, 20, 12)
        hb.setSpacing(16)

        lbl = QLabel("🗄  Base de données — Demandes d'accueil")
        f = QFont(); f.setPointSize(13); f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet("color:white; background:transparent;")

        self._stat_total   = QLabel("Total : 0")
        self._stat_traite  = QLabel("Traitées : 0")
        self._stat_attente = QLabel("En attente : 0")
        self._stat_filtre  = QLabel("")
        for w in (self._stat_total, self._stat_traite, self._stat_attente):
            w.setStyleSheet("color:#93c5fd; font-size:12px; font-weight:600; background:transparent;")
        self._stat_filtre.setStyleSheet("color:#fde68a; font-size:12px; font-weight:600; background:transparent;")

        self._refresh_lbl = QLabel("• À jour")
        self._refresh_lbl.setStyleSheet("color:#22c55e; font-weight:600; background:transparent;")

        self._spinner = QProgressBar()
        self._spinner.setRange(0, 0)
        self._spinner.setMaximumWidth(46)
        self._spinner.setMaximumHeight(12)
        self._spinner.setVisible(False)

        hb.addWidget(lbl)
        hb.addStretch(1)
        for w in (self._stat_total, self._stat_traite, self._stat_attente, self._stat_filtre,
                  self._refresh_lbl, self._spinner):
            hb.addWidget(w)

        # ── Séparateur ────────────────────────────────────────────────────────
        sep = QLabel("|")
        sep.setStyleSheet("color: #4a6fa0; background: transparent; font-size: 16px;")
        hb.addWidget(sep)

        # ── Boutons CRUD + Export ─────────────────────────────────────────────
        _H_BTN = "QPushButton { border-radius:4px; padding:4px 11px; font-weight:600; font-size:12px; color:white; }"
        for label, bg, hover, slot in [
            ("＋",       "#22c55e", "#16a34a", self._on_create),
            ("✏",        "#3b82f6", "#2563eb", self._on_update),
            ("🗑",        "#ef4444", "#dc2626", self._on_delete),
            ("⬇ Excel",  "#0d9488", "#0f766e", self._on_export_excel),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                _H_BTN +
                f"QPushButton {{ background:{bg}; }}"
                f"QPushButton:hover {{ background:{hover}; }}"
            )
            btn.setMinimumHeight(28)
            if label in ("＋", "✏", "🗑"):
                btn.setMaximumWidth(34)
            btn.clicked.connect(slot)
            hb.addWidget(btn)

        return header

    # ── Barre de filtres date + recherche globale ─────────────────────────────

    _DATE_BAR_SS = (
        "QFrame#dateFilterBar { background:#1e3a5f; }"
        "QLabel { color:#cbd5e1; font-size:11px; font-weight:600; background:transparent; }"
        "QLineEdit { border:1px solid #4a6fa0; border-radius:4px; padding:4px 8px;"
        "  font-size:12px; background:#162d4a; color:white; }"
        "QLineEdit:focus { border-color:#60a5fa; background:#1a3557; }"
        "QLineEdit::placeholder { color:#64748b; }"
        "QDateEdit { border:1px solid #4a6fa0; border-radius:4px; padding:3px 6px;"
        "  font-size:11px; background:#162d4a; color:white; }"
        "QDateEdit:focus { border-color:#60a5fa; }"
        "QDateEdit::drop-down { border:none; width:16px; }"
        "QPushButton#periodBtn {"
        "  background:#253f60; color:#93c5fd; border:1px solid #3b5a82;"
        "  border-radius:4px; padding:3px 10px; font-size:11px; font-weight:600; }"
        "QPushButton#periodBtn:hover { background:#2a4f80; color:white; }"
        "QPushButton#periodBtn:checked { background:#3b82f6; color:white; border-color:#3b82f6; }"
        "QPushButton#resetBtn {"
        "  background:#ef4444; color:white; border-radius:4px;"
        "  padding:3px 10px; font-size:11px; font-weight:700; }"
        "QPushButton#resetBtn:hover { background:#dc2626; }"
    )

    def _build_date_filter_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("dateFilterBar")
        bar.setFixedHeight(50)
        bar.setStyleSheet(self._DATE_BAR_SS)

        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 6, 14, 6)
        hl.setSpacing(8)

        # ── Recherche globale ────────────────────────────────────────────
        lbl_s = QLabel("🔍")
        lbl_s.setStyleSheet("font-size:14px; color:white; background:transparent;")
        hl.addWidget(lbl_s)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Recherche dans tous les champs…")
        self._search_edit.setMinimumWidth(200)
        self._search_edit.setMaximumWidth(260)
        self._search_edit.setFixedHeight(30)
        self._search_edit.textChanged.connect(self._on_search_changed)
        hl.addWidget(self._search_edit)

        # ── Séparateur ───────────────────────────────────────────────────
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("QFrame { color:#3b5a82; background:#3b5a82; }")
        sep1.setFixedWidth(1)
        hl.addWidget(sep1)

        # ── Raccourcis période ───────────────────────────────────────────
        hl.addWidget(QLabel("Période :"))
        self._period_btns: dict[str, QPushButton] = {}
        for key, label in [
            ("today",  "Aujourd'hui"),
            ("week",   "Cette semaine"),
            ("month",  "Ce mois"),
            ("year",   "Cette année"),
            ("all",    "Tout"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("periodBtn")
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, k=key: self._on_period_clicked(k))
            self._period_btns[key] = btn
            hl.addWidget(btn)
        self._period_btns["all"].setChecked(True)

        # ── Séparateur ───────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("QFrame { color:#3b5a82; background:#3b5a82; }")
        sep2.setFixedWidth(1)
        hl.addWidget(sep2)

        # ── Plage personnalisée ──────────────────────────────────────────
        hl.addWidget(QLabel("Du :"))
        _cal_drop_qss = (
            f"QDateEdit::drop-down {{ image: url({_CAL_ICON_DB}); width: 14px; height: 14px; border: none; }}"
        )
        self._de_from = QDateEdit()
        self._de_from.setCalendarPopup(True)
        self._de_from.setDisplayFormat("dd/MM/yyyy")
        self._de_from.setDate(QDate.currentDate().addMonths(-1))
        self._de_from.setFixedHeight(28)
        self._de_from.setFixedWidth(100)
        self._de_from.setStyleSheet(_cal_drop_qss)
        self._de_from.dateChanged.connect(self._on_custom_date_changed)
        hl.addWidget(self._de_from)

        hl.addWidget(QLabel("Au :"))
        self._de_to = QDateEdit()
        self._de_to.setCalendarPopup(True)
        self._de_to.setDisplayFormat("dd/MM/yyyy")
        self._de_to.setDate(QDate.currentDate())
        self._de_to.setFixedHeight(28)
        self._de_to.setFixedWidth(100)
        self._de_to.setStyleSheet(_cal_drop_qss)
        self._de_to.dateChanged.connect(self._on_custom_date_changed)
        hl.addWidget(self._de_to)

        # Masquer par défaut (affiché seulement en mode "personnalisé")
        self._custom_widgets = [self._de_from, self._de_to,
                                 hl.itemAt(hl.count() - 3).widget(),  # label "Du"
                                 hl.itemAt(hl.count() - 1).widget()]  # label "Au"

        hl.addStretch()

        # ── Bouton réinitialiser ─────────────────────────────────────────
        btn_reset = QPushButton("✕  Réinitialiser")
        btn_reset.setObjectName("resetBtn")
        btn_reset.setFixedHeight(28)
        btn_reset.clicked.connect(self._reset_all_filters)
        hl.addWidget(btn_reset)

        return bar

    def _on_search_changed(self, text: str) -> None:
        self._global_search = text.strip().lower()
        self._filter_timer.start()

    def _on_period_clicked(self, key: str) -> None:
        # Décocher tous les boutons sauf le cliqué
        for k, b in self._period_btns.items():
            b.setChecked(k == key)

        today = QDate.currentDate()
        if key == "today":
            self._date_from = today
            self._date_to   = today
        elif key == "week":
            self._date_from = today.addDays(-today.dayOfWeek() + 1)  # lundi
            self._date_to   = today
        elif key == "month":
            self._date_from = QDate(today.year(), today.month(), 1)
            self._date_to   = today
        elif key == "year":
            self._date_from = QDate(today.year(), 1, 1)
            self._date_to   = today
        else:  # "all"
            self._date_from = None
            self._date_to   = None

        self._apply_filters(reset_page=True)

    def _on_custom_date_changed(self) -> None:
        # Décocher les raccourcis — mode personnalisé
        for b in self._period_btns.values():
            b.setChecked(False)
        self._date_from = self._de_from.date()
        self._date_to   = self._de_to.date()
        self._apply_filters(reset_page=True)

    def _reset_all_filters(self) -> None:
        # Réinitialiser recherche
        self._search_edit.blockSignals(True)
        self._search_edit.clear()
        self._search_edit.blockSignals(False)
        self._global_search = ""

        # Réinitialiser dates
        self._date_from = None
        self._date_to   = None
        for k, b in self._period_btns.items():
            b.setChecked(k == "all")

        # Réinitialiser filtres colonnes
        for key, w in self._filter_widgets.items():
            if isinstance(w, QComboBox):
                w.blockSignals(True)
                w.setCurrentIndex(0)
                w.blockSignals(False)
            elif isinstance(w, QLineEdit):
                w.blockSignals(True)
                w.clear()
                w.blockSignals(False)

        self._apply_filters(reset_page=True)

    # ── Toolbar (actions + filtres globaux) ───────────────────────────────────

    # ── Barre de filtres par colonne ──────────────────────────────────────────

    def _build_filter_bar(self) -> QFrame:
        """Ligne de filtres sous le header du tableau, un widget par colonne visible."""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background:#eef2f7; border-bottom:2px solid #cbd5e1; }"
        )
        frame.setFixedHeight(34)

        # Positionnement manuel via setGeometry() — pas de layout manager sur ce frame
        self._filter_frame = frame
        self._filter_widgets: dict[str, QWidget] = {}

        for key in _COL_KEYS:
            if key == "statut":
                w = QComboBox(frame)
                w.setStyleSheet(_FILTER_ROW_STYLE)
                w.addItem("Tous", "")
                for s in ["en_attente", "en_cours", "traite", "non_traite"]:
                    w.addItem(s, s)
                w.currentIndexChanged.connect(lambda _: self._apply_filters(reset_page=True))
            elif key == "priorite":
                w = QComboBox(frame)
                w.setStyleSheet(_FILTER_ROW_STYLE)
                w.addItem("Toutes", "")
                for p in list(_PRIORITES):
                    w.addItem(p, p)
                w.currentIndexChanged.connect(lambda _: self._apply_filters(reset_page=True))
            elif key == "service":
                w = QComboBox(frame)
                w.setStyleSheet(_FILTER_ROW_STYLE)
                w.addItem("Tous", "")
                w.currentIndexChanged.connect(lambda _: self._apply_filters(reset_page=True))
                self._service_filter_cb = w
            elif key == "motif":
                w = QComboBox(frame)
                w.setStyleSheet(_FILTER_ROW_STYLE)
                w.addItem("Tous", "")
                w.currentIndexChanged.connect(lambda _: self._apply_filters(reset_page=True))
                self._motif_filter_cb = w
            elif key == "id":
                # Colonne ID : pas de filtre affiché (juste un label vide)
                w = QLabel("", frame)
            else:
                w = QLineEdit(frame)
                w.setStyleSheet(_FILTER_ROW_STYLE)
                w.setPlaceholderText("▼")
                w.textChanged.connect(lambda _: self._filter_timer.start())

            w.setFixedHeight(26)
            self._filter_widgets[key] = w

        return frame

    def _sync_filter_bar(self) -> None:
        """Repositionne les filtres colonnes pour qu'ils s'alignent sur le tableau."""
        hh = self.table.horizontalHeader()
        x_offset = self.table.verticalHeader().width() if self.table.verticalHeader().isVisible() else 0
        x_scroll = self.table.horizontalScrollBar().value()
        frame_h = self._filter_frame.height()
        pad_y = (frame_h - 26) // 2

        x = x_offset - x_scroll
        for i, key in enumerate(_COL_KEYS):
            w = self._filter_widgets.get(key)
            if w is None:
                continue
            col_w = hh.sectionSize(i)
            margin = 3
            w.setGeometry(x + margin, pad_y, max(col_w - margin * 2, 10), 26)
            x += col_w

    # ── Tableau ───────────────────────────────────────────────────────────────

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget(self)
        self.table.setColumnCount(len(_COL_KEYS))
        self.table.setHorizontalHeaderLabels(_COL_LABELS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(False)   # géré manuellement
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setSortingEnabled(False)   # tri manuel via clic en-tête

        hh = self.table.horizontalHeader()
        for i, (stretch, width) in enumerate(zip(_COL_STRETCH, _COL_WIDTHS)):
            if stretch:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, width)

        # Tri sur clic en-tête
        hh.sectionClicked.connect(self._on_header_clicked)
        # Synchronisation filtre/scroll
        hh.sectionResized.connect(lambda *_: self._sync_filter_bar())
        self.table.horizontalScrollBar().valueChanged.connect(lambda _: self._sync_filter_bar())

        return self.table

    # ── Barre de pagination ───────────────────────────────────────────────────

    def _build_pagination(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet("QFrame { background:#f1f5f9; border-top:1px solid #e2e8f0; }"
                          "QLabel { background:transparent; font-size:12px; color:#374151; }")
        box = QHBoxLayout(bar)
        box.setContentsMargins(12, 5, 12, 5)
        box.setSpacing(6)

        self._items_combo = QComboBox()
        self._items_combo.setStyleSheet(_INPUT_STYLE)
        self._items_combo.addItems(["20", "50", "100", "200", "Tous"])
        self._items_combo.setCurrentIndex(1)   # 50 par défaut
        self._items_combo.setMaximumWidth(75)
        self._items_combo.currentTextChanged.connect(self._on_items_changed)
        box.addWidget(QLabel("Lignes :"))
        box.addWidget(self._items_combo)

        box.addStretch(1)

        self._pag_label = QLabel("Page 1 / 1")
        self._pag_label.setStyleSheet("font-weight:600;")
        box.addWidget(self._pag_label)

        for sym, slot in [("◀◀", self._goto_first), ("◀", self._goto_prev),
                           ("▶", self._goto_next),   ("▶▶", self._goto_last)]:
            btn = QPushButton(sym)
            btn.setMaximumWidth(34)
            btn.setMinimumHeight(26)
            btn.setStyleSheet(_BTN_NEUTRAL)
            btn.clicked.connect(slot)
            box.addWidget(btn)

        return bar

    # ── Auto-refresh ──────────────────────────────────────────────────────────

    def _init_auto_refresh(self) -> None:
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._refresh_auto)
        self._auto_timer.start(AppConfig.AUTO_REFRESH_INTERVAL_MS)

    # ── Chargement (SQL: filtre, tri et pagination côté base) ─────────────────

    def _load_data(self) -> None:
        self._request_load(auto=False)

    def _refresh_auto(self) -> None:
        """Rafraîchissement périodique: sans effet si rien n'a changé en base (change_token)."""
        self._request_load(auto=True)

    def _filtres(self) -> _Filtres:
        """Instantané des filtres, du tri et de la page affichés à l'écran."""
        return _Filtres(
            date_from=self._date_from.toString("yyyy-MM-dd") if self._date_from else None,
            date_to=self._date_to.addDays(1).toString("yyyy-MM-dd") if self._date_to else None,
            search=self._global_search,
            cols=tuple((k, v) for k in _COL_KEYS if (v := self._get_filter_value(k))),
            sort_col=self._sort_col, sort_asc=self._sort_asc,
            page=self.current_page, per_page=self.items_per_page,
        )

    def _request_load(self, auto: bool = False) -> None:
        """Lance un chargement. `auto=True`: saute si le jeton de changement est inchangé."""
        if self._closing:
            return
        if self._refresh_in_progress:
            self._refresh_pending = True
            self._pending_manual = self._pending_manual or not auto
            return
        self._refresh_in_progress = True
        if not auto:
            self._spinner.setVisible(True)
            self._set_state("• Synchronisation…", "#1e88e5")
        self._start_worker(self._last_token if auto else None)

    def _start_worker(self, last_token: tuple | None) -> None:
        thread = QThread(self)
        worker = _ReloadWorker(self._filtres(), last_token)
        worker.moveToThread(thread)
        self._live.append((thread, worker))  # références gardées jusqu'à la fin réelle du thread
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(lambda: self._on_thread_done(thread))
        thread.start()

    def _on_thread_done(self, thread: QThread) -> None:
        self._live = [(t, w) for t, w in self._live if t is not thread]
        try:
            thread.deleteLater()
        except RuntimeError:
            pass

    def _finalize_refresh(self) -> None:
        self._refresh_in_progress = False
        self._spinner.setVisible(False)
        if self._refresh_pending and not self._closing:
            self._refresh_pending = False
            manual, self._pending_manual = self._pending_manual, False
            QTimer.singleShot(0, lambda: self._request_load(auto=not manual))

    def _on_finished(self, payload: dict) -> None:
        if self._closing:
            return
        try:
            if payload.get("unchanged"):
                self._set_state("• À jour", "#22c55e")
            else:
                self._apply_payload(payload)
        except Exception:
            _LOG.exception("Rendu de la page Base de données impossible")
            self._set_state("• Erreur d'affichage", "#c62828")
        finally:
            self._finalize_refresh()

    def _on_failed(self, msg: str) -> None:
        if self._closing:
            return
        self._last_token = None  # forcer un vrai rechargement au prochain tour
        self._set_state("• Erreur sync", "#c62828")
        self._finalize_refresh()

    def _apply_payload(self, payload: dict) -> None:
        self._last_token = payload.get("token")
        self.page_records = payload["rows"]
        self.total_count = payload["total"]
        self.filtered_count = payload["filtered"]
        self.current_page = payload["page"]
        self.total_pages = payload["pages"]
        self._refresh_filter_combos(payload["services"], payload["motifs"])
        self._render_page()
        self._stat_total.setText(f"Total : {self.total_count:,}")
        self._stat_traite.setText(f"Traitées : {payload['traite']:,}")
        self._stat_attente.setText(f"En attente : {payload['attente']:,}")
        n = self.filtered_count
        self._stat_filtre.setText(f"▶ {n:,} résultats filtrés" if n < self.total_count else "")
        self._set_state("• À jour", "#22c55e")

    def _refresh_filter_combos(self, services: list[str], motifs: list[str]) -> None:
        for cb, items, attr in [
            (self._service_filter_cb, services, "_services"),
            (self._motif_filter_cb,   motifs,   "_motifs"),
        ]:
            if items == getattr(self, attr):
                continue
            cur = cb.currentData()
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("Tous", "")
            for s in items:
                cb.addItem(s, s)
            idx = cb.findData(cur)
            if idx >= 0:
                cb.setCurrentIndex(idx)
            cb.blockSignals(False)
            setattr(self, attr, items)

    # ── Filtrage / tri ────────────────────────────────────────────────────────

    def _get_filter_value(self, key: str) -> str:
        w = self._filter_widgets.get(key)
        if w is None:
            return ""
        if isinstance(w, QComboBox):
            return w.currentData() or ""
        if isinstance(w, QLineEdit):
            return w.text().strip().lower()
        return ""

    def _apply_filters(self, reset_page: bool = True) -> None:
        """Recharge la page courante avec les filtres/tri affichés (SQL)."""
        self._filter_timer.stop()
        if reset_page:
            self.current_page = 1
        self._request_load(auto=False)

    def _on_header_clicked(self, col_idx: int) -> None:
        key = _COL_KEYS[col_idx]
        if self._sort_col == key:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = key
            self._sort_asc = False
        self._update_header_arrows()
        self._apply_filters(reset_page=False)

    def _update_header_arrows(self) -> None:
        for i, (key, label) in enumerate(zip(_COL_KEYS, _COL_LABELS)):
            if key == self._sort_col:
                arrow = " ▲" if self._sort_asc else " ▼"
                self.table.horizontalHeaderItem(i).setText(label + arrow)
            else:
                self.table.horizontalHeaderItem(i).setText(label)

    # ── Rendu tableau ─────────────────────────────────────────────────────────

    def _render_page(self) -> None:
        self._display_records(self.page_records)
        self._pag_label.setText(f"Page {self.current_page} / {self.total_pages}")
        QTimer.singleShot(0, self._sync_filter_bar)

    def _display_records(self, records: list[dict]) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(records))

        for row_idx, rec in enumerate(records):
            statut = str(rec.get("statut") or "").strip().lower()
            row_bg, _ = _ROW_COLORS.get(statut, (QColor(255, 255, 255), QColor(0, 0, 0)))
            row_bg_alt = row_bg.darker(104) if row_idx % 2 == 1 else row_bg

            for col_idx, key in enumerate(_COL_KEYS):
                val  = rec.get(key)
                text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(QBrush(row_bg_alt))

                # Couleur spéciale par colonne
                if key == "statut":
                    bg, fg = _ROW_COLORS.get(statut, (row_bg_alt, QColor("#374151")))
                    item.setBackground(QBrush(bg))
                    item.setForeground(QBrush(fg))
                    item.setFont(QFont("", 9, QFont.Weight.Bold))
                elif key == "priorite":
                    bg_hex, fg_hex = _PRIO_COLORS.get(text.lower(), ("#6b7280", "#ffffff"))
                    # Texte coloré: le fond d'item est écrasé par le QSS global (texte blanc sur blanc)
                    item.setForeground(QBrush(QColor(bg_hex)))
                    item.setFont(QFont("", 9, QFont.Weight.Bold))
                elif key == "satisfaction" and text:
                    try:
                        stars = int(float(text))
                        item.setText("★" * stars + "☆" * (5 - stars))
                        color = ["#dc2626","#f59e0b","#f59e0b","#22c55e","#22c55e"][min(stars-1,4)] if stars else "#9ca3af"
                        item.setForeground(QBrush(QColor(color)))
                    except ValueError:
                        pass
                elif val is None:
                    item.setForeground(QBrush(QColor("#9ca3af")))

                self.table.setItem(row_idx, col_idx, item)

        self.table.setUpdatesEnabled(True)

    # ── Pagination ────────────────────────────────────────────────────────────

    _MAX_DISPLAY_ALL = 500  # Seuil de sécurité pour l'option "Tous"

    def _on_items_changed(self, value: str) -> None:
        self.items_per_page = self._MAX_DISPLAY_ALL if value == "Tous" else int(value)
        self._apply_filters(reset_page=True)

    def _goto(self, page: int) -> None:
        page = max(1, min(page, self.total_pages))
        if page != self.current_page:
            self.current_page = page
            self._request_load(auto=False)

    def _goto_first(self) -> None:
        self._goto(1)

    def _goto_prev(self) -> None:
        self._goto(self.current_page - 1)

    def _goto_next(self) -> None:
        self._goto(self.current_page + 1)

    def _goto_last(self) -> None:
        self._goto(self.total_pages)


    # ── Export CSV ────────────────────────────────────────────────────────────

    def _on_export_excel(self) -> None:
        """Export des données filtrées vers un fichier Excel (.xlsx) avec mise en forme."""
        if not self.filtered_count:
            QMessageBox.information(self, "Export Excel", "Aucune donnée à exporter.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"demandes_accueil_{ts}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le fichier Excel",
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "Fichiers Excel (*.xlsx);;Tous les fichiers (*)",
        )
        if not path:
            return

        try:
            # Toutes les lignes filtrées (pas seulement la page affichée), relues à l'instant de l'export
            rows = lire_lignes(self._filtres())
            nb = len(rows)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Demandes Accueil"

            # ── Styles header ─────────────────────────────────────────────────
            hdr_fill   = PatternFill("solid", fgColor="1E3A5F")
            hdr_font   = XlFont(bold=True, color="FFFFFF", size=11)
            hdr_align  = Alignment(horizontal="center", vertical="center")
            thin_side  = Side(style="thin", color="CBD5E1")
            thin_border = Border(left=thin_side, right=thin_side,
                                 top=thin_side, bottom=thin_side)

            # ── Couleurs par statut ───────────────────────────────────────────
            _STATUS_FILL = {
                "traite":     PatternFill("solid", fgColor="DCFCE7"),  # vert pâle
                "en_attente": PatternFill("solid", fgColor="FEE2E2"),  # rouge pâle
                "en_cours":   PatternFill("solid", fgColor="DBEAFE"),  # bleu pâle
                "non_traite": PatternFill("solid", fgColor="FEF3C7"),  # orange pâle
            }
            _STATUS_FONT = {
                "traite":     XlFont(color="166534", bold=True),
                "en_attente": XlFont(color="991B1B", bold=True),
                "en_cours":   XlFont(color="1E40AF", bold=True),
                "non_traite": XlFont(color="92400E", bold=True),
            }
            _PRIO_FONT = {
                "haute":   XlFont(color="DC2626", bold=True),
                "urgente": XlFont(color="7C3AED", bold=True),
                "moyenne": XlFont(color="D97706", bold=True),
                "normale": XlFont(color="6B7280"),
            }

            # ── En-têtes ──────────────────────────────────────────────────────
            ws.append(_COL_LABELS)
            for col_idx, _ in enumerate(_COL_LABELS, start=1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill   = hdr_fill
                cell.font   = hdr_font
                cell.alignment = hdr_align
                cell.border = thin_border

            ws.row_dimensions[1].height = 20

            # ── Données ───────────────────────────────────────────────────────
            for row_idx, rec in enumerate(rows, start=2):
                statut = str(rec.get("statut") or "").strip().lower()
                prio   = str(rec.get("priorite") or "").strip().lower()
                row_fill = _STATUS_FILL.get(statut)

                for col_idx, key in enumerate(_COL_KEYS, start=1):
                    val  = rec.get(key)
                    text = "" if val is None else str(val)
                    cell = ws.cell(row=row_idx, column=col_idx, value=text)
                    if text.startswith("="):
                        cell.data_type = "s"  # texte saisi par un agent: ne jamais l'évaluer comme formule
                    cell.alignment = Alignment(vertical="center")
                    cell.border = thin_border

                    if key == "statut":
                        cell.fill = _STATUS_FILL.get(statut, PatternFill())
                        cell.font = _STATUS_FONT.get(statut, XlFont())
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif key == "priorite":
                        cell.font = _PRIO_FONT.get(prio, XlFont())
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif row_fill:
                        cell.fill = row_fill

                ws.row_dimensions[row_idx].height = 16

            # ── Largeurs colonnes ─────────────────────────────────────────────
            col_widths_xl = [8, 12, 16, 14, 14, 20, 20, 12, 14, 14, 14, 14, 18]
            for i, w in enumerate(col_widths_xl, start=1):
                ws.column_dimensions[get_column_letter(i)].width = w

            # ── Figer la première ligne ────────────────────────────────────────
            ws.freeze_panes = "A2"

            # ── Filtre auto Excel ─────────────────────────────────────────────
            ws.auto_filter.ref = ws.dimensions

            wb.save(path)
            QMessageBox.information(
                self, "Export réussi",
                f"✅ {nb:,} lignes exportées\n{path}",
            )
        except Exception as exc:
            _LOG.exception("Export Excel impossible")
            QMessageBox.critical(self, "Export Excel", f"Erreur lors de l'export :\n{exc}")

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _selected_record(self) -> Optional[dict]:
        row = self.table.currentRow()
        if 0 <= row < len(self.page_records):
            return self.page_records[row]
        return None

    def _invalidate_and_reload(self) -> None:
        """Après une action manuelle: oublie le jeton pour relire la base quoi qu'il arrive."""
        self._last_token = None
        self._request_load(auto=False)

    def _on_create(self) -> None:
        dlg = _RecordDialog(mode="create", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.payload()
        sat = p.pop("satisfaction")
        for k in ("nom", "prenom", "numero_cnps", "contacts"):
            p[k] = p[k] or ""
        try:
            ok = DemandeAccueil(**p, satisfaction=int(sat) if sat else None).save()
            if not ok:
                raise RuntimeError("enregistrement refusé, voir le journal")
        except Exception as exc:
            _LOG.exception("Création de demande impossible")
            QMessageBox.critical(self, "Création", f"Échec de la création : {exc}")
            return
        self._invalidate_and_reload()

    def _on_update(self) -> None:
        rec = self._selected_record()
        if not rec:
            QMessageBox.information(self, "Modification", "Sélectionnez une ligne à modifier.")
            return
        maj_lue = rec.get("_maj") or ""  # updated_at au moment d'ouvrir le dialogue
        dlg = _RecordDialog(initial=rec, mode="update", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.payload()
        p["updated_at"] = datetime.now().isoformat()
        parts = [f"{k} = ?" for k in p]  # clés issues de payload(): fixes, jamais saisies
        vals  = list(p.values()) + [rec.get("id"), maj_lue]
        try:
            # Contrôle optimiste: ne modifie que si personne n'a touché la ligne depuis la lecture
            n = db.execute_update(
                f"UPDATE {self.TABLE} SET {', '.join(parts)}"
                " WHERE id = ? AND COALESCE(updated_at, '') = ?",
                tuple(vals),
            )
            existe = bool(n) or bool(db.execute_query(
                f"SELECT 1 FROM {self.TABLE} WHERE id = ?", (rec.get("id"),)))
        except Exception as exc:
            _LOG.exception("Modification de demande impossible")
            QMessageBox.critical(self, "Modification", f"Échec de la modification : {exc}")
            return
        if not n:
            QMessageBox.warning(
                self, "Modification non enregistrée",
                "Cette demande a été modifiée depuis un autre poste." if existe
                else "Cette demande a été supprimée depuis un autre poste.",
            )
        self._invalidate_and_reload()

    def _on_delete(self) -> None:
        rec = self._selected_record()
        if not rec:
            QMessageBox.information(self, "Suppression", "Sélectionnez une ligne à supprimer.")
            return
        rid = rec.get("id")
        if QMessageBox.question(
            self, "Confirmer", f"Supprimer la demande ID {rid} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            n = db.execute_update(f"DELETE FROM {self.TABLE} WHERE id = ?", (rid,))
        except Exception as exc:
            _LOG.exception("Suppression de demande impossible")
            QMessageBox.critical(self, "Suppression", f"Échec de la suppression : {exc}")
            return
        if not n:
            QMessageBox.information(self, "Suppression", "Cette demande avait déjà été supprimée depuis un autre poste.")
        self._invalidate_and_reload()

    # ── État visuel ───────────────────────────────────────────────────────────

    def _set_state(self, text: str, color: str) -> None:
        self._refresh_lbl.setText(text)
        self._refresh_lbl.setStyleSheet(f"color:{color}; font-weight:600; background:transparent;")

    # ── Fermeture propre ──────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._closing = True
        for t in (getattr(self, "_auto_timer", None), self._filter_timer):
            if t is not None:
                t.stop()
        for thread, _ in list(self._live):
            try:
                thread.quit()
                if not thread.wait(1500):
                    # Lecture réseau lente: on détache le thread pour ne pas le détruire en marche
                    thread.setParent(None)
                    _THREADS_ORPHELINS.append(thread)
                    thread.finished.connect(lambda t=thread: _THREADS_ORPHELINS.remove(t)
                                            if t in _THREADS_ORPHELINS else None)
            except RuntimeError:
                pass
        super().closeEvent(event)
