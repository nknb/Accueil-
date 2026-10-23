"""Dashboard page — graphiques modernes adaptés pour le projet Accueil."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QMargins, QPropertyAnimation, QEasingCurve, QTimer, QDate
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QPieSeries,
    QStackedBarSeries,
    QValueAxis,
)
# QPieSeries conservé pour le graphique statut global
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QGridLayout,
    QLabel,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QGraphicsOpacityEffect,
    QPushButton,
    QDateEdit,
    QScrollArea,
    QFileDialog,
    QLineEdit,
    QMessageBox,
)
import os
import platform

from database.connection import db

_DASHBOARD_ICONS_DIR = os.path.dirname(__file__)
_CAL_ICON_DASHBOARD = os.path.join(_DASHBOARD_ICONS_DIR, "icons", "calendar.svg").replace("\\", "/")
from ui.dashboard_theme import (
    _BG_DEEP, _BG_CARD, _BG_HDR, _BORDER,
    _TXT1, _TXT2, _TXT3, _GRID,
    _C_NAVY, _C_GREEN, _C_AMBER, _C_BLUE,
    DATE_EDIT_QSS as _DATE_EDIT_QSS, BTN_QSS as _BTN_QSS,
    truncate as _truncate,
)


# ── Worker QThread ─────────────────────────────────────────────────────────────

class _DashboardWorker(QObject):
    """Charge toutes les données du dashboard dans un thread séparé.

    Signaux :
        finished(dict) — données prêtes (jamais depuis l'UI thread)
        failed(str)    — message d'erreur si la requête échoue
    """

    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, date_from: str, date_to: str) -> None:
        super().__init__()
        self._date_from = date_from
        self._date_to   = date_to

    def run(self) -> None:
        """Exécute toutes les requêtes SQL hors thread UI."""
        try:
            and_cond = "AND date(COALESCE(d.date, d.created_at)) BETWEEN ? AND ?"
            params   = (self._date_from, self._date_to)

            total_demandes = 0
            total_traite   = 0
            total_attente  = 0
            total_non_traite = 0
            services_names: list[str] = []
            services_counts: list[int] = []
            motifs_names: list[str] = []
            motifs_counts: list[int] = []
            wait_labels: list[str] = []
            wait_counts: list[int] = []
            avg_wait_min: float = 0.0
            sat_counts: list[int] = [0, 0, 0, 0, 0]   # notes 1→5
            sat_avg: float = 0.0
            sat_total: int = 0
            top_users: list[dict] = []
            dow_labels: list[str] = []
            dow_avgs:   list[float] = []

            # Statuts
            for row in db.execute_query(
                f"SELECT statut, COUNT(*) AS nb FROM accueil_demandeaccueil d WHERE 1=1 {and_cond} GROUP BY statut",
                params,
            ):
                st = str(row.get("statut") or "").strip().lower()
                nb = int(row.get("nb") or 0)
                total_demandes += nb
                if st == "traite":
                    total_traite += nb
                elif st == "en_attente":
                    total_attente += nb
                else:
                    total_non_traite += nb

            # Par service
            for row in db.execute_query(
                f"""SELECT COALESCE(s.nom, 'Non renseigné') AS service, COUNT(*) AS nb
                    FROM accueil_demandeaccueil d
                    LEFT JOIN accueil_service s ON d.service_demande_id = s.id
                    WHERE 1=1 {and_cond}
                    GROUP BY COALESCE(s.nom, 'Non renseigné') ORDER BY nb DESC LIMIT 8""",
                params,
            ):
                services_names.append(str(row.get("service") or ""))
                services_counts.append(int(row.get("nb") or 0))

            # Par motif
            for row in db.execute_query(
                f"""SELECT COALESCE(m.nom, 'Non renseigné') AS motif, COUNT(*) AS nb
                    FROM accueil_demandeaccueil d
                    LEFT JOIN accueil_motif m ON d.motif_id = m.id
                    WHERE 1=1 {and_cond}
                    GROUP BY COALESCE(m.nom, 'Non renseigné') ORDER BY nb DESC LIMIT 8""",
                params,
            ):
                motifs_names.append(str(row.get("motif") or ""))
                motifs_counts.append(int(row.get("nb") or 0))

            # Distribution temps d'attente par tranche
            _wait_sql = f"""
                SELECT
                  CASE
                    WHEN (CAST(substr(temps_attente,1,2) AS INT)*60
                          + CAST(substr(temps_attente,4,2) AS INT)) <= 15 THEN '≤ 15 min'
                    WHEN (CAST(substr(temps_attente,1,2) AS INT)*60
                          + CAST(substr(temps_attente,4,2) AS INT)) <= 30 THEN '15–30 min'
                    WHEN (CAST(substr(temps_attente,1,2) AS INT)*60
                          + CAST(substr(temps_attente,4,2) AS INT)) <= 60 THEN '30–60 min'
                    WHEN (CAST(substr(temps_attente,1,2) AS INT)*60
                          + CAST(substr(temps_attente,4,2) AS INT)) <= 90 THEN '60–90 min'
                    ELSE '> 90 min'
                  END AS tranche,
                  COUNT(*) AS nb
                FROM accueil_demandeaccueil d
                WHERE temps_attente IS NOT NULL AND temps_attente != '' {and_cond}
                GROUP BY tranche
                ORDER BY MIN(
                    CAST(substr(temps_attente,1,2) AS INT)*60
                    + CAST(substr(temps_attente,4,2) AS INT)
                )
            """
            _order = ['≤ 15 min', '15–30 min', '30–60 min', '60–90 min', '> 90 min']
            _raw_wait: dict[str, int] = {}
            for row in db.execute_query(_wait_sql, params):
                _raw_wait[str(row.get("tranche") or "")] = int(row.get("nb") or 0)
            for lbl in _order:
                wait_labels.append(lbl)
                wait_counts.append(_raw_wait.get(lbl, 0))

            # Temps d'attente moyen (en minutes)
            _avg_rows = db.execute_query(
                f"""SELECT AVG(
                        CAST(substr(temps_attente,1,2) AS INT)*60
                        + CAST(substr(temps_attente,4,2) AS INT)
                    ) AS avg_min
                    FROM accueil_demandeaccueil d
                    WHERE temps_attente IS NOT NULL AND temps_attente != '' {and_cond}""",
                params,
            )
            if _avg_rows:
                avg_wait_min = float(_avg_rows[0].get("avg_min") or 0.0)

            # Satisfaction : distribution notes 1–5 + moyenne
            for row in db.execute_query(
                f"""SELECT satisfaction, COUNT(*) AS nb
                    FROM accueil_demandeaccueil d
                    WHERE satisfaction IS NOT NULL {and_cond}
                    GROUP BY satisfaction ORDER BY satisfaction""",
                params,
            ):
                note = int(row.get("satisfaction") or 0)
                nb   = int(row.get("nb") or 0)
                if 1 <= note <= 5:
                    sat_counts[note - 1] = nb
                    sat_total += nb

            _sat_avg_rows = db.execute_query(
                f"""SELECT AVG(CAST(satisfaction AS REAL)) AS avg_sat
                    FROM accueil_demandeaccueil d
                    WHERE satisfaction IS NOT NULL {and_cond}""",
                params,
            )
            if _sat_avg_rows:
                sat_avg = float(_sat_avg_rows[0].get("avg_sat") or 0.0)

            # Moyenne de visites par jour de semaine
            # strftime('%w') : 0=Dim, 1=Lun, 2=Mar, 3=Mer, 4=Jeu, 5=Ven, 6=Sam
            _DOW_FR = {"1": "Lun", "2": "Mar", "3": "Mer", "4": "Jeu", "5": "Ven"}
            _DOW_ORDER = ["1", "2", "3", "4", "5"]  # Lun→Ven uniquement
            _dow_raw: dict[str, float] = {}
            for row in db.execute_query(
                f"""SELECT
                        strftime('%w', date(COALESCE(d.date, d.created_at))) AS dow,
                        CAST(COUNT(*) AS REAL)
                          / COUNT(DISTINCT date(COALESCE(d.date, d.created_at)))
                          AS avg_day
                    FROM accueil_demandeaccueil d
                    WHERE 1=1 {and_cond}
                    GROUP BY dow""",
                params,
            ):
                _dow_raw[str(row.get("dow") or "")] = float(row.get("avg_day") or 0.0)
            for _d in _DOW_ORDER:
                if _d in _dow_raw:
                    dow_labels.append(_DOW_FR[_d])
                    dow_avgs.append(round(_dow_raw[_d], 1))

            # Top usagers les plus fréquents
            # Clé d'identification : numero_cnps si disponible, sinon nom+prenom
            for row in db.execute_query(
                f"""SELECT
                        UPPER(TRIM(nom))                          AS nom,
                        TRIM(prenom)                              AS prenom,
                        COALESCE(NULLIF(TRIM(numero_cnps),''), '') AS cnps,
                        MAX(COALESCE(NULLIF(TRIM(contacts),''), '')) AS contact,
                        COUNT(*)                                  AS nb_visites,
                        MAX(date)                                 AS derniere_visite
                    FROM accueil_demandeaccueil d
                    WHERE 1=1 {and_cond}
                    GROUP BY
                        COALESCE(
                            NULLIF(TRIM(numero_cnps),''),
                            UPPER(TRIM(nom)) || '|' || TRIM(prenom)
                        )
                    ORDER BY nb_visites DESC""",
                params,
            ):
                top_users.append({
                    "nom":            str(row.get("nom") or ""),
                    "prenom":         str(row.get("prenom") or "").title(),
                    "cnps":           str(row.get("cnps") or ""),
                    "contact":        str(row.get("contact") or ""),
                    "nb_visites":     int(row.get("nb_visites") or 0),
                    "derniere_visite": str(row.get("derniere_visite") or ""),
                })

            self.finished.emit({
                "total_demandes":   total_demandes,
                "total_traite":     total_traite,
                "total_attente":    total_attente,
                "total_non_traite": total_non_traite,
                "services_names":   services_names,
                "services_counts":  services_counts,
                "motifs_names":     motifs_names,
                "motifs_counts":    motifs_counts,
                "wait_labels":      wait_labels,
                "wait_counts":      wait_counts,
                "avg_wait_min":     avg_wait_min,
                "sat_counts":       sat_counts,
                "sat_avg":          sat_avg,
                "sat_total":        sat_total,
                "top_users":        top_users,
                "dow_labels":       dow_labels,
                "dow_avgs":         dow_avgs,
            })

        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(exc))


# ── Fiche détaillée usager ────────────────────────────────────────────────────

class _UserDetailDialog(QDialog):
    """Fiche usager complète — 3 onglets : Vue d'ensemble · Historique · Analyse IA."""

    _AVATAR_COLORS = ["#1d4ed8", "#0891b2", "#059669", "#7c3aed", "#be185d", "#b45309"]

    # ── helpers statiques ─────────────────────────────────────────────────────
    @staticmethod
    def _avatar_color(name: str) -> str:
        idx = (ord(name[0]) if name else 0) % len(_UserDetailDialog._AVATAR_COLORS)
        return _UserDetailDialog._AVATAR_COLORS[idx]

    @staticmethod
    def _stars(avg: float) -> str:
        filled = round(avg)
        return "★" * filled + "☆" * (5 - filled)

    @staticmethod
    def _fmt_wait(minutes: float) -> str:
        h, m = divmod(int(minutes), 60)
        return f"{h}h {m:02d}min" if h else f"{m} min"

    @staticmethod
    def _kpi_card(icon: str, title: str, val: str, sub: str, clr: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{_BG_CARD}; border-radius:10px;"
            f" border:1px solid {_BORDER}; border-left:4px solid {clr}; }}"
        )
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(2)
        lt = QLabel(f"{icon}  {title}")
        lt.setStyleSheet(
            f"color:{_TXT3}; font-size:10px; font-weight:600; background:transparent; border:none;"
        )
        clr_v = "#a78bfa" if "★" in val else clr
        lv = QLabel(val)
        lv.setStyleSheet(
            f"color:{clr_v}; font-size:{'12px' if '★' in val else '18px'};"
            f" font-weight:800; background:transparent; border:none;"
        )
        box.addWidget(lt)
        box.addWidget(lv)
        if sub:
            ls = QLabel(sub)
            ls.setStyleSheet(
                f"color:{_TXT3}; font-size:9px; background:transparent; border:none;"
            )
            box.addWidget(ls)
        return card

    @staticmethod
    def _mini_bar_chart(title: str, counter, clr: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"background:{_BG_CARD}; border-radius:12px; border:1px solid {_BORDER};"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(6)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(
            f"color:{_TXT2}; font-size:11px; font-weight:700; background:transparent; border:none;"
        )
        fl.addWidget(lbl_t)
        total = sum(counter.values())
        for name, cnt in counter.most_common(6):
            pct   = cnt / total if total else 0
            bar_w = int(pct * 22)
            row   = QHBoxLayout()
            row.setSpacing(8)
            lbl_n = QLabel(_truncate(str(name), 26))
            lbl_n.setStyleSheet(
                f"color:{_TXT2}; font-size:10px; min-width:130px; background:transparent; border:none;"
            )
            lbl_b = QLabel("█" * bar_w + "░" * (22 - bar_w))
            lbl_b.setStyleSheet(
                f"color:{clr}; font-family:monospace; font-size:10px;"
                f" background:transparent; border:none;"
            )
            lbl_c = QLabel(f"{cnt}  ({pct*100:.0f}%)")
            lbl_c.setStyleSheet(
                f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
            )
            row.addWidget(lbl_n)
            row.addWidget(lbl_b, 1)
            row.addWidget(lbl_c)
            fl.addLayout(row)
        return frame

    # ── constructeur ─────────────────────────────────────────────────────────
    def __init__(self, user: dict, parent=None) -> None:
        super().__init__(parent)
        self._user = user
        self.setWindowTitle(
            f"{user.get('nom', '')} {user.get('prenom', '')} — Fiche usager"
        )
        self.setMinimumWidth(1040)
        self.setMinimumHeight(760)
        self.setStyleSheet(f"QDialog {{ background:{_BG_DEEP}; }}")
        self._stats = self._load_user_stats()
        self._build_ui()

    # ── chargement données + calculs IA ──────────────────────────────────────
    def _load_user_stats(self) -> dict:
        from collections import Counter
        from datetime import datetime, timedelta

        u = self._user
        _empty = {
            "visites": [], "nb_traite": 0, "nb_attente": 0, "nb_non_traite": 0,
            "avg_wait": 0.0, "min_wait": 0, "max_wait": 0,
            "avg_sat": 0.0, "sat_dist": {},
            "top_service": "", "top_motif": "", "svc_cnt": {}, "mot_cnt": {},
            "premiere_visite": "—", "derniere_visite": "—",
            "jours_depuis": None, "avg_interval": None,
            "jour_prefere": "—", "heure_preferee": "—",
            "tendance": "stable",
            "score_fidelite": 0, "risque_abandon": "inconnu",
            "prochaine_visite": "—", "est_en_retard": False, "profil": "—",
        }
        try:
            if u.get("cnps"):
                where = "WHERE TRIM(d.numero_cnps) = ?"
                bind  = (u["cnps"],)
            else:
                where = "WHERE UPPER(TRIM(d.nom)) = ? AND TRIM(d.prenom) = ?"
                bind  = (u["nom"], u["prenom"])

            rows = db.execute_query(
                f"""SELECT d.id, d.date, s.nom AS service, m.nom AS motif,
                           d.priorite, d.statut, d.temps_attente,
                           d.satisfaction, d.heure_arrivee, d.contacts
                    FROM accueil_demandeaccueil d
                    LEFT JOIN accueil_service s ON d.service_demande_id = s.id
                    LEFT JOIN accueil_motif   m ON d.motif_id = m.id
                    {where}
                    ORDER BY d.date DESC, d.heure_arrivee DESC""",
                bind,
            )

            # ── comptages statut ───────────────────────────────────────────
            nb_traite     = sum(1 for r in rows if (r.get("statut") or "") == "traite")
            nb_attente    = sum(1 for r in rows if (r.get("statut") or "") == "en_attente")
            nb_non_traite = sum(1 for r in rows if (r.get("statut") or "") == "non_traite")

            # ── temps d'attente ────────────────────────────────────────────
            def _to_min(t):
                if not t: return None
                try: return int(str(t)[:2]) * 60 + int(str(t)[3:5])
                except Exception: return None

            waits    = [w for w in (_to_min(r.get("temps_attente")) for r in rows) if w is not None]
            avg_wait = sum(waits) / len(waits) if waits else 0.0
            min_wait = min(waits) if waits else 0
            max_wait = max(waits) if waits else 0

            # ── satisfaction ───────────────────────────────────────────────
            sats    = [int(r["satisfaction"]) for r in rows
                       if r.get("satisfaction") and str(r["satisfaction"]).isdigit()]
            avg_sat  = sum(sats) / len(sats) if sats else 0.0
            sat_dist = Counter(sats)

            # ── services / motifs ──────────────────────────────────────────
            svc_cnt = Counter(
                r.get("service") for r in rows
                if r.get("service") and r.get("service") not in ("—", "")
            )
            mot_cnt = Counter(
                r.get("motif") for r in rows
                if r.get("motif") and r.get("motif") not in ("—", "")
            )

            # ── dates ──────────────────────────────────────────────────────
            dates_parsed = []
            for r in rows:
                try:
                    dates_parsed.append(
                        datetime.strptime(str(r.get("date") or "")[:10], "%Y-%m-%d").date()
                    )
                except Exception:
                    pass

            premiere_visite = str(min(dates_parsed)) if dates_parsed else "—"
            derniere_visite = str(max(dates_parsed)) if dates_parsed else "—"
            today           = datetime.now().date()
            jours_depuis    = (today - max(dates_parsed)).days if dates_parsed else None

            avg_interval = None
            if len(dates_parsed) >= 2:
                sd = sorted(dates_parsed)
                intervals    = [(sd[i + 1] - sd[i]).days for i in range(len(sd) - 1)]
                avg_interval = sum(intervals) / len(intervals)

            # ── préférences jour / heure ───────────────────────────────────
            _JOUR = {
                0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
                4: "Vendredi", 5: "Samedi", 6: "Dimanche",
            }
            jour_cnt  = Counter()
            heure_cnt = Counter()
            for r in rows:
                try:
                    jour_cnt[
                        datetime.strptime(str(r.get("date") or "")[:10], "%Y-%m-%d").weekday()
                    ] += 1
                except Exception:
                    pass
                h_str = str(r.get("heure_arrivee") or "")[:2]
                if h_str.isdigit():
                    heure_cnt[int(h_str)] += 1

            jour_prefere   = _JOUR.get(jour_cnt.most_common(1)[0][0], "—") if jour_cnt else "—"
            heure_preferee = f"{heure_cnt.most_common(1)[0][0]:02d}h00" if heure_cnt else "—"

            # ── tendance satisfaction (5 dernières vs 5 précédentes) ───────
            tendance = "stable"
            if len(sats) >= 6:
                r5 = sum(sats[:5]) / 5
                p5 = sum(sats[5:10]) / min(5, len(sats) - 5)
                tendance = "hausse" if r5 > p5 + 0.4 else ("baisse" if r5 < p5 - 0.4 else "stable")

            # ── IA / scoring RFM ───────────────────────────────────────────
            # R = Récence (40 pts)  F = Fréquence (40 pts)  M = Satisfaction (20 pts)
            freq_score = min(40, len(rows) * 2)
            if jours_depuis is not None and avg_interval:
                ratio         = jours_depuis / avg_interval
                recency_score = max(0, int(40 * max(0.0, 1.0 - ratio / 2.0)))
            elif jours_depuis is not None:
                recency_score = max(0, 40 - min(40, jours_depuis // 8))
            else:
                recency_score = 20
            sat_score      = int(avg_sat / 5 * 20) if avg_sat else 0
            score_fidelite = min(100, freq_score + recency_score + sat_score)

            if jours_depuis is None:
                risque_abandon = "inconnu"
            elif avg_interval and jours_depuis > avg_interval * 2.0:
                risque_abandon = "élevé"
            elif avg_interval and jours_depuis > avg_interval * 1.5:
                risque_abandon = "moyen"
            elif jours_depuis is not None and jours_depuis > 180:
                risque_abandon = "moyen"
            else:
                risque_abandon = "faible"

            prochaine_visite = "—"
            est_en_retard    = False
            if dates_parsed and avg_interval:
                nv               = max(dates_parsed) + timedelta(days=int(avg_interval))
                prochaine_visite = str(nv)
                est_en_retard    = nv < today

            profil = (
                "Usager régulier"    if len(rows) >= 10 else
                "Usager occasionnel" if len(rows) >= 5  else
                "Usager rare"        if len(rows) >= 2  else
                "Première visite"
            )

            return {
                "visites": rows, "nb_traite": nb_traite, "nb_attente": nb_attente,
                "nb_non_traite": nb_non_traite,
                "avg_wait": avg_wait, "min_wait": min_wait, "max_wait": max_wait,
                "avg_sat": avg_sat, "sat_dist": sat_dist,
                "top_service": svc_cnt.most_common(1)[0][0] if svc_cnt else "",
                "top_motif":   mot_cnt.most_common(1)[0][0] if mot_cnt else "",
                "svc_cnt": svc_cnt, "mot_cnt": mot_cnt,
                "premiere_visite": premiere_visite, "derniere_visite": derniere_visite,
                "jours_depuis": jours_depuis, "avg_interval": avg_interval,
                "jour_prefere": jour_prefere, "heure_preferee": heure_preferee,
                "tendance": tendance,
                "score_fidelite": score_fidelite, "risque_abandon": risque_abandon,
                "prochaine_visite": prochaine_visite, "est_en_retard": est_en_retard,
                "profil": profil,
            }
        except Exception:
            return _empty

    # ── construction UI principale ────────────────────────────────────────────
    def _build_ui(self) -> None:
        from PyQt6.QtWidgets import QTabWidget

        u     = self._user
        stats = self._stats

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header(u, stats))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border:none; background:{_BG_DEEP}; }}
            QTabBar::tab {{
                background:{_BG_HDR}; color:{_TXT2};
                padding:10px 24px; font-size:12px; font-weight:600;
                border:none; border-bottom:3px solid transparent; min-width:130px;
            }}
            QTabBar::tab:selected {{
                color:white; background:{_BG_CARD};
                border-bottom:3px solid {_C_NAVY};
            }}
            QTabBar::tab:hover {{ color:{_TXT1}; }}
        """)
        tabs.addTab(self._build_tab_overview(stats),
                    f"📊  Vue d'ensemble")
        tabs.addTab(self._build_tab_history(stats),
                    f"📅  Historique ({len(stats['visites'])} visites)")
        tabs.addTab(self._build_tab_ia(stats),
                    "🤖  Analyse IA")
        root.addWidget(tabs)

    # ── En-tête ───────────────────────────────────────────────────────────────
    def _build_header(self, u: dict, stats: dict) -> QFrame:
        hdr = QFrame()
        hdr.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 #0f172a, stop:0.4 {_C_NAVY}, stop:1 #1e40af); border:none;"
        )
        hdr.setFixedHeight(88)
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(14)

        initiale = (u.get("nom", "?")[0] if u.get("nom") else "?").upper()
        av_clr   = self._avatar_color(u.get("nom", ""))
        lbl_av   = QLabel(initiale)
        lbl_av.setFixedSize(54, 54)
        lbl_av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_av.setStyleSheet(
            f"background:{av_clr}; color:white; font-size:22px; font-weight:800;"
            f" border-radius:27px; border:2px solid rgba(255,255,255,0.3);"
        )
        lay.addWidget(lbl_av)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        lbl_name = QLabel(f"{u.get('nom', '')}  {u.get('prenom', '')}")
        lbl_name.setStyleSheet(
            "color:white; font-size:17px; font-weight:700; background:transparent;"
        )
        meta = []
        if u.get("cnps"):    meta.append(f"N° CNPS : {u['cnps']}")
        if u.get("contact"): meta.append(f"📞 {u['contact']}")
        meta.append(f"🏷 {stats['profil']}")
        lbl_meta = QLabel("   ·   ".join(meta))
        lbl_meta.setStyleSheet("color:#93c5fd; font-size:11px; background:transparent;")
        info_col.addWidget(lbl_name)
        info_col.addWidget(lbl_meta)
        lay.addLayout(info_col, 1)

        def _hdr_badge(top_val: str, top_lbl: str, border_clr: str,
                       val_clr: str, lbl_clr: str) -> QFrame:
            b    = QFrame()
            b.setStyleSheet(
                f"background:rgba(255,255,255,0.07); border:1px solid {border_clr};"
                f" border-radius:8px;"
            )
            bl   = QVBoxLayout(b)
            bl.setContentsMargins(12, 6, 12, 6)
            bl.setSpacing(0)
            lv   = QLabel(top_val)
            lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lv.setStyleSheet(
                f"color:{val_clr}; font-size:20px; font-weight:900;"
                f" background:transparent; border:none;"
            )
            ll   = QLabel(top_lbl)
            ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ll.setStyleSheet(
                f"color:{lbl_clr}; font-size:10px; background:transparent; border:none;"
            )
            bl.addWidget(lv)
            bl.addWidget(ll)
            return b

        lay.addWidget(_hdr_badge(
            str(u.get("nb_visites", 0)), "visites",
            "#f59e0b", "#fbbf24", "#fde68a",
        ))
        if stats["avg_sat"]:
            lay.addWidget(_hdr_badge(
                self._stars(stats["avg_sat"]), f"{stats['avg_sat']:.1f}/5",
                "#7c3aed", "#a78bfa", "#c4b5fd",
            ))
        sc     = stats["score_fidelite"]
        sc_clr = _C_GREEN if sc >= 70 else (_C_AMBER if sc >= 40 else "#ef4444")
        lay.addWidget(_hdr_badge(f"{sc}/100", "score fidélité", sc_clr, sc_clr, "#cbd5e1"))

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet(
            "QPushButton { background:rgba(239,68,68,160); color:white; border-radius:15px;"
            " font-weight:700; font-size:13px; border:none; }"
            "QPushButton:hover { background:#ef4444; }"
        )
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        lay.addWidget(btn_close)
        return hdr

    # ── Onglet 1 : Vue d'ensemble ─────────────────────────────────────────────
    def _build_tab_overview(self, stats: dict) -> QWidget:
        from PyQt6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        inner = QWidget()
        inner.setStyleSheet(f"background:{_BG_DEEP};")
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(12)

        # KPI ligne 1 — chiffres clés
        avg_w = self._fmt_wait(stats["avg_wait"]) if stats["avg_wait"] else "—"
        sat_s = self._stars(stats["avg_sat"])      if stats["avg_sat"]  else "—"
        sat_b = f"{stats['avg_sat']:.1f} / 5"     if stats["avg_sat"]  else "Aucune note"

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        for icon, title, val, sub, clr in [
            ("🗓", "Visites totales",  str(len(stats["visites"])),   "",     _C_NAVY),
            ("✅", "Traités",           str(stats["nb_traite"]),       "",     _C_GREEN),
            ("⏳", "En attente",        str(stats["nb_attente"]),      "",     _C_AMBER),
            ("❌", "Non traités",       str(stats["nb_non_traite"]),   "",     "#ef4444"),
            ("⌚", "Attente moy.",      avg_w,                         "",     _C_BLUE),
            ("⭐", "Satisfaction moy.", sat_s,                         sat_b,  "#7c3aed"),
        ]:
            row1.addWidget(self._kpi_card(icon, title, val, sub, clr))
        lay.addLayout(row1)

        # KPI ligne 2 — temporel
        jd     = stats["jours_depuis"]
        jd_str = f"{jd} jours" if jd is not None else "—"
        ai_str = f"{int(stats['avg_interval'])} jours" if stats["avg_interval"] else "—"
        jd_clr = "#ef4444" if (jd or 0) > 90 else (_C_AMBER if (jd or 0) > 30 else _C_GREEN)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        for icon, title, val, sub, clr in [
            ("📅", "1ère visite",      stats["premiere_visite"], "", _TXT2),
            ("📅", "Dernière visite",  stats["derniere_visite"],  "", _TXT2),
            ("⏱",  "Depuis dernière", jd_str,                    "", jd_clr),
            ("🔄", "Intervalle moy.", ai_str,                    "", _C_BLUE),
            ("📍", "Jour préféré",    stats["jour_prefere"],     "", _C_GREEN),
            ("🕐", "Heure préférée",  stats["heure_preferee"],   "", _C_GREEN),
        ]:
            row2.addWidget(self._kpi_card(icon, title, val, sub, clr))
        lay.addLayout(row2)

        # Barre infos : service principal · motif · attente min/max
        info_bar = QFrame()
        info_bar.setStyleSheet(
            f"background:{_BG_HDR}; border-radius:10px; border:1px solid {_BORDER};"
        )
        ib_lay = QHBoxLayout(info_bar)
        ib_lay.setContentsMargins(16, 10, 16, 10)
        ib_lay.setSpacing(24)

        def _pill(icon: str, lbl: str, val: str, clr: str) -> QFrame:
            f  = QFrame()
            f.setStyleSheet("background:transparent; border:none;")
            fl = QHBoxLayout(f)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(5)
            for text, style in [
                (icon, f"font-size:13px; color:{_TXT2};"),
                (f"{lbl} :", f"color:{_TXT3}; font-size:10px; font-weight:600;"),
                (val,  f"color:{clr}; font-size:11px; font-weight:700;"),
            ]:
                lb = QLabel(text)
                lb.setStyleSheet(f"background:transparent; border:none; {style}")
                fl.addWidget(lb)
            return f

        if stats["top_service"]:
            ib_lay.addWidget(_pill("📋", "Service principal", stats["top_service"], _C_BLUE))
        if stats["top_motif"]:
            ib_lay.addWidget(_pill("💬", "Motif principal", stats["top_motif"], _C_AMBER))
        if stats["min_wait"]:
            ib_lay.addWidget(_pill("⬇", "Attente min", self._fmt_wait(stats["min_wait"]), _C_GREEN))
        if stats["max_wait"]:
            ib_lay.addWidget(_pill("⬆", "Attente max", self._fmt_wait(stats["max_wait"]), "#ef4444"))
        ib_lay.addStretch(1)
        lay.addWidget(info_bar)

        # Distribution satisfaction
        if stats["sat_dist"]:
            sat_frame = QFrame()
            sat_frame.setStyleSheet(
                f"background:{_BG_CARD}; border-radius:10px; border:1px solid {_BORDER};"
            )
            sf_lay = QVBoxLayout(sat_frame)
            sf_lay.setContentsMargins(16, 12, 16, 12)
            sf_lay.setSpacing(7)
            lbl_st = QLabel("Répartition de la satisfaction")
            lbl_st.setStyleSheet(
                f"color:{_TXT2}; font-size:11px; font-weight:700; background:transparent; border:none;"
            )
            sf_lay.addWidget(lbl_st)
            total_sat = sum(stats["sat_dist"].values())
            for star in range(5, 0, -1):
                cnt   = stats["sat_dist"].get(star, 0)
                pct   = cnt / total_sat if total_sat else 0
                bar_w = int(pct * 20)
                clr   = _C_GREEN if star >= 4 else (_C_AMBER if star >= 3 else "#ef4444")
                sr    = QHBoxLayout()
                sr.setSpacing(8)
                l_star = QLabel("★" * star + "☆" * (5 - star))
                l_star.setStyleSheet(
                    f"color:{clr}; font-size:11px; min-width:80px; background:transparent; border:none;"
                )
                l_bar  = QLabel("█" * bar_w + "░" * (20 - bar_w))
                l_bar.setStyleSheet(
                    f"color:{clr}; font-family:monospace; font-size:10px; background:transparent; border:none;"
                )
                l_cnt  = QLabel(f"{cnt}  ({pct*100:.0f}%)")
                l_cnt.setStyleSheet(
                    f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
                )
                sr.addWidget(l_star)
                sr.addWidget(l_bar, 1)
                sr.addWidget(l_cnt)
                sf_lay.addLayout(sr)
            lay.addWidget(sat_frame)

        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    # ── Onglet 2 : Historique complet ─────────────────────────────────────────
    def _build_tab_history(self, stats: dict) -> QWidget:
        from PyQt6.QtWidgets import QTableWidget, QHeaderView

        container = QWidget()
        container.setStyleSheet(f"background:{_BG_DEEP};")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Barre recherche
        sb = QFrame()
        sb.setStyleSheet(
            f"background:{_BG_HDR}; border-bottom:1px solid {_BORDER};"
        )
        sb_lay = QHBoxLayout(sb)
        sb_lay.setContentsMargins(14, 8, 14, 8)
        sb_lay.setSpacing(8)
        lbl_ico = QLabel("🔍")
        lbl_ico.setStyleSheet("background:transparent; border:none;")
        sb_lay.addWidget(lbl_ico)
        self._hist_search = QLineEdit()
        self._hist_search.setPlaceholderText("Filtrer par date, service, motif, statut, priorité…")
        self._hist_search.setClearButtonEnabled(True)
        self._hist_search.setStyleSheet(f"""
            QLineEdit {{
                background:#0f172a; color:{_TXT1}; border:1px solid {_BORDER};
                border-radius:7px; padding:5px 10px; font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{_C_NAVY}; }}
        """)
        self._hist_search.textChanged.connect(self._filter_history)
        sb_lay.addWidget(self._hist_search)
        self._lbl_hist_count = QLabel(f"{len(stats['visites'])} visite(s)")
        self._lbl_hist_count.setStyleSheet(
            f"color:{_TXT3}; font-size:10px; min-width:90px; background:transparent; border:none;"
        )
        sb_lay.addWidget(self._lbl_hist_count)
        lay.addWidget(sb)

        # Table historique
        _H_COLS = ["Date", "Service", "Motif", "Priorité", "Statut",
                   "Attente", "Satisfaction", "Heure d'arrivée"]
        self._hist_tbl = QTableWidget(0, len(_H_COLS))
        self._hist_tbl.setHorizontalHeaderLabels(_H_COLS)
        self._hist_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hist_tbl.setAlternatingRowColors(True)
        self._hist_tbl.verticalHeader().setVisible(False)
        self._hist_tbl.setShowGrid(False)
        self._hist_tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{_BG_CARD}; alternate-background-color:#111827;
                color:{_TXT1}; border:none; font-size:11px;
            }}
            QHeaderView::section {{
                background:{_BG_HDR}; color:{_TXT2}; font-weight:700;
                font-size:10px; border:none;
                border-bottom:2px solid {_C_NAVY}; padding:6px 10px;
            }}
            QTableWidget::item {{
                padding:5px 10px; border-bottom:1px solid {_BORDER};
            }}
            QTableWidget::item:selected {{ background:{_C_NAVY}; color:white; }}
        """)
        h = self._hist_tbl.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for ci in range(3, len(_H_COLS)):
            h.setSectionResizeMode(ci, QHeaderView.ResizeMode.ResizeToContents)

        self._hist_all_rows = stats["visites"]
        self._fill_history(stats["visites"])
        lay.addWidget(self._hist_tbl)
        return container

    def _fill_history(self, rows: list) -> None:
        from PyQt6.QtWidgets import QTableWidgetItem

        _SI = {"traite": "✅ Traité", "en_attente": "⏳ En attente", "non_traite": "❌ Non traité"}
        _SC = {"traite": _C_GREEN,    "en_attente": _C_AMBER,         "non_traite": "#ef4444"}
        _PI = {"haute": "🔴 Haute",   "moyenne": "🟡 Moyenne",        "normale": "🟢 Normale"}
        _PC = {"haute": "#ef4444",    "moyenne": _C_AMBER,             "normale": _C_GREEN}

        self._hist_tbl.setRowCount(len(rows))
        for r, v in enumerate(rows):
            self._hist_tbl.setRowHeight(r, 36)
            sat_raw  = v.get("satisfaction") or ""
            sat_disp = (
                "★" * int(sat_raw) + "☆" * (5 - int(sat_raw))
                if str(sat_raw).isdigit() else "—"
            )
            statut   = str(v.get("statut")   or "")
            priorite = str(v.get("priorite") or "")
            row_vals = [
                (str(v.get("date", ""))[:10],               Qt.AlignmentFlag.AlignCenter),
                (v.get("service", "—"),                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                (v.get("motif",   "—"),                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                (_PI.get(priorite, priorite or "—"),        Qt.AlignmentFlag.AlignCenter),
                (_SI.get(statut,   statut   or "—"),        Qt.AlignmentFlag.AlignCenter),
                (str(v.get("temps_attente") or "—"),        Qt.AlignmentFlag.AlignCenter),
                (sat_disp,                                  Qt.AlignmentFlag.AlignCenter),
                (str(v.get("heure_arrivee") or "—"),        Qt.AlignmentFlag.AlignCenter),
            ]
            for c, (val, align) in enumerate(row_vals):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(int(align))
                if c == 4: item.setForeground(QColor(_SC.get(statut,   _TXT2)))
                if c == 3: item.setForeground(QColor(_PC.get(priorite, _TXT2)))
                if c == 6 and str(sat_raw).isdigit():
                    ns = int(sat_raw)
                    item.setForeground(
                        QColor(_C_GREEN if ns >= 4 else (_C_AMBER if ns >= 3 else "#ef4444"))
                    )
                self._hist_tbl.setItem(r, c, item)
        self._lbl_hist_count.setText(f"{len(rows)} visite(s)")

    def _filter_history(self, text: str) -> None:
        q = text.strip().lower()
        if not q:
            self._fill_history(self._hist_all_rows)
            return
        filtered = [
            r for r in self._hist_all_rows
            if q in " ".join(str(v) for v in r.values() if v is not None).lower()
        ]
        self._fill_history(filtered)

    # ── Onglet 3 : Analyse IA ─────────────────────────────────────────────────
    def _build_tab_ia(self, stats: dict) -> QWidget:
        from PyQt6.QtWidgets import QScrollArea, QProgressBar

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        inner = QWidget()
        inner.setStyleSheet(f"background:{_BG_DEEP};")
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(14)

        # ── Score de fidélité RFM ──────────────────────────────────────────
        sc     = stats["score_fidelite"]
        sc_clr = _C_GREEN if sc >= 70 else (_C_AMBER if sc >= 40 else "#ef4444")
        sc_lbl = ("Excellent" if sc >= 80 else "Bon" if sc >= 60
                  else "Moyen" if sc >= 40 else "Faible")

        fid = QFrame()
        fid.setStyleSheet(
            f"background:{_BG_CARD}; border-radius:12px;"
            f" border:1px solid {_BORDER}; border-left:4px solid {sc_clr};"
        )
        fid_lay = QVBoxLayout(fid)
        fid_lay.setContentsMargins(16, 14, 16, 14)
        fid_lay.setSpacing(10)

        top_row = QHBoxLayout()
        lbl_fid_t = QLabel("Score de fidélité  —  modèle RFM")
        lbl_fid_t.setStyleSheet(
            f"color:{_TXT1}; font-size:13px; font-weight:700; background:transparent; border:none;"
        )
        lbl_fid_d = QLabel("Récence · Fréquence · Satisfaction")
        lbl_fid_d.setStyleSheet(
            f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
        )
        lbl_fid_s = QLabel(f"{sc} / 100  —  {sc_lbl}")
        lbl_fid_s.setStyleSheet(
            f"color:{sc_clr}; font-size:14px; font-weight:800; background:transparent; border:none;"
        )
        top_row.addWidget(lbl_fid_t)
        top_row.addWidget(lbl_fid_d)
        top_row.addStretch(1)
        top_row.addWidget(lbl_fid_s)
        fid_lay.addLayout(top_row)

        pb_main = QProgressBar()
        pb_main.setRange(0, 100)
        pb_main.setValue(sc)
        pb_main.setTextVisible(False)
        pb_main.setFixedHeight(14)
        pb_main.setStyleSheet(f"""
            QProgressBar {{ background:#1e293b; border-radius:7px; border:none; }}
            QProgressBar::chunk {{ background:{sc_clr}; border-radius:7px; }}
        """)
        fid_lay.addWidget(pb_main)

        # Composantes RFM
        freq_sc = min(40, len(stats["visites"]) * 2)
        sat_sc  = int(stats["avg_sat"] / 5 * 20) if stats["avg_sat"] else 0
        rec_sc  = max(0, sc - freq_sc - sat_sc)
        comp_row = QHBoxLayout()
        comp_row.setSpacing(8)
        for lbl_c, val_c, mx_c, clr_c in [
            ("Fréquence (F)", freq_sc, 40, _C_BLUE),
            ("Récence (R)",   rec_sc,  40, _C_GREEN),
            ("Satisfaction",  sat_sc,  20, "#7c3aed"),
        ]:
            cf  = QFrame()
            cf.setStyleSheet(f"background:{_BG_HDR}; border-radius:8px; border:none;")
            cfl = QVBoxLayout(cf)
            cfl.setContentsMargins(10, 8, 10, 8)
            cfl.setSpacing(4)
            lbl_comp = QLabel(lbl_c)
            lbl_comp.setStyleSheet(
                f"color:{_TXT3}; font-size:9px; background:transparent; border:none;"
            )
            pb2 = QProgressBar()
            pb2.setRange(0, mx_c)
            pb2.setValue(max(0, val_c))
            pb2.setTextVisible(False)
            pb2.setFixedHeight(8)
            pb2.setStyleSheet(f"""
                QProgressBar {{ background:#0f172a; border-radius:4px; border:none; }}
                QProgressBar::chunk {{ background:{clr_c}; border-radius:4px; }}
            """)
            lbl_val = QLabel(f"{max(0, val_c)} / {mx_c}")
            lbl_val.setStyleSheet(
                f"color:{clr_c}; font-size:10px; font-weight:700; background:transparent; border:none;"
            )
            cfl.addWidget(lbl_comp)
            cfl.addWidget(pb2)
            cfl.addWidget(lbl_val)
            comp_row.addWidget(cf)
        fid_lay.addLayout(comp_row)
        lay.addWidget(fid)

        # ── Risque d'abandon + Prochaine visite ────────────────────────────
        risk_row = QHBoxLayout()
        risk_row.setSpacing(10)

        risque = stats["risque_abandon"]
        r_clr  = {"faible": _C_GREEN, "moyen": _C_AMBER,
                   "élevé": "#ef4444", "inconnu": _TXT3}[risque]
        r_icon = {"faible": "🟢", "moyen": "🟡",
                   "élevé": "🔴", "inconnu": "⚪"}[risque]
        r_desc = {
            "faible":  "L'usager revient régulièrement. Aucune action requise.",
            "moyen":   "Retard par rapport à son intervalle habituel. Surveillance recommandée.",
            "élevé":   "Absence prolongée détectée. Risque de non-retour élevé.",
            "inconnu": "Données insuffisantes pour évaluer le risque.",
        }[risque]

        risk_fr = QFrame()
        risk_fr.setStyleSheet(
            f"background:{_BG_CARD}; border-radius:12px; border:1px solid {r_clr};"
        )
        rfl = QVBoxLayout(risk_fr)
        rfl.setContentsMargins(16, 12, 16, 12)
        rfl.setSpacing(6)
        lbl_rt = QLabel(f"{r_icon}  Risque d'abandon : {risque.upper()}")
        lbl_rt.setStyleSheet(
            f"color:{r_clr}; font-size:13px; font-weight:700; background:transparent; border:none;"
        )
        lbl_rd = QLabel(r_desc)
        lbl_rd.setStyleSheet(
            f"color:{_TXT2}; font-size:11px; background:transparent; border:none;"
        )
        lbl_rd.setWordWrap(True)
        rfl.addWidget(lbl_rt)
        rfl.addWidget(lbl_rd)
        risk_row.addWidget(risk_fr, 1)

        nv_fr  = QFrame()
        nv_fr.setStyleSheet(
            f"background:{_BG_CARD}; border-radius:12px; border:1px solid {_BORDER};"
        )
        nvl = QVBoxLayout(nv_fr)
        nvl.setContentsMargins(16, 12, 16, 12)
        nvl.setSpacing(4)
        lbl_nvt = QLabel("Prochaine visite estimée")
        lbl_nvt.setStyleSheet(
            f"color:{_TXT3}; font-size:11px; font-weight:600; background:transparent; border:none;"
        )
        nv_clr  = "#ef4444" if stats.get("est_en_retard") else _C_BLUE
        lbl_nvv = QLabel(stats["prochaine_visite"])
        lbl_nvv.setStyleSheet(
            f"color:{nv_clr}; font-size:18px; font-weight:800; background:transparent; border:none;"
        )
        nv_note = (
            "En retard / date dépassée"
            if stats.get("est_en_retard") else
            ("Basé sur l'intervalle moyen entre visites"
             if stats["prochaine_visite"] != "—" else
             "Données insuffisantes (moins de 2 visites)")
        )
        lbl_nvn = QLabel(nv_note)
        lbl_nvn.setStyleSheet(
            f"color:{_TXT3}; font-size:9px; font-style:italic; background:transparent; border:none;"
        )
        nvl.addWidget(lbl_nvt)
        nvl.addWidget(lbl_nvv)
        nvl.addWidget(lbl_nvn)
        risk_row.addWidget(nv_fr)
        lay.addLayout(risk_row)

        # ── Tendance satisfaction ──────────────────────────────────────────
        tend      = stats["tendance"]
        tend_icon = {"hausse": "📈", "baisse": "📉", "stable": "➡️"}[tend]
        tend_clr  = {"hausse": _C_GREEN, "baisse": "#ef4444", "stable": _C_AMBER}[tend]
        tend_desc = {
            "hausse": "La satisfaction s'améliore sur les 5 dernières visites.",
            "baisse": "La satisfaction baisse. Vigilance sur la qualité du service.",
            "stable": "La satisfaction reste stable dans le temps.",
        }[tend]

        tend_fr = QFrame()
        tend_fr.setStyleSheet(
            f"background:{_BG_CARD}; border-radius:12px;"
            f" border:1px solid {_BORDER}; border-left:4px solid {tend_clr};"
        )
        tfl = QHBoxLayout(tend_fr)
        tfl.setContentsMargins(16, 12, 16, 12)
        tfl.setSpacing(12)
        lbl_ti = QLabel(tend_icon)
        lbl_ti.setStyleSheet("font-size:26px; background:transparent; border:none;")
        t_col = QVBoxLayout()
        t_col.setSpacing(2)
        lbl_tt = QLabel("Tendance satisfaction (5 dernières visites)")
        lbl_tt.setStyleSheet(
            f"color:{_TXT2}; font-size:11px; font-weight:700; background:transparent; border:none;"
        )
        lbl_tv = QLabel(tend.capitalize())
        lbl_tv.setStyleSheet(
            f"color:{tend_clr}; font-size:14px; font-weight:800; background:transparent; border:none;"
        )
        lbl_td = QLabel(tend_desc)
        lbl_td.setStyleSheet(
            f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
        )
        lbl_td.setWordWrap(True)
        t_col.addWidget(lbl_tt)
        t_col.addWidget(lbl_tv)
        t_col.addWidget(lbl_td)
        tfl.addWidget(lbl_ti)
        tfl.addLayout(t_col, 1)
        lay.addWidget(tend_fr)

        # ── Répartition services / motifs ──────────────────────────────────
        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        if stats["svc_cnt"]:
            charts_row.addWidget(
                self._mini_bar_chart("Répartition par service", stats["svc_cnt"], _C_BLUE)
            )
        if stats["mot_cnt"]:
            charts_row.addWidget(
                self._mini_bar_chart("Répartition par motif", stats["mot_cnt"], _C_AMBER)
            )
        if stats["svc_cnt"] or stats["mot_cnt"]:
            lay.addLayout(charts_row)

        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll


# ── Tableau usagers fréquents ─────────────────────────────────────────────────

class _TopUsersFrame(QFrame):
    """Tableau paginé des usagers les plus fréquents — design amélioré.

    Utilise des attributs d'instance pour éviter la collecte GC des wrappers
    PyQt6 (bus error avec closures).
    """

    _PAGE_SIZE = 15
    _MEDALS    = {0: ("#f59e0b", "🥇"), 1: ("#94a3b8", "🥈"), 2: ("#cd7f32", "🥉")}
    _AV_COLORS = ["#1d4ed8", "#0891b2", "#059669", "#7c3aed", "#be185d", "#b45309"]

    def __init__(self, users: list[dict], parent=None) -> None:
        super().__init__(parent)
        self._all_users  = users          # liste complète (jamais modifiée)
        self._users      = users          # liste courante (filtrée ou complète)
        self._page       = 0
        self._max_visits = users[0]["nb_visites"] if users else 1
        self._total_pg   = max(1, -(-len(users) // self._PAGE_SIZE))

        from PyQt6.QtWidgets import QTableWidget, QHeaderView, QSizePolicy

        self.setStyleSheet(f"""
            QFrame {{
                background:{_BG_CARD};
                border:1px solid {_BORDER};
                border-radius:14px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── En-tête carte ─────────────────────────────────────────────────────
        hdr_card = QFrame()
        hdr_card.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 #0f172a, stop:0.5 #1e3a5f, stop:1 #0f172a);"
            f"border-radius:14px 14px 0 0; border:none;"
        )
        hdr_card.setFixedHeight(54)
        hdr_lay = QHBoxLayout(hdr_card)
        hdr_lay.setContentsMargins(18, 10, 18, 10)
        hdr_lay.setSpacing(12)

        lbl_title = QLabel("🏆   Usagers les plus fréquents")
        lbl_title.setStyleSheet(
            "color:white; font-size:14px; font-weight:800; background:transparent;"
        )
        hdr_lay.addWidget(lbl_title)
        hdr_lay.addStretch(1)

        # Badge compteur total
        badge_total = QLabel(f"  {len(users)} usagers  ")
        badge_total.setStyleSheet(
            "background:rgba(255,255,255,0.12); color:#93c5fd; font-size:11px;"
            " font-weight:700; border-radius:10px; padding:2px 8px; border:none;"
        )
        hdr_lay.addWidget(badge_total)

        # Hint clic
        hint = QLabel("  👆 Cliquer sur une ligne pour voir le détail")
        hint.setStyleSheet(
            "color:#475569; font-size:10px; font-style:italic; background:transparent; border:none;"
        )
        hdr_lay.addWidget(hint)
        root.addWidget(hdr_card)

        # ── Barre de recherche ────────────────────────────────────────────────
        search_bar = QFrame()
        search_bar.setStyleSheet(
            f"background:{_BG_HDR}; border:none; border-bottom:1px solid {_BORDER};"
        )
        search_lay = QHBoxLayout(search_bar)
        search_lay.setContentsMargins(14, 8, 14, 8)
        search_lay.setSpacing(8)

        lbl_search_icon = QLabel("🔍")
        lbl_search_icon.setStyleSheet("background:transparent; border:none; font-size:13px;")
        search_lay.addWidget(lbl_search_icon)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Rechercher par nom, prénom, N° CNPS ou contact…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setStyleSheet(f"""
            QLineEdit {{
                background:#0f172a; color:{_TXT1}; border:1px solid {_BORDER};
                border-radius:7px; padding:5px 10px; font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{_C_NAVY}; }}
        """)
        self._search_box.textChanged.connect(self._on_search)
        search_lay.addWidget(self._search_box)

        self._lbl_search_result = QLabel("")
        self._lbl_search_result.setStyleSheet(
            f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
        )
        search_lay.addWidget(self._lbl_search_result)
        root.addWidget(search_bar)

        if not users:
            lbl_empty = QLabel("Aucune donnée disponible sur cette période.")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setStyleSheet(
                f"color:{_TXT3}; font-size:12px; padding:40px; background:transparent;"
            )
            root.addWidget(lbl_empty)
            # init stubs so attrs exist
            self._tbl = None; self._lbl_page = None
            self._btn_first = self._btn_prev = self._btn_next = self._btn_last = None
            return

        # ── Tableau ───────────────────────────────────────────────────────────
        _COLS = ["#", "Nom", "Prénom", "N° CNPS", "Contact", "Visites ▼", "Dernière visite"]
        self._tbl = QTableWidget(0, len(_COLS))
        self._tbl.setHorizontalHeaderLabels(_COLS)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setShowGrid(False)
        self._tbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._tbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background-color:{_BG_CARD};
                alternate-background-color:#111827;
                color:{_TXT1}; border:none; font-size:12px;
            }}
            QHeaderView::section {{
                background-color:{_BG_HDR}; color:{_TXT2}; font-weight:700;
                font-size:11px; border:none;
                border-bottom:2px solid {_C_NAVY}; padding:8px 12px;
            }}
            QTableWidget::item {{
                padding:6px 12px; border-bottom:1px solid {_BORDER};
            }}
            QTableWidget::item:selected {{ background-color:{_C_NAVY}; color:white; }}
            QTableWidget::item:hover    {{ background-color:#1e3a5f55; }}
        """)

        h = self._tbl.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_hdr = h

        self._tbl.cellClicked.connect(self._on_row_clicked)
        root.addWidget(self._tbl)

        # ── Barre pagination ──────────────────────────────────────────────────
        nav_bar = QFrame()
        nav_bar.setStyleSheet(
            f"background:{_BG_HDR}; border-top:1px solid {_BORDER};"
            f"border-radius:0 0 14px 14px;"
        )
        nav_hbox = QHBoxLayout(nav_bar)
        nav_hbox.setContentsMargins(14, 8, 14, 8)
        nav_hbox.setSpacing(6)

        lbl_info = QLabel(f"Total : {len(users)} usagers  ·  {self._PAGE_SIZE} par page")
        lbl_info.setStyleSheet(f"color:{_TXT3}; font-size:10px; background:transparent; border:none;")
        nav_hbox.addWidget(lbl_info)
        nav_hbox.addStretch(1)

        _BTN_S = (
            "QPushButton { background:#1e3a5f; color:#cbd5e1; border-radius:6px;"
            " padding:5px 12px; font-size:12px; font-weight:700; border:none; min-width:32px; }"
            "QPushButton:hover { background:#2563eb; color:white; }"
            "QPushButton:disabled { background:#1a2535; color:#334155; }"
        )
        self._btn_first = QPushButton("«")
        self._btn_prev  = QPushButton("‹  Préc.")
        self._lbl_page  = QLabel()
        self._lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_page.setMinimumWidth(110)
        self._lbl_page.setStyleSheet(
            f"color:{_TXT1}; font-size:11px; font-weight:700; background:transparent; border:none;"
        )
        self._btn_next  = QPushButton("Suiv.  ›")
        self._btn_last  = QPushButton("»")

        for btn in (self._btn_first, self._btn_prev, self._btn_next, self._btn_last):
            btn.setStyleSheet(_BTN_S)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._btn_first.clicked.connect(self._go_first)
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next.clicked.connect(self._go_next)
        self._btn_last.clicked.connect(self._go_last)

        nav_hbox.addWidget(self._btn_first)
        nav_hbox.addWidget(self._btn_prev)
        nav_hbox.addWidget(self._lbl_page)
        nav_hbox.addWidget(self._btn_next)
        nav_hbox.addWidget(self._btn_last)
        root.addWidget(nav_bar)

        self._render_page(0)

    # ── recherche ─────────────────────────────────────────────────────────────
    def _on_search(self, text: str) -> None:
        q = text.strip().lower()
        if q:
            self._users = [
                u for u in self._all_users
                if q in (u.get("nom") or "").lower()
                or q in (u.get("prenom") or "").lower()
                or q in (u.get("cnps") or "").lower()
                or q in (u.get("contact") or "").lower()
            ]
            n = len(self._users)
            self._lbl_search_result.setText(
                f"{n} résultat{'s' if n > 1 else ''}" if n else "Aucun résultat"
            )
        else:
            self._users = self._all_users
            self._lbl_search_result.setText("")

        self._total_pg = max(1, -(-len(self._users) // self._PAGE_SIZE))
        self._render_page(0)

    # ── navigation ────────────────────────────────────────────────────────────
    def _go_first(self) -> None: self._render_page(0)
    def _go_prev(self)  -> None: self._render_page(max(0, self._page - 1))
    def _go_next(self)  -> None: self._render_page(min(self._total_pg - 1, self._page + 1))
    def _go_last(self)  -> None: self._render_page(self._total_pg - 1)

    # ── rendu ─────────────────────────────────────────────────────────────────
    def _render_page(self, page: int) -> None:
        from PyQt6.QtWidgets import QTableWidgetItem
        if self._tbl is None:
            return

        self._page = page
        start  = page * self._PAGE_SIZE
        chunk  = self._users[start: start + self._PAGE_SIZE]
        mx     = self._max_visits or 1

        self._tbl.setRowCount(len(chunk))
        for r, u in enumerate(chunk):
            self._tbl.setRowHeight(r, 38)
            global_rank = start + r
            medal_clr, medal = self._MEDALS.get(global_rank, (_TXT2, ""))
            rank_txt = f"{medal} {global_rank + 1}" if medal else str(global_rank + 1)

            nb      = int(u.get("nb_visites", 0))
            bar_w   = int(nb / mx * 14)
            bar_txt = f"{'█' * bar_w}{'░' * (14 - bar_w)}  {nb}"

            # Couleur barre selon intensité
            intensity = nb / mx
            bar_clr = _C_GREEN if intensity >= 0.8 else (_C_AMBER if intensity >= 0.4 else _TXT2)

            row_data = [
                (rank_txt,             Qt.AlignmentFlag.AlignCenter),
                (u.get("nom", ""),     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                (u.get("prenom", ""),  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                (u.get("cnps") or "—", Qt.AlignmentFlag.AlignCenter),
                (u.get("contact") or "—", Qt.AlignmentFlag.AlignCenter),
                (bar_txt,              Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                (u.get("derniere_visite", ""), Qt.AlignmentFlag.AlignCenter),
            ]
            for c, (val, align) in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(int(align))
                # Top 3 en gras
                if global_rank < 3:
                    f = item.font(); f.setBold(True); item.setFont(f)
                    if c == 0:
                        item.setForeground(QColor(medal_clr))
                # Barre visites colorée
                if c == 5:
                    item.setForeground(QColor(bar_clr))
                self._tbl.setItem(r, c, item)

        # Hauteur fixe = nb lignes × 38 + header
        hdr_h = self._tbl_hdr.height()
        self._tbl.setFixedHeight(38 * len(chunk) + hdr_h + 2)

        self._lbl_page.setText(f"Page  {page + 1}  /  {self._total_pg}")
        self._btn_first.setEnabled(page > 0)
        self._btn_prev.setEnabled(page > 0)
        self._btn_next.setEnabled(page < self._total_pg - 1)
        self._btn_last.setEnabled(page < self._total_pg - 1)

    # ── clic ligne ────────────────────────────────────────────────────────────
    def _on_row_clicked(self, row: int, _col: int = 0) -> None:
        idx = self._page * self._PAGE_SIZE + row
        if 0 <= idx < len(self._users):
            _UserDetailDialog(self._users[idx], parent=self).exec()


# ── Gestionnaire de graphiques ────────────────────────────────────────────────

class _ChartHandler:
    """Construit et rafraîchit les graphiques du Dashboard Accueil."""

    def __init__(self, layout: QGridLayout) -> None:
        self._layout = layout
        self._responsive_label_specs: list[tuple[QLabel, int]] = []
        self._animations: list = []

        _y = QDate.currentDate().year()
        self._filter_date_from: str = f"{_y}-01-01"
        self._filter_date_to: str   = f"{_y}-12-31"

        self._loading_label: QLabel | None = None
        self._worker: _DashboardWorker | None = None
        self._thread: QThread | None = None
        self._last_data: dict | None = None

        # Refresh silencieux
        self._bg_worker: _DashboardWorker | None = None
        self._bg_thread: QThread | None = None
        self._bg_retry: int = 0
        self._refreshing: bool = False          # verrou anti double-refresh
        self._lbl_sync: QLabel | None = None    # indicateur "⟳ HH:MM" dans la barre filtre
        self._pulse_timer: QTimer | None = None

    def refresh(self, *, silent: bool = False) -> None:
        """Déclenche un rechargement des données.

        silent=False (défaut, appels manuels/filtre) : affiche l'écran de chargement.
        silent=True  (appels auto-timer)              : garde les graphiques existants,
                     met à jour discrètement sans clignotement.
        """
        if self._refreshing:
            return   # un refresh est déjà en cours, on ignore
        self._refreshing = True
        self._bg_retry = 0

        if silent and self._last_data is not None:
            self._set_sync_state("loading")
            self._start_bg_worker()
        else:
            self._animations.clear()
            self._show_loading()
            self._start_worker()

    # ── Indicateur de synchronisation ────────────────────────────────────────

    def _set_sync_state(self, state: str) -> None:
        """Met à jour le petit indicateur dans la barre de filtres.

        state : 'loading' | 'ok' | 'error'
        """
        if self._lbl_sync is None:
            return
        from PyQt6.QtCore import QTime
        now = QTime.currentTime().toString("HH:mm")
        if state == "loading":
            self._lbl_sync.setText("  ⟳ actualisation…")
            self._lbl_sync.setStyleSheet(
                f"color:{_TXT3}; font-size:10px; font-style:italic; background:transparent; border:none;"
            )
            # Pulse discret : clignotement léger via opacité
            self._pulse_timer = QTimer()
            self._pulse_timer.setInterval(600)
            self._pulse_timer.timeout.connect(self._pulse_sync)
            self._pulse_timer.start()
        elif state == "ok":
            if self._pulse_timer:
                self._pulse_timer.stop()
                self._pulse_timer = None
            self._lbl_sync.setText(f"  ✓ {now}")
            self._lbl_sync.setStyleSheet(
                f"color:#22c55e; font-size:10px; font-weight:600; background:transparent; border:none;"
            )
            # Revient à gris après 4s
            QTimer.singleShot(4000, lambda: self._lbl_sync.setStyleSheet(
                f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
            ) if self._lbl_sync else None)
        elif state == "error":
            if self._pulse_timer:
                self._pulse_timer.stop()
                self._pulse_timer = None
            self._lbl_sync.setText(f"  ⚠ erreur {now}")
            self._lbl_sync.setStyleSheet(
                "color:#f87171; font-size:10px; background:transparent; border:none;"
            )

    def _pulse_sync(self) -> None:
        """Alterne l'opacité du label pour simuler un clignotement discret."""
        if self._lbl_sync is None:
            return
        current = self._lbl_sync.styleSheet()
        if "opacity:0.3" in current:
            self._lbl_sync.setStyleSheet(current.replace("opacity:0.3", "opacity:1"))
        else:
            self._lbl_sync.setStyleSheet(current + " opacity:0.3;")

    # ── Chargement initial (avec écran de chargement) ─────────────────────────

    def _show_loading(self) -> None:
        """Vide le layout et affiche un spinner textuel — pour le premier chargement."""
        layout = self._layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._loading_label = QLabel("⟳  Chargement des données…")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(
            f"color:{_TXT2}; font-size:14px; background:transparent;"
        )
        layout.addWidget(self._loading_label, 0, 0, 1, 5)

    def _is_thread_running(self) -> bool:
        if self._thread is None:
            return False
        try:
            return self._thread.isRunning()
        except RuntimeError:
            self._thread = None
            return False

    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None:
            try:
                thread.deleteLater()
            except RuntimeError:
                pass

    def _start_worker(self) -> None:
        """Démarre le worker visible (premier chargement ou changement de filtre)."""
        if self._is_thread_running():
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None

        thread = QThread()
        self._thread = thread
        self._worker = _DashboardWorker(self._filter_date_from, self._filter_date_to)
        self._worker.moveToThread(thread)

        thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.failed.connect(self._on_data_failed)
        self._worker.finished.connect(thread.quit)
        self._worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        thread.start()

    def _on_data_ready(self, data: dict) -> None:
        """Callback — données reçues → rebuild complet."""
        self._refreshing = False
        self._last_data = data
        self._build_charts(data)
        self._set_sync_state("ok")

    def _on_data_failed(self, error_msg: str) -> None:
        """Callback — erreur chargement initial → affiche le message."""
        self._refreshing = False
        self._set_sync_state("error")
        layout = self._layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        err_label = QLabel(f"⚠  Erreur de chargement :\n{error_msg}")
        err_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        err_label.setStyleSheet("color:#ef4444; font-size:13px; background:transparent;")
        err_label.setWordWrap(True)
        layout.addWidget(err_label, 0, 0, 1, 5)

    # ── Refresh silencieux (auto-timer) ───────────────────────────────────────

    def _is_bg_thread_running(self) -> bool:
        if self._bg_thread is None:
            return False
        try:
            return self._bg_thread.isRunning()
        except RuntimeError:
            self._bg_thread = None
            return False

    def _start_bg_worker(self) -> None:
        """Lance le worker en arrière-plan sans toucher à l'UI."""
        if self._is_bg_thread_running():
            return   # déjà en cours

        thread = QThread()
        self._bg_thread = thread
        self._bg_worker = _DashboardWorker(self._filter_date_from, self._filter_date_to)
        self._bg_worker.moveToThread(thread)

        thread.started.connect(self._bg_worker.run)
        self._bg_worker.finished.connect(self._on_bg_data_ready)
        self._bg_worker.failed.connect(self._on_bg_data_failed)
        self._bg_worker.finished.connect(thread.quit)
        self._bg_worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_bg_thread_finished)
        thread.start()

    def _on_bg_thread_finished(self) -> None:
        thread = self._bg_thread
        self._bg_thread = None
        if thread is not None:
            try:
                thread.deleteLater()
            except RuntimeError:
                pass

    def _on_bg_data_ready(self, data: dict) -> None:
        """Refresh silencieux réussi — on met à jour sans vider les graphiques."""
        self._refreshing = False
        self._bg_retry = 0
        self._last_data = data
        # Rebuild discret : les widgets existants sont remplacés mais sans écran blanc
        self._animations.clear()
        self._build_charts(data)
        self._set_sync_state("ok")

    def _on_bg_data_failed(self, error_msg: str) -> None:
        """Refresh silencieux échoué — retry jusqu'à 3 fois, puis abandon silencieux."""
        self._bg_retry += 1
        if self._bg_retry < 3:
            # Réessayer dans 15s
            QTimer.singleShot(15_000, self._start_bg_worker)
        else:
            self._refreshing = False
            self._bg_retry = 0
            self._set_sync_state("error")

    # ── Filtres de dates ──────────────────────────────────────────────────────

    def _make_filter_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background-color: {_BG_HDR}; border-radius: 10px; border: 1px solid {_BORDER}; }}"
            f"QLabel {{ color: {_TXT2}; font-size: 11px; font-weight: 600;"
            f"  background: transparent; border: none; }}"
        )
        bar.setMinimumHeight(46)

        hbox = QHBoxLayout(bar)
        hbox.setContentsMargins(16, 8, 16, 8)
        hbox.setSpacing(10)

        icon = QLabel("\U0001f5d3")
        icon.setStyleSheet("font-size: 14px; border: none; background: transparent;")
        hbox.addWidget(icon)

        def _make_de(val: str) -> QDateEdit:
            de = QDateEdit()
            de.setCalendarPopup(True)
            de.setDisplayFormat("dd/MM/yyyy")
            de.setStyleSheet(
                _DATE_EDIT_QSS +
                f"QDateEdit::drop-down {{ image: url({_CAL_ICON_DASHBOARD}); width: 16px; height: 16px; }}"
            )
            de.setDate(QDate.fromString(val, "yyyy-MM-dd"))
            return de

        hbox.addWidget(QLabel("Du :"))
        self._de_from = _make_de(self._filter_date_from)
        self._de_from.dateChanged.connect(lambda d: self._on_date_changed("from", d))
        hbox.addWidget(self._de_from)

        hbox.addWidget(QLabel("  Au :"))
        self._de_to = _make_de(self._filter_date_to)
        self._de_to.dateChanged.connect(lambda d: self._on_date_changed("to", d))
        hbox.addWidget(self._de_to)

        hbox.addStretch(1)

        reset_btn = QPushButton("↺  Réinitialiser")
        reset_btn.setStyleSheet(_BTN_QSS)
        reset_btn.clicked.connect(self._on_filter_reset)
        hbox.addWidget(reset_btn)

        export_btn = QPushButton("📥  Exporter Excel")
        export_btn.setStyleSheet(
            "QPushButton { background: #16a34a; color: white; border-radius: 6px;"
            " padding: 5px 14px; font-size: 11px; font-weight: 700; border: none; }"
            "QPushButton:hover { background: #15803d; }"
            "QPushButton:pressed { background: #166534; }"
            "QPushButton:disabled { background: #374151; color: #6b7280; }"
        )
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._on_export_excel)
        hbox.addWidget(export_btn)

        # Indicateur de dernière synchronisation
        self._lbl_sync = QLabel()
        self._lbl_sync.setStyleSheet(
            f"color:{_TXT3}; font-size:10px; background:transparent; border:none;"
        )
        hbox.addWidget(self._lbl_sync)

        return bar

    def _on_date_changed(self, which: str, date: QDate) -> None:
        if which == "from":
            self._filter_date_from = date.toString("yyyy-MM-dd")
        else:
            self._filter_date_to = date.toString("yyyy-MM-dd")
        self.refresh()

    def _on_filter_reset(self) -> None:
        _y = QDate.currentDate().year()
        self._filter_date_from = f"{_y}-01-01"
        self._filter_date_to   = f"{_y}-12-31"
        self.refresh()

    # ── Export Excel ──────────────────────────────────────────────────────────

    def _on_export_excel(self) -> None:
        """Ouvre le dialogue de sauvegarde puis génère le fichier Excel."""
        data = getattr(self, "_last_data", None)
        if not data:
            QMessageBox.warning(
                self._layout.parentWidget(),
                "Données indisponibles",
                "Aucune donnée chargée. Attendez la fin du chargement.",
            )
            return

        d_from = self._filter_date_from
        d_to   = self._filter_date_to
        default_name = f"Dashboard_CNPS_{d_from}_{d_to}.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self._layout.parentWidget(),
            "Exporter le rapport Excel",
            default_name,
            "Fichiers Excel (*.xlsx)",
        )
        if not path:
            return

        try:
            self._write_excel(path, data, d_from, d_to)
        except Exception as exc:
            QMessageBox.critical(
                self._layout.parentWidget(),
                "Erreur export",
                f"Impossible de créer le fichier :\n{exc}",
            )
            return

        # Ouvrir le fichier automatiquement
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            pass

        QMessageBox.information(
            self._layout.parentWidget(),
            "Export réussi",
            f"Rapport exporté :\n{path}",
        )

    def _write_excel(self, path: str, data: dict, d_from: str, d_to: str) -> None:
        """Génère le fichier .xlsx formaté avec openpyxl."""
        import openpyxl
        from openpyxl.styles import (
            Font, PatternFill, Alignment, Border, Side
        )
        from openpyxl.utils import get_column_letter
        from datetime import date as _date

        wb = openpyxl.Workbook()

        # ── Styles communs ────────────────────────────────────────────────────
        _navy    = "1E3A5F"
        _green   = "16A34A"
        _amber   = "D97706"
        _blue    = "2563EB"
        _light   = "EFF6FF"
        _gray    = "F1F5F9"
        _white   = "FFFFFF"
        _bdr_clr = "CBD5E1"

        def _hdr_font(size=11, bold=True, color=_white):
            return Font(name="Calibri", size=size, bold=bold, color=color)

        def _body_font(size=10, bold=False, color="1E293B"):
            return Font(name="Calibri", size=size, bold=bold, color=color)

        def _fill(hex_color):
            return PatternFill("solid", fgColor=hex_color)

        def _center():
            return Alignment(horizontal="center", vertical="center", wrap_text=True)

        def _left():
            return Alignment(horizontal="left", vertical="center")

        def _thin_border():
            s = Side(style="thin", color=_bdr_clr)
            return Border(left=s, right=s, top=s, bottom=s)

        def _write_row(ws, row, values, font=None, fill=None, align=None, border=None):
            for col, val in enumerate(values, 1):
                c = ws.cell(row=row, column=col, value=val)
                if font:   c.font   = font
                if fill:   c.fill   = fill
                if align:  c.alignment = align
                if border: c.border = border

        def _auto_width(ws, min_w=10, max_w=50):
            for col_cells in ws.columns:
                length = max(
                    len(str(c.value)) if c.value is not None else 0
                    for c in col_cells
                )
                ws.column_dimensions[get_column_letter(col_cells[0].column)].width = \
                    max(min_w, min(max_w, length + 4))

        # ================================================================
        # FEUILLE 1 : Résumé
        # ================================================================
        ws1 = wb.active
        ws1.title = "Résumé"
        ws1.sheet_view.showGridLines = False

        # Titre principal
        ws1.merge_cells("A1:F1")
        c = ws1["A1"]
        c.value = "RAPPORT DE GESTION — CNPS ACCUEIL"
        c.font  = Font(name="Calibri", size=16, bold=True, color=_white)
        c.fill  = _fill(_navy)
        c.alignment = _center()
        ws1.row_dimensions[1].height = 36

        # Sous-titre période
        ws1.merge_cells("A2:F2")
        c = ws1["A2"]
        c.value = f"Période : du {d_from} au {d_to}   |   Généré le {_date.today().strftime('%d/%m/%Y')}"
        c.font  = _hdr_font(size=10, color="94A3B8")
        c.fill  = _fill("0F172A")
        c.alignment = _center()
        ws1.row_dimensions[2].height = 20

        # Ligne vide
        ws1.row_dimensions[3].height = 8

        # KPI cards
        total_demandes   = data.get("total_demandes", 0)
        total_traite     = data.get("total_traite", 0)
        total_attente    = data.get("total_attente", 0)
        total_non_traite = data.get("total_non_traite", 0)
        avg_wait         = data.get("avg_wait_min", 0.0)
        taux             = int(total_traite / total_demandes * 100) if total_demandes > 0 else 0
        avg_h, avg_m     = divmod(int(avg_wait), 60)
        avg_str          = f"{avg_h}h {avg_m:02d}min" if avg_h else f"{avg_m} min"

        kpis = [
            ("Total demandes",       total_demandes,       _navy),
            ("Demandes traitées",    total_traite,          _green),
            ("En attente",           total_attente + total_non_traite, _amber),
            ("Taux de traitement",   f"{taux} %",           _blue),
            ("Temps attente moyen",  avg_str,               "7C3AED"),
        ]

        row = 4
        ws1.row_dimensions[row].height = 20
        ws1.row_dimensions[row + 1].height = 32
        ws1.row_dimensions[row + 2].height = 18

        for col_idx, (label, value, color) in enumerate(kpis, 1):
            lbl_cell = ws1.cell(row=row, column=col_idx, value=label)
            lbl_cell.font  = _hdr_font(size=9, color=_white)
            lbl_cell.fill  = _fill(color)
            lbl_cell.alignment = _center()

            val_cell = ws1.cell(row=row + 1, column=col_idx, value=value)
            val_cell.font  = Font(name="Calibri", size=18, bold=True, color=color)
            val_cell.fill  = _fill(_light)
            val_cell.alignment = _center()
            val_cell.border = _thin_border()

            ws1.cell(row=row + 2, column=col_idx).fill = _fill(_gray)

        ws1.row_dimensions[row + 3].height = 12

        # Section services
        row_s = row + 4
        ws1.merge_cells(f"A{row_s}:F{row_s}")
        c = ws1.cell(row=row_s, column=1, value="Demandes par service")
        c.font = _hdr_font(size=11, color=_white)
        c.fill = _fill(_navy)
        c.alignment = _left()
        c.border = _thin_border()
        ws1.row_dimensions[row_s].height = 22

        row_s += 1
        _write_row(ws1, row_s, ["Service", "Nb demandes"],
                   font=_hdr_font(size=10, color=_navy), fill=_fill(_light),
                   align=_center(), border=_thin_border())
        ws1.row_dimensions[row_s].height = 18

        svc_names  = data.get("services_names", [])
        svc_counts = data.get("services_counts", [])
        for i, (name, cnt) in enumerate(zip(svc_names, svc_counts)):
            row_s += 1
            bg = _white if i % 2 == 0 else _gray
            ws1.cell(row=row_s, column=1, value=name).font  = _body_font()
            ws1.cell(row=row_s, column=1).fill   = _fill(bg)
            ws1.cell(row=row_s, column=1).border = _thin_border()
            ws1.cell(row=row_s, column=1).alignment = _left()
            ws1.cell(row=row_s, column=2, value=cnt).font   = _body_font(bold=True)
            ws1.cell(row=row_s, column=2).fill   = _fill(bg)
            ws1.cell(row=row_s, column=2).border = _thin_border()
            ws1.cell(row=row_s, column=2).alignment = _center()

        ws1.column_dimensions["A"].width = 34
        ws1.column_dimensions["B"].width = 18
        for col_l in ["C", "D", "E", "F"]:
            ws1.column_dimensions[col_l].width = 22

        # ================================================================
        # FEUILLE 2 : Temps d'attente
        # ================================================================
        ws2 = wb.create_sheet("Temps d'attente")
        ws2.sheet_view.showGridLines = False

        ws2.merge_cells("A1:C1")
        c = ws2["A1"]
        c.value = "Distribution des temps d'attente"
        c.font  = _hdr_font(size=13, color=_white)
        c.fill  = _fill(_navy)
        c.alignment = _center()
        ws2.row_dimensions[1].height = 30

        ws2.merge_cells("A2:C2")
        c = ws2["A2"]
        c.value = f"Période : {d_from} → {d_to}"
        c.font  = _hdr_font(size=10, color="94A3B8")
        c.fill  = _fill("0F172A")
        c.alignment = _center()

        row2 = 4
        _write_row(ws2, row2, ["Tranche d'attente", "Nb demandes", "% du total"],
                   font=_hdr_font(size=10, color=_white), fill=_fill(_navy),
                   align=_center(), border=_thin_border())
        ws2.row_dimensions[row2].height = 20

        wait_labels = data.get("wait_labels", [])
        wait_counts = data.get("wait_counts", [])
        total_wait  = sum(wait_counts) or 1
        _wcolors    = [_green, "84CC16", _amber, "F97316", "EF4444"]

        for i, (lbl, cnt) in enumerate(zip(wait_labels, wait_counts)):
            row2 += 1
            pct = f"{cnt / total_wait * 100:.1f} %"
            color_hex = _wcolors[i % len(_wcolors)]
            ws2.cell(row=row2, column=1, value=lbl).font  = Font(name="Calibri", size=10, bold=True, color=color_hex)
            ws2.cell(row=row2, column=1).fill   = _fill(_light if i % 2 == 0 else _gray)
            ws2.cell(row=row2, column=1).border = _thin_border()
            ws2.cell(row=row2, column=1).alignment = _left()
            ws2.cell(row=row2, column=2, value=cnt).font   = _body_font(bold=True)
            ws2.cell(row=row2, column=2).fill   = _fill(_light if i % 2 == 0 else _gray)
            ws2.cell(row=row2, column=2).border = _thin_border()
            ws2.cell(row=row2, column=2).alignment = _center()
            ws2.cell(row=row2, column=3, value=pct).font   = _body_font()
            ws2.cell(row=row2, column=3).fill   = _fill(_light if i % 2 == 0 else _gray)
            ws2.cell(row=row2, column=3).border = _thin_border()
            ws2.cell(row=row2, column=3).alignment = _center()

        # Ligne total
        row2 += 1
        _write_row(ws2, row2,
                   ["TOTAL", sum(wait_counts), "100 %"],
                   font=_hdr_font(size=10, color=_white),
                   fill=_fill(_navy), align=_center(), border=_thin_border())
        _auto_width(ws2)

        # ================================================================
        # FEUILLE 3 : Motifs
        # ================================================================
        ws3 = wb.create_sheet("Motifs")
        ws3.sheet_view.showGridLines = False

        ws3.merge_cells("A1:C1")
        c = ws3["A1"]
        c.value = "Demandes par motif"
        c.font  = _hdr_font(size=13, color=_white)
        c.fill  = _fill(_navy)
        c.alignment = _center()
        ws3.row_dimensions[1].height = 30

        row3 = 3
        _write_row(ws3, row3, ["Motif", "Nb demandes", "% du total"],
                   font=_hdr_font(size=10, color=_white), fill=_fill(_navy),
                   align=_center(), border=_thin_border())

        motifs_names  = data.get("motifs_names", [])
        motifs_counts = data.get("motifs_counts", [])
        total_motifs  = sum(motifs_counts) or 1
        for i, (name, cnt) in enumerate(zip(motifs_names, motifs_counts)):
            row3 += 1
            bg = _white if i % 2 == 0 else _gray
            pct = f"{cnt / total_motifs * 100:.1f} %"
            ws3.cell(row=row3, column=1, value=name).font  = _body_font()
            ws3.cell(row=row3, column=1).fill   = _fill(bg)
            ws3.cell(row=row3, column=1).border = _thin_border()
            ws3.cell(row=row3, column=1).alignment = _left()
            ws3.cell(row=row3, column=2, value=cnt).font   = _body_font(bold=True)
            ws3.cell(row=row3, column=2).fill   = _fill(bg)
            ws3.cell(row=row3, column=2).border = _thin_border()
            ws3.cell(row=row3, column=2).alignment = _center()
            ws3.cell(row=row3, column=3, value=pct).font   = _body_font()
            ws3.cell(row=row3, column=3).fill   = _fill(bg)
            ws3.cell(row=row3, column=3).border = _thin_border()
            ws3.cell(row=row3, column=3).alignment = _center()

        row3 += 1
        _write_row(ws3, row3, ["TOTAL", sum(motifs_counts), "100 %"],
                   font=_hdr_font(size=10, color=_white),
                   fill=_fill(_navy), align=_center(), border=_thin_border())
        _auto_width(ws3)

        # ================================================================
        # FEUILLE 4 : Satisfaction
        # ================================================================
        ws_sat = wb.create_sheet("Satisfaction")
        ws_sat.sheet_view.showGridLines = False

        sat_counts_xl = data.get("sat_counts", [0, 0, 0, 0, 0])
        sat_avg_xl    = data.get("sat_avg", 0.0)
        sat_total_xl  = data.get("sat_total", 0)
        _sat_colors_xl = [_green, "F97316", _amber, "84CC16", "16A34A"]

        ws_sat.merge_cells("A1:D1")
        c = ws_sat["A1"]
        c.value = "Rapport de satisfaction usagers — CNPS Accueil"
        c.font  = _hdr_font(size=13, color=_white)
        c.fill  = _fill(_navy)
        c.alignment = _center()
        ws_sat.row_dimensions[1].height = 30

        ws_sat.merge_cells("A2:D2")
        c = ws_sat["A2"]
        c.value = f"Période : {d_from} → {d_to}   |   Total avis : {sat_total_xl}   |   Moyenne : {sat_avg_xl:.2f} / 5"
        c.font  = _hdr_font(size=10, color="94A3B8")
        c.fill  = _fill("0F172A")
        c.alignment = _center()

        # KPI satisfaction
        _sat_kpi_labels = [
            ("Note moyenne",          f"{sat_avg_xl:.2f} / 5",                        _navy),
            ("Total avis",            sat_total_xl,                                    _blue),
            ("Avis positifs (4-5★)",  sat_counts_xl[3] + sat_counts_xl[4],            _green),
            ("Avis négatifs (1-2★)",  sat_counts_xl[0] + sat_counts_xl[1],            "B91C1C"),
        ]
        row_k = 4
        ws_sat.row_dimensions[row_k].height = 18
        ws_sat.row_dimensions[row_k + 1].height = 28
        for ci, (lbl, val, clr) in enumerate(_sat_kpi_labels, 1):
            c = ws_sat.cell(row=row_k, column=ci, value=lbl)
            c.font = _hdr_font(size=9, color=_white); c.fill = _fill(clr); c.alignment = _center()
            c = ws_sat.cell(row=row_k + 1, column=ci, value=val)
            c.font = Font(name="Calibri", size=16, bold=True, color=clr)
            c.fill = _fill(_light); c.alignment = _center(); c.border = _thin_border()

        row_sat = row_k + 3
        _write_row(ws_sat, row_sat, ["Note", "Libellé", "Nb avis", "% des avis"],
                   font=_hdr_font(size=10, color=_white), fill=_fill(_navy),
                   align=_center(), border=_thin_border())
        ws_sat.row_dimensions[row_sat].height = 20

        _sat_xl_labels = ["★ Très insatisfait", "★★ Insatisfait", "★★★ Neutre",
                          "★★★★ Satisfait", "★★★★★ Très satisfait"]
        total_sat_denom = sat_total_xl or 1
        for i, (cnt, lbl, clr) in enumerate(zip(sat_counts_xl, _sat_xl_labels, _sat_colors_xl)):
            row_sat += 1
            pct = f"{cnt / total_sat_denom * 100:.1f} %"
            bg = _white if i % 2 == 0 else _gray
            ws_sat.cell(row=row_sat, column=1, value=i + 1).font = Font(name="Calibri", size=11, bold=True, color=clr)
            ws_sat.cell(row=row_sat, column=1).fill   = _fill(bg)
            ws_sat.cell(row=row_sat, column=1).border = _thin_border()
            ws_sat.cell(row=row_sat, column=1).alignment = _center()
            ws_sat.cell(row=row_sat, column=2, value=lbl).font  = _body_font(bold=True, color=clr)
            ws_sat.cell(row=row_sat, column=2).fill   = _fill(bg)
            ws_sat.cell(row=row_sat, column=2).border = _thin_border()
            ws_sat.cell(row=row_sat, column=2).alignment = _left()
            ws_sat.cell(row=row_sat, column=3, value=cnt).font   = _body_font(bold=True)
            ws_sat.cell(row=row_sat, column=3).fill   = _fill(bg)
            ws_sat.cell(row=row_sat, column=3).border = _thin_border()
            ws_sat.cell(row=row_sat, column=3).alignment = _center()
            ws_sat.cell(row=row_sat, column=4, value=pct).font   = _body_font()
            ws_sat.cell(row=row_sat, column=4).fill   = _fill(bg)
            ws_sat.cell(row=row_sat, column=4).border = _thin_border()
            ws_sat.cell(row=row_sat, column=4).alignment = _center()

        row_sat += 1
        _write_row(ws_sat, row_sat, ["", "TOTAL", sat_total_xl, "100 %"],
                   font=_hdr_font(size=10, color=_white),
                   fill=_fill(_navy), align=_center(), border=_thin_border())
        _auto_width(ws_sat)

        # ================================================================
        # FEUILLE 5 : Usagers fréquents
        # ================================================================
        ws_top = wb.create_sheet("Usagers fréquents")
        ws_top.sheet_view.showGridLines = False

        top_users_xl = data.get("top_users", [])
        _medals_xl = {0: "🥇", 1: "🥈", 2: "🥉"}

        ws_top.merge_cells("A1:G1")
        c = ws_top["A1"]
        c.value = "Classement des usagers les plus fréquents"
        c.font  = _hdr_font(size=13, color=_white)
        c.fill  = _fill(_navy)
        c.alignment = _center()
        ws_top.row_dimensions[1].height = 30

        ws_top.merge_cells("A2:G2")
        c = ws_top["A2"]
        c.value = f"Période : {d_from} → {d_to}   |   {len(top_users_xl)} usagers affichés"
        c.font  = _hdr_font(size=10, color="94A3B8")
        c.fill  = _fill("0F172A")
        c.alignment = _center()

        row_t = 4
        _write_row(ws_top, row_t,
                   ["Rang", "Nom", "Prénom", "N° CNPS", "Contact", "Nb visites", "Dernière visite"],
                   font=_hdr_font(size=10, color=_white), fill=_fill(_navy),
                   align=_center(), border=_thin_border())
        ws_top.row_dimensions[row_t].height = 20

        _top_accent = {0: "F59E0B", 1: "94A3B8", 2: "B45309"}
        for i, u in enumerate(top_users_xl):
            row_t += 1
            bg = _white if i % 2 == 0 else _gray
            medal = _medals_xl.get(i, "")
            rank_str = f"{medal} {i + 1}" if medal else str(i + 1)
            accent = _top_accent.get(i, "1E293B")
            is_top3 = i < 3
            row_vals = [
                rank_str, u["nom"], u["prenom"],
                u["cnps"] or "—", u["contact"] or "—",
                u["nb_visites"], u["derniere_visite"],
            ]
            for ci, val in enumerate(row_vals, 1):
                cell = ws_top.cell(row=row_t, column=ci, value=val)
                cell.font   = Font(name="Calibri", size=10,
                                   bold=is_top3,
                                   color=accent if (is_top3 and ci in (1, 6)) else "1E293B")
                cell.fill   = _fill(bg)
                cell.border = _thin_border()
                cell.alignment = _center() if ci != 2 else _left()
        _auto_width(ws_top)

        # ================================================================
        # FEUILLE 6 : Détail brut
        # ================================================================
        ws4 = wb.create_sheet("Données brutes")
        ws4.sheet_view.showGridLines = False

        and_cond = "AND date(COALESCE(d.date, d.created_at)) BETWEEN ? AND ?"
        raw_rows = db.execute_query(
            f"""SELECT d.date, d.nom, d.prenom, d.numero_cnps,
                       s.nom AS service, m.nom AS motif,
                       d.priorite, d.statut, d.temps_attente,
                       d.heure_arrivee, d.heure_reception, d.satisfaction
                FROM accueil_demandeaccueil d
                LEFT JOIN accueil_service s ON d.service_demande_id = s.id
                LEFT JOIN accueil_motif   m ON d.motif_id = m.id
                WHERE 1=1 {and_cond}
                ORDER BY d.date DESC, d.heure_arrivee DESC""",
            (d_from, d_to),
        )

        ws4.merge_cells("A1:L1")
        c = ws4["A1"]
        c.value = f"Données brutes — {d_from} au {d_to}"
        c.font  = _hdr_font(size=12, color=_white)
        c.fill  = _fill(_navy)
        c.alignment = _center()
        ws4.row_dimensions[1].height = 26

        headers = ["Date", "Nom", "Prénom", "N° CNPS", "Service", "Motif",
                   "Priorité", "Statut", "Temps attente", "Heure arrivée",
                   "Heure réception", "Satisfaction"]
        _write_row(ws4, 2, headers,
                   font=_hdr_font(size=10, color=_white), fill=_fill("1E3A5F"),
                   align=_center(), border=_thin_border())
        ws4.row_dimensions[2].height = 18
        ws4.freeze_panes = "A3"

        for i, row_data in enumerate(raw_rows):
            r = i + 3
            bg = _white if i % 2 == 0 else _gray
            vals = [
                row_data.get("date", ""),
                (row_data.get("nom", "") or "").upper(),
                (row_data.get("prenom", "") or "").title(),
                row_data.get("numero_cnps", ""),
                row_data.get("service", ""),
                row_data.get("motif", ""),
                row_data.get("priorite", ""),
                row_data.get("statut", ""),
                row_data.get("temps_attente", ""),
                row_data.get("heure_arrivee", ""),
                row_data.get("heure_reception", ""),
                row_data.get("satisfaction", ""),
            ]
            for col_idx, val in enumerate(vals, 1):
                cell = ws4.cell(row=r, column=col_idx, value=val)
                cell.font      = _body_font(size=9)
                cell.fill      = _fill(bg)
                cell.border    = _thin_border()
                cell.alignment = _center() if col_idx != 2 else _left()

        _auto_width(ws4)

        wb.save(path)

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _fade_in(self, widget, delay_ms: int = 0) -> None:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        # Conserver la référence Python pour éviter la collecte GC avant le timer
        self._animations.append(effect)

        def _start() -> None:
            try:
                anim = QPropertyAnimation(effect, b"opacity")
            except RuntimeError:
                return   # widget ou effet déjà supprimé
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(550)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            self._animations.append(anim)

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _start)
        else:
            _start()

    def _make_kpi_card(self, title: str, value: str, subtitle: str, accent: str, delay_ms: int = 0) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {_BG_CARD}; border-radius: 12px;"
            f" border: 1px solid {_BORDER}; border-top: 3px solid {accent}; }}"
        )
        frame.setMinimumHeight(110)
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(14, 10, 14, 10)
        vbox.setSpacing(4)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(
            f"color: {_TXT3}; font-weight: 600; letter-spacing: 0.7px; border: none; background: transparent;"
        )
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(
            f"color: {accent}; font-size: 20px; font-weight: 800; border: none; background: transparent;"
        )
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(f"color: {_TXT3}; border: none; background: transparent;")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_value)
        vbox.addWidget(lbl_sub)
        vbox.addStretch(1)

        self._responsive_label_specs.extend([(lbl_title, 9), (lbl_value, 18), (lbl_sub, 9)])
        self._fade_in(frame, delay_ms)
        return frame

    def _make_chart_card(self, title: str, subtitle: str, delay_ms: int = 0) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {_BG_CARD}; border-radius: 12px; border: 1px solid {_BORDER}; }}"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = QFrame()
        hdr.setStyleSheet(
            f"QFrame {{ background-color: {_BG_HDR}; border: none;"
            " border-radius: 12px; border-bottom-left-radius: 0; border-bottom-right-radius: 0;"
            f" border-bottom: 1px solid {_BORDER}; }}"
        )
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(18, 11, 18, 9)
        hdr_lay.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(
            f"color: {_TXT1}; font-weight: 700; font-size: 12px; border: none; background: transparent;"
        )
        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"color: {_TXT2}; font-size: 10px; border: none; background: transparent;")
        hdr_lay.addWidget(lbl_t)
        hdr_lay.addWidget(lbl_s)
        outer.addWidget(hdr)

        self._fade_in(card, delay_ms)
        return card, outer

    def _base_chart(self, bg: str = _BG_CARD) -> QChart:
        chart = QChart()
        chart.setTheme(QChart.ChartTheme.ChartThemeDark)
        chart.setTitle("")
        chart.setBackgroundBrush(QColor(bg))
        chart.setBackgroundRoundness(0)
        chart.setMargins(QMargins(10, 6, 10, 6))
        chart.setAnimationOptions(QChart.AnimationOption.AllAnimations)
        chart.setAnimationDuration(700)
        tf = chart.titleFont()
        tf.setPointSize(1)
        chart.setTitleFont(tf)
        return chart

    @staticmethod
    def _styled_view(chart: QChart, min_h: int = 220) -> QChartView:
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setStyleSheet("background: transparent; border: none;")
        view.setMinimumHeight(min_h)
        return view

    def _style_legend(self, chart: QChart) -> None:
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        lf = chart.legend().font()
        lf.setPointSize(9)
        chart.legend().setFont(lf)
        chart.legend().setColor(QColor(_TXT1))
        chart.legend().setLabelColor(QColor(_TXT2))

    def _style_axis(self, axis) -> None:
        lf = axis.labelsFont()
        lf.setPointSize(9)
        axis.setLabelsFont(lf)
        axis.setLabelsColor(QColor(_TXT2))
        if isinstance(axis, QValueAxis):
            axis.setGridLineColor(QColor(_GRID))

    # ── Construction principale ───────────────────────────────────────────────

    def add_chart(self) -> None:
        """Point d'entrée : lance le chargement async puis construit les graphiques."""
        self.refresh()

    def _build_charts(self, data: dict) -> None:
        """Construit tous les widgets graphiques à partir des données reçues du worker."""
        layout = self._layout
        self._responsive_label_specs = []
        self._animations.clear()

        # Vider le layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        parent = layout.parentWidget()
        if parent is not None:
            parent.setStyleSheet(f"background-color: {_BG_DEEP};")

        total_demandes   = data.get("total_demandes", 0)
        total_traite     = data.get("total_traite", 0)
        total_attente    = data.get("total_attente", 0)
        total_non_traite = data.get("total_non_traite", 0)
        services_names   = data.get("services_names", [])
        services_counts  = data.get("services_counts", [])
        motifs_names     = data.get("motifs_names", [])
        motifs_counts    = data.get("motifs_counts", [])
        wait_labels      = data.get("wait_labels", [])
        wait_counts      = data.get("wait_counts", [])
        avg_wait_min     = data.get("avg_wait_min", 0.0)
        sat_counts       = data.get("sat_counts", [0, 0, 0, 0, 0])
        sat_avg          = data.get("sat_avg", 0.0)
        sat_total        = data.get("sat_total", 0)
        top_users        = data.get("top_users", [])
        dow_labels       = data.get("dow_labels", [])
        dow_avgs         = data.get("dow_avgs", [])

        # ── Mise en page grille 4 colonnes ────────────────────────────────
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(14, 12, 14, 12)
        for col in range(5):
            layout.setColumnStretch(col, 1)

        # LIGNE 0 : Barre de filtres
        layout.addWidget(self._make_filter_bar(), 0, 0, 1, 5)

        # LIGNE 1 : 5 cartes KPI (span adapté)
        taux = int(total_traite / total_demandes * 100) if total_demandes > 0 else 0
        avg_h, avg_m = divmod(int(avg_wait_min), 60)
        avg_wait_str = f"{avg_h}h {avg_m:02d}min" if avg_h else f"{avg_m} min"
        sat_stars = "★" * round(sat_avg) + "☆" * (5 - round(sat_avg)) if sat_avg else "—"
        sat_label = f"{sat_avg:.1f} / 5" if sat_total > 0 else "—"
        kpi_data = [
            ("Total demandes",      str(total_demandes),                   "Dans la période",      _C_NAVY),
            ("Demand. traitées",    str(total_traite),                     "Statut traité",        _C_GREEN),
            ("En attente",          str(total_attente + total_non_traite), "Non traitées",         _C_AMBER),
            ("Temps attente moyen", avg_wait_str,                          "Tous statuts",         _C_BLUE),
            ("Satisfaction moy.",   sat_label,                             sat_stars,              "#7c3aed"),
        ]
        for col, (title, value, sub, accent) in enumerate(kpi_data):
            layout.addWidget(self._make_kpi_card(title, value, sub, accent, delay_ms=col * 70), 1, col)

        # LIGNE 2 : Camembert statut | Camembert priorité
        pie_card, pie_lay = self._make_chart_card(
            "Statut global des demandes", "Trait\u00e9es vs non trait\u00e9es", delay_ms=100,
        )
        pie_series = QPieSeries()
        s_t = pie_series.append(f"Trait\u00e9es  ({total_traite})", max(total_traite, 1))
        s_a = pie_series.append(f"En attente  ({total_attente + total_non_traite})", max(total_attente + total_non_traite, 1))
        s_t.setColor(QColor(_C_BLUE));  s_t.setBorderColor(QColor(_C_BLUE))
        s_a.setColor(QColor(_C_AMBER)); s_a.setBorderColor(QColor(_C_AMBER))
        s_t.setExploded(True); s_t.setExplodeDistanceFactor(0.05)
        pie_chart = self._base_chart()
        pie_chart.addSeries(pie_series)
        pie_chart.setMargins(QMargins(8, 4, 8, 4))
        self._style_legend(pie_chart)
        pie_lay.addWidget(self._styled_view(pie_chart, min_h=200))
        layout.addWidget(pie_card, 2, 0, 1, 2)

        # Graphique temps d'attente — barres verticales colorées par tranche
        wait_card, wait_lay = self._make_chart_card(
            "Distribution des temps d'attente",
            "Nombre de demandes par tranche de durée d'attente",
            delay_ms=180,
        )
        _bar_colors = [_C_GREEN, "#84cc16", _C_AMBER, "#f97316", "#ef4444"]
        wait_series_list = []
        _wl = wait_labels if (wait_labels and not all(c == 0 for c in wait_counts)) else ["Aucune donnée"]
        _wc = wait_counts if (wait_labels and not all(c == 0 for c in wait_counts)) else [0]
        for i, (lbl, cnt) in enumerate(zip(_wl, _wc)):
            bs = QBarSet(lbl)
            bs.setColor(QColor(_bar_colors[i % len(_bar_colors)]))
            bs.setBorderColor(QColor(_bar_colors[i % len(_bar_colors)]))
            bs.append(cnt)
            wait_series_list.append(bs)

        wait_bar_series = QBarSeries()
        for bs in wait_series_list:
            wait_bar_series.append(bs)
        wait_bar_series.setLabelsVisible(True)
        wait_bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        wait_chart = self._base_chart()
        wait_chart.addSeries(wait_bar_series)
        wait_chart.setMargins(QMargins(8, 8, 8, 4))

        ax_x = QBarCategoryAxis()
        ax_x.append([""] * len(_wl))
        self._style_axis(ax_x)
        wait_chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        wait_bar_series.attachAxis(ax_x)

        ax_y = QValueAxis()
        ax_y.setRange(0, max(_wc) * 1.25 if max(_wc) > 0 else 10)
        ax_y.setLabelFormat("%d")
        ax_y.setTickCount(5)
        self._style_axis(ax_y)
        wait_chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        wait_bar_series.attachAxis(ax_y)

        self._style_legend(wait_chart)
        wait_chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        wait_lay.addWidget(self._styled_view(wait_chart, min_h=200))
        layout.addWidget(wait_card, 2, 2, 1, 3)

        # LIGNE 3 : Satisfaction — barres par note (gauche) + camembert positif/négatif (droite)
        _sat_colors = ["#ef4444", "#f97316", _C_AMBER, "#84cc16", _C_GREEN]
        _sat_labels = ["★ 1", "★★ 2", "★★★ 3", "★★★★ 4", "★★★★★ 5"]

        sat_bar_card, sat_bar_lay = self._make_chart_card(
            "Répartition des notes de satisfaction",
            f"Sur {sat_total} avis collectés — moyenne {sat_avg:.1f} / 5",
            delay_ms=220,
        )
        # Même pattern que "Distribution temps d'attente" :
        # N QBarSet × 1 valeur + QBarSeries + axe avec labels vides → labels légende + valeurs au-dessus
        _sat_series = QBarSeries()
        _sat_series.setBarWidth(0.55)
        for lbl, cnt, clr in zip(_sat_labels, sat_counts, _sat_colors):
            bs = QBarSet(lbl)
            bs.setColor(QColor(clr))
            bs.setBorderColor(QColor(clr))
            bs.append(cnt)
            _sat_series.append(bs)
        _sat_series.setLabelsVisible(True)
        _sat_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        _sat_chart = self._base_chart()
        _sat_chart.addSeries(_sat_series)
        _sat_chart.setMargins(QMargins(8, 8, 8, 4))

        _ax_cat = QBarCategoryAxis()
        _ax_cat.append([""] * len(_sat_labels))
        self._style_axis(_ax_cat)
        _sat_chart.addAxis(_ax_cat, Qt.AlignmentFlag.AlignBottom)
        _sat_series.attachAxis(_ax_cat)

        _ax_val = QValueAxis()
        _ax_val.setRange(0, max(sat_counts) * 1.35 if max(sat_counts) > 0 else 10)
        _ax_val.setLabelFormat("%d")
        _ax_val.setTickCount(5)
        self._style_axis(_ax_val)
        _sat_chart.addAxis(_ax_val, Qt.AlignmentFlag.AlignLeft)
        _sat_series.attachAxis(_ax_val)

        self._style_legend(_sat_chart)
        _sat_chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        sat_bar_lay.addWidget(self._styled_view(_sat_chart, min_h=220))
        layout.addWidget(sat_bar_card, 3, 0, 1, 3)

        # Camembert satisfaction positive (4-5) vs négative (1-2) vs neutre (3)
        sat_pos     = sat_counts[3] + sat_counts[4]   # notes 4 et 5
        sat_neg     = sat_counts[0] + sat_counts[1]   # notes 1 et 2
        sat_neutral = sat_counts[2]                   # note 3

        sat_pie_card, sat_pie_lay = self._make_chart_card(
            "Indice de satisfaction",
            "Positif (4-5★) · Neutre (3★) · Négatif (1-2★)",
            delay_ms=260,
        )
        sat_pie_series = QPieSeries()
        _sp = [
            (f"Positif  ({sat_pos})",     max(sat_pos, 1),     _C_GREEN),
            (f"Neutre  ({sat_neutral})",   max(sat_neutral, 1), _C_AMBER),
            (f"Négatif  ({sat_neg})",      max(sat_neg, 1),     "#ef4444"),
        ]
        for lbl, val, clr in _sp:
            sl = sat_pie_series.append(lbl, val)
            sl.setColor(QColor(clr)); sl.setBorderColor(QColor(clr))
        if sat_pos > 0:
            sat_pie_series.slices()[0].setExploded(True)
            sat_pie_series.slices()[0].setExplodeDistanceFactor(0.06)
        sat_pie_chart = self._base_chart()
        sat_pie_chart.addSeries(sat_pie_series)
        sat_pie_chart.setMargins(QMargins(8, 4, 8, 4))
        self._style_legend(sat_pie_chart)
        sat_pie_lay.addWidget(self._styled_view(sat_pie_chart, min_h=210))
        layout.addWidget(sat_pie_card, 3, 3, 1, 2)

        # LIGNE 4 : Barres horizontales par service (gauche) + par motif (droite)
        self._add_horiz_bar_card(
            layout, row=4, col_start=0, col_span=2,
            title="Demandes par service",
            subtitle="Volume de demandes enregistrées par service",
            names=services_names, counts=services_counts,
            color=_C_NAVY, delay_ms=320,
        )
        self._add_horiz_bar_card(
            layout, row=4, col_start=2, col_span=3,
            title="Demandes par motif",
            subtitle="Volume de demandes enregistrées par motif",
            names=motifs_names, counts=motifs_counts,
            color=_C_GREEN, delay_ms=380,
        )

        # LIGNE 5 : Affluence moyenne par jour de la semaine (pleine largeur)
        self._add_dow_bar_card(
            layout, row=5,
            dow_labels=dow_labels, dow_avgs=dow_avgs,
            delay_ms=420,
        )

        # LIGNE 6 : Tableau usagers les plus fréquents (pleine largeur)
        layout.addWidget(
            self._make_top_users_card(top_users, delay_ms=480),
            6, 0, 1, 5,
        )

    def _make_top_users_card(self, users: list[dict], delay_ms: int = 0) -> QFrame:
        """Délègue à _TopUsersFrame — classe propre sans closures (évite le bus error)."""
        frame = _TopUsersFrame(users, parent=None)
        self._fade_in(frame, delay_ms)
        return frame

    def _add_dow_bar_card(
        self,
        layout: QGridLayout,
        row: int,
        dow_labels: list[str],
        dow_avgs:   list[float],
        delay_ms:   int = 0,
    ) -> None:
        """Graphique barres verticales : affluence moyenne par jour de la semaine."""
        card, card_lay = self._make_chart_card(
            "📅  Affluence moyenne par jour",
            "Nombre moyen de visites reçues chaque jour de la semaine · selon le filtre de dates",
            delay_ms=delay_ms,
        )

        if not dow_labels:
            lbl = QLabel("Aucune donnée disponible sur cette période.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{_TXT3}; font-size:12px; padding:20px; background:transparent;")
            card_lay.addWidget(lbl)
            layout.addWidget(card, row, 0, 1, 5)
            return

        # Couleur différente par jour (Lun→Ven)
        _DAY_COLORS = {
            "Lun": "#1d4ed8",  # bleu
            "Mar": "#0891b2",  # cyan
            "Mer": "#059669",  # vert
            "Jeu": "#7c3aed",  # violet
            "Ven": "#f59e0b",  # ambre
        }

        # QStackedBarSeries diagonal : 1 QBarSet par jour avec N valeurs
        # (valeur réelle à sa position, 0 ailleurs) → barres séparées + couleur individuelle
        nd     = len(dow_labels)
        series = QStackedBarSeries()
        series.setBarWidth(0.5)
        for i, (day, avg) in enumerate(zip(dow_labels, dow_avgs)):
            bs = QBarSet(day)
            bs.setColor(QColor(_DAY_COLORS.get(day, _C_BLUE)))
            bs.setBorderColor(QColor(_DAY_COLORS.get(day, _C_BLUE)))
            for j in range(nd):
                bs.append(avg if j == i else 0)
            series.append(bs)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)
        series.setLabelsFormat("@value")

        chart = self._base_chart()
        chart.addSeries(series)
        chart.setMargins(QMargins(10, 14, 10, 4))

        ax_x = QBarCategoryAxis()
        ax_x.append(dow_labels)   # Lun, Mar, Mer, Jeu, Ven
        self._style_axis(ax_x)
        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(ax_x)

        max_val = max(dow_avgs) if dow_avgs else 1
        ax_y = QValueAxis()
        ax_y.setRange(0, max_val * 1.45)
        ax_y.setLabelFormat("%.1f")
        ax_y.setTickCount(6)
        ax_y.setTitleText("Moy. visites / jour")
        ax_y.setTitleFont(QFont("", 9))
        ax_y.setTitleBrush(QColor(_TXT3))
        self._style_axis(ax_y)
        chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(ax_y)

        chart.legend().setVisible(False)   # noms déjà sur l'axe X
        card_lay.addWidget(self._styled_view(chart, min_h=250))
        layout.addWidget(card, row, 0, 1, 5)
        self._fade_in(card, delay_ms)

    def _add_horiz_bar_card(  # noqa: E302
        self, layout: QGridLayout, row: int, col_start: int, col_span: int,
        title: str, subtitle: str, names: list[str], counts: list[int],
        color: str, delay_ms: int = 0,
    ) -> None:
        if not names:
            names = ["Aucune donn\u00e9e"]; counts = [0]

        card, card_lay = self._make_chart_card(title, subtitle, delay_ms=delay_ms)

        bar_set = QBarSet("Demandes")
        bar_set.setColor(QColor(color)); bar_set.setBorderColor(QColor(color))
        for n in counts:
            bar_set.append(n)

        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setBarWidth(0.55)
        series.setLabelsVisible(True)

        chart = self._base_chart()
        chart.addSeries(series)
        chart.setMargins(QMargins(8, 4, 24, 4))

        ax_y = QBarCategoryAxis()
        ax_y.append([_truncate(s, 24) for s in names])
        self._style_axis(ax_y)
        chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(ax_y)

        max_val = max(counts) if counts else 1
        ax_x = QValueAxis()
        ax_x.setRange(0, max_val * 1.3)
        ax_x.setLabelFormat("%d")
        ax_x.setTickCount(5)
        self._style_axis(ax_x)
        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(ax_x)
        chart.legend().setVisible(False)

        min_h = max(200, len(names) * 32 + 60)
        card_lay.addWidget(self._styled_view(chart, min_h=min_h))
        layout.addWidget(card, row, col_start, 1, col_span)


# ── Page Dashboard ────────────────────────────────────────────────────────────

class DashboardPage(QMainWindow):
    """Page Dashboard embarquant des graphiques modernes adaptés pour l'Accueil."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dashboard")

        # Widget central avec scroll
        central = QWidget()
        self.setCentralWidget(central)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_BG_DEEP}; border: none; }}"
            "QScrollBar:vertical { background: #1e293b; width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: #475569; border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setStyleSheet(f"background-color: {_BG_DEEP};")
        self._grid = QGridLayout(content)
        scroll.setWidget(content)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._chart_handler = _ChartHandler(self._grid)
        self._chart_handler.add_chart()

        # Rafraîchissement automatique silencieux toutes les 60s
        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: self._chart_handler.refresh(silent=True))
        self._timer.start(60_000)

    def closeEvent(self, event):
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()
        # Attendre la fin du thread worker si actif
        handler = getattr(self, "_chart_handler", None)
        if handler and handler._is_thread_running():
            handler._thread.quit()
            handler._thread.wait(2000)
        super().closeEvent(event)
