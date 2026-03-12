# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project_dir = Path.cwd().resolve()

hiddenimports = []
hiddenimports += collect_submodules("widgets")
hiddenimports += collect_submodules("sidebar")
hiddenimports += collect_submodules("database")
hiddenimports += collect_submodules("utils")
hiddenimports += [
    "pkgutil",
    "bcrypt._bcrypt",
]

# Fichiers nécessaires au runtime
# - sidebar/style.qss : thème de l'application
# La base SQLite n'est pas embarquée pour permettre un déploiement
# multi-utilisateurs sur une base partagée externe (CNPS_DB_PATH).
datas = [
    (str(project_dir / "sidebar" / "style.qss"), "sidebar"),
]

block_cipher = None

a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CNPSAccueil",
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CNPSAccueil",
)
