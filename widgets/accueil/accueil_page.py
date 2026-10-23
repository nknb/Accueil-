"""Accueil page embedding the Show_Data UI — avec rendu de tableau moderne."""

from datetime import date, datetime, time, timedelta

from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
)

from config import AppConfig
from database.connection import db
from utils import app_logger
from .Show_Data import Ui_MainWindow


# ── Rôle custom pour le flag is_traite ───────────────────────────────────────
_ROLE_IS_TRAITE = Qt.ItemDataRole.UserRole + 10


# ── Délégué de rendu moderne ─────────────────────────────────────────────────

class _ModernRowDelegate(QStyledItemDelegate):
    """Délégué de rendu moderne pour la table Accueil.

    - Fond coloré selon statut : vert pâle (TRAITÉ) / rouge pâle (EN ATTENTE)
    - Barre indicatrice verticale 5 px sur la première colonne
    - Badge pill arrondi sur la colonne Statut (col 12)
    - Séparateur horizontal subtil entre lignes
    - Overlay indigo semi-transparent sur la ligne sélectionnée
    - Taille de police dynamique (mise à jour par AccueilPage via font_size)
    """

    _STATUS_COL = 10   # colonne Statut (Priorité + Date supprimées)

    # Palette TRAITÉ
    _TRAITE_BG  = QColor("#ecfdf5")
    _TRAITE_BAR = QColor("#22c55e")
    _TRAITE_FG  = QColor("#166534")

    # Palette EN ATTENTE / NON TRAITÉ
    _NON_BG     = QColor("#fff1f2")
    _NON_BAR    = QColor("#ef4444")
    _NON_FG     = QColor("#991b1b")

    _BAR_W    = 5
    _SEL_OVRL = QColor(99, 102, 241, 40)   # indigo semi-transparent
    _DIVIDER  = QColor(0, 0, 0, 12)

    # ── Alignements réutilisables ────────────────────────────────────────────
    _AL  = Qt.AlignmentFlag.AlignLeft    | Qt.AlignmentFlag.AlignVCenter
    _AC  = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

    # ── Config typographique par colonne (12 colonnes, Priorité supprimée) ──
    # Format : (bold, italic, align, fixed_color_or_None, size_delta)
    # fixed_color = None → couleur dynamique selon statut (fg)
    _COL_CFG = {
        0:  (True,  False, _AL, None,                0),   # Nom — gras, couleur statut
        1:  (False, False, _AL, QColor("#374151"),   0),   # Prénom — normal, gris foncé
        2:  (False, False, _AL, QColor("#6b7280"),  -1),   # N° CNPS — petit, muted
        3:  (True,  False, _AL, QColor("#1e3a5f"),   0),   # Service — gras, navy
        4:  (False, True,  _AL, QColor("#4b5563"),   0),   # Motif — italic, ardoise
        5:  (False, False, _AL, QColor("#6b7280"),  -1),   # Contact — petit, muted
        6:  (True,  False, _AC, QColor("#1e293b"),   0),   # H. arrivée — gras, centré
        7:  (True,  False, _AC, QColor("#065f46"),   0),   # H. réception — gras, vert foncé
        8:  (True,  False, _AC, None,                0),   # T. attente — coloré selon durée
        9:  (False, False, _AC, QColor("#b45309"),   0),   # Satisfaction — étoiles, ambre
        # 10: Statut → badge pill, géré séparément
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_size: int = 8   # mis à jour dynamiquement par AccueilPage

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _wait_color(text: str) -> QColor:
        """Couleur du temps d'attente : vert ≤15 min, orange ≤30, rouge >30."""
        try:
            parts = str(text).strip().split(":")
            total_min = int(parts[0]) * 60 + int(parts[1]) if len(parts) >= 2 else int(parts[0])
            if total_min <= 15:
                return QColor("#166534")
            if total_min <= 30:
                return QColor("#92400e")
            return QColor("#991b1b")
        except (ValueError, IndexError):
            return QColor("#374151")

    @staticmethod
    def _stars(text: str) -> str:
        """Convertit un chiffre 1-5 en étoiles (ex : 4 → ★★★★☆)."""
        try:
            v = max(0, min(5, int(float(text))))
            return "★" * v + "☆" * (5 - v)
        except (ValueError, TypeError):
            return text

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        row = index.row()
        col = index.column()
        model = index.model()

        is_traite = bool(model.index(row, 0).data(_ROLE_IS_TRAITE))

        bg  = self._TRAITE_BG  if is_traite else self._NON_BG
        bar = self._TRAITE_BAR if is_traite else self._NON_BAR
        fg  = self._TRAITE_FG  if is_traite else self._NON_FG

        if row % 2 == 0:
            bg = bg.darker(103)

        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Fond
        painter.fillRect(rect, bg)

        # 2. Barre indicatrice (première colonne)
        if col == 0:
            painter.fillRect(QRect(rect.left(), rect.top(), self._BAR_W, rect.height()), bar)

        # 3. Séparateur horizontal
        painter.setPen(QPen(self._DIVIDER, 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        # 4. Overlay sélection
        if selected:
            painter.fillRect(rect, self._SEL_OVRL)

        painter.restore()

        # ── 5. Récupération du texte brut ────────────────────────────────────
        raw_text = index.data(Qt.ItemDataRole.DisplayRole)
        if not raw_text:
            return
        text = str(raw_text)

        # ── 6. Colonne Statut → badge pill centré ────────────────────────────
        if col == self._STATUS_COL:
            char_w  = max(6, self.font_size - 1)
            badge_w = max(len(text) * char_w + 16, 70)
            badge_h = min(rect.height() - 6, max(14, self.font_size + 6))
            badge_x = rect.left() + (rect.width() - badge_w) // 2
            badge_y = rect.top() + (rect.height() - badge_h) // 2
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(bar))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(badge_rect, badge_h / 2, badge_h / 2)

            font = QFont("", max(6, self.font_size - 1))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor("white")))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
            return

        # ── 7. Typographie per-colonne ────────────────────────────────────────
        cfg = self._COL_CFG.get(col)
        if cfg is None:
            return

        bold, italic, align, fixed_color, size_delta = cfg

        # Taille de police adaptée
        pt = max(6, self.font_size + int(size_delta))
        font = QFont("", pt)
        font.setBold(bold)
        font.setItalic(italic)

        # Couleur selon la colonne
        if fixed_color is not None:
            color = fixed_color
        elif col == 8:   # Temps d'attente → coloré par durée
            color = self._wait_color(text)
        else:
            color = fg

        # Texte transformé selon la colonne
        if col == 9 and text not in ("-", ""):   # Satisfaction → étoiles
            text = self._stars(text)

        # Padding gauche : réserve la barre indicatrice sur col 0
        left_pad = self._BAR_W + 5 if col == 0 else 6
        text_rect = rect.adjusted(left_pad, 0, -4, 0)

        painter.save()
        painter.setFont(font)
        painter.setPen(QPen(color))
        painter.drawText(
            text_rect,
            align | Qt.TextFlag.TextSingleLine,
            text,
        )
        painter.restore()


