import sys
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QMainWindow, QApplication, QLabel, QPushButton, 
                              QDateEdit, QHBoxLayout, QVBoxLayout, QWidget, QProgressBar, QGridLayout,
                              QMessageBox, QDialog, QFrame)
from PyQt6.QtCore import Qt, QTimer, QDate, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor
from PyQt6.QtCharts import (QChart, QChartView, QPieSeries, QBarSeries, QBarSet, 
                             QBarCategoryAxis, QValueAxis, QLineSeries)

from config import AppConfig
from .Show_Data import Ui_MainWindow
from database.connection import db


class DashboardDataWorker(QObject):
    """Worker Qt pour charger les agrégats dashboard hors thread UI."""

    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, fetch_fn, args):
        super().__init__()
        self._fetch_fn = fetch_fn
        self._args = args

    def run(self):
        try:
            payload = self._fetch_fn(*self._args)
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))


class DashboardPage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._compact_mode = self._is_compact_screen()
        self.dashboard_font = QFont(self.ui.get_data_btn.font())
        self._apply_dashboard_background()

        # Cache pour les comparaisons
        self.previous_stats = {}
        self._refresh_in_progress = False
        self._refresh_pending = False
        self._pending_reason = ""
        self._data_thread = None
        self._data_worker = None
        self._cache_ttl_sec = AppConfig.DASHBOARD_CACHE_TTL_SEC
        self._dashboard_cache = {}

        # Masquer les éléments inutiles de la barre d'outils et réorganiser
        self.ui.lineEdit.hide()
        self.ui.get_path_btn.hide()
        self.ui.save_btn.hide()
        self.ui.get_data_btn.hide()
        self.ui.line.hide()
        
        # Référence à la table
        self.result_table = self.ui.tableWidget
        self.ui.label_2.setText("Dashboard")
        
        # Créer les contrôles de filtre
        self._create_filter_controls()
        
        # Créer les labels KPI dans la barre blanche
        self._create_kpi_labels()
        
        # Configurer les graphiques (remplace la table)
        self._setup_charts()
        
        # Charger toutes les données
        self.request_refresh("initial")
        
        # Actualiser automatiquement toutes les 30 secondes
        self.kpi_timer = QTimer()
        self.kpi_timer.timeout.connect(lambda: self.request_refresh("auto"))
        self.kpi_timer.start(AppConfig.DASHBOARD_KPI_REFRESH_INTERVAL_MS)

    def _is_compact_screen(self):
        screen = self.screen()
        available_width = screen.availableGeometry().width() if screen else 1366
        return available_width <= 1440

    def _apply_dashboard_background(self):
        """Applique un fond visuel plus lisible et moderne au Dashboard."""
        self.setStyleSheet("""
            #MainWindow {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f4f7fb,
                    stop: 1 #e8f0fb
                );
            }

            #groupBox {
                border: none;
                border-radius: 8px;
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #1e88e5,
                    stop: 1 #42a5f5
                );
            }

            #groupBox_2 {
                background-color: rgba(255, 255, 255, 235);
                border: 1px solid #d9e2ef;
                border-radius: 10px;
            }

            #widget {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #d9e2ef;
                border-radius: 8px;
            }
        """)
    
    def _create_filter_controls(self):
        """Crée les contrôles de filtre de période"""
        default_end_date = QDate.currentDate()
        period_days = max(1, int(getattr(AppConfig, "DASHBOARD_DEFAULT_PERIOD_DAYS", 30)))
        default_start_date = default_end_date.addDays(-(period_days - 1))
        compact = self._compact_mode
        self.ui.horizontalLayout_2.setSpacing(6 if compact else 10)
        self.ui.horizontalLayout_2.setContentsMargins(8 if compact else 12, 6 if compact else 10, 8 if compact else 12, 6 if compact else 10)

        self.refresh_state_label = QLabel("• À jour")
        self.refresh_state_label.setFont(self.dashboard_font)
        self.refresh_state_label.setStyleSheet("color: #0a8f2e; font-weight: 600;")
        self.ui.horizontalLayout_2.addWidget(self.refresh_state_label)

        self.refresh_spinner = QProgressBar()
        self.refresh_spinner.setFixedWidth(70 if compact else 90)
        self.refresh_spinner.setRange(0, 0)
        self.refresh_spinner.setVisible(False)
        self.refresh_spinner.setTextVisible(False)
        self.refresh_spinner.setStyleSheet("QProgressBar { border: 1px solid #cfd8dc; border-radius: 8px; background: #f2f5f8; } QProgressBar::chunk { background-color: #1e88e5; border-radius: 7px; }")
        self.ui.horizontalLayout_2.addWidget(self.refresh_spinner)
        
        # Bouton de rafraîchissement manuel
        self.refresh_btn = QPushButton("🔄")
        refresh_btn_size = 30 if compact else 35
        self.refresh_btn.setFixedSize(refresh_btn_size, refresh_btn_size)
        self.refresh_btn.setToolTip("Actualiser maintenant")
        self.refresh_btn.clicked.connect(lambda: self.request_refresh("manual"))
        self.refresh_btn.setFont(self.dashboard_font)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a8f2e;
                color: white;
                border-radius: 17px;
                border: 1px solid #0a8f2e;
            }
            QPushButton:hover {
                background-color: #087625;
            }
        """)
        self.ui.horizontalLayout_2.addWidget(self.refresh_btn)

        # Bouton de suivi SLA
        self.sla_follow_btn = QPushButton("Suivi SLA")
        self.sla_follow_btn.setFixedHeight(30 if compact else 35)
        self.sla_follow_btn.setToolTip("Afficher les indicateurs SLA sur la période")
        self.sla_follow_btn.clicked.connect(self.show_sla_followup)
        self.sla_follow_btn.setFont(self.dashboard_font)
        self.sla_follow_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e88e5;
                color: white;
                border-radius: 8px;
                border: 1px solid #1e88e5;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #176fc0;
            }
        """)
        self.ui.horizontalLayout_2.addWidget(self.sla_follow_btn)
        
        # Plage de dates
        self.start_date_label = QLabel("Date début")
        self.start_date_label.setFont(self.dashboard_font)
        self.start_date_label.setStyleSheet("color: #333333;")
        self.ui.horizontalLayout_2.addWidget(self.start_date_label)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setDate(default_start_date)
        self.start_date_edit.setMaximumWidth(118 if compact else 132)
        self.start_date_edit.setFont(self.dashboard_font)
        self.start_date_edit.setStyleSheet("""
            QDateEdit {
                padding: 5px 8px;
                color: #333333;
                border: 1px solid #c7c7c7;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QDateEdit::drop-down { border: none; }
        """)
        self.start_date_edit.dateChanged.connect(self.on_period_changed)
        self.ui.horizontalLayout_2.addWidget(self.start_date_edit)

        self.end_date_label = QLabel("Date fin")
        self.end_date_label.setFont(self.dashboard_font)
        self.end_date_label.setStyleSheet("color: #333333;")
        self.ui.horizontalLayout_2.addWidget(self.end_date_label)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.end_date_edit.setDate(default_end_date)
        self.end_date_edit.setMaximumWidth(118 if compact else 132)
        self.end_date_edit.setFont(self.dashboard_font)
        self.end_date_edit.setStyleSheet("""
            QDateEdit {
                padding: 5px 8px;
                color: #333333;
                border: 1px solid #c7c7c7;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QDateEdit::drop-down { border: none; }
        """)
        self.end_date_edit.dateChanged.connect(self.on_period_changed)
        self.ui.horizontalLayout_2.addWidget(self.end_date_edit)

        self.period_7d_btn = QPushButton("7j")
        self.period_7d_btn.setFixedHeight(27 if compact else 30)
        self.period_7d_btn.setToolTip("Afficher les 7 derniers jours")
        self.period_7d_btn.setFont(self.dashboard_font)
        self.period_7d_btn.clicked.connect(lambda: self._apply_period_preset("7d"))
        self.ui.horizontalLayout_2.addWidget(self.period_7d_btn)

        self.period_30d_btn = QPushButton("30j")
        self.period_30d_btn.setFixedHeight(27 if compact else 30)
        self.period_30d_btn.setToolTip("Afficher les 30 derniers jours")
        self.period_30d_btn.setFont(self.dashboard_font)
        self.period_30d_btn.clicked.connect(lambda: self._apply_period_preset("30d"))
        self.ui.horizontalLayout_2.addWidget(self.period_30d_btn)

        self.period_month_btn = QPushButton("Mois")
        self.period_month_btn.setFixedHeight(27 if compact else 30)
        self.period_month_btn.setToolTip("Afficher le mois en cours")
        self.period_month_btn.setFont(self.dashboard_font)
        self.period_month_btn.clicked.connect(lambda: self._apply_period_preset("month"))
        self.ui.horizontalLayout_2.addWidget(self.period_month_btn)

        self._preset_buttons = {
            "7d": self.period_7d_btn,
            "30d": self.period_30d_btn,
            "month": self.period_month_btn,
        }
        self._sync_active_preset_from_dates()

    def _preset_button_style(self, active=False):
        if active:
            return """
                QPushButton {
                    background-color: #1e88e5;
                    color: #ffffff;
                    border-radius: 6px;
                    border: 1px solid #1e88e5;
                    padding: 0 8px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #176fc0;
                }
            """
        return """
            QPushButton {
                background-color: #f5f7fa;
                color: #1f2937;
                border-radius: 6px;
                border: 1px solid #cfd8e3;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #e8eff8;
            }
        """

    def _set_active_preset(self, preset_key=None):
        for key, button in self._preset_buttons.items():
            button.setStyleSheet(self._preset_button_style(active=(key == preset_key)))

    def _sync_active_preset_from_dates(self):
        start_date = self.start_date_edit.date()
        end_date = self.end_date_edit.date()
        today = QDate.currentDate()

        active_preset = None
        if end_date == today:
            if start_date == today.addDays(-6):
                active_preset = "7d"
            elif start_date == today.addDays(-29):
                active_preset = "30d"
            elif start_date == QDate(today.year(), today.month(), 1):
                active_preset = "month"

        self._set_active_preset(active_preset)

    def _apply_period_preset(self, preset):
        end_date = QDate.currentDate()
        if preset == "7d":
            start_date = end_date.addDays(-6)
        elif preset == "30d":
            start_date = end_date.addDays(-29)
        elif preset == "month":
            start_date = QDate(end_date.year(), end_date.month(), 1)
        else:
            return

        self.start_date_edit.blockSignals(True)
        self.end_date_edit.blockSignals(True)
        try:
            self.start_date_edit.setDate(start_date)
            self.end_date_edit.setDate(end_date)
        finally:
            self.start_date_edit.blockSignals(False)
            self.end_date_edit.blockSignals(False)

        self._set_active_preset(preset)
        self.request_refresh(f"preset:{preset}")

    def _style_chart(self, chart):
        chart.setBackgroundVisible(False)
        chart.setTitleFont(self.dashboard_font)
        chart.setTitleBrush(QColor("#333333"))
        chart.legend().setFont(self.dashboard_font)
        chart.legend().setLabelColor(QColor("#333333"))

    def _style_axes(self, axis_x=None, axis_y=None):
        if axis_x is not None:
            axis_x.setLabelsFont(self.dashboard_font)
            axis_x.setLabelsColor(QColor("#333333"))
        if axis_y is not None:
            axis_y.setLabelsFont(self.dashboard_font)
            axis_y.setLabelsColor(QColor("#333333"))
    
    def on_period_changed(self):
        """Gère le changement de plage de dates"""
        self._sync_active_preset_from_dates()
        self.request_refresh("period")

    def _set_refresh_state(self, text, color):
        self.refresh_state_label.setText(text)
        self.refresh_state_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def request_refresh(self, reason="manual"):
        """Demande un refresh transparent avec anti-chevauchement et coalescing."""
        self._pending_reason = reason
        if self._refresh_in_progress:
            self._refresh_pending = True
            self._set_refresh_state("• Synchronisation en attente...", "#ef6c00")
            return

        self._refresh_in_progress = True
        self._refresh_pending = False
        self._set_refresh_state("• Synchronisation...", "#1e88e5")
        self.refresh_btn.setEnabled(False)
        self.refresh_spinner.setVisible(True)
        QTimer.singleShot(0, self.update_all_data)

    def _build_cache_key(self, start_date, end_date):
        return f"{start_date.isoformat()}::{end_date.isoformat()}"

    def _get_cached_payload(self, cache_key):
        entry = self._dashboard_cache.get(cache_key)
        if not entry:
            return None
        ts = entry.get("ts")
        payload = entry.get("payload")
        if not ts or not payload:
            return None
        if (datetime.now() - ts).total_seconds() > self._cache_ttl_sec:
            return None
        return payload

    def _set_cached_payload(self, cache_key, payload):
        self._dashboard_cache[cache_key] = {
            "ts": datetime.now(),
            "payload": payload,
        }

    def _finalize_refresh(self):
        self._refresh_in_progress = False
        self.refresh_btn.setEnabled(True)
        self.refresh_spinner.setVisible(False)

        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, lambda: self.request_refresh(self._pending_reason or "queued"))

    def _start_data_worker(self, args):
        self._data_thread = QThread(self)
        self._data_worker = DashboardDataWorker(self._build_dashboard_payload, args)
        self._data_worker.moveToThread(self._data_thread)
        self._data_thread.started.connect(self._data_worker.run)
        self._data_worker.finished.connect(self._on_data_worker_finished)
        self._data_worker.failed.connect(self._on_data_worker_failed)
        self._data_worker.finished.connect(self._data_thread.quit)
        self._data_worker.failed.connect(self._data_thread.quit)
        self._data_thread.finished.connect(self._data_worker.deleteLater)
        self._data_thread.finished.connect(self._data_thread.deleteLater)
        self._data_thread.finished.connect(lambda: setattr(self, "_data_worker", None))
        self._data_thread.finished.connect(lambda: setattr(self, "_data_thread", None))
        self._data_thread.start()

    def _on_data_worker_finished(self, payload):
        try:
            cache_key = payload.get("cache_key")
            if cache_key:
                self._set_cached_payload(cache_key, payload)
            self.update_kpi(payload)
            self.update_charts(payload)
            self._set_refresh_state("• À jour", "#0a8f2e")
        except Exception as e:
            self._set_refresh_state("• Erreur de synchronisation", "#c62828")
            print(f"Erreur application payload dashboard: {e}")
        finally:
            self._finalize_refresh()

    def _on_data_worker_failed(self, error_message):
        self._set_refresh_state("• Erreur de synchronisation", "#c62828")
        print(f"Erreur worker dashboard: {error_message}")
        self._finalize_refresh()

    def closeEvent(self, event):
        timer = getattr(self, "kpi_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

        thread = getattr(self, "_data_thread", None)
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(2000)

        super().closeEvent(event)

    @staticmethod
    def _build_dashboard_payload(start_str, end_str, comp_start_str, comp_end_str, today, cache_key):
        query_total = """
            SELECT COUNT(*) as total
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ?
        """
        result_total = db.execute_query(query_total, (start_str, end_str))
        result_total_comp = db.execute_query(query_total, (comp_start_str, comp_end_str))

        query_attente = """
            SELECT COUNT(*) as attente
            FROM accueil_demandeaccueil
            WHERE DATE(date) = ? AND statut = 'en_attente'
        """
        result_attente = db.execute_query(query_attente, (today,))

        query_traite = """
            SELECT COUNT(*) as traite
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ? AND statut = 'traite'
        """
        result_traite = db.execute_query(query_traite, (start_str, end_str))
        result_traite_comp = db.execute_query(query_traite, (comp_start_str, comp_end_str))

        query_satisfaction = """
            SELECT AVG(satisfaction) as satisfaction_moyenne
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ?
            AND satisfaction IS NOT NULL
            AND satisfaction > 0
        """
        result_satisfaction = db.execute_query(query_satisfaction, (start_str, end_str))

        query_statut = """
            SELECT statut, COUNT(*) as count
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ?
            GROUP BY statut
        """
        results_statut = db.execute_query(query_statut, (start_str, end_str))

        query_delai_objectif = """
            SELECT
                CASE
                    WHEN LOWER(TRIM(CAST(delai_objectif AS TEXT))) IN ('1', 'true', 'vrai', 'yes') THEN 1
                    ELSE 0
                END AS objectif_atteint,
                COUNT(*) as count
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ?
              AND statut = 'traite'
            GROUP BY objectif_atteint
        """
        results_delai_objectif = db.execute_query(query_delai_objectif, (start_str, end_str))

        query_services = f"""
            SELECT s.nom, COUNT(*) as count
            FROM accueil_demandeaccueil d
            LEFT JOIN accueil_service s ON d.service_demande_id = s.id
            WHERE DATE(d.date) BETWEEN ? AND ?
            GROUP BY s.nom
            ORDER BY count DESC
            LIMIT {AppConfig.DASHBOARD_TOP_ITEMS_LIMIT}
        """
        results_services = db.execute_query(query_services, (start_str, end_str))

        query_motifs = f"""
            SELECT m.nom, COUNT(*) as count
            FROM accueil_demandeaccueil d
            LEFT JOIN accueil_motif m ON d.motif_id = m.id
            WHERE DATE(d.date) BETWEEN ? AND ?
            GROUP BY m.nom
            ORDER BY count DESC
            LIMIT {AppConfig.DASHBOARD_TOP_ITEMS_LIMIT}
        """
        results_motifs = db.execute_query(query_motifs, (start_str, end_str))

        query_flux = """
            SELECT
                CAST(strftime('%H', heure_arrivee) AS INTEGER) as heure,
                COUNT(*) as count
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ?
            AND heure_arrivee IS NOT NULL
            AND TRIM(CAST(heure_arrivee AS TEXT)) <> ''
            GROUP BY heure
            ORDER BY heure
        """
        results_flux = db.execute_query(query_flux, (start_str, end_str))

        query_satisfaction_rate = """
            SELECT
                COUNT(*) AS total_traite,
                SUM(CASE WHEN satisfaction >= 4 THEN 1 ELSE 0 END) AS satisfaites,
                SUM(CASE WHEN satisfaction = 3 THEN 1 ELSE 0 END) AS moyennes,
                SUM(CASE WHEN satisfaction <= 2 AND satisfaction IS NOT NULL THEN 1 ELSE 0 END) AS insatisfaites
            FROM accueil_demandeaccueil
            WHERE DATE(date) BETWEEN ? AND ?
            AND statut = 'traite'
        """
        result_rate = db.execute_query(query_satisfaction_rate, (start_str, end_str))

        return {
            "cache_key": cache_key,
            "result_total": result_total,
            "result_total_comp": result_total_comp,
            "result_attente": result_attente,
            "result_traite": result_traite,
            "result_traite_comp": result_traite_comp,
            "result_satisfaction": result_satisfaction,
            "results_statut": results_statut,
            "results_delai_objectif": results_delai_objectif,
            "results_services": results_services,
            "results_motifs": results_motifs,
            "results_flux": results_flux,
            "result_rate": result_rate,
        }
    
    def _get_date_range(self):
        """Retourne la plage Date début / Date fin sélectionnée."""
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()

        if start_date > end_date:
            start_date, end_date = end_date, start_date

        return start_date, end_date

    def _create_sla_card(self, title_text, value_text, subtitle_text, background_color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {background_color};
                border: 1px solid #d9e2ef;
                border-radius: 12px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel(title_text)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #334155; font-size: 10pt; font-weight: 600;")

        value = QLabel(value_text)
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("color: #0f172a; font-size: 16pt; font-weight: 700;")

        subtitle = QLabel(subtitle_text)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #475569; font-size: 9pt;")

        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(subtitle)
        return card

    def _show_sla_followup_dialog(self, start_date, end_date, n, avg_min, sla_lt_15, sla_ge_15, niveau_sla, top_services, top_hours):
        dialog = QDialog(self)
        dialog.setWindowTitle("Suivi SLA")
        dialog.setMinimumSize(860, 600)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f8fbff;
            }
            QLabel#title {
                color: #0f172a;
                font-size: 18pt;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #475569;
                font-size: 10pt;
            }
            QLabel#status {
                color: #0f172a;
                font-size: 10pt;
                font-weight: 700;
                padding: 6px 12px;
                border-radius: 10px;
                background-color: #eef2ff;
                border: 1px solid #c7d2fe;
            }
            QLabel#section {
                color: #1e3a8a;
                font-size: 11pt;
                font-weight: 700;
                padding: 4px 0;
            }
            QFrame#sectionBox {
                background: #ffffff;
                border: 1px solid #dbe7f5;
                border-radius: 12px;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #f1f5f9;
                color: #0f172a;
                text-align: center;
                font-weight: 600;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #22c55e;
                border-radius: 7px;
            }
            QPushButton {
                background-color: #1e88e5;
                color: white;
                border-radius: 8px;
                border: 1px solid #1e88e5;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #176fc0;
            }
        """)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(18, 16, 18, 14)
        main_layout.setSpacing(10)

        title = QLabel("Suivi SLA")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        subtitle = QLabel(
            f"Période: {start_date.strftime('%d/%m/%Y')} → {end_date.strftime('%d/%m/%Y')}  |  "
            "SLA = demandes traitées en moins de 15 minutes"
        )
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle)

        status_chip = QLabel(f"Niveau SLA: {niveau_sla}")
        status_chip.setObjectName("status")
        status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(status_chip, alignment=Qt.AlignmentFlag.AlignCenter)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(10)
        cards_layout.addWidget(self._create_sla_card("Demandes traitées", str(n), "Volume analysé", "#eef6ff"), 0, 0)
        cards_layout.addWidget(self._create_sla_card("Attente moyenne", f"{avg_min} min", "Plus bas = mieux", "#f3fdf5"), 0, 1)
        cards_layout.addWidget(self._create_sla_card("SLA < 15 min", f"{sla_lt_15}%", "Objectif atteint", "#ecfdf3"), 0, 2)
        cards_layout.addWidget(self._create_sla_card("SLA ≥ 15 min", f"{sla_ge_15}%", "Hors objectif", "#fff1f2"), 0, 3)
        main_layout.addLayout(cards_layout)

        progress_box = QFrame()
        progress_box.setObjectName("sectionBox")
        progress_layout = QVBoxLayout(progress_box)
        progress_layout.setContentsMargins(12, 10, 12, 10)
        progress_layout.setSpacing(6)
        progress_title = QLabel("Performance SLA globale")
        progress_title.setObjectName("section")
        progress_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(progress_title)

        sla_bar = QProgressBar()
        bar_value = max(0, min(100, int(round(float(sla_lt_15)))))
        sla_bar.setValue(bar_value)
        sla_bar.setFormat(f"{sla_lt_15}% de demandes dans l'objectif (< 15 min)")
        progress_layout.addWidget(sla_bar)
        main_layout.addWidget(progress_box)

        sections_layout = QHBoxLayout()
        sections_layout.setSpacing(10)

        services_box = QFrame()
        services_box.setObjectName("sectionBox")
        services_layout = QVBoxLayout(services_box)
        services_layout.setContentsMargins(12, 10, 12, 10)
        services_layout.setSpacing(6)
        services_title = QLabel("Services prioritaires SLA")
        services_title.setObjectName("section")
        services_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        services_layout.addWidget(services_title)

        if top_services:
            services_lines = "\n".join([
                f"• <b>{r.get('service')}</b> : <span style='color:#b91c1c;'>{r.get('pct_ge_15')}%</span> hors objectif (n={r.get('n')})"
                for r in top_services
            ])
        else:
            services_lines = "• Aucune donnée suffisante"
        services_text = QLabel(services_lines)
        services_text.setWordWrap(True)
        services_text.setTextFormat(Qt.TextFormat.RichText)
        services_text.setStyleSheet("color: #334155; font-size: 10pt;")
        services_layout.addWidget(services_text)
        sections_layout.addWidget(services_box)

        hours_box = QFrame()
        hours_box.setObjectName("sectionBox")
        hours_layout = QVBoxLayout(hours_box)
        hours_layout.setContentsMargins(12, 10, 12, 10)
        hours_layout.setSpacing(6)
        hours_title = QLabel("Heures critiques")
        hours_title.setObjectName("section")
        hours_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hours_layout.addWidget(hours_title)

        if top_hours:
            hours_lines = "\n".join([
                f"• <b>{r.get('heure')}</b> : <span style='color:#b91c1c;'>{r.get('pct_ge_15')}%</span> hors objectif (n={r.get('n')})"
                for r in top_hours
            ])
        else:
            hours_lines = "• Aucune donnée suffisante"
        hours_text = QLabel(hours_lines)
        hours_text.setWordWrap(True)
        hours_text.setTextFormat(Qt.TextFormat.RichText)
        hours_text.setStyleSheet("color: #334155; font-size: 10pt;")
        hours_layout.addWidget(hours_text)
        sections_layout.addWidget(hours_box)

        main_layout.addLayout(sections_layout)

        footer = QLabel(
            "Lecture rapide: SLA < 15 min doit monter, SLA ≥ 15 min doit baisser. "
            "Agis d'abord sur le 1er service et la 1ère heure critique."
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #475569; font-size: 10pt; font-weight: 600;")
        main_layout.addWidget(footer)

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(dialog.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        dialog.exec()

    def show_sla_followup(self):
        """Affiche un résumé SLA opérationnel sur la plage de dates sélectionnée."""
        try:
            start_date, end_date = self._get_date_range()
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            query_kpi = """
                WITH t AS (
                    SELECT
                        CAST(substr(temps_attente,1,2) AS INT)*3600 +
                        CAST(substr(temps_attente,4,2) AS INT)*60 +
                        CAST(substr(temps_attente,7,2) AS INT) AS wait_sec
                    FROM accueil_demandeaccueil
                    WHERE statut='traite'
                      AND DATE(date) BETWEEN ? AND ?
                      AND temps_attente GLOB '[0-9][0-9]:[0-5][0-9]:[0-5][0-9]'
                )
                SELECT
                    COUNT(*) AS n,
                    ROUND(AVG(wait_sec)/60.0,2) AS avg_min,
                    ROUND(SUM(CASE WHEN wait_sec < 900 THEN 1 ELSE 0 END)*100.0/COUNT(*),2) AS sla_lt_15,
                    ROUND(SUM(CASE WHEN wait_sec >= 900 THEN 1 ELSE 0 END)*100.0/COUNT(*),2) AS sla_ge_15
                FROM t
            """
            kpi = db.execute_query(query_kpi, (start_str, end_str))
            row = kpi[0] if kpi else {}
            n = int(row.get('n') or 0)
            avg_min = row.get('avg_min') if row.get('avg_min') is not None else 0
            sla_lt_15 = row.get('sla_lt_15') if row.get('sla_lt_15') is not None else 0
            sla_ge_15 = row.get('sla_ge_15') if row.get('sla_ge_15') is not None else 0

            query_services = f"""
                WITH t AS (
                    SELECT
                        COALESCE(s.nom,'Non défini') AS service,
                        CAST(substr(d.temps_attente,1,2) AS INT)*3600 +
                        CAST(substr(d.temps_attente,4,2) AS INT)*60 +
                        CAST(substr(d.temps_attente,7,2) AS INT) AS wait_sec
                    FROM accueil_demandeaccueil d
                    LEFT JOIN accueil_service s ON s.id=d.service_demande_id
                    WHERE d.statut='traite'
                      AND DATE(d.date) BETWEEN ? AND ?
                      AND d.temps_attente GLOB '[0-9][0-9]:[0-5][0-9]:[0-5][0-9]'
                )
                SELECT
                    service,
                    COUNT(*) AS n,
                    ROUND(SUM(CASE WHEN wait_sec >= 900 THEN 1 ELSE 0 END)*100.0/COUNT(*),2) AS pct_ge_15
                FROM t
                GROUP BY service
                HAVING COUNT(*) >= 10
                ORDER BY pct_ge_15 DESC, n DESC
                LIMIT {AppConfig.DASHBOARD_SLA_TOP_LIMIT}
            """
            top_services = db.execute_query(query_services, (start_str, end_str))

            query_hours = f"""
                WITH t AS (
                    SELECT
                        CAST(substr(heure_arrivee,1,2) AS INT) AS h,
                        CAST(substr(temps_attente,1,2) AS INT)*3600 +
                        CAST(substr(temps_attente,4,2) AS INT)*60 +
                        CAST(substr(temps_attente,7,2) AS INT) AS wait_sec
                    FROM accueil_demandeaccueil
                    WHERE statut='traite'
                      AND DATE(date) BETWEEN ? AND ?
                      AND heure_arrivee GLOB '[0-2][0-9]:[0-5][0-9]:[0-5][0-9]'
                      AND temps_attente GLOB '[0-9][0-9]:[0-5][0-9]:[0-5][0-9]'
                )
                SELECT
                    printf('%02dh', h) AS heure,
                    COUNT(*) AS n,
                    ROUND(SUM(CASE WHEN wait_sec >= 900 THEN 1 ELSE 0 END)*100.0/COUNT(*),2) AS pct_ge_15
                FROM t
                GROUP BY h
                HAVING COUNT(*) >= 8
                ORDER BY pct_ge_15 DESC, n DESC
                LIMIT {AppConfig.DASHBOARD_SLA_TOP_LIMIT}
            """
            top_hours = db.execute_query(query_hours, (start_str, end_str))

            if n == 0:
                niveau_sla = "Non calculable (aucune demande traitée sur la période)"
            elif sla_lt_15 >= 90:
                niveau_sla = "Excellent"
            elif sla_lt_15 >= 80:
                niveau_sla = "Correct (à améliorer)"
            elif sla_lt_15 >= 70:
                niveau_sla = "Fragile"
            else:
                niveau_sla = "Critique"

            self._show_sla_followup_dialog(
                start_date,
                end_date,
                n,
                avg_min,
                sla_lt_15,
                sla_ge_15,
                niveau_sla,
                top_services,
                top_hours,
            )
        except Exception as e:
            QMessageBox.warning(self, "Suivi SLA", f"Erreur lors du calcul SLA: {e}")
    
    def _setup_charts(self):
        """Configure les graphiques à la place de la table"""
        # Masquer la table d'origine
        self.result_table.hide()
        
        # Créer un widget container pour les graphiques
        charts_widget = QWidget()
        charts_widget.setObjectName("chartsWidget")
        charts_widget.setStyleSheet("""
            #chartsWidget {
                background: transparent;
            }
            #chartsWidget QChartView {
                background-color: rgba(255, 255, 255, 248);
                border: 1px solid #d9e2ef;
                border-radius: 8px;
            }
        """)
        charts_layout = QGridLayout(charts_widget)
        charts_layout.setSpacing(6 if self._compact_mode else 10)
        charts_layout.setContentsMargins(
            6 if self._compact_mode else 10,
            6 if self._compact_mode else 10,
            6 if self._compact_mode else 10,
            6 if self._compact_mode else 10,
        )
        
        # Créer les graphiques
        self._create_status_chart()
        self._create_delai_objectif_chart()
        self._create_services_chart()
        self._create_motifs_chart()
        self._create_hourly_chart()
        self._create_satisfaction_rate_chart()
        
        # Ajouter les graphiques à la grille (2x3)
        charts_layout.addWidget(self.status_chart_view, 0, 0)
        charts_layout.addWidget(self.delai_objectif_chart_view, 0, 1)
        charts_layout.addWidget(self.services_chart_view, 0, 2)
        charts_layout.addWidget(self.motifs_chart_view, 1, 0)
        charts_layout.addWidget(self.hourly_chart_view, 1, 1)
        charts_layout.addWidget(self.satisfaction_rate_chart_view, 1, 2)
        
        # Remplacer la table par le widget de graphiques
        parent_layout = self.result_table.parent().layout()
        if parent_layout:
            parent_layout.replaceWidget(self.result_table, charts_widget)
    
    def _create_status_chart(self):
        """Crée le graphique en camembert pour les statuts"""
        self.status_series = QPieSeries()
        self.status_chart = QChart()
        self.status_chart.addSeries(self.status_series)
        self.status_chart.setTitle("📊 Répartition par Statut")
        self.status_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.status_chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._style_chart(self.status_chart)
        
        self.status_chart_view = QChartView(self.status_chart)
        self.status_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.status_chart_view.setMinimumSize(280, 220) if self._compact_mode else self.status_chart_view.setMinimumSize(320, 280)
    
    def _create_delai_objectif_chart(self):
        """Crée le graphique en camembert pour le délai objectif (15 min)."""
        self.delai_objectif_series = QPieSeries()
        self.delai_objectif_chart = QChart()
        self.delai_objectif_chart.addSeries(self.delai_objectif_series)
        self.delai_objectif_chart.setTitle("🎯 Délai Objectif 15 min (Demandes Traitées)")
        self.delai_objectif_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.delai_objectif_chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._style_chart(self.delai_objectif_chart)
        
        self.delai_objectif_chart_view = QChartView(self.delai_objectif_chart)
        self.delai_objectif_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.delai_objectif_chart_view.setMinimumSize(280, 220) if self._compact_mode else self.delai_objectif_chart_view.setMinimumSize(320, 280)
    
    def _create_services_chart(self):
        """Crée le graphique en barres pour les services"""
        self.services_series = QBarSeries()
        self.services_chart = QChart()
        self.services_chart.addSeries(self.services_series)
        self.services_chart.setTitle("🏢 Top 5 Services")
        self.services_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.services_chart.legend().setVisible(False)
        self._style_chart(self.services_chart)
        
        self.services_chart_view = QChartView(self.services_chart)
        self.services_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.services_chart_view.setMinimumSize(280, 220) if self._compact_mode else self.services_chart_view.setMinimumSize(320, 280)
    
    def _create_motifs_chart(self):
        """Crée le graphique en barres pour les motifs"""
        self.motifs_series = QBarSeries()
        self.motifs_chart = QChart()
        self.motifs_chart.addSeries(self.motifs_series)
        self.motifs_chart.setTitle("📝 Top 5 Motifs")
        self.motifs_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.motifs_chart.legend().setVisible(False)
        self._style_chart(self.motifs_chart)
        
        self.motifs_chart_view = QChartView(self.motifs_chart)
        self.motifs_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.motifs_chart_view.setMinimumSize(280, 220) if self._compact_mode else self.motifs_chart_view.setMinimumSize(320, 280)
    
    def _create_hourly_chart(self):
        """Crée le graphique en barres pour le flux horaire"""
        self.hourly_series = QBarSeries()
        self.hourly_chart = QChart()
        self.hourly_chart.addSeries(self.hourly_series)
        self.hourly_chart.setTitle("⏰ Flux Horaire")
        self.hourly_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.hourly_chart.legend().setVisible(False)
        self._style_chart(self.hourly_chart)
        
        self.hourly_chart_view = QChartView(self.hourly_chart)
        self.hourly_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.hourly_chart_view.setMinimumSize(280, 220) if self._compact_mode else self.hourly_chart_view.setMinimumSize(320, 280)
    
    def _create_satisfaction_rate_chart(self):
        """Crée le graphique en barres du taux de satisfaction des demandes traitées."""
        self.satisfaction_rate_series = QBarSeries()
        self.satisfaction_rate_chart = QChart()
        self.satisfaction_rate_chart.addSeries(self.satisfaction_rate_series)
        self.satisfaction_rate_chart.setTitle("⭐ Taux de Satisfaction (Demandes Traitées)")
        self.satisfaction_rate_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.satisfaction_rate_chart.legend().setVisible(False)
        self._style_chart(self.satisfaction_rate_chart)
        
        self.satisfaction_rate_chart_view = QChartView(self.satisfaction_rate_chart)
        self.satisfaction_rate_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.satisfaction_rate_chart_view.setMinimumSize(280, 220) if self._compact_mode else self.satisfaction_rate_chart_view.setMinimumSize(320, 280)
    
    def _setup_table(self):
        """Configure la table des statistiques (OBSOLÈTE - remplacé par charts)"""
        pass
    
    def _create_kpi_labels(self):
        """Crée les 5 labels KPI avec alertes colorées"""
        compact = self._compact_mode
        self._kpi_font_size = "9pt" if compact else "10pt"
        self._kpi_padding = "6px 9px" if compact else "8px 12px"
        kpi_min_width = 112 if compact else 130

        # Style de base
        base_style = f"""
            QLabel {{
                color: #000;
                font-size: {self._kpi_font_size};
                font-weight: bold;
                padding: {self._kpi_padding};
                border-radius: 8px;
                border: 2px solid #ddd;
            }}
        """
        
        # Créer les KPI labels
        self.kpi_total = QLabel("📊 Total: --")
        self.kpi_total.setStyleSheet(base_style + "QLabel { background-color: #E3F2FD; }")
        self.kpi_total.setFont(self.dashboard_font)
        self.kpi_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kpi_total.setMinimumWidth(kpi_min_width)
        
        self.kpi_attente = QLabel("⏳ Attente: --")
        self.kpi_attente.setStyleSheet(base_style + "QLabel { background-color: #FFF9C4; }")
        self.kpi_attente.setFont(self.dashboard_font)
        self.kpi_attente.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kpi_attente.setMinimumWidth(kpi_min_width)
        
        self.kpi_traite = QLabel("✅ Traités: --")
        self.kpi_traite.setStyleSheet(base_style + "QLabel { background-color: #C8E6C9; }")
        self.kpi_traite.setFont(self.dashboard_font)
        self.kpi_traite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kpi_traite.setMinimumWidth(kpi_min_width)
        
        self.kpi_satisfaction = QLabel("⭐ Satisf: --")
        self.kpi_satisfaction.setStyleSheet(base_style + "QLabel { background-color: #CFD8DC; }")
        self.kpi_satisfaction.setFont(self.dashboard_font)
        self.kpi_satisfaction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kpi_satisfaction.setMinimumWidth(kpi_min_width)
        
        # Layout horizontal pour les KPI
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(6 if compact else 10)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.addWidget(self.kpi_total)
        kpi_layout.addWidget(self.kpi_attente)
        kpi_layout.addWidget(self.kpi_traite)
        kpi_layout.addWidget(self.kpi_satisfaction)
        kpi_layout.addStretch()
        
        # Ajouter au widget
        self.ui.horizontalLayout_2.insertLayout(0, kpi_layout)
    
    def update_kpi(self, payload=None):
        """Met à jour les KPI avec alertes colorées et comparaisons"""
        try:
            start_date, end_date = self._get_date_range()
            
            # Calculer la période de comparaison (même durée avant)
            delta_days = (end_date - start_date).days + 1
            comp_end = start_date - timedelta(days=1)
            if payload is None:
                comp_start = comp_end - timedelta(days=delta_days - 1)
                payload = self._build_dashboard_payload(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    comp_start.strftime("%Y-%m-%d"),
                    comp_end.strftime("%Y-%m-%d"),
                    datetime.now().strftime("%Y-%m-%d"),
                    self._build_cache_key(start_date, end_date),
                )

            result_total = payload.get('result_total', [])
            total = result_total[0]['total'] if result_total else 0

            result_total_comp = payload.get('result_total_comp', [])
            total_comp = result_total_comp[0]['total'] if result_total_comp else 0
            
            diff_total = total - total_comp
            trend_total = f" ({diff_total:+d})" if total_comp > 0 else ""
            self.kpi_total.setText(f"📊 Total: {total}{trend_total}")
            
            # KPI 2: Demandes en attente (seulement aujourd'hui)
            result_attente = payload.get('result_attente', [])
            attente = result_attente[0]['attente'] if result_attente else 0
            self.kpi_attente.setText(f"⏳ Attente: {attente}")
            
            # Alerte colorée pour attente
            if attente == 0:
                color = "#C8E6C9"  # Vert
            elif attente <= 5:
                color = "#FFF9C4"  # Jaune
            else:
                color = "#FFCDD2"  # Rouge
            self.kpi_attente.setStyleSheet(f"""
                QLabel {{
                    color: #000;
                    font-size: {self._kpi_font_size};
                    font-weight: bold;
                    padding: {self._kpi_padding};
                    border-radius: 8px;
                    border: 2px solid #ddd;
                    background-color: {color};
                }}
            """)
            
            # KPI 3: Demandes traitées
            result_traite = payload.get('result_traite', [])
            traite = result_traite[0]['traite'] if result_traite else 0

            result_traite_comp = payload.get('result_traite_comp', [])
            traite_comp = result_traite_comp[0]['traite'] if result_traite_comp else 0
            
            diff_traite = traite - traite_comp
            trend_traite = f" ({diff_traite:+d})" if traite_comp > 0 else ""
            self.kpi_traite.setText(f"✅ Traités: {traite}{trend_traite}")
            
            # KPI 4: Satisfaction moyenne
            result_satisfaction = payload.get('result_satisfaction', [])
            satisfaction_moy = result_satisfaction[0]['satisfaction_moyenne'] if result_satisfaction and result_satisfaction[0]['satisfaction_moyenne'] else 0
            
            if satisfaction_moy:
                self.kpi_satisfaction.setText(f"⭐ Satisf: {satisfaction_moy:.1f}/5")
                # Alerte colorée pour satisfaction
                if satisfaction_moy >= 4:
                    color = "#C8E6C9"  # Vert
                elif satisfaction_moy >= 3:
                    color = "#FFF9C4"  # Jaune
                else:
                    color = "#FFCDD2"  # Rouge
                self.kpi_satisfaction.setStyleSheet(f"""
                    QLabel {{
                        color: #000;
                        font-size: {self._kpi_font_size};
                        font-weight: bold;
                        padding: {self._kpi_padding};
                        border-radius: 8px;
                        border: 2px solid #ddd;
                        background-color: {color};
                    }}
                """)
            else:
                self.kpi_satisfaction.setText("⭐ Satisf: --")
            
            # Sauvegarder les stats pour comparaison
            self.previous_stats = {
                'total': total,
                'traite': traite,
                'satisfaction': satisfaction_moy
            }
                
        except Exception as e:
            print(f"Erreur lors de la mise à jour des KPI: {e}")
            import traceback
            traceback.print_exc()
            self.kpi_total.setText("📊 Total: Erreur")
            self.kpi_attente.setText("⏳ Attente: --")
            self.kpi_traite.setText("✅ Traités: --")
            self.kpi_satisfaction.setText("⭐ Satisf: --")
    
    def update_charts(self, payload=None):
        """Met à jour tous les graphiques avec les données de la base"""
        try:
            from PyQt6.QtGui import QColor
            from PyQt6.QtCore import Qt as QtCore_Qt
            
            start_date, end_date = self._get_date_range()
            if payload is None:
                delta_days = (end_date - start_date).days + 1
                comp_end = start_date - timedelta(days=1)
                comp_start = comp_end - timedelta(days=delta_days - 1)
                payload = self._build_dashboard_payload(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    comp_start.strftime("%Y-%m-%d"),
                    comp_end.strftime("%Y-%m-%d"),
                    datetime.now().strftime("%Y-%m-%d"),
                    self._build_cache_key(start_date, end_date),
                )
            
            # ========== GRAPHIQUE 1: STATUTS ==========
            self.status_series.clear()
            results_statut = payload.get('results_statut', [])
            
            statut_config = {
                'en_attente': ('⏳ En attente', QColor(211, 47, 47, 85)),
                'non_traite': ('Non Traité', QColor(255, 152, 0, 90)),
                'en_cours': ('🔄 En cours', QColor(179, 229, 252)),
                'traite': ('✅ Traité', QColor(10, 143, 46, 85)),
                'annule': ('❌ Annulé', QColor(255, 205, 210))
            }
            
            for result in results_statut:
                statut = result['statut']
                count = result['count']
                label, color = statut_config.get(statut, (statut, QColor(200, 200, 200)))
                slice = self.status_series.append(f"{label}\n{count}", count)
                slice.setBrush(color)
                slice.setLabelFont(self.dashboard_font)
                slice.setLabelColor(QColor("#333333"))
                slice.setLabelVisible(True)
            
            # ========== GRAPHIQUE 2: DÉLAI OBJECTIF (15 MIN) ==========
            self.delai_objectif_series.clear()
            results_delai_objectif = payload.get('results_delai_objectif', [])
            
            delai_objectif_config = {
                1: ('✅ < 15 min (Objectif atteint)', QColor(200, 230, 201)),
                0: ('❌ ≥ 15 min (Hors objectif)', QColor(255, 205, 210)),
            }

            counts_by_objectif = {1: 0, 0: 0}
            for result in results_delai_objectif:
                try:
                    objectif_atteint = int(result['objectif_atteint'])
                except (TypeError, ValueError):
                    objectif_atteint = 0
                counts_by_objectif[objectif_atteint] = int(result['count'] or 0)

            self.delai_objectif_chart.setTitle(
                "🎯 Délai Objectif 15 min (Demandes Traitées)"
                f"\n✅ < 15 min: {counts_by_objectif.get(1, 0)} | ❌ ≥ 15 min: {counts_by_objectif.get(0, 0)}"
            )

            for objectif_atteint in (1, 0):
                count = counts_by_objectif.get(objectif_atteint, 0)
                _, color = delai_objectif_config.get(objectif_atteint, (objectif_atteint, QColor(200, 200, 200)))
                if objectif_atteint == 1:
                    slice_title = f"Objectif atteint < 15 min: {count}"
                else:
                    slice_title = f"Hors objectif ≥ 15 min: {count}"

                # Valeur minimale si count=0 pour conserver l'entrée visible dans la légende
                slice_value = count if count > 0 else 0.0001
                slice = self.delai_objectif_series.append(slice_title, slice_value)
                slice.setBrush(color)
                slice.setLabelFont(self.dashboard_font)
                slice.setLabelColor(QColor("#333333"))
                slice.setLabelVisible(True)
            
            # ========== GRAPHIQUE 3: TOP 5 SERVICES ==========
            self.services_chart.removeAllSeries()
            self.services_series = QBarSeries()
            results_services = payload.get('results_services', [])
            
            services_names = []
            services_set = QBarSet("Demandes")
            services_set.setColor(QColor(33, 150, 243))
            
            for result in results_services:
                service = result['nom'] if result['nom'] else 'Non défini'
                count = result['count']
                services_names.append(service[:15] + "..." if len(service) > 15 else service)
                services_set.append(count)
            
            self.services_series.append(services_set)
            self.services_chart.addSeries(self.services_series)
            
            # Supprimer les anciens axes pour éviter l'accumulation
            for axis in self.services_chart.axes():
                self.services_chart.removeAxis(axis)
            
            # Axes pour services
            if services_names:
                axis_x = QBarCategoryAxis()
                axis_x.append(services_names)
                self.services_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
                self.services_series.attachAxis(axis_x)
                
                axis_y = QValueAxis()
                axis_y.setRange(0, max([services_set.at(i) for i in range(services_set.count())]) * 1.2 if services_set.count() > 0 else 10)
                self.services_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
                self.services_series.attachAxis(axis_y)
                self._style_axes(axis_x, axis_y)
            
            # ========== GRAPHIQUE 4: TOP 5 MOTIFS ==========
            self.motifs_chart.removeAllSeries()
            self.motifs_series = QBarSeries()
            results_motifs = payload.get('results_motifs', [])
            
            motifs_names = []
            motifs_set = QBarSet("Demandes")
            motifs_set.setColor(QColor(76, 175, 80))
            
            for result in results_motifs:
                motif = result['nom'] if result['nom'] else 'Non défini'
                count = result['count']
                motifs_names.append(motif[:15] + "..." if len(motif) > 15 else motif)
                motifs_set.append(count)
            
            self.motifs_series.append(motifs_set)
            self.motifs_chart.addSeries(self.motifs_series)
            
            # Supprimer les anciens axes pour éviter l'accumulation
            for axis in self.motifs_chart.axes():
                self.motifs_chart.removeAxis(axis)
            
            # Axes pour motifs
            if motifs_names:
                axis_x = QBarCategoryAxis()
                axis_x.append(motifs_names)
                self.motifs_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
                self.motifs_series.attachAxis(axis_x)
                
                axis_y = QValueAxis()
                axis_y.setRange(0, max([motifs_set.at(i) for i in range(motifs_set.count())]) * 1.2 if motifs_set.count() > 0 else 10)
                self.motifs_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
                self.motifs_series.attachAxis(axis_y)
                self._style_axes(axis_x, axis_y)
            
            # ========== GRAPHIQUE 5: FLUX HORAIRE ==========
            self.hourly_chart.removeAllSeries()
            self.hourly_series = QBarSeries()
            results_flux = payload.get('results_flux', [])
            
            hourly_names = []
            hourly_set = QBarSet("Demandes")
            hourly_set.setColor(QColor(255, 152, 0))
            
            for result in results_flux:
                heure = result['heure']
                count = result['count']
                hourly_names.append(f"{heure:02d}h")
                hourly_set.append(count)
            
            self.hourly_series.append(hourly_set)
            self.hourly_chart.addSeries(self.hourly_series)
            
            # Supprimer les anciens axes pour éviter l'accumulation
            for axis in self.hourly_chart.axes():
                self.hourly_chart.removeAxis(axis)
            
            # Axes pour flux horaire
            if hourly_names:
                axis_x = QBarCategoryAxis()
                axis_x.append(hourly_names)
                self.hourly_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
                self.hourly_series.attachAxis(axis_x)
                
                axis_y = QValueAxis()
                axis_y.setRange(0, max([hourly_set.at(i) for i in range(hourly_set.count())]) * 1.2 if hourly_set.count() > 0 else 10)
                self.hourly_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
                self.hourly_series.attachAxis(axis_y)
                self._style_axes(axis_x, axis_y)
            
            # ========== GRAPHIQUE 6: TAUX DE SATISFACTION (DEMANDES TRAITÉES) ==========
            self.satisfaction_rate_chart.removeAllSeries()
            self.satisfaction_rate_series = QBarSeries()
            result_rate = payload.get('result_rate', [])

            categories = ["Satisfaites", "Moyennes", "Insatisfaites"]
            rate_set = QBarSet("Taux (%)")
            rate_set.setColor(QColor(156, 39, 176))

            if result_rate:
                row = result_rate[0]
                total_traite = int(row.get('total_traite') or 0)
                satisfaites = int(row.get('satisfaites') or 0)
                moyennes = int(row.get('moyennes') or 0)
                insatisfaites = int(row.get('insatisfaites') or 0)

                if total_traite > 0:
                    rate_set.append(round((satisfaites / total_traite) * 100, 2))
                    rate_set.append(round((moyennes / total_traite) * 100, 2))
                    rate_set.append(round((insatisfaites / total_traite) * 100, 2))
                else:
                    rate_set.append(0)
                    rate_set.append(0)
                    rate_set.append(0)
            else:
                rate_set.append(0)
                rate_set.append(0)
                rate_set.append(0)

            self.satisfaction_rate_series.append(rate_set)
            self.satisfaction_rate_chart.addSeries(self.satisfaction_rate_series)

            # Supprimer les anciens axes pour éviter l'accumulation
            for axis in self.satisfaction_rate_chart.axes():
                self.satisfaction_rate_chart.removeAxis(axis)

            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            self.satisfaction_rate_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            self.satisfaction_rate_series.attachAxis(axis_x)

            axis_y = QValueAxis()
            axis_y.setRange(0, 100)
            axis_y.setLabelFormat("%.0f%%")
            self.satisfaction_rate_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            self.satisfaction_rate_series.attachAxis(axis_y)
            self._style_axes(axis_x, axis_y)
                
        except Exception as e:
            print(f"Erreur lors de la mise à jour des graphiques: {e}")
            import traceback
            traceback.print_exc()
    
    def update_statistics_table(self):
        """Met à jour la table avec des statistiques détaillées (OBSOLÈTE - remplacé par charts)"""
        # Remplacé par update_charts()
        self.update_charts()
    
    def update_all_data(self):
        """Met à jour tous les KPI et les graphiques"""
        try:
            # Rollover quotidien: en_attente des jours précédents -> non_traite
            try:
                db.rollover_pending_to_non_traite()
            except Exception as e:
                print(f"Erreur rollover quotidien dashboard: {e}")

            start_date, end_date = self._get_date_range()
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            delta_days = (end_date - start_date).days + 1
            comp_end = start_date - timedelta(days=1)
            comp_start = comp_end - timedelta(days=delta_days - 1)

            cache_key = self._build_cache_key(start_date, end_date)
            cached_payload = self._get_cached_payload(cache_key)

            if cached_payload is not None:
                self.update_kpi(cached_payload)
                self.update_charts(cached_payload)
                self._set_refresh_state("• À jour", "#0a8f2e")
                self._finalize_refresh()
                return

            args = (
                start_str,
                end_str,
                comp_start.strftime("%Y-%m-%d"),
                comp_end.strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                cache_key,
            )
            self._start_data_worker(args)
        except Exception as e:
            self._set_refresh_state("• Erreur de synchronisation", "#c62828")
            print(f"Erreur update_all_data: {e}")
            self._finalize_refresh()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DashboardPage()
    window.show()
    sys.exit(app.exec())
