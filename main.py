# main.py
"""Point d'entrée pour l'application CNPS Accueil"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QDialog, QMessageBox, QApplication
from PyQt6.QtCore import QTimer, Qt, QFile, QTextStream, QIODevice, QSettings
import sys
import base64
import socket
from pathlib import Path
import sqlite3
import hashlib
import warnings
import os
from datetime import datetime, timedelta

# Bcrypt disponible via utils/password_manager
try:
    from utils.password_manager import PasswordManager as _PM
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

warnings.filterwarnings(
    "ignore",
    message=r"sipPyTypeDict\(\) is deprecated.*",
    category=DeprecationWarning,
)

# Configuration des imports
sys.path.insert(0, str(Path(__file__).parent))

# Importer la configuration
from config import AppConfig
import res  # Resource file

# ===== IMPORTER LA FENÊTRE PRINCIPALE =====
try:
    from sidebar.main_windows import MainWindow
    print("✅ Fenêtre sidebar/main_windows.py importée avec succès")
    print(f"📦 Type de MainWindow: {type(MainWindow)}")
except Exception as e:
    print(f"❌ Erreur d'importation: {e}")
    print(f"📁 Traceback complet:")
    import traceback
    traceback.print_exc()
    MainWindow = None

# ===== PARTIE 1: INTERFACE DE CONNEXION =====
class Ui_Form(object):
    """Interface de connexion générée par Qt Designer
    
    Cette classe définit l'UI pour l'écran de connexion avec:
    - Champs de saisie pour identifiant et mot de passe
    - Bouton de connexion
    - Logo et branding CNPS
    """
    
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(580, 520)
        Form.setStyleSheet(
            "QDialog { border: none; outline: none; }"
            "QLineEdit { outline: none; }"
            "QLineEdit:focus { outline: none; }"
        )
        self.widget = QtWidgets.QWidget(parent=Form)
        self.widget.setGeometry(QtCore.QRect(8, 8, 564, 504))
        self.widget.setStyleSheet("QPushButton#pushButton{\n"
"    background-color: qlineargradient(spread:pad, x1:0, y1:0.505682, x2:1, y2:0.477, stop:0 rgba(11, 131, 120, 219), stop:1 rgba(85, 98, 112, 226));\n"
"    color:rgba(255, 255, 255, 210);\n"
"    border-radius:5px;\n"
"}\n"
"\n"
"QPushButton#pushButton:hover{\n"
"    background-color: qlineargradient(spread:pad, x1:0, y1:0.505682, x2:1, y2:0.477, stop:0 rgba(150, 123, 111, 219), stop:1 rgba(85, 81, 84, 226));\n"
"}\n"
"\n"
"QPushButton#pushButton:pressed{\n"
"    padding-left:5px;\n"
"    padding-top:5px;\n"
"    background-color:rgba(150, 123, 111, 255);\n"
"}\n"
"\n"
"QPushButton#pushButton_2, #pushButton_3, #pushButton_4, #pushButton_5{\n"
"    background-color: rgba(0, 0, 0, 0);\n"
"    color:rgba(85, 98, 112, 255);\n"
"}\n"
"\n"
"QPushButton#pushButton_2:hover, #pushButton_3:hover, #pushButton_4:hover, #pushButton_5:hover{\n"
"    color: rgba(131, 96, 53, 255);\n"
"}\n"
"\n"
"QPushButton#pushButton_2:pressed, #pushButton_3:pressed, #pushButton_4:pressed, #pushButton_5:pressed{\n"
"    padding-left:5px;\n"
"    padding-top:5px;\n"
"    color:rgba(91, 88, 53, 255);\n"
"}\n"
"\n"
"")
        self.widget.setObjectName("widget")
        self.label = QtWidgets.QLabel(parent=self.widget)
        self.label.setGeometry(QtCore.QRect(30, 30, 281, 430))
        self.label.setStyleSheet("background-image: url(:/images/dscn1055.jpg);\n"
"background-position: right;\n"
"background-repeat: no-repeat;\n"
"border-top-left-radius: 50px;")
        self.label.setText("")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(parent=self.widget)
        self.label_2.setGeometry(QtCore.QRect(30, 30, 241, 431))
        self.label_2.setStyleSheet("background-color:rgba(0, 0, 0, 80);\n"
"border-top-left-radius: 50px;")
        self.label_2.setText("")
        self.label_2.setObjectName("label_2")
        self.label_3 = QtWidgets.QLabel(parent=self.widget)
        self.label_3.setGeometry(QtCore.QRect(270, 30, 240, 430))
        self.label_3.setStyleSheet("background-color:rgba(255, 255, 255, 255);\n"
"border-bottom-right-radius: 50px;")
        self.label_3.setText("")
        self.label_3.setObjectName("label_3")
        self.label_4 = QtWidgets.QLabel(parent=self.widget)
        self.label_4.setGeometry(QtCore.QRect(320, 80, 131, 40))
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.label_4.setFont(font)
        self.label_4.setStyleSheet("color: rgb(0, 85, 164);")
        self.label_4.setObjectName("label_4")
        self.lineEdit = QtWidgets.QLineEdit(parent=self.widget)
        self.lineEdit.setGeometry(QtCore.QRect(295, 150, 190, 40))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit.setFont(font)
        self.lineEdit.setStyleSheet("background-color:rgba(0, 0, 0, 0);\n"
"border:none;\n"
"outline:none;\n"
"border-bottom:2px solid rgba(46, 82, 101, 200);\n"
"color:rgba(0, 0, 0, 240);\n"
"padding-bottom:7px;")
        self.lineEdit.setObjectName("lineEdit")
        self.lineEdit_2 = QtWidgets.QLineEdit(parent=self.widget)
        self.lineEdit_2.setGeometry(QtCore.QRect(295, 215, 190, 40))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.lineEdit_2.setFont(font)
        self.lineEdit_2.setStyleSheet("background-color:rgba(0, 0, 0, 0);\n"
"border:none;\n"
"outline:none;\n"
"border-bottom:2px solid rgba(46, 82, 101, 200);\n"
"color:rgba(0, 0, 0, 240);\n"
"padding-bottom:7px;")
        self.lineEdit_2.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.pushButton = QtWidgets.QPushButton(parent=self.widget)
        self.pushButton.setGeometry(QtCore.QRect(295, 295, 190, 40))
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.pushButton.setFont(font)
        self.pushButton.setObjectName("pushButton")
        self.label_7 = QtWidgets.QLabel(parent=self.widget)
        self.label_7.setGeometry(QtCore.QRect(50, 80, 180, 40))
        font = QtGui.QFont()
        font.setPointSize(22)
        font.setBold(True)
        self.label_7.setFont(font)
        self.label_7.setStyleSheet("color: rgb(243, 146, 0);\n"
"font-weight: bold;")
        self.label_7.setObjectName("label_7")
        self.label_8 = QtWidgets.QLabel(parent=self.widget)
        self.label_8.setEnabled(True)
        self.label_8.setGeometry(QtCore.QRect(50, 140, 201, 51))
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.label_8.setFont(font)
        self.label_8.setMouseTracking(True)
        self.label_8.setTabletTracking(False)
        self.label_8.setStyleSheet("color:rgba(255, 255, 255, 170);")
        self.label_8.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.label_8.setScaledContents(False)
        self.label_8.setWordWrap(True)
        self.label_8.setObjectName("label_8")

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.label_4.setText(_translate("Form", "Se connecter"))
        self.lineEdit.setPlaceholderText(_translate("Form", "Identifiant"))
        self.lineEdit_2.setPlaceholderText(_translate("Form", "Mot de passe"))
        self.pushButton.setText(_translate("Form", "Connexion"))
        self.label_7.setText(_translate("Form", "Accueil +"))
        self.label_8.setText(_translate("Form", "Bienvenue dans l’application de gestion de l’accueil de la Caisse Nationale de Prévoyance Sociale.\n"
""))

# ===== PARTIE 1b: CHIFFREMENT LOCAL "SE SOUVENIR DE MOI" =====
# Chiffrement XOR + base64 avec clé dérivée du nom de machine.
# Obfuscation locale uniquement — ne jamais transmettre ces données sur le réseau.

def _machine_key() -> bytes:
    """Clé 32 octets dérivée du nom d'hôte (spécifique à la machine)."""
    machine_id = (socket.gethostname() + "CNPS_ACCUEIL_v1").encode()
    return hashlib.sha256(machine_id).digest()


