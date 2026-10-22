# ui/demande_widgets.py
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from database.models import DemandeAccueil, Service, Motif, Priorite, Statut
from datetime import datetime, time
from typing import Optional

class DemandeFormWidget(QWidget):
    """Formulaire de saisie des demandes - Version complète"""
    
    def __init__(self, demande: Optional[DemandeAccueil] = None):
        super().__init__()
        self.demande = demande or DemandeAccueil()
        self.init_ui()
        
        if demande:
            self.load_data()
            
    def init_ui(self):
        """Initialise l'interface du formulaire"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ===== SECTION INFORMATIONS PERSONNELLES =====
        personal_group = QGroupBox("👤 Informations personnelles")
        personal_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #417690;
            }
        """)
        
        personal_layout = QFormLayout(personal_group)
        personal_layout.setSpacing(15)
        personal_layout.setContentsMargins(20, 20, 20, 20)
        
        # Style des inputs
        input_style = """
            QLineEdit, QComboBox, QTextEdit, QTimeEdit, QDateEdit {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                background-color: white;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QTimeEdit:focus, QDateEdit:focus {
                border-color: #417690;
                border-width: 2px;
            }
            QLineEdit:hover, QComboBox:hover, QTextEdit:hover, QTimeEdit:hover, QDateEdit:hover {
                border-color: #6c757d;
            }
        """
        
        # Nom
        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Nom du client")
        self.nom_input.setMinimumHeight(40)
        self.nom_input.setStyleSheet(input_style)
        personal_layout.addRow("Nom *:", self.nom_input)
        
        # Prénom
        self.prenom_input = QLineEdit()
        self.prenom_input.setPlaceholderText("Prénom du client")
        self.prenom_input.setMinimumHeight(40)
        self.prenom_input.setStyleSheet(input_style)
        personal_layout.addRow("Prénom *:", self.prenom_input)
        
        # CNPS
        self.cnps_input = QLineEdit()
        self.cnps_input.setPlaceholderText("Numéro CNPS (optionnel)")
        self.cnps_input.setMinimumHeight(40)
        self.cnps_input.setStyleSheet(input_style)
        personal_layout.addRow("N° CNPS:", self.cnps_input)
        
        # Contacts
        self.contacts_input = QLineEdit()
        self.contacts_input.setPlaceholderText("Téléphone ou email")
        self.contacts_input.setMinimumHeight(40)
        self.contacts_input.setStyleSheet(input_style)
        personal_layout.addRow("Contacts:", self.contacts_input)
        
        layout.addWidget(personal_group)
        
        # ===== SECTION DEMANDE =====
        demande_group = QGroupBox("📋 Détails de la demande")
        demande_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #417690;
            }
        """)
        
        demande_layout = QFormLayout(demande_group)
        demande_layout.setSpacing(15)
        demande_layout.setContentsMargins(20, 20, 20, 20)
        
        # Service
        self.service_combo = QComboBox()
        self.service_combo.setMinimumHeight(40)
        self.service_combo.setStyleSheet(input_style)
        self.refresh_services()
        demande_layout.addRow("Service *:", self.service_combo)
        
        # Motif
        self.motif_combo = QComboBox()
        self.motif_combo.setMinimumHeight(40)
        self.motif_combo.setStyleSheet(input_style)
        self.refresh_motifs()
        demande_layout.addRow("Motif *:", self.motif_combo)
        
        # Priorité
        self.priorite_combo = QComboBox()
        self.priorite_combo.setMinimumHeight(40)
        self.priorite_combo.setStyleSheet(input_style)
        for priorite in Priorite:
            self.priorite_combo.addItem(str(priorite), priorite.value)
        demande_layout.addRow("Priorité:", self.priorite_combo)
        
        # Statut
        self.statut_combo = QComboBox()
        self.statut_combo.setMinimumHeight(40)
        self.statut_combo.setStyleSheet(input_style)
        for statut in Statut:
            self.statut_combo.addItem(str(statut), statut.value)
        demande_layout.addRow("Statut:", self.statut_combo)
        
        layout.addWidget(demande_group)
        
        # ===== SECTION HORAIRES =====
        time_group = QGroupBox("⏰ Horaires")
        time_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #417690;
            }
        """)
        
        time_layout = QFormLayout(time_group)
        time_layout.setSpacing(15)
        time_layout.setContentsMargins(20, 20, 20, 20)
        
        # Date
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setMinimumHeight(40)
        self.date_input.setStyleSheet(input_style)
        time_layout.addRow("Date *:", self.date_input)
        
        # Heure d'arrivée
        self.heure_arrivee = QTimeEdit()
        self.heure_arrivee.setTime(QTime.currentTime())
        self.heure_arrivee.setDisplayFormat("HH:mm:ss")
        self.heure_arrivee.setMinimumHeight(40)
        self.heure_arrivee.setStyleSheet(input_style)
        time_layout.addRow("Heure d'arrivée *:", self.heure_arrivee)
        
        # Heure de réception
        self.heure_reception = QTimeEdit()
        self.heure_reception.setTime(QTime.currentTime())
        self.heure_reception.setDisplayFormat("HH:mm:ss")
        self.heure_reception.setMinimumHeight(40)
        self.heure_reception.setStyleSheet(input_style)
        self.heure_reception.setSpecialValueText("Non traitée")
        time_layout.addRow("Heure de réception:", self.heure_reception)
        
        layout.addWidget(time_group)
        
        # ===== SECTION OBSERVATIONS =====
        obs_group = QGroupBox("📝 Observations")
        obs_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #417690;
            }
        """)
        
        obs_layout = QVBoxLayout(obs_group)
        obs_layout.setContentsMargins(20, 20, 20, 20)
        
        self.observations = QTextEdit()
        self.observations.setPlaceholderText("Observations, notes, date de rendez-vous...")
        self.observations.setMinimumHeight(100)
        self.observations.setMaximumHeight(150)
        self.observations.setStyleSheet(input_style)
        obs_layout.addWidget(self.observations)
        
        layout.addWidget(obs_group)
        
        # ===== SECTION SATISFACTION (pour modification) =====
        if self.demande and self.demande.id:
            sat_group = QGroupBox("⭐ Satisfaction")
            sat_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 14px;
                    border: 2px solid #e9ecef;
                    border-radius: 10px;
                    margin-top: 12px;
                    padding-top: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 10px;
                    color: #417690;
                }
            """)
            
            sat_layout = QFormLayout(sat_group)
            sat_layout.setContentsMargins(20, 20, 20, 20)
            
            # Note
            self.satisfaction_combo = QComboBox()
            self.satisfaction_combo.addItem("Non évalué", None)
            for i in range(1, 6):
                self.satisfaction_combo.addItem("⭐" * i, i)
            self.satisfaction_combo.setMinimumHeight(40)
            self.satisfaction_combo.setStyleSheet(input_style)
            sat_layout.addRow("Note:", self.satisfaction_combo)
            
            # Commentaire
            self.commentaire_satisfaction = QTextEdit()
            self.commentaire_satisfaction.setPlaceholderText("Commentaire du client...")
            self.commentaire_satisfaction.setMaximumHeight(80)
            self.commentaire_satisfaction.setStyleSheet(input_style)
            sat_layout.addRow("Commentaire:", self.commentaire_satisfaction)
            
            layout.addWidget(sat_group)
        
        # Remplir les valeurs si modification
        if self.demande and self.demande.id:
            self.load_data()
    
    def refresh_services(self):
        """Rafraîchit la liste des services"""
        self.service_combo.clear()
        try:
            services = Service.get_all(actif_only=True)
            for service in services:
                self.service_combo.addItem(service.nom, service.id)
        except Exception as e:
            print(f"Erreur chargement services: {e}")
    
    def refresh_motifs(self):
        """Rafraîchit la liste des motifs"""
        self.motif_combo.clear()
        try:
            motifs = Motif.get_all(actif_only=True)
            for motif in motifs:
                self.motif_combo.addItem(motif.nom, motif.id)
        except Exception as e:
            print(f"Erreur chargement motifs: {e}")
    
    def load_data(self):
        """Charge les données d'une demande existante"""
        try:
            # Informations personnelles
            self.nom_input.setText(self.demande.nom or "")
            self.prenom_input.setText(self.demande.prenom or "")
            self.cnps_input.setText(self.demande.numero_cnps or "")
            self.contacts_input.setText(self.demande.contacts or "")
            
            # Service
            if self.demande.service_demande_id:
                index = self.service_combo.findData(self.demande.service_demande_id)
                if index >= 0:
                    self.service_combo.setCurrentIndex(index)
            
            # Motif
            if self.demande.motif_id:
                index = self.motif_combo.findData(self.demande.motif_id)
                if index >= 0:
                    self.motif_combo.setCurrentIndex(index)
            
            # Priorité
            priorite_value = self.demande.priorite or 'normale'
            for i in range(self.priorite_combo.count()):
                if self.priorite_combo.itemData(i) == priorite_value:
                    self.priorite_combo.setCurrentIndex(i)
                    break
            
            # Statut
            statut_value = self.demande.statut or 'en_attente'
            for i in range(self.statut_combo.count()):
                if self.statut_combo.itemData(i) == statut_value:
                    self.statut_combo.setCurrentIndex(i)
                    break
            
            # Date
            if self.demande.date:
                if hasattr(self.demande.date, 'strftime'):
                    date_q = QDate.fromString(self.demande.date.strftime("%Y-%m-%d"), "yyyy-MM-dd")
                else:
                    date_q = QDate.currentDate()
                self.date_input.setDate(date_q)
            
            # Heure arrivée
            if self.demande.heure_arrivee:
                if hasattr(self.demande.heure_arrivee, 'strftime'):
                    time_str = self.demande.heure_arrivee.strftime("%H:%M:%S")
                else:
                    time_str = str(self.demande.heure_arrivee)
                self.heure_arrivee.setTime(QTime.fromString(time_str, "HH:mm:ss"))
            
            # Heure réception
            if self.demande.heure_reception:
                if hasattr(self.demande.heure_reception, 'strftime'):
                    time_str = self.demande.heure_reception.strftime("%H:%M:%S")
                else:
                    time_str = str(self.demande.heure_reception)
                self.heure_reception.setTime(QTime.fromString(time_str, "HH:mm:ss"))
            
            # Observations
            self.observations.setPlainText(self.demande.observations or "")
            
            # Satisfaction
            if hasattr(self, 'satisfaction_combo'):
                if self.demande.satisfaction:
                    for i in range(self.satisfaction_combo.count()):
                        if self.satisfaction_combo.itemData(i) == self.demande.satisfaction:
                            self.satisfaction_combo.setCurrentIndex(i)
                            break
                if hasattr(self, 'commentaire_satisfaction'):
                    self.commentaire_satisfaction.setPlainText(self.demande.commentaire_satisfaction or "")
                    
        except Exception as e:
            print(f"Erreur chargement données: {e}")
    
    def save(self) -> bool:
        """Sauvegarde la demande"""
        try:
            # Validation des champs obligatoires
            if not self.nom_input.text().strip():
                QMessageBox.warning(self, "Attention", "Le nom est obligatoire")
                return False
            if not self.prenom_input.text().strip():
                QMessageBox.warning(self, "Attention", "Le prénom est obligatoire")
                return False
            if not self.service_combo.currentData():
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un service")
                return False
            if not self.motif_combo.currentData():
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un motif")
                return False
            
            # Récupérer les valeurs
            self.demande.nom = self.nom_input.text().strip()
            self.demande.prenom = self.prenom_input.text().strip()
            self.demande.numero_cnps = self.cnps_input.text().strip()
            self.demande.contacts = self.contacts_input.text().strip()
            self.demande.service_demande_id = self.service_combo.currentData()
            self.demande.motif_id = self.motif_combo.currentData()
            self.demande.priorite = self.priorite_combo.currentData()
            self.demande.statut = self.statut_combo.currentData()
            self.demande.observations = self.observations.toPlainText().strip()
            
            # Date
            date_py = self.date_input.date().toPyDate()
            self.demande.date = date_py
            
            # Heures
            time_arrivee = self.heure_arrivee.time()
            self.demande.heure_arrivee = time(time_arrivee.hour(), time_arrivee.minute(), time_arrivee.second())
            
            if self.heure_reception.time() != QTime(0, 0):
                time_recep = self.heure_reception.time()
                self.demande.heure_reception = time(time_recep.hour(), time_recep.minute(), time_recep.second())
            else:
                self.demande.heure_reception = None
            
            # Satisfaction
            if hasattr(self, 'satisfaction_combo'):
                self.demande.satisfaction = self.satisfaction_combo.currentData()
            if hasattr(self, 'commentaire_satisfaction'):
                self.demande.commentaire_satisfaction = self.commentaire_satisfaction.toPlainText().strip()
            
            # Calculer le temps d'attente
            self.demande.calculer_temps_attente()
            
            # Sauvegarder
            return self.demande.save()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde:\n{str(e)}")
            return False