# ── Dialogue de traitement ────────────────────────────────────────────────────

class TraitementDialog(QDialog):
    """Formulaire de traitement d'une demande — design navy/card moderne."""

    _DIALOG_SS = """
        QDialog {
            background: #f0f4f8;
        }
        /* ── Header ── */
        #tdHeader {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0f2744, stop:0.6 #1e3a5f, stop:1 #1a4a7a);
            border-radius: 0px;
        }
        #tdHeaderTitle {
            color: #ffffff;
            font-size: 14px;
            font-weight: 700;
        }
        #tdHeaderSub {
            color: #bfdbfe;
            font-size: 11px;
        }
        /* ── Cards ── */
        QGroupBox {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 700;
            color: #1e3a5f;
            padding-top: 14px;
            margin-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        /* ── Champs lecture seule ── */
        QLineEdit[readOnly="true"] {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 6px 10px;
            color: #374151;
            font-size: 12px;
        }
        /* ── Labels champ ── */
        #tdFieldLabel {
            color: #64748b;
            font-size: 10px;
            font-weight: 600;
        }
        /* ── Textarea commentaire ── */
        QTextEdit {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 8px;
            color: #1e293b;
            font-size: 12px;
        }
        QTextEdit:focus { border-color: #3b82f6; }
        /* ── Boutons ── */
        #tdBtnSave {
            background: #1e3a5f;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 28px;
            font-size: 12px;
            font-weight: 700;
        }
        #tdBtnSave:hover  { background: #163059; }
        #tdBtnSave:pressed{ background: #0f2744; }
        #tdBtnCancel {
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 10px 22px;
            font-size: 12px;
            font-weight: 600;
        }
        #tdBtnCancel:hover { background: #e2e8f0; }
        /* ── Badges horaires ── */
        #tdTimeBadge {
            color: #1e293b;
            font-size: 20px;
            font-weight: 700;
            background: #f1f5f9;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            padding: 6px 14px;
        }
        #tdTimeBadgeLive {
            color: #1e3a5f;
            font-size: 20px;
            font-weight: 700;
            background: #dcfce7;
            border: 2px solid #86efac;
            border-radius: 10px;
            padding: 6px 14px;
        }
        /* ── Compteur d'attente ── */
        #tdWaitDisplay {
            font-size: 18px;
            font-weight: 700;
            padding: 2px 8px;
        }
        /* ── Étoiles satisfaction ── */
        #tdStar {
            font-size: 22px;
            background: transparent;
            border: none;
            padding: 0 3px;
        }
    """

    @staticmethod
    def _note_valide(valeur) -> int:
        """Note de satisfaction 0-5; toute valeur illisible (texte, 99…) devient 0/5 au lieu de bloquer le traitement."""
        try:
            return max(0, min(5, int(float(valeur or 0))))
        except (TypeError, ValueError):
            return 0

    def __init__(self, demande: dict, parent=None):
        super().__init__(parent)
        self.demande = demande
        self._satisfaction = self._note_valide(demande.get("satisfaction"))
        self._arrivee_dt   = self._parse_arrivee(demande)
        # Heure de réception capturée une seule fois à l'ouverture
        self._heure_reception = datetime.now()
        self.setWindowTitle("Traitement de la demande")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(self._DIALOG_SS)
        self._build_ui()

    @staticmethod
    def _parse_arrivee(demande: dict):
        """Parse l'heure d'arrivée en datetime pour calculer l'attente."""
        raw = demande.get("heure_arrivee")
        if not raw:
            return None
        try:
            h_str = AccueilPage._format_time_value(raw)   # → HH:MM:SS
            t = datetime.strptime(h_str, "%H:%M:%S").time()
            return datetime.combine(datetime.now().date(), t)
        except (ValueError, TypeError):
            return None

    # ── Construction UI ────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        body = QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 16)
        body.setSpacing(12)

        body.addWidget(self._make_info_card())
        body.addWidget(self._make_timing_card())
        body.addWidget(self._make_evaluation_card())
        body.addLayout(self._make_buttons())

        root.addLayout(body)

    def _make_header(self) -> QWidget:
        """Bandeau navy avec nom/prénom et service."""
        header = QWidget()
        header.setObjectName("tdHeader")
        header.setFixedHeight(72)
        hl = QVBoxLayout(header)
        hl.setContentsMargins(20, 10, 20, 10)
        hl.setSpacing(3)

        nom     = (self.demande.get("nom") or "").upper()
        prenom  = (self.demande.get("prenom") or "").title()
        service = self.demande.get("service") or "—"
        cnps    = self.demande.get("numero_cnps") or "—"

        title = QLabel(f"Traitement — {nom.upper()} {prenom}")
        title.setObjectName("tdHeaderTitle")

        sub = QLabel(f"Service : {service}   |   N° CNPS : {cnps}")
        sub.setObjectName("tdHeaderSub")

        hl.addWidget(title)
        hl.addWidget(sub)
        return header

    @staticmethod
    def _field(label_text: str, value: str) -> QVBoxLayout:
        """Mini colonne : label gris + champ lecture seule."""
        col = QVBoxLayout()
        col.setSpacing(3)
        lbl = QLabel(label_text)
        lbl.setObjectName("tdFieldLabel")
        inp = QLineEdit(value or "—")
        inp.setReadOnly(True)
        inp.setMinimumHeight(34)
        col.addWidget(lbl)
        col.addWidget(inp)
        return col

    def _make_info_card(self) -> QGroupBox:
        box = QGroupBox("Informations de l'assuré")
        grid = QGridLayout(box)
        grid.setSpacing(10)
        grid.setContentsMargins(12, 8, 12, 12)

        motif   = self.demande.get("motif") or "—"
        contact = self.demande.get("contacts") or "—"

        grid.addLayout(self._field("Nom",     self.demande.get("nom") or ""), 0, 0)
        grid.addLayout(self._field("Prénom",  self.demande.get("prenom") or ""), 0, 1)
        grid.addLayout(self._field("N° CNPS", self.demande.get("numero_cnps") or ""), 0, 2)
        grid.addLayout(self._field("Service", self.demande.get("service") or ""), 1, 0, 1, 2)
        grid.addLayout(self._field("Contact", contact), 1, 2)
        grid.addLayout(self._field("Motif",   motif), 2, 0, 1, 3)
        return box

    def _make_timing_card(self) -> QGroupBox:
        """Carte horaires — heure réception capturée à l'ouverture, temps fixe."""
        box = QGroupBox("Horaires & Temps d'attente")
        vl = QVBoxLayout(box)
        vl.setSpacing(10)
        vl.setContentsMargins(12, 8, 12, 14)

        # ── Badges heure arrivée / heure réception ───────────────────────────
        clocks_row = QHBoxLayout()
        clocks_row.setSpacing(16)

        h_arr = AccueilPage._format_time_value(self.demande.get("heure_arrivee"))
        h_rec = self._heure_reception.strftime("%H:%M:%S")

        def _time_col(label_text, badge_text, obj_name):
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setObjectName("tdFieldLabel")
            badge = QLabel(badge_text)
            badge.setObjectName(obj_name)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl)
            col.addWidget(badge)
            return col

        clocks_row.addLayout(
            _time_col("Heure d'arrivée (Pré-accueil)", h_arr, "tdTimeBadge"), 1)
        clocks_row.addLayout(
            _time_col("Heure de réception  ✔ enregistrée", h_rec, "tdTimeBadgeLive"), 1)
        vl.addLayout(clocks_row)

        # ── Temps d'attente calculé une seule fois ───────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #e2e8f0; margin: 4px 0;")
        vl.addWidget(sep)

        wait_row = QHBoxLayout()
        wait_lbl = QLabel("Temps d'attente :")
        wait_lbl.setObjectName("tdFieldLabel")

        if self._arrivee_dt:
            delta_sec = max(0, int((self._heure_reception - self._arrivee_dt).total_seconds()))
            h, rem = divmod(delta_sec, 3600)
            m, s   = divmod(rem, 60)
            wait_str = f"{h:02d}h {m:02d}min {s:02d}s"
            color = "#166534" if delta_sec <= 900 else (
                    "#92400e" if delta_sec <= 1800 else "#991b1b")
        else:
            wait_str, color = "—", "#64748b"

        wait_val = QLabel(wait_str)
        wait_val.setObjectName("tdWaitDisplay")
        wait_val.setStyleSheet(
            f"font-size:18px; font-weight:700; padding:2px 8px; color:{color};")

        wait_row.addWidget(wait_lbl)
        wait_row.addWidget(wait_val)
        wait_row.addStretch()
        vl.addLayout(wait_row)

        return box

    def _make_evaluation_card(self) -> QGroupBox:
        box = QGroupBox("Évaluation")
        vl = QVBoxLayout(box)
        vl.setSpacing(10)
        vl.setContentsMargins(12, 8, 12, 12)

        # Étoiles cliquables
        star_lbl = QLabel("Satisfaction")
        star_lbl.setObjectName("tdFieldLabel")
        vl.addWidget(star_lbl)

        star_row = QHBoxLayout()
        star_row.setSpacing(0)
        star_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._star_btns = []
        for i in range(1, 6):
            btn = QPushButton("★" if i <= self._satisfaction else "☆")
            btn.setObjectName("tdStar")
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, v=i: self._set_satisfaction(v))
            self._star_btns.append(btn)
            star_row.addWidget(btn)
        self._refresh_stars()
        vl.addLayout(star_row)

        # Commentaire
        cmt_lbl = QLabel("Commentaire (optionnel)")
        cmt_lbl.setObjectName("tdFieldLabel")
        vl.addWidget(cmt_lbl)

        self.commentaire_input = QTextEdit()
        self.commentaire_input.setPlainText(str(self.demande.get("commentaire_satisfaction") or ""))
        self.commentaire_input.setFixedHeight(80)
        self.commentaire_input.setPlaceholderText("Observations sur cette prise en charge…")
        vl.addWidget(self.commentaire_input)
        return box

    def _make_buttons(self) -> QHBoxLayout:
        hl = QHBoxLayout()
        hl.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setObjectName("tdBtnCancel")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("✔  Valider le traitement")
        btn_save.setObjectName("tdBtnSave")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)

        hl.addStretch()
        hl.addWidget(btn_cancel)
        hl.addWidget(btn_save)
        return hl

    # ── Satisfaction ───────────────────────────────────────────────────────

    def _set_satisfaction(self, value: int):
        self._satisfaction = value
        self._refresh_stars()

    def _refresh_stars(self):
        for i, btn in enumerate(self._star_btns, start=1):
            if i <= self._satisfaction:
                btn.setText("★")
                btn.setStyleSheet(
                    "font-size:22px; background:transparent; border:none;"
                    "color:#f59e0b; padding:0 3px;"
                )
            else:
                btn.setText("☆")
                btn.setStyleSheet(
                    "font-size:22px; background:transparent; border:none;"
                    "color:#cbd5e1; padding:0 3px;"
                )

    # ── Payload ────────────────────────────────────────────────────────────

    def payload(self):
        return {
            "heure_reception": self._heure_reception.strftime("%H:%M:%S"),
            "satisfaction": self._satisfaction,
            "commentaire_satisfaction": self.commentaire_input.toPlainText().strip(),
        }


