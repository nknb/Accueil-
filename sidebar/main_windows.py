# sidebar/main_windows.py
"""Fenêtre principale de l'application avec interface sidebar

Cette fenêtre utilise Ui_MainWindow générée par Qt Designer et ajoute
la logique métier pour la gestion des demandes d'accueil.
"""

import sys
from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget
from PyQt6.QtCore import pyqtSlot, QFile, QTextStream, Qt, QPoint
from PyQt6.QtCore import QIODevice
from pathlib import Path

# CORRECTION IMPORTANTE: importer depuis le fichier sidebar.py
from .sidebar import Ui_MainWindow

# Importer les widgets de pages
from widgets import AccueilPage, DashboardPage, PreAccueilPage, DatabasePage, UsersPage
from database.connection import db
from utils import app_logger

class MainWindow(QMainWindow):
    """Fenêtre principale avec gestion des rôles et permissions
    
    Attributs:
        current_user: Dict contenant les infos de l'utilisateur actuellement connecté
        ui: Instance de Ui_MainWindow (interface générée)
    """
    
    def __init__(self):
        super(MainWindow, self).__init__()

        # Fenêtre sans barre de titre native
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_pos = QPoint()

        # Permissions par défaut avant connexion (évite erreurs pendant l'init UI)
        self.allowed_views = {'accueil', 'dashboard', 'preaccueil', 'database', 'users'}

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Boutons de contrôle fenêtre dans la barre de header
        self._add_window_controls()

        # Lazy loading : pages créées à la première navigation
        _VIEW_NAMES = ['accueil', 'dashboard', 'preaccueil', 'database', 'users']
        self._page_factories = {
            'accueil':    AccueilPage,
            'dashboard':  DashboardPage,
            'preaccueil': PreAccueilPage,
            'database':   DatabasePage,
            'users':      UsersPage,
        }
        self._page_cache: dict = {}

        # Vider les placeholders du designer et insérer des QWidget légers
        while self.ui.stackedWidget.count() > 0:
            self.ui.stackedWidget.removeWidget(self.ui.stackedWidget.widget(0))
        for _ in _VIEW_NAMES:
            self.ui.stackedWidget.addWidget(QWidget())

        # Créer la page Accueil immédiatement (vue par défaut + set_current_user)
        self._create_page('accueil')
        
        # Connecter les signaux des boutons de menu
        self.ui.home_btn_1.toggled.connect(self.on_home_btn_1_toggled)
        self.ui.home_btn_2.toggled.connect(self.on_home_btn_2_toggled)
        self.ui.dashborad_btn_1.toggled.connect(self.on_dashborad_btn_1_toggled)
        self.ui.dashborad_btn_2.toggled.connect(self.on_dashborad_btn_2_toggled)
        self.ui.orders_btn_1.toggled.connect(self.on_orders_btn_1_toggled)
        self.ui.orders_btn_2.toggled.connect(self.on_orders_btn_2_toggled)
        self.ui.products_btn_1.toggled.connect(self.on_products_btn_1_toggled)
        self.ui.products_btn_2.toggled.connect(self.on_products_btn_2_toggled)
        self.ui.customers_btn_1.toggled.connect(self.on_customers_btn_1_toggled)
        self.ui.customers_btn_2.toggled.connect(self.on_customers_btn_2_toggled)
        
        # Connecter les boutons spéciaux
        self.ui.user_btn.clicked.connect(self.on_user_btn_clicked)
        self.ui.change_btn.toggled.connect(self.on_change_btn_toggled)
        
        # Connecter le changement de page
        self.ui.stackedWidget.currentChanged.connect(self.on_stackedWidget_currentChanged)
        
        self.ui.icon_only_widget.hide()
        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.home_btn_2.setChecked(True)
        
        # Variable pour stocker l'utilisateur connecté
        self.current_user = None
        
        app_logger.info("Fenêtre principale initialisée avec tous les widgets")

    # ── Lazy loading des pages ────────────────────────────────────────────────

    _VIEW_NAMES = ['accueil', 'dashboard', 'preaccueil', 'database', 'users']

    def _create_page(self, name: str) -> None:
        """Crée la page `name` si elle n'existe pas encore et remplace le placeholder."""
        if name in self._page_cache:
            return
        page = self._page_factories[name]()
        self._page_cache[name] = page
        idx = self._VIEW_NAMES.index(name)
        old = self.ui.stackedWidget.widget(idx)
        self.ui.stackedWidget.removeWidget(old)
        old.deleteLater()
        self.ui.stackedWidget.insertWidget(idx, page)

    @property
    def accueil_page(self):    return self._page_cache.get('accueil')
    @property
    def dashboard_page(self):  return self._page_cache.get('dashboard')
    @property
    def preaccueil_page(self): return self._page_cache.get('preaccueil')
    @property
    def database_page(self):   return self._page_cache.get('database')
    @property
    def users_page(self):      return self._page_cache.get('users')

    def _add_window_controls(self):
        """Ajoute les boutons Réduire / Agrandir / Fermer dans la barre de header."""
        header = self.ui.widget  # barre du haut (change_btn + user_btn)

        _BTN = (
            ("─", "#f59e0b", "#d97706", "#b45309", self.showMinimized),   # Réduire
            ("□", "#22c55e", "#16a34a", "#15803d", self._toggle_maximize), # Agrandir
            ("✕", "#ef4444", "#dc2626", "#b91c1c", self.close),            # Fermer
        )

        for symbol, bg, hover, pressed, slot in _BTN:
            btn = QPushButton(symbol, header)
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:white; border-radius:11px;"
                f"  font-size:11px; font-weight:700; border:none; }}"
                f"QPushButton:hover {{ background:{hover}; }}"
                f"QPushButton:pressed {{ background:{pressed}; }}"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            self.ui.horizontalLayout_4.addWidget(btn)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ── Déplacement fenêtre sans barre de titre ───────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if (event.buttons() == Qt.MouseButton.LeftButton
                and not self._drag_pos.isNull()
                and not self.isMaximized()):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()

    def mouseDoubleClickEvent(self, event):
        """Double-clic sur la barre de header → agrandir/restaurer."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()

    def _apply_role_permissions(self, role: str):
        """Applique les permissions d'interface selon le rôle."""
        permissions_by_role = {
            'preaccueil': {'preaccueil'},
            'accueil': {'accueil', 'preaccueil'},
            'manager': {'accueil', 'preaccueil', 'dashboard'},
            'admin': {'accueil', 'preaccueil', 'dashboard', 'database', 'users'},
        }

        self.allowed_views = permissions_by_role.get(role, {'accueil'})

        # Accueil
        self.ui.home_btn_1.setVisible('accueil' in self.allowed_views)
        self.ui.home_btn_2.setVisible('accueil' in self.allowed_views)

        # Dashboard
        self.ui.dashborad_btn_1.setVisible('dashboard' in self.allowed_views)
        self.ui.dashborad_btn_2.setVisible('dashboard' in self.allowed_views)

        # Pré-accueil
        self.ui.orders_btn_1.setVisible('preaccueil' in self.allowed_views)
        self.ui.orders_btn_2.setVisible('preaccueil' in self.allowed_views)

        # Base de données
        self.ui.products_btn_1.setVisible('database' in self.allowed_views)
        self.ui.products_btn_2.setVisible('database' in self.allowed_views)

        # Utilisateurs
        self.ui.customers_btn_1.setVisible('users' in self.allowed_views)
        self.ui.customers_btn_2.setVisible('users' in self.allowed_views)

    def _go_to_view(self, view_name: str):
        """Navigue vers une vue autorisée selon le rôle."""
        view_index_map = {
            'accueil': 0,
            'dashboard': 1,
            'preaccueil': 2,
            'database': 3,
            'users': 4,
        }

        if view_name not in self.allowed_views:
            app_logger.warning(f"Accès refusé à la vue '{view_name}' pour rôle {self.current_user.get('role') if self.current_user else 'inconnu'}")
            return

        self._create_page(view_name)
        self.ui.stackedWidget.setCurrentIndex(view_index_map[view_name])

    def _get_fallback_allowed_index(self) -> int:
        """Retourne un index autorisé de repli selon les permissions courantes."""
        ordered_views = ['dashboard', 'accueil', 'preaccueil', 'database', 'users']
        view_index_map = {
            'accueil': 0,
            'dashboard': 1,
            'preaccueil': 2,
            'database': 3,
            'users': 4,
        }

        for view_name in ordered_views:
            if view_name in self.allowed_views:
                return view_index_map[view_name]

        return 0

    def _set_default_view_for_role(self, role: str):
        """Positionne la vue par défaut après connexion selon le rôle."""
        if role == 'manager':
            self._go_to_view('dashboard')
            self.ui.dashborad_btn_1.setChecked(True)
            self.ui.dashborad_btn_2.setChecked(True)
        elif role == 'preaccueil':
            self._go_to_view('preaccueil')
            self.ui.orders_btn_1.setChecked(True)
            self.ui.orders_btn_2.setChecked(True)
        else:
            self._go_to_view('accueil')
            self.ui.home_btn_1.setChecked(True)
            self.ui.home_btn_2.setChecked(True)

    def set_current_user(self, user):
        """Reçoit l'utilisateur connecté depuis main.py
        
        Args:
            user: Dict avec id, username, email, role, role_display
        """
        self.current_user = user
        self.accueil_page.set_current_user(user)
        try:
            updated_rows = db.rollover_pending_to_non_traite()
            if updated_rows:
                app_logger.info(f"Rollover quotidien appliqué: {updated_rows} demandes passées en non_traite")
        except Exception as e:
            app_logger.error(f"Erreur rollover quotidien des statuts: {e}")
        app_logger.info(f"Utilisateur connecté: {user['username']} - {user['role_display']}")
        print(f"✅ Utilisateur connecté à sidebar: {user['username']} - {user['role_display']}")
        role = user['role']
        self._apply_role_permissions(role)

        if role == 'admin':
            print("👑 Mode Administrateur - Accès complet")
        elif role == 'manager':
            print("📊 Mode Manager - Accueil, Pré-accueil, Dashboard")
        elif role == 'accueil':
            print("🏢 Mode Agent Accueil - Accueil, Pré-accueil")
        elif role == 'preaccueil':
            print("🛂 Mode Pré-accueil - Pré-accueil uniquement")

        self._set_default_view_for_role(role)

    ## Function for searching
    def on_search_btn_clicked(self):
        """Déclenche la recherche et affiche les résultats"""
        self.ui.stackedWidget.setCurrentIndex(5)
        search_text = self.ui.search_input.text().strip()
        if search_text:
            self.ui.label_9.setText(f"Résultats pour: {search_text}")
        app_logger.info(f"Recherche: {search_text}")

    ## Function for changing page to user page
    def on_user_btn_clicked(self):
        """Bascule vers la page profil utilisateur"""
        self.ui.stackedWidget.setCurrentIndex(6)
        if self.current_user:
            self.ui.label_10.setText(f"Profil de {self.current_user['username']}")
        app_logger.info("Accès au profil utilisateur")

    ## Change QPushButton Checkable status when stackedWidget index changed
    def on_stackedWidget_currentChanged(self, index):
        """Gère les boutons lors du changement d'onglet
        
        Args:
            index: Index du nouvel onglet affiché
        """
        # Verrouillage d'accès même en cas de setCurrentIndex forcé
        index_view_map = {
            0: 'accueil',
            1: 'dashboard',
            2: 'preaccueil',
            3: 'database',
            4: 'users',
        }

        if index in index_view_map and index_view_map[index] not in self.allowed_views:
            fallback_index = self._get_fallback_allowed_index()
            if fallback_index != index:
                app_logger.warning(
                    f"Accès direct refusé à l'index {index} ({index_view_map[index]}), redirection vers index {fallback_index}"
                )
                self.ui.stackedWidget.setCurrentIndex(fallback_index)
                return

        btn_list = self.ui.icon_only_widget.findChildren(QPushButton) \
                    + self.ui.full_menu_widget.findChildren(QPushButton)
        
        for btn in btn_list:
            # Ne pas modifier les boutons pour search et user
            if index in [5, 6]:
                btn.setAutoExclusive(False)
                btn.setChecked(False)
            else:
                btn.setAutoExclusive(True)
            
    ## functions for changing menu page
    def on_home_btn_1_toggled(self, checked):
        """Affiche la page d'accueil (version courte menu)"""
        if checked:
            self._go_to_view('accueil')
    
    def on_home_btn_2_toggled(self, checked):
        if checked:
            self._go_to_view('accueil')

    def on_dashborad_btn_1_toggled(self, checked):
        if checked:
            self._go_to_view('dashboard')

    def on_dashborad_btn_2_toggled(self, checked):
        if checked:
            self._go_to_view('dashboard')

    def on_orders_btn_1_toggled(self, checked):
        if checked:
            self._go_to_view('preaccueil')

    def on_orders_btn_2_toggled(self, checked):
        if checked:
            self._go_to_view('preaccueil')

    def on_products_btn_1_toggled(self, checked):
        if checked:
            self._go_to_view('database')

    def on_products_btn_2_toggled(self, checked):
        if checked:
            self._go_to_view('database')

    def on_customers_btn_1_toggled(self, checked):
        if checked:
            self._go_to_view('users')

    def on_customers_btn_2_toggled(self, checked):
        if checked:
            self._go_to_view('users')

    def on_change_btn_toggled(self, checked):
        """Toggle entre menu plein et menu réduit
        
        Args:
            checked: État du bouton
        """
        if checked:
            self.ui.full_menu_widget.show()
            self.ui.icon_only_widget.hide()
            app_logger.info("Menu étendu affiché")
        else:
            self.ui.full_menu_widget.hide()
            self.ui.icon_only_widget.show()
            app_logger.info("Menu réduit affiché")

    def closeEvent(self, event):
        """Fermeture propre de la fenêtre et des pages enfants.

        Évite les warnings/crashs liés aux QThread encore actifs dans les widgets.
        """
        child_pages = [
            getattr(self, "accueil_page", None),
            getattr(self, "preaccueil_page", None),
            getattr(self, "database_page", None),
            getattr(self, "dashboard_page", None),
            getattr(self, "users_page", None),
        ]

        for page in child_pages:
            if page is None:
                continue
            try:
                page.close()
            except Exception as close_error:
                app_logger.warning(f"Fermeture page partielle ({type(page).__name__}): {close_error}")

        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Chemin absolu sécurisé vers le style
    style_path = Path(__file__).parent / "style.qss"

    if style_path.exists():
        style_file = QFile(str(style_path))
        style_file.open(
            QIODevice.OpenModeFlag.ReadOnly |
            QIODevice.OpenModeFlag.Text
        )
        style_stream = QTextStream(style_file)
        app.setStyleSheet(style_stream.readAll())
        style_file.close()
    else:
        print("⚠️ style.qss introuvable")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())