"""Database page embedding the new Show_Data UI."""

from datetime import datetime
from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from config import AppConfig
from database.connection import db
from .Show_Data import Ui_MainWindow


class DatabaseReloadWorker(QObject):
    """Worker de rechargement DB hors thread UI."""

    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, table_name):
        super().__init__()
        self.table_name = table_name

    def run(self):
        try:
            columns_info = db.execute_query(f"PRAGMA table_info({self.table_name})")
            columns = [col.get("name") for col in columns_info]
            query = f"""
                SELECT *
                FROM {self.table_name}
                ORDER BY
                    COALESCE(updated_at, created_at, date) DESC,
                    id DESC
            """
            records = db.execute_query(query)
            payload = {
                "columns": columns,
                "records": records,
            }
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))


class DatabaseRecordDialog(QDialog):
    """Formulaire générique pour créer/modifier un enregistrement."""

    def __init__(self, columns_info, initial_values=None, mode="create", parent=None):
        super().__init__(parent)
        self.columns_info = columns_info or []
        self.initial_values = initial_values or {}
        self.mode = mode
        self._editors = {}

        title = "Créer un enregistrement" if mode == "create" else "Modifier l'enregistrement"
        self.setWindowTitle(title)
        self.resize(620, 560)
        self._build_ui()

    @staticmethod
    def _normalize_default(raw_default):
        if raw_default is None:
            return ""
        text = str(raw_default).strip()
        if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
            return text[1:-1]
        return text

    def _initial_value_for(self, col_name, default_value):
        if col_name in self.initial_values:
            value = self.initial_values.get(col_name)
            return "" if value is None else str(value)

        if self.mode == "create":
            if col_name == "date":
                return datetime.now().date().isoformat()
            if col_name in {"heure_arrivee", "heure_reception"}:
                return datetime.now().strftime("%H:%M:%S")
            if col_name == "statut":
                return "en_attente"
            if col_name == "priorite":
                return "normale"

        return self._normalize_default(default_value)

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()

        excluded = {"id", "created_at", "updated_at"}
        for col in self.columns_info:
            col_name = col.get("name")
            if not col_name or col_name in excluded:
                continue

            col_type = str(col.get("type") or "").upper()
            default_value = col.get("dflt_value")
            initial_text = self._initial_value_for(col_name, default_value)

            if col_name in {"commentaire_satisfaction"} or "TEXT" in col_type:
                editor = QTextEdit()
                editor.setMaximumHeight(90)
                editor.setPlainText(initial_text)
            else:
                editor = QLineEdit(initial_text)

            required = bool(col.get("notnull", 0)) and col.get("dflt_value") is None
            label = f"{col_name}{' *' if required else ''}"
            form.addRow(label, editor)
            self._editors[col_name] = editor

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def payload(self):
        data = {}
        for col_name, editor in self._editors.items():
            if isinstance(editor, QTextEdit):
                text = editor.toPlainText().strip()
            else:
                text = editor.text().strip()
            data[col_name] = text if text != "" else None
        return data