# ── Worker async ──────────────────────────────────────────────────────────────

def plage_jour(jour_iso: str) -> tuple:
    """Renvoie (jour, jour suivant) en chaînes ISO pour `date >= ? AND date < ?`.

    Reste correct si `date` est stockée en 'AAAA-MM-JJ' ou 'AAAA-MM-JJTHH:MM:SS'
    et permet d'utiliser un index sur `date` (contrairement à DATE(date) = ?).
    """
    jour = date.fromisoformat(jour_iso[:10])
    return jour.isoformat(), (jour + timedelta(days=1)).isoformat()


def marquer_traitee(demande_id, valeurs: tuple, role, agent_id=None) -> int:
    """UPDATE du traitement d'une demande; renvoie le nombre de lignes modifiées.

    Pour le rôle 'accueil' la clause WHERE exige statut != 'traite' (atomique): si un autre
    poste a déjà traité la demande, 0 ligne est modifiée (l'agent d'origine est donc conservé).
    Admin/manager gardent le droit de modifier et deviennent alors l'agent enregistré.
    `valeurs` = (heure_reception, satisfaction, commentaire, temps_attente, delai_objectif, updated_at);
    `agent_id` = id de l'utilisateur connecté (traçabilité: agent_accueil_id), inchangé s'il est inconnu (None).
    """
    garde = " AND COALESCE(statut, '') != 'traite'" if role == "accueil" else ""
    valeurs = tuple(valeurs)
    return db.execute_update(
        """
        UPDATE accueil_demandeaccueil
        SET heure_reception = ?,
            satisfaction = ?,
            commentaire_satisfaction = ?,
            temps_attente = ?,
            delai_objectif = ?,
            statut = 'traite',
            updated_at = ?,
            traite_le = ?,
            agent_accueil_id = COALESCE(?, agent_accueil_id)
        WHERE id = ?""" + garde,
        valeurs + (valeurs[-1], agent_id, demande_id),
    )


