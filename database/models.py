# database/models.py
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
import uuid
from enum import Enum
import hashlib
import os

# Importer db depuis connection.py, PAS depuis models
from database.connection import db

# ============= ENUMS =============

class Priorite(Enum):
    NORME = 'normale'
    MOYENNE = 'moyenne'
    HAUTE = 'haute'
    
    def __str__(self):
        labels = {
            'normale': '🟢 Normale',
            'moyenne': '🟡 Moyenne',
            'haute': '🔴 Haute (Urgent)'
        }
        return labels.get(self.value, self.value)
    
    @property
    def color(self):
        colors = {
            'normale': '#28a745',
            'moyenne': '#ffc107',
            'haute': '#dc3545'
        }
        return colors.get(self.value, '#6c757d')

class Statut(Enum):
    EN_ATTENTE = 'en_attente'
    EN_COURS = 'en_cours'
    TRAITE = 'traite'
    ANNULE = 'annule'
    
    def __str__(self):
        labels = {
            'en_attente': '⏳ En attente',
            'en_cours': '🔄 En cours',
            'traite': '✅ Traité',
            'annule': '❌ Annulé'
        }
        return labels.get(self.value, self.value)
    
    @property
    def color(self):
        colors = {
            'en_attente': '#ffc107',
            'en_cours': '#17a2b8',
            'traite': '#28a745',
            'annule': '#dc3545'
        }
        return colors.get(self.value, '#6c757d')

class Role(Enum):
    """Rôles des utilisateurs"""
    ADMIN = 'admin'
    PRE_ACCUEIL = 'preaccueil'
    ACCUEIL = 'accueil'
    MANAGER = 'manager'
    
    def __str__(self):
        labels = {
            'admin': '👑 Administrateur',
            'preaccueil': '🛂 Pré-accueil',
            'accueil': '🏢 Agent d\'accueil',
            'manager': '📊 Manager'
        }
        return labels.get(self.value, self.value)
    
    @property
    def level(self):
        """Niveau de permission (plus le chiffre est élevé, plus les droits sont importants)"""
        levels = {
            'admin': 100,
            'manager': 80,
            'accueil': 50,
            'preaccueil': 30
        }
        return levels.get(self.value, 0)

# ============= PERMISSIONS =============

