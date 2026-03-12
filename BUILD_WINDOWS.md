# Build Windows avec PyInstaller

Ce projet doit etre compile **sur Windows** pour obtenir un `.exe` Windows.

## Prerequis
- Windows 10/11
- Python 3.11 installe (et `py` disponible)
- Le projet copie sur la machine Windows

## Build rapide
1. Ouvrir `cmd` dans le dossier du projet.
2. Lancer:

```bat
build_windows.bat
```

## Installation rapide sur un poste utilisateur
1. Copier **tout le dossier `dist`** sur le poste (exe + `_internal` + `db.sqlite3`).
2. Lancer:

```bat
dist\CNPSAccueil.exe
```

## Resultat
- Executable genere:

`dist\CNPSAccueil.exe`

- Dossier runtime requis:

`dist\_internal\`

Ne pas deplacer/copy uniquement le `.exe` sans le dossier `_internal`.

## Portabilite des donnees
- En mode `.exe`, l'application utilise uniquement `db.sqlite3` situe dans le meme dossier que `CNPSAccueil.exe`.
- Si vous deplacez/copiez le dossier `dist` vers un autre poste, les donnees se deplacent avec ce dossier.
- Pour conserver les donnees, copiez toujours le dossier `dist` complet.

## Notes
- En mode executable, `CNPS_DB_PATH` n'est pas utilise: seule la base locale du dossier `dist` est prise en compte.
- Le style `sidebar/style.qss` est inclus dans le build.
- Si SmartScreen bloque l'exe, choisir **Informations complementaires** puis **Executer quand meme**.
