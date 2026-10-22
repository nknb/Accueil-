"""Wrapper for PreAccueil widget using Show_Data UI structure."""

from datetime import datetime
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QMainWindow,
    QWidget,
    QMessageBox,
    QHeaderView,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QObject, QThread, QRect, QRectF, pyqtSignal

from config import AppConfig
from .Show_Data import Ui_MainWindow
from database.connection import db
from database.models import DemandeAccueil
from utils import app_logger


# ── Rôle custom pour le délégué ───────────────────────────────────────────────
_ROLE_PA_IS_TRAITE = Qt.ItemDataRole.UserRole + 20


# ── Délégué de rendu — même design que la page Accueil ───────────────────────

class _PreAccueilRowDelegate(QStyledItemDelegate):
    """Rendu identique à AccueilPage : fond coloré, barre, badge statut."""

    _STATUS_COL = 7   # colonne Statut

    _TRAITE_BG  = QColor("#ecfdf5")
    _TRAITE_BAR = QColor("#22c55e")
    _TRAITE_FG  = QColor("#166534")

    _NON_BG     = QColor("#fff1f2")
    _NON_BAR    = QColor("#ef4444")
    _NON_FG     = QColor("#991b1b")

    _BAR_W    = 5
    _SEL_OVRL = QColor(99, 102, 241, 40)
    _DIVIDER  = QColor(0, 0, 0, 12)

    _AL = Qt.AlignmentFlag.AlignLeft    | Qt.AlignmentFlag.AlignVCenter
    _AC = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

    # Typographie par colonne : (bold, italic, align, fixed_color, size_delta)
    _COL_CFG = {
        0: (True,  False, _AL, None,              0),   # Nom — gras, couleur statut
        1: (False, False, _AL, QColor("#374151"), 0),   # Prénom
        2: (False, False, _AL, QColor("#6b7280"), -1),  # N° CNPS — muted
        3: (True,  False, _AL, QColor("#1e3a5f"), 0),   # Service — navy gras
        4: (False, True,  _AL, QColor("#4b5563"), 0),   # Motif — italic
        5: (False, False, _AL, QColor("#6b7280"), -1),  # Contact — muted
        6: (True,  False, _AC, QColor("#1e293b"), 0),   # H. arrivée — centré gras
        # 7 : Statut → badge pill
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_size: int = 8

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        row = index.row()
        col = index.column()
        model = index.model()

        is_traite = bool(model.index(row, 0).data(_ROLE_PA_IS_TRAITE))

        bg  = self._TRAITE_BG  if is_traite else self._NON_BG
        bar = self._TRAITE_BAR if is_traite else self._NON_BAR
        fg  = self._TRAITE_FG  if is_traite else self._NON_FG

        if row % 2 == 0:
            bg = bg.darker(103)

        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(rect, bg)

        if col == 0:
            painter.fillRect(QRect(rect.left(), rect.top(), self._BAR_W, rect.height()), bar)

        painter.setPen(QPen(self._DIVIDER, 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        if selected:
            painter.fillRect(rect, self._SEL_OVRL)

        painter.restore()

        raw_text = index.data(Qt.ItemDataRole.DisplayRole)
        if not raw_text:
            return
        text = str(raw_text)

        # Statut → badge pill
        if col == self._STATUS_COL:
            char_w  = max(6, self.font_size - 1)
            badge_w = max(len(text) * char_w + 16, 80)
            badge_h = min(rect.height() - 6, max(14, self.font_size + 6))
            badge_x = rect.left() + (rect.width() - badge_w) // 2
            badge_y = rect.top() + (rect.height() - badge_h) // 2
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(bar))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(badge_rect, badge_h / 2, badge_h / 2)
            font = QFont("", max(6, self.font_size - 1))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor("white")))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
            return

        # Typographie par colonne
        cfg = self._COL_CFG.get(col)
        if cfg is None:
            return

        bold, italic, align, fixed_color, size_delta = cfg
        pt = max(6, self.font_size + int(size_delta))
        font = QFont("", pt)
        font.setBold(bold)
        font.setItalic(italic)
        color = fixed_color if fixed_color is not None else fg

        left_pad = self._BAR_W + 5 if col == 0 else 6
        text_rect = rect.adjusted(left_pad, 0, -4, 0)

        painter.save()
        painter.setFont(font)
        painter.setPen(QPen(color))
        painter.drawText(text_rect, align | Qt.TextFlag.TextSingleLine, text)
        painter.restore()


