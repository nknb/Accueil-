# AccueilCNPS.spec
# Fichier de configuration PyInstaller pour l'application CNPS Accueil
# Générer le .exe avec : pyinstaller AccueilCNPS.spec

import sys
from pathlib import Path

block_cipher = None
PROJECT_DIR = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[
        # Ressources images
        ('resources', 'resources'),
        # Fichiers UI
        ('ui', 'ui'),
        # Sidebar (styles, layouts)
        ('sidebar', 'sidebar'),
        # Widgets
        ('widgets', 'widgets'),
        # Utils
        ('utils', 'utils'),
        # Fichier de ressources Qt compilé
        ('res.py', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtCharts',
        'PyQt6.QtSql',
        'sqlite3',
        'bcrypt',
        'hashlib',
        'json',
        'pathlib',
        'widgets.accueil.accueil_page',
        'widgets.preaccueil.preaccueil_page',
        'widgets.dashboard.Main',
        'widgets.users.Main',
        'widgets.database.database_page',
        'sidebar.main_windows',
        'utils.password_manager',
        'config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AccueilCNPS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Pas de fenêtre console noire
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='resources/images/cnps_icon.ico',  # Décommenter si vous avez une icône .ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AccueilCNPS',
)