class Permission:
    """Gestion des permissions par rôle"""
    
    # Définition des permissions
    VIEW_DASHBOARD = 'view_dashboard'
    VIEW_DEMANDES = 'view_demandes'
    CREATE_DEMANDE = 'create_demande'
    EDIT_DEMANDE = 'edit_demande'
    DELETE_DEMANDE = 'delete_demande'
    PROCESS_DEMANDE = 'process_demande'
    VIEW_STATS = 'view_stats'
    EXPORT_DATA = 'export_data'
    MANAGE_SERVICES = 'manage_services'
    MANAGE_MOTIFS = 'manage_motifs'
    MANAGE_USERS = 'manage_users'
    VIEW_LOGS = 'view_logs'
    VIEW_ALL_DEMANDES = 'view_all_demandes'
    
    # ✅ MATRICE DES PERMISSIONS PAR RÔLE
    ROLE_PERMISSIONS = {
        # 👑 ADMINISTRATEUR : TOUS LES DROITS
        Role.ADMIN: [
            VIEW_DASHBOARD, VIEW_DEMANDES, VIEW_ALL_DEMANDES,
            CREATE_DEMANDE, EDIT_DEMANDE, DELETE_DEMANDE, PROCESS_DEMANDE,
            VIEW_STATS, EXPORT_DATA,
            MANAGE_SERVICES, MANAGE_MOTIFS, MANAGE_USERS, VIEW_LOGS
        ],
        
        # 📊 MANAGER : TOUT SAUF ADMINISTRATION
        Role.MANAGER: [
            VIEW_DASHBOARD, VIEW_DEMANDES, VIEW_ALL_DEMANDES,
            CREATE_DEMANDE, EDIT_DEMANDE, DELETE_DEMANDE, PROCESS_DEMANDE,
            VIEW_STATS, EXPORT_DATA,
            VIEW_LOGS
        ],
        
        # 🏢 AGENT ACCUEIL : CRUD COMPLET SUR LES DEMANDES
        Role.ACCUEIL: [
            VIEW_DASHBOARD, VIEW_DEMANDES, VIEW_ALL_DEMANDES,
            CREATE_DEMANDE, EDIT_DEMANDE, PROCESS_DEMANDE,  # ✅ Peut modifier et traiter
            # ❌ Pas de suppression
            # ❌ Pas de statistiques
            # ❌ Pas d'export
            # ❌ Pas d'administration
        ],
        
        # 🛂 AGENT PRÉ-ACCUEIL : CRÉATION UNIQUEMENT
        Role.PRE_ACCUEIL: [
            VIEW_DEMANDES,              # ✅ Voir les demandes
            CREATE_DEMANDE,            # ✅ Créer des demandes
            # ❌ PAS de modification
            # ❌ PAS de traitement
            # ❌ PAS de suppression
            # ❌ PAS de dashboard
            # ❌ PAS de statistiques
            # ❌ PAS d'export
            # ❌ PAS d'administration
        ]
    }
    
    @classmethod
    def has_permission(cls, user_role: Role, permission: str) -> bool:
        """Vérifie si un rôle a une permission"""
        if user_role in cls.ROLE_PERMISSIONS:
            return permission in cls.ROLE_PERMISSIONS[user_role]
        return False
    
    @classmethod
    def get_permissions(cls, user_role: Role) -> list:
        """Retourne toutes les permissions d'un rôle"""
        return cls.ROLE_PERMISSIONS.get(user_role, [])
    
    @classmethod
    def can_edit(cls, user_role: Role) -> bool:
        """Vérifie si le rôle peut modifier des demandes"""
        return cls.has_permission(user_role, cls.EDIT_DEMANDE)
    
    @classmethod
    def can_process(cls, user_role: Role) -> bool:
        """Vérifie si le rôle peut traiter des demandes"""
        return cls.has_permission(user_role, cls.PROCESS_DEMANDE)
    
    @classmethod
    def can_delete(cls, user_role: Role) -> bool:
        """Vérifie si le rôle peut supprimer des demandes"""
        return cls.has_permission(user_role, cls.DELETE_DEMANDE)
    
    @classmethod
    def can_view_stats(cls, user_role: Role) -> bool:
        """Vérifie si le rôle peut voir les statistiques"""
        return cls.has_permission(user_role, cls.VIEW_STATS)
    
    @classmethod
    def can_view_dashboard(cls, user_role: Role) -> bool:
        """Vérifie si le rôle peut voir le tableau de bord"""
        return cls.has_permission(user_role, cls.VIEW_DASHBOARD)

# ============= MODELE SERVICE =============

@dataclass
class Service:
    id: int = None
    nom: str = ""
    description: str = ""
    actif: bool = True
    couleur: str = "#417690"
    
    @classmethod
    def get_all(cls, actif_only: bool = True) -> List['Service']:
        """Récupère tous les services"""
        try:
            query = "SELECT * FROM accueil_service"
            if actif_only:
                query += " WHERE actif = 1"
            query += " ORDER BY nom"
            
            results = db.execute_query(query)
            return [cls(**r) for r in results]
        except Exception as e:
            print(f"Erreur récupération services: {e}")
            return []
    
    @classmethod
    def get_by_id(cls, service_id: int) -> Optional['Service']:
        """Récupère un service par son ID"""
        try:
            result = db.execute_query(
                "SELECT * FROM accueil_service WHERE id = ?",
                (service_id,)
            )
            return cls(**result[0]) if result else None
        except Exception as e:
            print(f"Erreur récupération service {service_id}: {e}")
            return None

# ============= MODELE MOTIF =============

@dataclass
class Motif:
    id: int = None
    nom: str = ""
    description: str = ""
    actif: bool = True
    priorite_defaut: str = "normale"
    
    @classmethod
    def get_all(cls, actif_only: bool = True) -> List['Motif']:
        """Récupère tous les motifs"""
        try:
            query = "SELECT * FROM accueil_motif"
            if actif_only:
                query += " WHERE actif = 1"
            query += " ORDER BY nom"
            
            results = db.execute_query(query)
            return [cls(**r) for r in results]
        except Exception as e:
            print(f"Erreur récupération motifs: {e}")
            return []
    
    @classmethod
    def get_by_id(cls, motif_id: int) -> Optional['Motif']:
        """Récupère un motif par son ID"""
        try:
            result = db.execute_query(
                "SELECT * FROM accueil_motif WHERE id = ?",
                (motif_id,)
            )
            return cls(**result[0]) if result else None
        except Exception as e:
            print(f"Erreur récupération motif {motif_id}: {e}")
            return None

