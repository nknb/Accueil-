# ui/main_window.py
import sys
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from datetime import datetime, date, timedelta
from typing import Optional
import uuid

from database.connection import db
from database.models import (
    DemandeAccueil, Service, Motif, 
    Priorite, Statut, Utilisateur, Role, Permission
)
from ui.dashboard import DashboardSimple as DashboardWidget
from ui.demande_widgets import DemandeFormWidget, DemandeTableWidget
from ui.statistics import StatisticsWidget
from ui.permissions import PermissionManager, RoleBasedAccessMixin

class MainWindow(QMainWindow, RoleBasedAccessMixin):
    """Fenêtre principale de l'application avec gestion des rôles"""
    
    def __init__(self):
        super().__init__()
        self.current_user = None
        self.permission_manager = None
        self.init_ui()
        self.setup_shortcuts()
        self.apply_styles()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("Système de Gestion d'Accueil - CNPS")
        self.setMinimumSize(1400, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Barre de titre personnalisée
        self.create_title_bar()
        main_layout.addWidget(self.title_bar)
        
        # Barre d'outils
        self.create_toolbar()
        main_layout.addWidget(self.toolbar)
        
        # Zone de contenu avec onglets
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)
        
        # Création des onglets
        self.create_dashboard_tab()
        self.create_demandes_tab()
        self.create_stats_tab()
        self.create_administration_tab()
        
        # Barre d'état
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Timer pour rafraîchissement automatique
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(60000)  # Rafraîchir toutes les minutes
        
    def set_current_user(self, user):
        """Définit l'utilisateur courant et applique les permissions"""
        self.current_user = user
        if user:
            self.permission_manager = PermissionManager(user)
            self.apply_permissions()
            self.update_user_info()
            self.update_status_bar()
            
    def update_user_info(self):
        """Met à jour les informations utilisateur"""
        if self.current_user:
            role_display = self.current_user.get('role_display', self.current_user.get('role', ''))
            full_name = self.current_user.get('full_name', self.current_user.get('username', ''))
            self.user_info.setText(f"👤 {full_name} | {role_display}")
            
    # ============ GESTION DES PERMISSIONS PAR RÔLE ============
    
    def apply_permissions(self):
        """Applique les permissions selon le rôle de l'utilisateur"""
        if not self.current_user:
            return
        
        role = self.current_user.get('role', '')
        print(f"🔐 Application des permissions pour le rôle: {role}")
        
        # Transmettre le rôle au tableau des demandes
        if hasattr(self, 'demandes_table'):
            self.demandes_table.set_user_role(role)
        
        # Transmettre le rôle au dashboard
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.set_role(role)
        
        # ===== CONFIGURATION SELON LE RÔLE =====
        
        # 🛂 PRÉ-ACCUEIL : Seulement la liste des demandes et création
        if role == 'preaccueil':
            self.show_dashboard_tab(False)      # ❌ Pas de tableau de bord
            self.show_demandes_tab(True)        # ✅ Liste des demandes
            self.show_stats_tab(False)          # ❌ Pas de statistiques
            self.show_admin_tab(False)          # ❌ Pas d'administration
            self.enable_export(False)           # ❌ Pas d'export
            self.enable_nouvelle_demande(True)  # ✅ Peut créer des demandes
            self.enable_actions_demandes(False) # ❌ Pas d'actions sur les demandes
            
            # Message en barre d'état
            self.status_bar.showMessage("🛂 Mode Pré-accueil - Création de demandes uniquement")
            
        # 🏢 ACCUEIL : Dashboard + Demandes (CRUD sauf suppression)
        elif role == 'accueil':
            self.show_dashboard_tab(True)       # ✅ Tableau de bord
            self.show_demandes_tab(True)        # ✅ Liste des demandes
            self.show_stats_tab(False)          # ❌ Pas de statistiques
            self.show_admin_tab(False)          # ❌ Pas d'administration
            self.enable_export(False)           # ❌ Pas d'export
            self.enable_nouvelle_demande(True)  # ✅ Peut créer des demandes
            self.enable_actions_demandes(True)  # ✅ Actions (modifier, traiter)
            self.enable_delete_demandes(False)  # ❌ Pas de suppression
            
            self.status_bar.showMessage("🏢 Mode Accueil - Gestion complète des demandes")
            
        # 📊 MANAGER : Tout sauf administration
        elif role == 'manager':
            self.show_dashboard_tab(True)       # ✅ Tableau de bord
            self.show_demandes_tab(True)        # ✅ Liste des demandes
            self.show_stats_tab(True)           # ✅ Statistiques
            self.show_admin_tab(False)          # ❌ Pas d'administration
            self.enable_export(True)            # ✅ Export
            self.enable_nouvelle_demande(True)  # ✅ Création
            self.enable_actions_demandes(True)  # ✅ Toutes actions
            self.enable_delete_demandes(True)   # ✅ Suppression
            
            self.status_bar.showMessage("📊 Mode Manager - Accès complet sauf administration")
            
        # 👑 ADMIN : Tout
        elif role == 'admin':
            self.show_all_tabs()                # ✅ Tous les onglets
            self.enable_export(True)            # ✅ Export
            self.enable_nouvelle_demande(True)  # ✅ Création
            self.enable_actions_demandes(True)  # ✅ Toutes actions
            self.enable_delete_demandes(True)   # ✅ Suppression
            
            self.status_bar.showMessage("👑 Mode Administrateur - Accès illimité")
    
    def show_all_tabs(self):
        """Affiche tous les onglets"""
        self.show_dashboard_tab(True)
        self.show_demandes_tab(True)
        self.show_stats_tab(True)
        self.show_admin_tab(True)
    
    def show_dashboard_tab(self, visible):
        """Affiche/masque l'onglet tableau de bord"""
        for btn in self.nav_button_group.buttons():
            if "Tableau de bord" in btn.text():
                btn.setVisible(visible)
        if self.content_stack.count() > 0:
            self.content_stack.widget(0).setVisible(visible)
    
    def show_demandes_tab(self, visible):
        """Affiche/masque l'onglet demandes"""
        for btn in self.nav_button_group.buttons():
            if "Demandes" in btn.text():
                btn.setVisible(visible)
        if self.content_stack.count() > 1:
            self.content_stack.widget(1).setVisible(visible)
    
    def show_stats_tab(self, visible):
        """Affiche/masque l'onglet statistiques"""
        for btn in self.nav_button_group.buttons():
            if "Statistiques" in btn.text():
                btn.setVisible(visible)
        if self.content_stack.count() > 2:
            self.content_stack.widget(2).setVisible(visible)
            if hasattr(self, 'stats_widget'):
                self.stats_widget.setVisible(visible)
    
    def show_admin_tab(self, visible):
        """Affiche/masque l'onglet administration"""
        for btn in self.nav_button_group.buttons():
            if "Administration" in btn.text():
                btn.setVisible(visible)
        if self.content_stack.count() > 3:
            self.content_stack.widget(3).setVisible(visible)
    
    def enable_export(self, enabled):
        """Active/désactive l'export de données"""
        if hasattr(self, 'demandes_table'):
            if hasattr(self.demandes_table, 'export_btn'):
                self.demandes_table.export_btn.setVisible(enabled)
        if hasattr(self, 'stats_widget'):
            if hasattr(self.stats_widget, 'export_btn'):
                self.stats_widget.export_btn.setVisible(enabled)
    
    def enable_nouvelle_demande(self, enabled):
        """Active/désactive le bouton Nouvelle demande"""
        if hasattr(self, 'add_demande_btn'):
            self.add_demande_btn.setVisible(enabled)
    
    def enable_actions_demandes(self, enabled):
        """Active/désactive les actions sur les demandes"""
        if hasattr(self, 'demandes_table'):
            self.demandes_table.enable_actions = enabled
    
    def enable_delete_demandes(self, enabled):
        """Active/désactive la suppression des demandes"""
        if hasattr(self, 'demandes_table'):
            self.demandes_table.enable_delete = enabled
    
    # ============ INTERFACE UTILISATEUR ============
    
    def create_title_bar(self):
        """Crée une barre de titre personnalisée"""
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(60)
        self.title_bar.setObjectName("titleBar")
        
        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Logo et titre
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        logo_label = QLabel("🏢")
        logo_label.setStyleSheet("font-size: 28px; color: white;")
        title_layout.addWidget(logo_label)
        
        title_label = QLabel("CNPS - Accueil")
        title_label.setObjectName("appTitle")
        title_layout.addWidget(title_label)
        
        layout.addWidget(title_container)
        layout.addStretch()
        
        # Informations utilisateur
        self.user_info = QLabel()
        self.user_info.setObjectName("userInfo")
        self.user_info.setText("👤 Non connecté")
        layout.addWidget(self.user_info)
        
        # Bouton de déconnexion
        self.logout_btn = QPushButton("🚪 Déconnexion")
        self.logout_btn.setObjectName("logoutButton")
        self.logout_btn.clicked.connect(self.logout)
        layout.addWidget(self.logout_btn)
    
    def create_toolbar(self):
        """Crée la barre d'outils principale"""
        self.toolbar = QFrame()
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setFixedHeight(70)
        
        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Navigation
        nav_buttons = [
            ("📊 Tableau de bord", self.show_dashboard, "dashboard"),
            ("📋 Demandes", self.show_demandes, "demandes"),
            ("📈 Statistiques", self.show_stats, "stats"),
            ("⚙️ Administration", self.show_admin, "admin"),
        ]
        
        self.nav_button_group = QButtonGroup(self)
        
        for label, callback, name in nav_buttons:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName(f"navButton_{name}")
            btn.clicked.connect(callback)
            layout.addWidget(btn)
            self.nav_button_group.addButton(btn)
        
        layout.addStretch()
        
        # Actions rapides - Nouvelle demande
        self.add_demande_btn = QPushButton("➕ Nouvelle demande")
        self.add_demande_btn.setObjectName("actionButton")
        self.add_demande_btn.clicked.connect(self.open_demande_form)
        layout.addWidget(self.add_demande_btn)
        
        # Bouton rafraîchir
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setObjectName("iconButton")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.refresh_btn.setToolTip("Rafraîchir (F5)")
        self.refresh_btn.setFixedSize(45, 45)
        layout.addWidget(self.refresh_btn)
        
        # Bouton aide
        self.help_btn = QPushButton("❓")
        self.help_btn.setObjectName("iconButton")
        self.help_btn.clicked.connect(self.show_help)
        self.help_btn.setToolTip("Aide (F1)")
        self.help_btn.setFixedSize(45, 45)
        layout.addWidget(self.help_btn)
    
    def create_dashboard_tab(self):
        """Crée l'onglet tableau de bord"""
        self.dashboard_widget = DashboardWidget(self)
        self.content_stack.addWidget(self.dashboard_widget)
    
    def create_demandes_tab(self):
        """Crée l'onglet des demandes"""
        demandes_widget = QWidget()
        layout = QVBoxLayout(demandes_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Filtres
        filters_widget = self.create_filters_widget()
        layout.addWidget(filters_widget)
        
        # Tableau des demandes
        self.demandes_table = DemandeTableWidget()
        self.demandes_table.demandes_updated.connect(self.on_demandes_updated)
        layout.addWidget(self.demandes_table)
        
        self.content_stack.addWidget(demandes_widget)
    
    def create_stats_tab(self):
        """Crée l'onglet statistiques"""
        self.stats_widget = StatisticsWidget(self)
        self.content_stack.addWidget(self.stats_widget)
    
    def create_administration_tab(self):
        """Crée l'onglet administration"""
        admin_widget = QWidget()
        layout = QVBoxLayout(admin_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Onglets internes
        tabs = QTabWidget()
        tabs.setObjectName("adminTabs")
        
        # Services
        services_widget = self.create_services_widget()
        tabs.addTab(services_widget, "🏢 Services")
        
        # Motifs
        motifs_widget = self.create_motifs_widget()
        tabs.addTab(motifs_widget, "🏷️ Motifs")
        
        # Utilisateurs
        users_widget = self.create_users_widget()
        tabs.addTab(users_widget, "👥 Utilisateurs")
        
        # Logs
        logs_widget = self.create_logs_widget()
        tabs.addTab(logs_widget, "📋 Journal")
        
        layout.addWidget(tabs)
        self.content_stack.addWidget(admin_widget)
    
    def create_filters_widget(self):
        """Widget de filtres avancés"""
        filters_widget = QFrame()
        filters_widget.setObjectName("filtersWidget")
        
        layout = QHBoxLayout(filters_widget)
        layout.setSpacing(15)
        
        # Date range
        date_range = QWidget()
        date_layout = QHBoxLayout(date_range)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(5)
        
        self.date_debut = QDateEdit()
        self.date_debut.setDate(QDate.currentDate().addDays(-30))
        self.date_debut.setCalendarPopup(True)
        self.date_debut.setDisplayFormat("dd/MM/yyyy")
        date_layout.addWidget(QLabel("Du:"))
        date_layout.addWidget(self.date_debut)
        
        self.date_fin = QDateEdit()
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setCalendarPopup(True)
        self.date_fin.setDisplayFormat("dd/MM/yyyy")
        date_layout.addWidget(QLabel("au:"))
        date_layout.addWidget(self.date_fin)
        
        layout.addWidget(date_range)
        
        # Service
        layout.addWidget(QLabel("Service:"))
        self.service_filter = QComboBox()
        self.service_filter.addItem("📋 Tous les services", None)
        self.refresh_service_filter()
        self.service_filter.setMinimumWidth(150)
        layout.addWidget(self.service_filter)
        
        # Statut
        layout.addWidget(QLabel("Statut:"))
        self.statut_filter = QComboBox()
        self.statut_filter.addItem("📌 Tous les statuts", None)
        for statut in Statut:
            self.statut_filter.addItem(str(statut), statut.value)
        self.statut_filter.setMinimumWidth(150)
        layout.addWidget(self.statut_filter)
        
        # Priorité
        layout.addWidget(QLabel("Priorité:"))
        self.priorite_filter = QComboBox()
        self.priorite_filter.addItem("🎯 Toutes les priorités", None)
        for priorite in Priorite:
            self.priorite_filter.addItem(str(priorite), priorite.value)
        self.priorite_filter.setMinimumWidth(150)
        layout.addWidget(self.priorite_filter)
        
        # Bouton appliquer
        apply_btn = QPushButton("🔍 Appliquer")
        apply_btn.setObjectName("applyFilterButton")
        apply_btn.clicked.connect(self.apply_filters)
        layout.addWidget(apply_btn)
        
        # Bouton réinitialiser
        reset_btn = QPushButton("🔄 Réinitialiser")
        reset_btn.setObjectName("resetFilterButton")
        reset_btn.clicked.connect(self.reset_filters)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
        
        # Recherche
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un nom, CNPS, contact...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        layout.addWidget(self.search_input)
        
        return filters_widget
    
    # ============ GESTION DES DEMANDES ============
    
    def open_demande_form(self, demande: Optional[DemandeAccueil] = None):
        """Ouvre le formulaire de demande - Adapté selon le rôle"""
        role = self.current_user.get('role', '') if self.current_user else ''
        
        # 🛂 PRÉ-ACCUEIL : Formulaire simplifié
        if role == 'preaccueil':
            self.open_demande_form_simplified()
        else:
            # Autres rôles : Formulaire complet
            self.open_demande_form_complete(demande)
    
    def open_demande_form_simplified(self):
        """Formulaire simplifié pour le pré-accueil"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🛂 Nouvelle demande d'accueil - Pré-accueil")
        dialog.setModal(True)
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(550)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ===== EN-TÊTE =====
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #17a2b8, stop:1 #138496);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 25px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        icon_label = QLabel("🛂")
        icon_label.setStyleSheet("font-size: 36px; color: white;")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel("Nouvelle demande - Pré-accueil")
        title_label.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: white;
            margin-left: 15px;
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addWidget(header)
        
        # ===== FORMULAIRE SIMPLIFIÉ =====
        form_container = QWidget()
        form_container.setStyleSheet("""
            QWidget {
                background-color: white;
                padding: 30px;
            }
        """)
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(25)
        form_layout.setContentsMargins(40, 40, 40, 40)
        
        # Style commun pour les inputs
        input_style = """
            QLineEdit, QComboBox, QTimeEdit {
                border: 2px solid #dee2e6;
                border-radius: 10px;
                padding: 12px 15px;
                font-size: 14px;
                background-color: white;
                min-width: 300px;
            }
            QLineEdit:focus, QComboBox:focus, QTimeEdit:focus {
                border-color: #17a2b8;
                border-width: 2px;
            }
            QLineEdit:hover, QComboBox:hover, QTimeEdit:hover {
                border-color: #6c757d;
            }
        """
        
        # Nom
        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Nom du client")
        self.nom_input.setMinimumHeight(45)
        self.nom_input.setStyleSheet(input_style)
        form_layout.addRow("👤 Nom *:", self.nom_input)
        
        # Prénom
        self.prenom_input = QLineEdit()
        self.prenom_input.setPlaceholderText("Prénom du client")
        self.prenom_input.setMinimumHeight(45)
        self.prenom_input.setStyleSheet(input_style)
        form_layout.addRow("👤 Prénom *:", self.prenom_input)
        
        # Service
        self.service_combo = QComboBox()
        self.service_combo.setMinimumHeight(45)
        self.refresh_service_combo()
        self.service_combo.setStyleSheet(input_style)
        form_layout.addRow("🏢 Service *:", self.service_combo)
        
        # Motif
        self.motif_combo = QComboBox()
        self.motif_combo.setMinimumHeight(45)
        self.refresh_motif_combo()
        self.motif_combo.setStyleSheet(input_style)
        form_layout.addRow("📋 Motif *:", self.motif_combo)
        
        # Heure d'arrivée
        self.heure_arrivee = QTimeEdit()
        self.heure_arrivee.setTime(QTime.currentTime())
        self.heure_arrivee.setDisplayFormat("HH:mm:ss")
        self.heure_arrivee.setMinimumHeight(45)
        self.heure_arrivee.setStyleSheet(input_style)
        form_layout.addRow("⏰ Heure d'arrivée *:", self.heure_arrivee)
        
        # Message d'information
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f4f8;
                border-radius: 10px;
                padding: 15px;
                margin-top: 20px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        
        info_icon = QLabel("ℹ️")
        info_icon.setStyleSheet("font-size: 20px;")
        info_layout.addWidget(info_icon)
        
        info_text = QLabel("Les autres informations seront complétées par l'agent d'accueil")
        info_text.setStyleSheet("""
            color: #17a2b8;
            font-size: 14px;
            font-weight: 500;
        """)
        info_layout.addWidget(info_text)
        info_layout.addStretch()
        
        form_layout.addRow(info_frame)
        
        layout.addWidget(form_container)
        
        # ===== BOUTONS =====
        buttons_container = QWidget()
        buttons_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                padding: 20px 30px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(20, 10, 20, 10)
        
        cancel_btn = QPushButton("❌ Annuler")
        cancel_btn.setMinimumHeight(50)
        cancel_btn.setMinimumWidth(150)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(cancel_btn)
        
        buttons_layout.addStretch()
        
        save_btn = QPushButton("✅ Enregistrer la demande")
        save_btn.setMinimumHeight(50)
        save_btn.setMinimumWidth(250)
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #28a745, stop:1 #218838);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #218838, stop:1 #1e7e34);
            }
        """)
        save_btn.clicked.connect(dialog.accept)
        buttons_layout.addWidget(save_btn)
        
        layout.addWidget(buttons_container)
        
        # Sauvegarde
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_simplified_demande()
    
    def save_simplified_demande(self):
        """Sauvegarde une demande simplifiée (pré-accueil)"""
        try:
            # Validation
            if not self.nom_input.text().strip():
                QMessageBox.warning(self, "⚠️ Attention", "Le nom est obligatoire")
                return
            if not self.prenom_input.text().strip():
                QMessageBox.warning(self, "⚠️ Attention", "Le prénom est obligatoire")
                return
            if not self.service_combo.currentData():
                QMessageBox.warning(self, "⚠️ Attention", "Veuillez sélectionner un service")
                return
            if not self.motif_combo.currentData():
                QMessageBox.warning(self, "⚠️ Attention", "Veuillez sélectionner un motif")
                return
            
            demande = DemandeAccueil()
            demande.nom = self.nom_input.text().strip()
            demande.prenom = self.prenom_input.text().strip()
            demande.service_demande_id = self.service_combo.currentData()
            demande.motif_id = self.motif_combo.currentData()
            demande.heure_arrivee = self.heure_arrivee.time().toPyTime()
            demande.statut = 'en_attente'
            demande.priorite = 'normale'
            
            if demande.save():
                self.refresh_demandes()
                self.log_action("CREATE_DEMANDE", f"Demande créée par pré-accueil: {demande.nom} {demande.prenom}")
                
                QMessageBox.information(
                    self, 
                    "✅ Succès", 
                    "✅ La demande a été enregistrée avec succès !\n\n"
                    "Elle sera traitée par un agent d'accueil.",
                    QMessageBox.StandardButton.Ok
                )
            else:
                QMessageBox.critical(self, "❌ Erreur", "Impossible d'enregistrer la demande")
                
        except Exception as e:
            QMessageBox.critical(self, "❌ Erreur", f"Erreur lors de l'enregistrement:\n{str(e)}")
    
    def open_demande_form_complete(self, demande: Optional[DemandeAccueil] = None):
        """Formulaire complet pour les autres rôles"""
        from ui.demande_widgets import DemandeFormWidget
        
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Nouvelle demande" if not demande else "✏️ Modification de la demande")
        dialog.setModal(True)
        dialog.setMinimumWidth(900)
        dialog.setMinimumHeight(700)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # En-tête
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #417690, stop:1 #2d5a6e);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 25px;
            }
        """)
        header_layout = QHBoxLayout(header)
        
        icon_label = QLabel("📋")
        icon_label.setStyleSheet("font-size: 36px; color: white;")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel("Nouvelle demande d'accueil" if not demande else "Modification de la demande")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white; margin-left: 15px;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addWidget(header)
        
        # Formulaire
        form_container = QWidget()
        form_container.setStyleSheet("background-color: white; padding: 30px;")
        form_layout = QVBoxLayout(form_container)
        
        form = DemandeFormWidget(demande)
        form_layout.addWidget(form)
        
        layout.addWidget(form_container)
        
        # Boutons
        buttons_container = QWidget()
        buttons_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                padding: 20px 30px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        
        cancel_btn = QPushButton("❌ Annuler")
        cancel_btn.setMinimumHeight(50)
        cancel_btn.setMinimumWidth(150)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(cancel_btn)
        
        buttons_layout.addStretch()
        
        save_btn = QPushButton("✅ Enregistrer")
        save_btn.setMinimumHeight(50)
        save_btn.setMinimumWidth(200)
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #28a745, stop:1 #218838);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #218838, stop:1 #1e7e34);
            }
        """)
        save_btn.clicked.connect(dialog.accept)
        buttons_layout.addWidget(save_btn)
        
        layout.addWidget(buttons_container)
        
        if dialog.exec() == QDialog.DialogCode.Accepted and form.save():
            self.refresh_demandes()
            self.log_action("CREATE_DEMANDE" if not demande else "EDIT_DEMANDE", 
                          f"Demande {'créée' if not demande else 'modifiée'}")
            QMessageBox.information(
                self, 
                "✅ Succès", 
                "La demande a été enregistrée avec succès !",
                QMessageBox.StandardButton.Ok
            )
    
    def refresh_service_combo(self):
        """Rafraîchit la liste des services"""
        self.service_combo.clear()
        try:
            services = Service.get_all(actif_only=True)
            for service in services:
                self.service_combo.addItem(service.nom, service.id)
        except Exception as e:
            print(f"Erreur chargement services: {e}")
    
    def refresh_motif_combo(self):
        """Rafraîchit la liste des motifs"""
        self.motif_combo.clear()
        try:
            motifs = Motif.get_all(actif_only=True)
            for motif in motifs:
                self.motif_combo.addItem(motif.nom, motif.id)
        except Exception as e:
            print(f"Erreur chargement motifs: {e}")
    
    # ============ FILTRES ET RECHERCHE ============
    
    def refresh_service_filter(self):
        """Rafraîchit la liste des services dans le filtre"""
        self.service_filter.clear()
        self.service_filter.addItem("📋 Tous les services", None)
        try:
            services = Service.get_all(actif_only=True)
            for service in services:
                self.service_filter.addItem(service.nom, service.id)
        except Exception as e:
            print(f"Erreur chargement services: {e}")
    
    def apply_filters(self):
        """Applique les filtres"""
        filters = {
            'date_debut': self.date_debut.date().toPyDate(),
            'date_fin': self.date_fin.date().toPyDate(),
            'service_id': self.service_filter.currentData(),
            'statut': self.statut_filter.currentData(),
            'priorite': self.priorite_filter.currentData()
        }
        if hasattr(self, 'demandes_table'):
            self.demandes_table.apply_filters(filters)
    
    def reset_filters(self):
        """Réinitialise les filtres"""
        self.date_debut.setDate(QDate.currentDate().addDays(-30))
        self.date_fin.setDate(QDate.currentDate())
        self.service_filter.setCurrentIndex(0)
        self.statut_filter.setCurrentIndex(0)
        self.priorite_filter.setCurrentIndex(0)
        self.search_input.clear()
        self.apply_filters()
    
    def on_search_text_changed(self, text):
        """Gère la recherche en temps réel"""
        if hasattr(self, 'demandes_table'):
            self.demandes_table.search(text)
    
    def on_demandes_updated(self):
        """Callback quand les demandes sont mises à jour"""
        self.update_status_bar()
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.refresh()
        if hasattr(self, 'stats_widget'):
            self.stats_widget.refresh()
    
    # ============ RAFRAÎCHISSEMENT ============
    
    def refresh_data(self):
        """Rafraîchit toutes les données"""
        self.refresh_demandes()
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.refresh()
        if hasattr(self, 'stats_widget'):
            self.stats_widget.refresh()
        self.update_status_bar()
    
    def refresh_demandes(self):
        """Rafraîchit la liste des demandes"""
        if hasattr(self, 'demandes_table'):
            self.demandes_table.refresh()
    
    def auto_refresh(self):
        """Rafraîchissement automatique"""
        if self.isVisible():
            self.refresh_demandes()
            self.update_status_bar()
    
    def update_status_bar(self):
        """Met à jour la barre d'état"""
        try:
            today = date.today()
            demandes_aujourdhui = DemandeAccueil.get_all({
                'date_debut': today,
                'date_fin': today
            })
            
            en_attente = len([d for d in demandes_aujourdhui if d.statut == 'en_attente'])
            en_cours = len([d for d in demandes_aujourdhui if d.statut == 'en_cours'])
            traitees = len([d for d in demandes_aujourdhui if d.statut == 'traite'])
            urgentes = len([d for d in demandes_aujourdhui if d.priorite == 'haute'])
            
            now = QDateTime.currentDateTime().toString("HH:mm:ss")
            
            status_text = f"📅 {today.strftime('%d/%m/%Y')} | 🕐 {now} | "
            status_text += f"📋 Demandes: {len(demandes_aujourdhui)} | "
            status_text += f"⏳ En attente: {en_attente} | "
            status_text += f"🔄 En cours: {en_cours} | "
            status_text += f"✅ Traitées: {traitees} | "
            status_text += f"🔴 Urgentes: {urgentes}"
            
            if self.current_user:
                status_text += f" | 👤 {self.current_user.get('username', '')}"
            
            self.status_bar.showMessage(status_text)
            
        except Exception as e:
            self.status_bar.showMessage(f"📅 {date.today().strftime('%d/%m/%Y')} | Système prêt")
    
    # ============ ADMINISTRATION ============
    
    def create_services_widget(self):
        """Widget de gestion des services"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Barre d'outils
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 10)
        
        add_btn = QPushButton("➕ Nouveau service")
        add_btn.setObjectName("actionButton")
        add_btn.clicked.connect(self.add_service)
        toolbar_layout.addWidget(add_btn)
        
        toolbar_layout.addStretch()
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.clicked.connect(self.refresh_services)
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addWidget(toolbar)
        
        # Tableau des services
        self.services_table = QTableWidget()
        self.services_table.setColumnCount(5)
        self.services_table.setHorizontalHeaderLabels(["ID", "Nom", "Description", "Couleur", "Actions"])
        self.services_table.horizontalHeader().setStretchLastSection(True)
        self.services_table.setAlternatingRowColors(True)
        self.services_table.setSortingEnabled(True)
        
        layout.addWidget(self.services_table)
        
        self.refresh_services()
        return widget
    
    def refresh_services(self):
        """Rafraîchit la liste des services"""
        try:
            services = Service.get_all(actif_only=False)
            self.services_table.setRowCount(len(services))
            
            for i, service in enumerate(services):
                self.services_table.setItem(i, 0, QTableWidgetItem(str(service.id)))
                self.services_table.setItem(i, 1, QTableWidgetItem(service.nom))
                self.services_table.setItem(i, 2, QTableWidgetItem(service.description[:100] + "..." if service.description and len(service.description) > 100 else service.description))
                
                # Couleur
                color_widget = QWidget()
                color_layout = QHBoxLayout(color_widget)
                color_layout.setContentsMargins(0, 0, 0, 0)
                color_layout.setSpacing(5)
                
                color_label = QLabel()
                color_label.setFixedSize(20, 20)
                color_label.setStyleSheet(f"background-color: {service.couleur}; border-radius: 10px; border: 1px solid #dee2e6;")
                color_layout.addWidget(color_label)
                
                color_text = QLabel(service.couleur)
                color_layout.addWidget(color_text)
                color_layout.addStretch()
                
                self.services_table.setCellWidget(i, 3, color_widget)
                
                # Actions
                actions_widget = self.create_service_actions_widget(service)
                self.services_table.setCellWidget(i, 4, actions_widget)
                
            self.refresh_service_filter()
            
        except Exception as e:
            print(f"Erreur rafraîchissement services: {e}")
    
    def create_service_actions_widget(self, service):
        """Crée les actions pour un service"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(35, 35)
        edit_btn.setToolTip("Modifier")
        edit_btn.clicked.connect(lambda checked, s=service: self.edit_service(s))
        layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(35, 35)
        delete_btn.setToolTip("Supprimer")
        delete_btn.clicked.connect(lambda checked, s=service: self.delete_service(s))
        layout.addWidget(delete_btn)
        
        return widget
    
    def add_service(self):
        """Ajoute un nouveau service"""
        dialog = self.create_service_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "✅ Succès", "Service ajouté avec succès!")
            self.refresh_services()
    
    def edit_service(self, service):
        """Modifie un service"""
        dialog = self.create_service_dialog(service)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "✅ Succès", f"Service '{service.nom}' modifié avec succès!")
            self.refresh_services()
    
    def delete_service(self, service):
        """Supprime un service"""
        reply = QMessageBox.question(
            self,
            "🗑️ Confirmation",
            f"Voulez-vous vraiment supprimer le service '{service.nom}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "✅ Succès", f"Service '{service.nom}' supprimé!")
            self.refresh_services()
    
    def create_service_dialog(self, service=None):
        """Crée un dialogue pour service"""
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Nouveau service" if not service else "✏️ Modifier le service")
        dialog.setModal(True)
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        header = QLabel("🏢 Service" if not service else f"✏️ {service.nom}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #417690; padding: 10px;")
        layout.addWidget(header)
        
        form = QFormLayout()
        form.setSpacing(15)
        
        nom_input = QLineEdit()
        if service:
            nom_input.setText(service.nom)
        form.addRow("Nom *:", nom_input)
        
        desc_input = QTextEdit()
        desc_input.setMaximumHeight(100)
        if service:
            desc_input.setPlainText(service.description)
        form.addRow("Description:", desc_input)
        
        couleur_input = QLineEdit()
        couleur_input.setText(service.couleur if service else "#417690")
        form.addRow("Couleur:", couleur_input)
        
        actif_check = QCheckBox("Service actif")
        actif_check.setChecked(service.actif if service else True)
        form.addRow(actif_check)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        return dialog
    
    def create_motifs_widget(self):
        """Widget de gestion des motifs"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 10)
        
        add_btn = QPushButton("➕ Nouveau motif")
        add_btn.clicked.connect(self.add_motif)
        toolbar_layout.addWidget(add_btn)
        
        toolbar_layout.addStretch()
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.clicked.connect(self.refresh_motifs)
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addWidget(toolbar)
        
        self.motifs_table = QTableWidget()
        self.motifs_table.setColumnCount(6)
        self.motifs_table.setHorizontalHeaderLabels(["ID", "Nom", "Description", "Priorité", "Actif", "Actions"])
        self.motifs_table.horizontalHeader().setStretchLastSection(True)
        self.motifs_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.motifs_table)
        
        self.refresh_motifs()
        return widget
    
    def refresh_motifs(self):
        """Rafraîchit la liste des motifs"""
        try:
            motifs = Motif.get_all(actif_only=False)
            self.motifs_table.setRowCount(len(motifs))
            
            for i, motif in enumerate(motifs):
                self.motifs_table.setItem(i, 0, QTableWidgetItem(str(motif.id)))
                self.motifs_table.setItem(i, 1, QTableWidgetItem(motif.nom))
                self.motifs_table.setItem(i, 2, QTableWidgetItem(motif.description[:100] + "..." if motif.description and len(motif.description) > 100 else motif.description))
                self.motifs_table.setItem(i, 3, QTableWidgetItem(motif.priorite_defaut))
                self.motifs_table.setItem(i, 4, QTableWidgetItem("✅ Actif" if motif.actif else "❌ Inactif"))
                
                actions_widget = self.create_motif_actions_widget(motif)
                self.motifs_table.setCellWidget(i, 5, actions_widget)
                
        except Exception as e:
            print(f"Erreur motifs: {e}")
    
    def create_motif_actions_widget(self, motif):
        """Crée les actions pour un motif"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(35, 35)
        edit_btn.clicked.connect(lambda checked, m=motif: self.edit_motif(m))
        layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(35, 35)
        delete_btn.clicked.connect(lambda checked, m=motif: self.delete_motif(m))
        layout.addWidget(delete_btn)
        
        return widget
    
    def add_motif(self):
        """Ajoute un nouveau motif"""
        dialog = self.create_motif_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "✅ Succès", "Motif ajouté avec succès!")
            self.refresh_motifs()
    
    def edit_motif(self, motif):
        """Modifie un motif"""
        dialog = self.create_motif_dialog(motif)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "✅ Succès", f"Motif '{motif.nom}' modifié!")
            self.refresh_motifs()
    
    def delete_motif(self, motif):
        """Supprime un motif"""
        reply = QMessageBox.question(
            self,
            "🗑️ Confirmation",
            f"Supprimer le motif '{motif.nom}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "✅ Succès", "Motif supprimé!")
            self.refresh_motifs()
    
    def create_motif_dialog(self, motif=None):
        """Crée un dialogue pour motif"""
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Nouveau motif" if not motif else "✏️ Modifier le motif")
        dialog.setModal(True)
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        header = QLabel("🏷️ Motif" if not motif else f"✏️ {motif.nom}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #417690; padding: 10px;")
        layout.addWidget(header)
        
        form = QFormLayout()
        form.setSpacing(15)
        
        nom_input = QLineEdit()
        if motif:
            nom_input.setText(motif.nom)
        form.addRow("Nom *:", nom_input)
        
        desc_input = QTextEdit()
        desc_input.setMaximumHeight(100)
        if motif:
            desc_input.setPlainText(motif.description)
        form.addRow("Description:", desc_input)
        
        priorite_combo = QComboBox()
        for priorite in Priorite:
            priorite_combo.addItem(str(priorite), priorite.value)
        if motif:
            index = priorite_combo.findData(motif.priorite_defaut)
            if index >= 0:
                priorite_combo.setCurrentIndex(index)
        form.addRow("Priorité:", priorite_combo)
        
        actif_check = QCheckBox("Motif actif")
        actif_check.setChecked(motif.actif if motif else True)
        form.addRow(actif_check)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        return dialog
    
    def create_users_widget(self):
        """Widget de gestion des utilisateurs"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 10)
        
        add_btn = QPushButton("➕ Nouvel utilisateur")
        add_btn.clicked.connect(self.add_user)
        toolbar_layout.addWidget(add_btn)
        
        toolbar_layout.addStretch()
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.clicked.connect(self.refresh_users)
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addWidget(toolbar)
        
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels(["ID", "Nom", "Prénom", "Username", "Email", "Rôle", "Actions"])
        self.users_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.users_table)
        
        self.refresh_users()
        return widget
    
    def refresh_users(self):
        """Rafraîchit la liste des utilisateurs"""
        try:
            users = db.execute_query("SELECT * FROM auth_user ORDER BY role, username")
            self.users_table.setRowCount(len(users))
            
            for i, user in enumerate(users):
                self.users_table.setItem(i, 0, QTableWidgetItem(str(user['id'])[:8]))
                self.users_table.setItem(i, 1, QTableWidgetItem(user.get('nom', '')))
                self.users_table.setItem(i, 2, QTableWidgetItem(user.get('prenom', '')))
                self.users_table.setItem(i, 3, QTableWidgetItem(user['username']))
                self.users_table.setItem(i, 4, QTableWidgetItem(user.get('email', '')))
                self.users_table.setItem(i, 5, QTableWidgetItem(str(Role(user['role']))))
                
                actions_widget = self.create_user_actions_widget(user)
                self.users_table.setCellWidget(i, 6, actions_widget)
                
        except Exception as e:
            print(f"Erreur utilisateurs: {e}")
    
    def create_user_actions_widget(self, user):
        """Crée les actions pour un utilisateur"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(35, 35)
        edit_btn.clicked.connect(lambda: self.edit_user(user))
        layout.addWidget(edit_btn)
        
        if user['username'] != 'admin':
            delete_btn = QPushButton("🗑️")
            delete_btn.setFixedSize(35, 35)
            delete_btn.clicked.connect(lambda: self.delete_user(user))
            layout.addWidget(delete_btn)
        
        return widget
    
    def add_user(self):
        """Ajoute un nouvel utilisateur"""
        dialog = self.create_user_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "✅ Succès", "Utilisateur créé!")
            self.refresh_users()
    
    def edit_user(self, user):
        """Modifie un utilisateur"""
        dialog = self.create_user_dialog(user)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "✅ Succès", f"Utilisateur '{user['username']}' modifié!")
            self.refresh_users()
    
    def delete_user(self, user):
        """Supprime un utilisateur"""
        reply = QMessageBox.question(
            self,
            "🗑️ Confirmation",
            f"Supprimer l'utilisateur '{user['username']}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "✅ Succès", "Utilisateur supprimé!")
            self.refresh_users()
    
    def create_user_dialog(self, user=None):
        """Crée un dialogue pour utilisateur"""
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Nouvel utilisateur" if not user else "✏️ Modifier l'utilisateur")
        dialog.setModal(True)
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout(dialog)
        
        header = QLabel("👥 Utilisateur" if not user else f"✏️ {user['username']}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #417690; padding: 10px;")
        layout.addWidget(header)
        
        form = QFormLayout()
        form.setSpacing(15)
        
        username_input = QLineEdit()
        if user:
            username_input.setText(user['username'])
            username_input.setEnabled(False)
        form.addRow("Username *:", username_input)
        
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if not user:
            password_input.setPlaceholderText("Minimum 8 caractères")
        form.addRow("Mot de passe:", password_input)
        
        nom_input = QLineEdit()
        if user:
            nom_input.setText(user.get('nom', ''))
        form.addRow("Nom:", nom_input)
        
        prenom_input = QLineEdit()
        if user:
            prenom_input.setText(user.get('prenom', ''))
        form.addRow("Prénom:", prenom_input)
        
        email_input = QLineEdit()
        if user:
            email_input.setText(user.get('email', ''))
        form.addRow("Email:", email_input)
        
        role_combo = QComboBox()
        roles = [
            ("👑 Administrateur", "admin"),
            ("📊 Manager", "manager"),
            ("🏢 Agent accueil", "accueil"),
            ("🛂 Agent pré-accueil", "preaccueil"),
        ]
        for label, value in roles:
            role_combo.addItem(label, value)
        if user:
            index = role_combo.findData(user['role'])
            if index >= 0:
                role_combo.setCurrentIndex(index)
        form.addRow("Rôle *:", role_combo)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        return dialog
    
    def create_logs_widget(self):
        """Widget de journalisation"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(5)
        self.logs_table.setHorizontalHeaderLabels(["Date/Heure", "Utilisateur", "Niveau", "Action", "Détails"])
        self.logs_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.logs_table)
        
        self.refresh_logs()
        return widget
    
    def refresh_logs(self):
        """Rafraîchit les logs"""
        self.logs_table.setRowCount(10)
        logs = [
            ("2024-01-15 09:23:45", "admin", "SUCCÈS", "Connexion", "Connexion réussie"),
            ("2024-01-15 09:25:12", "admin", "INFO", "Création", "Nouvelle demande #12345"),
            ("2024-01-15 09:30:01", "accueil", "SUCCÈS", "Traitement", "Demande #12345 traitée"),
        ]
        
        for i, (date, user, level, action, details) in enumerate(logs):
            self.logs_table.setItem(i, 0, QTableWidgetItem(date))
            self.logs_table.setItem(i, 1, QTableWidgetItem(user))
            self.logs_table.setItem(i, 2, QTableWidgetItem(level))
            self.logs_table.setItem(i, 3, QTableWidgetItem(action))
            self.logs_table.setItem(i, 4, QTableWidgetItem(details))
    
    # ============ RACCOURCIS ============
    
    def setup_shortcuts(self):
        """Configure les raccourcis clavier"""
        QShortcut(QKeySequence("Ctrl+N"), self, self.open_demande_form)
        QShortcut(QKeySequence("Ctrl+F"), self, self.focus_search)
        QShortcut(QKeySequence("F5"), self, self.refresh_data)
        QShortcut(QKeySequence("Ctrl+D"), self, lambda: self.show_dashboard())
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self.show_demandes())
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: self.show_stats())
        QShortcut(QKeySequence("F1"), self, self.show_help)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
    
    def focus_search(self):
        """Focus sur le champ de recherche"""
        if hasattr(self, 'search_input'):
            self.search_input.setFocus()
            self.search_input.selectAll()
    
    # ============ AFFICHAGE DES ONGLETS ============
    
    def show_dashboard(self):
        """Affiche le tableau de bord"""
        self.content_stack.setCurrentIndex(0)
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.refresh()
        self.update_nav_buttons("dashboard")
    
    def show_demandes(self):
        """Affiche la liste des demandes"""
        self.content_stack.setCurrentIndex(1)
        self.refresh_demandes()
        self.update_nav_buttons("demandes")
    
    def show_stats(self):
        """Affiche les statistiques"""
        self.content_stack.setCurrentIndex(2)
        if hasattr(self, 'stats_widget'):
            self.stats_widget.refresh()
        self.update_nav_buttons("stats")
    
    def show_admin(self):
        """Affiche l'administration"""
        self.content_stack.setCurrentIndex(3)
        self.refresh_services()
        self.refresh_motifs()
        self.refresh_users()
        self.refresh_logs()
        self.update_nav_buttons("admin")
    
    def update_nav_buttons(self, active_tab):
        """Met à jour l'état des boutons de navigation"""
        for btn in self.nav_button_group.buttons():
            btn.setChecked(active_tab in btn.text().lower())
    
    # ============ AIDE ============
    
    def show_help(self):
        """Affiche l'aide"""
        role = self.current_user.get('role', '') if self.current_user else ''
        
        help_text = f"""
        <h2>Aide - Système de Gestion d'Accueil CNPS</h2>
        
        <h3>👤 Votre rôle : {self.current_user.get('role_display', role) if self.current_user else 'Non connecté'}</h3>
        
        <h3>📋 Fonctionnalités disponibles :</h3>
        <ul>
        """
        
        if role == 'preaccueil':
            help_text += """
            <li>✅ Créer des nouvelles demandes (nom, prénom, service, motif, heure)</li>
            <li>✅ Consulter toutes les demandes</li>
            <li>❌ Modifier les demandes</li>
            <li>❌ Traiter les demandes</li>
            <li>❌ Supprimer les demandes</li>
            <li>❌ Tableau de bord</li>
            <li>❌ Statistiques</li>
            <li>❌ Administration</li>
            """
        elif role == 'accueil':
            help_text += """
            <li>✅ Créer, modifier et traiter les demandes</li>
            <li>✅ Tableau de bord</li>
            <li>❌ Supprimer les demandes</li>
            <li>❌ Statistiques</li>
            <li>❌ Export</li>
            <li>❌ Administration</li>
            """
        elif role == 'manager':
            help_text += """
            <li>✅ Gestion complète des demandes (créer, modifier, traiter, supprimer)</li>
            <li>✅ Tableau de bord</li>
            <li>✅ Statistiques et export</li>
            <li>❌ Administration (services, motifs, utilisateurs)</li>
            """
        elif role == 'admin':
            help_text += """
            <li>✅ TOUTES les fonctionnalités</li>
            <li>✅ Gestion des services</li>
            <li>✅ Gestion des motifs</li>
            <li>✅ Gestion des utilisateurs</li>
            <li>✅ Journal des activités</li>
            """
        
        help_text += """
        </ul>
        
        <h3>🔑 Raccourcis clavier :</h3>
        <ul>
            <li><b>Ctrl+N</b> : Nouvelle demande</li>
            <li><b>Ctrl+F</b> : Rechercher</li>
            <li><b>F5</b> : Rafraîchir</li>
            <li><b>Ctrl+D</b> : Tableau de bord</li>
            <li><b>Ctrl+L</b> : Demandes</li>
            <li><b>Ctrl+S</b> : Statistiques</li>
            <li><b>F1</b> : Aide</li>
            <li><b>Ctrl+Q</b> : Quitter</li>
        </ul>
        
        <p><i>Version 2.0.0 - © CNPS 2024</i></p>
        """
        
        QMessageBox.information(self, "❓ Aide - CNPS Accueil", help_text)
    
    # ============ DÉCONNEXION ============
    
    def logout(self):
        """Déconnexion"""
        reply = QMessageBox.question(
            self,
            "🚪 Déconnexion",
            "Voulez-vous vraiment vous déconnecter ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            username = self.current_user.get('username', '') if self.current_user else ''
            self.log_action("LOGOUT", f"Déconnexion: {username}")
            
            self.current_user = None
            self.close()
            
            from ui.login_dialog import LoginDialog
            login = LoginDialog()
            if login.exec() == QDialog.DialogCode.Accepted:
                self.set_current_user(login.user)
                self.show()
                self.show_dashboard()
                self.log_action("LOGIN", f"Connexion: {login.user.get('username', '')}")
            else:
                sys.exit(0)
    
    # ============ JOURNALISATION ============
    
    def log_action(self, action, details):
        """Journalise une action"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        username = self.current_user.get('username', 'system') if self.current_user else 'system'
        print(f"[{timestamp}] {username} - {action}: {details}")
    
    # ============ STYLES ============
    
    def apply_styles(self):
        """Applique les styles CSS"""
        style = """
        QMainWindow {
            background-color: #f5f7fa;
        }
        
        #titleBar {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #417690, stop:1 #2d5a6e);
            border-bottom: 1px solid #1e3f4f;
        }
        
        #appTitle {
            color: white;
            font-size: 20px;
            font-weight: bold;
            padding-left: 15px;
        }
        
        #userInfo {
            color: white;
            padding: 8px 20px;
            background-color: rgba(255,255,255,0.15);
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
        }
        
        #logoutButton {
            background-color: rgba(220, 53, 69, 0.9);
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
            margin-left: 15px;
        }
        
        #logoutButton:hover {
            background-color: #dc3545;
        }
        
        #mainToolbar {
            background-color: white;
            border-bottom: 2px solid #e9ecef;
        }
        
        #navButton_dashboard, #navButton_demandes, #navButton_stats, #navButton_admin {
            background-color: transparent;
            border: none;
            padding: 12px 25px;
            color: #6c757d;
            font-weight: 600;
            font-size: 14px;
            border-radius: 0;
        }
        
        #navButton_dashboard:checked, #navButton_demandes:checked, 
        #navButton_stats:checked, #navButton_admin:checked {
            color: #417690;
            border-bottom: 4px solid #417690;
            background-color: rgba(65, 118, 144, 0.05);
        }
        
        #actionButton {
            background-color: #28a745;
            color: white;
            border: none;
            padding: 10px 25px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 14px;
        }
        
        #actionButton:hover {
            background-color: #218838;
        }
        
        #iconButton {
            background-color: transparent;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            font-size: 18px;
        }
        
        #iconButton:hover {
            background-color: #f8f9fa;
            border-color: #adb5bd;
        }
        
        #filtersWidget {
            background-color: white;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        #searchInput {
            padding: 10px 20px;
            border: 2px solid #e9ecef;
            border-radius: 25px;
            min-width: 280px;
            font-size: 14px;
        }
        
        #searchInput:focus {
            border-color: #417690;
            outline: none;
        }
        
        QStatusBar {
            background-color: white;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
            padding: 8px;
            font-size: 13px;
        }
        
        QTableWidget {
            border: 1px solid #e9ecef;
            border-radius: 8px;
            background-color: white;
            gridline-color: #f1f3f5;
        }
        
        QTableWidget::item {
            padding: 12px;
            border-bottom: 1px solid #f1f3f5;
        }
        
        QTableWidget::item:selected {
            background-color: rgba(65, 118, 144, 0.1);
            color: #212529;
        }
        
        QHeaderView::section {
            background-color: #f8f9fa;
            padding: 12px;
            border: none;
            border-bottom: 2px solid #dee2e6;
            font-weight: 600;
            color: #495057;
        }
        """
        
        self.setStyleSheet(style)
    
    # ============ ÉVÉNEMENTS ============
    
    def closeEvent(self, event):
        """Gère la fermeture de la fenêtre"""
        if self.current_user:
            self.log_action("LOGOUT", f"Fermeture application: {self.current_user.get('username', '')}")
        event.accept()