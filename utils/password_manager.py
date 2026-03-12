# utils/password_manager.py
"""Gestion sécurisée des mots de passe avec bcrypt"""

import bcrypt
from .logger import auth_logger
from typing import Optional


class PasswordManager:
    """Classe pour gérer le hachage et la vérification des mots de passe"""
    
    # Coût de hachage bcrypt (13 est un bon équilibre)
    BCRYPT_COST = 13
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hache un mot de passe avec bcrypt
        
        Args:
            password: Mot de passe en clair
            
        Returns:
            str: Mot de passe hashé
            
        Raises:
            ValueError: Si le mot de passe est vide
        """
        if not password:
            raise ValueError("Le mot de passe ne peut pas être vide")
        
        try:
            salt = bcrypt.gensalt(rounds=PasswordManager.BCRYPT_COST)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            auth_logger.debug("Mot de passe hashé avec succès")
            return hashed.decode('utf-8')
        except Exception as e:
            auth_logger.error(f"Erreur lors du hachage du mot de passe: {str(e)}")
            raise
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe en clair contre sa version hashée
        
        Args:
            password: Mot de passe en clair à vérifier
            hashed_password: Mot de passe hashé stocké en BD
            
        Returns:
            bool: True si le mot de passe correspond, False sinon
        """
        if not password or not hashed_password:
            return False
        
        try:
            verified = bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
            if not verified:
                auth_logger.warning("Tentative de connexion avec mot de passe incorrect")
            return verified
        except Exception as e:
            auth_logger.error(f"Erreur lors de la vérification du mot de passe: {str(e)}")
            return False
    
    @staticmethod
    def is_password_hashed(password: str) -> bool:
        """Vérifie si un mot de passe est déjà hashé (format bcrypt)
        
        Args:
            password: Mot de passe à vérifier
            
        Returns:
            bool: True si c'est un hash bcrypt valide
        """
        if not password:
            return False
        
        try:
            # Les hashes bcrypt commencent par $2a$, $2b$ ou $2y$
            return password.startswith(('$2a$', '$2b$', '$2y$'))
        except Exception:
            return False