class PreAccueilPage(QMainWindow):
    """PreAccueil page using the Show_Data UI structure with custom logic."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._refresh_in_progress = False
        self._refresh_pending = False
        self._refresh_context = {"silent": False}
        self._reload_thread = None
        self._reload_worker = None
        self._cache_ttl_sec = AppConfig.PREACCUEIL_CACHE_TTL_SEC
        self._demandes_cache = {}
        self._last_table_signature = None
        self._clock_timer = None
        self._auto_refresh_timer = None

        # ── Pagination ──────────────────────────────────────────────────
        self._all_pa_results: list = []
        self._pa_page: int = 0
        self._pa_page_size: int = 25
        
        # Setup UI from Show_Data
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Customize for PreAccueil
        self.setWindowTitle("Enregistrement Pré-Accueil")
        self.ui.label_2.setText("  Pré-Accueil — Enregistrement des demandes")
        self._apply_global_style()
        
        # Hide entire widget containing buttons (not needed for preaccueil)
        self.ui.widget.hide()
        
        # Setup table columns for PreAccueil
        self.ui.tableWidget.setColumnCount(8)
        self.ui.tableWidget.setHorizontalHeaderLabels([
            "Nom", "Prénom", "N° CNPS", "Service", "Motif", "Contact", "Heure d'arrivée", "Statut"
        ])
        self._setup_modern_table()
        self._pa_build_pagination_bar()

        # Create form widget for input
        self.create_input_form()
        
        # Connect signals
        self.btn_enregistrer.clicked.connect(self.enregistrer_demande)
        self.btn_effacer.clicked.connect(self.effacer_formulaire)
        
        # Load initial data
        self.load_services()
        self.load_motifs()
        self.load_demandes()
        self._init_auto_refresh()
        
        app_logger.info("PreAccueilPage initialisée complètement")

    def _apply_global_style(self):
        """Applique un thème moderne navy/slate sur toute la page."""
        self.setStyleSheet("""
            /* ── Fenêtre principale ──────────────────────────────── */
            QMainWindow, #centralwidget {
                background: #f0f4f8;
            }

            /* ── Header groupBox (bandeau titre) ─────────────────── */
            #groupBox {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0f2744, stop:0.5 #1e3a5f, stop:1 #1a4a7a);
                border: none;
                border-radius: 0px;
            }
            #groupBox QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            #groupBox QPushButton {
                background: rgba(255,255,255,0.15);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 5px;
                padding: 5px 14px;
                font-weight: 600;
            }
            #groupBox QPushButton:hover { background: rgba(255,255,255,0.25); }

            /* ── Zone tableau groupBox_2 ─────────────────────────── */
            #groupBox_2 {
                background: #ffffff;
                border: none;
                border-top: 1px solid #e2e8f0;
            }
        """)

        # Style du tableau
        self.ui.tableWidget.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                gridline-color: transparent;
                selection-background-color: #dbeafe;
                selection-color: #1e3a5f;
                outline: none;
            }
            QTableWidget::item { padding: 6px 10px; border: none; }
            QTableWidget::item:selected { background: #dbeafe; color: #1e3a5f; }
            QHeaderView::section {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1e3a5f, stop:1 #163059);
                color: white;
                font-weight: 700;
                font-size: 11px;
                padding: 8px 10px;
                border: none;
                border-right: 1px solid #2a4f80;
                border-bottom: 2px solid #3b82f6;
            }
            QHeaderView::section:last { border-right: none; }
            QScrollBar:vertical {
                background: #f1f5f9; width: 7px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #94a3b8; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #64748b; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    def _init_auto_refresh(self):
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._on_auto_refresh_timeout)
        self._auto_refresh_timer.start(AppConfig.AUTO_REFRESH_INTERVAL_MS)

    def _on_auto_refresh_timeout(self):
        self.load_demandes(silent=True)

    def _set_refresh_state(self, text, color):
        if hasattr(self, "refresh_state_label") and self.refresh_state_label is not None:
            self.refresh_state_label.setText(text)
            self.refresh_state_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _build_cache_key(self, today_str):
        return f"{today_str}::preaccueil"

    def _get_cached_results(self, today_str):
        entry = self._demandes_cache.get(self._build_cache_key(today_str))
        if not entry:
            return None
        ts = entry.get("ts")
        data = entry.get("data")
        if not ts or data is None:
            return None
        if (datetime.now() - ts).total_seconds() > self._cache_ttl_sec:
            return None
        return data

    def _set_cached_results(self, today_str, results):
        self._demandes_cache[self._build_cache_key(today_str)] = {
            "ts": datetime.now(),
            "data": results,
        }

    def _finalize_refresh(self):
        self._refresh_in_progress = False
        if hasattr(self, "refresh_spinner") and self.refresh_spinner is not None:
            self.refresh_spinner.setVisible(False)

        if self._refresh_pending:
            self._refresh_pending = False
            ctx = dict(self._refresh_context)
            QTimer.singleShot(
                0,
                lambda: self.load_demandes(
                    preserve_ui_state=ctx.get("preserve_ui_state", True),
                    silent=ctx.get("silent", True),
                ),
            )

    def _start_reload_worker(self, today_str):
        self._reload_thread = QThread(self)
        self._reload_worker = PreAccueilDemandesWorker(today_str)
        self._reload_worker.moveToThread(self._reload_thread)
        self._reload_thread.started.connect(self._reload_worker.run)
        self._reload_worker.finished.connect(self._on_reload_finished)
        self._reload_worker.failed.connect(self._on_reload_failed)
        self._reload_worker.finished.connect(self._reload_thread.quit)
        self._reload_worker.failed.connect(self._reload_thread.quit)
        self._reload_thread.finished.connect(self._reload_worker.deleteLater)
        self._reload_thread.finished.connect(self._reload_thread.deleteLater)
        self._reload_thread.finished.connect(lambda: setattr(self, "_reload_worker", None))
        self._reload_thread.finished.connect(lambda: setattr(self, "_reload_thread", None))
        self._reload_thread.start()

    def _build_table_signature(self, results):
        return tuple(
            (
                row.get("nom"),
                row.get("prenom"),
                row.get("numero_cnps"),
                row.get("service"),
                row.get("motif"),
                row.get("contacts"),
                row.get("heure_arrivee"),
                row.get("statut"),
            )
            for row in results
        )

    def _apply_demandes_results(self, results, silent=False):
        current_signature = self._build_table_signature(results)
        if silent and current_signature == self._last_table_signature:
            self._set_refresh_state("• À jour", "#0a8f2e")
            return

        self._last_table_signature = current_signature

        # Normaliser et stocker tous les résultats pour la pagination
        self._all_pa_results = results
        self._pa_goto_page(0)
        self._set_refresh_state("• À jour", "#0a8f2e")
        app_logger.info(f"Demandes chargées: {len(results)}")

    # ── Pagination PreAccueil ─────────────────────────────────────────────────

    _PA_BAR_SS = (
        "QWidget#paPagBar { background:#f1f5f9; border-top:1px solid #e2e8f0; }"
        "QPushButton { background:#1e3a5f; color:white; border-radius:4px;"
        "  padding:3px 9px; font-weight:700; font-size:12px; min-width:28px; }"
        "QPushButton:hover { background:#2a4f80; }"
        "QPushButton:disabled { background:#cbd5e1; color:#94a3b8; }"
        "QComboBox { border:1px solid #d1d5db; border-radius:4px; padding:2px 6px;"
        "  font-size:11px; background:white; color:#1e3a5f; font-weight:600; }"
        "QLabel { font-size:11px; color:#374151; font-weight:600; background:transparent; }"
    )

    def _pa_build_pagination_bar(self):
        bar = QWidget()
        bar.setObjectName("paPagBar")
        bar.setFixedHeight(38)
        bar.setStyleSheet(self._PA_BAR_SS)

        hl = QHBoxLayout(bar)
        hl.setContentsMargins(12, 4, 12, 4)
        hl.setSpacing(6)

        hl.addWidget(QLabel("Lignes :"))
        self._pa_combo_pp = QComboBox()
        self._pa_combo_pp.setFixedWidth(58)
        for v in [10, 25, 50, 100]:
            self._pa_combo_pp.addItem(str(v), v)
        self._pa_combo_pp.setCurrentIndex(1)  # 25 par défaut
        self._pa_combo_pp.currentIndexChanged.connect(self._pa_on_pp_changed)
        hl.addWidget(self._pa_combo_pp)

        hl.addStretch()

        self._pa_btn_first = QPushButton("◀◀")
        self._pa_btn_prev  = QPushButton("◀")
        self._pa_lbl_info  = QLabel("Page 1 / 1 — 0 enreg.")
        self._pa_lbl_info.setMinimumWidth(180)
        self._pa_lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pa_btn_next  = QPushButton("▶")
        self._pa_btn_last  = QPushButton("▶▶")

        for btn in (self._pa_btn_first, self._pa_btn_prev,
                    self._pa_btn_next, self._pa_btn_last):
            btn.setFixedSize(30, 26)

        self._pa_btn_first.clicked.connect(lambda: self._pa_goto_page(0))
        self._pa_btn_prev.clicked.connect(self._pa_prev_page)
        self._pa_btn_next.clicked.connect(self._pa_next_page)
        self._pa_btn_last.clicked.connect(
            lambda: self._pa_goto_page(self._pa_total_pages() - 1)
        )

        for w in (self._pa_btn_first, self._pa_btn_prev, self._pa_lbl_info,
                  self._pa_btn_next, self._pa_btn_last):
            hl.addWidget(w)

        self.ui.groupBox_2.layout().addWidget(bar, 1, 0)

    def _pa_total_pages(self) -> int:
        n = len(self._all_pa_results)
        return max(1, (n + self._pa_page_size - 1) // self._pa_page_size)

    def _pa_goto_page(self, page: int):
        total = self._pa_total_pages()
        self._pa_page = max(0, min(page, total - 1))
        self._pa_render_page()
        self._pa_update_nav()

    def _pa_prev_page(self):
        self._pa_goto_page(self._pa_page - 1)

    def _pa_next_page(self):
        self._pa_goto_page(self._pa_page + 1)

    def _pa_on_pp_changed(self):
        self._pa_page_size = self._pa_combo_pp.currentData()
        self._pa_goto_page(0)

    def _pa_update_nav(self):
        total = self._pa_total_pages()
        n = len(self._all_pa_results)
        start = self._pa_page * self._pa_page_size + 1
        end   = min((self._pa_page + 1) * self._pa_page_size, n)
        self._pa_lbl_info.setText(
            f"Page {self._pa_page + 1} / {total}  —  {n} enreg. ({start}-{end})"
        )
        self._pa_btn_first.setEnabled(self._pa_page > 0)
        self._pa_btn_prev.setEnabled(self._pa_page > 0)
        self._pa_btn_next.setEnabled(self._pa_page < total - 1)
        self._pa_btn_last.setEnabled(self._pa_page < total - 1)

    def _pa_render_page(self):
        start = self._pa_page * self._pa_page_size
        page_results = self._all_pa_results[start: start + self._pa_page_size]

        table = self.ui.tableWidget
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(0)
            for row_idx, demande in enumerate(page_results):
                table.insertRow(row_idx)

                nom    = (demande.get('nom') or "—").upper()
                prenom = (demande.get('prenom') or "—").title()
                cnps   = (demande.get('numero_cnps') or "—").upper()
                service = demande.get('service') or "—"
                motif   = demande.get('motif') or "—"
                contact = demande.get('contacts') or "—"
                heure   = demande.get('heure_arrivee')
                statut  = demande.get('statut') or "en_attente"

                if isinstance(heure, str):
                    heure = heure.split('T')[1][:8] if 'T' in heure else heure[:8]

                s = str(statut).strip().lower()
                statut_display = (
                    "En attente" if s == "en_attente" else
                    "Traité"     if s in ("traite", "traité") else
                    "En cours"   if s == "en_cours" else statut
                )
                is_traite = s in ("traite", "traité")

                for col_idx, text in enumerate([
                    nom, prenom, cnps, service, motif,
                    contact, heure or "—", statut_display,
                ]):
                    cell = QTableWidgetItem(str(text))
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col_idx == 0:
                        cell.setData(_ROLE_PA_IS_TRAITE, is_traite)
                    table.setItem(row_idx, col_idx, cell)
        finally:
            table.setUpdatesEnabled(True)

    def _on_reload_finished(self, results):
        try:
            today_str = datetime.now().date().isoformat()
            self._set_cached_results(today_str, results)
            self._apply_demandes_results(results, silent=self._refresh_context.get("silent", False))
        finally:
            self._finalize_refresh()

    def _on_reload_failed(self, error_message):
        self._set_refresh_state("• Erreur sync", "#c62828")
        app_logger.error(f"Erreur lors du chargement async des demandes: {error_message}")
        self._finalize_refresh()

    # ── Proportions des 8 colonnes (somme = 1.0) ─────────────────────────────
    # Nom, Prénom, N°CNPS, Service, Motif, Contact, H.arrivée, Statut
    _COL_PROPORTIONS = [0.13, 0.13, 0.10, 0.16, 0.16, 0.11, 0.10, 0.11]

    def _setup_modern_table(self):
        """Table navy responsive — toutes les colonnes visibles à l'écran."""
        table = self.ui.tableWidget
        header = table.horizontalHeader()

        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setStretchLastSection(False)

        table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                outline: none;
                gridline-color: transparent;
                selection-background-color: #dbeafe;
                selection-color: #1e3a5f;
            }
            QTableWidget::item { padding: 0px 8px; border: none; }
            QTableWidget::item:selected { background: #dbeafe; color: #1e3a5f; }
            QHeaderView { background: #1e3a5f; border: none; }
            QHeaderView::section {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1e3a5f, stop:1 #163059);
                color: white;
                font-weight: 700;
                padding: 7px 8px;
                border: none;
                border-right: 1px solid #2a4f80;
                border-bottom: 2px solid #3b82f6;
            }
            QHeaderView::section:last { border-right: none; }
            QScrollBar:vertical {
                background: #f1f5f9; width: 6px; border-radius: 3px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        hf = QFont("", 8)
        hf.setBold(True)
        header.setFont(hf)

        table.setItemDelegate(_PreAccueilRowDelegate(table))

        QTimer.singleShot(0, self._fit_table)

    # ── Responsive ────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_table)

    def _fit_table(self):
        """Redistribue les largeurs de colonnes proportionnellement au viewport."""
        if not hasattr(self, "ui") or self.ui.tableWidget is None:
            return
        table = self.ui.tableWidget
        vp_w = table.viewport().width()
        if vp_w <= 0:
            return

        header = table.horizontalHeader()

        # Police adaptée à la largeur
        if vp_w >= 1200:
            hdr_size, row_h = 8, 32
        elif vp_w >= 900:
            hdr_size, row_h = 7, 30
        else:
            hdr_size, row_h = 6, 27

        hf = QFont("", hdr_size)
        hf.setBold(True)
        header.setFont(hf)
        table.verticalHeader().setDefaultSectionSize(row_h)

        delegate = table.itemDelegate()
        if isinstance(delegate, _PreAccueilRowDelegate):
            delegate.font_size = hdr_size + 1

        for col_idx, prop in enumerate(self._COL_PROPORTIONS):
            w = max(45, int(vp_w * prop))
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col_idx, w)

        table.viewport().update()

    # ── Styles du formulaire ──────────────────────────────────────────────────
    _FORM_SS = """
        QWidget#preaccueilFormCard {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
        }
        /* ── En-tête du formulaire ── */
        #paFormHeader {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0f2744, stop:0.6 #1e3a5f, stop:1 #1a4a7a);
            border-radius: 12px 12px 0 0;
        }
        #paFormHeaderTitle {
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
        }
        #paFormHeaderSync {
            color: #bfdbfe;
            font-size: 11px;
            font-weight: 600;
        }
        /* ── Labels champ ── */
        #paFieldLabel {
            color: #64748b;
            font-size: 10px;
            font-weight: 600;
        }
        /* ── Champ heure ── */
        #paHeureBadge {
            color: #1e3a5f;
            font-size: 22px;
            font-weight: 700;
            background: #eff6ff;
            border: 2px solid #bfdbfe;
            border-radius: 10px;
            padding: 2px 8px;
        }
        #paDateLabel {
            color: #64748b;
            font-size: 10px;
            font-weight: 600;
        }
        /* ── Inputs ── */
        QLineEdit, QComboBox {
            border: 1px solid #e2e8f0;
            border-radius: 7px;
            padding: 7px 10px;
            background: #f8fafc;
            color: #1e293b;
            font-size: 12px;
        }
        QLineEdit:focus, QComboBox:focus {
            border: 1px solid #3b82f6;
            background: #f0f7ff;
        }
        QLineEdit[readOnly="true"] {
            background: transparent;
            border: none;
            color: #1e3a5f;
        }
        /* ── Séparateur ── */
        #paSeparator {
            background: #e2e8f0;
        }
        /* ── Boutons ── */
        #paBtn_save {
            background: #1e3a5f;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 28px;
            font-size: 12px;
            font-weight: 700;
        }
        #paBtn_save:hover  { background: #163059; }
        #paBtn_save:pressed{ background: #0f2744; }
        #paBtn_clear {
            background: transparent;
            color: #64748b;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 12px;
            font-weight: 600;
        }
        #paBtn_clear:hover { background: #f1f5f9; color: #374151; }
    """

    def create_input_form(self):
        """Formulaire d'enregistrement — design navy card, labels au-dessus."""
        card = QWidget()
        card.setObjectName("preaccueilFormCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card_vl = QVBoxLayout(card)
        card_vl.setContentsMargins(0, 0, 0, 0)
        card_vl.setSpacing(0)

        # ── En-tête du formulaire ─────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("paFormHeader")
        header.setFixedHeight(48)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)

        title_lbl = QLabel("Nouvelle demande d'accueil")
        title_lbl.setObjectName("paFormHeaderTitle")
        hl.addWidget(title_lbl)
        hl.addStretch()

        self.refresh_state_label = QLabel("• À jour")
        self.refresh_state_label.setObjectName("paFormHeaderSync")
        self.refresh_spinner = QLabel("⟳")
        self.refresh_spinner.setObjectName("paFormHeaderSync")
        self.refresh_spinner.setVisible(False)
        hl.addWidget(self.refresh_spinner)
        hl.addWidget(self.refresh_state_label)

        card_vl.addWidget(header)

        # ── Corps du formulaire ───────────────────────────────────────────────
        body = QWidget()
        body_vl = QVBoxLayout(body)
        body_vl.setContentsMargins(16, 14, 16, 14)
        body_vl.setSpacing(12)
        card_vl.addWidget(body)

        # Helper : mini-colonne label + input
        def field(label_text, widget):
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setObjectName("paFieldLabel")
            col.addWidget(lbl)
            col.addWidget(widget)
            return col

        def inp(placeholder="", min_h=36):
            w = QLineEdit()
            w.setPlaceholderText(placeholder)
            w.setMinimumHeight(min_h)
            return w

        def combo(min_h=36):
            w = QComboBox()
            w.setMinimumHeight(min_h)
            return w

        # ── Ligne 1 : Nom · Prénom · N° CNPS ────────────────────────────────
        self.input_nom    = inp("ex : COULIBALY")
        self.input_prenom = inp("ex : Aminata")
        self.input_cnps   = inp("ex : 202300012345 (optionnel)")

        # Normalisation automatique à la sortie du champ
        self.input_nom.editingFinished.connect(
            lambda: self.input_nom.setText(self.input_nom.text().strip().upper())
        )
        self.input_prenom.editingFinished.connect(
            lambda: self.input_prenom.setText(self.input_prenom.text().strip().title())
        )
        self.input_cnps.editingFinished.connect(
            lambda: self.input_cnps.setText(self.input_cnps.text().strip().upper())
        )

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row1.addLayout(field("Nom *", self.input_nom))
        row1.addLayout(field("Prénom *", self.input_prenom))
        row1.addLayout(field("N° CNPS", self.input_cnps))
        body_vl.addLayout(row1)

        # ── Ligne 2 : Service · Motif ────────────────────────────────────────
        self.combo_service = combo()
        self.combo_service.addItem("— Sélectionner un service —")
        self.combo_motif = combo()
        self.combo_motif.addItem("— Sélectionner un motif —")

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        row2.addLayout(field("Service demandé *", self.combo_service))
        row2.addLayout(field("Motif *", self.combo_motif))
        body_vl.addLayout(row2)

        # ── Ligne 3 : Contact · Heure d'arrivée ─────────────────────────────
        self.input_contact = inp("Téléphone ou email (optionnel)")

        # Heure : badge horloge précis (heure + date)
        heure_container = QWidget()
        heure_container.setObjectName("paHeureContainer")
        heure_vl = QVBoxLayout(heure_container)
        heure_vl.setContentsMargins(0, 0, 0, 0)
        heure_vl.setSpacing(2)

        self.label_heure_arrivee = QLineEdit()
        self.label_heure_arrivee.setObjectName("paHeureBadge")
        self.label_heure_arrivee.setReadOnly(True)
        self.label_heure_arrivee.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_heure_arrivee.setMinimumHeight(48)
        self.label_heure_arrivee.setFixedWidth(160)

        self._date_label = QLabel(datetime.now().strftime("%d/%m/%Y"))
        self._date_label.setObjectName("paDateLabel")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heure_vl.addWidget(self.label_heure_arrivee)
        heure_vl.addWidget(self._date_label)

        heure_col = QVBoxLayout()
        heure_col.setSpacing(4)
        lbl_h = QLabel("Heure d'arrivée  ⚡ enregistrée au clic")
        lbl_h.setObjectName("paFieldLabel")
        heure_col.addWidget(lbl_h)
        heure_col.addWidget(heure_container)

        row3 = QHBoxLayout()
        row3.setSpacing(12)
        row3.addLayout(field("Contact", self.input_contact))
        row3.addLayout(heure_col)
        body_vl.addLayout(row3)

        # ── Séparateur ───────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("paSeparator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        body_vl.addWidget(sep)

        # ── Boutons ──────────────────────────────────────────────────────────
        self.btn_enregistrer = QPushButton("✔  Enregistrer la demande")
        self.btn_enregistrer.setObjectName("paBtn_save")
        self.btn_enregistrer.setMinimumHeight(40)
        self.btn_enregistrer.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_effacer = QPushButton("Effacer")
        self.btn_effacer.setObjectName("paBtn_clear")
        self.btn_effacer.setMinimumHeight(40)
        self.btn_effacer.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_effacer)
        btn_row.addWidget(self.btn_enregistrer)
        body_vl.addLayout(btn_row)

        # ── Insertion dans le layout parent ──────────────────────────────────
        card.setStyleSheet(self._FORM_SS)
        parent_layout = self.ui.centralwidget.layout()
        parent_layout.insertWidget(2, card)

        # ── Horloge ──────────────────────────────────────────────────────────
        self.update_heure_arrivee()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.update_heure_arrivee)
        self._clock_timer.start(AppConfig.PREACCUEIL_CLOCK_INTERVAL_MS)

    def load_services(self):
        """Load services from database."""
        try:
            query = "SELECT id, nom FROM accueil_service ORDER BY nom"
            results = db.execute_query(query)
            
            self.combo_service.clear()
            self.combo_service.addItem("-- Sélectionner un service --", None)
            
            if results:
                for service in results:
                    service_id = service.get('id')
                    service_nom = service.get('nom')
                    self.combo_service.addItem(service_nom, service_id)
                app_logger.info(f"Services chargés: {len(results)}")
            else:
                app_logger.warning("Aucun service trouvé en base de données")
        except Exception as e:
            app_logger.error(f"Erreur lors du chargement des services: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors du chargement des services: {e}")

    def load_motifs(self):
        """Load motifs from database."""
        try:
            query = "SELECT id, nom FROM accueil_motif ORDER BY nom"
            results = db.execute_query(query)
            
            self.combo_motif.clear()
            self.combo_motif.addItem("-- Sélectionner un motif --", None)
            
            if results:
                for motif in results:
                    motif_id = motif.get('id')
                    motif_nom = motif.get('nom')
                    self.combo_motif.addItem(motif_nom, motif_id)
                app_logger.info(f"Motifs chargés: {len(results)}")
            else:
                app_logger.warning("Aucun motif trouvé en base de données")
        except Exception as e:
            app_logger.error(f"Erreur lors du chargement des motifs: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors du chargement des motifs: {e}")

    def update_heure_arrivee(self):
        """Met à jour le badge heure d'arrivée à la seconde près."""
        now = datetime.now()
        # Ligne principale : heure précise
        self.label_heure_arrivee.setText(now.strftime("%H:%M:%S"))

    def enregistrer_demande(self):
        """Save demand to database."""
        # Validation
        nom = self.input_nom.text().strip().upper()
        prenom = self.input_prenom.text().strip().title()
        service_idx = self.combo_service.currentIndex()
        motif_idx = self.combo_motif.currentIndex()
        
        if not nom:
            QMessageBox.warning(self, "Erreur Validation", "Le nom est obligatoire")
            self.input_nom.setFocus()
            return
        
        if not prenom:
            QMessageBox.warning(self, "Erreur Validation", "Le prénom est obligatoire")
            self.input_prenom.setFocus()
            return
        
        if service_idx == 0:
            QMessageBox.warning(self, "Erreur Validation", "Veuillez sélectionner un service")
            self.combo_service.setFocus()
            return
        
        if motif_idx == 0:
            QMessageBox.warning(self, "Erreur Validation", "Veuillez sélectionner un motif")
            self.combo_motif.setFocus()
            return
        
        try:
            service_id = self.combo_service.itemData(service_idx)
            motif_id = self.combo_motif.itemData(motif_idx)
            cnps = self.input_cnps.text().strip() or None
            contact = self.input_contact.text().strip() or None

            # Heure capturée au moment précis du clic — une seule fois
            heure_arrivee = datetime.now()

            # Create new demand
            demande = DemandeAccueil(
                date=heure_arrivee.date(),
                nom=nom,
                prenom=prenom,
                numero_cnps=cnps,
                service_demande_id=service_id,
                motif_id=motif_id,
                contacts=contact,
                heure_arrivee=heure_arrivee,
                statut='en_attente',
                priorite='normale'
            )

            # Save to database
            if demande.save():
                h_str = heure_arrivee.strftime("%H:%M:%S")
                QMessageBox.information(
                    self, "Enregistrement confirmé",
                    f"✅  Demande enregistrée\n\n"
                    f"👤  {nom.upper()} {prenom}\n"
                    f"⏰  Heure d'arrivée : {h_str}"
                )
                self.effacer_formulaire()
                self._demandes_cache.clear()
                self.load_demandes()
                app_logger.info(f"Demande enregistrée: {demande.id} à {h_str}")
            else:
                QMessageBox.warning(self, "Erreur", "❌ Erreur lors de l'enregistrement de la demande")
                app_logger.error("Erreur lors de la sauvegarde de la demande")
        
        except Exception as e:
            app_logger.error(f"Erreur lors de l'enregistrement: {e}")
            QMessageBox.critical(self, "Erreur", f"❌ Erreur: {str(e)}")

    def effacer_formulaire(self):
        """Clear the form."""
        self.input_nom.clear()
        self.input_prenom.clear()
        self.input_cnps.clear()
        self.input_contact.clear()
        self.combo_service.setCurrentIndex(0)
        self.combo_motif.setCurrentIndex(0)
        self.input_nom.setFocus()
        app_logger.info("Formulaire réinitialisé")

    def load_demandes(self, preserve_ui_state=False, silent=False):
        """Load and display today's demands in the table."""
        if self._refresh_in_progress:
            self._refresh_pending = True
            self._refresh_context = {
                "preserve_ui_state": preserve_ui_state,
                "silent": silent,
            }
            self._set_refresh_state("• Sync en attente...", "#ef6c00")
            return

        self._refresh_in_progress = True
        self._refresh_context = {
            "preserve_ui_state": preserve_ui_state,
            "silent": silent,
        }
        if hasattr(self, "refresh_spinner") and self.refresh_spinner is not None:
            self.refresh_spinner.setVisible(True)
        self._set_refresh_state("• Synchronisation...", "#1e88e5")

        try:
            today_str = datetime.now().date().isoformat()
            cached_results = self._get_cached_results(today_str)
            if cached_results is not None:
                self._apply_demandes_results(cached_results, silent=silent)
                self._finalize_refresh()
                return

            self._start_reload_worker(today_str)
        except Exception as e:
            app_logger.error(f"Erreur lors du chargement des demandes: {e}")
            self._set_refresh_state("• Erreur sync", "#c62828")
            self._finalize_refresh()

    def closeEvent(self, event):
        timer = getattr(self, "_clock_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

        auto_refresh_timer = getattr(self, "_auto_refresh_timer", None)
        if auto_refresh_timer is not None and auto_refresh_timer.isActive():
            auto_refresh_timer.stop()

        thread = getattr(self, "_reload_thread", None)
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1500)

        super().closeEvent(event)


class PreAccueilDemandesWorker(QObject):
    """Worker Qt pour charger les demandes du jour hors thread UI."""

    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, today_str):
        super().__init__()
        self.today_str = today_str

    def run(self):
        query = """
        SELECT
            d.nom, d.prenom, d.numero_cnps, s.nom as service, m.nom as motif,
            d.contacts, d.heure_arrivee, d.statut
        FROM accueil_demandeaccueil d
        LEFT JOIN accueil_service s ON d.service_demande_id = s.id
        LEFT JOIN accueil_motif m ON d.motif_id = m.id
        WHERE DATE(d.date) = ?
        ORDER BY d.created_at DESC
        """
        try:
            results = db.execute_query(query, (self.today_str,))
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))
