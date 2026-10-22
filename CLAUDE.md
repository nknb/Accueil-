# CNPS Accueil

Application de bureau de gestion de l'accueil (CNPS, Côte d'Ivoire), utilisée sur des postes Windows qui partagent une base SQLite sur un partage réseau. Interface en français.

## Stack
Python 3.11, PyQt6 + QtCharts, SQLite (stdlib), bcrypt, openpyxl (export Excel). Versions épinglées dans `requirements.txt` (dev: `requirements-dev.txt`).

## Arborescence
- `main.py` — point d'entrée et fenêtre de connexion (`LoginApp`)
- `config.py` — `AppConfig`: chemins de la base, PRAGMA, rôles, durées de verrouillage
- `database/connection.py` — `DatabaseConnection` (instance globale `db`), schéma, retry sur verrou
- `database/models.py` — `DemandeAccueil`, `Service`, `Motif`, `Permission`, `Role`
- `sidebar/` — fenêtre principale, navigation, filtrage des vues par rôle (`main_windows.py`)
- `widgets/{accueil,preaccueil,database,dashboard,users}/` — une page par dossier
- `ui/` — widgets partagés (formulaire de demande, statistiques, permissions)
- `utils/` — `PasswordManager` (bcrypt), validateurs, loggers
- `sidebar/style.qss` — styles; `resources/` — icônes; `res.py`, `*/resource.py`, `*/resource_rc.py` — générés par Qt (ne pas éditer)
- `seed_data.py` — jeu de données de démonstration (écrit dans `db.sqlite3` du dossier courant)
- `tests/` — pytest (base temporaire, jamais `db.sqlite3`)

## Commandes
- Installer: `pip install -r requirements-dev.txt`
- Lancer: `python main.py`
- Données de démo: `python seed_data.py`
- Tests: `python -m pytest`
- Build PyInstaller: `pyinstaller AccueilCNPS.spec`
- Build Nuitka: `bash build_nuitka.sh` (à lancer sous Windows: PyQt6 n'est pas supporté par Nuitka sous macOS)

## Conventions
- PEP 8, annotations de type, docstrings en français.
- Styles dans les fichiers `.qss`, pas de feuilles de style inline nouvelles.
- Requêtes SQL toujours paramétrées (`?`). Un nom de table n'est inséré dans le SQL que s'il vient d'une liste fixe.
- Pas de `print` pour les erreurs: utiliser `logging` / `utils.logger`. Jamais de nom, prénom, n° CNPS ou mot de passe dans les logs.
- Connexions SQLite fermées avec `with closing(...)` ou via `db.get_connection()`.

## Zones sensibles
- **Authentification** (`main.py`, `utils/password_manager.py`): bcrypt seulement, aucun mot de passe en dur ni mémorisé. Verrouillage après 5 échecs, stocké en base (`echecs`, `verrouille_jusqua`), incrément atomique.
- **Rôles** (`database/models.py:Permission`, `sidebar/main_windows.py:_apply_role_permissions`): admin, manager, accueil, preaccueil. Les pages Base de données et Utilisateurs sont réservées à l'admin.
- **Base de données**: `db.sqlite3` contient des données personnelles réelles. Elle n'est jamais commitée ni embarquée dans un build. `db_config.json` est local (modèle: `db_config.example.json`).
- **Numéro de demande**: calculé dans l'INSERT (`DemandeAccueil.save`), pour éviter les doublons entre postes.

## Workflow obligatoire
`/ecc:plan` → tdd-workflow → `/python-review` → vérification (`python -m pytest`, lancement de l'app)
