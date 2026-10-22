# ui/permissions.py
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from database.models import Permission, Role

class PermissionManager:
    """Gestionnaire centralisé des permissions UI"""
    
    def __init__(self, user):
        self.user = user
        self.user_role = None
        if user and 'role' in user:
            try:
                self.user_role = Role(user['role'])
            except Exception:                pass
    
    def has_permission(self, permission: str) -> bool:
        """Vérifie si l'utilisateur a une permission"""
        if not self.user or not self.user_role:
            return False
        return Permission.has_permission(self.user_role, permission)
    
    def filter_menu_items(self, menu_items):
        """Filtre les éléments de menu selon les permissions"""
        return [item for item in menu_items if self.has_permission(item.get('permission', ''))]
    
    def configure_ui_for_role(self, widget):
        """Configure l'interface selon le rôle"""
        role_configs = {
            Role.ADMIN: {
                'visible': ['dashboard', 'demandes', 'stats', 'admin', 'export'],
                'enabled': ['all'],
                'theme': 'admin'
            },
            Role.MANAGER: {
                'visible': ['dashboard', 'demandes', 'stats', 'export'],
                'enabled': ['dashboard', 'demandes', 'stats', 'export'],
                'theme': 'manager'
            },
            Role.ACCUEIL: {
                'visible': ['dashboard', 'demandes'],
                'enabled': ['dashboard', 'demandes'],
                'theme': 'agent'
            },
            Role.PRE_ACCUEIL: {
                'visible': ['demandes'],
                'enabled': ['demandes'],
                'theme': 'preaccueil'
            }
        }
        
        config = role_configs.get(self.user_role, {})
        return config

class RoleBasedAccessMixin:
    """Mixin pour ajouter le contrôle d'accès basé sur les rôles aux widgets"""
    
    def setup_role_access(self, user):
        self.permission_manager = PermissionManager(user)
        self.apply_role_restrictions()
    
    def apply_role_restrictions(self):
        """Applique les restrictions selon le rôle"""
        if hasattr(self, 'permission_manager'):
            config = self.permission_manager.configure_ui_for_role(self)
            self.hide_unauthorized_elements(config.get('visible', []))
            self.disable_unauthorized_elements(config.get('enabled', []))
    
    def hide_unauthorized_elements(self, visible_sections):
        """Masque les sections non autorisées"""
        pass
    
    def disable_unauthorized_elements(self, enabled_sections):
        """Désactive les éléments non autorisés"""
        pass