def _encrypt_credential(value: str) -> str:
    """Chiffre `value` avec XOR machine-key + base64."""
    key   = _machine_key()
    enc   = bytes(b ^ key[i % len(key)] for i, b in enumerate(value.encode("utf-8")))
    return base64.b64encode(enc).decode("ascii")


def _decrypt_credential(token: str) -> str:
    """Déchiffre un token produit par `_encrypt_credential`."""
    key   = _machine_key()
    enc   = base64.b64decode(token.encode("ascii"))
    dec   = bytes(b ^ key[i % len(key)] for i, b in enumerate(enc))
    return dec.decode("utf-8")


# ===== PARTIE 2: FONCTIONS DE HASHAGE =====

_HEX_CHARS = frozenset("0123456789abcdef")


def _sha256_hex(mot_de_passe: str) -> str:
    """Hash SHA256 brut (usage interne migration uniquement)."""
    return hashlib.sha256(mot_de_passe.encode("utf-8")).hexdigest()


def _is_sha256_hash(h: str) -> bool:
    """Détecte si un hash est au format SHA256 legacy (64 caractères hex)."""
    return len(h) == 64 and all(c in _HEX_CHARS for c in h.lower())


def hash_password(mot_de_passe: str) -> str:
    """Hash un mot de passe. Utilise bcrypt si disponible, sinon SHA256.

    Returns:
        str: Le hash du mot de passe (bcrypt ou SHA256 hex)
    """
    if _BCRYPT_AVAILABLE:
        return _PM.hash_password(mot_de_passe)
    return _sha256_hex(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe_entre: str, hash_stocke: str) -> bool:
    """Vérifie un mot de passe contre son hash stocké.

    Supporte la migration transparente SHA256 → bcrypt :
    - Si le hash stocké est un SHA256 legacy (64 hex), vérifie avec SHA256.
    - Si le hash stocké est bcrypt (commence par $2b$), vérifie avec bcrypt.
    - Si bcrypt n'est pas disponible, repli sur SHA256.

    Returns:
        bool: True si le mot de passe correspond
    """
    if not hash_stocke:
        return False

    # Hash bcrypt
    if hash_stocke.startswith("$2b$") or hash_stocke.startswith("$2a$"):
        if _BCRYPT_AVAILABLE:
            return _PM.verify_password(mot_de_passe_entre, hash_stocke)
        return False

    # Hash SHA256 legacy
    if _is_sha256_hash(hash_stocke):
        return _sha256_hex(mot_de_passe_entre) == hash_stocke.lower()

    # Fallback
    return _sha256_hex(mot_de_passe_entre) == hash_stocke


