"""Accueil page embedding the Show_Data UI."""

from datetime import datetime, time
from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from config import AppConfig
from database.connection import db
from .Show_Data import Ui_MainWindow


class AccueilDemandesWorker(QObject):
    """Worker Qt pour charger les demandes du jour hors thread UI."""

    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, today_str):
        super().__init__()
        self.today_str = today_str

    def run(self):
        query = f"""
        SELECT
            d.id,
            d.nom,
            d.prenom,
            d.numero_cnps,
            s.nom AS service,
            m.nom AS motif,
            d.contacts,
            d.heure_arrivee,
            d.heure_reception,
            d.temps_attente,
            d.satisfaction,
            d.priorite,
            d.date,
            d.statut,
            d.updated_at
        FROM accueil_demandeaccueil d
        LEFT JOIN accueil_service s ON d.service_demande_id = s.id
        LEFT JOIN accueil_motif m ON d.motif_id = m.id
        WHERE DATE(d.date) = ?
        ORDER BY CASE WHEN d.statut = 'en_attente' THEN 0 ELSE 1 END,
             COALESCE(d.created_at, d.updated_at, d.date) DESC
        LIMIT {AppConfig.ACCUEIL_DAILY_LIST_LIMIT}
        """
        try:
            results = db.execute_query(query, (self.today_str,))
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class TraitementDialog(QDialog):
    """Formulaire de traitement d'une demande."""

    def __init__(self, demande: dict, parent=None):
        super().__init__(parent)
        self.demande = demande
        self._action_font = parent.ui.get_data_btn.font() if parent and hasattr(parent, "ui") else self.font()
        self.setWindowTitle("Traitement de la demande")
        self.setModal(True)
        self.resize(560, 420)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        readonly_style = "background-color: #f0f0f0; color: #666666;"

        self.nom_input = QLineEdit(str(self.demande.get("nom") or ""))
        self.nom_input.setReadOnly(True)
        self.nom_input.setFont(self._action_font)
        self.nom_input.setStyleSheet(readonly_style)
        form.addRow("Nom", self.nom_input)

        self.prenom_input = QLineEdit(str(self.demande.get("prenom") or ""))
        self.prenom_input.setReadOnly(True)
        self.prenom_input.setFont(self._action_font)
        self.prenom_input.setStyleSheet(readonly_style)
        form.addRow("Prenom", self.prenom_input)

        self.cnps_input = QLineEdit(str(self.demande.get("numero_cnps") or ""))
        self.cnps_input.setReadOnly(True)
        self.cnps_input.setFont(self._action_font)
        self.cnps_input.setStyleSheet(readonly_style)
        form.addRow("N CNPS", self.cnps_input)

        self.service_input = QLineEdit(str(self.demande.get("service") or ""))
        self.service_input.setReadOnly(True)
        self.service_input.setFont(self._action_font)
        self.service_input.setStyleSheet(readonly_style)
        form.addRow("Service", self.service_input)

        self.motif_input = QLineEdit(str(self.demande.get("motif") or ""))
        self.motif_input.setReadOnly(True)
        self.motif_input.setFont(self._action_font)
        self.motif_input.setStyleSheet(readonly_style)
        form.addRow("Motif", self.motif_input)

        self.contact_input = QLineEdit(str(self.demande.get("contacts") or ""))
        self.contact_input.setReadOnly(True)
        self.contact_input.setFont(self._action_font)
        self.contact_input.setStyleSheet(readonly_style)
        form.addRow("Contact", self.contact_input)

        heure_arrivee_txt = AccueilPage._format_time_value(self.demande.get("heure_arrivee"))
        self.heure_arrivee_input = QLineEdit(heure_arrivee_txt)
        self.heure_arrivee_input.setReadOnly(True)
        self.heure_arrivee_input.setFont(self._action_font)
        self.heure_arrivee_input.setStyleSheet(readonly_style)
        form.addRow("Heure arrivee", self.heure_arrivee_input)

        self.heure_reception_input = QLineEdit(datetime.now().strftime("%H:%M:%S"))
        self.heure_reception_input.setReadOnly(True)
        self.heure_reception_input.setFont(self._action_font)
        self.heure_reception_input.setStyleSheet(readonly_style)
        form.addRow("Heure reception", self.heure_reception_input)

        self.satisfaction_input = QSpinBox()
        self.satisfaction_input.setRange(0, 5)
        self.satisfaction_input.setValue(int(self.demande.get("satisfaction") or 0))
        self.satisfaction_input.setFont(self._action_font)
        form.addRow("Satisfaction (0-5)", self.satisfaction_input)

        self.commentaire_input = QTextEdit()
        self.commentaire_input.setPlainText(str(self.demande.get("commentaire_satisfaction") or ""))
        self.commentaire_input.setMaximumHeight(90)
        self.commentaire_input.setFont(self._action_font)
        form.addRow("Commentaire", self.commentaire_input)

        root.addLayout(form)
        self.setFont(self._action_font)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def payload(self):
        reception_dt = datetime.now()
        return {
            "heure_reception": reception_dt.strftime("%H:%M:%S"),
            "satisfaction": int(self.satisfaction_input.value()),
            "commentaire_satisfaction": self.commentaire_input.toPlainText().strip(),
        }


