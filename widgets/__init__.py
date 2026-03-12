# widgets/__init__.py
"""Package des widgets de l'application CNPS Accueil"""

from .accueil import AccueilPage
from .dashboard import DashboardPage
from .preaccueil import PreAccueilPage
from .database import DatabasePage
from .users import UsersPage

__all__ = [
    'AccueilPage',
    'DashboardPage',
    'PreAccueilPage',
    'DatabasePage',
    'UsersPage',
]
