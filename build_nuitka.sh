#!/bin/bash
# build_nuitka.sh — Compilation Nuitka de l'application CNPS Accueil
# Usage : bash build_nuitka.sh

set -e

PYTHON="${PYTHON:-python}"  # PyQt6 n'est pas supporté par Nuitka sous macOS: compiler sous Windows
PROJECT="$(dirname "$0")"

echo "==> Compilation Nuitka — CNPS Accueil"
echo "    Python : $PYTHON"
echo "    Projet : $PROJECT"
echo ""

cd "$PROJECT"

"$PYTHON" -m nuitka \
    --standalone \
    --enable-plugin=pyqt6 \
    --include-data-dir=resources=resources \
    --include-data-dir=ui=ui \
    --include-data-dir=sidebar=sidebar \
    --include-data-dir=widgets=widgets \
    --include-data-dir=utils=utils \
    --include-data-files=res.py=res.py \
    --nofollow-import-to=tkinter \
    --nofollow-import-to=matplotlib \
    --nofollow-import-to=scipy \
    --nofollow-import-to=IPython \
    --nofollow-import-to=jupyter \
    --output-filename=AccueilCNPS \
    --output-dir=dist_nuitka \
    --remove-output \
    main.py

echo ""
echo "==> Build terminé : dist_nuitka/main.dist/"
