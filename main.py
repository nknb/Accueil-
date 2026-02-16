# main.py
"""Point d'entrée pour l'application CNPS Accueil"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QDialog, QMessageBox, QApplication
from PyQt6.QtCore import QTimer, Qt, QFile, QTextStream, QIODevice
import sys
from pathlib import Path
import sqlite3
import hashlib
from datetime import datetime

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
except ImportError as e:
    print(f"❌ Erreur d'importation: {e}")
    print("📁 Vérifiez que le chemin sidebar/main_windows.py existe")
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
        Form.resize(625, 565)
        self.widget = QtWidgets.QWidget(parent=Form)
        self.widget.setGeometry(QtCore.QRect(30, 30, 550, 500))
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
        font.setPointSize(20)
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

# ===== PARTIE 2: FONCTIONS DE HASHAGE =====
def hash_sha256(mot_de_passe: str) -> str:
    """Hash un mot de passe en SHA256
    
    Args:
        mot_de_passe: Le mot de passe à hasher
        
    Returns:
        str: Le hash SHA256 du mot de passe
    """
    return hashlib.sha256(mot_de_passe.encode('utf-8')).hexdigest()


def verifier_mot_de_passe(mot_de_passe_entre: str, hash_stocke: str) -> bool:
    """Vérifie qu'un mot de passe correspond à son hash
    
    Args:
        mot_de_passe_entre: Le mot de passe entré par l'utilisateur
        hash_stocke: Le hash stocké en base de données
        
    Returns:
        bool: True si le mot de passe correspond, False sinon
    """
    hash_calcule = hash_sha256(mot_de_passe_entre)
    return hash_calcule == hash_stocke

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
        
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.setWindowTitle("Connexion - CNPS Accueil")
        
        self.ui.pushButton.clicked.connect(self.se_connecter)
        self.ui.lineEdit.returnPressed.connect(self.se_connecter)
        self.ui.lineEdit_2.returnPressed.connect(self.se_connecter)
        
        # Labels de message
        self.message_label = QtWidgets.QLabel(self.ui.widget)
        self.message_label.setGeometry(QtCore.QRect(295, 260, 190, 30))
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setVisible(False)
        
        self.tentative_label = QtWidgets.QLabel(self.ui.widget)
        self.tentative_label.setGeometry(QtCore.QRect(295, 340, 190, 30))
        self.tentative_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tentative_label.setVisible(False)
        
        self.db_path = AppConfig.get_db_path()
        self.creer_table()
        self.creer_utilisateurs_defaut()
        self.ui.lineEdit.setFocus()
    
    def creer_table(self):
        try:
            conn = sqlite3.connect(self.db_path)
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
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM auth_user")
            count = cursor.fetchone()[0]
            
            if count == 0:
                for user in AppConfig.DEFAULT_USERS:
                    password_hash = hash_sha256(user['password'])
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
            conn = sqlite3.connect(str(self.db_path))
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
                    self.mettre_a_jour_last_login(user[0])
                    
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
            self.afficher_message(f"❌ Erreur: {str(e)}", "#dc3545")
            print(f"❌ Erreur base de données: {e}")
        finally:
            self.ui.pushButton.setEnabled(True)
            self.ui.pushButton.setText("Connexion")
    
    def mettre_a_jour_last_login(self, user_id: int):
        """Met à jour la date de dernière connexion
        
        Args:
            user_id: ID de l'utilisateur
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE auth_user SET last_login = ? WHERE id = ?", 
                         (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
        except:
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
    
    def keyPressEvent(self, event):
        """Gère les touches spéciales
        
        Args:
            event: L'événement de touche
        """
        if event.key() == Qt.Key.Key_Escape:
            sys.exit(0)
        elif event.key() == Qt.Key.Key_F1:
            self.afficher_aide()
        else:
            super().keyPressEvent(event)
    
    def afficher_aide(self):
        """Affiche l'aide en ligne"""
        aide = """
        <h2>🔐 Aide à la connexion</h2>
        <h3>📝 Comment se connecter :</h3>
        <ul>
            <li>Entrez votre <b>identifiant</b></li>
            <li>Entrez votre <b>mot de passe</b></li>
            <li>Cliquez sur <b>Connexion</b> ou appuyez sur <b>Entrée</b></li>
        </ul>
        <h3>👥 Comptes de test :</h3>
        <ul>
            <li><b>admin</b> / admin123 - 👑 Administrateur</li>
            <li><b>manager</b> / manager123 - 📊 Manager</li>
            <li><b>accueil</b> / accueil123 - 🏢 Agent Accueil</li>
            <li><b>preaccueil</b> / preaccueil123 - 🛂 Agent Pré-accueil</li>
        </ul>
        """
        QMessageBox.information(self, "Aide - Connexion", aide)


# ===== PARTIE 4: PROGRAMME PRINCIPAL =====
if __name__ == "__main__":
    print("🚀 Démarrage de l'application...")
    app = QApplication(sys.argv)
    
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