# ============= MODELE DEMANDE =============

@dataclass
class DemandeAccueil:
    # Champs obligatoires sans valeurs par défaut complexes
    id: str = None
    date: str = None
    nom: str = ""
    prenom: str = ""
    numero_cnps: str = ""
    service_demande_id: int = None
    motif_id: int = None
    priorite: str = "normale"
    statut: str = "en_attente"
    satisfaction: Optional[int] = None
    commentaire_satisfaction: str = ""
    heure_arrivee: Optional[str] = None
    heure_reception: Optional[str] = None
    temps_attente: Optional[str] = None
    delai_objectif: int = 0
    contacts: str = ""
    agent_accueil_id: Optional[int] = None
    observations: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    traite_le: Optional[str] = None
    
    # Champs non inclus dans __init__
    _service: Optional[Service] = field(default=None, repr=False, init=False)
    _motif: Optional[Motif] = field(default=None, repr=False, init=False)
    
    def __post_init__(self):
        """Convertit les chaînes en objets date/heure si nécessaire"""
        # Convertir les dates si elles sont en string
        if isinstance(self.date, str) and self.date:
            try:
                self.date = datetime.strptime(self.date, "%Y-%m-%d").date()
            except ValueError:
                self.date = date.today()
        
        if isinstance(self.heure_arrivee, str) and self.heure_arrivee:
            try:
                self.heure_arrivee = datetime.strptime(self.heure_arrivee, "%H:%M:%S").time()
            except ValueError:
                self.heure_arrivee = datetime.now().time()
                
        if isinstance(self.heure_reception, str) and self.heure_reception:
            try:
                self.heure_reception = datetime.strptime(self.heure_reception, "%H:%M:%S").time()
            except ValueError:
                self.heure_reception = None
                
        if isinstance(self.created_at, str) and self.created_at:
            try:
                self.created_at = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            except ValueError:
                self.created_at = datetime.now()
                
        if isinstance(self.updated_at, str) and self.updated_at:
            try:
                self.updated_at = datetime.fromisoformat(self.updated_at.replace('Z', '+00:00'))
            except ValueError:
                self.updated_at = datetime.now()
                
        if isinstance(self.traite_le, str) and self.traite_le:
            try:
                self.traite_le = datetime.fromisoformat(self.traite_le.replace('Z', '+00:00'))
            except ValueError:
                self.traite_le = None
        
        # Initialiser les valeurs par défaut si None
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.date is None:
            self.date = date.today()
        if self.heure_arrivee is None:
            self.heure_arrivee = datetime.now().time()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    @property
    def service(self) -> Optional[Service]:
        """Récupère le service associé (lazy loading)"""
        if self._service is None and self.service_demande_id:
            self._service = Service.get_by_id(self.service_demande_id)
        return self._service
    
    @property
    def motif(self) -> Optional[Motif]:
        """Récupère le motif associé (lazy loading)"""
        if self._motif is None and self.motif_id:
            self._motif = Motif.get_by_id(self.motif_id)
        return self._motif
    
    @property
    def nom_complet(self) -> str:
        return f"{self.nom} {self.prenom}".strip()
    
    @property
    def est_urgente(self) -> bool:
        return self.priorite == 'haute'
    
    @property
    def est_traitee(self) -> bool:
        return self.statut == 'traite'
    
    @property
    def temps_attente_minutes(self) -> Optional[int]:
        """Temps d'attente en minutes"""
        if self.temps_attente:
            if isinstance(self.temps_attente, str):
                parts = self.temps_attente.split(':')
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    return h * 60 + m + s // 60
        return None
    
    @property
    def delai_objectif_bool(self) -> bool:
        """Convertit delai_objectif en booléen"""
        return bool(self.delai_objectif)
    
    @property
    def satisfaction_etoiles(self) -> str:
        if self.satisfaction:
            return '⭐' * self.satisfaction
        return "Non évalué"
    
    def save(self) -> bool:
        """Sauvegarde la demande en base"""
        try:
            # Préparer les dates pour la sauvegarde
            date_str = self.date.isoformat() if hasattr(self.date, 'isoformat') else str(self.date)
            heure_arrivee_str = self.heure_arrivee.isoformat() if hasattr(self.heure_arrivee, 'isoformat') else self.heure_arrivee
            heure_reception_str = self.heure_reception.isoformat() if hasattr(self.heure_reception, 'isoformat') else self.heure_reception
            created_at_str = self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at
            updated_at_str = datetime.now().isoformat()
            traite_le_str = self.traite_le.isoformat() if self.traite_le and hasattr(self.traite_le, 'isoformat') else self.traite_le
            
            data = {
                'id': self.id,
                'date': date_str,
                'nom': self.nom,
                'prenom': self.prenom,
                'numero_cnps': self.numero_cnps or "",
                'service_demande_id': self.service_demande_id,
                'motif_id': self.motif_id,
                'priorite': self.priorite,
                'statut': self.statut,
                'satisfaction': self.satisfaction,
                'commentaire_satisfaction': self.commentaire_satisfaction or "",
                'heure_arrivee': heure_arrivee_str,
                'heure_reception': heure_reception_str,
                'temps_attente': self.temps_attente,
                'delai_objectif': 1 if self.delai_objectif else 0,
                'contacts': self.contacts or "",
                'agent_accueil_id': self.agent_accueil_id,
                'observations': self.observations or "",
                'traite_le': traite_le_str,
                'updated_at': updated_at_str
            }
            
            # Vérifier si la demande existe
            existing = db.execute_query(
                "SELECT id FROM accueil_demandeaccueil WHERE id = ?",
                (self.id,)
            )
            
            if existing:
                # Mise à jour
                set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
                query = f"UPDATE accueil_demandeaccueil SET {set_clause} WHERE id = ?"
                params = list(data.values()) + [self.id]
                return db.execute_update(query, tuple(params)) > 0
            else:
                # Insertion
                data['created_at'] = created_at_str
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?'] * len(data))
                query = f"INSERT INTO accueil_demandeaccueil ({columns}) VALUES ({placeholders})"
                return db.execute_insert(query, tuple(data.values())) > 0
                
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    @classmethod
    def get_all(cls, filters: Dict[str, Any] = None, limit: int = 100) -> List['DemandeAccueil']:
        """Récupère toutes les demandes avec filtres"""
        try:
            query = "SELECT * FROM accueil_demandeaccueil WHERE 1=1"
            params = []
            
            if filters:
                if filters.get('date_debut'):
                    query += " AND date >= ?"
                    params.append(filters['date_debut'].isoformat())
                if filters.get('date_fin'):
                    query += " AND date <= ?"
                    params.append(filters['date_fin'].isoformat())
                if filters.get('statut'):
                    query += " AND statut = ?"
                    params.append(filters['statut'])
                if filters.get('service_id'):
                    query += " AND service_demande_id = ?"
                    params.append(filters['service_id'])
                if filters.get('priorite'):
                    query += " AND priorite = ?"
                    params.append(filters['priorite'])
            
            query += " ORDER BY date DESC, created_at DESC LIMIT ?"
            params.append(limit)
            
            results = db.execute_query(query, tuple(params))
            return [cls(**r) for r in results]
            
        except Exception as e:
            print(f"Erreur lors de la récupération des demandes: {e}")
            return []
    
    @classmethod
    def get_by_id(cls, demande_id: str) -> Optional['DemandeAccueil']:
        """Récupère une demande par son ID"""
        try:
            result = db.execute_query(
                "SELECT * FROM accueil_demandeaccueil WHERE id = ?",
                (demande_id,)
            )
            return cls(**result[0]) if result else None
        except Exception as e:
            print(f"Erreur lors de la récupération de la demande: {e}")
            return None
    
    def marquer_traite(self):
        """Marque la demande comme traitée"""
        self.statut = 'traite'
        self.traite_le = datetime.now()
        if not self.heure_reception:
            self.heure_reception = datetime.now().time()
        self.calculer_temps_attente()
        return self.save()
    
    def calculer_temps_attente(self):
        """Calcule le temps d'attente"""
        if self.heure_arrivee and self.heure_reception:
            try:
                if hasattr(self.heure_arrivee, 'hour'):
                    arrivee = timedelta(
                        hours=self.heure_arrivee.hour,
                        minutes=self.heure_arrivee.minute,
                        seconds=self.heure_arrivee.second
                    )
                else:
                    arrivee = timedelta(0)
                    
                if hasattr(self.heure_reception, 'hour'):
                    reception = timedelta(
                        hours=self.heure_reception.hour,
                        minutes=self.heure_reception.minute,
                        seconds=self.heure_reception.second
                    )
                else:
                    reception = timedelta(0)
                
                if reception >= arrivee:
                    delta = reception - arrivee
                    self.temps_attente = str(delta)
                    self.delai_objectif = 1 if delta.total_seconds() > 900 else 0
            except Exception as e:
                print(f"Erreur lors du calcul du temps d'attente: {e}")