class AccueilPage(QMainWindow):
    """Accueil page based on the designer-generated Show_Data UI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.current_user_role = None
        self._refresh_in_progress = False
        self._last_table_signature = None
        self._refresh_pending = False
        self._refresh_context = {"preserve_ui_state": False, "silent": False}
        self._reload_thread = None
        self._reload_worker = None
        self._cache_ttl_sec = AppConfig.ACCUEIL_CACHE_TTL_SEC
        self._demandes_cache = {}

        self._init_indicators()
        self._init_table()
        self._wire_actions()
        self.load_demandes()
        self._init_auto_refresh()

    def _init_auto_refresh(self):
        """Active un rafraîchissement discret de la liste des demandes."""
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._on_auto_refresh_timeout)
        self._auto_refresh_timer.start(AppConfig.AUTO_REFRESH_INTERVAL_MS)

    def _on_auto_refresh_timeout(self):
        self.load_demandes(preserve_ui_state=True, silent=True)

    def set_current_user(self, user):
        role = (user or {}).get("role")
        self.current_user_role = str(role).strip().lower() if role else None

    def _init_indicators(self):
        action_font = self.ui.get_data_btn.font()

        current_date = datetime.now().strftime('%d/%m/%Y')
        self.indicateur_jour = QLabel(
            f"Liste de demande du <span style='color:#1e88e5; text-decoration: underline;'>{current_date}</span>"
        )
        self.indicateur_jour.setFont(action_font)
        self.indicateur_jour.setStyleSheet("color: #333333;")

        self.indicateur_traite = QLabel("Traite: 0")
        self.indicateur_traite.setFont(action_font)
        self.indicateur_traite.setStyleSheet("color: #0a8f2e;")

        self.indicateur_attente = QLabel("En attente: 0")
        self.indicateur_attente.setFont(action_font)
        self.indicateur_attente.setStyleSheet("color: #d32f2f;")

        self.refresh_state_label = QLabel("• À jour")
        self.refresh_state_label.setFont(action_font)
        self.refresh_state_label.setStyleSheet("color: #0a8f2e; font-weight: 600;")

        self.refresh_spinner = QLabel("⟳")
        self.refresh_spinner.setFont(action_font)
        self.refresh_spinner.setStyleSheet("color: #1e88e5; font-weight: 700;")
        self.refresh_spinner.setVisible(False)

        # Mettre tout sur la ligne des boutons (Traitement / Actualiser), aligné à gauche
        for index in reversed(range(self.ui.horizontalLayout_2.count())):
            item = self.ui.horizontalLayout_2.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                self.ui.horizontalLayout_2.takeAt(index)

        self.ui.horizontalLayout_2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ui.horizontalLayout_2.insertWidget(0, self.indicateur_jour)
        self.ui.horizontalLayout_2.insertWidget(1, self.indicateur_traite)
        self.ui.horizontalLayout_2.insertWidget(2, self.indicateur_attente)
        self.ui.horizontalLayout_2.insertWidget(3, self.refresh_state_label)
        self.ui.horizontalLayout_2.insertWidget(4, self.refresh_spinner)

    def _init_table(self):
        self.ui.tableWidget.setColumnCount(13)
        self.ui.tableWidget.setHorizontalHeaderLabels([
            "Nom",
            "Prenom",
            "N CNPS",
            "Service",
            "Motif",
            "Contact",
            "Heure arrivee",
            "Heure reception",
            "Temps attente",
            "Satisfaction",
            "Priorite",
            "Date",
            "Statut",
        ])
        self.ui.tableWidget.setRowCount(0)
        self.ui.tableWidget.setAlternatingRowColors(True)
        self.ui.tableWidget.setSelectionBehavior(self.ui.tableWidget.SelectionBehavior.SelectRows)
        self.ui.tableWidget.setSelectionMode(self.ui.tableWidget.SelectionMode.SingleSelection)
        self.ui.tableWidget.setWordWrap(False)
        self.ui.tableWidget.verticalHeader().setVisible(False)
        self.ui.tableWidget.setHorizontalScrollMode(self.ui.tableWidget.ScrollMode.ScrollPerPixel)
        self.ui.tableWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._apply_table_column_layout()

    def _apply_table_column_layout(self):
        table = self.ui.tableWidget
        header = table.horizontalHeader()
        screen = QApplication.primaryScreen()
        available_width = screen.availableGeometry().width() if screen else 1366
        compact_mode = available_width <= 1440
        width_scale = 0.84 if compact_mode else 1.0

        header.setMinimumSectionSize(76 if compact_mode else 90)
        table.verticalHeader().setDefaultSectionSize(34 if compact_mode else 38)
        header.setStretchLastSection(False)

        for col_idx in range(table.columnCount()):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)

        column_widths = {
            0: 130,
            1: 130,
            2: 120,
            3: 140,
            4: 170,
            5: 140,
            6: 115,
            7: 125,
            8: 115,
            9: 105,
            10: 105,
            11: 105,
            12: 110,
        }

        for col_idx, width in column_widths.items():
            scaled_width = max(76 if compact_mode else 90, int(width * width_scale))
            table.setColumnWidth(col_idx, scaled_width)

    def _wire_actions(self):
        self.ui.get_data_btn.clicked.connect(self.load_demandes)
        self.ui.save_btn.clicked.connect(self.open_selected_demande)
        self.ui.tableWidget.cellDoubleClicked.connect(lambda _row, _col: self.open_selected_demande())

    def _set_refresh_state(self, text, color):
        self.refresh_state_label.setText(text)
        self.refresh_state_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _build_cache_key(self, today_str):
        return f"{today_str}::accueil"

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
        self.refresh_spinner.setVisible(False)

        if self._refresh_pending:
            self._refresh_pending = False
            ctx = dict(self._refresh_context)
            QTimer.singleShot(0, lambda: self.load_demandes(ctx.get("preserve_ui_state", True), ctx.get("silent", True)))

    def _start_reload_worker(self, today_str):
        self._reload_thread = QThread(self)
        self._reload_worker = AccueilDemandesWorker(today_str)
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

    def _apply_demandes_results(self, results, preserve_ui_state=False, silent=False):
        selected_demande_id = self._get_selected_demande_id() if preserve_ui_state else None
        scroll_value = self.ui.tableWidget.verticalScrollBar().value() if preserve_ui_state else 0

        current_signature = tuple(
            (
                r.get("id"),
                r.get("statut"),
                r.get("heure_reception"),
                r.get("temps_attente"),
                r.get("satisfaction"),
                r.get("updated_at"),
            )
            for r in results
        )
        if silent and current_signature == self._last_table_signature:
            self._set_refresh_state("• À jour", "#0a8f2e")
            return
        self._last_table_signature = current_signature

        self.ui.tableWidget.setUpdatesEnabled(False)
        try:
            self.ui.tableWidget.setRowCount(0)

            total_traite = 0
            total_attente = 0

            for row_idx, demande in enumerate(results):
                self.ui.tableWidget.insertRow(row_idx)

                demande_id = demande.get("id")
                nom = demande.get("nom")
                prenom = demande.get("prenom")
                cnps = demande.get("numero_cnps")
                service = demande.get("service")
                motif = demande.get("motif")
                contact = demande.get("contacts")
                heure = demande.get("heure_arrivee")
                heure_reception = demande.get("heure_reception")
                temps_attente = demande.get("temps_attente")
                satisfaction = demande.get("satisfaction")
                priorite = demande.get("priorite")
                date_value = demande.get("date")
                statut = demande.get("statut")

                if statut == "traite":
                    total_traite += 1
                elif statut == "en_attente":
                    total_attente += 1

                heure_text = self._format_time_value(heure)
                reception_text = self._format_time_value(heure_reception)

                row_items = [
                    nom or "-",
                    prenom or "-",
                    cnps or "-",
                    service or "-",
                    motif or "-",
                    contact or "-",
                    heure_text,
                    reception_text,
                    str(temps_attente) if temps_attente is not None else "-",
                    str(satisfaction) if satisfaction is not None else "-",
                    priorite or "-",
                    str(date_value) if date_value is not None else "-",
                    statut or "-",
                ]
                for col_idx, text in enumerate(row_items):
                    cell = QTableWidgetItem(str(text))
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col_idx == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, demande_id)
                    self.ui.tableWidget.setItem(row_idx, col_idx, cell)

                if statut == "en_attente":
                    row_bg_color = QColor(211, 47, 47, 45)
                else:
                    row_bg_color = QColor(10, 143, 46, 35)

                for col_idx in range(self.ui.tableWidget.columnCount()):
                    row_item = self.ui.tableWidget.item(row_idx, col_idx)
                    if row_item is not None:
                        row_item.setBackground(row_bg_color)

                statut_item = self.ui.tableWidget.item(row_idx, 12)
                if statut_item is not None:
                    if statut == "traite":
                        statut_item.setForeground(QColor("#0a8f2e"))
                    elif statut == "en_attente":
                        statut_item.setForeground(QColor("#d32f2f"))

            current_date = datetime.now().strftime('%d/%m/%Y')
            self.indicateur_jour.setText(
                f"Liste de demande du <span style='color:#1e88e5; text-decoration: underline;'>{current_date}</span>"
            )
            self.indicateur_traite.setText(f"Traite: {total_traite}")
            self.indicateur_attente.setText(f"En attente: {total_attente}")

            if preserve_ui_state:
                self._restore_selection_by_id(selected_demande_id)
                self.ui.tableWidget.verticalScrollBar().setValue(scroll_value)

            self._set_refresh_state("• À jour", "#0a8f2e")
        finally:
            self.ui.tableWidget.setUpdatesEnabled(True)

    def _on_reload_finished(self, results):
        try:
            today_str = datetime.now().date().isoformat()
            self._set_cached_results(today_str, results)
            self._apply_demandes_results(
                results,
                preserve_ui_state=self._refresh_context.get("preserve_ui_state", False),
                silent=self._refresh_context.get("silent", False),
            )
        finally:
            self._finalize_refresh()

    def _on_reload_failed(self, error_message):
        self._set_refresh_state("• Erreur sync", "#c62828")
        print(f"Erreur refresh accueil async: {error_message}")
        self._finalize_refresh()

    def _get_selected_demande_id(self):
        row = self.ui.tableWidget.currentRow()
        if row < 0:
            return None
        item = self.ui.tableWidget.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _restore_selection_by_id(self, demande_id):
        if not demande_id:
            return
        for row_idx in range(self.ui.tableWidget.rowCount()):
            item = self.ui.tableWidget.item(row_idx, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == demande_id:
                self.ui.tableWidget.setCurrentCell(row_idx, 0)
                return

    @staticmethod
    def _format_time_value(value):
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, str):
            return value.split("T")[1][:8] if "T" in value else value[:8]
        return str(value)

    @staticmethod
    def _parse_time_value(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                if "T" in text:
                    return datetime.fromisoformat(text.replace("Z", "+00:00")).time()
            except ValueError:
                pass
            try:
                return datetime.strptime(text[:8], "%H:%M:%S").time()
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_wait_time(arrivee_time, reception_time):
        if not arrivee_time or not reception_time:
            return None
        delta = datetime.combine(datetime.today(), reception_time) - datetime.combine(datetime.today(), arrivee_time)
        if delta.total_seconds() < 0:
            return None
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:01d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _compute_delai_objectif(wait_time):
        if not wait_time:
            return 0
        try:
            parts = str(wait_time).strip().split(":")
            if len(parts) != 3:
                return 0
            hours, minutes, seconds = map(int, parts)
            total_seconds = (hours * 3600) + (minutes * 60) + seconds
            return 1 if total_seconds < 900 else 0
        except (TypeError, ValueError):
            return 0

    def open_selected_demande(self):
        row = self.ui.tableWidget.currentRow()
        if row < 0:
            QMessageBox.information(self, "Traitement", "Selectionne une ligne d'abord.")
            return

        statut_item = self.ui.tableWidget.item(row, 12)
        statut_selectionne = (statut_item.text().strip().lower() if statut_item and statut_item.text() else "")
        if self.current_user_role == "accueil" and statut_selectionne == "traite":
            QMessageBox.information(
                self,
                "Traitement verrouille",
                "Cette ligne est deja traitee et ne peut plus etre modifiee par l'agent d'accueil.",
            )
            return

        row_id_item = self.ui.tableWidget.item(row, 0)
        if row_id_item is None:
            return
        demande_id = row_id_item.data(Qt.ItemDataRole.UserRole)
        if not demande_id:
            return

        details = db.execute_query(
            """
            SELECT d.id, d.nom, d.prenom, d.numero_cnps, d.contacts,
                   d.heure_arrivee, d.satisfaction, d.commentaire_satisfaction,
                   d.statut, s.nom AS service, m.nom AS motif
            FROM accueil_demandeaccueil d
            LEFT JOIN accueil_service s ON d.service_demande_id = s.id
            LEFT JOIN accueil_motif m ON d.motif_id = m.id
            WHERE d.id = ?
            """,
            (demande_id,),
        )
        if not details:
            QMessageBox.warning(self, "Traitement", "Demande introuvable.")
            return

        demande = details[0]
        if self.current_user_role == "accueil" and str(demande.get("statut") or "").strip().lower() == "traite":
            QMessageBox.information(
                self,
                "Traitement verrouille",
                "Cette ligne est deja traitee et ne peut plus etre modifiee par l'agent d'accueil.",
            )
            return

        dialog = TraitementDialog(demande, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.payload()
        heure_reception = payload["heure_reception"]
        arrivee_time = self._parse_time_value(demande.get("heure_arrivee"))
        reception_time = self._parse_time_value(heure_reception)
        temps_attente = self._format_wait_time(arrivee_time, reception_time)
        delai_objectif = self._compute_delai_objectif(temps_attente)

        db.execute_update(
            """
            UPDATE accueil_demandeaccueil
            SET heure_reception = ?,
                satisfaction = ?,
                commentaire_satisfaction = ?,
                temps_attente = ?,
                delai_objectif = ?,
                statut = 'traite',
                updated_at = ?
            WHERE id = ?
            """,
            (
                heure_reception,
                payload["satisfaction"],
                payload["commentaire_satisfaction"],
                temps_attente,
                delai_objectif,
                datetime.now().isoformat(),
                demande_id,
            ),
        )
        self._demandes_cache.clear()
        self.load_demandes()

    def load_demandes(self, preserve_ui_state=False, silent=False):
        """Charge les demandes enregistrees par le preaccueil."""
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
        self.refresh_spinner.setVisible(True)
        self._set_refresh_state("• Synchronisation...", "#1e88e5")
        today_str = datetime.now().date().isoformat()

        cached_results = self._get_cached_results(today_str)
        if cached_results is not None:
            try:
                self._apply_demandes_results(cached_results, preserve_ui_state=preserve_ui_state, silent=silent)
            finally:
                self._finalize_refresh()
            return

        try:
            self._start_reload_worker(today_str)
        except Exception as e:
            self._set_refresh_state("• Erreur sync", "#c62828")
            print(f"Erreur lancement refresh accueil: {e}")
            self._finalize_refresh()

    def closeEvent(self, event):
        timer = getattr(self, "_auto_refresh_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

        thread = getattr(self, "_reload_thread", None)
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1500)

        super().closeEvent(event)
