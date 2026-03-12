import hashlib
import sys
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QHeaderView,
    QTableWidgetItem,
    QTextEdit,
)

from database.connection import db
from .Show_Data import Ui_MainWindow


def hash_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class UsersPage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.current_table = "auth_user"
        self.current_columns = []
        self.current_records = []

        self._ensure_management_tables()
        self._init_ui()
        self._wire_actions()
        self.load_current_table()

    def _ensure_management_tables(self):
        db.execute_update(
            """
            CREATE TABLE IF NOT EXISTS accueil_motif (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom VARCHAR(200) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                actif BOOLEAN NOT NULL DEFAULT 1,
                priorite_defaut VARCHAR(10) NOT NULL DEFAULT 'normale'
            )
            """
        )

        db.execute_update(
            """
            CREATE TABLE IF NOT EXISTS accueil_service (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom VARCHAR(200) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                actif BOOLEAN NOT NULL DEFAULT 1,
                couleur VARCHAR(20) NOT NULL DEFAULT '#417690'
            )
            """
        )

    def _init_ui(self):
        self.ui.label_2.setText("Gestion Utilisateurs / Motifs / Services")
        self.ui.lineEdit.hide()

        self.entity_combo = QComboBox()
        self.entity_combo.addItem("Utilisateurs", "auth_user")
        self.entity_combo.addItem("Motifs", "accueil_motif")
        self.entity_combo.addItem("Services", "accueil_service")
        self.ui.horizontalLayout_2.insertWidget(1, self.entity_combo)

        self.ui.get_data_btn.setText("Rafraîchir")
        self.ui.save_btn.setText("Ajouter")
        self._update_delete_button_text()

        self.ui.tableWidget.setEditTriggers(self.ui.tableWidget.EditTrigger.NoEditTriggers)
        self.ui.tableWidget.setSelectionBehavior(self.ui.tableWidget.SelectionBehavior.SelectRows)
        self.ui.tableWidget.setAlternatingRowColors(True)
        self.ui.tableWidget.setWordWrap(False)
        self.ui.tableWidget.verticalHeader().setVisible(False)
        self.ui.tableWidget.setHorizontalScrollMode(self.ui.tableWidget.ScrollMode.ScrollPerPixel)
        self.ui.tableWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _is_compact_screen(self) -> bool:
        screen = self.ui.tableWidget.screen()
        available_width = screen.availableGeometry().width() if screen else 1366
        return available_width <= 1440

    def _apply_users_table_layout(self):
        table = self.ui.tableWidget
        header = table.horizontalHeader()
        compact_mode = self._is_compact_screen()

        header.setStretchLastSection(False)
        header.setMinimumSectionSize(76 if compact_mode else 90)
        table.verticalHeader().setDefaultSectionSize(34 if compact_mode else 38)
        table.resizeColumnsToContents()

        min_width = 76 if compact_mode else 90
        max_width = 135 if compact_mode else 180
        id_width = 82 if compact_mode else 96

        for col_idx in range(table.columnCount()):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
            header_item = table.horizontalHeaderItem(col_idx)
            column_name = header_item.text().lower() if header_item else ""
            target = max(min_width, min(table.columnWidth(col_idx), max_width))
            if column_name in {"id", "uuid"}:
                target = id_width
            table.setColumnWidth(col_idx, target)

    def _wire_actions(self):
        self.entity_combo.currentIndexChanged.connect(self.on_entity_changed)
        self.ui.get_data_btn.clicked.connect(self.load_current_table)
        self.ui.save_btn.clicked.connect(self.on_add_clicked)
        self.ui.get_path_btn.clicked.connect(self.on_delete_user_clicked)

    def on_entity_changed(self):
        self.current_table = self.entity_combo.currentData()
        self._update_delete_button_text()
        self.load_current_table()

    def _update_delete_button_text(self):
        if self.current_table == "auth_user":
            self.ui.get_path_btn.setText("Supprimer utilisateur")
        elif self.current_table == "accueil_motif":
            self.ui.get_path_btn.setText("Supprimer motif")
        elif self.current_table == "accueil_service":
            self.ui.get_path_btn.setText("Supprimer service")
        else:
            self.ui.get_path_btn.setText("Supprimer")

    def _get_table_columns(self, table_name: str):
        result = db.execute_query(f"PRAGMA table_info({table_name})")
        return [row["name"] for row in result]

    def load_current_table(self):
        try:
            table_name = self.current_table
            self.current_columns = self._get_table_columns(table_name)
            if not self.current_columns:
                self.ui.tableWidget.setRowCount(0)
                self.ui.tableWidget.setColumnCount(0)
                return

            query = f"SELECT * FROM {table_name} ORDER BY id DESC"
            self.current_records = db.execute_query(query)
            self._display_records(self.current_records, self.current_columns)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Chargement impossible: {e}")

    def _display_records(self, records, columns):
        self.ui.tableWidget.setColumnCount(len(columns))
        self.ui.tableWidget.setHorizontalHeaderLabels(columns)
        self.ui.tableWidget.setRowCount(len(records))

        for row_idx, row_data in enumerate(records):
            for col_idx, column in enumerate(columns):
                value = row_data.get(column)
                text = "" if value is None else str(value)

                if self.current_table == "auth_user" and column == "password":
                    text = "********"

                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.ui.tableWidget.setItem(row_idx, col_idx, item)

            self._apply_users_table_layout()

    def on_add_clicked(self):
        if self.current_table == "auth_user":
            self._add_user()
            return
        if self.current_table == "accueil_motif":
            self._add_motif()
            return
        if self.current_table == "accueil_service":
            self._add_service()
            return

    def on_delete_user_clicked(self):
        selected_row = self.ui.tableWidget.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Suppression", "Sélectionnez une ligne à supprimer.")
            return

        id_col = self.current_columns.index("id") if "id" in self.current_columns else -1
        nom_col = self.current_columns.index("nom") if "nom" in self.current_columns else -1
        username_col = self.current_columns.index("username") if "username" in self.current_columns else -1

        if id_col < 0:
            QMessageBox.warning(self, "Suppression", "Colonne id introuvable.")
            return

        row_id = self.ui.tableWidget.item(selected_row, id_col).text()

        if self.current_table == "auth_user":
            entity_label = "utilisateur"
            display_name = self.ui.tableWidget.item(selected_row, username_col).text() if username_col >= 0 else row_id
        elif self.current_table == "accueil_motif":
            entity_label = "motif"
            display_name = self.ui.tableWidget.item(selected_row, nom_col).text() if nom_col >= 0 else row_id
        elif self.current_table == "accueil_service":
            entity_label = "service"
            display_name = self.ui.tableWidget.item(selected_row, nom_col).text() if nom_col >= 0 else row_id
        else:
            entity_label = "élément"
            display_name = row_id

        confirm = QMessageBox.question(
            self,
            "Confirmer",
            f"Supprimer le {entity_label} '{display_name}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            db.execute_update(f"DELETE FROM {self.current_table} WHERE id = ?", (row_id,))
            QMessageBox.information(self, "Succès", f"{entity_label.capitalize()} supprimé avec succès.")
            self.load_current_table()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Suppression impossible: {e}")

    def _add_user(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter un utilisateur")
        form = QFormLayout(dialog)

        username_input = QLineEdit()
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        email_input = QLineEdit()
        role_combo = QComboBox()
        role_combo.addItems(["admin", "manager", "accueil", "preaccueil"])
        active_check = QCheckBox("Actif")
        active_check.setChecked(True)

        form.addRow("Username:", username_input)
        form.addRow("Mot de passe:", password_input)
        form.addRow("Email:", email_input)
        form.addRow("Rôle:", role_combo)
        form.addRow("", active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        username = username_input.text().strip()
        password = password_input.text()
        email = email_input.text().strip()
        role = role_combo.currentText()
        is_active = 1 if active_check.isChecked() else 0

        if not username or not password:
            QMessageBox.warning(self, "Validation", "Username et mot de passe sont obligatoires.")
            return

        is_superuser = 1 if role == "admin" else 0
        is_staff = 1 if role in ["admin", "manager"] else 0
        date_joined = datetime.now().isoformat()

        try:
            db.execute_insert(
                """
                INSERT INTO auth_user
                (username, password, email, is_active, is_superuser, is_staff, date_joined, role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    hash_sha256(password),
                    email,
                    is_active,
                    is_superuser,
                    is_staff,
                    date_joined,
                    role,
                ),
            )
            QMessageBox.information(self, "Succès", "Utilisateur ajouté avec succès.")
            self.load_current_table()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Ajout utilisateur impossible: {e}")

    def _add_motif(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter un motif")
        form = QFormLayout(dialog)

        nom_input = QLineEdit()
        description_input = QTextEdit()
        description_input.setMaximumHeight(80)
        priorite_combo = QComboBox()
        priorite_combo.addItems(["normale", "moyenne", "haute"])
        active_check = QCheckBox("Actif")
        active_check.setChecked(True)

        form.addRow("Nom:", nom_input)
        form.addRow("Description:", description_input)
        form.addRow("Priorité défaut:", priorite_combo)
        form.addRow("", active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        nom = nom_input.text().strip()
        description = description_input.toPlainText().strip()
        priorite = priorite_combo.currentText()
        actif = 1 if active_check.isChecked() else 0

        if not nom:
            QMessageBox.warning(self, "Validation", "Le nom du motif est obligatoire.")
            return

        try:
            db.execute_insert(
                """
                INSERT INTO accueil_motif (nom, description, actif, priorite_defaut)
                VALUES (?, ?, ?, ?)
                """,
                (nom, description, actif, priorite),
            )
            QMessageBox.information(self, "Succès", "Motif ajouté avec succès.")
            self.load_current_table()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Ajout motif impossible: {e}")

    def _add_service(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter un service")
        form = QFormLayout(dialog)

        nom_input = QLineEdit()
        description_input = QTextEdit()
        description_input.setMaximumHeight(80)
        couleur_input = QLineEdit("#417690")
        active_check = QCheckBox("Actif")
        active_check.setChecked(True)

        form.addRow("Nom:", nom_input)
        form.addRow("Description:", description_input)
        form.addRow("Couleur:", couleur_input)
        form.addRow("", active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        nom = nom_input.text().strip()
        description = description_input.toPlainText().strip()
        couleur = couleur_input.text().strip() or "#417690"
        actif = 1 if active_check.isChecked() else 0

        if not nom:
            QMessageBox.warning(self, "Validation", "Le nom du service est obligatoire.")
            return

        try:
            db.execute_insert(
                """
                INSERT INTO accueil_service (nom, description, actif, couleur)
                VALUES (?, ?, ?, ?)
                """,
                (nom, description, actif, couleur),
            )
            QMessageBox.information(self, "Succès", "Service ajouté avec succès.")
            self.load_current_table()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Ajout service impossible: {e}")


if __name__ == '__main__':
    print("start")
    app = QApplication(sys.argv)

    window = UsersPage()
    window.show()

    sys.exit(app.exec())
