"""
seed_data.py — Génération de données de test réalistes pour l'application CNPS Accueil.

Insère :
  - 9 services CNPS réalistes
  - 18 motifs de demande réalistes
  - 5 200 demandes d'accueil sur les 18 derniers mois

Usage :
    python seed_data.py
"""

import sqlite3
import random
from datetime import datetime, timedelta, time

# ── Connexion ─────────────────────────────────────────────────────────────────

DB_PATH = "db.sqlite3"
conn = sqlite3.connect(DB_PATH, timeout=30)
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA synchronous = NORMAL")


# ── Référentiels ──────────────────────────────────────────────────────────────

SERVICES = [
    ("Immatriculation",          "#3b82f6", "Ouverture et gestion des comptes assurés"),
    ("Retraite",                  "#6366f1", "Pension de retraite et droits à la retraite"),
    ("Accidents du travail",      "#ef4444", "Déclaration et indemnisation AT/MP"),
    ("Prestations familiales",    "#22c55e", "Allocations familiales et maternité"),
    ("Remboursement de soins",    "#f59e0b", "Prise en charge et remboursement médical"),
    ("Cotisations employeurs",    "#0ea5e9", "Déclaration et paiement des cotisations"),
    ("Réclamations",              "#8b5cf6", "Traitement des contestations et litiges"),
    ("Renseignements généraux",   "#64748b", "Information et orientation des usagers"),
    ("Carte CNPS / Attestation",  "#10b981", "Délivrance et renouvellement des documents"),
]

MOTIFS = [
    # Immatriculation
    ("Première immatriculation",         "normale"),
    ("Mise à jour données personnelles",  "normale"),
    ("Fusion / correction de dossier",    "haute"),
    # Retraite
    ("Demande de liquidation retraite",   "haute"),
    ("Vérification des droits retraite",  "normale"),
    ("Problème de paiement pension",      "haute"),
    # Accidents du travail
    ("Déclaration d'accident du travail", "haute"),
    ("Suivi de dossier AT",               "moyenne"),
    # Prestations familiales
    ("Demande d'allocations familiales",  "normale"),
    ("Naissance / mariage",               "normale"),
    # Remboursement de soins
    ("Remboursement de soins médicaux",   "normale"),
    ("Hospitalisation longue durée",      "haute"),
    # Cotisations
    ("Régularisation de cotisations",     "moyenne"),
    ("Attestation de paiement",           "normale"),
    # Réclamations
    ("Contestation de décision",          "haute"),
    ("Réclamation non traitement",        "moyenne"),
    # Général
    ("Renseignements généraux",           "normale"),
    ("Orientation vers autre service",    "normale"),
]

# ── Noms ivoiriens réalistes ──────────────────────────────────────────────────

PRENOMS = [
    "Adjoua", "Akissi", "Amenan", "Affoué", "Akoua", "Assoua", "Bintou",
    "Clarisse", "Djeneba", "Fatoumata", "Gnénin", "Kadiatou", "Maimouna",
    "Nafissatou", "Rokia", "Salimata", "Tenin", "Wassa", "Yah", "Zénabou",
    "Abou", "Adama", "Adrien", "Alexis", "Amadou", "Amara", "Arsène",
    "Bakary", "Barthélémy", "Boubacar", "Calixte", "Cheick", "Clément",
    "Daouda", "David", "Drissa", "Edmond", "Emmanuel", "Etienne",
    "François", "Hamidou", "Ibrahim", "Issiaka", "Jean-Baptiste",
    "Koffi", "Konan", "Lamine", "Marcel", "Mamadou", "Moussa",
    "N'Goran", "Noël", "Oumar", "Pascal", "Patrice", "Philippe",
    "Raphaël", "René", "Séydou", "Souleymane", "Thierry", "Yacouba",
]

NOMS = [
    "Abidji", "Adjoumani", "Aké", "Akindès", "Ako", "Allou", "Amani",
    "Assi", "Atta", "Attié", "Bah", "Bakayoko", "Bamba", "Baoné",
    "Ble", "Blin", "Boni", "Brou", "Camara", "Cissé", "Coulibaly",
    "Dao", "Diabaté", "Diallo", "Diarrassouba", "Diomandé", "Djè",
    "Doumbia", "Dramane", "Fofana", "Gbagbo", "Gnagne", "Gnonsoa",
    "Gon", "Guéi", "Gueu", "Gueye", "Haidara", "Ibo", "Ipou",
    "Kamagaté", "Kanté", "Konaté", "Koné", "Koua", "Kouakou",
    "Kouassi", "Kouya", "Loba", "Maïga", "Manga", "Meité",
    "N'Da", "N'Dri", "N'Guessan", "N'Zi", "Niangoran", "Niankama",
    "Okou", "Ouattara", "Ouédraogo", "Palenfo", "Sanogo", "Savané",
    "Silué", "Soro", "Sylla", "Tamini", "Tano", "Tapé", "Tiémoko",
    "Touré", "Traoré", "Vanga", "Yapo", "Yao", "Yao-Kouamé", "Zadi",
    "Zagbayou", "Zié", "Zoro", "Zouaghi",
]


