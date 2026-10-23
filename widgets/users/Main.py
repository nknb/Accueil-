"""Widget Utilisateurs — design moderne adapté pour le projet Accueil."""

from __future__ import annotations

import json
from contextlib import closing
import sqlite3 as _sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.password_manager import PasswordManager as _PM
from utils.validators import InputValidator

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QMainWindow,
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
    QGroupBox,
    QHeaderView,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QCheckBox,
    QTextEdit,
)

from database.connection import db


# ── Styles partagés ───────────────────────────────────────────────────────────

_BTN_PRIMARY = (
    "QPushButton { background:#1e3a5f; color:white; border-radius:5px;"
    " padding:6px 14px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#2a4f80; }"
    "QPushButton:pressed { background:#16294a; }"
)
_BTN_SUCCESS = (
    "QPushButton { background:#15803d; color:white; border-radius:5px;"
    " padding:6px 14px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#16a34a; }"
    "QPushButton:pressed { background:#0f5c2c; }"
)
_BTN_DANGER = (
    "QPushButton { background:#b91c1c; color:white; border-radius:5px;"
    " padding:6px 14px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#dc2626; }"
    "QPushButton:pressed { background:#991b1b; }"
)
_BTN_NEUTRAL = (
    "QPushButton { background:#64748b; color:white; border-radius:5px;"
    " padding:6px 14px; font-weight:600; font-size:12px; }"
    "QPushButton:hover { background:#475569; }"
    "QPushButton:pressed { background:#334155; }"
)
_INPUT_STYLE = (
    "QLineEdit, QComboBox { border:1px solid #d1d5db; border-radius:5px;"
    " padding:6px 10px; font-size:12px; background:white; color:#111827; }"
    "QLineEdit:focus, QComboBox:focus { border:2px solid #1e3a5f; }"
)
_TABLE_STYLE = (
    "QTableWidget { background:white; border:1px solid #e5e7eb; border-radius:8px;"
    " font-size:13px; color:#1f2937; }"
    "QTableWidget::item { padding:8px 12px; border:none; }"
    "QTableWidget::item:selected { background:#dbeafe; color:#1e3a5f; border:none; }"
    "QHeaderView::section { background:#1e3a5f; color:white; font-weight:700;"
    " font-size:12px; padding:8px 12px; border:none; }"
    "QTableWidget QTableCornerButton::section { background:#1e3a5f; }"
    "QTableWidget::item:alternate { background:#f1f5f9; }"
)


def _hash_password(password: str) -> str:
    """Hash bcrypt (le login refuse tout autre format)."""
    return _PM.hash_password(password)


def retire_admin_autorise(uid) -> bool:
    """False si `uid` est le dernier administrateur actif (le supprimer ou le rétrograder bloquerait l'appli)."""
    admins = db.execute_query("SELECT id FROM auth_user WHERE role = 'admin' AND is_active = 1")
    return not any(str(a["id"]) == str(uid) for a in admins) or len(admins) > 1