# Alias de compatibilité
hash_sha256 = _sha256_hex


def log_runtime_db_path(db_path: Path):
    """Journalise le chemin DB réellement utilisé au démarrage."""
    try:
        if getattr(sys, "frozen", False):
            runtime_dir = Path(sys.executable).resolve().parent
        else:
            runtime_dir = Path(__file__).resolve().parent

        logs_dir = runtime_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "runtime_db_path.log"

        now = datetime.now().isoformat(timespec="seconds")
        line = f"{now} | pid={os.getpid()} | db_path={db_path}\n"
        with log_file.open("a", encoding="utf-8") as fp:
            fp.write(line)
    except Exception:
        pass

# ===== PARTIE 3: LOGIQUE DE CONNEXION =====
class LoginApp(QDialog):
    """Fenêtre de connexion à l'application CNPS Accueil
    
    Gère:
    - Affichage de l'interface de connexion
    - Vérification des identifiants en base de données
    - SHA256 des mots de passe
    - Limitation du nombre de tentatives (5 max)
    - Création des utilisateurs par défaut
    - Transition vers la fenêtre principale
    
    Attributs:
        utilisateur: Dict contenant les infos de l'utilisateur connecté
        tentatives: Nombre de tentatives de connexion échouées
        max_tentatives: Nombre max de tentatives (AppConfig.MAX_LOGIN_ATTEMPTS)
        db_path: Chemin vers la base de données SQLite
        main_window: Référence à la fenêtre principale
    """
    
    def __init__(self):
        super().__init__()
        self.utilisateur = None
        self.tentatives = 0
        self.max_tentatives = AppConfig.MAX_LOGIN_ATTEMPTS
        self.main_window = None
        self.settings = QSettings("CNPS", "AccueilApp")
        
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.setWindowTitle("Connexion - CNPS Accueil")

        # Fenêtre sans cadre + fond transparent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Bouton fermeture ✕ en haut à droite
        self._btn_close = QtWidgets.QPushButton("✕", self.ui.widget)
        self._btn_close.setGeometry(QtCore.QRect(538, 8, 26, 26))
        self._btn_close.setStyleSheet(
            "QPushButton { background: rgba(220,38,38,200); color: white;"
            " border-radius: 13px; font-size: 12px; font-weight: 700; border: none; }"
            "QPushButton:hover { background: rgba(239,68,68,255); }"
            "QPushButton:pressed { background: rgba(185,28,28,255); }"
        )
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(lambda: sys.exit(0))

        self.ui.pushButton.clicked.connect(self.se_connecter)
        self.ui.lineEdit.returnPressed.connect(self.se_connecter)
        self.ui.lineEdit_2.returnPressed.connect(self.se_connecter)
        
        # Labels de message
        self.message_label = QtWidgets.QLabel(self.ui.widget)
        self.message_label.setGeometry(QtCore.QRect(285, 255, 210, 60))
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)
        
        self.tentative_label = QtWidgets.QLabel(self.ui.widget)
        self.tentative_label.setGeometry(QtCore.QRect(295, 340, 190, 30))
        self.tentative_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tentative_label.setVisible(False)
        
        self.db_path = AppConfig.get_db_path()

        # ── Case "Se souvenir de moi" ─────────────────────────────────────────
        self._chk_remember = QtWidgets.QCheckBox("Se souvenir de moi", self.ui.widget)
        self._chk_remember.setGeometry(QtCore.QRect(295, 262, 190, 24))
        self._chk_remember.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chk_remember.setStyleSheet(
            "QCheckBox { color: #94a3b8; font-size: 11px; background: transparent; }"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px;"
            "  border: 1px solid #475569; background: #1e293b; }"
            "QCheckBox::indicator:checked { background: #3b82f6; border-color: #3b82f6; }"
            "QCheckBox::indicator:hover { border-color: #3b82f6; }"
        )

        self.creer_table()
        self.creer_utilisateurs_defaut()
        self.charger_dernieres_identifiants()
        self.ui.lineEdit.setFocus()

    def _open_db_connection(self) -> sqlite3.Connection:
        """Ouvre une connexion SQLite avec pragmas adaptés au multi-accès."""
        conn = sqlite3.connect(str(self.db_path), timeout=AppConfig.DB_TIMEOUT)
        pragmas = AppConfig.get_sqlite_pragmas(self.db_path)
        conn.execute(f"PRAGMA journal_mode = {pragmas['journal_mode']}")
        conn.execute(f"PRAGMA busy_timeout = {pragmas['busy_timeout_ms']}")
        conn.execute(f"PRAGMA foreign_keys = {pragmas['foreign_keys']}")
        conn.execute(f"PRAGMA synchronous = {pragmas['synchronous']}")
        return conn

    def charger_dernieres_identifiants(self):
        """Charge username + mot de passe chiffré si l'option était cochée."""
        # Purge l'ancien mot de passe en clair s'il était stocké (sécurité legacy)
        if self.settings.contains("auth/last_password"):
            self.settings.remove("auth/last_password")
            self.settings.sync()

        last_username  = self.settings.value("auth/last_username",  "", type=str)
        remember_me    = self.settings.value("auth/remember_me",    False, type=bool)
        encrypted_pass = self.settings.value("auth/remember_token", "", type=str)

        if last_username:
            self.ui.lineEdit.setText(last_username)

        if remember_me and encrypted_pass:
            try:
                mot_de_passe = _decrypt_credential(encrypted_pass)
                self.ui.lineEdit_2.setText(mot_de_passe)
                self._chk_remember.setChecked(True)
                print("✅ Identifiants mémorisés chargés")
            except Exception:
                # Token corrompu ou changement de machine → on efface proprement
                self._effacer_credentials_memorises()

    def sauvegarder_identifiants(self, username: str, mot_de_passe: str, remember: bool):
        """Sauvegarde username et, si `remember`, le mot de passe chiffré."""
        self.settings.setValue("auth/last_username", username)
        self.settings.setValue("auth/remember_me",   remember)
        if remember:
            self.settings.setValue("auth/remember_token", _encrypt_credential(mot_de_passe))
        else:
            self._effacer_credentials_memorises(keep_username=True)
        self.settings.sync()

    def _effacer_credentials_memorises(self, keep_username: bool = False):
        """Efface les credentials mémorisés (conserve le username si demandé)."""
        if not keep_username:
            self.settings.remove("auth/last_username")
        self.settings.remove("auth/remember_me")
        self.settings.remove("auth/remember_token")
        self.settings.sync()
    
    def creer_table(self):
        try:
            conn = self._open_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(150) NOT NULL UNIQUE,
                    password VARCHAR(128) NOT NULL,
                    email VARCHAR(254) NOT NULL DEFAULT '',
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_superuser BOOLEAN NOT NULL DEFAULT 0,
                    is_staff BOOLEAN NOT NULL DEFAULT 0,
                    date_joined DATETIME NOT NULL,
                    last_login DATETIME,
                    role VARCHAR(20) DEFAULT 'preaccueil'
                )
            """)
            conn.commit()
            conn.close()
            print("✅ Table auth_user créée/vérifiée")
        except Exception as e:
            print(f"❌ Erreur création table: {e}")
    
    def creer_utilisateurs_defaut(self):
        """Crée les utilisateurs par défaut s'ils n'existent pas"""
        try:
            conn = self._open_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM auth_user")
            count = cursor.fetchone()[0]
            
            if count == 0:
                for user in AppConfig.DEFAULT_USERS:
                    password_hash = hash_password(user['initial_password'])
                    cursor.execute("""
                        INSERT INTO auth_user 
                        (username, password, email, is_active, is_superuser, is_staff, date_joined, role)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user['username'],
                        password_hash,
                        user['email'],
                        1,  # is_active
                        1 if user['role'] == 'admin' else 0,  # is_superuser
                        1 if user['role'] in ['admin', 'manager'] else 0,  # is_staff
                        datetime.now().isoformat(),
                        user['role']
                    ))
                conn.commit()
                print("✅ Utilisateurs par défaut créés")
            conn.close()
        except Exception as e:
            print(f"❌ Erreur création utilisateurs: {e}")
    
    def se_connecter(self):
        """Déclenche la vérification de connexion"""
        if self.tentatives >= self.max_tentatives:
            self.afficher_message("⛔ Compte verrouillé (5 min)", "#dc3545")
            self.ui.pushButton.setEnabled(False)
            QTimer.singleShot(AppConfig.LOCKOUT_DURATION, self.deverrouiller)
            return
        
        identifiant = self.ui.lineEdit.text().strip()
        mot_de_passe = self.ui.lineEdit_2.text()
        
        if not identifiant or not mot_de_passe:
            self.afficher_message("❌ Identifiants requis", "#dc3545")
            return
        
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton.setText("Vérification...")
        QTimer.singleShot(100, lambda: self.verifier_db(identifiant, mot_de_passe))
    
    def verifier_db(self, identifiant: str, mot_de_passe: str):
        """Vérifie les identifiants en base de données
        
        Args:
            identifiant: Le nom d'utilisateur
            mot_de_passe: Le mot de passe
        """
        try:
            conn = self._open_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, password, email, role, is_superuser 
                FROM auth_user 
                WHERE username = ? AND is_active = 1
            """, (identifiant,))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                if verifier_mot_de_passe(mot_de_passe, user[2]):
                    self.utilisateur = {
                        'id': user[0],
                        'username': user[1],
                        'email': user[3],
                        'role': user[4] or ('admin' if user[5] else 'accueil'),
                    }
                    self.utilisateur['role_display'] = self.get_role_display(self.utilisateur['role'])
                    
                    print(f"✅ Connexion réussie: {identifiant} ({self.utilisateur['role']})")
                    self.tentatives = 0
                    self.afficher_message("✅ Connexion réussie!", "#28a745")
                    self.sauvegarder_identifiants(
                        identifiant, mot_de_passe,
                        self._chk_remember.isChecked(),
                    )
                    self.mettre_a_jour_last_login(user[0])
                    # Migration SHA256 → bcrypt si bcrypt disponible
                    if _BCRYPT_AVAILABLE and _is_sha256_hash(user[2]):
                        self._migrer_hash_bcrypt(user[0], mot_de_passe)
                    
                    # Ouvrir la fenêtre principale
                    print("🔍 Tentative d'ouverture de la fenêtre principale...")
                    self.ouvrir_fenetre_principale()
                else:
                    self.tentatives += 1
                    reste = self.max_tentatives - self.tentatives
                    self.afficher_message(f"❌ Mot de passe incorrect", "#dc3545")
                    if reste > 0:
                        self.tentative_label.setText(f"⚠️ Tentatives restantes: {reste}")
                        self.tentative_label.setVisible(True)
                    self.ui.lineEdit_2.clear()
                    self.ui.lineEdit_2.setFocus()
            else:
                self.tentatives += 1
                reste = self.max_tentatives - self.tentatives
                self.afficher_message(f"❌ Utilisateur inconnu", "#dc3545")
                if reste > 0:
                    self.tentative_label.setText(f"⚠️ Tentatives restantes: {reste}")
                    self.tentative_label.setVisible(True)
                self.ui.lineEdit_2.clear()
                self.ui.lineEdit_2.setFocus()
                
        except Exception as e:
            msg = str(e).lower()
            if "unable to open database" in msg or "no such file" in msg:
                self.afficher_message(
                    "🌐 Réseau indisponible – base de données introuvable, vérifier le réseau.\n"
                    "Contacter l'administrateur : N'Guessan Kouakou N'Goran Blanchard — 07 77 14 51 87",
                    "#b45309",
                )
            else:
                self.afficher_message(f"❌ Erreur: {str(e)}", "#dc3545")
            print(f"❌ Erreur base de données: {e}")
        finally:
            self.ui.pushButton.setEnabled(True)
            self.ui.pushButton.setText("Connexion")
    
    def _migrer_hash_bcrypt(self, user_id, mot_de_passe: str):
        """Remplace silencieusement un hash SHA256 legacy par un hash bcrypt."""
        try:
            nouveau_hash = _PM.hash_password(mot_de_passe)
            conn = self._open_db_connection()
            conn.execute(
                "UPDATE auth_user SET password = ? WHERE id = ?",
                (nouveau_hash, user_id),
            )
            conn.commit()
            conn.close()
            print(f"✅ Hash migré SHA256→bcrypt pour user id={user_id}")
        except Exception as exc:
            print(f"⚠️ Migration hash bcrypt échouée: {exc}")

    def mettre_a_jour_last_login(self, user_id: int):
        """Met à jour la date de dernière connexion
        
        Args:
            user_id: ID de l'utilisateur
        """
        try:
            conn = self._open_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE auth_user SET last_login = ? WHERE id = ?", 
                         (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    def ouvrir_fenetre_principale(self):
        """Ouvre la fenêtre principale après connexion réussie"""
        print("🔍 ÉTAPE 1: Début de ouvrir_fenetre_principale")
        
        if MainWindow is None:
            print("❌ MainWindow est None - import échoué")
            QMessageBox.critical(self, "Erreur", "Impossible de charger la fenêtre principale")
            return
        
        print("🔍 ÉTAPE 2: MainWindow OK")
        
        try:
            # Créer la fenêtre
            self.main_window = MainWindow()
            print("🔍 ÉTAPE 3: Fenêtre créée avec succès")
            
            # ⚠️ IMPORTANT: Stocker la référence dans QApplication pour éviter garbage collection
            QApplication.instance().main_window = self.main_window
            print("🔍 ÉTAPE 3bis: Fenêtre stockée dans QApplication")
            
            # Transmettre l'utilisateur
            if hasattr(self.main_window, 'set_current_user'):
                print("🔍 ÉTAPE 4: Appel de set_current_user")
                self.main_window.set_current_user(self.utilisateur)
            else:
                print("⚠️ set_current_user non trouvé")
            
            # Afficher la fenêtre
            print("🔍 ÉTAPE 5: Appel de show()")
            self.main_window.show()
            
            # Forcer l'affichage
            self.main_window.raise_()
            self.main_window.activateWindow()
            
            print("🔍 ÉTAPE 6: show() exécuté")
            
            # Petit délai pour s'assurer que la fenêtre est affichée
            QTimer.singleShot(100, self.fermer_login)
            print("🔍 ÉTAPE 7: Fermeture de la fenêtre de connexion prévue")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'ouverture: {e}")
            import traceback
            traceback.print_exc()
    
    def fermer_login(self):
        """Ferme la fenêtre de connexion après un délai"""
        print("🔍 Fermeture de la fenêtre de connexion")
        self.accept()
    
    def get_role_display(self, role: str) -> str:
        """Retourne le libellé d'affichage du rôle
        
        Args:
            role: Code du rôle
            
        Returns:
            str: Libellé avec emoji
        """
        return AppConfig.ROLES.get(role, {}).get('display', role)
    
    def afficher_message(self, texte: str, couleur: str):
        """Affiche un message temporaire
        
        Args:
            texte: Le texte à afficher
            couleur: La couleur de fond (hex)
        """
        self.message_label.setText(texte)
        self.message_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: 11px;
                font-weight: bold;
                background-color: {couleur};
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        self.message_label.setVisible(True)
        QTimer.singleShot(3000, lambda: self.message_label.setVisible(False))
    
    def deverrouiller(self):
        """Déverrouille le compte après la durée de lockout"""
        self.tentatives = 0
        self.ui.pushButton.setEnabled(True)
        self.tentative_label.setVisible(False)
        self.afficher_message("✅ Compte déverrouillé", "#28a745")

    # ── Déplacement de la fenêtre sans barre de titre ────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            sys.exit(0)
        elif event.key() == Qt.Key.Key_F1:
            self.afficher_aide()
        elif (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
              and event.key() == Qt.Key.Key_R):
            self._admin_reset_dialog()
        else:
            super().keyPressEvent(event)

    def _admin_reset_dialog(self):
        """Dialogue de réinitialisation protégé — accessible admin uniquement (Ctrl+Shift+R)."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Réinitialisation — Admin requis")
        dlg.setFixedWidth(340)
        dlg.setStyleSheet("QDialog { background:#f8fafc; }")

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        lbl_title = QtWidgets.QLabel("🔐  Réinitialisation de la base de données")
        lbl_title.setStyleSheet("font-weight:700; font-size:13px; color:#1e3a5f;")
        lbl_title.setWordWrap(True)
        lay.addWidget(lbl_title)

        lbl_info = QtWidgets.QLabel(
            "Cette action remet la configuration sur la base locale.\n"
            "Réservée aux administrateurs."
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lbl_info.setWordWrap(True)
        lay.addWidget(lbl_info)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        lay.addWidget(sep)

        f_user = QtWidgets.QLineEdit()
        f_user.setPlaceholderText("Identifiant administrateur")
        f_user.setStyleSheet(
            "border:1px solid #d1d5db; border-radius:5px; padding:7px 10px; font-size:12px;"
        )
        lay.addWidget(f_user)

        f_pass = QtWidgets.QLineEdit()
        f_pass.setPlaceholderText("Mot de passe")
        f_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        f_pass.setStyleSheet(
            "border:1px solid #d1d5db; border-radius:5px; padding:7px 10px; font-size:12px;"
        )
        lay.addWidget(f_pass)

        lbl_err = QtWidgets.QLabel()
        lbl_err.setStyleSheet(
            "color:#991b1b; background:#fee2e2; border-radius:4px; padding:5px 8px; font-size:11px;"
        )
        lbl_err.setVisible(False)
        lbl_err.setWordWrap(True)
        lay.addWidget(lbl_err)

        btn_row = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Annuler")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#64748b; color:white; border-radius:5px;"
            " padding:7px 16px; font-weight:600; }"
            "QPushButton:hover { background:#475569; }"
        )
        btn_confirm = QtWidgets.QPushButton("Réinitialiser")
        btn_confirm.setStyleSheet(
            "QPushButton { background:#b91c1c; color:white; border-radius:5px;"
            " padding:7px 16px; font-weight:600; }"
            "QPushButton:hover { background:#dc2626; }"
        )
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_confirm)
        lay.addLayout(btn_row)

        _reset_attempts = [0]
        _reset_locked_until = [None]  # datetime | None

        def _do_reset():
            # ── Rate-limit : 3 tentatives max, verrouillage 5 min ──
            now = datetime.now()
            if _reset_locked_until[0] and now < _reset_locked_until[0]:
                remaining = int((_reset_locked_until[0] - now).total_seconds() / 60) + 1
                lbl_err.setText(f"Trop de tentatives. Réessayez dans {remaining} min.")
                lbl_err.setVisible(True)
                return

            username = f_user.text().strip()
            password = f_pass.text()
            if not username or not password:
                lbl_err.setText("Identifiant et mot de passe requis.")
                lbl_err.setVisible(True)
                return

            # Vérification TOUJOURS sur la base locale (indépendante du chemin configuré)
            local_db = AppConfig._runtime_dir() / "db.sqlite3"
            try:
                conn = sqlite3.connect(str(local_db), timeout=5)
                row = conn.execute(
                    "SELECT password, role, is_superuser FROM auth_user "
                    "WHERE username = ? AND is_active = 1",
                    (username,),
                ).fetchone()
                conn.close()
            except Exception as exc:
                lbl_err.setText(f"Erreur accès base locale : {exc}")
                lbl_err.setVisible(True)
                return

            if row is None:
                _reset_attempts[0] += 1
                lbl_err.setText("Utilisateur introuvable.")
                lbl_err.setVisible(True)
                if _reset_attempts[0] >= 3:
                    _reset_locked_until[0] = datetime.now() + timedelta(minutes=5)
                return

            stored_hash, role, is_super = row
            if not verifier_mot_de_passe(password, stored_hash):
                _reset_attempts[0] += 1
                if _reset_attempts[0] >= 3:
                    _reset_locked_until[0] = datetime.now() + timedelta(minutes=5)
                    lbl_err.setText("Trop de tentatives. Compte verrouillé 5 min.")
                else:
                    lbl_err.setText(
                        f"Mot de passe incorrect. "
                        f"({3 - _reset_attempts[0]} essai(s) restant(s))"
                    )
                lbl_err.setVisible(True)
                return

            if role != "admin" and not is_super:
                lbl_err.setText("Accès refusé — compte administrateur requis.")
                lbl_err.setVisible(True)
                return

            # ── Authentification admin OK → réinitialiser ──
            import json as _json
            cfg = AppConfig.DB_CONFIG_FILE
            try:
                cfg.write_text(
                    _json.dumps({"custom_db_path": ""}, indent=2), encoding="utf-8"
                )
            except Exception:
                cfg.unlink(missing_ok=True)

            dlg.accept()
            self.db_path = AppConfig.get_db_path()
            self.creer_table()
            self.creer_utilisateurs_defaut()
            self.afficher_message("✅ Base locale restaurée", "#28a745")

        btn_confirm.clicked.connect(_do_reset)
        f_pass.returnPressed.connect(_do_reset)
        dlg.exec()
    
    def afficher_aide(self):
        """Affiche l'aide en ligne"""
        aide = """
        <h2>Aide à la connexion</h2>
        <h3>Comment se connecter :</h3>
        <ul>
            <li>Entrez votre <b>identifiant</b></li>
            <li>Entrez votre <b>mot de passe</b></li>
            <li>Cliquez sur <b>Connexion</b> ou appuyez sur <b>Entrée</b></li>
        </ul>
        <h3>Problème de connexion ?</h3>
        <p>Contactez votre administrateur système pour obtenir vos identifiants.</p>
        """
        QMessageBox.information(self, "Aide - Connexion", aide)


