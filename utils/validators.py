# utils/validators.py
"""Module de validation des entrées utilisateur"""

import re
from typing import Tuple, Optional
from .logger import auth_logger


class InputValidator:
    """Classe pour valider les entrées utilisateur"""
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    USERNAME_PATTERN = re.compile(r'[a-zA-Z0-9_-]{3,20}')
    PASSWORD_MIN_LENGTH = 8
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, Optional[str]]:
        """Valide le nom d'utilisateur
        
        Args:
            username: Nom d'utilisateur à valider
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not username:
            return False, "Le nom d'utilisateur ne peut pas être vide"
        
        if len(username) < 3:
            return False, "Le nom d'utilisateur doit avoir au minimum 3 caractères"
        
        if len(username) > 20:
            return False, "Le nom d'utilisateur ne peut pas dépasser 20 caractères"
        
        if not InputValidator.USERNAME_PATTERN.fullmatch(username):
            return False, "Le nom d'utilisateur ne peut contenir que des lettres, chiffres, tirets et underscores"
        
        return True, None
    
    @staticmethod
    def validate_password(password: str, confirm_password: str = None) -> Tuple[bool, Optional[str]]:
        """Valide le mot de passe
        
        Args:
            password: Mot de passe à valider
            confirm_password: Confirmation du mot de passe (optionnel)
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not password:
            return False, "Le mot de passe ne peut pas être vide"
        
        if len(password) < InputValidator.PASSWORD_MIN_LENGTH:
            return False, f"Le mot de passe doit avoir au minimum {InputValidator.PASSWORD_MIN_LENGTH} caractères"
        
        # Vérifier la force du mot de passe
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        if len(password.encode('utf-8')) > 72:
            return False, "Le mot de passe ne peut pas dépasser 72 octets"
        
        if not (has_upper and has_lower and has_digit):
            return False, "Le mot de passe doit contenir au minimum une majuscule, une minuscule et un chiffre"
        
        if confirm_password is not None:
            if password != confirm_password:
                return False, "Les mots de passe ne correspondent pas"
        
        return True, None
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """Valide l'adresse email
        
        Args:
            email: Email à valider
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not email:
            return False, "L'email ne peut pas être vide"
        
        if len(email) > 255:
            return False, "L'email ne peut pas dépasser 255 caractères"
        
        if not InputValidator.EMAIL_PATTERN.fullmatch(email) or '..' in email or email.startswith('.'):
            return False, "Format d'email invalide"
        
        return True, None
    
    @staticmethod
    def validate_login(username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Valide les données de connexion
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            Tuple (is_valid, error_message)
        """
        # Valider le nom d'utilisateur
        is_valid, error = InputValidator.validate_username(username)
        if not is_valid:
            auth_logger.warning("Tentative de connexion avec un nom d'utilisateur invalide")
            return False, error
        
        # Vérifier les mots de passes (ne pas valider la force pour la connexion)
        if not password:
            auth_logger.warning("Tentative de connexion sans mot de passe")
            return False, "Le mot de passe ne peut pas être vide"
        
        if len(password) < 3:  # Minimum pour la connexion
            return False, "Mot de passe invalide"
        
        return True, None
    
    @staticmethod
    def sanitize_input(input_text: str) -> str:
        """Nettoie les entrées pour éviter les injections SQL
        
        Args:
            input_text: Texte à nettoyer
            
        Returns:
            str: Texte nettoyé
        """
        if not input_text:
            return ""
        
        # Supprimer les espaces avant et après
        cleaned = input_text.strip()
        
        # Remplacer les caractères dangereux
        dangerous_chars = {'\'': '', '"': '', ';': '', '--': '', '/*': '', '*/': ''}
        for char, replacement in dangerous_chars.items():
            cleaned = cleaned.replace(char, replacement)
        
        return cleaned