def verifier_chemin_base(path: str) -> tuple[bool, str]:
    """Teste une base existante en lecture seule (sqlite3.connect créerait sinon un fichier vide)."""
    if not path:
        return False, "Chemin vide."
    if not Path(path).is_file():
        return False, "Fichier introuvable."
    try:
        with closing(_sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.execute("SELECT 1 FROM auth_user LIMIT 1")
    except Exception as exc:
        return False, f"Base de l'application invalide : {exc}"
    return True, ""


# ── Dialogue utilisateur ──────────────────────────────────────────────────────

class UserFormDialog(QDialog):
    """Dialogue pour ajouter / modifier un utilisateur."""

    ROLES = ["admin", "manager", "accueil", "preaccueil"]

    def __init__(
        self,
        parent: QWidget,
        username: str = "",
        email: str = "",
        role: str = "accueil",
        with_password: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Utilisateur")
        self.setMinimumWidth(380)
        self._with_password = with_password
        self._initial = (username, email)  # valeurs existantes: on ne bloque pas la modification d'un compte ancien

        self.username_edit = QLineEdit(self)
        self.username_edit.setText(username)
        self.username_edit.setPlaceholderText("Identifiant (username)")
        self.username_edit.setStyleSheet(_INPUT_STYLE)

        self.email_edit = QLineEdit(self)
        self.email_edit.setText(email)
        self.email_edit.setPlaceholderText("Adresse e-mail (optionnel)")
        self.email_edit.setStyleSheet(_INPUT_STYLE)

        self.password_edit = QLineEdit(self)
        self.password_edit.setPlaceholderText(
            "Mot de passe" if with_password else "Laisser vide pour conserver"
        )
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setStyleSheet(_INPUT_STYLE)

        self.role_combo = QComboBox(self)
        self.role_combo.addItems(self.ROLES)
        self.role_combo.setStyleSheet(_INPUT_STYLE)
        idx = self.role_combo.findText(role or "accueil")
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Utilisateur :", self.username_edit)
        form.addRow("E-mail :", self.email_edit)
        form.addRow("Rôle :", self.role_combo)
        lbl_pwd = "Mot de passe :" if with_password else "Nouveau mot de passe :"
        form.addRow(lbl_pwd, self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            orientation=Qt.Orientation.Horizontal, parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(_BTN_PRIMARY)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(_BTN_NEUTRAL)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        main = QVBoxLayout(self)
        main.setContentsMargins(20, 18, 20, 16)
        main.setSpacing(14)
        main.addLayout(form)
        main.addWidget(buttons)

    def get_data(self) -> tuple[str, str, Optional[str], str]:
        username = self.username_edit.text().strip()
        email = self.email_edit.text().strip()
        password = self.password_edit.text().strip()
        role = self.role_combo.currentText().strip() or "accueil"
        if not username:
            raise ValueError("Le nom d'utilisateur est obligatoire.")
        if username != self._initial[0]:
            valide, message = InputValidator.validate_username(username)
            if not valide:
                raise ValueError(message)
        if email and email != self._initial[1]:
            valide, message = InputValidator.validate_email(email)
            if not valide:
                raise ValueError(message)
        if self._with_password and not password:
            raise ValueError("Le mot de passe est obligatoire.")
        if password:  # vide = conserver l'ancien (modification)
            valide, message = InputValidator.validate_password(password)
            if not valide:
                raise ValueError(message)
        return username, email, (password or None), role


# ── Onglet Utilisateurs ───────────────────────────────────────────────────────

class _UsersTab(QWidget):
    """Onglet de gestion des comptes utilisateurs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._users: list[dict] = []
        self._build_ui()
        # Debounce : évite un aller-retour BD à chaque frappe
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_filter)
        self._refresh_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Bandeau en-tête
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1e3a5f, stop:1 #2a4f80); }"
        )
        h_box = QHBoxLayout(header)
        h_box.setContentsMargins(20, 14, 20, 14)
        h_box.setSpacing(16)

        lbl_title = QLabel("\U0001f464  Gestion des utilisateurs")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        lbl_title.setFont(f)
        lbl_title.setStyleSheet("color:white; background:transparent;")

        self._stat_total = QLabel("Total : 0")
        self._stat_admin  = QLabel("Admins : 0")
        self._stat_agent  = QLabel("Agents : 0")
        for lbl in (self._stat_total, self._stat_admin, self._stat_agent):
            lbl.setStyleSheet("color:#93c5fd; font-size:12px; font-weight:600; background:transparent;")

        h_box.addWidget(lbl_title)
        h_box.addStretch(1)
        h_box.addWidget(self._stat_total)
        h_box.addWidget(self._stat_admin)
        h_box.addWidget(self._stat_agent)
        root.addWidget(header)

        # Corps
        body = QFrame()
        body.setStyleSheet("QFrame { background:#f8fafc; }")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(10)

        # Barre de recherche + filtre + bouton Ajouter
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("\U0001f50d  Rechercher un utilisateur\u2026")
        self.search_edit.setStyleSheet(_INPUT_STYLE)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())
        top_bar.addWidget(self.search_edit, 3)

        self.role_filter = QComboBox(self)
        self.role_filter.setStyleSheet(_INPUT_STYLE)
        self.role_filter.addItem("Tous les r\u00f4les", None)
        self.role_filter.addItem("Administrateurs", "admin")
        self.role_filter.addItem("Managers", "manager")
        self.role_filter.addItem("Agents accueil", "accueil")
        self.role_filter.addItem("Pr\u00e9-accueil", "preaccueil")
        self.role_filter.currentIndexChanged.connect(self._apply_filter)
        top_bar.addWidget(self.role_filter, 1)

        self.add_btn = QPushButton("\uff0b  Ajouter")
        self.add_btn.setStyleSheet(_BTN_PRIMARY)
        self.add_btn.setMinimumHeight(34)
        self.add_btn.clicked.connect(self._on_add)
        top_bar.addWidget(self.add_btn)
        body_layout.addLayout(top_bar)

        # Tableau
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Utilisateur", "E-mail", "R\u00f4le"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnHidden(0, True)
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.verticalHeader().setDefaultSectionSize(42)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        body_layout.addWidget(self.table, 1)

        # Boutons d'action
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(8)

        self.edit_btn = QPushButton("\u270f  Modifier")
        self.edit_btn.setStyleSheet(_BTN_SUCCESS)
        self.edit_btn.setMinimumHeight(34)
        self.edit_btn.clicked.connect(self._on_edit)

        self.delete_btn = QPushButton("\U0001f5d1  Supprimer")
        self.delete_btn.setStyleSheet(_BTN_DANGER)
        self.delete_btn.setMinimumHeight(34)
        self.delete_btn.clicked.connect(self._on_delete)

        self.reset_btn = QPushButton("\U0001f511  R\u00e9initialiser mot de passe")
        self.reset_btn.setStyleSheet(_BTN_NEUTRAL)
        self.reset_btn.setMinimumHeight(34)
        self.reset_btn.clicked.connect(self._on_reset_password)

        actions_bar.addWidget(self.edit_btn)
        actions_bar.addWidget(self.delete_btn)
        actions_bar.addWidget(self.reset_btn)
        actions_bar.addStretch(1)
        body_layout.addLayout(actions_bar)
        root.addWidget(body, 1)

    # ── Données ───────────────────────────────────────────────────────────────

    def _load_users(self) -> None:
        self._users.clear()
        try:
            rows = db.execute_query(
                "SELECT id, username, email, role FROM auth_user ORDER BY id DESC"
            )
            self._users = list(rows)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur base de donn\u00e9es",
                                 f"Impossible de charger les utilisateurs :\n{exc}")

    def _filtered_users(self) -> list[dict]:
        search = self.search_edit.text().strip().lower()
        role_filter = self.role_filter.currentData()
        result = []
        for user in self._users:
            if role_filter is not None and user.get("role") != role_filter:
                continue
            if search and (
                search not in str(user.get("username") or "").lower()
                and search not in str(user.get("email") or "").lower()
                and search not in str(user.get("role") or "").lower()
            ):
                continue
            result.append(user)
        return result

    def _refresh_table(self) -> None:
        """Recharge depuis la BD puis applique le filtre. Appeler après add/edit/delete."""
        self._load_users()
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Filtre en mémoire et re-rendu — pas d'accès BD. Appelé sur chaque frappe/filtre."""
        filtered = self._filtered_users()

        # Stats en-tête
        all_roles = [u.get("role") for u in self._users]
        self._stat_total.setText(f"Total : {len(self._users)}")
        self._stat_admin.setText(f"Admins : {all_roles.count('admin')}")
        self._stat_agent.setText(f"Agents : {sum(1 for r in all_roles if r in ('accueil', 'preaccueil'))}")

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        for row_idx, user in enumerate(filtered):
            user_id = user.get("id")
            username = str(user.get("username") or "")
            email = str(user.get("email") or "")
            role = str(user.get("role") or "")

            id_item = QTableWidgetItem(str(user_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)

            user_item = QTableWidgetItem(f"   {username}")
            self.table.setItem(row_idx, 1, user_item)

            email_item = QTableWidgetItem(f"   {email}")
            self.table.setItem(row_idx, 2, email_item)

            role_item = QTableWidgetItem(f"  {role.upper()}  ")
            role_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rf = role_item.font(); rf.setBold(True); rf.setPointSize(10)
            role_item.setFont(rf)
            colors = {
                "admin":      ("#1e3a5f", "#ffffff"),
                "manager":    ("#4f46e5", "#ffffff"),
                "accueil":    ("#15803d", "#ffffff"),
                "preaccueil": ("#b45309", "#ffffff"),
            }
            # Texte coloré: le fond d'item est écrasé par le QSS global (texte blanc sur blanc)
            bg, _ = colors.get(role, ("#64748b", "#ffffff"))
            role_item.setForeground(QColor(bg))
            self.table.setItem(row_idx, 3, role_item)

        self.table.setSortingEnabled(True)

    def _selected_user_id(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text() if item else None

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_add(self) -> None:
        dialog = UserFormDialog(self, with_password=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            username, email, password, role = dialog.get_data()
        except ValueError as exc:
            QMessageBox.warning(self, "Utilisateur", str(exc))
            return
        try:
            is_admin = 1 if role == "admin" else 0
            db.execute_insert(
                "INSERT INTO auth_user (username, password, email, role, is_active, is_superuser, is_staff, date_joined)"
                " VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                (username, _hash_password(password), email, role, is_admin, is_admin, datetime.now().isoformat()),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Utilisateur", f"Impossible d'ajouter :\n{exc}")
            return
        self._refresh_table()

    def _on_edit(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            QMessageBox.information(self, "Modification", "S\u00e9lectionnez d'abord un utilisateur.")
            return
        try:
            rows = db.execute_query(
                "SELECT username, email, role FROM auth_user WHERE id = ?", (uid,)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Utilisateur", f"Impossible de lire :\n{exc}")
            return
        if not rows:
            QMessageBox.warning(self, "Modification", "L'utilisateur n'existe plus.")
            return
        row = rows[0]
        dialog = UserFormDialog(
            self, username=str(row.get("username") or ""),
            email=str(row.get("email") or ""),
            role=str(row.get("role") or "accueil"), with_password=False,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new_username, new_email, new_password, new_role = dialog.get_data()
        except ValueError as exc:
            QMessageBox.warning(self, "Utilisateur", str(exc))
            return

        is_admin = 1 if new_role == "admin" else 0
        if not is_admin and not retire_admin_autorise(uid):
            QMessageBox.warning(self, "Modification", "Impossible de rétrograder le dernier administrateur.")
            return
        try:
            if new_password:
                db.execute_update(
                    "UPDATE auth_user SET username=?, email=?, role=?, is_superuser=?, is_staff=?, password=? WHERE id=?",
                    (new_username, new_email, new_role, is_admin, is_admin, _hash_password(new_password), uid),
                )
            else:
                db.execute_update(
                    "UPDATE auth_user SET username=?, email=?, role=?, is_superuser=?, is_staff=? WHERE id=?",
                    (new_username, new_email, new_role, is_admin, is_admin, uid),
                )
        except Exception as exc:  # ex.: identifiant déjà pris (UNIQUE)
            QMessageBox.critical(self, "Utilisateur", f"Impossible de modifier :\n{exc}")
            return
        self._refresh_table()

    def _on_delete(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            QMessageBox.information(self, "Suppression", "S\u00e9lectionnez d'abord un utilisateur.")
            return
        reply = QMessageBox.question(
            self, "Confirmer la suppression",
            "Voulez-vous vraiment supprimer cet utilisateur ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not retire_admin_autorise(uid):
            QMessageBox.warning(self, "Suppression", "Impossible de supprimer le dernier administrateur.")
            return
        try:
            db.execute_update("DELETE FROM auth_user WHERE id = ?", (uid,))
        except Exception as exc:
            QMessageBox.critical(self, "Utilisateur", f"Impossible de supprimer :\n{exc}")
            return
        self._refresh_table()

    def _on_reset_password(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            QMessageBox.information(self, "Mot de passe", "S\u00e9lectionnez d'abord un utilisateur.")
            return
        dialog = UserFormDialog(self, with_password=True)
        dialog.setWindowTitle("R\u00e9initialiser le mot de passe")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            _, _, new_password, _ = dialog.get_data()
        except ValueError as exc:
            QMessageBox.warning(self, "Mot de passe", str(exc))
            return
        try:
            db.execute_update(
                "UPDATE auth_user SET password = ?, echecs = 0, verrouille_jusqua = NULL WHERE id = ?",
                (_hash_password(new_password), uid),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Mot de passe", f"Impossible de mettre \u00e0 jour :\n{exc}")
            return
        QMessageBox.information(self, "Mot de passe", "Le mot de passe a \u00e9t\u00e9 mis \u00e0 jour.")


# ── Onglet Motifs & Services ──────────────────────────────────────────────────

class _MotifServiceTab(QWidget):
    """Onglet de gestion des motifs et services de l'accueil."""

    _TABLE_CONFIG = {
        "accueil_motif":   ("Motif",   ["id", "nom", "description", "actif", "priorite_defaut"]),
        "accueil_service": ("Service", ["id", "nom", "description", "actif", "couleur"]),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_table = "accueil_motif"
        self._columns: list[str] = []
        self._records: list[dict] = []
        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #14532d, stop:1 #166534); }"
        )
        hbox = QHBoxLayout(header)
        hbox.setContentsMargins(20, 14, 20, 14)
        lbl = QLabel("\U0001f4cb  Motifs & Services")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet("color:white; background:transparent;")
        hbox.addWidget(lbl)
        hbox.addStretch(1)
        root.addWidget(header)

        # Corps
        body = QFrame()
        body.setStyleSheet("QFrame { background:#f8fafc; }")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(10)

        # Sélecteur table + bouton Ajouter
        top = QHBoxLayout()
        top.setSpacing(8)
        self.table_combo = QComboBox(self)
        self.table_combo.setStyleSheet(_INPUT_STYLE)
        self.table_combo.addItem("Motifs", "accueil_motif")
        self.table_combo.addItem("Services", "accueil_service")
        self.table_combo.currentIndexChanged.connect(self._on_table_changed)
        top.addWidget(self.table_combo, 1)
        self.add_btn = QPushButton("\uff0b  Ajouter")
        self.add_btn.setStyleSheet(_BTN_PRIMARY)
        self.add_btn.setMinimumHeight(34)
        self.add_btn.clicked.connect(self._on_add)
        top.addWidget(self.add_btn)
        body_layout.addLayout(top)

        # Tableau
        self.table = QTableWidget(self)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.verticalHeader().setDefaultSectionSize(38)
        body_layout.addWidget(self.table, 1)

        # Bouton supprimer
        del_bar = QHBoxLayout()
        self.delete_btn = QPushButton("\U0001f5d1  Supprimer")
        self.delete_btn.setStyleSheet(_BTN_DANGER)
        self.delete_btn.setMinimumHeight(34)
        self.delete_btn.clicked.connect(self._on_delete)
        del_bar.addWidget(self.delete_btn)
        del_bar.addStretch(1)
        body_layout.addLayout(del_bar)
        root.addWidget(body, 1)

    # ── Données ───────────────────────────────────────────────────────────────

    def _on_table_changed(self) -> None:
        self._current_table = self.table_combo.currentData()
        self._load_data()

    _TABLES_AUTORISEES = frozenset({"accueil_motif", "accueil_service"})

    def _load_data(self) -> None:
        # Le nom de table est inséré dans le SQL: on n'accepte que ces deux tables
        assert self._current_table in self._TABLES_AUTORISEES, self._current_table
        try:
            cols_info = db.execute_query(f"PRAGMA table_info({self._current_table})")
            self._columns = [c.get("name") for c in cols_info]
            self._records = db.execute_query(f"SELECT * FROM {self._current_table} ORDER BY id DESC")
            self._display()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Chargement impossible : {exc}")

    def _display(self) -> None:
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels(self._columns)
        self.table.setRowCount(len(self._records))
        hh = self.table.horizontalHeader()
        for col_idx, col_name in enumerate(self._columns):
            hh.setSectionResizeMode(
                col_idx,
                QHeaderView.ResizeMode.Stretch if col_name in ("nom", "description")
                else QHeaderView.ResizeMode.ResizeToContents,
            )
        for row_idx, record in enumerate(self._records):
            for col_idx, col_name in enumerate(self._columns):
                val = record.get(col_name)
                item = QTableWidgetItem("" if val is None else str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

    def _selected_id(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0 or "id" not in self._columns:
            return None
        id_col = self._columns.index("id")
        item = self.table.item(row, id_col)
        return item.text() if item else None

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_add(self) -> None:
        label, _ = self._TABLE_CONFIG.get(self._current_table, ("Élément", []))
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Ajouter un {label.lower()}")
        form = QFormLayout(dialog)

        nom_input = QLineEdit()
        nom_input.setStyleSheet(_INPUT_STYLE)
        desc_input = QTextEdit()
        desc_input.setMaximumHeight(80)
        actif_check = QCheckBox("Actif")
        actif_check.setChecked(True)
        form.addRow("Nom :", nom_input)
        form.addRow("Description :", desc_input)
        form.addRow("", actif_check)

        extra_combo = None
        if self._current_table == "accueil_motif":
            extra_combo = QComboBox()
            extra_combo.setStyleSheet(_INPUT_STYLE)
            extra_combo.addItems(["normale", "moyenne", "haute"])
            form.addRow("Priorité :", extra_combo)
        elif self._current_table == "accueil_service":
            extra_combo = QLineEdit("#417690")
            extra_combo.setStyleSheet(_INPUT_STYLE)
            form.addRow("Couleur :", extra_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        nom = nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Validation", f"Le nom du {label.lower()} est obligatoire.")
            return

        desc = desc_input.toPlainText().strip()
        actif = 1 if actif_check.isChecked() else 0

        try:
            if self._current_table == "accueil_motif":
                prio = extra_combo.currentText() if extra_combo else "normale"
                db.execute_insert(
                    "INSERT INTO accueil_motif (nom, description, actif, priorite_defaut) VALUES (?,?,?,?)",
                    (nom, desc, actif, prio),
                )
            elif self._current_table == "accueil_service":
                couleur = extra_combo.text().strip() if isinstance(extra_combo, QLineEdit) else "#417690"
                db.execute_insert(
                    "INSERT INTO accueil_service (nom, description, actif, couleur) VALUES (?,?,?,?)",
                    (nom, desc, actif, couleur or "#417690"),
                )
            self._load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Ajout impossible : {exc}")

    def _on_delete(self) -> None:
        uid = self._selected_id()
        if uid is None:
            QMessageBox.information(self, "Suppression", "S\u00e9lectionnez d'abord une ligne.")
            return
        label, _ = self._TABLE_CONFIG.get(self._current_table, ("Élément", []))
        reply = QMessageBox.question(
            self, "Confirmer", f"Supprimer ce {label.lower()} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            db.execute_update(f"DELETE FROM {self._current_table} WHERE id = ?", (uid,))
            self._load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Suppression impossible : {exc}")


# ── Onglet Configuration ──────────────────────────────────────────────────────

class _ConfigTab(QWidget):
    """Onglet Configuration : affiche et permet de modifier le chemin de la BD."""

    _SS_HEADER = (
        "QWidget#cfgHeader { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        "  stop:0 #0f2744, stop:0.6 #1e3a5f, stop:1 #1a4a7a); }"
    )
    _SS_CARD = (
        "QGroupBox { background:#ffffff; border:1px solid #e2e8f0; border-radius:10px;"
        "  font-weight:700; font-size:12px; color:#1e3a5f; padding-top:18px; margin-top:8px; }"
        "QGroupBox::title { subcontrol-origin:margin; left:14px; top:2px; }"
    )
    _SS_INPUT = (
        "QLineEdit { border:1px solid #d1d5db; border-radius:6px; padding:8px 12px;"
        "  font-size:12px; background:white; color:#111827; }"
        "QLineEdit:focus { border:2px solid #1e3a5f; }"
        "QLineEdit:read-only { background:#f8fafc; color:#64748b; }"
    )
    _SS_RADIO = (
        "QRadioButton { font-size:12px; font-weight:600; color:#374151; spacing:8px; }"
        "QRadioButton::indicator { width:16px; height:16px; }"
        "QRadioButton::indicator:checked { background:#1e3a5f; border:3px solid #93c5fd;"
        "  border-radius:8px; }"
        "QRadioButton::indicator:unchecked { background:#e5e7eb; border:2px solid #9ca3af;"
        "  border-radius:8px; }"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_config()

    # ── Construction de l'interface ──────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── En-tête ──────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("cfgHeader")
        header.setStyleSheet(self._SS_HEADER)
        header.setFixedHeight(60)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 0, 20, 0)

        icon_lbl = QLabel("⚙️")
        icon_lbl.setStyleSheet("font-size:22px; background:transparent;")
        title_lbl = QLabel("Configuration de l'application")
        title_lbl.setStyleSheet(
            "color:white; font-size:15px; font-weight:700; background:transparent;"
        )
        sub_lbl = QLabel("Connexion à la base de données")
        sub_lbl.setStyleSheet(
            "color:#bfdbfe; font-size:11px; font-weight:500; background:transparent;"
        )
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)

        h_lay.addWidget(icon_lbl)
        h_lay.addSpacing(10)
        h_lay.addLayout(title_col)
        h_lay.addStretch()
        root.addWidget(header)

        # ── Zone scrollable ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:#f8fafc; border:none; }")

        body = QWidget()
        body.setStyleSheet("background:#f8fafc;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 20, 24, 24)
        body_lay.setSpacing(16)

        # ── Carte : statut actuel ─────────────────────────────────────────
        status_grp = QGroupBox("Base de données active")
        status_grp.setStyleSheet(self._SS_CARD)
        sg = QVBoxLayout(status_grp)
        sg.setContentsMargins(14, 10, 14, 14)
        sg.setSpacing(10)

        # Chemin courant
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Chemin :"))
        self._lbl_current_path = QLabel()
        self._lbl_current_path.setStyleSheet(
            "color:#1e3a5f; font-weight:600; font-size:12px;"
            " background:#eff6ff; border:1px solid #bfdbfe; border-radius:5px;"
            " padding:5px 10px;"
        )
        self._lbl_current_path.setWordWrap(True)
        path_row.addWidget(self._lbl_current_path, 1)
        sg.addLayout(path_row)

        # Type + badge connexion
        info_row = QHBoxLayout()
        type_lbl = QLabel("Type :")
        info_row.addWidget(type_lbl)
        self._lbl_type = QLabel()
        self._lbl_type.setStyleSheet(
            "font-weight:700; font-size:11px; border-radius:5px; padding:3px 10px;"
        )
        info_row.addWidget(self._lbl_type)
        info_row.addSpacing(20)

        self._lbl_conn_status = QLabel("— non testé —")
        self._lbl_conn_status.setStyleSheet("color:#64748b; font-size:11px;")
        info_row.addWidget(self._lbl_conn_status)
        info_row.addStretch()

        btn_test_cur = QPushButton("🔌  Tester la connexion")
        btn_test_cur.setStyleSheet(_BTN_PRIMARY)
        btn_test_cur.setFixedHeight(32)
        btn_test_cur.clicked.connect(self._test_current)
        info_row.addWidget(btn_test_cur)
        sg.addLayout(info_row)

        body_lay.addWidget(status_grp)

        # ── Carte : modifier la configuration ────────────────────────────
        cfg_grp = QGroupBox("Modifier la configuration")
        cfg_grp.setStyleSheet(self._SS_CARD)
        cg = QVBoxLayout(cfg_grp)
        cg.setContentsMargins(14, 10, 14, 14)
        cg.setSpacing(12)

        # Sélection réseau / local
        mode_row = QHBoxLayout()
        self._radio_network = QRadioButton("Réseau (production)")
        self._radio_local   = QRadioButton("Local (développement / test)")
        self._radio_network.setStyleSheet(self._SS_RADIO)
        self._radio_local.setStyleSheet(self._SS_RADIO)
        self._radio_network.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._radio_network)
        mode_row.addSpacing(30)
        mode_row.addWidget(self._radio_local)
        mode_row.addStretch()
        cg.addLayout(mode_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        cg.addWidget(sep)

        # Champ chemin
        path_lbl = QLabel("Chemin de la base de données :")
        path_lbl.setStyleSheet("font-size:11px; font-weight:600; color:#64748b;")
        cg.addWidget(path_lbl)

        path_input_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setStyleSheet(self._SS_INPUT)
        self._path_edit.setFixedHeight(36)
        self._path_edit.setPlaceholderText("Ex : //srvgagnoa/prod/datagagnoa/accueil/db.sqlite3")
        path_input_row.addWidget(self._path_edit, 1)

        btn_test_new = QPushButton("🔌  Tester")
        btn_test_new.setStyleSheet(_BTN_NEUTRAL)
        btn_test_new.setFixedHeight(36)
        btn_test_new.clicked.connect(self._test_new_path)
        path_input_row.addWidget(btn_test_new)
        cg.addLayout(path_input_row)

        self._lbl_test_result = QLabel()
        self._lbl_test_result.setWordWrap(True)
        self._lbl_test_result.setVisible(False)
        cg.addWidget(self._lbl_test_result)

        # Boutons action
        action_row = QHBoxLayout()
        action_row.addStretch()

        btn_reset = QPushButton("↩  Réinitialiser (local)")
        btn_reset.setStyleSheet(_BTN_NEUTRAL)
        btn_reset.setFixedHeight(34)
        btn_reset.clicked.connect(self._reset_local)
        action_row.addWidget(btn_reset)

        btn_save = QPushButton("💾  Sauvegarder")
        btn_save.setStyleSheet(_BTN_SUCCESS)
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._save_config)
        action_row.addWidget(btn_save)
        cg.addLayout(action_row)

        body_lay.addWidget(cfg_grp)

        # ── Note redémarrage ─────────────────────────────────────────────
        note = QLabel(
            "ℹ️  Tout changement de base de données sera pris en compte "
            "au prochain démarrage de l'application."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#92400e; background:#fef3c7; border:1px solid #fde68a;"
            " border-radius:7px; padding:10px 14px; font-size:11px;"
        )
        body_lay.addWidget(note)
        body_lay.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ── Logique ──────────────────────────────────────────────────────────────

    def _load_config(self):
        from config import AppConfig
        current = AppConfig.get_db_path()
        self._lbl_current_path.setText(str(current))

        is_network = self._is_network_path(str(current))
        if is_network:
            self._lbl_type.setText("  Réseau  ")
            self._lbl_type.setStyleSheet(
                "font-weight:700; font-size:11px; border-radius:5px; padding:3px 10px;"
                " background:#dbeafe; color:#1e40af;"
            )
        else:
            self._lbl_type.setText("  Local  ")
            self._lbl_type.setStyleSheet(
                "font-weight:700; font-size:11px; border-radius:5px; padding:3px 10px;"
                " background:#dcfce7; color:#166534;"
            )

        # Pré-remplir le champ de modification
        self._path_edit.setText(str(current))

        if is_network:
            self._radio_network.setChecked(True)
        else:
            self._radio_local.setChecked(True)

    def _on_mode_changed(self):
        from config import AppConfig
        if self._radio_network.isChecked():
            self._path_edit.setText(AppConfig.DEFAULT_NETWORK_DB)
        else:
            local = str(AppConfig._runtime_dir() / "db.sqlite3")
            self._path_edit.setText(local)
        self._lbl_test_result.setVisible(False)

    @staticmethod
    def _is_network_path(path: str) -> bool:
        return path.startswith("//") or path.startswith("\\\\")

    def _test_current(self):
        from config import AppConfig
        self._run_test(str(AppConfig.get_db_path()), self._lbl_conn_status)

    def _test_new_path(self):
        self._lbl_test_result.setVisible(True)
        self._run_test(self._path_edit.text().strip(), self._lbl_test_result)

    @staticmethod
    def _run_test(path: str, label: QLabel):
        ok, erreur = verifier_chemin_base(path)
        if ok:
            label.setText(f"✅ Connexion réussie : {path}")
            label.setStyleSheet(
                "color:#166534; font-size:11px; background:#dcfce7;"
                " border-radius:5px; padding:4px 8px;"
            )
        else:
            label.setText(f"❌ Échec : {erreur}")
            label.setStyleSheet(
                "color:#991b1b; font-size:11px; background:#fee2e2;"
                " border-radius:5px; padding:4px 8px;"
            )

    def _save_config(self):
        from config import AppConfig
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Chemin vide", "Veuillez saisir un chemin de base de données.")
            return
        # La base locale par défaut peut ne pas exister encore (créée au démarrage)
        if Path(path) != AppConfig._runtime_dir() / "db.sqlite3":
            ok, erreur = verifier_chemin_base(path)
            if not ok:
                QMessageBox.warning(self, "Chemin refusé", f"{erreur}\n\nUn chemin faux ferait créer une base vide au prochain démarrage.")
                return
        try:
            config = {"custom_db_path": path}
            AppConfig.DB_CONFIG_FILE.write_text(
                json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            # Rafraîchir l'affichage statut
            self._load_config()
            self._lbl_test_result.setVisible(False)
            QMessageBox.information(
                self,
                "Configuration sauvegardée",
                f"✅ Nouveau chemin enregistré :\n{path}\n\n"
                "Redémarrez l'application pour appliquer le changement.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible d'écrire la configuration :\n{exc}")

    def _reset_local(self):
        from config import AppConfig
        local = str(AppConfig._runtime_dir() / "db.sqlite3")
        self._path_edit.setText(local)
        self._radio_local.setChecked(True)
        self._lbl_test_result.setVisible(False)


# ── Page principale (QMainWindow) ─────────────────────────────────────────────

class UsersPage(QMainWindow):
    """Page de gestion des utilisateurs, motifs et services — design moderne."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestion utilisateurs")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget(central)
        tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #f8fafc; }"
            "QTabBar::tab { background: #e2e8f0; color: #374151; padding: 10px 20px;"
            "  font-weight: 600; border: none; border-radius: 0; }"
            "QTabBar::tab:selected { background: #1e3a5f; color: white; }"
            "QTabBar::tab:hover:!selected { background: #cbd5e1; }"
        )

        self._users_tab = _UsersTab()
        self._motifs_tab = _MotifServiceTab()
        self._config_tab = _ConfigTab()

        tabs.addTab(self._users_tab, "\U0001f464  Utilisateurs")
        tabs.addTab(self._motifs_tab, "\U0001f4cb  Motifs & Services")
        tabs.addTab(self._config_tab, "\u2699\ufe0f  Configuration")

        layout.addWidget(tabs)
