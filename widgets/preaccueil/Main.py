"""Test/Demo script for PreAccueil widget.
This file is for standalone testing only. Use preaccueil_page.py for app integration.
"""

import sys
from PyQt6.QtWidgets import QApplication
from preaccueil_page import PreAccueilPage


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PreAccueilPage()
