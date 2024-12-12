import sqlite3
import random
from datetime import datetime, timedelta
import os

# Konfiguration
DB_DIR = 'db'
WORKERS_DB = os.path.join(DB_DIR, 'workers.db')
TOOLS_DB = os.path.join(DB_DIR, 'lager.db')
CONSUMABLES_DB = os.path.join(DB_DIR, 'consumables.db')
LENDINGS_DB = os.path.join(DB_DIR, 'lendings.db')

# Testdaten
BEREICHE = [
    ('Technik', 40),  # 40% Wahrscheinlichkeit
    ('Kaufmännisches', 15),
    ('Verwaltung', 15),
    ('Digital und Medien', 10),
    ('Service', 10),
    ('APE', 10)
]

WERKZEUGE = [
    # Holzbearbeitung
    ('Akkuschrauber Bosch', 'Holz', 'Elektrowerkzeug'),
    ('Handkreissäge Makita', 'Holz', 'Elektrowerkzeug'),
    ('Stichsäge DeWalt', 'Holz', 'Elektrowerkzeug'),
    ('Hobel', 'Holz', 'Handwerkzeug'),
    ('Schleifmaschine Festool', 'Holz', 'Elektrowerkzeug'),
    ('Holzraspel Set', 'Holz', 'Handwerkzeug'),
    ('Stemmeisen Set', 'Holz', 'Handwerkzeug'),
    ('Holzhammer', 'Holz', 'Handwerkzeug'),
    ('Bandschleifer Makita', 'Holz', 'Elektrowerkzeug'),
    ('Tischkreissäge', 'Holz', 'Stationär'),
    ('Drechselbank', 'Holz', 'Stationär'),
    ('Oberfräse Festool', 'Holz', 'Elektrowerkzeug'),
    
    # Metallbearbeitung
    ('Schweißgerät', 'Metall', 'Elektrowerkzeug'),
    ('Winkelschleifer Bosch', 'Metall', 'Elektrowerkzeug'),
    ('Metallsäge', 'Metall', 'Handwerkzeug'),
    ('Metallfeilen Set', 'Metall', 'Handwerkzeug'),
    ('Blechschere', 'Metall', 'Handwerkzeug'),
    ('Plasmaschneider', 'Metall', 'Elektrowerkzeug'),
    ('Metallbohrer Set', 'Metall', 'Zubehör'),
    ('Standbohrmaschine', 'Metall', 'Stationär'),
    ('Drehbank', 'Metall', 'Stationär'),
    ('Metallbandsäge', 'Metall', 'Stationär')
]

VERBRAUCHSMATERIAL = [
    # Schutzausrüstung
    ('Schutzbrille', 'PSA', 50, 20, 'Stück'),
    ('Arbeitshandschuhe Gr. L', 'PSA', 100, 30, 'Paar'),
    ('Arbeitshandschuhe Gr. M', 'PSA', 100, 30, 'Paar'),
    ('Gehörschutz', 'PSA', 30, 10, 'Stück'),
    ('Schweißerhandschuhe', 'PSA', 20, 5, 'Paar'),
    ('Schweißermaske', 'PSA', 10, 3, 'Stück'),
    ('Staubmaske FFP2', 'PSA', 200, 50, 'Stück'),
    
    # Holzbearbeitung
    ('Schleifpapier Korn 80', 'Holz', 100, 30, 'Bogen'),
    ('Schleifpapier Korn 120', 'Holz', 100, 30, 'Bogen'),
    ('Schleifpapier Korn 240', 'Holz', 100, 30, 'Bogen'),
    ('Holzleim', 'Holz', 20, 5, 'Flasche'),
    ('Holzdübel 8mm', 'Holz', 500, 100, 'Stück'),
    ('Holzschrauben 4x30', 'Holz', 1000, 200, 'Stück'),
    
    # Metallbearbeitung
    ('Schweißdraht 1.0mm', 'Metall', 20, 5, 'Rolle'),
    ('Trennscheiben 125mm', 'Metall', 50, 15, 'Stück'),
    ('Schleifscheiben 125mm', 'Metall', 50, 15, 'Stück'),
    ('Metallbohrer HSS 3mm', 'Metall', 30, 10, 'Stück'),
    ('Metallbohrer HSS 5mm', 'Metall', 30, 10, 'Stück'),
    ('Kühlschmiermittel', 'Metall', 10, 3, 'Liter')
]