# ============= MODELE UTILISATEUR =============

class Utilisateur:
    """Modèle utilisateur avec authentification sécurisée"""
    
    def __init__(self, id=None, username=None, password_hash=None, email=None,
                 role='preaccueil', is_active=True, last_login=None,
                 date_joined=None, nom=None, prenom=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.role = role
        self.is_active = is_active
        self.last_login = last_login
        self.date_joined = date_joined or datetime.now()
        self.nom = nom or ""
        self.prenom = prenom or ""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash sécurisé du mot de passe (PBKDF2)"""
        salt = os.urandom(32).hex()
        iterations = 100000
        hash_obj = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return f"{salt}${iterations}${hash_obj.hex()}"
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Vérifie le mot de passe"""
        try:
            salt, iterations, hash_hex = password_hash.split('$')
            iterations = int(iterations)
            hash_obj = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations
            )
            return hash_obj.hex() == hash_hex
        except Exception as e:
            print(f"Erreur vérification mot de passe: {e}")
            return False
    
    def save(self) -> bool:
        """Sauvegarde l'utilisateur en base"""
        try:
            if self.id:
                # Mise à jour
                query = """
                    UPDATE auth_user 
                    SET username = ?, email = ?, role = ?, is_active = ?,
                        last_login = ?, nom = ?, prenom = ?
                    WHERE id = ?
                """
                params = (self.username, self.email, self.role, 1 if self.is_active else 0,
                         self.last_login.isoformat() if self.last_login else None,
                         self.nom, self.prenom, self.id)
                db.execute_update(query, params)
            else:
                # Création
                query = """
                    INSERT INTO auth_user 
                    (id, username, password, email, role, is_active, date_joined, nom, prenom)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self.id = self.id or str(uuid.uuid4())
                params = (self.id, self.username, self.password_hash, self.email,
                         self.role, 1, self.date_joined.isoformat(),
                         self.nom, self.prenom)
                db.execute_insert(query, params)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde utilisateur: {e}")
            return False
    
    @classmethod
    def authenticate(cls, username: str, password: str) -> Optional['Utilisateur']:
        """Authentifie un utilisateur"""
        try:
            result = db.execute_query(
                "SELECT * FROM auth_user WHERE username = ? AND is_active = 1",
                (username,)
            )
            
            if result and cls.verify_password(password, result[0]['password']):
                user = cls(
                    id=result[0]['id'],
                    username=result[0]['username'],
                    password_hash=result[0]['password'],
                    email=result[0]['email'],
                    role=result[0]['role'],
                    is_active=bool(result[0]['is_active']),
                    nom=result[0].get('nom', ''),
                    prenom=result[0].get('prenom', ''),
                    date_joined=result[0].get('date_joined')
                )
                
                # Mettre à jour last_login
                user.last_login = datetime.now()
                user.save()
                
                return user
        except Exception as e:
            print(f"Erreur authentification: {e}")
        
        return None
    
    @classmethod
    def get_by_id(cls, user_id: str) -> Optional['Utilisateur']:
        """Récupère un utilisateur par son ID"""
        try:
            result = db.execute_query(
                "SELECT * FROM auth_user WHERE id = ?",
                (user_id,)
            )
            if result:
                return cls(**result[0])
        except Exception as e:
            print(f"Erreur récupération utilisateur: {e}")
        return None
    
    def has_permission(self, permission: str) -> bool:
        """Vérifie si l'utilisateur a une permission"""
        try:
            role = Role(self.role)
            return Permission.has_permission(role, permission)
        except:
            return False
    
    def has_role(self, role_name: str) -> bool:
        """Vérifie si l'utilisateur a un rôle spécifique"""
        return self.role == role_name
    
    @property
    def role_display(self):
        """Affichage du rôle"""
        try:
            return str(Role(self.role))
        except:
            return self.role
    
    @property
    def full_name(self):
        """Nom complet"""
        return f"{self.prenom} {self.nom}".strip() or self.username

