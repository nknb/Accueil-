"""Page Base de données — design moderne avec filtres colonnes, export Excel et couleurs statut."""

from __future__ import annotations

import os
from collections import Counter
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
    QTextEdit,
    QFileDialog,
)

from config import AppConfig
from database.connection import db


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


# ── Worker de rechargement ────────────────────────────────────────────────────

class _ReloadWorker(QObject):
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def run(self) -> None:
        try:
            records = db.execute_query(
                """SELECT
                    d.id, d.date, d.nom, d.prenom, d.numero_cnps,
                    COALESCE(s.nom, '—') AS service,
                    COALESCE(m.nom, '—') AS motif,
                    d.priorite, d.statut,
                    d.heure_arrivee, d.temps_attente,
                    d.satisfaction, d.contacts
                FROM accueil_demandeaccueil d
                LEFT JOIN accueil_service s ON d.service_demande_id = s.id
                LEFT JOIN accueil_motif   m ON d.motif_id = m.id
                ORDER BY COALESCE(d.updated_at, d.created_at, d.date) DESC, d.id DESC"""
            )
            services  = [r["nom"] for r in db.execute_query(
                "SELECT nom FROM accueil_service WHERE actif=1 ORDER BY nom")]
            motifs    = [r["nom"] for r in db.execute_query(
                "SELECT nom FROM accueil_motif WHERE actif=1 ORDER BY nom")]
            self.finished.emit({"records": records, "services": services, "motifs": motifs})
        except Exception as exc:
            self.failed.emit(str(exc))


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
        self._priorite = _cb("priorite", ["normale", "moyenne", "haute", "urgente"])
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
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

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

        self.all_records:      list[dict] = []
        self.filtered_records: list[dict] = []
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
        self._last_sig: tuple | None = None
        self._reload_thread: QThread | None = None
        self._reload_worker: _ReloadWorker | None = None
        self._cache: dict = {}
        self._cache_ttl_sec = AppConfig.DATABASE_CACHE_TTL_SEC

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
        self._apply_filters(reset_page=True)

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
                for p in ["normale", "moyenne", "haute", "urgente"]:
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
                w.textChanged.connect(lambda _: self._apply_filters(reset_page=True))

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
        self._auto_timer.timeout.connect(self._refresh_discreet)
        self._auto_timer.start(AppConfig.AUTO_REFRESH_INTERVAL_MS)

    # ── Chargement / cache ────────────────────────────────────────────────────

    def _load_data(self) -> None:
        self._refresh_discreet(force=True)

    def _get_cached(self) -> Optional[dict]:
        entry = self._cache.get("payload")
        if not entry:
            return None
        if (datetime.now() - entry["ts"]).total_seconds() > self._cache_ttl_sec:
            return None
        return entry["data"]

    def _set_cached(self, data: dict) -> None:
        self._cache["payload"] = {"ts": datetime.now(), "data": data}

    def _refresh_discreet(self, force: bool = False) -> None:
        if self._refresh_in_progress:
            self._refresh_pending = True
            return
        self._refresh_in_progress = True
        self._spinner.setVisible(True)
        self._set_state("• Synchronisation…", "#1e88e5")

        if not force:
            cached = self._get_cached()
            if cached is not None:
                try:
                    self._apply_payload(cached)
                finally:
                    self._finalize_refresh()
                return

        self._start_worker()

    def _start_worker(self) -> None:
        self._reload_thread = QThread(self)
        self._reload_worker = _ReloadWorker()
        self._reload_worker.moveToThread(self._reload_thread)
        self._reload_thread.started.connect(self._reload_worker.run)
        self._reload_worker.finished.connect(self._on_finished)
        self._reload_worker.failed.connect(self._on_failed)
        self._reload_worker.finished.connect(self._reload_thread.quit)
        self._reload_worker.failed.connect(self._reload_thread.quit)
        self._reload_thread.finished.connect(self._on_thread_done)
        self._reload_thread.start()

    def _on_thread_done(self) -> None:
        thread = self._reload_thread
        self._reload_thread = None
        self._reload_worker = None
        if thread:
            try:
                thread.deleteLater()
            except RuntimeError:
                pass

    def _finalize_refresh(self) -> None:
        self._refresh_in_progress = False
        self._spinner.setVisible(False)
        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self._refresh_discreet)

    def _on_finished(self, payload: dict) -> None:
        try:
            self._set_cached(payload)
            self._apply_payload(payload)
        finally:
            self._finalize_refresh()

    def _on_failed(self, msg: str) -> None:
        self._set_state("• Erreur sync", "#c62828")
        self._finalize_refresh()

    def _apply_payload(self, payload: dict) -> None:
        records  = payload.get("records") or []
        services = payload.get("services") or []
        motifs   = payload.get("motifs") or []

        sig = tuple((r.get("id"), r.get("statut")) for r in records)
        if sig == self._last_sig:
            self._set_state("• À jour", "#22c55e")
            return
        self._last_sig = sig
        self.all_records = records

        # Mettre à jour les ComboBox de filtre Service / Motif
        self._refresh_filter_combos(services, motifs)

        self._apply_filters(reset_page=True)
        self._update_stats()
        self._set_state("• À jour", "#22c55e")

    def _refresh_filter_combos(self, services: list[str], motifs: list[str]) -> None:
        for cb, items, attr in [
            (self._service_filter_cb, services, "_services"),
            (self._motif_filter_cb,   motifs,   "_motifs"),
        ]:
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
        col_filters = {k: self._get_filter_value(k) for k in _COL_KEYS}
        # Pré-cache : True = exact match (QComboBox), False = sous-chaîne (QLineEdit)
        combo_keys = frozenset(
            k for k in _COL_KEYS if isinstance(self._filter_widgets.get(k), QComboBox)
        )

        result = []
        for rec in self.all_records:
            # ── Filtre plage de dates ────────────────────────────────────
            if self._date_from or self._date_to:
                raw_date = str(rec.get("date") or "")[:10]  # "YYYY-MM-DD"
                try:
                    rec_date = QDate.fromString(raw_date, "yyyy-MM-dd")
                    if not rec_date.isValid():
                        continue
                    if self._date_from and rec_date < self._date_from:
                        continue
                    if self._date_to and rec_date > self._date_to:
                        continue
                except Exception:
                    continue

            # ── Recherche globale (tous les champs) ──────────────────────
            if self._global_search:
                all_text = " ".join(str(v) for v in rec.values() if v is not None).lower()
                if self._global_search not in all_text:
                    continue

            # ── Filtres colonnes ─────────────────────────────────────────
            skip = False
            for key, fval in col_filters.items():
                if not fval:
                    continue
                cell = str(rec.get(key) or "").lower()
                if key in combo_keys:
                    if cell != fval:
                        skip = True; break
                else:
                    if fval not in cell:
                        skip = True; break
            if skip:
                continue
            result.append(rec)

        self.filtered_records = self._sort_records(result)
        if reset_page:
            self.current_page = 1
        n = len(self.filtered_records)
        self.total_pages = max(1, (n + self.items_per_page - 1) // self.items_per_page)
        self.current_page = max(1, min(self.current_page, self.total_pages))
        self._render_page()
        self._update_filter_stat(n)

    def _sort_records(self, records: list[dict]) -> list[dict]:
        col = self._sort_col

        def _key(rec):
            v = rec.get(col)
            if v is None:
                return (9, "")
            text = str(v).strip()
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return (0, datetime.strptime(text[:len(fmt)], fmt))
                except ValueError:
                    pass
            try:
                return (1, float(text))
            except (ValueError, TypeError):
                pass
            return (2, text.lower())

        return sorted(records, key=_key, reverse=not self._sort_asc)

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
        hh = self.table.horizontalHeader()
        for i, (key, label) in enumerate(zip(_COL_KEYS, _COL_LABELS)):
            if key == self._sort_col:
                arrow = " ▲" if self._sort_asc else " ▼"
                self.table.horizontalHeaderItem(i).setText(label + arrow)
            else:
                self.table.horizontalHeaderItem(i).setText(label)

    # ── Rendu tableau ─────────────────────────────────────────────────────────

    def _render_page(self) -> None:
        start = (self.current_page - 1) * self.items_per_page
        page  = self.filtered_records[start: start + self.items_per_page]
        self._display_records(page)
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
                    item.setBackground(QBrush(QColor(bg_hex)))
                    item.setForeground(QBrush(QColor(fg_hex)))
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

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _update_stats(self) -> None:
        total  = len(self.all_records)
        counts = Counter(str(r.get("statut") or "").lower() for r in self.all_records)
        self._stat_total.setText(f"Total : {total:,}")
        self._stat_traite.setText(f"Traitées : {counts['traite']:,}")
        self._stat_attente.setText(f"En attente : {counts['en_attente']:,}")

    def _update_filter_stat(self, n: int) -> None:
        total = len(self.all_records)
        if n < total:
            self._stat_filtre.setText(f"▶ {n:,} résultats filtrés")
        else:
            self._stat_filtre.setText("")

    # ── Filtres toolbar ───────────────────────────────────────────────────────

    def _on_reset_all(self) -> None:
        for w in self._filter_widgets.values():
            if isinstance(w, QLineEdit):
                w.clear()
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(0)
        self._apply_filters(reset_page=True)

    # ── Pagination ────────────────────────────────────────────────────────────

    _MAX_DISPLAY_ALL = 500  # Seuil de sécurité pour l'option "Tous"

    def _on_items_changed(self, value: str) -> None:
        if value == "Tous":
            self.items_per_page = min(len(self.all_records), self._MAX_DISPLAY_ALL)
        else:
            self.items_per_page = int(value)
        self.current_page = 1
        self._apply_filters(reset_page=True)

    def _goto_first(self) -> None:
        if self.current_page != 1:
            self.current_page = 1; self._render_page()

    def _goto_prev(self) -> None:
        if self.current_page > 1:
            self.current_page -= 1; self._render_page()

    def _goto_next(self) -> None:
        if self.current_page < self.total_pages:
            self.current_page += 1; self._render_page()

    def _goto_last(self) -> None:
        if self.current_page != self.total_pages:
            self.current_page = self.total_pages; self._render_page()

    # ── Export CSV ────────────────────────────────────────────────────────────

    def _on_export_excel(self) -> None:
        """Export des données filtrées vers un fichier Excel (.xlsx) avec mise en forme."""
        if not self.filtered_records:
            QMessageBox.information(self, "Export Excel", "Aucune donnée à exporter.")
            return

        nb = len(self.filtered_records)
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
            for row_idx, rec in enumerate(self.filtered_records, start=2):
                statut = str(rec.get("statut") or "").strip().lower()
                prio   = str(rec.get("priorite") or "").strip().lower()
                row_fill = _STATUS_FILL.get(statut)

                for col_idx, key in enumerate(_COL_KEYS, start=1):
                    val  = rec.get(key)
                    text = "" if val is None else str(val)
                    cell = ws.cell(row=row_idx, column=col_idx, value=text)
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
            QMessageBox.critical(self, "Export Excel", f"Erreur lors de l'export :\n{exc}")

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _selected_record(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        start = (self.current_page - 1) * self.items_per_page
        idx   = start + row
        if 0 <= idx < len(self.filtered_records):
            return self.filtered_records[idx]
        return None

    def _invalidate_and_reload(self) -> None:
        self._cache.clear()
        self._last_sig = None
        self._refresh_discreet(force=True)

    def _on_create(self) -> None:
        dlg = _RecordDialog(mode="create", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.payload()
        p["created_at"] = datetime.now().isoformat()
        p["updated_at"] = datetime.now().isoformat()
        p["id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
        cols = [k for k, v in p.items() if v is not None]
        vals = [p[k] for k in cols]
        try:
            db.execute_insert(
                f"INSERT INTO {self.TABLE} ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})",
                tuple(vals),
            )
            self._invalidate_and_reload()
        except Exception as exc:
            QMessageBox.critical(self, "CRUD", f"Échec création : {exc}")

    def _on_update(self) -> None:
        rec = self._selected_record()
        if not rec:
            QMessageBox.information(self, "CRUD", "Sélectionnez une ligne à modifier.")
            return
        dlg = _RecordDialog(initial=rec, mode="update", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.payload()
        p["updated_at"] = datetime.now().isoformat()
        parts = [f"{k} = ?" for k in p if k != "id"]
        vals  = [p[k] for k in p if k != "id"]
        vals.append(rec.get("id"))
        try:
            db.execute_update(
                f"UPDATE {self.TABLE} SET {', '.join(parts)} WHERE id = ?",
                tuple(vals),
            )
            self._invalidate_and_reload()
        except Exception as exc:
            QMessageBox.critical(self, "CRUD", f"Échec modification : {exc}")

    def _on_delete(self) -> None:
        rec = self._selected_record()
        if not rec:
            QMessageBox.information(self, "CRUD", "Sélectionnez une ligne à supprimer.")
            return
        rid = rec.get("id")
        if QMessageBox.question(
            self, "Confirmer", f"Supprimer la demande ID {rid} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            db.execute_update(f"DELETE FROM {self.TABLE} WHERE id = ?", (rid,))
            self._invalidate_and_reload()
        except Exception as exc:
            QMessageBox.critical(self, "CRUD", f"Échec suppression : {exc}")

    # ── État visuel ───────────────────────────────────────────────────────────

    def _set_state(self, text: str, color: str) -> None:
        self._refresh_lbl.setText(text)
        self._refresh_lbl.setStyleSheet(f"color:{color}; font-weight:600; background:transparent;")

    # ── Fermeture propre ──────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        for attr in ("_auto_timer",):
            t = getattr(self, attr, None)
            if t and t.isActive():
                t.stop()
        thread = self._reload_thread
        if thread:
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(1500)
            except RuntimeError:
                pass
        super().closeEvent(event)
