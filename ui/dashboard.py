# ui/dashboard_simple.py
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from datetime import datetime, date, timedelta
from database.models import DemandeAccueil, Service, Priorite, Statut

class DashboardSimple(QWidget):
    """Tableau de bord simple et épuré"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_role = None
        self.init_ui()
        self.refresh()
        
        # Rafraîchissement automatique toutes les 30 secondes
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(30000)
        
    def init_ui(self):
        """Interface simple sans fioritures"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # ===== 1. EN-TÊTE SIMPLE =====
        header = self.create_header()
        layout.addWidget(header)
        
        # ===== 2. STATISTIQUES EN LIGNE =====
        stats = self.create_stats_row()
        layout.addWidget(stats)
        
        # ===== 3. DEUX COLONNES =====
        columns = QHBoxLayout()
        columns.setSpacing(15)
        
        # Colonne gauche : Demandes du jour
        self.today_widget = self.create_today_section()
        columns.addWidget(self.today_widget, 1)
        
        # Colonne droite : Activités récentes
        self.activities_widget = self.create_activities_section()
        columns.addWidget(self.activities_widget, 1)
        
        layout.addLayout(columns)
        
        # ===== 4. RÉPARTITION SIMPLE =====
        self.distribution_widget = self.create_distribution_section()
        layout.addWidget(self.distribution_widget)
        
    def create_header(self):
        """En-tête minimaliste"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # Titre
        title = QLabel("📊 Tableau de bord")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Rôle
        self.role_label = QLabel("")
        self.role_label.setStyleSheet("""
            background-color: #f0f0f0;
            padding: 5px 12px;
            border-radius: 12px;
            font-size: 12px;
            color: #555;
        """)
        layout.addWidget(self.role_label)
        
        # Date
        self.date_label = QLabel()
        self.date_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        self.update_date()
        layout.addWidget(self.date_label)
        
        return header
    
    def create_stats_row(self):
        """Ligne de statistiques en chiffres"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 4 statistiques principales
        self.stats_cards = {}
        stats = [
            ("total", "📋 Total", "0", "#2c3e50"),
            ("attente", "⏳ En attente", "0", "#f39c12"),
            ("traite", "✅ Traité", "0", "#27ae60"),
            ("urgent", "🔴 Urgent", "0", "#e74c3c"),
        ]
        
        for key, label, value, color in stats:
            card = self.create_stat_card(label, value, color)
            layout.addWidget(card)
            self.stats_cards[key] = card
        
        return widget
    
    def create_stat_card(self, title, value, color):
        """Carte de statistique très simple"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                border-left: 4px solid {color};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        # Titre
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #777; font-size: 12px;")
        layout.addWidget(lbl_title)
        
        # Valeur
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(lbl_value)
        
        return card
    
    def create_today_section(self):
        """Section des demandes du jour"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        # Titre
        title_layout = QHBoxLayout()
        title = QLabel("📋 Demandes du jour")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        self.today_count = QLabel("0")
        self.today_count.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        title_layout.addWidget(self.today_count)
        
        layout.addLayout(title_layout)
        
        # Tableau simple
        self.today_table = QTableWidget()
        self.today_table.setColumnCount(3)
        self.today_table.setHorizontalHeaderLabels(["Heure", "Client", "Statut"])
        self.today_table.horizontalHeader().setStretchLastSection(True)
        self.today_table.setAlternatingRowColors(True)
        self.today_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.today_table.setMaximumHeight(200)
        self.today_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.today_table)
        
        # Bouton voir tout
        btn_view = QPushButton("Voir toutes les demandes →")
        btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #3498db;
                border: none;
                text-align: right;
                font-size: 12px;
                padding: 5px;
            }
            QPushButton:hover {
                color: #2980b9;
                text-decoration: underline;
            }
        """)
        btn_view.clicked.connect(self.view_all_demandes)
        layout.addWidget(btn_view)
        
        return widget
    
    def create_activities_section(self):
        """Section des activités récentes"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        # Titre
        title = QLabel("🕐 Activités récentes")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        # Liste simple
        self.activities_list = QListWidget()
        self.activities_list.setMaximumHeight(200)
        self.activities_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #eee;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        
        layout.addWidget(self.activities_list)
        
        return widget
    
    def create_distribution_section(self):
        """Section de répartition simple"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                margin-top: 5px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        # Titre
        title = QLabel("📊 Répartition par service")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        # Tableau simple
        self.distribution_table = QTableWidget()
        self.distribution_table.setColumnCount(3)
        self.distribution_table.setHorizontalHeaderLabels(["Service", "Demandes", "%"])
        self.distribution_table.horizontalHeader().setStretchLastSection(True)
        self.distribution_table.setAlternatingRowColors(True)
        self.distribution_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.distribution_table.setMaximumHeight(150)
        self.distribution_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.distribution_table)
        
        return widget
    
    def update_date(self):
        """Met à jour la date"""
        now = QDateTime.currentDateTime()
        self.date_label.setText(now.toString("dd/MM/yyyy HH:mm"))
    
    def set_role(self, role):
        """Définit le rôle"""
        self.user_role = role
        self.setVisible(role in ['accueil', 'manager', 'admin'])
        
        roles = {
            'accueil': '🏢 Accueil',
            'manager': '📊 Manager',
            'admin': '👑 Admin'
        }
        self.role_label.setText(roles.get(role, ''))
    
    def refresh(self):
        """Rafraîchit les données"""
        try:
            today = date.today()
            
            # Récupérer les données
            all_demandes = DemandeAccueil.get_all({}, limit=200)
            today_demandes = [d for d in all_demandes if d.date and d.date == today]
            
            # Mettre à jour
            self.update_stats(today_demandes)
            self.update_today_demandes(today_demandes)
            self.update_activities(all_demandes[:15])
            self.update_distribution(all_demandes)
            self.update_date()
            
        except Exception as e:
            print(f"Erreur refresh: {e}")
    
    def update_stats(self, demandes):
        """Met à jour les statistiques"""
        total = len(demandes)
        attente = len([d for d in demandes if d.statut == 'en_attente'])
        traite = len([d for d in demandes if d.statut == 'traite'])
        urgent = len([d for d in demandes if d.priorite == 'haute'])
        
        # Mettre à jour les cartes
        stats = {
            'total': str(total),
            'attente': str(attente),
            'traite': str(traite),
            'urgent': str(urgent)
        }
        
        for key, value in stats.items():
            if key in self.stats_cards:
                card = self.stats_cards[key]
                # Trouver le label de valeur (le dernier QLabel)
                labels = card.findChildren(QLabel)
                if len(labels) >= 2:
                    labels[1].setText(value)
    
    def update_today_demandes(self, demandes):
        """Met à jour la liste des demandes du jour"""
        self.today_count.setText(str(len(demandes)))
        
        # Trier par heure
        demandes_triees = sorted(
            demandes,
            key=lambda d: d.heure_arrivee if d.heure_arrivee else "00:00:00"
        )[:5]  # 5 max
        
        self.today_table.setRowCount(len(demandes_triees))
        
        for i, d in enumerate(demandes_triees):
            # Heure
            heure = d.heure_arrivee.strftime("%H:%M") if hasattr(d.heure_arrivee, 'strftime') else str(d.heure_arrivee)[:5]
            self.today_table.setItem(i, 0, QTableWidgetItem(heure))
            
            # Client
            self.today_table.setItem(i, 1, QTableWidgetItem(f"{d.nom} {d.prenom}"))
            
            # Statut
            statut = str(Statut(d.statut)) if d.statut else ""
            item = QTableWidgetItem(statut)
            try:
                item.setForeground(QColor(Statut(d.statut).color))
            except:
                pass
            self.today_table.setItem(i, 2, item)
    
    def update_activities(self, demandes):
        """Met à jour la liste des activités"""
        self.activities_list.clear()
        
        activities = []
        for d in demandes[:8]:
            if d.created_at:
                heure = d.created_at.strftime("%H:%M") if hasattr(d.created_at, 'strftime') else ""
                activities.append(f"✅ {heure} - Nouvelle: {d.nom} {d.prenom}")
            
            if d.traite_le and d.statut == 'traite':
                heure = d.traite_le.strftime("%H:%M") if hasattr(d.traite_le, 'strftime') else ""
                activities.append(f"🔄 {heure} - Traitée: {d.nom} {d.prenom}")
        
        for activity in activities[:6]:  # 6 max
            self.activities_list.addItem(activity)
    
    def update_distribution(self, demandes):
        """Met à jour la répartition par service"""
        # Compter par service
        services = {}
        for d in demandes:
            if d.service_demande_id:
                nom = d.service.nom if d.service else f"S{d.service_demande_id}"
                services[nom] = services.get(nom, 0) + 1
        
        total = len(demandes) or 1
        
        # Top 3
        top_services = sorted(services.items(), key=lambda x: x[1], reverse=True)[:3]
        
        self.distribution_table.setRowCount(len(top_services))
        
        for i, (nom, count) in enumerate(top_services):
            pourcent = (count / total) * 100
            
            self.distribution_table.setItem(i, 0, QTableWidgetItem(nom))
            
            item_count = QTableWidgetItem(str(count))
            item_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.distribution_table.setItem(i, 1, item_count)
            
            item_pct = QTableWidgetItem(f"{pourcent:.0f}%")
            item_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.distribution_table.setItem(i, 2, item_pct)
    
    def view_all_demandes(self):
        """Voir toutes les demandes"""
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'show_demandes'):
            parent.show_demandes()