# ============= STATISTIQUES =============

class StatistiquesQuotidiennes:
    """Modèle pour les statistiques quotidiennes"""
    
    def __init__(self, date=None):
        self.date = date or date.today()
        self.total_demandes = 0
        self.demandes_traitees = 0
        self.demandes_urgentes = 0
        self.temps_attente_moyen = None
        self.satisfaction_moyenne = None
    
    @classmethod
    def get_for_date(cls, date_obj):
        """Récupère les stats pour une date donnée"""
        stats = cls(date_obj)
        
        try:
            # Calculer les stats à partir des demandes
            demandes = DemandeAccueil.get_all({
                'date_debut': date_obj,
                'date_fin': date_obj
            })
            
            stats.total_demandes = len(demandes)
            stats.demandes_traitees = len([d for d in demandes if d.statut == 'traite'])
            stats.demandes_urgentes = len([d for d in demandes if d.priorite == 'haute'])
            
            # Temps d'attente moyen
            temps_attente = [d.temps_attente_minutes for d in demandes if d.temps_attente_minutes]
            if temps_attente:
                stats.temps_attente_moyen = sum(temps_attente) / len(temps_attente)
            
            # Satisfaction moyenne
            notes = [d.satisfaction for d in demandes if d.satisfaction]
            if notes:
                stats.satisfaction_moyenne = sum(notes) / len(notes)
                
        except Exception as e:
            print(f"Erreur calcul statistiques: {e}")
        
        return stats
    
    @property
    def taux_traitement(self):
        if self.total_demandes > 0:
            return round((self.demandes_traitees / self.total_demandes) * 100, 1)
        return 0