def agent_du_traitement(demande_id):
    """Identifiant de connexion de l'agent qui a traité la demande; None si inconnu (non traitée, compte supprimé)."""
    lignes = db.execute_query(
        "SELECT u.username FROM accueil_demandeaccueil d JOIN auth_user u ON u.id = d.agent_accueil_id WHERE d.id = ?",
        (demande_id,),
    )
    return lignes[0]["username"] if lignes else None


class AccueilDemandesWorker(QObject):
    """Worker Qt pour charger les demandes du jour hors thread UI.

    Si `previous_token` est fourni (rafraîchissement automatique), le jeton de changement
    est lu d'abord: s'il est identique, la liste n'est pas relue (signal `unchanged`).
    """

    finished = pyqtSignal(list)
    unchanged = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, today_str, previous_token=None):
        super().__init__()
        self.today_str = today_str
        self.previous_token = previous_token
        self.token = None

    def run(self):
        try:
            self.token = db.change_token()
        except Exception as exc:  # repli: rechargement complet
            app_logger.warning(f"Lecture du jeton de changement impossible (accueil): {exc}")
            self.token = None
        if self.token is not None and self.token == self.previous_token:
            self.unchanged.emit()
            return
        debut, fin = plage_jour(self.today_str)
        query = """
        SELECT
            d.id,
            d.nom,
            d.prenom,
            d.numero_cnps,
            s.nom AS service,
            m.nom AS motif,
            d.contacts,
            d.heure_arrivee,
            d.heure_reception,
            d.temps_attente,
            d.satisfaction,
            d.date,
            d.statut,
            d.updated_at
        FROM accueil_demandeaccueil d
        LEFT JOIN accueil_service s ON d.service_demande_id = s.id
        LEFT JOIN accueil_motif m ON d.motif_id = m.id
        WHERE d.date >= ? AND d.date < ?
        ORDER BY CASE WHEN d.statut = 'en_attente' THEN 0 ELSE 1 END,
             COALESCE(d.created_at, d.updated_at, d.date) DESC
        """
        try:
            results = db.execute_query(query, (debut, fin))
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Page principale ───────────────────────────────────────────────────────────

