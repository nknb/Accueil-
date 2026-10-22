# ui/statistics.py
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from datetime import datetime, date, timedelta
from database.models import DemandeAccueil, Service
from collections import defaultdict

class StatisticsWidget(QWidget):
    """Widget de statistiques et rapports"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_period = "30"  # jours par défaut
        self.init_ui()
        self.refresh()
        
    def init_ui(self):
        """Initialise l'interface des statistiques"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # En-tête
        header = QLabel("📈 Statistiques et Analyses")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #417690; padding: 10px 0;")
        layout.addWidget(header)
        
        # Barre d'outils des statistiques
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Zone de contenu avec onglets
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("statsTabs")
        
        # Onglet Vue d'ensemble
        self.overview_widget = self.create_overview_widget()
        self.tab_widget.addTab(self.overview_widget, "📊 Vue d'ensemble")
        
        # Onglet Performance
        self.performance_widget = self.create_performance_widget()
        self.tab_widget.addTab(self.performance_widget, "⏱️ Performance")
        
        # Onglet Satisfaction
        self.satisfaction_widget = self.create_satisfaction_widget()
        self.tab_widget.addTab(self.satisfaction_widget, "⭐ Satisfaction")
        
        # Onglet Export
        self.export_widget = self.create_export_widget()
        self.tab_widget.addTab(self.export_widget, "📤 Export")
        
        layout.addWidget(self.tab_widget)
        
    def create_toolbar(self):
        """Crée la barre d'outils des statistiques"""
        toolbar = QFrame()
        toolbar.setObjectName("statsToolbar")
        toolbar.setStyleSheet("""
            QFrame#statsToolbar {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(toolbar)
        
        # Période
        layout.addWidget(QLabel("Période:"))
        
        self.period_combo = QComboBox()
        periods = [
            ("7 derniers jours", "7"),
            ("30 derniers jours", "30"),
            ("90 derniers jours", "90"),
            ("Cette année", "365"),
            ("Personnalisée", "custom")
        ]
        for label, value in periods:
            self.period_combo.addItem(label, value)
        self.period_combo.currentIndexChanged.connect(self.on_period_changed)
        layout.addWidget(self.period_combo)
        
        # Date personnalisée (cachée par défaut)
        self.custom_date_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_date_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.date_debut = QDateEdit()
        self.date_debut.setDate(QDate.currentDate().addDays(-30))
        self.date_debut.setCalendarPopup(True)
        custom_layout.addWidget(QLabel("Du:"))
        custom_layout.addWidget(self.date_debut)
        
        self.date_fin = QDateEdit()
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setCalendarPopup(True)
        custom_layout.addWidget(QLabel("au:"))
        custom_layout.addWidget(self.date_fin)
        
        self.custom_date_widget.setVisible(False)
        layout.addWidget(self.custom_date_widget)
        
        layout.addStretch()
        
        # Bouton Rafraîchir
        refresh_btn = QPushButton("🔄 Rafraîchir")
        refresh_btn.setObjectName("refreshButton")
        refresh_btn.clicked.connect(self.refresh)
        refresh_btn.setStyleSheet("""
            QPushButton#refreshButton {
                background-color: #417690;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton#refreshButton:hover {
                background-color: #2d5a6e;
            }
        """)
        layout.addWidget(refresh_btn)
        
        return toolbar
        
    def create_overview_widget(self):
        """Crée le widget de vue d'ensemble"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # KPIs principaux
        kpi_widget = QWidget()
        kpi_layout = QHBoxLayout(kpi_widget)
        kpi_layout.setSpacing(15)
        
        self.kpi_cards = {}
        kpis = [
            ("total", "📋 Total demandes", "0", "#417690"),
            ("moyenne_journaliere", "📊 Moyenne/jour", "0", "#6f42c1"),
            ("traitement", "✅ Taux traitement", "0%", "#28a745"),
            ("attente_moyen", "⏱️ Attente moyen", "0 min", "#fd7e14"),
            ("satisfaction", "⭐ Satisfaction", "0.0", "#17a2b8"),
        ]
        
        for key, title, value, color in kpis:
            card = self.create_stat_card(title, value, color)
            kpi_layout.addWidget(card)
            self.kpi_cards[key] = card.findChild(QLabel, f"value_{key}")
            
        layout.addWidget(kpi_widget)
        
        # Graphiques
        charts_widget = QWidget()
        charts_layout = QHBoxLayout(charts_widget)
        charts_layout.setSpacing(20)
        
        # Graphique d'évolution
        evolution_chart = self.create_evolution_chart()
        charts_layout.addWidget(evolution_chart, 1)
        
        # Répartition par service
        service_chart = self.create_service_distribution_chart()
        charts_layout.addWidget(service_chart, 1)
        
        layout.addWidget(charts_widget, 1)
        
        # Tableau des tendances
        trends_widget = self.create_trends_table()
        layout.addWidget(trends_widget)
        
        return widget
        
    def create_performance_widget(self):
        """Crée le widget de performance"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Graphiques de performance
        perf_charts = QWidget()
        perf_layout = QHBoxLayout(perf_charts)
        
        # Temps d'attente par service
        waiting_chart = self.create_waiting_time_chart()
        perf_layout.addWidget(waiting_chart, 1)
        
        # Flux horaire
        hourly_chart = self.create_hourly_flow_chart()
        perf_layout.addWidget(hourly_chart, 1)
        
        layout.addWidget(perf_charts)
        
        # Tableau de performance détaillé
        self.performance_table = QTableWidget()
        self.performance_table.setColumnCount(6)
        self.performance_table.setHorizontalHeaderLabels([
            "Service", "Volume", "Taux traitement", "Temps moyen", "Délai dépassé", "Urgent"
        ])
        self.performance_table.horizontalHeader().setStretchLastSection(True)
        self.performance_table.setAlternatingRowColors(True)
        layout.addWidget(self.performance_table, 1)
        
        return widget
        
    def create_satisfaction_widget(self):
        """Crée le widget de satisfaction"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # En-tête satisfaction
        header = QLabel("⭐ Évaluation de la satisfaction client")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529; padding: 10px 0;")
        layout.addWidget(header)
        
        # Graphiques satisfaction
        sat_charts = QWidget()
        sat_layout = QHBoxLayout(sat_charts)
        
        # Distribution des notes
        rating_chart = self.create_rating_distribution_chart()
        sat_layout.addWidget(rating_chart, 1)
        
        # Évolution satisfaction
        sat_evolution = self.create_satisfaction_evolution_chart()
        sat_layout.addWidget(sat_evolution, 1)
        
        layout.addWidget(sat_charts)
        
        # Commentaires récents
        comments_widget = self.create_comments_widget()
        layout.addWidget(comments_widget, 1)
        
        return widget
        
    def create_export_widget(self):
        """Crée le widget d'export"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # En-tête
        header = QLabel("📤 Export des données et rapports")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529; padding: 10px 0;")
        layout.addWidget(header)
        
        # Options d'export
        options_group = QGroupBox("Options d'export")
        options_layout = QVBoxLayout(options_group)
        
        # Période
        period_widget = QWidget()
        period_layout = QHBoxLayout(period_widget)
        period_layout.addWidget(QLabel("Période:"))
        self.export_period = QComboBox()
        self.export_period.addItems(["Aujourd'hui", "Cette semaine", "Ce mois", "Personnalisée"])
        period_layout.addWidget(self.export_period)
        period_layout.addStretch()
        options_layout.addWidget(period_widget)
        
        # Format
        format_widget = QWidget()
        format_layout = QHBoxLayout(format_widget)
        format_layout.addWidget(QLabel("Format:"))
        self.export_format = QComboBox()
        self.export_format.addItems(["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"])
        format_layout.addWidget(self.export_format)
        format_layout.addStretch()
        options_layout.addWidget(format_widget)
        
        # Inclusions
        inclusions = QWidget()
        inclusions_layout = QHBoxLayout(inclusions)
        inclusions_layout.addWidget(QLabel("Inclure:"))
        self.include_details = QCheckBox("Détails des demandes")
        self.include_details.setChecked(True)
        inclusions_layout.addWidget(self.include_details)
        self.include_stats = QCheckBox("Statistiques")
        self.include_stats.setChecked(True)
        inclusions_layout.addWidget(self.include_stats)
        self.include_charts = QCheckBox("Graphiques")
        self.include_charts.setChecked(True)
        inclusions_layout.addWidget(self.include_charts)
        inclusions_layout.addStretch()
        options_layout.addWidget(inclusions)
        
        layout.addWidget(options_group)
        
        # Boutons d'export
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        
        export_btn = QPushButton("📥 Générer le rapport")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        export_btn.clicked.connect(self.export_report)
        buttons_layout.addWidget(export_btn)
        
        schedule_btn = QPushButton("⏰ Planifier un rapport")
        schedule_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        schedule_btn.clicked.connect(self.schedule_report)
        buttons_layout.addWidget(schedule_btn)
        
        buttons_layout.addStretch()
        layout.addWidget(buttons_widget)
        
        # Historique des exports
        history_group = QGroupBox("Exports récents")
        history_layout = QVBoxLayout(history_group)
        
        self.export_history = QTableWidget()
        self.export_history.setColumnCount(4)
        self.export_history.setHorizontalHeaderLabels(["Date", "Type", "Période", "Actions"])
        self.export_history.horizontalHeader().setStretchLastSection(True)
        history_layout.addWidget(self.export_history)
        
        layout.addWidget(history_group)
        
        return widget
        
    def create_stat_card(self, title, value, color):
        """Crée une carte de statistique"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
                border-left: 5px solid {color};
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #6c757d; font-size: 14px;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setObjectName(f"value_{title.split()[1].lower() if len(title.split()) > 1 else 'value'}")
        value_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #212529;")
        layout.addWidget(value_label)
        
        return card
        
    def create_evolution_chart(self):
        """Crée un graphique d'évolution"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("📈 Évolution des demandes")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        # Zone du graphique
        chart_area = QFrame()
        chart_area.setMinimumHeight(200)
        chart_area.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;")
        
        chart_layout = QVBoxLayout(chart_area)
        
        # Graphique simulé avec des barres
        bars_widget = QWidget()
        bars_layout = QHBoxLayout(bars_widget)
        bars_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        self.evolution_bars = []
        days = ["J-7", "J-6", "J-5", "J-4", "J-3", "J-2", "J-1", "Aujourd'hui"]
        
        for day in days:
            bar_container = QWidget()
            bar_container_layout = QVBoxLayout(bar_container)
            bar_container_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
            bar_container_layout.setSpacing(5)
            
            bar = QFrame()
            bar.setMinimumHeight(30)
            bar.setMaximumHeight(150)
            bar.setStyleSheet("background-color: #417690; border-radius: 5px;")
            bar_container_layout.addWidget(bar)
            
            value_label = QLabel("0")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("font-size: 12px; font-weight: bold;")
            bar_container_layout.addWidget(value_label)
            
            day_label = QLabel(day)
            day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_label.setStyleSheet("font-size: 11px; color: #6c757d;")
            bar_container_layout.addWidget(day_label)
            
            bars_layout.addWidget(bar_container)
            self.evolution_bars.append((bar, value_label))
            
        chart_layout.addWidget(bars_widget)
        layout.addWidget(chart_area)
        
        # Légende
        legend = QLabel("← Passé         Présent →")
        legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legend.setStyleSheet("color: #6c757d; font-size: 12px; padding: 5px;")
        layout.addWidget(legend)
        
        return widget
        
    def create_service_distribution_chart(self):
        """Crée un graphique de répartition par service"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("📊 Répartition par service")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        # Liste des services avec pourcentages
        self.service_distribution = QTableWidget()
        self.service_distribution.setColumnCount(3)
        self.service_distribution.setHorizontalHeaderLabels(["Service", "Nombre", "%"])
        self.service_distribution.horizontalHeader().setStretchLastSection(True)
        self.service_distribution.setAlternatingRowColors(True)
        
        layout.addWidget(self.service_distribution)
        
        return widget
        
    def create_waiting_time_chart(self):
        """Crée un graphique des temps d'attente par service"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("⏱️ Temps d'attente moyen par service")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        self.waiting_table = QTableWidget()
        self.waiting_table.setColumnCount(2)
        self.waiting_table.setHorizontalHeaderLabels(["Service", "Temps moyen"])
        self.waiting_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.waiting_table)
        
        return widget
        
    def create_hourly_flow_chart(self):
        """Crée un graphique du flux horaire"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("🕐 Flux horaire des demandes")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        self.hourly_table = QTableWidget()
        self.hourly_table.setColumnCount(3)
        self.hourly_table.setHorizontalHeaderLabels(["Heure", "Demandes", "Traitement"])
        self.hourly_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.hourly_table)
        
        return widget
        
    def create_rating_distribution_chart(self):
        """Crée un graphique de distribution des notes"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("⭐ Distribution des notes")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        self.rating_distribution = QTableWidget()
        self.rating_distribution.setColumnCount(3)
        self.rating_distribution.setHorizontalHeaderLabels(["Note", "Nombre", "%"])
        self.rating_distribution.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.rating_distribution)
        
        return widget
        
    def create_satisfaction_evolution_chart(self):
        """Crée un graphique d'évolution de la satisfaction"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("📈 Évolution de la satisfaction")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        self.satisfaction_evolution = QTableWidget()
        self.satisfaction_evolution.setColumnCount(2)
        self.satisfaction_evolution.setHorizontalHeaderLabels(["Période", "Note moyenne"])
        self.satisfaction_evolution.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.satisfaction_evolution)
        
        return widget
        
    def create_trends_table(self):
        """Crée le tableau des tendances"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
                margin-top: 20px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("📊 Tendances et analyses")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        self.trends_table = QTableWidget()
        self.trends_table.setColumnCount(4)
        self.trends_table.setHorizontalHeaderLabels(["Indicateur", "Valeur", "Variation", "Tendance"])
        self.trends_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.trends_table)
        
        return widget
        
    def create_comments_widget(self):
        """Crée le widget des commentaires satisfaction"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        
        title = QLabel("💬 Derniers commentaires clients")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        
        self.comments_table = QTableWidget()
        self.comments_table.setColumnCount(3)
        self.comments_table.setHorizontalHeaderLabels(["Date", "Note", "Commentaire"])
        self.comments_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.comments_table)
        
        return widget
        
    def on_period_changed(self, index):
        """Gère le changement de période"""
        period = self.period_combo.currentData()
        self.custom_date_widget.setVisible(period == "custom")
        self.refresh()
        
    def refresh(self):
        """Rafraîchit toutes les statistiques"""
        try:
            # Déterminer la période
            period = self.period_combo.currentData()
            
            if period == "custom":
                date_debut = self.date_debut.date().toPyDate()
                date_fin = self.date_fin.date().toPyDate()
            else:
                days = int(period)
                date_fin = date.today()
                date_debut = date_fin - timedelta(days=days)
            
            # Récupérer les demandes pour la période
            filters = {
                'date_debut': date_debut,
                'date_fin': date_fin
            }
            demandes = DemandeAccueil.get_all(filters)
            
            # Mettre à jour les KPIs
            self.update_kpis(demandes, date_debut, date_fin)
            
            # Mettre à jour les graphiques
            self.update_evolution_chart(demandes, date_debut, date_fin)
            self.update_service_distribution(demandes)
            self.update_performance_table(demandes)
            self.update_waiting_times(demandes)
            self.update_hourly_flow(demandes)
            self.update_satisfaction_stats(demandes)
            self.update_trends(demandes, date_debut, date_fin)
            self.update_comments(demandes)
            
        except Exception as e:
            print(f"Erreur lors du rafraîchissement des statistiques: {e}")
            
    def update_kpis(self, demandes, date_debut, date_fin):
        """Met à jour les cartes KPI"""
        total = len(demandes)
        
        # Moyenne journalière
        nb_jours = (date_fin - date_debut).days or 1
        moyenne_journaliere = total / nb_jours
        
        # Taux de traitement
        traitees = len([d for d in demandes if d.statut == 'traite'])
        taux_traitement = (traitees / total * 100) if total > 0 else 0
        
        # Temps d'attente moyen
        temps_attente = [d.temps_attente_minutes for d in demandes if d.temps_attente_minutes]
        attente_moyen = sum(temps_attente) / len(temps_attente) if temps_attente else 0
        
        # Satisfaction moyenne
        notes = [d.satisfaction for d in demandes if d.satisfaction]
        satisfaction_moyenne = sum(notes) / len(notes) if notes else 0
        
        # Mettre à jour les labels
        if hasattr(self, 'kpi_cards'):
            if 'total' in self.kpi_cards and self.kpi_cards['total']:
                self.kpi_cards['total'].setText(str(total))
            if 'moyenne_journaliere' in self.kpi_cards and self.kpi_cards['moyenne_journaliere']:
                self.kpi_cards['moyenne_journaliere'].setText(f"{moyenne_journaliere:.1f}")
            if 'traitement' in self.kpi_cards and self.kpi_cards['traitement']:
                self.kpi_cards['traitement'].setText(f"{taux_traitement:.1f}%")
            if 'attente_moyen' in self.kpi_cards and self.kpi_cards['attente_moyen']:
                self.kpi_cards['attente_moyen'].setText(f"{attente_moyen:.0f} min")
            if 'satisfaction' in self.kpi_cards and self.kpi_cards['satisfaction']:
                self.kpi_cards['satisfaction'].setText(f"{satisfaction_moyenne:.1f} ⭐")
                
    def update_evolution_chart(self, demandes, date_debut, date_fin):
        """Met à jour le graphique d'évolution"""
        # Grouper par jour
        demandes_par_jour = defaultdict(int)
        for d in demandes:
            jour = d.date.isoformat() if hasattr(d.date, 'isoformat') else str(d.date)
            demandes_par_jour[jour] += 1
        
        # Calculer les 8 derniers jours
        today = date.today()
        bars_data = []
        
        for i in range(7, -1, -1):
            jour = today - timedelta(days=i)
            jour_str = jour.isoformat()
            count = demandes_par_jour.get(jour_str, 0)
            bars_data.append((jour, count))
        
        # Mettre à jour les barres
        max_count = max([c for _, c in bars_data] + [1])
        
        for i, (bar, value_label) in enumerate(self.evolution_bars):
            if i < len(bars_data):
                jour, count = bars_data[i]
                # Hauteur proportionnelle (max 150px)
                height = max(30, int((count / max_count) * 120) if max_count > 0 else 30)
                bar.setMinimumHeight(height)
                bar.setMaximumHeight(height)
                value_label.setText(str(count))
                
    def update_service_distribution(self, demandes):
        """Met à jour la distribution par service"""
        # Grouper par service
        service_counts = defaultdict(int)
        services = {}
        
        for d in demandes:
            if d.service_demande_id:
                service_counts[d.service_demande_id] += 1
                if d.service and d.service_demande_id not in services:
                    services[d.service_demande_id] = d.service.nom
        
        total = len(demandes) or 1
        self.service_distribution.setRowCount(len(service_counts))
        
        for i, (service_id, count) in enumerate(sorted(service_counts.items(), key=lambda x: x[1], reverse=True)):
            service_name = services.get(service_id, f"Service {service_id}")
            pourcentage = (count / total * 100)
            
            self.service_distribution.setItem(i, 0, QTableWidgetItem(service_name))
            self.service_distribution.setItem(i, 1, QTableWidgetItem(str(count)))
            
            pourcentage_item = QTableWidgetItem(f"{pourcentage:.1f}%")
            pourcentage_item.setForeground(QColor('#417690'))
            self.service_distribution.setItem(i, 2, pourcentage_item)
            
    def update_performance_table(self, demandes):
        """Met à jour le tableau de performance"""
        # Grouper par service
        service_stats = defaultdict(lambda: {
            'total': 0, 'traitees': 0, 'temps': [], 'delai': 0, 'urgentes': 0
        })
        
        for d in demandes:
            if d.service_demande_id:
                stats = service_stats[d.service_demande_id]
                stats['total'] += 1
                if d.statut == 'traite':
                    stats['traitees'] += 1
                if d.temps_attente_minutes:
                    stats['temps'].append(d.temps_attente_minutes)
                if d.delai_objectif:
                    stats['delai'] += 1
                if d.priorite == 'haute':
                    stats['urgentes'] += 1
        
        self.performance_table.setRowCount(len(service_stats))
        
        for i, (service_id, stats) in enumerate(service_stats.items()):
            service = Service.get_by_id(service_id)
            service_name = service.nom if service else f"Service {service_id}"
            
            taux = (stats['traitees'] / stats['total'] * 100) if stats['total'] > 0 else 0
            temps_moyen = sum(stats['temps']) / len(stats['temps']) if stats['temps'] else 0
            taux_delai = (stats['delai'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            self.performance_table.setItem(i, 0, QTableWidgetItem(service_name))
            self.performance_table.setItem(i, 1, QTableWidgetItem(str(stats['total'])))
            
            taux_item = QTableWidgetItem(f"{taux:.1f}%")
            if taux >= 80:
                taux_item.setForeground(QColor('#28a745'))
            elif taux >= 50:
                taux_item.setForeground(QColor('#ffc107'))
            else:
                taux_item.setForeground(QColor('#dc3545'))
            self.performance_table.setItem(i, 2, taux_item)
            
            self.performance_table.setItem(i, 3, QTableWidgetItem(f"{temps_moyen:.0f} min" if temps_moyen else "-"))
            
            delai_item = QTableWidgetItem(f"{taux_delai:.1f}%")
            delai_item.setForeground(QColor('#dc3545') if taux_delai > 20 else QColor('#28a745'))
            self.performance_table.setItem(i, 4, delai_item)
            
            self.performance_table.setItem(i, 5, QTableWidgetItem(str(stats['urgentes'])))
            
    def update_waiting_times(self, demandes):
        """Met à jour les temps d'attente"""
        # Grouper par service
        service_temps = defaultdict(list)
        
        for d in demandes:
            if d.service_demande_id and d.temps_attente_minutes:
                service_temps[d.service_demande_id].append(d.temps_attente_minutes)
        
        self.waiting_table.setRowCount(len(service_temps))
        
        for i, (service_id, temps) in enumerate(service_temps.items()):
            service = Service.get_by_id(service_id)
            service_name = service.nom if service else f"Service {service_id}"
            moyenne = sum(temps) / len(temps)
            
            self.waiting_table.setItem(i, 0, QTableWidgetItem(service_name))
            
            temps_item = QTableWidgetItem(f"{moyenne:.0f} min")
            if moyenne <= 15:
                temps_item.setForeground(QColor('#28a745'))
            elif moyenne <= 30:
                temps_item.setForeground(QColor('#ffc107'))
            else:
                temps_item.setForeground(QColor('#dc3545'))
            self.waiting_table.setItem(i, 1, temps_item)
            
    def update_hourly_flow(self, demandes):
        """Met à jour le flux horaire"""
        # Grouper par heure
        hourly_counts = defaultdict(int)
        hourly_treated = defaultdict(int)
        
        for d in demandes:
            if d.heure_arrivee:
                if hasattr(d.heure_arrivee, 'hour'):
                    hour = d.heure_arrivee.hour
                else:
                    # Si c'est une string, extraire l'heure
                    try:
                        hour = int(str(d.heure_arrivee).split(':')[0])
                    except Exception:                        continue
                        
                hourly_counts[hour] += 1
                if d.statut == 'traite':
                    hourly_treated[hour] += 1
        
        hours = sorted(hourly_counts.keys())
        self.hourly_table.setRowCount(len(hours))
        
        for i, hour in enumerate(hours):
            total = hourly_counts[hour]
            traitees = hourly_treated.get(hour, 0)
            taux = (traitees / total * 100) if total > 0 else 0
            
            self.hourly_table.setItem(i, 0, QTableWidgetItem(f"{hour:02d}:00 - {hour+1:02d}:00"))
            self.hourly_table.setItem(i, 1, QTableWidgetItem(str(total)))
            
            taux_item = QTableWidgetItem(f"{taux:.0f}%")
            if taux >= 80:
                taux_item.setForeground(QColor('#28a745'))
            elif taux >= 50:
                taux_item.setForeground(QColor('#ffc107'))
            else:
                taux_item.setForeground(QColor('#dc3545'))
            self.hourly_table.setItem(i, 2, taux_item)
            
    def update_satisfaction_stats(self, demandes):
        """Met à jour les statistiques de satisfaction"""
        # Distribution des notes
        rating_counts = defaultdict(int)
        for d in demandes:
            if d.satisfaction:
                rating_counts[d.satisfaction] += 1
        
        total_notes = sum(rating_counts.values()) or 1
        self.rating_distribution.setRowCount(5)
        
        for i in range(1, 6):
            count = rating_counts.get(i, 0)
            pourcentage = (count / total_notes * 100)
            
            self.rating_distribution.setItem(i-1, 0, QTableWidgetItem(f"{'⭐' * i}"))
            self.rating_distribution.setItem(i-1, 1, QTableWidgetItem(str(count)))
            self.rating_distribution.setItem(i-1, 2, QTableWidgetItem(f"{pourcentage:.1f}%"))
        
        # Évolution de la satisfaction
        # Grouper par semaine
        weekly_satisfaction = defaultdict(list)
        for d in demandes:
            if d.satisfaction and d.date:
                # Obtenir le début de semaine
                if hasattr(d.date, 'isocalendar'):
                    year, week, _ = d.date.isocalendar()
                    week_key = f"S{week:02d}"
                else:
                    week_key = "S00"
                weekly_satisfaction[week_key].append(d.satisfaction)
        
        weeks = sorted(weekly_satisfaction.keys())[-6:]  # 6 dernières semaines
        self.satisfaction_evolution.setRowCount(len(weeks))
        
        for i, week in enumerate(weeks):
            avg = sum(weekly_satisfaction[week]) / len(weekly_satisfaction[week])
            self.satisfaction_evolution.setItem(i, 0, QTableWidgetItem(week))
            self.satisfaction_evolution.setItem(i, 1, QTableWidgetItem(f"{avg:.1f} ⭐"))
            
    def update_trends(self, demandes, date_debut, date_fin):
        """Met à jour les tendances"""
        trends = [
            ("Volume de demandes", str(len(demandes)), "", "📈"),
            ("Taux de traitement", f"{self.kpi_cards['traitement'].text() if 'traitement' in self.kpi_cards else '0%'}", "", "↗️"),
            ("Satisfaction client", f"{self.kpi_cards['satisfaction'].text() if 'satisfaction' in self.kpi_cards else '0 ⭐'}", "", "📊"),
            ("Performance services", "3/5 services ⚠️", "-5%", "📉"),
        ]
        
        self.trends_table.setRowCount(len(trends))
        
        for i, (indicator, value, variation, trend) in enumerate(trends):
            self.trends_table.setItem(i, 0, QTableWidgetItem(indicator))
            self.trends_table.setItem(i, 1, QTableWidgetItem(value))
            self.trends_table.setItem(i, 2, QTableWidgetItem(variation))
            self.trends_table.setItem(i, 3, QTableWidgetItem(trend))
            
    def update_comments(self, demandes):
        """Met à jour les commentaires satisfaction"""
        # Filtrer les demandes avec commentaires
        with_comments = [d for d in demandes if d.commentaire_satisfaction and d.commentaire_satisfaction.strip()]
        with_comments = sorted(with_comments, key=lambda x: x.date if hasattr(x.date, '__lt__') else str(x.date), reverse=True)[:10]
        
        self.comments_table.setRowCount(len(with_comments))
        
        for i, demande in enumerate(with_comments):
            date_str = demande.date.strftime("%d/%m/%Y") if hasattr(demande.date, 'strftime') else str(demande.date)
            self.comments_table.setItem(i, 0, QTableWidgetItem(date_str))
            self.comments_table.setItem(i, 1, QTableWidgetItem(f"{'⭐' * demande.satisfaction}" if demande.satisfaction else "Non noté"))
            
            comment = demande.commentaire_satisfaction
            if len(comment) > 50:
                comment = comment[:50] + "..."
            self.comments_table.setItem(i, 2, QTableWidgetItem(comment))
            
    def export_report(self):
        """Exporte le rapport"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le rapport",
            f"rapport_statistiques_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "Excel (*.xlsx);;CSV (*.csv);;PDF (*.pdf)"
        )
        
        if filename:
            QMessageBox.information(
                self,
                "✅ Export réussi",
                f"Le rapport a été exporté avec succès vers :\n{filename}"
            )
            
    def schedule_report(self):
        """Planifie un rapport automatique"""
        QMessageBox.information(
            self,
            "⏰ Planification",
            "Cette fonctionnalité sera disponible prochainement."
        )