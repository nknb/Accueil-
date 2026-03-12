"""Wrapper for PreAccueil widget using Show_Data UI structure."""

from datetime import datetime
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QMainWindow,
    QWidget,
    QMessageBox,
    QHeaderView,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal

from config import AppConfig
from .Show_Data import Ui_MainWindow
from database.connection import db
from database.models import DemandeAccueil
from utils import app_logger


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
        
        # Setup UI from Show_Data
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Customize for PreAccueil
        self.setWindowTitle("📋 Enregistrement Pré-Accueil")
        self.ui.label_2.setText("Formulaire Enregistrement Pré-Accueil")
        
        # Hide entire widget containing buttons (not needed for preaccueil)
        self.ui.widget.hide()
        
        # Setup table columns for PreAccueil
        self.ui.tableWidget.setColumnCount(8)
        self.ui.tableWidget.setHorizontalHeaderLabels([
            "Nom", "Prénom", "N° CNPS", "Service", "Motif", "Contact", "Heure d'arrivée", "Statut"
        ])
        self._setup_modern_table()
        
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
        self.ui.tableWidget.setUpdatesEnabled(False)
        try:
            self.ui.tableWidget.setRowCount(0)

            for row_idx, demande in enumerate(results):
                self.ui.tableWidget.insertRow(row_idx)

                nom = demande.get('nom') or "—"
                prenom = demande.get('prenom') or "—"
                cnps = demande.get('numero_cnps') or "—"
                service = demande.get('service') or "—"
                motif = demande.get('motif') or "—"
                contact = demande.get('contacts') or "—"
                heure = demande.get('heure_arrivee')
                statut = demande.get('statut') or "en_attente"

                if isinstance(heure, str):
                    heure = heure.split('T')[1][:8] if 'T' in heure else heure[:8]

                items = [
                    nom,
                    prenom,
                    cnps,
                    service,
                    motif,
                    contact,
                    heure or "—",
                    statut,
                ]

                for col_idx, item_text in enumerate(items):
                    cell = QTableWidgetItem(str(item_text))
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col_idx == 7:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        if str(item_text).strip().lower() == "en_attente":
                            cell.setForeground(QColor("#d32f2f"))
                        else:
                            cell.setForeground(QColor("#0a8f2e"))
                    self.ui.tableWidget.setItem(row_idx, col_idx, cell)

                row_bg_color = QColor(211, 47, 47, 45) if statut == "en_attente" else QColor(10, 143, 46, 35)
                for col_idx in range(self.ui.tableWidget.columnCount()):
                    row_item = self.ui.tableWidget.item(row_idx, col_idx)
                    if row_item is not None:
                        row_item.setBackground(row_bg_color)

            self._set_refresh_state("• À jour", "#0a8f2e")
            app_logger.info(f"Demandes chargées: {len(results)}")
        finally:
            self.ui.tableWidget.setUpdatesEnabled(True)

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

    def _setup_modern_table(self):
        """Applique un style moderne et lisible à la table des demandes."""
        table = self.ui.tableWidget
        header = table.horizontalHeader()
        screen = table.screen()
        available_width = screen.availableGeometry().width() if screen else 1366
        compact_mode = available_width <= 1440

        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34 if compact_mode else 38)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header.setHighlightSections(False)
        header.setMinimumSectionSize(76 if compact_mode else 90)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for col_idx in range(table.columnCount()):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)

        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Service
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Motif
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Contact

        width_scale = 0.86 if compact_mode else 1.0
        table.setColumnWidth(0, int(130 * width_scale))
        table.setColumnWidth(1, int(130 * width_scale))
        table.setColumnWidth(2, int(120 * width_scale))
        table.setColumnWidth(6, int(130 * width_scale))
        table.setColumnWidth(7, int(120 * width_scale))

        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 10px;
                color: #000000;
                gridline-color: #d0d0d0;
                selection-background-color: #e3f2fd;
                selection-color: #000000;
                padding: 4px;
            }
            QTableWidget::item {
                padding: 8px 6px;
            }
            QHeaderView::section {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                padding: 10px 8px;
            }
            QTableCornerButton::section {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

    def create_input_form(self):
        """Create the input form above the table."""
        # Create a container for the form
        form_widget = QWidget()
        form_widget.setObjectName("preaccueilFormCard")
        form_widget.setMaximumWidth(980)
        form_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(16, 14, 16, 14)
        form_layout.setSpacing(12)
        
        # Form title + état de synchro
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)

        title = QLabel("👤 Informations de la Demande")
        title.setObjectName("preaccueilFormTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        self.refresh_state_label = QLabel("• À jour")
        self.refresh_spinner = QLabel("⟳")

        title_row.addWidget(self.refresh_state_label)
        title_row.addWidget(self.refresh_spinner)

        form_layout.addLayout(title_row)

        base_font = self.ui.get_data_btn.font()

        def _apply_accueil_typography(widget):
            widget_font = widget.font()
            widget_font.setFamily(base_font.family())
            widget_font.setBold(base_font.bold())
            widget_font.setItalic(base_font.italic())
            widget.setFont(widget_font)

        _apply_accueil_typography(title)
        
        # Form grid
        form_group = QGroupBox()
        form_group.setObjectName("preaccueilFormGroup")
        grid_layout = QGridLayout(form_group)
        grid_layout.setHorizontalSpacing(12)
        grid_layout.setVerticalSpacing(10)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 2)
        grid_layout.setColumnStretch(2, 1)
        grid_layout.setColumnStretch(3, 2)
        
        # Row 1: N° CNPS
        self.input_cnps = QLineEdit()
        self.input_cnps.setPlaceholderText("ex: 123456789 (optionnel)")
        self.input_cnps.setMinimumHeight(38)
        label_cnps = QLabel("N° CNPS:")
        grid_layout.addWidget(label_cnps, 0, 0)
        grid_layout.addWidget(self.input_cnps, 0, 1, 1, 3)
        
        # Row 2: Nom & Prénom
        self.input_nom = QLineEdit()
        self.input_nom.setPlaceholderText("ex: Dupont")
        self.input_nom.setMinimumHeight(38)
        self.input_prenom = QLineEdit()
        self.input_prenom.setPlaceholderText("ex: Jean")
        self.input_prenom.setMinimumHeight(38)
        label_nom = QLabel("Nom:")
        grid_layout.addWidget(label_nom, 1, 0)
        grid_layout.addWidget(self.input_nom, 1, 1)
        label_prenom = QLabel("Prénom:")
        grid_layout.addWidget(label_prenom, 1, 2)
        grid_layout.addWidget(self.input_prenom, 1, 3)
        
        # Row 3: Service & Motif
        self.combo_service = QComboBox()
        self.combo_service.addItem("-- Sélectionner un service --")
        self.combo_service.setMinimumHeight(38)
        self.combo_motif = QComboBox()
        self.combo_motif.addItem("-- Sélectionner un motif --")
        self.combo_motif.setMinimumHeight(38)
        label_service = QLabel("Service demandé:")
        grid_layout.addWidget(label_service, 2, 0)
        grid_layout.addWidget(self.combo_service, 2, 1)
        label_motif = QLabel("Motif:")
        grid_layout.addWidget(label_motif, 2, 2)
        grid_layout.addWidget(self.combo_motif, 2, 3)
        
        # Row 4: Contact & Heure d'arrivée
        self.input_contact = QLineEdit()
        self.input_contact.setPlaceholderText("Numéro téléphone ou email")
        self.input_contact.setMinimumHeight(38)
        self.label_heure_arrivee = QLineEdit()
        self.label_heure_arrivee.setReadOnly(True)
        self.label_heure_arrivee.setPlaceholderText("Heure d'arrivée automatique")
        self.label_heure_arrivee.setMinimumHeight(38)
        label_contact = QLabel("Contact:")
        grid_layout.addWidget(label_contact, 3, 0)
        grid_layout.addWidget(self.input_contact, 3, 1)
        label_heure = QLabel("Heure d'arrivée:")
        grid_layout.addWidget(label_heure, 3, 2)
        grid_layout.addWidget(self.label_heure_arrivee, 3, 3)

        for field_widget in [
            self.input_cnps,
            self.input_nom,
            self.input_prenom,
            self.combo_service,
            self.combo_motif,
            self.input_contact,
            self.label_heure_arrivee,
            label_cnps,
            label_nom,
            label_prenom,
            label_service,
            label_motif,
            label_contact,
            label_heure,
            self.refresh_state_label,
            self.refresh_spinner,
        ]:
            _apply_accueil_typography(field_widget)

        self.refresh_state_label.setStyleSheet("color: #0a8f2e; font-weight: 600;")
        self.refresh_spinner.setStyleSheet("color: #1e88e5; font-weight: 700;")
        self.refresh_spinner.setVisible(False)

        for row in range(4):
            label_left = grid_layout.itemAtPosition(row, 0).widget()
            label_right = grid_layout.itemAtPosition(row, 2).widget() if row > 0 else None
            if isinstance(label_left, QLabel):
                label_left.setObjectName("preaccueilFieldLabel")
            if isinstance(label_right, QLabel):
                label_right.setObjectName("preaccueilFieldLabel")
        
        form_layout.addWidget(form_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.btn_enregistrer = QPushButton("💾 Enregistrer")
        self.btn_enregistrer.setObjectName("preaccueilPrimaryBtn")
        self.btn_enregistrer.setMinimumHeight(38)
        _apply_accueil_typography(self.btn_enregistrer)
        
        self.btn_effacer = QPushButton("🗑️ Effacer")
        self.btn_effacer.setObjectName("preaccueilSecondaryBtn")
        self.btn_effacer.setMinimumHeight(38)
        _apply_accueil_typography(self.btn_effacer)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_enregistrer)
        buttons_layout.addWidget(self.btn_effacer)
        buttons_layout.addStretch()
        
        form_layout.addLayout(buttons_layout)
        
        # Insert form at the beginning of the table's parent layout
        # Find the groupBox_2 which contains the table
        parent_layout = self.ui.centralwidget.layout()
        parent_layout.insertWidget(2, form_widget, alignment=Qt.AlignmentFlag.AlignHCenter)  # Insert before table group

        form_widget.setStyleSheet("""
            QWidget#preaccueilFormCard {
                background-color: rgba(255, 255, 255, 242);
                border: 1px solid #dce4ee;
                border-radius: 12px;
            }
            QLabel#preaccueilFormTitle {
                color: #1f2937;
                padding: 2px 2px 6px 2px;
            }
            QGroupBox#preaccueilFormGroup {
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                background-color: #ffffff;
                margin-top: 4px;
            }
            QLabel#preaccueilFieldLabel {
                color: #334155;
            }
            QLineEdit, QComboBox {
                border: 1px solid #cfd8e3;
                border-radius: 8px;
                padding: 7px 10px;
                background-color: #ffffff;
                color: #1e293b;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #42a5f5;
                background-color: #f8fbff;
            }
            QLineEdit[readOnly="true"] {
                background-color: #f8fafc;
                color: #64748b;
            }
            QPushButton#preaccueilPrimaryBtn {
                background-color: #0a8f2e;
                color: white;
                border: 1px solid #0a8f2e;
                border-radius: 8px;
                padding: 0 14px;
            }
            QPushButton#preaccueilPrimaryBtn:hover {
                background-color: #087625;
            }
            QPushButton#preaccueilSecondaryBtn {
                background-color: #d32f2f;
                color: white;
                border: 1px solid #d32f2f;
                border-radius: 8px;
                padding: 0 14px;
            }
            QPushButton#preaccueilSecondaryBtn:hover {
                background-color: #b71c1c;
            }
        """)
        
        # Update heure d'arrivée automatically
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
        """Update arrival time automatically."""
        now = datetime.now()
        heure_str = now.strftime("%H:%M:%S")
        self.label_heure_arrivee.setText(heure_str)

    def enregistrer_demande(self):
        """Save demand to database."""
        # Validation
        nom = self.input_nom.text().strip()
        prenom = self.input_prenom.text().strip()
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
                QMessageBox.information(self, "Succès", "✅ Demande enregistrée avec succès!")
                self.effacer_formulaire()
                self._demandes_cache.clear()
                self.load_demandes()
                app_logger.info(f"Demande enregistrée: {demande.id} - {nom} {prenom}")
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
