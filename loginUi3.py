# loginUi3.py
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QDialog, QMessageBox, QApplication
from PyQt6.QtCore import QTimer, Qt
import sys ,res
from pathlib import Path
import sqlite3
import hashlib
import os

# Configuration des imports
sys.path.append(str(Path(__file__).parent))

# ===== PARTIE 1: VOTRE INTERFACE (INCHANGÉE) =====
class Ui_Form(object):
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


# ===== PARTIE 2: FONCTIONS DE HASHAGE SHA256 =====
def hash_sha256(mot_de_passe):
    """
    Hash un mot de passe avec SHA256 et retourne le hash en hexadécimal
    """
    return hashlib.sha256(mot_de_passe.encode('utf-8')).hexdigest()

def verifier_mot_de_passe(mot_de_passe_entre, hash_stocke):
    """
    Vérifie si le mot de passe correspond au hash stocké
    """
    # Hasher le mot de passe entré
    hash_calcule = hash_sha256(mot_de_passe_entre)
    
    # Comparaison sécurisée
    return hash_calcule == hash_stocke


# ===== PARTIE 3: LOGIQUE DE CONNEXION =====
class LoginApp(QDialog):
    """Application de connexion avec votre interface"""
    
    def __init__(self):
        super().__init__()
        self.utilisateur = None
        self.tentatives = 0
        self.max_tentatives = 5
        
        # Utiliser VOTRE interface (inchangée)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Titre de la fenêtre
        self.setWindowTitle("Connexion - CNPS Accueil")
        
        # Connecter le bouton de connexion
        self.ui.pushButton.clicked.connect(self.se_connecter)
        
        # Connexion avec la touche Entrée
        self.ui.lineEdit.returnPressed.connect(self.se_connecter)
        self.ui.lineEdit_2.returnPressed.connect(self.se_connecter)
        
        # Label pour les messages (superposé à votre interface)
        self.message_label = QtWidgets.QLabel(self.ui.widget)
        self.message_label.setGeometry(QtCore.QRect(295, 260, 190, 30))
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setVisible(False)
        
        # Label pour les tentatives
        self.tentative_label = QtWidgets.QLabel(self.ui.widget)
        self.tentative_label.setGeometry(QtCore.QRect(295, 340, 190, 30))
        self.tentative_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tentative_label.setVisible(False)
        
        # Trouver la base de données
        self.db_path = self.trouver_db()
        
        # Créer la table si elle n'existe pas
        self.creer_table()
        
        # Créer des utilisateurs par défaut avec hash si nécessaire
        self.creer_utilisateurs_defaut()
        
        # Focus sur l'identifiant
        self.ui.lineEdit.setFocus()
    
    def trouver_db(self):
        """Trouve le chemin de la base de données"""
        chemins = [
            "db.sqlite3",
            "../db.sqlite3",
            Path(__file__).parent / "db.sqlite3"
        ]
        
        for chemin in chemins:
            if Path(chemin).exists():
                print(f"✅ Base trouvée: {chemin}")
                return str(chemin)
        
        print("⚠️ Base non trouvée, création d'une nouvelle base")
        return str(Path(__file__).parent / "db.sqlite3")
    
    def creer_table(self):
        """Crée la table auth_user si elle n'existe pas"""
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
        """Crée des utilisateurs par défaut avec hash SHA256 si la table est vide"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier s'il y a des utilisateurs
            cursor.execute("SELECT COUNT(*) FROM auth_user")
            count = cursor.fetchone()[0]
            
            if count == 0:
                from datetime import datetime
                
                # Utilisateurs par défaut avec mots de passe hashés
                utilisateurs = [
                    ('admin', hash_sha256('admin123'), 'admin@cnps.ci', 1, 1, 1, 'admin'),
                    ('manager', hash_sha256('manager123'), 'manager@cnps.ci', 1, 0, 1, 'manager'),
                    ('accueil', hash_sha256('accueil123'), 'accueil@cnps.ci', 1, 0, 0, 'accueil'),
                    ('preaccueil', hash_sha256('preaccueil123'), 'preaccueil@cnps.ci', 1, 0, 0, 'preaccueil'),
                ]
                
                for username, password_hash, email, is_active, is_super, is_staff, role in utilisateurs:
                    cursor.execute("""
                        INSERT INTO auth_user 
                        (username, password, email, is_active, is_superuser, is_staff, date_joined, role)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (username, password_hash, email, is_active, is_super, is_staff, 
                          datetime.now().isoformat(), role))
                
                conn.commit()
                print("✅ Utilisateurs par défaut créés avec hash SHA256")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Erreur création utilisateurs: {e}")
    
    def se_connecter(self):
        """Vérifie les identifiants"""
        # Vérifier le verrouillage
        if self.tentatives >= self.max_tentatives:
            self.afficher_message("⛔ Compte verrouillé (5 min)", "#dc3545")
            self.tentative_label.setText("⏰ Réessayez dans 5 minutes")
            self.tentative_label.setStyleSheet("color: #ffc107; font-size: 10px;")
            self.tentative_label.setVisible(True)
            self.ui.pushButton.setEnabled(False)
            QTimer.singleShot(300000, self.deverrouiller)  # 5 minutes
            return
        
        identifiant = self.ui.lineEdit.text().strip()
        mot_de_passe = self.ui.lineEdit_2.text()
        
        if not identifiant or not mot_de_passe:
            self.afficher_message("❌ Identifiants requis", "#dc3545")
            return
        
        # Désactiver le bouton
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton.setText("Vérification...")
        
        # Vérifier en arrière-plan
        QTimer.singleShot(100, lambda: self.verifier_db(identifiant, mot_de_passe))
    
    def verifier_db(self, identifiant, mot_de_passe):
        """Vérifie dans la base de données avec hash SHA256"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Chercher l'utilisateur
            cursor.execute("""
                SELECT id, username, password, email, role, is_superuser 
                FROM auth_user 
                WHERE username = ? AND is_active = 1
            """, (identifiant,))
            
            user = cursor.fetchone()
            conn.close()
            
            if user:
                # Récupérer le hash stocké
                hash_stocke = user[2]
                
                # Vérifier le mot de passe avec la fonction de hash
                if verifier_mot_de_passe(mot_de_passe, hash_stocke):
                    # Succès - Mot de passe correct
                    self.utilisateur = {
                        'id': user[0],
                        'username': user[1],
                        'email': user[3],
                        'role': user[4] or ('admin' if user[5] else 'accueil'),
                    }
                    
                    # Ajouter l'affichage du rôle
                    self.utilisateur['role_display'] = self.get_role_display(self.utilisateur['role'])
                    
                    # Succès
                    print(f"✅ Connexion réussie: {identifiant} ({self.utilisateur['role']})")
                    self.tentatives = 0
                    
                    # Afficher message de succès
                    self.afficher_message("✅ Connexion réussie!", "#28a745")
                    
                    # Mettre à jour last_login
                    self.mettre_a_jour_last_login(user[0])
                    
                    # Accepter la connexion
                    QTimer.singleShot(1000, self.accepter_connexion)
                else:
                    # Mauvais mot de passe
                    self.tentatives += 1
                    reste = self.max_tentatives - self.tentatives
                    
                    self.afficher_message(f"❌ Mot de passe incorrect", "#dc3545")
                    if reste > 0:
                        self.tentative_label.setText(f"⚠️ Tentatives restantes: {reste}")
                        self.tentative_label.setStyleSheet("color: #ffc107; font-size: 10px;")
                        self.tentative_label.setVisible(True)
                    
                    self.ui.lineEdit_2.clear()
                    self.ui.lineEdit_2.setFocus()
                    
                    print(f"❌ Échec connexion pour {identifiant} - Tentative {self.tentatives}/{self.max_tentatives}")
            else:
                # Utilisateur non trouvé
                self.tentatives += 1
                reste = self.max_tentatives - self.tentatives
                
                self.afficher_message(f"❌ Utilisateur inconnu", "#dc3545")
                if reste > 0:
                    self.tentative_label.setText(f"⚠️ Tentatives restantes: {reste}")
                    self.tentative_label.setStyleSheet("color: #ffc107; font-size: 10px;")
                    self.tentative_label.setVisible(True)
                
                self.ui.lineEdit_2.clear()
                self.ui.lineEdit_2.setFocus()
                
                print(f"❌ Utilisateur '{identifiant}' non trouvé")
                
        except Exception as e:
            self.afficher_message(f"❌ Erreur: {str(e)}", "#dc3545")
            print(f"❌ Erreur base de données: {e}")
        
        finally:
            # Réactiver le bouton
            self.ui.pushButton.setEnabled(True)
            self.ui.pushButton.setText("Connexion")
    
    def mettre_a_jour_last_login(self, user_id):
        """Met à jour la date de dernière connexion"""
        try:
            from datetime import datetime
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE auth_user 
                SET last_login = ? 
                WHERE id = ?
            """, (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
        except:
            pass  # Silencieux si erreur
    
    def accepter_connexion(self):
        """Accepte la connexion et ferme la boîte de dialogue"""
        self.accept()
    
    def get_role_display(self, role):
        """Retourne l'affichage du rôle"""
        roles = {
            'admin': '👑 Administrateur',
            'manager': '📊 Manager',
            'accueil': '🏢 Agent Accueil',
            'preaccueil': '🛂 Agent Pré-accueil'
        }
        return roles.get(role, role)
    
    def afficher_message(self, texte, couleur):
        """Affiche un message temporaire"""
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
        """Déverrouille après 5 minutes"""
        self.tentatives = 0
        self.ui.pushButton.setEnabled(True)
        self.tentative_label.setVisible(False)
        self.afficher_message("✅ Compte déverrouillé", "#28a745")
    
    def keyPressEvent(self, event):
        """Gère les touches"""
        if event.key() == Qt.Key.Key_Escape:
            sys.exit(0)
        elif event.key() == Qt.Key.Key_F1:
            self.afficher_aide()
        else:
            super().keyPressEvent(event)
    
    def afficher_aide(self):
        """Affiche l'aide"""
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
        
        <h3>⌨️ Raccourcis :</h3>
        <ul>
            <li><b>Entrée</b> : Valider</li>
            <li><b>Échap</b> : Quitter</li>
            <li><b>F1</b> : Cette aide</li>
        </ul>
        """
        
        QMessageBox.information(self, "Aide - Connexion", aide)


# ===== PARTIE 4: PROGRAMME PRINCIPAL =====
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Créer et afficher la fenêtre de connexion
    login = LoginApp()
    
    if login.exec() == QDialog.DialogCode.Accepted:
        # Connexion réussie
        user = login.utilisateur
        print(f"✅ Connecté: {user['username']} - {user['role_display']}")
        
        # ICI vous pouvez ouvrir votre fenêtre principale
        # from votre_fenetre_principale import MainWindow
        # main_window = MainWindow()
        # main_window.set_user(user)
        # main_window.show()
        
        # Pour test, on affiche juste un message
        msg = QMessageBox()
        msg.setWindowTitle("Connexion réussie")
        msg.setText(f"Bienvenue {user['username']} !\n\nRôle: {user['role_display']}")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        
        sys.exit(app.exec())
    else:
        print("👋 Au revoir!")
        sys.exit(0)