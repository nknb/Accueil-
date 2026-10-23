# CNPS Accueil

Application de bureau de gestion de l'accueil de la Caisse Nationale de Prévoyance Sociale (Côte d'Ivoire). Elle tourne sur des postes Windows qui partagent une base SQLite placée sur un partage réseau. L'interface est en français.

## Fonctionnalités

- **Pré-accueil** : enregistrement des visiteurs à leur arrivée (nom, prénom, n° CNPS, service, motif, contact). L'heure d'arrivée est prise au clic.
- **Accueil** : liste des demandes du jour, traitement d'une demande (heure de réception, note de satisfaction), calcul du temps d'attente et de l'objectif de 15 minutes.
- **Dashboard** : statistiques par période (services, motifs, temps d'attente, satisfaction, usagers fréquents) avec graphiques QtCharts et export Excel.
- **Base de données** : consultation, filtres, création, modification et suppression des demandes, export Excel (administrateur).
- **Utilisateurs** : comptes, motifs, services et chemin de la base (administrateur).
- Les demandes encore « en attente » des jours précédents passent en `non_traite` à la connexion suivante.

## Rôles

| Rôle | Pages accessibles |
|---|---|
| `admin` | Accueil, Pré-accueil, Dashboard, Base de données, Utilisateurs |
| `manager` | Accueil, Pré-accueil, Dashboard |
| `accueil` | Accueil, Pré-accueil |
| `preaccueil` | Pré-accueil |

Au premier démarrage (table des utilisateurs vide), quatre comptes (`admin`, `manager`, `accueil`, `preaccueil`) sont créés avec un mot de passe aléatoire affiché une seule fois. Après 5 échecs, le compte est verrouillé 5 minutes (compteur stocké en base).

## Installation

Python 3.11.

```bash
pip install -r requirements-dev.txt   # requirements.txt pour l'exécution seule
python main.py
```

## Base de données

Le chemin est résolu dans cet ordre :

1. `db_config.json` à côté de l'application (modèle : `db_config.example.json`, modifiable depuis Utilisateurs > Configuration) ;
2. variable d'environnement `CNPS_DB_PATH` ;
3. `db.sqlite3` dans le dossier de l'application.

`db.sqlite3` contient des données personnelles : il n'est jamais commité ni embarqué dans un build. Le schéma est créé automatiquement au démarrage. `python seed_data.py` génère des données de démonstration ; il refuse de s'exécuter si la base contient déjà des demandes, sauf avec `--force`.

## Tests

```bash
python -m pytest
```

Les tests utilisent une base temporaire, jamais `db.sqlite3`.

## Build

- PyInstaller : `pyinstaller AccueilCNPS.spec`
- Nuitka : `bash build_nuitka.sh` (à lancer sous Windows, PyQt6 n'étant pas supporté par Nuitka sous macOS)
- Déploiement sur un poste : `installer_windows/INSTALLER_PC.bat` (en administrateur) ; `DESINSTALLER.bat` supprime tout le dossier d'installation, y compris une éventuelle base locale.

## Structure

- `main.py` : point d'entrée et fenêtre de connexion
- `config.py` : chemins, PRAGMA SQLite, rôles, durées de verrouillage
- `database/` : connexion SQLite (retry sur verrou) et modèles
- `sidebar/` : fenêtre principale, navigation et filtrage des pages par rôle
- `widgets/` : une page par dossier (`accueil`, `preaccueil`, `dashboard`, `database`, `users`)
- `ui/dashboard_theme.py` : couleurs partagées du dashboard
- `utils/` : mots de passe (bcrypt), validateurs, journalisation
- `tests/` : pytest

## Suivi des tâches

Le suivi se fait avec [beads](https://github.com/gastownhall/beads) (`bd ready`, `bd list`). Voir `CLAUDE.md` et `AGENTS.md` pour les conventions du projet.