class DatabasePage(QMainWindow):
    """Database page based on the designer-generated Show_Data UI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.table_name = "accueil_demandeaccueil"
        self.all_records = []
        self.all_columns = []
        self.filtered_records = []
        self.current_page = 1
        self.items_per_page = 20
        self.total_pages = 1
        self._refresh_in_progress = False
        self._last_records_signature = None
        self._refresh_pending = False
        self._reload_thread = None
        self._reload_worker = None
        self._cache_ttl_sec = AppConfig.DATABASE_CACHE_TTL_SEC
        self._records_cache = {}

        self._init_ui()
        self._add_search_bar()
        self._wire_actions()
        self.load_full_database_table()
        self._init_auto_refresh()

    def _init_auto_refresh(self):
        """Active un rafraîchissement discret de la table base de données."""
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._on_auto_refresh_timeout)
        self._auto_refresh_timer.start(AppConfig.AUTO_REFRESH_INTERVAL_MS)

    def _on_auto_refresh_timeout(self):
        self.refresh_database_discreet()

    def _set_refresh_state(self, text, color):
        self.refresh_state_label.setText(text)
        self.refresh_state_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _build_cache_key(self):
        return f"{self.table_name}::full"

    def _get_cached_payload(self):
        entry = self._records_cache.get(self._build_cache_key())
        if not entry:
            return None
        ts = entry.get("ts")
        payload = entry.get("payload")
        if not ts or not payload:
            return None
        if (datetime.now() - ts).total_seconds() > self._cache_ttl_sec:
            return None
        return payload

    def _set_cached_payload(self, payload):
        self._records_cache[self._build_cache_key()] = {
            "ts": datetime.now(),
            "payload": payload,
        }

    def _finalize_refresh(self):
        self._refresh_in_progress = False
        self.spinner.setVisible(False)

        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_database_discreet)

    def _start_reload_worker(self):
        self._reload_thread = QThread(self)
        self._reload_worker = DatabaseReloadWorker(self.table_name)
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

    def _apply_reload_payload(self, payload):
        selected_key = self._get_selected_key()
        current_scroll = self.ui.tableWidget.verticalScrollBar().value()
        current_page = self.current_page
        current_search = self.search_input.text()

        new_columns = payload.get("columns") or []
        new_records = payload.get("records") or []

        if not new_columns:
            self.all_columns = []
            self.all_records = []
            self.filtered_records = []
            return

        new_signature = self._compute_records_signature(new_records)
        if new_signature == self._last_records_signature:
            self._set_refresh_state("• À jour", "#0a8f2e")
            return

        self.all_columns = new_columns
        self.all_records = new_records
        self._last_records_signature = new_signature

        current_sort_col = self.sort_column_combo.currentData()
        self.sort_column_combo.blockSignals(True)
        self.sort_column_combo.clear()
        for col in self.all_columns:
            self.sort_column_combo.addItem(col, col)

        preferred_column = None
        if current_sort_col in self.all_columns:
            preferred_column = current_sort_col
        else:
            for candidate in ("updated_at", "created_at", "date", "id"):
                if candidate in self.all_columns:
                    preferred_column = candidate
                    break
        if preferred_column is not None:
            self.sort_column_combo.setCurrentIndex(self.all_columns.index(preferred_column))
        self.sort_column_combo.blockSignals(False)

        self.ui.tableWidget.setUpdatesEnabled(False)
        self.search_input.setText(current_search)
        self.current_page = current_page
        self.perform_search(reset_page=False, show_spinner=False)
        self._restore_selected_key(selected_key)
        self.ui.tableWidget.verticalScrollBar().setValue(current_scroll)
        self.ui.tableWidget.setUpdatesEnabled(True)

        self._set_refresh_state("• À jour", "#0a8f2e")

    def _on_reload_finished(self, payload):
        try:
            self._set_cached_payload(payload)
            self._apply_reload_payload(payload)
        finally:
            self._finalize_refresh()

    def _on_reload_failed(self, error_message):
        self._set_refresh_state("• Erreur sync", "#c62828")
        print(f"Erreur refresh DB async: {error_message}")
        self._finalize_refresh()

    def _add_search_bar(self):
        """Ajoute la barre de recherche, spinner et pagination."""
        self.ui.save_btn.hide()  # Bouton Exporter non utilisé

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.setMaximumWidth(200)
        self.ui.horizontalLayout_2.insertWidget(0, self.search_input)

        self.search_btn = self.ui.get_data_btn
        self.search_btn.setText("Recherche")
        self.search_btn.setMaximumWidth(100)
        self.ui.horizontalLayout_2.insertWidget(1, self.search_btn)

        self.sort_column_combo = QComboBox()
        self.sort_column_combo.setMaximumWidth(150)
        self.sort_column_combo.setPlaceholderText("Trier par")
        self.ui.horizontalLayout_2.insertWidget(2, self.sort_column_combo)

        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItem("⬇ Desc", "desc")
        self.sort_order_combo.addItem("⬆ Asc", "asc")
        self.sort_order_combo.setMaximumWidth(90)
        self.ui.horizontalLayout_2.insertWidget(3, self.sort_order_combo)

        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setMaximumWidth(60)
        self.spinner.setVisible(False)
        self.ui.horizontalLayout_2.insertWidget(4, self.spinner)

        self.refresh_state_label = QLabel("• À jour")
        self.refresh_state_label.setStyleSheet("color: #0a8f2e; font-weight: 600;")
        self.ui.horizontalLayout_2.insertWidget(5, self.refresh_state_label)

        self.items_combo = QComboBox()
        self.items_combo.addItems(["20", "50", "100", "Tous"])
        self.items_combo.setMaximumWidth(80)
        self.ui.horizontalLayout_2.insertWidget(6, self.items_combo)

        self.pagination_label = QLabel("Page 1/1")
        self.pagination_label.setMaximumWidth(70)
        self.ui.horizontalLayout_2.insertWidget(7, self.pagination_label)

        self.btn_first = QPushButton("<<")
        self.btn_first.setMaximumWidth(35)
        self.ui.horizontalLayout_2.insertWidget(8, self.btn_first)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setMaximumWidth(35)
        self.ui.horizontalLayout_2.insertWidget(9, self.btn_prev)

        self.btn_next = QPushButton(">")
        self.btn_next.setMaximumWidth(35)
        self.ui.horizontalLayout_2.insertWidget(10, self.btn_next)

        self.btn_last = QPushButton(">>")
        self.btn_last.setMaximumWidth(35)
        self.ui.horizontalLayout_2.insertWidget(11, self.btn_last)

        self.btn_update = QPushButton("Modifier")
        self.btn_update.setMaximumWidth(95)
        self.ui.horizontalLayout_2.insertWidget(12, self.btn_update)

        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.setMaximumWidth(95)
        self.ui.horizontalLayout_2.insertWidget(13, self.btn_delete)

    def _init_ui(self):
        self.ui.tableWidget.setRowCount(0)
        self.ui.tableWidget.setColumnCount(0)
        self.ui.tableWidget.setEditTriggers(self.ui.tableWidget.EditTrigger.NoEditTriggers)
        self.ui.tableWidget.setAlternatingRowColors(True)
        self.ui.tableWidget.setSelectionBehavior(self.ui.tableWidget.SelectionBehavior.SelectRows)
        self.ui.tableWidget.setWordWrap(False)
        self.ui.tableWidget.verticalHeader().setVisible(False)
        self.ui.tableWidget.setHorizontalScrollMode(self.ui.tableWidget.ScrollMode.ScrollPerPixel)
        self.ui.tableWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header = self.ui.tableWidget.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(76 if self._is_compact_screen() else 90)
        self.ui.tableWidget.verticalHeader().setDefaultSectionSize(34 if self._is_compact_screen() else 38)
        self.ui.tableWidget.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                color: #000000;
                gridline-color: #d0d0d0;
                selection-background-color: #e3f2fd;
                selection-color: #000000;
            }
            QHeaderView::section {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                padding: 6px;
            }
            """
        )

    def _is_compact_screen(self):
        screen = self.ui.tableWidget.screen()
        available_width = screen.availableGeometry().width() if screen else 1366
        return available_width <= 1440

    def _compact_columns(self):
        """Réduit les colonnes pour tenir un maximum dans la largeur disponible."""
        table = self.ui.tableWidget
        header = table.horizontalHeader()

        if table.columnCount() == 0:
            return

        table.resizeColumnsToContents()

        compact_mode = self._is_compact_screen()
        min_width = 68 if compact_mode else 70
        max_width = 135 if compact_mode else 160
        status_width = 100 if compact_mode else 110
        id_width = 80 if compact_mode else 90

        for col_idx in range(table.columnCount()):
            column_name = (table.horizontalHeaderItem(col_idx).text().lower() if table.horizontalHeaderItem(col_idx) else "")
            current_width = table.columnWidth(col_idx)
            target_width = max(min_width, min(current_width, max_width))

            if column_name in {"id", "uuid"}:
                target_width = id_width
            elif column_name == "statut":
                target_width = status_width

            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(col_idx, target_width)

    def _wire_actions(self):
        self.search_btn.clicked.connect(self.perform_search)
        self.search_input.returnPressed.connect(self.perform_search)
        self.sort_column_combo.currentTextChanged.connect(self.perform_search)
        self.sort_order_combo.currentTextChanged.connect(self.perform_search)
        self.items_combo.currentTextChanged.connect(self.on_items_per_page_changed)
        self.btn_first.clicked.connect(self.goto_first_page)
        self.btn_prev.clicked.connect(self.goto_prev_page)
        self.btn_next.clicked.connect(self.goto_next_page)
        self.btn_last.clicked.connect(self.goto_last_page)
        self.btn_update.clicked.connect(self.update_selected_record)
        self.btn_delete.clicked.connect(self.delete_selected_record)

    def _get_columns_info(self):
        return db.execute_query(f"PRAGMA table_info({self.table_name})")

    def _get_selected_record(self):
        row = self.ui.tableWidget.currentRow()
        if row < 0:
            return None
        start_idx = (self.current_page - 1) * self.items_per_page
        record_idx = start_idx + row
        if record_idx < 0 or record_idx >= len(self.filtered_records):
            return None
        return self.filtered_records[record_idx]

    def _invalidate_and_refresh(self):
        self._records_cache.clear()
        self.refresh_database_discreet()

    @staticmethod
    def _is_required_without_default(col):
        return bool(col.get("notnull", 0)) and col.get("dflt_value") is None and not bool(col.get("pk", 0))

    def create_record(self):
        columns_info = self._get_columns_info()
        if not columns_info:
            QMessageBox.warning(self, "CRUD", "Impossible de lire la structure de table.")
            return

        dialog = DatabaseRecordDialog(columns_info, mode="create", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.payload()

        if "created_at" in [c.get("name") for c in columns_info]:
            payload["created_at"] = datetime.now().isoformat()
        if "updated_at" in [c.get("name") for c in columns_info]:
            payload["updated_at"] = datetime.now().isoformat()

        missing_required = []
        for col in columns_info:
            col_name = col.get("name")
            if not col_name or col_name == "id":
                continue
            if self._is_required_without_default(col) and payload.get(col_name) in (None, ""):
                missing_required.append(col_name)

        if missing_required:
            QMessageBox.warning(
                self,
                "CRUD - Création",
                "Champs obligatoires manquants: " + ", ".join(missing_required),
            )
            return

        insert_cols = []
        insert_values = []
        for col_name, value in payload.items():
            if value is not None:
                insert_cols.append(col_name)
                insert_values.append(value)

        if not insert_cols:
            QMessageBox.warning(self, "CRUD - Création", "Aucune valeur à insérer.")
            return

        placeholders = ", ".join(["?"] * len(insert_cols))
        query = f"INSERT INTO {self.table_name} ({', '.join(insert_cols)}) VALUES ({placeholders})"

        try:
            db.execute_insert(query, tuple(insert_values))
            self._invalidate_and_refresh()
            QMessageBox.information(self, "CRUD", "Enregistrement créé avec succès.")
        except Exception as exc:
            QMessageBox.critical(self, "CRUD - Création", f"Échec de création: {exc}")

    def update_selected_record(self):
        selected = self._get_selected_record()
        if not selected:
            QMessageBox.information(self, "CRUD", "Sélectionnez une ligne à modifier.")
            return

        if "id" not in selected:
            QMessageBox.warning(self, "CRUD", "Impossible de modifier: colonne 'id' absente.")
            return

        columns_info = self._get_columns_info()
        dialog = DatabaseRecordDialog(columns_info, initial_values=selected, mode="update", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.payload()
        if "updated_at" in [c.get("name") for c in columns_info]:
            payload["updated_at"] = datetime.now().isoformat()

        set_parts = []
        set_values = []
        for col_name, value in payload.items():
            if col_name == "id":
                continue
            set_parts.append(f"{col_name} = ?")
            set_values.append(value)

        if not set_parts:
            QMessageBox.information(self, "CRUD", "Aucune modification à enregistrer.")
            return

        set_values.append(selected.get("id"))
        query = f"UPDATE {self.table_name} SET {', '.join(set_parts)} WHERE id = ?"

        try:
            affected = db.execute_update(query, tuple(set_values))
            if affected <= 0:
                QMessageBox.warning(self, "CRUD - Modification", "Aucune ligne modifiée.")
                return
            self._invalidate_and_refresh()
            QMessageBox.information(self, "CRUD", "Enregistrement modifié avec succès.")
        except Exception as exc:
            QMessageBox.critical(self, "CRUD - Modification", f"Échec de modification: {exc}")

    def delete_selected_record(self):
        selected = self._get_selected_record()
        if not selected:
            QMessageBox.information(self, "CRUD", "Sélectionnez une ligne à supprimer.")
            return

        if "id" not in selected:
            QMessageBox.warning(self, "CRUD", "Impossible de supprimer: colonne 'id' absente.")
            return

        selected_id = selected.get("id")
        confirm = QMessageBox.question(
            self,
            "CRUD - Suppression",
            f"Confirmer la suppression de l'enregistrement ID={selected_id} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            affected = db.execute_update(f"DELETE FROM {self.table_name} WHERE id = ?", (selected_id,))
            if affected <= 0:
                QMessageBox.warning(self, "CRUD - Suppression", "Aucune ligne supprimée.")
                return
            self._invalidate_and_refresh()
            QMessageBox.information(self, "CRUD", "Enregistrement supprimé avec succès.")
        except Exception as exc:
            QMessageBox.critical(self, "CRUD - Suppression", f"Échec de suppression: {exc}")

    @staticmethod
    def _parse_sort_value(value):
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        # Date/DateTime ISO
        try:
            return (0, datetime.fromisoformat(text.replace("Z", "+00:00")))
        except Exception:
            pass

        # Date simple
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return (1, datetime.strptime(text, fmt))
            except Exception:
                continue

        # Heure
        try:
            return (2, datetime.strptime(text[:8], "%H:%M:%S"))
        except Exception:
            pass

        # Numérique
        try:
            return (3, int(text))
        except Exception:
            pass
        try:
            return (4, float(text))
        except Exception:
            pass

        return (5, text.lower())

    def _apply_order_filter(self):
        sort_column = self.sort_column_combo.currentData()
        sort_order = self.sort_order_combo.currentData() or "desc"

        if not sort_column:
            return

        sortable = []
        empty_values = []
        for record in self.filtered_records:
            parsed = self._parse_sort_value(record.get(sort_column))
            if parsed is None:
                empty_values.append(record)
            else:
                sortable.append((parsed, record))

        sortable.sort(key=lambda item: item[0], reverse=(sort_order == "desc"))
        self.filtered_records = [record for _, record in sortable] + empty_values

    def _get_table_columns(self):
        columns_info = db.execute_query(f"PRAGMA table_info({self.table_name})")
        return [col.get("name") for col in columns_info]

    def on_items_per_page_changed(self, value):
        """Change le nombre d'éléments par page."""
        if value == "Tous":
            self.items_per_page = len(self.all_records)
        else:
            self.items_per_page = int(value)
        self.current_page = 1
        self.perform_search()

    def perform_search(self, reset_page=True, show_spinner=True):
        """Effectue la recherche sur toutes les colonnes avec pagination."""
        if show_spinner:
            self.spinner.setVisible(True)
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            self.filtered_records = self.all_records
        else:
            filtered_records = []
            for record in self.all_records:
                for column in self.all_columns:
                    value = record.get(column)
                    if value is not None:
                        if search_text in str(value).lower():
                            filtered_records.append(record)
                            break
            self.filtered_records = filtered_records

        self._apply_order_filter()

        if reset_page:
            self.current_page = 1
        self.total_pages = max(1, (len(self.filtered_records) + self.items_per_page - 1) // self.items_per_page)
        self.current_page = min(max(1, self.current_page), self.total_pages)
        self._update_pagination_display()
        if show_spinner:
            self.spinner.setVisible(False)

    def _compute_records_signature(self, records):
        signature = []
        for record in records:
            signature.append(
                (
                    record.get("id"),
                    record.get("updated_at"),
                    record.get("statut"),
                    record.get("temps_attente"),
                    record.get("heure_reception"),
                    record.get("satisfaction"),
                )
            )
        return tuple(signature)

    def _get_selected_key(self):
        row = self.ui.tableWidget.currentRow()
        if row < 0:
            return None
        id_col = self.all_columns.index("id") if "id" in self.all_columns else 0
        item = self.ui.tableWidget.item(row, id_col)
        return item.text() if item else None

    def _restore_selected_key(self, selected_key):
        if not selected_key:
            return
        id_col = self.all_columns.index("id") if "id" in self.all_columns else 0
        for row in range(self.ui.tableWidget.rowCount()):
            item = self.ui.tableWidget.item(row, id_col)
            if item and item.text() == selected_key:
                self.ui.tableWidget.setCurrentCell(row, id_col)
                return

    def _reload_all_records(self):
        self.all_columns = self._get_table_columns()
        if not self.all_columns:
            self.all_records = []
            self.filtered_records = []
            return False

        # Initialiser/rafraîchir le filtre d'ordre par colonne (sans casser les choix utilisateur)
        current_sort_col = self.sort_column_combo.currentData()
        self.sort_column_combo.blockSignals(True)
        self.sort_column_combo.clear()
        for col in self.all_columns:
            self.sort_column_combo.addItem(col, col)

        preferred_column = None
        if current_sort_col in self.all_columns:
            preferred_column = current_sort_col
        else:
            for candidate in ("updated_at", "created_at", "date", "id"):
                if candidate in self.all_columns:
                    preferred_column = candidate
                    break
        if preferred_column is not None:
            self.sort_column_combo.setCurrentIndex(self.all_columns.index(preferred_column))
        self.sort_column_combo.blockSignals(False)

        query = f"""
            SELECT *
            FROM {self.table_name}
            ORDER BY
                COALESCE(updated_at, created_at, date) DESC,
                id DESC
        """
        self.all_records = db.execute_query(query)
        return True

    def refresh_database_discreet(self):
        """Rafraîchit discrètement la table sans perturber l'utilisateur."""
        if self._refresh_in_progress:
            self._refresh_pending = True
            self._set_refresh_state("• Sync en attente...", "#ef6c00")
            return

        self._refresh_in_progress = True
        self.spinner.setVisible(True)
        self._set_refresh_state("• Synchronisation...", "#1e88e5")

        cached_payload = self._get_cached_payload()
        if cached_payload is not None:
            try:
                self._apply_reload_payload(cached_payload)
            finally:
                self._finalize_refresh()
            return

        self._start_reload_worker()

    def _update_pagination_display(self):
        """Met à jour l'affichage de la page actuelle."""
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_records = self.filtered_records[start_idx:end_idx]
        self._display_records(page_records, self.all_columns)
        self.pagination_label.setText(f"Page {self.current_page}/{self.total_pages}")
        self.btn_first.setEnabled(self.current_page > 1)
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)
        self.btn_last.setEnabled(self.current_page < self.total_pages)

    def goto_first_page(self):
        """Va à la première page."""
        if self.current_page > 1:
            self.current_page = 1
            self._update_pagination_display()

    def goto_prev_page(self):
        """Va à la page précédente."""
        if self.current_page > 1:
            self.current_page -= 1
            self._update_pagination_display()

    def goto_next_page(self):
        """Va à la page suivante."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._update_pagination_display()

    def goto_last_page(self):
        """Va à la dernière page."""
        if self.current_page < self.total_pages:
            self.current_page = self.total_pages
            self._update_pagination_display()

    def _display_records(self, records, columns):
        """Affiche les enregistrements dans le tableau."""
        self.ui.tableWidget.setColumnCount(len(columns))
        self.ui.tableWidget.setHorizontalHeaderLabels(columns)
        self.ui.tableWidget.setRowCount(len(records))

        for row_idx, record in enumerate(records):
            row_status = (str(record.get("statut") or "").strip().lower() if "statut" in columns else "")
            if row_status == "en_attente":
                row_bg_color = QColor(211, 47, 47, 45)
            elif row_status:
                row_bg_color = QColor(10, 143, 46, 35)
            else:
                row_bg_color = None

            for col_idx, column_name in enumerate(columns):
                value = record.get(column_name)
                text = "" if value is None else str(value)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                if column_name == "statut":
                    status_value = (text or "").strip().lower()
                    if status_value == "traite":
                        item.setForeground(QColor("#0a8f2e"))
                    elif status_value == "en_attente":
                        item.setForeground(QColor("#d32f2f"))
                    elif status_value == "en_cours":
                        item.setForeground(Qt.GlobalColor.darkYellow)

                if value is None or text == "":
                    item.setForeground(Qt.GlobalColor.gray)

                if row_bg_color is not None:
                    item.setBackground(row_bg_color)

                self.ui.tableWidget.setItem(row_idx, col_idx, item)

        self._compact_columns()

    def load_full_database_table(self):
        """Charge toutes les lignes avec toutes les colonnes de la table principale."""
        if not self._reload_all_records():
            self.ui.tableWidget.setRowCount(0)
            self.ui.tableWidget.setColumnCount(0)
            return
        self._last_records_signature = self._compute_records_signature(self.all_records)
        self.filtered_records = self.all_records
        self._apply_order_filter()
        self.current_page = 1
        self.total_pages = max(1, (len(self.all_records) + self.items_per_page - 1) // self.items_per_page)
        self._update_pagination_display()

    def closeEvent(self, event):
        timer = getattr(self, "_auto_refresh_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        super().closeEvent(event)
