# sidebar/main_windows.py
"""Fenêtre principale de l'application avec interface sidebar

Cette fenêtre utilise Ui_MainWindow générée par Qt Designer et ajoute
la logique métier pour la gestion des demandes d'accueil.
"""

import sys 
from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton
from PyQt6.QtCore import pyqtSlot, QFile, QTextStream
from PyQt6.QtCore import QIODevice
from pathlib import Path

# CORRECTION IMPORTANTE: importer depuis le fichier sidebar.py
from sidebar import Ui_MainWindow

class MainWindow(QMainWindow):
    """Fenêtre principale avec gestion des rôles et permissions
    
    Attributs:
        current_user: Dict contenant les infos de l'utilisateur actuellement connecté
        ui: Instance de Ui_MainWindow (interface générée)
    """
    
    def __init__(self):
        super(MainWindow, self).__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.icon_only_widget.hide()
        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.home_btn_2.setChecked(True)
        
        # Variable pour stocker l'utilisateur connecté
        self.current_user = None

    def set_current_user(self, user):
        """Reçoit l'utilisateur connecté depuis main.py
        
        Args:
            user: Dict avec id, username, email, role, role_display
        """
        self.current_user = user
        print(f"✅ Utilisateur connecté à sidebar: {user['username']} - {user['role_display']}")
        self.setWindowTitle(f"CNPS Accueil - {user['role_display']}")
        
        # Vous pouvez adapter l'interface selon le rôle
        role = user['role']
        if role == 'admin':
            print("👑 Mode Administrateur - Accès complet")
        elif role == 'manager':
            print("📊 Mode Manager")
        elif role == 'accueil':
            print("🏢 Mode Agent Accueil")
        elif role == 'preaccueil':
            print("🛂 Mode Pré-accueil")

    ## Function for searching
    def on_search_btn_clicked(self):
        """Déclenche la recherche et affiche les résultats"""
        self.ui.stackedWidget.setCurrentIndex(5)
        search_text = self.ui.search_input.text().strip()
        if search_text:
            self.ui.label_9.setText(search_text)

    ## Function for changing page to user page
    def on_user_btn_clicked(self):
        """Bascule vers la page profil utilisateur"""
        self.ui.stackedWidget.setCurrentIndex(6)

    ## Change QPushButton Checkable status when stackedWidget index changed
    def on_stackedWidget_currentChanged(self, index):
        """Gère les boutons lors du changement d'onglet
        
        Args:
            index: Index du nouvel onglet affiché
        """
        btn_list = self.ui.icon_only_widget.findChildren(QPushButton) \
                    + self.ui.full_menu_widget.findChildren(QPushButton)
        
        for btn in btn_list:
            if index in [5, 6]:
                btn.setAutoExclusive(False)
                btn.setChecked(False)
            else:
                btn.setAutoExclusive(True)
            
    ## functions for changing menu page
    def on_home_btn_1_toggled(self):
        """Affiche la page d'accueil (version courte menu)"""
        self.ui.stackedWidget.setCurrentIndex(0)
    
    def on_home_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    def on_dashborad_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(1)

    def on_dashborad_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(1)

    def on_orders_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(2)

    def on_orders_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(2)

    def on_products_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(3)

    def on_products_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(3)

    def on_customers_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(4)

    def on_customers_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(4)


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