def random_cnps() -> str:
    return f"CI{random.randint(100000000, 999999999)}"


def random_phone() -> str:
    prefix = random.choice(["07", "05", "01", "27", "25", "21"])
    return f"{prefix} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}"


def random_arrival(day: datetime) -> str:
    """Heure d'arrivée entre 7h30 et 16h30."""
    h = random.randint(7, 16)
    m = random.randint(0 if h > 7 else 30, 59)
    s = random.randint(0, 59)
    return time(h, m, s).strftime("%H:%M:%S")


def random_wait_minutes() -> int:
    """Distribution réaliste du temps d'attente (en minutes)."""
    r = random.random()
    if r < 0.35:     return random.randint(1, 10)    # 35 % très court
    if r < 0.60:     return random.randint(10, 20)   # 25 % dans la cible
    if r < 0.80:     return random.randint(20, 40)   # 20 % acceptable
    if r < 0.93:     return random.randint(40, 90)   # 13 % long
    return random.randint(90, 180)                   #  7 % très long


def minutes_to_hhmmss(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}:00"


def random_statut(day: datetime) -> str:
    """Statut selon l'ancienneté de la demande."""
    delta = (datetime.now() - day).days
    if delta == 0:
        r = random.random()
        if r < 0.55: return "traite"
        if r < 0.80: return "en_attente"
        return "en_cours"
    if delta <= 1:
        return random.choices(["traite", "non_traite"], weights=[85, 15])[0]
    return random.choices(["traite", "non_traite"], weights=[92, 8])[0]


# ── Peuplement des référentiels ───────────────────────────────────────────────

print("⚙️  Mise à jour des services…")
conn.execute("DELETE FROM accueil_service")
conn.executemany(
    "INSERT INTO accueil_service (nom, couleur, description, actif) VALUES (?, ?, ?, 1)",
    SERVICES,
)

print("⚙️  Mise à jour des motifs…")
conn.execute("DELETE FROM accueil_motif")
conn.executemany(
    "INSERT INTO accueil_motif (nom, priorite_defaut, description, actif) VALUES (?, ?, '', 1)",
    MOTIFS,
)
conn.commit()

# Récupérer les IDs générés
service_ids = [r[0] for r in conn.execute("SELECT id FROM accueil_service").fetchall()]
motif_ids   = [r[0] for r in conn.execute("SELECT id FROM accueil_motif").fetchall()]

# ── Génération des demandes ───────────────────────────────────────────────────

NB_DEMANDES  = 12_000
JOURS_ARRIERE = 730   # ~24 mois

print(f"⚙️  Génération de {NB_DEMANDES:,} demandes…")

# Supprimer les 2 enregistrements de test existants
conn.execute("DELETE FROM accueil_demandeaccueil")
conn.commit()

BATCH_SIZE = 500
batch = []
inserted = 0

# Poids pour la distribution des jours (jours récents plus chargés)
now = datetime.now()

