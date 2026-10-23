"""Perf/non-régression du dashboard: requêtes indexables, regroupées, refresh conditionnel."""
from datetime import date, timedelta
import random
import time

from database.connection import db
from widgets.dashboard.Main import _WAIT_MIN, _DashboardWorker


def _legacy(d_from, d_to):
    """Ancienne implémentation (≈10 requêtes, date(COALESCE(...)) BETWEEN) gardée comme référence."""
    if True:
            and_cond = "AND date(COALESCE(d.date, d.created_at)) BETWEEN ? AND ?"
            params   = (d_from, d_to)

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
                    WHEN ({_WAIT_MIN}) <= 15 THEN '≤ 15 min'
                    WHEN ({_WAIT_MIN}) <= 30 THEN '15–30 min'
                    WHEN ({_WAIT_MIN}) <= 60 THEN '30–60 min'
                    WHEN ({_WAIT_MIN}) <= 90 THEN '60–90 min'
                    ELSE '> 90 min'
                  END AS tranche,
                  COUNT(*) AS nb
                FROM accueil_demandeaccueil d
                WHERE temps_attente IS NOT NULL AND temps_attente != '' {and_cond}
                GROUP BY tranche
                ORDER BY MIN(
                    {_WAIT_MIN}
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
                        {_WAIT_MIN}
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

            return ({
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


# ── Jeu de données ───────────────────────────────────────────────────────────

_STATUTS = ["traite", "en_attente", "non_traite", " Traite ", "EN_ATTENTE", None, "autre"]
_ATTENTES = ["0:05:00", "0:12:30", "00:20:00", "0:45:10", "1:10:00", "2:00:00", "", None, "abc"]


def _jeu(n: int, seed: int = 1, dates_nulles: bool = True):
    """n demandes sur 2021: dates 'AAAA-MM-JJ', ISO 'T', 'espace', et date NULL (created_at seul)."""
    rnd = random.Random(seed)
    debut = date(2021, 1, 1)
    rows = []
    for i in range(n):
        j = (debut + timedelta(days=rnd.randrange(365))).isoformat()
        fmt = rnd.randrange(4 if dates_nulles else 3)
        d, c = {0: (j, j + "T09:00:00"), 1: (j + "T10:30:15", j + "T10:30:15"),
                2: (j + " 11:00:00", j + " 11:00:00"), 3: (None, j + "T08:00:00.123456")}[fmt]
        rows.append((f"perf{seed}-{i}", d, f"N{rnd.randrange(30)}", f"P{rnd.randrange(30)}",
                     rnd.choice(["", None, f"C{rnd.randrange(20)}"]),
                     rnd.choice([None, 1, 2, 3]), rnd.choice([None, 1, 2, 3]),
                     rnd.choice(_STATUTS), rnd.choice([None, 1, 2, 3, 4, 5, 0, 7]),
                     rnd.choice(_ATTENTES), rnd.choice(["", None, "0102030405"]), c, c))
    return rows


def _charger(rows):
    db.execute_update("DELETE FROM accueil_demandeaccueil")
    db.execute_many(
        "INSERT INTO accueil_demandeaccueil (id, date, nom, prenom, numero_cnps, service_demande_id,"
        " motif_id, statut, satisfaction, temps_attente, contacts, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def _normalise(d):
    """Les égalités à rang égal (LIMIT/ORDER BY nb) n'ont pas d'ordre garanti: on les trie."""
    d = dict(d)
    d["top_users"] = sorted(d["top_users"], key=lambda u: (-u["nb_visites"], u["nom"], u["prenom"], u["cnps"]))
    for k, v in (("services_names", "services_counts"), ("motifs_names", "motifs_counts")):
        d[k], d[v] = zip(*sorted(zip(d[k], d[v]), key=lambda t: (-t[1], t[0]))) if d[k] else ((), ())
    return d


def test_worker_identique_a_l_ancienne_version():
    _charger(_jeu(3000))
    for a, b in [("2021-01-01", "2021-12-31"), ("2021-03-15", "2021-03-15"),
                 ("2021-06-01", "2021-06-30"), ("2020-01-01", "2020-12-31")]:
        assert _normalise(_DashboardWorker(a, b).load()) == _normalise(_legacy(a, b)), (a, b)


def test_worker_identique_sans_date_nulle():
    _charger(_jeu(3000, seed=5, dates_nulles=False))
    for a, b in [("2021-01-01", "2021-12-31"), ("2021-07-04", "2021-07-20")]:
        assert _normalise(_DashboardWorker(a, b).load()) == _normalise(_legacy(a, b)), (a, b)


def test_bornes_incluses_formats_mixtes():
    _charger([
        ("b1", "2021-05-01", "A", "a", "", 1, 1, "traite", 5, "0:10:00", "", "2021-05-01T00:00:00", "x"),
        ("b2", "2021-05-31T23:59:59", "A", "a", "", 1, 1, "traite", 5, "0:10:00", "", "x", "x"),
        ("b3", "2021-06-01", "A", "a", "", 1, 1, "traite", 5, "0:10:00", "", "x", "x"),
        ("b4", None, "A", "a", "", 1, 1, "traite", 5, "0:10:00", "", "2021-05-15 08:00:00", "x"),
    ])
    assert _DashboardWorker("2021-05-01", "2021-05-31").load()["total_demandes"] == 3


def test_plage_inversee_donne_un_avertissement_sans_requete(qtbot):
    from widgets.dashboard.Main import DashboardPage
    page = DashboardPage()
    qtbot.addWidget(page)
    qtbot.waitUntil(lambda: page._chart_handler._last_data is not None, timeout=10000)
    h = page._chart_handler
    h._on_date_changed("from", h._de_to.date().addDays(5))
    assert "début" in h._lbl_sync.text()
    assert not h._refreshing


def test_refresh_silencieux_saute_le_redessin_si_rien_n_a_change(qtbot, monkeypatch):
    from widgets.dashboard import Main as M
    _charger(_jeu(50, seed=2))
    page = M.DashboardPage()
    qtbot.addWidget(page)
    h = page._chart_handler
    qtbot.waitUntil(lambda: h._last_data is not None and not h._refreshing, timeout=10000)
    appels = []
    orig = h._build_charts
    monkeypatch.setattr(h, "_build_charts", lambda d: (appels.append(1), orig(d)))
    loads = []
    orig_load = M._DashboardWorker.load
    monkeypatch.setattr(M._DashboardWorker, "load", lambda self: (loads.append(1), orig_load(self))[1])

    h.refresh(silent=True)
    qtbot.waitUntil(lambda: not h._refreshing, timeout=10000)
    assert not appels and not loads            # rien n'a changé: ni requêtes lourdes ni redessin

    db.execute_update("UPDATE accueil_demandeaccueil SET updated_at = '2099-01-01' WHERE id = 'perf2-0'")
    h.refresh(silent=True)
    qtbot.waitUntil(lambda: not h._refreshing, timeout=10000)
    assert loads and (appels or h._last_data is not None)

    h.refresh()                                # refresh visible: recharge toujours
    qtbot.waitUntil(lambda: not h._refreshing, timeout=10000)
    assert len(loads) == 2
    page.close()


def test_token_en_erreur_recharge(monkeypatch):
    _charger(_jeu(10, seed=3))
    w = _DashboardWorker("2021-01-01", "2021-12-31", skip_if_token=(1, "", ""))
    monkeypatch.setattr(db, "change_token", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    res = []
    w.finished.connect(res.append)
    w.run()
    assert res


def test_mesure_avant_apres_20000(capsys):
    _charger(_jeu(20000, seed=4, dates_nulles=False))
    a, b = "2021-01-01", "2021-12-31"
    def med(f):
        t = []
        for _ in range(5):
            t0 = time.perf_counter(); f(); t.append(time.perf_counter() - t0)
        return sorted(t)[2]
    for (x, y) in [(a, b), ("2021-03-01", "2021-03-07")]:
        avant, apres = med(lambda x=x, y=y: _legacy(x, y)), med(lambda x=x, y=y: _DashboardWorker(x, y).load())
        with capsys.disabled():
            print(f"\n[perf] 20 000 demandes {x}..{y}: avant={avant*1000:.0f} ms, apres={apres*1000:.0f} ms")
    assert apres < avant * 1.5  # période courte: l'index doit jouer (marge: machine chargée ou lente)