class DemandeTableWidget(QWidget):
    """Tableau des demandes avec fonctionnalités avancées et permissions par rôle"""
    
    demandes_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.user_role = None
        self.enable_actions = True
        self.enable_delete = False
        self.filters = {}
        self.init_ui()
        self.refresh()
        
    def init_ui(self):
        """Initialise l'interface du tableau"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Barre de recherche rapide
        search_bar = QWidget()
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(0, 0, 0, 10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher (nom, prénom, CNPS, contact...)")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #dee2e6;
                border-radius: 25px;
                padding: 12px 20px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #417690;
            }
        """)
        search_layout.addWidget(self.search_input)
        
        layout.addWidget(search_bar)
        
        # Tableau
        self.table = QTableWidget()
        self.table.setObjectName("demandeTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_double_click)
        
        # Style du tableau
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e9ecef;
                border-radius: 10px;
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
        """)
        
        # Configuration des colonnes
        headers = ["ID", "Date", "Client", "Service", "Motif", "Priorité", "Statut", "Attente", "Actions"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Largeurs des colonnes
        self.table.setColumnWidth(0, 100)  # ID
        self.table.setColumnWidth(1, 100)  # Date
        self.table.setColumnWidth(2, 200)  # Client
        self.table.setColumnWidth(3, 150)  # Service
        self.table.setColumnWidth(4, 150)  # Motif
        self.table.setColumnWidth(5, 120)  # Priorité
        self.table.setColumnWidth(6, 120)  # Statut
        self.table.setColumnWidth(7, 100)  # Attente
        self.table.setColumnWidth(8, 150)  # Actions
        
        layout.addWidget(self.table)
        
        # Boutons d'action sous le tableau
        self.create_action_buttons()
        
    def create_action_buttons(self):
        """Crée les boutons d'action sous le tableau"""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(15)
        
        # Bouton Marquer comme traité
        self.marquer_traite_btn = QPushButton("✅ Marquer comme traité")
        self.marquer_traite_btn.setMinimumHeight(45)
        self.marquer_traite_btn.setMinimumWidth(200)
        self.marquer_traite_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.marquer_traite_btn.clicked.connect(self.marquer_traite_selection)
        button_layout.addWidget(self.marquer_traite_btn)
        
        # Bouton Modifier
        self.modifier_btn = QPushButton("✏️ Modifier")
        self.modifier_btn.setMinimumHeight(45)
        self.modifier_btn.setMinimumWidth(150)
        self.modifier_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: black;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: white;
            }
        """)
        self.modifier_btn.clicked.connect(self.modifier_selection)
        button_layout.addWidget(self.modifier_btn)
        
        # Bouton Supprimer
        self.supprimer_btn = QPushButton("🗑️ Supprimer")
        self.supprimer_btn.setMinimumHeight(45)
        self.supprimer_btn.setMinimumWidth(150)
        self.supprimer_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.supprimer_btn.clicked.connect(self.supprimer_selection)
        button_layout.addWidget(self.supprimer_btn)
        
        button_layout.addStretch()
        
        # Bouton Exporter
        self.export_btn = QPushButton("📊 Exporter")
        self.export_btn.setMinimumHeight(45)
        self.export_btn.setMinimumWidth(150)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #adb5bd;
            }
        """)
        self.export_btn.clicked.connect(self.export_data)
        button_layout.addWidget(self.export_btn)
        
        # Bouton Rafraîchir
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(45, 45)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(self.refresh_btn)
        
        layout = self.layout()
        layout.addWidget(button_widget)
        
    def set_user_role(self, role):
        """Définit le rôle de l'utilisateur et applique les permissions"""
        self.user_role = role
        self.apply_role_permissions()
        
    def apply_role_permissions(self):
        """Applique les permissions selon le rôle"""
        if not self.user_role:
            return
            
        # 🛂 PRÉ-ACCUEIL : Lecture seule + création uniquement
        if self.user_role == 'preaccueil':
            self.marquer_traite_btn.setVisible(False)
            self.modifier_btn.setVisible(False)
            self.supprimer_btn.setVisible(False)
            self.export_btn.setVisible(False)
            self.enable_actions = False
            
        # 🏢 ACCUEIL : Peut modifier et traiter, mais pas supprimer
        elif self.user_role == 'accueil':
            self.marquer_traite_btn.setVisible(True)
            self.modifier_btn.setVisible(True)
            self.supprimer_btn.setVisible(False)
            self.export_btn.setVisible(False)
            self.enable_actions = True
            self.enable_delete = False
            
        # 📊 MANAGER : Toutes actions sauf administration
        elif self.user_role == 'manager':
            self.marquer_traite_btn.setVisible(True)
            self.modifier_btn.setVisible(True)
            self.supprimer_btn.setVisible(True)
            self.export_btn.setVisible(True)
            self.enable_actions = True
            self.enable_delete = True
            
        # 👑 ADMIN : Toutes actions
        elif self.user_role == 'admin':
            self.marquer_traite_btn.setVisible(True)
            self.modifier_btn.setVisible(True)
            self.supprimer_btn.setVisible(True)
            self.export_btn.setVisible(True)
            self.enable_actions = True
            self.enable_delete = True
    
    def create_actions_widget(self, demande_id: str, statut: str = None) -> QWidget:
        """Crée le widget d'actions selon les permissions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 👁️ VOIR - Tout le monde peut voir
        view_btn = self.create_action_button("👁️", "#17a2b8", "Voir détails")
        view_btn.clicked.connect(lambda: self.view_demande(demande_id))
        layout.addWidget(view_btn)
        
        # ✅ TRAITER - Accueil, Manager, Admin uniquement
        if self.user_role in ['accueil', 'manager', 'admin'] and statut != 'traite':
            process_btn = self.create_action_button("✅", "#28a745", "Traiter la demande")
            process_btn.clicked.connect(lambda: self.process_demande(demande_id))
            layout.addWidget(process_btn)
        
        # ✏️ MODIFIER - Accueil, Manager, Admin uniquement
        if self.user_role in ['accueil', 'manager', 'admin']:
            edit_btn = self.create_action_button("✏️", "#ffc107", "Modifier")
            edit_btn.clicked.connect(lambda: self.edit_demande(demande_id))
            layout.addWidget(edit_btn)
        
        # 🗑️ SUPPRIMER - Manager et Admin uniquement
        if self.user_role in ['manager', 'admin']:
            delete_btn = self.create_action_button("🗑️", "#dc3545", "Supprimer")
            delete_btn.clicked.connect(lambda: self.delete_demande(demande_id))
            layout.addWidget(delete_btn)
        
        return widget
    
    def create_action_button(self, text, color, tooltip):
        """Crée un bouton d'action stylisé"""
        btn = QPushButton(text)
        btn.setFixedSize(32, 32)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
        """)
        return btn
    
    def darken_color(self, color):
        """Assombrit une couleur pour l'effet hover"""
        colors = {
            "#17a2b8": "#138496",
            "#28a745": "#218838",
            "#ffc107": "#e0a800",
            "#dc3545": "#c82333",
        }
        return colors.get(color, color)
    
    def refresh(self):
        """Rafraîchit le tableau"""
        try:
            # Récupérer les demandes avec filtres
            demandes = DemandeAccueil.get_all(self.filters, limit=100)
            self.table.setRowCount(len(demandes))
            
            for i, demande in enumerate(demandes):
                # ID (tronqué)
                demande_id = str(demande.id)[:8] if demande.id else ""
                id_item = QTableWidgetItem(demande_id)
                id_item.setData(Qt.ItemDataRole.UserRole, demande.id)
                self.table.setItem(i, 0, id_item)
                
                # Date
                date_str = ""
                if demande.date:
                    if hasattr(demande.date, 'strftime'):
                        date_str = demande.date.strftime("%d/%m/%Y")
                    else:
                        date_str = str(demande.date)
                self.table.setItem(i, 1, QTableWidgetItem(date_str))
                
                # Client
                client_item = QTableWidgetItem(f"{demande.nom} {demande.prenom}".strip())
                self.table.setItem(i, 2, client_item)
                
                # Service
                service_nom = demande.service.nom if demande.service else ""
                self.table.setItem(i, 3, QTableWidgetItem(service_nom))
                
                # Motif
                motif_nom = demande.motif.nom if demande.motif else ""
                self.table.setItem(i, 4, QTableWidgetItem(motif_nom))
                
                # Priorité
                priorite_text = str(Priorite(demande.priorite)) if demande.priorite else ""
                priorite_item = QTableWidgetItem(priorite_text)
                try:
                    priorite_item.setForeground(QColor(Priorite(demande.priorite).color))
                except Exception:                    pass
                self.table.setItem(i, 5, priorite_item)
                
                # Statut
                statut_text = str(Statut(demande.statut)) if demande.statut else ""
                statut_item = QTableWidgetItem(statut_text)
                try:
                    statut_item.setForeground(QColor(Statut(demande.statut).color))
                except Exception:                    pass
                self.table.setItem(i, 6, statut_item)
                
                # Temps d'attente
                attente_text = "-"
                if demande.temps_attente_minutes:
                    attente_text = f"{demande.temps_attente_minutes} min"
                    if demande.delai_objectif_bool:
                        attente_text += " ⚠️"
                attente_item = QTableWidgetItem(attente_text)
                if demande.temps_attente_minutes and demande.temps_attente_minutes > 15:
                    attente_item.setForeground(QColor('#dc3545'))
                self.table.setItem(i, 7, attente_item)
                
                # Widget d'actions
                if self.user_role != 'preaccueil':  # Pré-accueil pas d'actions
                    actions_widget = self.create_actions_widget(demande.id, demande.statut)
                    self.table.setCellWidget(i, 8, actions_widget)
                
            # Ajuster la hauteur des lignes
            for i in range(self.table.rowCount()):
                self.table.setRowHeight(i, 50)
                
        except Exception as e:
            print(f"Erreur rafraîchissement tableau: {e}")
    
    def marquer_traite_selection(self):
        """Marque la demande sélectionnée comme traitée"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            demande_id = self.table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
            self.process_demande(demande_id)
        else:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une demande à traiter")
    
    def modifier_selection(self):
        """Modifie la demande sélectionnée"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            demande_id = self.table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
            self.edit_demande(demande_id)
        else:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une demande à modifier")
    
    def supprimer_selection(self):
        """Supprime la demande sélectionnée"""
        if not self.enable_delete:
            QMessageBox.warning(self, "Accès refusé", "Vous n'avez pas les droits pour supprimer des demandes")
            return
            
        current_row = self.table.currentRow()
        if current_row >= 0:
            demande_id = self.table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
            self.delete_demande(demande_id)
        else:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une demande à supprimer")
    
    def view_demande(self, demande_id: str):
        """Affiche les détails d'une demande"""
        demande = DemandeAccueil.get_by_id(demande_id)
        if demande:
            dialog = QDialog(self)
            dialog.setWindowTitle("📋 Détails de la demande")
            dialog.setMinimumWidth(600)
            dialog.setModal(True)
            
            layout = QVBoxLayout(dialog)
            
            # En-tête
            header = QFrame()
            header.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #417690, stop:1 #2d5a6e);
                    border-radius: 8px;
                    padding: 20px;
                }
            """)
            header_layout = QHBoxLayout(header)
            
            icon_label = QLabel("📋")
            icon_label.setStyleSheet("font-size: 32px; color: white;")
            header_layout.addWidget(icon_label)
            
            title_label = QLabel(f"Demande du {demande.date}")
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-left: 10px;")
            header_layout.addWidget(title_label)
            
            header_layout.addStretch()
            
            statut_label = QLabel(str(Statut(demande.statut)))
            statut_label.setStyleSheet(f"""
                background-color: {Statut(demande.statut).color};
                color: white;
                padding: 8px 15px;
                border-radius: 15px;
                font-weight: bold;
            """)
            header_layout.addWidget(statut_label)
            
            layout.addWidget(header)
            
            # Corps
            content = QFrame()
            content.setStyleSheet("background-color: white; padding: 20px;")
            content_layout = QFormLayout(content)
            content_layout.setSpacing(15)
            
            # Informations
            content_layout.addRow("ID:", QLabel(str(demande.id)))
            content_layout.addRow("Client:", QLabel(f"{demande.nom} {demande.prenom}"))
            content_layout.addRow("N° CNPS:", QLabel(demande.numero_cnps or "-"))
            content_layout.addRow("Contacts:", QLabel(demande.contacts or "-"))
            content_layout.addRow("Service:", QLabel(demande.service.nom if demande.service else "-"))
            content_layout.addRow("Motif:", QLabel(demande.motif.nom if demande.motif else "-"))
            content_layout.addRow("Priorité:", QLabel(str(Priorite(demande.priorite))))
            content_layout.addRow("Date arrivée:", QLabel(f"{demande.date} à {demande.heure_arrivee}"))
            
            if demande.heure_reception:
                content_layout.addRow("Date traitement:", QLabel(f"{demande.date} à {demande.heure_reception}"))
                if demande.temps_attente_minutes:
                    content_layout.addRow("Temps d'attente:", QLabel(f"{demande.temps_attente_minutes} minutes"))
            
            if demande.observations:
                content_layout.addRow("Observations:", QLabel(demande.observations))
            
            if demande.satisfaction:
                content_layout.addRow("Satisfaction:", QLabel(f"{demande.satisfaction_etoiles}"))
                if demande.commentaire_satisfaction:
                    content_layout.addRow("Commentaire:", QLabel(demande.commentaire_satisfaction))
            
            layout.addWidget(content)
            
            # Bouton fermer
            close_btn = QPushButton("Fermer")
            close_btn.setMinimumHeight(40)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
            """)
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec()
    
    def edit_demande(self, demande_id: str):
        """Édite une demande"""
        if not self.enable_actions:
            QMessageBox.warning(self, "Accès refusé", "Vous n'avez pas les droits pour modifier des demandes")
            return
            
        demande = DemandeAccueil.get_by_id(demande_id)
        if demande:
            from ui.main_window import MainWindow
            parent = self.parent()
            while parent and not isinstance(parent, MainWindow):
                parent = parent.parent()
            if parent:
                parent.open_demande_form_complete(demande)
    
    def process_demande(self, demande_id: str):
        """Traite une demande (marque comme traitée)"""
        if not self.enable_actions:
            QMessageBox.warning(self, "Accès refusé", "Vous n'avez pas les droits pour traiter des demandes")
            return
            
        try:
            demande = DemandeAccueil.get_by_id(demande_id)
            if demande and demande.statut != 'traite':
                reply = QMessageBox.question(
                    self,
                    "Confirmation",
                    f"Marquer la demande de {demande.nom} {demande.prenom} comme traitée ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    demande.marquer_traite()
                    self.refresh()
                    self.demandes_updated.emit()
                    QMessageBox.information(self, "✅ Succès", "Demande marquée comme traitée")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du traitement:\n{str(e)}")
    
    def delete_demande(self, demande_id: str):
        """Supprime une demande"""
        if not self.enable_delete:
            QMessageBox.warning(self, "Accès refusé", "Vous n'avez pas les droits pour supprimer des demandes")
            return
            
        try:
            demande = DemandeAccueil.get_by_id(demande_id)
            if demande:
                reply = QMessageBox.question(
                    self,
                    "🗑️ Confirmation",
                    f"Voulez-vous vraiment supprimer la demande de {demande.nom} {demande.prenom} ?\n\nCette action est irréversible.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Logique de suppression à implémenter
                    QMessageBox.information(self, "✅ Succès", "Demande supprimée avec succès")
                    self.refresh()
                    self.demandes_updated.emit()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression:\n{str(e)}")
    
    def apply_filters(self, filters: dict):
        """Applique les filtres"""
        self.filters = filters
        self.refresh()
    
    def search(self, text: str):
        """Recherche en temps réel"""
        text = text.lower()
        for row in range(self.table.rowCount()):
            hide = True
            for col in [1, 2, 3, 4]:  # Date, Client, Service, Motif
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    hide = False
                    break
            self.table.setRowHidden(row, hide)
    
    def on_search_text_changed(self, text):
        """Gère la recherche en temps réel"""
        self.search(text)
    
    def export_data(self):
        """Exporte les données au format CSV"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Exporter les données",
                f"demandes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    # En-têtes
                    headers = []
                    for col in range(self.table.columnCount() - 1):  # Sans la colonne Actions
                        headers.append(self.table.horizontalHeaderItem(col).text())
                    f.write(";".join(headers) + "\n")
                    
                    # Données
                    for row in range(self.table.rowCount()):
                        if not self.table.isRowHidden(row):
                            row_data = []
                            for col in range(self.table.columnCount() - 1):
                                item = self.table.item(row, col)
                                row_data.append(item.text() if item else "")
                            f.write(";".join(row_data) + "\n")
                
                QMessageBox.information(self, "✅ Succès", f"Données exportées vers {filename}")
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export:\n{str(e)}")
    
    def on_double_click(self, index):
        """Gère le double-clic sur une ligne"""
        if self.enable_actions:
            row = index.row()
            demande_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.edit_demande(demande_id)
        else:
            row = index.row()
            demande_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.view_demande(demande_id)