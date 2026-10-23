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

## Sauvegarde

La base est un fichier unique partagé: sans sauvegarde, une corruption ou une panne du partage fait tout perdre. La sauvegarde est une copie cohérente faite avec l'API de SQLite (les autres postes peuvent continuer à travailler), vérifiée par `PRAGMA integrity_check`, puis rangée dans le dossier `sauvegardes/` à côté de la base (`accueil-AAAAMMJJ-HHMMSS.sqlite3`). Les 30 dernières sont conservées.

- **À la demande** : Utilisateurs > Configuration > « Sauvegarder maintenant » (affiche aussi la date de la dernière sauvegarde).
- **Chaque nuit** (recommandé), sur un poste ou le serveur, une seule fois pour toute l'agence : clic droit > « Exécuter en tant qu'administrateur » sur `installer_windows\PLANIFIER_SAUVEGARDE.bat` (option : `PLANIFIER_SAUVEGARDE.bat 22:00 30` pour l'heure et le nombre de copies gardées). Il crée la tâche Windows « CNPS Accueil sauvegarde » avec **votre** compte (le mot de passe est demandé ; ce compte doit pouvoir écrire sur le partage de la base) et propose un essai immédiat. Équivalent à la main :

  ```bat
  schtasks /Create /SC DAILY /ST 22:00 /TN "CNPS Accueil sauvegarde" /TR "C:\CNPS\AccueilCNPS\AccueilCNPS.exe --sauvegarde"
  ```

  Options : `--base CHEMIN`, `--dossier DOSSIER`, `--garder N`. Code de sortie : 0 réussi, 1 échec, 2 arguments invalides ; le détail est dans `logs/app.log`.
- **Restaurer** : fermer l'application sur tous les postes, copier la sauvegarde choisie à la place de `db.sqlite3`, relancer.
- Vérifiez de temps en temps qu'une sauvegarde récente existe et copiez le dossier `sauvegardes/` hors du serveur.

Au démarrage, `PRAGMA optimize` met à jour les statistiques de SQLite pour que les index soient bien choisis (aucune action à faire).

## Fonctionnement multi-postes

Plusieurs postes lisent et écrivent le même fichier SQLite. Pour rester fluide :

- **Pas de rechargement inutile** : chaque page compare `db.change_token()` à la valeur précédente et ne relit rien si elle est identique. Ce jeton est un compteur (`app_meta.version`) que des déclencheurs SQL font avancer à chaque écriture sur les demandes, services et motifs ; il ne dépend pas de l'horloge des postes.
- **Écritures sérialisées** : `BEGIN IMMEDIATE`, nouvel essai avec délai croissant si la base est verrouillée, numéro de demande calculé dans l'`INSERT`.
- **Conflits** : un traitement déjà fait ailleurs est refusé (« déjà traitée depuis un autre poste ») ; la modification d'une demande depuis la page Base de données est refusée si la ligne a changé entre-temps.
- **Requêtes indexables** : les filtres de date s'écrivent `date >= ? AND date < ?` (jamais `DATE(date) = ?`).
- **Recherche** : la fonction SQL `PYLOWER` rend la recherche insensible à la casse, accents compris.

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