# ===== PARTIE 4: PROGRAMME PRINCIPAL =====
if __name__ == "__main__":
    print("🚀 Démarrage de l'application...")
    app = QApplication(sys.argv)

    resolved_db_path = AppConfig.get_db_path()
    print(f"[DB] Chemin utilisé: {resolved_db_path}")
    log_runtime_db_path(resolved_db_path)

    # Forcer un thème clair (désactive tout effet de mode nuit système)
    app.setStyle("Fusion")
    light_palette = QtGui.QPalette()
    light_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
    light_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#000000"))
    light_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#ffffff"))
    light_palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#f5f5f5"))
    light_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#000000"))
    light_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#ffffff"))
    light_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#000000"))
    light_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#2a82da"))
    light_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(light_palette)
    
    # Charger les styles depuis le fichier QSS
    style_path = AppConfig.get_style_path()
    if style_path:
        try:
            style_file = QFile(str(style_path))
            style_file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text)
            style_stream = QTextStream(style_file)
            app.setStyleSheet(style_stream.readAll())
            style_file.close()
            print(f"✅ Style chargé depuis: {style_path}")
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement du style: {e}")
    else:
        print("⚠️ Fichier de style non trouvé, style par défaut utilisé")
    
    print("🔍 Création de la fenêtre de connexion...")
    login = LoginApp()
    
    print("🔍 Exécution de la fenêtre de connexion...")
    result = login.exec()
    print(f"🔍 Résultat de connexion: {result}")
    
    if result == QDialog.DialogCode.Accepted:
        print("✅ Connexion acceptée, lancement de la boucle principale")
        sys.exit(app.exec())
    else:
        print("👋 Au revoir!")
        sys.exit(0)