VORNAMEN = [
    'Alexander', 'Benjamin', 'Christian', 'Daniel', 'Erik', 'Florian', 'Georg',
    'Hannah', 'Isabel', 'Julia', 'Katharina', 'Laura', 'Marie', 'Nina',
    'Oliver', 'Paul', 'Robert', 'Stefan', 'Thomas', 'Ulrich',
    'Victoria', 'Werner', 'Xaver', 'Yvonne', 'Zoe'
]

NACHNAMEN = [
    'Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber', 'Meyer', 'Wagner',
    'Becker', 'Schulz', 'Hoffmann', 'Schäfer', 'Koch', 'Bauer', 'Richter',
    'Klein', 'Wolf', 'Schröder', 'Neumann', 'Schwarz', 'Zimmermann',
    'Braun', 'Krüger', 'Hofmann', 'Hartmann', 'Lange'
]

def generate_barcode():
    """Generiert einen 10-stelligen Barcode"""
    return str(random.randint(1000000000, 9999999999))

def create_connection(db_file):
    """Erstellt eine Datenbankverbindung"""
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(f"Fehler beim Verbindungsaufbau zu {db_file}: {e}")
        return None

def insert_workers(conn, num_workers=30):
    """Fügt Testdaten für Mitarbeiter ein"""
    used_names = set()
    workers = []
    
    while len(workers) < num_workers:
        vorname = random.choice(VORNAMEN)
        nachname = random.choice(NACHNAMEN)
        name_combo = (vorname, nachname)
        
        if name_combo not in used_names:
            used_names.add(name_combo)
            bereich = random.choices([b[0] for b in BEREICHE], 
                                   weights=[b[1] for b in BEREICHE])[0]
            email = f"{vorname.lower()}.{nachname.lower()}@firma.de"
            barcode = generate_barcode()
            workers.append((barcode, vorname, nachname, bereich, email))
    
    conn.executemany('''
        INSERT OR IGNORE INTO workers 
        (barcode, name, lastname, bereich, email)
        VALUES (?, ?, ?, ?, ?)
    ''', workers)
    conn.commit()

def insert_tools(conn):
    """Fügt Testdaten für Werkzeuge ein"""
    tools = []
    for werkzeug, bereich, typ in WERKZEUGE:
        # Erstelle 1-3 Exemplare pro Werkzeug
        for _ in range(random.randint(1, 3)):
            status = random.choices(
                ['Verfügbar', 'Ausgeliehen', 'Defekt'],
                weights=[80, 15, 5]
            )[0]
            tools.append((
                generate_barcode(),
                werkzeug,
                f'Werkstatt {bereich}',
                typ,
                status,
                None,  # image_path
                None if status != 'Defekt' else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
    
    conn.executemany('''
        INSERT OR IGNORE INTO tools 
        (barcode, gegenstand, ort, typ, status, image_path, defect_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', tools)
    conn.commit()

def insert_consumables(conn):
    """Fügt Testdaten für Verbrauchsmaterial ein"""
    consumables = []
    for bezeichnung, typ, max_bestand, min_bestand, einheit in VERBRAUCHSMATERIAL:
        aktueller_bestand = random.randint(min_bestand // 2, max_bestand)
        status = 'Verfügbar'
        if aktueller_bestand <= min_bestand:
            status = 'Nachbestellen'
        if aktueller_bestand == 0:
            status = 'Leer'
            
        consumables.append((
            generate_barcode(),
            bezeichnung,
            f'Lager {typ}',
            typ,
            status,
            min_bestand,
            aktueller_bestand,
            einheit
        ))
    
    conn.executemany('''
        INSERT OR IGNORE INTO consumables 
        (barcode, bezeichnung, ort, typ, status, 
         mindestbestand, aktueller_bestand, einheit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', consumables)
    conn.commit()

def main():
    """Hauptfunktion zum Erstellen der Testdaten"""
    # Stelle sicher, dass der DB-Ordner existiert
    os.makedirs(DB_DIR, exist_ok=True)
    
    # Mitarbeiter
    conn_workers = create_connection(WORKERS_DB)
    if conn_workers:
        insert_workers(conn_workers)
        conn_workers.close()
        print("Mitarbeiter-Testdaten erstellt")
    
    # Werkzeuge
    conn_tools = create_connection(TOOLS_DB)
    if conn_tools:
        insert_tools(conn_tools)
        conn_tools.close()
        print("Werkzeug-Testdaten erstellt")
    
    # Verbrauchsmaterial
    conn_consumables = create_connection(CONSUMABLES_DB)
    if conn_consumables:
        insert_consumables(conn_consumables)
        conn_consumables.close()
        print("Verbrauchsmaterial-Testdaten erstellt")

if __name__ == '__main__':
    main() 