# ============= INITIALISATION BASE DE DONNEES =============

def init_auth_database():
    """Initialise les tables d'authentification"""
    
    create_table_query = """
    CREATE TABLE IF NOT EXISTS auth_user (
        id VARCHAR(36) PRIMARY KEY,
        username VARCHAR(150) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        email VARCHAR(254),
        role VARCHAR(20) NOT NULL DEFAULT 'preaccueil',
        is_active BOOLEAN NOT NULL DEFAULT 1,
        last_login DATETIME,
        date_joined DATETIME NOT NULL,
        nom VARCHAR(100),
        prenom VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_auth_user_username ON auth_user(username);
    CREATE INDEX IF NOT EXISTS idx_auth_user_role ON auth_user(role);
    CREATE INDEX IF NOT EXISTS idx_auth_user_active ON auth_user(is_active);
    """
    
    try:
        with db.get_connection() as conn:
            conn.executescript(create_table_query)
        print("✅ Table auth_user créée/vérifiée avec succès")
        
        # Créer l'admin par défaut si aucun utilisateur n'existe
        users = db.execute_query("SELECT COUNT(*) as count FROM auth_user")
        if users and users[0]['count'] == 0:
            admin = Utilisateur(
                username="admin",
                email="admin@cnps.ci",
                role="admin",
                nom="Administrateur",
                prenom="Système"
            )
            admin.password_hash = Utilisateur.hash_password("Admin@2024")
            admin.save()
            print("✅ Administrateur par défaut créé: admin / Admin@2024")
            
    except Exception as e:
        print(f"Erreur création table auth_user: {e}")