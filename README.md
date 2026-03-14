# CNPS Accueil — Résumé de l’application

L’application CNPS Accueil est une interface de gestion et de suivi des demandes, conçue avec Python (PyQt6) et une base SQLite. Elle propose :

- **Interface graphique moderne** : basée sur PyQt6, avec une fenêtre principale, une barre latérale, et plusieurs pages (Accueil, Dashboard, Pré-Accueil, Base de données, Utilisateurs).
- **Gestion des utilisateurs** : authentification, rôles (administrateur, accueil), permissions, gestion des comptes.
- **Tableau de bord** : statistiques, graphiques interactifs (QtCharts), indicateurs clés, filtres dynamiques.
- **Gestion des demandes** : création, suivi, historique, motifs, services.
- **Base de données locale** : stockage sécurisé des données via SQLite, vérification et création automatique des tables.
- **Modularité** : chaque fonctionnalité est organisée en modules (widgets, sidebar, database, utils), facilitant la maintenance et l’évolution.
- **Personnalisation** : styles graphiques via fichiers .qss, ressources (icônes, images) intégrées.
- **Logs et sécurité** : journalisation des actions, gestion des mots de passe (hashage), validation des entrées.

### Structure du projet

- `main.py` : point d’entrée, gestion de l’interface et du cycle de vie.
- `sidebar/` : barre latérale, navigation, ressources.
- `widgets/` : pages principales (Accueil, Dashboard, Pré-Accueil, Base de données, Utilisateurs).
- `database/` : connexion, modèles, gestion des données.
- `utils/` : outils de validation, gestion des logs, sécurité.
- `resources/` : images, icônes, fichiers de style.

### Technologies utilisées

- Python 3.11
- PyQt6 & QtCharts
- SQLite
- pandas, numpy, bcrypt
# Accueil-
Projet simple de gestion de l’accueil
