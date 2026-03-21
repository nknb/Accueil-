"""Dashboard page — graphiques modernes adaptés pour le projet Accueil."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QMargins, QPropertyAnimation, QEasingCurve, QTimer, QDate
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QPieSeries,
    QValueAxis,
)
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QGridLayout,
    QLabel,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QGraphicsOpacityEffect,
    QPushButton,
    QDateEdit,
    QScrollArea,
    QApplication,
)

from database.connection import db
from ui.dashboard_theme import (
    _BG_DEEP, _BG_CARD, _BG_HDR, _BORDER,
    _TXT1, _TXT2, _TXT3, _GRID,
    _C_NAVY, _C_GREEN, _C_AMBER, _C_BLUE,
    DATE_EDIT_QSS as _DATE_EDIT_QSS, BTN_QSS as _BTN_QSS,
    truncate as _truncate,
)


# ── Worker QThread ─────────────────────────────────────────────────────────────

class _DashboardWorker(QObject):
    """Charge toutes les données du dashboard dans un thread séparé.

    Signaux :
        finished(dict) — données prêtes (jamais depuis l'UI thread)
        failed(str)    — message d'erreur si la requête échoue
    """

    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, date_from: str, date_to: str) -> None:
        super().__init__()
        self._date_from = date_from
        self._date_to   = date_to

    def run(self) -> None:
        """Exécute toutes les requêtes SQL hors thread UI."""
        try:
            and_cond = "AND date(COALESCE(d.updated_at, d.created_at, d.date)) BETWEEN ? AND ?"
            params   = (self._date_from, self._date_to)

            total_demandes = 0
            total_traite   = 0
            total_attente  = 0
            total_non_traite = 0
            services_names: list[str] = []
            services_counts: list[int] = []
            motifs_names: list[str] = []
            motifs_counts: list[int] = []
            priorites_names: list[str] = []
            priorites_counts: list[int] = []

            # Statuts
            for row in db.execute_query(
                f"SELECT statut, COUNT(*) AS nb FROM accueil_demandeaccueil d WHERE 1=1 {and_cond} GROUP BY statut",
                params,
            ):
                st = str(row.get("statut") or "").strip().lower()
                nb = int(row.get("nb") or 0)
                total_demandes += nb
                if st == "traite":
                    total_traite += nb
                elif st == "en_attente":
                    total_attente += nb
                else:
                    total_non_traite += nb

            # Par service
            for row in db.execute_query(
                f"""SELECT COALESCE(s.nom, 'Non renseigné') AS service, COUNT(*) AS nb
                    FROM accueil_demandeaccueil d
                    LEFT JOIN accueil_service s ON d.service_demande_id = s.id
                    WHERE 1=1 {and_cond}
                    GROUP BY COALESCE(s.nom, 'Non renseigné') ORDER BY nb DESC LIMIT 8""",
                params,
            ):
                services_names.append(str(row.get("service") or ""))
                services_counts.append(int(row.get("nb") or 0))

            # Par motif
            for row in db.execute_query(
                f"""SELECT COALESCE(m.nom, 'Non renseigné') AS motif, COUNT(*) AS nb
                    FROM accueil_demandeaccueil d
                    LEFT JOIN accueil_motif m ON d.motif_id = m.id
                    WHERE 1=1 {and_cond}
                    GROUP BY COALESCE(m.nom, 'Non renseigné') ORDER BY nb DESC LIMIT 8""",
                params,
            ):
                motifs_names.append(str(row.get("motif") or ""))
                motifs_counts.append(int(row.get("nb") or 0))

            # Par priorité
            for row in db.execute_query(
                f"""SELECT COALESCE(priorite, 'normale') AS priorite, COUNT(*) AS nb
                    FROM accueil_demandeaccueil d
                    WHERE 1=1 {and_cond}
                    GROUP BY COALESCE(priorite, 'normale') ORDER BY nb DESC""",
                params,
            ):
                priorites_names.append(str(row.get("priorite") or ""))
                priorites_counts.append(int(row.get("nb") or 0))

            self.finished.emit({
                "total_demandes":   total_demandes,
                "total_traite":     total_traite,
                "total_attente":    total_attente,
                "total_non_traite": total_non_traite,
                "services_names":   services_names,
                "services_counts":  services_counts,
                "motifs_names":     motifs_names,
                "motifs_counts":    motifs_counts,
                "priorites_names":  priorites_names,
                "priorites_counts": priorites_counts,
            })

        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(exc))


# ── Gestionnaire de graphiques ────────────────────────────────────────────────

class _ChartHandler:
    """Construit et rafraîchit les graphiques du Dashboard Accueil."""

    def __init__(self, layout: QGridLayout) -> None:
        self._layout = layout
        self._responsive_label_specs: list[tuple[QLabel, int]] = []
        self._animations: list[QPropertyAnimation] = []

        _y = QDate.currentDate().year()
        self._filter_date_from: str = f"{_y}-01-01"
        self._filter_date_to: str   = f"{_y}-12-31"

        self._loading_label: QLabel | None = None
        self._worker: _DashboardWorker | None = None
        self._thread: QThread | None = None

    def refresh(self) -> None:
        """Lance le chargement asynchrone puis construit les graphiques."""
        self._animations.clear()
        self._show_loading()
        self._start_worker()

    # ── Chargement asynchrone ─────────────────────────────────────────────────

    def _show_loading(self) -> None:
        """Affiche un indicateur de chargement pendant la requête."""
        layout = self._layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._loading_label = QLabel("Chargement des données…")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(
            f"color: {_TXT2}; font-size: 14px; background: transparent;"
        )
        layout.addWidget(self._loading_label, 0, 0, 1, 4)

    def _is_thread_running(self) -> bool:
        """Vérifie si le thread précédent tourne encore (sans crasher sur objet C++ supprimé)."""
        if self._thread is None:
            return False
        try:
            return self._thread.isRunning()
        except RuntimeError:
            # L'objet C++ sous-jacent a déjà été supprimé par deleteLater
            self._thread = None
            return False

    def _on_thread_finished(self) -> None:
        """Nullifie la référence Python AVANT que deleteLater ne supprime l'objet C++."""
        thread = self._thread
        self._thread = None
        if thread is not None:
            try:
                thread.deleteLater()
            except RuntimeError:
                pass

    def _start_worker(self) -> None:
        """Démarre le worker dans un QThread dédié."""
        # Nettoyage du thread précédent si encore actif
        if self._is_thread_running():
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None

        thread = QThread()
        self._thread = thread
        self._worker = _DashboardWorker(self._filter_date_from, self._filter_date_to)
        self._worker.moveToThread(thread)

        thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.failed.connect(self._on_data_failed)
        self._worker.finished.connect(thread.quit)
        self._worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)

        thread.start()

    def _on_data_ready(self, data: dict) -> None:
        """Callback UI thread — reçoit les données et construit les graphiques."""
        self._build_charts(data)

    def _on_data_failed(self, error_msg: str) -> None:
        """Callback UI thread — affiche l'erreur dans le layout."""
        layout = self._layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        err_label = QLabel(f"Erreur de chargement :\n{error_msg}")
        err_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        err_label.setStyleSheet("color: #ef4444; font-size: 13px; background: transparent;")
        err_label.setWordWrap(True)
        layout.addWidget(err_label, 0, 0, 1, 4)

    # ── Filtres de dates ──────────────────────────────────────────────────────

    def _make_filter_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background-color: {_BG_HDR}; border-radius: 10px; border: 1px solid {_BORDER}; }}"
            f"QLabel {{ color: {_TXT2}; font-size: 11px; font-weight: 600;"
            f"  background: transparent; border: none; }}"
        )
        bar.setMinimumHeight(46)

        hbox = QHBoxLayout(bar)
        hbox.setContentsMargins(16, 8, 16, 8)
        hbox.setSpacing(10)

        icon = QLabel("\U0001f5d3")
        icon.setStyleSheet("font-size: 14px; border: none; background: transparent;")
        hbox.addWidget(icon)

        def _make_de(val: str) -> QDateEdit:
            de = QDateEdit()
            de.setCalendarPopup(True)
            de.setDisplayFormat("dd/MM/yyyy")
            de.setStyleSheet(_DATE_EDIT_QSS)
            de.setDate(QDate.fromString(val, "yyyy-MM-dd"))
            return de

        hbox.addWidget(QLabel("Du :"))
        self._de_from = _make_de(self._filter_date_from)
        self._de_from.dateChanged.connect(lambda d: self._on_date_changed("from", d))
        hbox.addWidget(self._de_from)

        hbox.addWidget(QLabel("  Au :"))
        self._de_to = _make_de(self._filter_date_to)
        self._de_to.dateChanged.connect(lambda d: self._on_date_changed("to", d))
        hbox.addWidget(self._de_to)

        hbox.addStretch(1)

        reset_btn = QPushButton("\u21ba  R\u00e9initialiser")
        reset_btn.setStyleSheet(_BTN_QSS)
        reset_btn.clicked.connect(self._on_filter_reset)
        hbox.addWidget(reset_btn)

        return bar

    def _on_date_changed(self, which: str, date: QDate) -> None:
        if which == "from":
            self._filter_date_from = date.toString("yyyy-MM-dd")
        else:
            self._filter_date_to = date.toString("yyyy-MM-dd")
        self.refresh()

    def _on_filter_reset(self) -> None:
        _y = QDate.currentDate().year()
        self._filter_date_from = f"{_y}-01-01"
        self._filter_date_to   = f"{_y}-12-31"
        self.refresh()

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _fade_in(self, widget, delay_ms: int = 0) -> None:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)

        def _start() -> None:
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(550)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            self._animations.append(anim)

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _start)
        else:
            _start()

    def _make_kpi_card(self, title: str, value: str, subtitle: str, accent: str, delay_ms: int = 0) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {_BG_CARD}; border-radius: 12px;"
            f" border: 1px solid {_BORDER}; border-top: 3px solid {accent}; }}"
        )
        frame.setMinimumHeight(110)
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(14, 10, 14, 10)
        vbox.setSpacing(4)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(
            f"color: {_TXT3}; font-weight: 600; letter-spacing: 0.7px; border: none; background: transparent;"
        )
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(
            f"color: {accent}; font-size: 20px; font-weight: 800; border: none; background: transparent;"
        )
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(f"color: {_TXT3}; border: none; background: transparent;")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_value)
        vbox.addWidget(lbl_sub)
        vbox.addStretch(1)

        self._responsive_label_specs.extend([(lbl_title, 9), (lbl_value, 18), (lbl_sub, 9)])
        self._fade_in(frame, delay_ms)
        return frame

    def _make_chart_card(self, title: str, subtitle: str, delay_ms: int = 0) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {_BG_CARD}; border-radius: 12px; border: 1px solid {_BORDER}; }}"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = QFrame()
        hdr.setStyleSheet(
            f"QFrame {{ background-color: {_BG_HDR}; border: none;"
            " border-radius: 12px; border-bottom-left-radius: 0; border-bottom-right-radius: 0;"
            f" border-bottom: 1px solid {_BORDER}; }}"
        )
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(18, 11, 18, 9)
        hdr_lay.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(
            f"color: {_TXT1}; font-weight: 700; font-size: 12px; border: none; background: transparent;"
        )
        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"color: {_TXT2}; font-size: 10px; border: none; background: transparent;")
        hdr_lay.addWidget(lbl_t)
        hdr_lay.addWidget(lbl_s)
        outer.addWidget(hdr)

        self._fade_in(card, delay_ms)
        return card, outer

    def _base_chart(self, bg: str = _BG_CARD) -> QChart:
        chart = QChart()
        chart.setTheme(QChart.ChartTheme.ChartThemeDark)
        chart.setTitle("")
        chart.setBackgroundBrush(QColor(bg))
        chart.setBackgroundRoundness(0)
        chart.setMargins(QMargins(10, 6, 10, 6))
        chart.setAnimationOptions(QChart.AnimationOption.AllAnimations)
        chart.setAnimationDuration(700)
        tf = chart.titleFont()
        tf.setPointSize(1)
        chart.setTitleFont(tf)
        return chart

    @staticmethod
    def _styled_view(chart: QChart, min_h: int = 220) -> QChartView:
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setStyleSheet("background: transparent; border: none;")
        view.setMinimumHeight(min_h)
        return view

    def _style_legend(self, chart: QChart) -> None:
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        lf = chart.legend().font()
        lf.setPointSize(9)
        chart.legend().setFont(lf)
        chart.legend().setColor(QColor(_TXT1))
        chart.legend().setLabelColor(QColor(_TXT2))

    def _style_axis(self, axis) -> None:
        lf = axis.labelsFont()
        lf.setPointSize(9)
        axis.setLabelsFont(lf)
        axis.setLabelsColor(QColor(_TXT2))
        if isinstance(axis, QValueAxis):
            axis.setGridLineColor(QColor(_GRID))

    # ── Construction principale ───────────────────────────────────────────────

    def add_chart(self) -> None:
        """Point d'entrée : lance le chargement async puis construit les graphiques."""
        self.refresh()

    def _build_charts(self, data: dict) -> None:
        """Construit tous les widgets graphiques à partir des données reçues du worker."""
        layout = self._layout
        self._responsive_label_specs = []
        self._animations.clear()

        # Vider le layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        parent = layout.parentWidget()
        if parent is not None:
            parent.setStyleSheet(f"background-color: {_BG_DEEP};")

        total_demandes   = data.get("total_demandes", 0)
        total_traite     = data.get("total_traite", 0)
        total_attente    = data.get("total_attente", 0)
        total_non_traite = data.get("total_non_traite", 0)
        services_names   = data.get("services_names", [])
        services_counts  = data.get("services_counts", [])
        motifs_names     = data.get("motifs_names", [])
        motifs_counts    = data.get("motifs_counts", [])
        priorites_names  = data.get("priorites_names", [])
        priorites_counts = data.get("priorites_counts", [])

        # ── Mise en page grille 4 colonnes ────────────────────────────────
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(14, 12, 14, 12)
        for col in range(4):
            layout.setColumnStretch(col, 1)

        # LIGNE 0 : Barre de filtres
        layout.addWidget(self._make_filter_bar(), 0, 0, 1, 4)

        # LIGNE 1 : 4 cartes KPI
        taux = int(total_traite / total_demandes * 100) if total_demandes > 0 else 0
        kpi_data = [
            ("Total demandes",    str(total_demandes),                     "Dans la p\u00e9riode",  _C_NAVY),
            ("Demand. trait\u00e9es", str(total_traite),                   "Statut trait\u00e9",     _C_GREEN),
            ("En attente",        str(total_attente + total_non_traite),   "Non trait\u00e9es",      _C_AMBER),
            ("Taux traitement",   f"{taux}\u00a0%",                        "Trait\u00e9es / total",  _C_BLUE),
        ]
        for col, (title, value, sub, accent) in enumerate(kpi_data):
            layout.addWidget(self._make_kpi_card(title, value, sub, accent, delay_ms=col * 80), 1, col)

        # LIGNE 2 : Camembert statut | Camembert priorité
        pie_card, pie_lay = self._make_chart_card(
            "Statut global des demandes", "Trait\u00e9es vs non trait\u00e9es", delay_ms=100,
        )
        pie_series = QPieSeries()
        s_t = pie_series.append(f"Trait\u00e9es  ({total_traite})", max(total_traite, 1))
        s_a = pie_series.append(f"En attente  ({total_attente + total_non_traite})", max(total_attente + total_non_traite, 1))
        s_t.setColor(QColor(_C_BLUE));  s_t.setBorderColor(QColor(_C_BLUE))
        s_a.setColor(QColor(_C_AMBER)); s_a.setBorderColor(QColor(_C_AMBER))
        s_t.setExploded(True); s_t.setExplodeDistanceFactor(0.05)
        pie_chart = self._base_chart()
        pie_chart.addSeries(pie_series)
        pie_chart.setMargins(QMargins(8, 4, 8, 4))
        self._style_legend(pie_chart)
        pie_lay.addWidget(self._styled_view(pie_chart, min_h=200))
        layout.addWidget(pie_card, 2, 0, 1, 2)

        prio_card, prio_lay = self._make_chart_card(
            "Demandes par priorit\u00e9", "R\u00e9partition selon la priorit\u00e9", delay_ms=180,
        )
        prio_series = QPieSeries()
        prio_colors = [_C_AMBER, _C_BLUE, _C_GREEN, _C_NAVY]
        if priorites_names:
            for i, (name, nb) in enumerate(zip(priorites_names, priorites_counts)):
                sl = prio_series.append(f"{name}  ({nb})", max(nb, 1))
                c = prio_colors[i % len(prio_colors)]
                sl.setColor(QColor(c)); sl.setBorderColor(QColor(c))
                if i == 0:
                    sl.setExploded(True); sl.setExplodeDistanceFactor(0.05)
        else:
            sl = prio_series.append("Aucune donn\u00e9e", 1)
            sl.setColor(QColor(_BORDER)); sl.setBorderColor(QColor(_BORDER))
        prio_chart = self._base_chart()
        prio_chart.addSeries(prio_series)
        prio_chart.setMargins(QMargins(8, 4, 8, 4))
        self._style_legend(prio_chart)
        prio_lay.addWidget(self._styled_view(prio_chart, min_h=200))
        layout.addWidget(prio_card, 2, 2, 1, 2)

        # LIGNE 3 : Barres horizontales par service (gauche) + par motif (droite)
        self._add_horiz_bar_card(
            layout, row=3, col_start=0, col_span=2,
            title="Demandes par service",
            subtitle="Volume de demandes enregistr\u00e9es par service",
            names=services_names, counts=services_counts,
            color=_C_NAVY, delay_ms=260,
        )
        self._add_horiz_bar_card(
            layout, row=3, col_start=2, col_span=2,
            title="Demandes par motif",
            subtitle="Volume de demandes enregistr\u00e9es par motif",
            names=motifs_names, counts=motifs_counts,
            color=_C_GREEN, delay_ms=320,
        )

    def _add_horiz_bar_card(
        self, layout: QGridLayout, row: int, col_start: int, col_span: int,
        title: str, subtitle: str, names: list[str], counts: list[int],
        color: str, delay_ms: int = 0,
    ) -> None:
        if not names:
            names = ["Aucune donn\u00e9e"]; counts = [0]

        card, card_lay = self._make_chart_card(title, subtitle, delay_ms=delay_ms)

        bar_set = QBarSet("Demandes")
        bar_set.setColor(QColor(color)); bar_set.setBorderColor(QColor(color))
        for n in counts:
            bar_set.append(n)

        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setBarWidth(0.55)
        series.setLabelsVisible(True)

        chart = self._base_chart()
        chart.addSeries(series)
        chart.setMargins(QMargins(8, 4, 24, 4))

        ax_y = QBarCategoryAxis()
        ax_y.append([_truncate(s, 24) for s in names])
        self._style_axis(ax_y)
        chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(ax_y)

        max_val = max(counts) if counts else 1
        ax_x = QValueAxis()
        ax_x.setRange(0, max_val * 1.3)
        ax_x.setLabelFormat("%d")
        ax_x.setTickCount(5)
        self._style_axis(ax_x)
        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(ax_x)
        chart.legend().setVisible(False)

        min_h = max(200, len(names) * 32 + 60)
        card_lay.addWidget(self._styled_view(chart, min_h=min_h))
        layout.addWidget(card, row, col_start, 1, col_span)


# ── Page Dashboard ────────────────────────────────────────────────────────────

class DashboardPage(QMainWindow):
    """Page Dashboard embarquant des graphiques modernes adaptés pour l'Accueil."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dashboard")

        # Widget central avec scroll
        central = QWidget()
        self.setCentralWidget(central)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_BG_DEEP}; border: none; }}"
            "QScrollBar:vertical { background: #1e293b; width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: #475569; border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setStyleSheet(f"background-color: {_BG_DEEP};")
        self._grid = QGridLayout(content)
        scroll.setWidget(content)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._chart_handler = _ChartHandler(self._grid)
        self._chart_handler.add_chart()

        # Rafraîchissement automatique toutes les 30 secondes
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._chart_handler.refresh)
        self._timer.start(30_000)

    def closeEvent(self, event):
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()
        # Attendre la fin du thread worker si actif
        handler = getattr(self, "_chart_handler", None)
        if handler and handler._is_thread_running():
            handler._thread.quit()
            handler._thread.wait(2000)
        super().closeEvent(event)