class AccueilPage(QMainWindow):
    """Page Accueil avec délégué de rendu moderne et tableau stylisé."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.current_user_role = None
        self.current_user_id = None
        self._refresh_in_progress = False
        self._last_table_signature = None
        self._refresh_pending = False
        self._refresh_context = {"preserve_ui_state": False, "silent": False}
        self._reload_thread = None
        self._last_token = None
        self._last_token_day = None

        # ── Pagination ──────────────────────────────────────────────────
        self._all_acc_results: list = []
        self._acc_page: int = 0
        self._acc_page_size: int = 25
        self._reload_worker = None
        self._cache_ttl_sec = AppConfig.ACCUEIL_CACHE_TTL_SEC
        self._demandes_cache = {}

        self.setWindowTitle("Accueil — Traitement des demandes")
        self.ui.label_2.setText("  Accueil — Traitement des demandes du jour")
        self._apply_global_style()
        self._init_indicators()
        self._init_table()
        self._wire_actions()
        self.load_demandes()
        self._init_auto_refresh()

    # ── Thème global ──────────────────────────────────────────────────────────

    def _apply_global_style(self):
        """Applique le thème navy/slate cohérent avec le reste de l'application."""
        self.setStyleSheet("""
            QMainWindow, #centralwidget {
                background: #f0f4f8;
            }
            #groupBox {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0f2744, stop:0.5 #1e3a5f, stop:1 #1a4a7a);
                border: none;
                border-radius: 0px;
            }
            #groupBox QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            #groupBox QPushButton {
                background: rgba(255,255,255,0.15);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 5px;
                padding: 5px 14px;
                font-weight: 600;
            }
            #groupBox QPushButton:hover { background: rgba(255,255,255,0.25); }
            #groupBox_2 {
                background: #ffffff;
                border: none;
                border-top: 1px solid #e2e8f0;
            }
            #horizontalLayout_2 QLabel {
                color: #1e293b;
                font-size: 12px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 4px;
            }
        """)

    # ── Auto-refresh ──────────────────────────────────────────────────────────

    def _init_auto_refresh(self):
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._on_auto_refresh_timeout)
        self._auto_refresh_timer.start(AppConfig.AUTO_REFRESH_INTERVAL_MS)

    def _on_auto_refresh_timeout(self):
        self.load_demandes(preserve_ui_state=True, silent=True)

    def set_current_user(self, user):
        role = (user or {}).get("role")
        self.current_user_role = str(role).strip().lower() if role else None
        self.current_user_id = (user or {}).get("id")   # enregistré comme agent à chaque traitement

    # ── Indicateurs ───────────────────────────────────────────────────────────

    def _init_indicators(self):
        action_font = self.ui.get_data_btn.font()

        current_date = datetime.now().strftime('%d/%m/%Y')
        self.indicateur_jour = QLabel(
            f"Liste de demande du <span style='color:#1e88e5; text-decoration: underline;'>{current_date}</span>"
        )
        self.indicateur_jour.setFont(action_font)
        self.indicateur_jour.setStyleSheet("color: #333333;")

        self.indicateur_traite = QLabel("✅  Traités: 0")
        self.indicateur_traite.setFont(action_font)
        self.indicateur_traite.setStyleSheet(
            "color: #166534; background: #dcfce7; border-radius: 10px;"
            "padding: 2px 10px; font-weight: 700;"
        )

        self.indicateur_attente = QLabel("⏳  En attente: 0")
        self.indicateur_attente.setFont(action_font)
        self.indicateur_attente.setStyleSheet(
            "color: #991b1b; background: #fee2e2; border-radius: 10px;"
            "padding: 2px 10px; font-weight: 700;"
        )

        self.refresh_state_label = QLabel("• À jour")
        self.refresh_state_label.setFont(action_font)
        self.refresh_state_label.setStyleSheet("color: #0a8f2e; font-weight: 600;")

        self.refresh_spinner = QLabel("⟳")
        self.refresh_spinner.setFont(action_font)
        self.refresh_spinner.setStyleSheet("color: #1e88e5; font-weight: 700;")
        self.refresh_spinner.setVisible(False)

        for index in reversed(range(self.ui.horizontalLayout_2.count())):
            item = self.ui.horizontalLayout_2.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                self.ui.horizontalLayout_2.takeAt(index)

        self.ui.horizontalLayout_2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ui.horizontalLayout_2.insertWidget(0, self.indicateur_jour)
        self.ui.horizontalLayout_2.insertWidget(1, self.indicateur_traite)
        self.ui.horizontalLayout_2.insertWidget(2, self.indicateur_attente)
        self.ui.horizontalLayout_2.insertWidget(3, self.refresh_state_label)
        self.ui.horizontalLayout_2.insertWidget(4, self.refresh_spinner)

    # ── Initialisation du tableau ─────────────────────────────────────────────

    def _init_table(self):
        table = self.ui.tableWidget

        table.setColumnCount(11)
        table.setHorizontalHeaderLabels([
            "Nom", "Prénom", "N° CNPS", "Service", "Motif", "Contact",
            "H. Arrivée", "H. Réception", "T. Attente",
            "Satisfaction", "Statut",
        ])
        table.setRowCount(0)
        table.setAlternatingRowColors(False)   # géré par le délégué
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.setSelectionMode(table.SelectionMode.SingleSelection)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.setHorizontalScrollMode(table.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setShowGrid(False)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers)

        # Délégué de rendu moderne
        table.setItemDelegate(_ModernRowDelegate(table))

        # Style moderne du tableau — cohérent avec PreAccueil
        table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                outline: none;
                gridline-color: transparent;
                selection-background-color: transparent;
                selection-color: inherit;
            }
            QTableWidget::item {
                padding: 0px 6px;
                border: none;
            }
            QTableWidget::item:selected { background: transparent; }
            QHeaderView { background: #1e3a5f; border: none; }
            QHeaderView::section {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1e3a5f, stop:1 #163059);
                color: white;
                font-weight: 700;
                letter-spacing: 0.3px;
                padding: 6px 6px;
                border: none;
                border-right: 1px solid #2a4f80;
                border-bottom: 2px solid #3b82f6;
            }
            QHeaderView::section:last { border-right: none; }
            QScrollBar:vertical {
                background: #f1f5f9; width: 6px; border-radius: 3px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        # En-tête horizontal
        table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setDefaultSectionSize(28)

        # Déclenchement du layout responsive après affichage
        QTimer.singleShot(0, self._on_resize_deferred)
        QTimer.singleShot(0, self._acc_build_pagination_bar)

    # Proportions des 12 colonnes (somme = 1.0)
    # Nom, Prénom, CNPS, Service, Motif, Contact,
    # H.arrivée, H.récep, T.attente, Satisf, Statut
    _COL_PROPORTIONS = [
        0.10, 0.10, 0.08, 0.14, 0.14, 0.08,
        0.07, 0.07, 0.07, 0.07, 0.08,
    ]

    def _fit_columns_to_width(self, available_width: int) -> None:
        """Distribue les largeurs proportionnellement et adapte la typographie."""
        if available_width <= 0:
            return
        table = self.ui.tableWidget
        header = table.horizontalHeader()

        # ── Taille de police selon la largeur disponible ──────────────────────
        if available_width >= 1300:
            font_size   = 9
            hdr_size    = 8
            row_height  = 30
        elif available_width >= 1000:
            font_size   = 8
            hdr_size    = 7
            row_height  = 27
        else:
            font_size   = 7
            hdr_size    = 6
            row_height  = 24

        # Police en-tête
        hf = QFont("", hdr_size)
        hf.setBold(True)
        header.setFont(hf)

        # Police cellules (délégué)
        delegate = table.itemDelegate()
        if isinstance(delegate, _ModernRowDelegate):
            delegate.font_size = font_size

        # Hauteur de ligne
        table.verticalHeader().setDefaultSectionSize(row_height)

        # ── Largeurs proportionnelles ─────────────────────────────────────────
        header.setStretchLastSection(False)
        for col_idx, proportion in enumerate(self._COL_PROPORTIONS):
            w = max(45, int(available_width * proportion))
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col_idx, w)

        table.viewport().update()

    # ── Responsive resize ────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._on_resize_deferred)

    def _on_resize_deferred(self):
        if not hasattr(self, "ui") or self.ui.tableWidget is None:
            return
        vp_width = self.ui.tableWidget.viewport().width()
        if vp_width > 0:
            self._fit_columns_to_width(vp_width)

    # ── Connexions ────────────────────────────────────────────────────────────

    def _wire_actions(self):
        self.ui.get_data_btn.clicked.connect(self.load_demandes)
        self.ui.save_btn.clicked.connect(self.open_selected_demande)
        self.ui.tableWidget.cellDoubleClicked.connect(lambda _row, _col: self.open_selected_demande())

    # ── Refresh state ─────────────────────────────────────────────────────────

    def _set_refresh_state(self, text, color):
        self.refresh_state_label.setText(text)
        self.refresh_state_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _build_cache_key(self, today_str):
        return f"{today_str}::accueil"

    def _get_cached_results(self, today_str):
        entry = self._demandes_cache.get(self._build_cache_key(today_str))
        if not entry:
            return None
        ts = entry.get("ts")
        data = entry.get("data")
        if not ts or data is None:
            return None
        if (datetime.now() - ts).total_seconds() > self._cache_ttl_sec:
            return None
        return data

    def _set_cached_results(self, today_str, results):
        self._demandes_cache[self._build_cache_key(today_str)] = {
            "ts": datetime.now(),
            "data": results,
        }

    # ── Refresh lifecycle ─────────────────────────────────────────────────────

    def _finalize_refresh(self):
        self._refresh_in_progress = False
        self.refresh_spinner.setVisible(False)

        if self._refresh_pending:
            self._refresh_pending = False
            ctx = dict(self._refresh_context)
            QTimer.singleShot(0, lambda: self.load_demandes(ctx.get("preserve_ui_state", True), ctx.get("silent", True)))

    def _start_reload_worker(self, today_str, silent=False):
        self._reload_thread = QThread(self)
        # Auto-refresh: on ne relit la liste que si le jeton a changé (même jour)
        prev = self._last_token if (silent and self._last_token_day == today_str) else None
        self._reload_worker = AccueilDemandesWorker(today_str, previous_token=prev)
        self._reload_worker.moveToThread(self._reload_thread)
        self._reload_thread.started.connect(self._reload_worker.run)
        self._reload_worker.finished.connect(self._on_reload_finished)
        self._reload_worker.failed.connect(self._on_reload_failed)
        self._reload_worker.unchanged.connect(self._on_reload_unchanged)
        self._reload_worker.unchanged.connect(self._reload_thread.quit)
        self._reload_worker.finished.connect(self._reload_thread.quit)
        self._reload_worker.failed.connect(self._reload_thread.quit)
        self._reload_thread.finished.connect(self._reload_worker.deleteLater)
        self._reload_thread.finished.connect(self._reload_thread.deleteLater)
        self._reload_thread.finished.connect(lambda: setattr(self, "_reload_worker", None))
        self._reload_thread.finished.connect(lambda: setattr(self, "_reload_thread", None))
        self._reload_thread.start()

    # ── Peuplement du tableau ─────────────────────────────────────────────────

    def _apply_demandes_results(self, results, preserve_ui_state=False, silent=False):
        selected_demande_id = self._get_selected_demande_id() if preserve_ui_state else None
        scroll_value = self.ui.tableWidget.verticalScrollBar().value() if preserve_ui_state else 0

        current_signature = tuple(
            (
                r.get("id"), r.get("statut"), r.get("heure_reception"),
                r.get("temps_attente"), r.get("satisfaction"), r.get("updated_at"),
            )
            for r in results
        )
        if silent and current_signature == self._last_table_signature:
            self._set_refresh_state("• À jour", "#0a8f2e")
            return
        self._last_table_signature = current_signature

        # Compteurs globaux (sur TOUS les résultats, pas seulement la page)
        total_traite  = sum(1 for r in results if r.get("statut") == "traite")
        total_attente = sum(1 for r in results if r.get("statut") == "en_attente")

        current_date = datetime.now().strftime('%d/%m/%Y')
        self.indicateur_jour.setText(
            f"Liste de demande du <span style='color:#1e88e5; text-decoration: underline;'>{current_date}</span>"
        )
        self.indicateur_traite.setText(f"✅  Traités: {total_traite}")
        self.indicateur_attente.setText(f"⏳  En attente: {total_attente}")

        # Stocker et afficher la première page
        self._all_acc_results = results
        self._acc_goto_page(0)

        if preserve_ui_state:
            self._restore_selection_by_id(selected_demande_id)
            self.ui.tableWidget.verticalScrollBar().setValue(scroll_value)

        self._set_refresh_state("• À jour", "#0a8f2e")

    def _on_reload_unchanged(self):
        """Rien de nouveau en base: on garde l'affichage actuel."""
        try:
            self._set_refresh_state("• À jour", "#0a8f2e")
        finally:
            self._finalize_refresh()

    def _on_reload_finished(self, results):
        try:
            today_str = datetime.now().date().isoformat()
            worker = getattr(self, "_reload_worker", None)
            self._last_token = getattr(worker, "token", None)
            self._last_token_day = today_str
            self._set_cached_results(today_str, results)
            self._apply_demandes_results(
                results,
                preserve_ui_state=self._refresh_context.get("preserve_ui_state", False),
                silent=self._refresh_context.get("silent", False),
            )
        finally:
            self._finalize_refresh()

    def _on_reload_failed(self, error_message):
        self._set_refresh_state("• Erreur sync", "#c62828")
        app_logger.error(f"Erreur refresh accueil async: {error_message}")
        self._finalize_refresh()

    # ── Pagination Accueil ────────────────────────────────────────────────────

    _ACC_BAR_SS = (
        "QWidget#accPagBar { background:#f1f5f9; border-top:1px solid #e2e8f0; }"
        "QPushButton { background:#1e3a5f; color:white; border-radius:4px;"
        "  padding:3px 9px; font-weight:700; font-size:12px; min-width:28px; }"
        "QPushButton:hover { background:#2a4f80; }"
        "QPushButton:disabled { background:#cbd5e1; color:#94a3b8; }"
        "QComboBox { border:1px solid #d1d5db; border-radius:4px; padding:2px 6px;"
        "  font-size:11px; background:white; color:#1e3a5f; font-weight:600; }"
        "QLabel { font-size:11px; color:#374151; font-weight:600; background:transparent; }"
    )

    def _acc_build_pagination_bar(self):
        bar = QWidget()
        bar.setObjectName("accPagBar")
        bar.setFixedHeight(38)
        bar.setStyleSheet(self._ACC_BAR_SS)

        hl = QHBoxLayout(bar)
        hl.setContentsMargins(12, 4, 12, 4)
        hl.setSpacing(6)

        hl.addWidget(QLabel("Lignes :"))
        self._acc_combo_pp = QComboBox()
        self._acc_combo_pp.setFixedWidth(58)
        for v in [10, 25, 50, 100]:
            self._acc_combo_pp.addItem(str(v), v)
        self._acc_combo_pp.setCurrentIndex(1)
        self._acc_combo_pp.currentIndexChanged.connect(self._acc_on_pp_changed)
        hl.addWidget(self._acc_combo_pp)

        hl.addStretch()

        self._acc_btn_first = QPushButton("◀◀")
        self._acc_btn_prev  = QPushButton("◀")
        self._acc_lbl_info  = QLabel("Page 1 / 1 — 0 enreg.")
        self._acc_lbl_info.setMinimumWidth(190)
        self._acc_lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acc_btn_next  = QPushButton("▶")
        self._acc_btn_last  = QPushButton("▶▶")

        for btn in (self._acc_btn_first, self._acc_btn_prev,
                    self._acc_btn_next, self._acc_btn_last):
            btn.setFixedSize(30, 26)

        self._acc_btn_first.clicked.connect(lambda: self._acc_goto_page(0))
        self._acc_btn_prev.clicked.connect(self._acc_prev_page)
        self._acc_btn_next.clicked.connect(self._acc_next_page)
        self._acc_btn_last.clicked.connect(
            lambda: self._acc_goto_page(self._acc_total_pages() - 1)
        )

        for w in (self._acc_btn_first, self._acc_btn_prev, self._acc_lbl_info,
                  self._acc_btn_next, self._acc_btn_last):
            hl.addWidget(w)

        self.ui.groupBox_2.layout().addWidget(bar, 1, 0)

    def _acc_total_pages(self) -> int:
        n = len(self._all_acc_results)
        return max(1, (n + self._acc_page_size - 1) // self._acc_page_size)

    def _acc_goto_page(self, page: int):
        total = self._acc_total_pages()
        self._acc_page = max(0, min(page, total - 1))
        self._acc_render_page()
        self._acc_update_nav()

    def _acc_prev_page(self):
        self._acc_goto_page(self._acc_page - 1)

    def _acc_next_page(self):
        self._acc_goto_page(self._acc_page + 1)

    def _acc_on_pp_changed(self):
        self._acc_page_size = self._acc_combo_pp.currentData()
        self._acc_goto_page(0)

    def _acc_update_nav(self):
        total = self._acc_total_pages()
        n = len(self._all_acc_results)
        start = self._acc_page * self._acc_page_size + 1
        end   = min((self._acc_page + 1) * self._acc_page_size, n)
        self._acc_lbl_info.setText(
            f"Page {self._acc_page + 1} / {total}  —  {n} enreg. ({start}-{end})"
        )
        self._acc_btn_first.setEnabled(self._acc_page > 0)
        self._acc_btn_prev.setEnabled(self._acc_page > 0)
        self._acc_btn_next.setEnabled(self._acc_page < total - 1)
        self._acc_btn_last.setEnabled(self._acc_page < total - 1)

    def _acc_render_page(self):
        start = self._acc_page * self._acc_page_size
        page_results = self._all_acc_results[start: start + self._acc_page_size]

        table = self.ui.tableWidget
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(0)
            for row_idx, demande in enumerate(page_results):
                table.insertRow(row_idx)

                demande_id = demande.get("id")
                nom    = (demande.get("nom") or "").upper()
                prenom = (demande.get("prenom") or "").title()
                cnps   = (demande.get("numero_cnps") or "").upper()
                service = demande.get("service")
                motif   = demande.get("motif")
                contact = demande.get("contacts")
                heure   = demande.get("heure_arrivee")
                heure_reception = demande.get("heure_reception")
                temps_attente   = demande.get("temps_attente")
                satisfaction    = demande.get("satisfaction")
                statut = demande.get("statut")

                heure_text     = self._format_time_value(heure)
                reception_text = self._format_time_value(heure_reception)

                row_items = [
                    nom or "-", prenom or "-", cnps or "-",
                    service or "-", motif or "-", contact or "-",
                    heure_text, reception_text,
                    str(temps_attente) if temps_attente is not None else "-",
                    str(satisfaction) if satisfaction is not None else "-",
                    statut or "-",
                ]
                for col_idx, text in enumerate(row_items):
                    cell = QTableWidgetItem(str(text))
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col_idx == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, demande_id)
                        cell.setData(_ROLE_IS_TRAITE, statut == "traite")
                    table.setItem(row_idx, col_idx, cell)
        finally:
            table.setUpdatesEnabled(True)

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _get_selected_demande_id(self):
        row = self.ui.tableWidget.currentRow()
        if row < 0:
            return None
        item = self.ui.tableWidget.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _restore_selection_by_id(self, demande_id):
        if not demande_id:
            return
        for row_idx in range(self.ui.tableWidget.rowCount()):
            item = self.ui.tableWidget.item(row_idx, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == demande_id:
                self.ui.tableWidget.setCurrentCell(row_idx, 0)
                return

    # ── Utilitaires de temps ──────────────────────────────────────────────────

    @staticmethod
    def _format_time_value(value):
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, str):
            return value.split("T")[1][:8] if "T" in value else value[:8]
        return str(value)

    @staticmethod
    def _parse_time_value(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                if "T" in text:
                    return datetime.fromisoformat(text.replace("Z", "+00:00")).time()
            except ValueError:
                pass
            try:
                return datetime.strptime(text[:8], "%H:%M:%S").time()
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_wait_time(arrivee_time, reception_time):
        if not arrivee_time or not reception_time:
            return None
        delta = datetime.combine(datetime.today(), reception_time) - datetime.combine(datetime.today(), arrivee_time)
        if delta.total_seconds() < 0:
            return None
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:01d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _compute_delai_objectif(wait_time):
        if not wait_time:
            return 0
        try:
            parts = str(wait_time).strip().split(":")
            if len(parts) != 3:
                return 0
            hours, minutes, seconds = map(int, parts)
            total_seconds = (hours * 3600) + (minutes * 60) + seconds
            return 1 if total_seconds < 900 else 0
        except (TypeError, ValueError):
            return 0

    # ── Traitement d'une demande ──────────────────────────────────────────────

    def open_selected_demande(self):
        row = self.ui.tableWidget.currentRow()
        if row < 0:
            QMessageBox.information(self, "Traitement", "Selectionne une ligne d'abord.")
            return

        statut_item = self.ui.tableWidget.item(row, _ModernRowDelegate._STATUS_COL)   # colonne Statut (10)
        statut_selectionne = (statut_item.text().strip().lower() if statut_item and statut_item.text() else "")
        if self.current_user_role == "accueil" and statut_selectionne == "traite":
            QMessageBox.information(
                self, "Traitement verrouille",
                "Cette ligne est deja traitee et ne peut plus etre modifiee par l'agent d'accueil.",
            )
            return

        row_id_item = self.ui.tableWidget.item(row, 0)
        if row_id_item is None:
            return
        demande_id = row_id_item.data(Qt.ItemDataRole.UserRole)
        if not demande_id:
            return

        details = db.execute_query(
            """
            SELECT d.id, d.nom, d.prenom, d.numero_cnps, d.contacts,
                   d.heure_arrivee, d.satisfaction, d.commentaire_satisfaction,
                   d.statut, s.nom AS service, m.nom AS motif
            FROM accueil_demandeaccueil d
            LEFT JOIN accueil_service s ON d.service_demande_id = s.id
            LEFT JOIN accueil_motif m ON d.motif_id = m.id
            WHERE d.id = ?
            """,
            (demande_id,),
        )
        if not details:
            QMessageBox.warning(self, "Traitement", "Demande introuvable.")
            return

        demande = details[0]
        if self.current_user_role == "accueil" and str(demande.get("statut") or "").strip().lower() == "traite":
            QMessageBox.information(
                self, "Traitement verrouille",
                "Cette ligne est deja traitee et ne peut plus etre modifiee par l'agent d'accueil.",
            )
            return

        dialog = TraitementDialog(demande, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.payload()
        heure_reception = payload["heure_reception"]
        arrivee_time = self._parse_time_value(demande.get("heure_arrivee"))
        reception_time = self._parse_time_value(heure_reception)
        temps_attente = self._format_wait_time(arrivee_time, reception_time)
        delai_objectif = self._compute_delai_objectif(temps_attente)

        modifiees = marquer_traitee(
            demande_id,
            (
                heure_reception,
                payload["satisfaction"],
                payload["commentaire_satisfaction"],
                temps_attente,
                delai_objectif,
                datetime.now().isoformat(),
            ),
            self.current_user_role,
            self.current_user_id,
        )
        if modifiees == 0:
            par = agent_du_traitement(demande_id)
            QMessageBox.information(
                self, "Traitement",
                "Cette demande a déjà été traitée" + (f" par {par}" if par else "")
                + " depuis un autre poste. La liste va être actualisée.",
            )
        self._demandes_cache.clear()
        self.load_demandes()

    # ── Chargement des données ────────────────────────────────────────────────

    def load_demandes(self, preserve_ui_state=False, silent=False):
        """Charge les demandes enregistrees par le preaccueil."""
        if self._refresh_in_progress:
            self._refresh_pending = True
            self._refresh_context = {"preserve_ui_state": preserve_ui_state, "silent": silent}
            self._set_refresh_state("• Sync en attente...", "#ef6c00")
            return

        self._refresh_in_progress = True
        self._refresh_context = {"preserve_ui_state": preserve_ui_state, "silent": silent}
        self.refresh_spinner.setVisible(True)
        self._set_refresh_state("• Synchronisation...", "#1e88e5")
        today_str = datetime.now().date().isoformat()

        cached_results = self._get_cached_results(today_str)
        if cached_results is not None:
            try:
                self._apply_demandes_results(cached_results, preserve_ui_state=preserve_ui_state, silent=silent)
            finally:
                self._finalize_refresh()
            return

        try:
            self._start_reload_worker(today_str, silent=silent)
        except Exception as e:
            self._set_refresh_state("• Erreur sync", "#c62828")
            app_logger.error(f"Erreur lancement refresh accueil: {e}")
            self._finalize_refresh()

    # ── Fermeture propre ──────────────────────────────────────────────────────

    def closeEvent(self, event):
        timer = getattr(self, "_auto_refresh_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

        thread = getattr(self, "_reload_thread", None)
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1500)

        super().closeEvent(event)
