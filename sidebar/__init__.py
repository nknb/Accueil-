"""Package sidebar

Expose `Ui_MainWindow` au niveau du package pour permettre
`from sidebar import Ui_MainWindow`.
"""

from .sidebar import Ui_MainWindow

__all__ = ["Ui_MainWindow"]