for i in range(NB_DEMANDES):
    # Jour aléatoire (jours récents surreprésentés)
    weight = random.betavariate(2.5, 1.0)   # plus de poids sur les jours récents
    delta_days = int(weight * JOURS_ARRIERE)
    day = now - timedelta(days=delta_days)

    # Ne pas générer le week-end (samedi=5, dimanche=6)
    while day.weekday() >= 5:
        day -= timedelta(days=1)

    date_str     = day.strftime("%Y-%m-%d")
    created_at   = day.replace(hour=7, minute=0, second=0).isoformat()

    heure_arrivee = random_arrival(day)
    wait_min      = random_wait_minutes()
    wait_str      = minutes_to_hhmmss(wait_min)
    delai_obj     = 1 if wait_min <= 15 else 0

    statut = random_statut(day)

    heure_reception = None
    traite_le       = None
    satisfaction    = None
    commentaire     = None
    updated_at      = created_at

    if statut == "traite":
        arr_h, arr_m, arr_s = map(int, heure_arrivee.split(":"))
        rec_time = time(arr_h, arr_m, arr_s)
        total_sec = arr_h * 3600 + arr_m * 60 + arr_s + wait_min * 60
        rec_h, rem = divmod(total_sec, 3600)
        rec_m, rec_s = divmod(rem, 60)
        heure_reception = f"{min(rec_h,23):02d}:{rec_m:02d}:{rec_s:02d}"
        traite_le = day.replace(
            hour=min(rec_h, 23), minute=rec_m, second=rec_s
        ).isoformat()
        updated_at = traite_le

        if random.random() < 0.65:
            satisfaction = random.choices([1, 2, 3, 4, 5], weights=[3, 5, 15, 40, 37])[0]
            if satisfaction <= 2:
                commentaire = random.choice([
                    "Attente trop longue", "Agent peu aimable",
                    "Dossier perdu", "Mal orienté",
                ])
            elif satisfaction == 5:
                commentaire = random.choice([
                    "Excellent accueil", "Très satisfait",
                    "Service rapide et efficace", "",
                ])

    service_id = random.choice(service_ids)
    motif_id   = random.choice(motif_ids)
    priorite   = random.choices(
        ["normale", "moyenne", "haute"],
        weights=[60, 25, 15],
    )[0]

    record = (
        str(i + 1).zfill(6),          # id
        date_str,                      # date
        random.choice(NOMS),           # nom
        random.choice(PRENOMS),        # prenom
        random_cnps() if random.random() < 0.80 else "",  # numero_cnps
        service_id,                    # service_demande_id
        motif_id,                      # motif_id
        priorite,                      # priorite
        statut,                        # statut
        satisfaction,                  # satisfaction
        commentaire,                   # commentaire_satisfaction
        heure_arrivee,                 # heure_arrivee
        heure_reception,               # heure_reception
        wait_str,                      # temps_attente
        delai_obj,                     # delai_objectif
        random_phone() if random.random() < 0.70 else "",  # contacts
        None,                          # agent_accueil_id
        None,                          # observations
        created_at,                    # created_at
        updated_at,                    # updated_at
        traite_le,                     # traite_le
    )
    batch.append(record)

    if len(batch) >= BATCH_SIZE:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            """INSERT INTO accueil_demandeaccueil (
                id, date, nom, prenom, numero_cnps,
                service_demande_id, motif_id, priorite, statut,
                satisfaction, commentaire_satisfaction,
                heure_arrivee, heure_reception, temps_attente, delai_objectif,
                contacts, agent_accueil_id, observations,
                created_at, updated_at, traite_le
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            batch,
        )
        conn.execute("COMMIT")
        inserted += len(batch)
        batch.clear()
        print(f"   … {inserted:,} / {NB_DEMANDES:,} insérés")

# Dernier lot
if batch:
    conn.execute("BEGIN IMMEDIATE")
    conn.executemany(
        """INSERT INTO accueil_demandeaccueil (
            id, date, nom, prenom, numero_cnps,
            service_demande_id, motif_id, priorite, statut,
            satisfaction, commentaire_satisfaction,
            heure_arrivee, heure_reception, temps_attente, delai_objectif,
            contacts, agent_accueil_id, observations,
            created_at, updated_at, traite_le
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        batch,
    )
    conn.execute("COMMIT")
    inserted += len(batch)

conn.close()

# ── Résumé ────────────────────────────────────────────────────────────────────

conn2 = sqlite3.connect(DB_PATH)
total     = conn2.execute("SELECT COUNT(*) FROM accueil_demandeaccueil").fetchone()[0]
traites   = conn2.execute("SELECT COUNT(*) FROM accueil_demandeaccueil WHERE statut='traite'").fetchone()[0]
attente   = conn2.execute("SELECT COUNT(*) FROM accueil_demandeaccueil WHERE statut='en_attente'").fetchone()[0]
sla_ok    = conn2.execute("SELECT COUNT(*) FROM accueil_demandeaccueil WHERE delai_objectif=1").fetchone()[0]
nb_svc    = conn2.execute("SELECT COUNT(*) FROM accueil_service").fetchone()[0]
nb_mot    = conn2.execute("SELECT COUNT(*) FROM accueil_motif").fetchone()[0]
conn2.close()

print()
print("═" * 50)
print(f"  Services   : {nb_svc}")
print(f"  Motifs     : {nb_mot}")
print(f"  Demandes   : {total:,}")
print(f"    ✅ Traitées  : {traites:,} ({traites/total*100:.1f} %)")
print(f"    ⏳ En attente: {attente:,}")
print(f"    ⏱  SLA ≤15min : {sla_ok:,} ({sla_ok/total*100:.1f} %)")
print("═" * 50)
print("✅ Seeding terminé.")
