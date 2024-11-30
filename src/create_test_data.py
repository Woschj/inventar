import sqlite3
import random
import os
from app import DBConfig, get_db_connection
import logging
from datetime import datetime, timedelta

# Absolute Pfade zu den Datenbanken
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKERS_DB = os.path.join(BASE_DIR, 'workers.db')
TOOLS_DB = os.path.join(BASE_DIR, 'lager.db')
LENDINGS_DB = os.path.join(BASE_DIR, 'lendings.db')
CONSUMABLES_DB = os.path.join(BASE_DIR, 'consumables.db')

def init_dbs():
    """Erstellt alle notwendigen Datenbanktabellen"""
    try:
        # Workers Database
        with sqlite3.connect(DBConfig.WORKERS_DB) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS workers (
                    barcode TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    bereich TEXT,
                    email TEXT
                );
                
                CREATE TABLE IF NOT EXISTS workers_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_barcode TEXT NOT NULL,
                    action TEXT NOT NULL,
                    changed_fields TEXT,
                    changed_by TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (worker_barcode) REFERENCES workers(barcode)
                );
                
                CREATE TABLE IF NOT EXISTS deleted_workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    name TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    barcode TEXT NOT NULL,
                    bereich TEXT,
                    email TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            ''')
            
        # Tools Database
        with sqlite3.connect(DBConfig.TOOLS_DB) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS tools (
                    barcode TEXT PRIMARY KEY,
                    gegenstand TEXT NOT NULL,
                    ort TEXT DEFAULT 'Lager',
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    image_path TEXT
                );
                
                CREATE TABLE IF NOT EXISTS tools_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_barcode TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    changed_fields TEXT,
                    changed_by TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
                );
                
                CREATE TABLE IF NOT EXISTS tool_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_barcode TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    comment TEXT,
                    changed_by TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
                );
                
                CREATE TABLE IF NOT EXISTS deleted_tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT NOT NULL,
                    gegenstand TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    status TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            ''')
            
        # Consumables Database
        with sqlite3.connect(DBConfig.CONSUMABLES_DB) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS consumables (
                    barcode TEXT PRIMARY KEY,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT DEFAULT 'Lager',
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    mindestbestand INTEGER DEFAULT 0,
                    aktueller_bestand INTEGER DEFAULT 0,
                    einheit TEXT DEFAULT 'Stück',
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS consumables_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consumable_barcode TEXT NOT NULL,
                    worker_barcode TEXT NOT NULL,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    old_stock INTEGER NOT NULL,
                    new_stock INTEGER NOT NULL,
                    changed_by TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (consumable_barcode) REFERENCES consumables(barcode)
                );
                
                CREATE TABLE IF NOT EXISTS deleted_consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    barcode TEXT NOT NULL,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    mindestbestand INTEGER,
                    letzter_bestand INTEGER,
                    einheit TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            ''')
            
        # Lendings Database
        with sqlite3.connect(DBConfig.LENDINGS_DB) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS lendings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_barcode TEXT NOT NULL,
                    item_barcode TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    checkout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    return_time DATETIME,
                    amount INTEGER DEFAULT 1,
                    old_stock INTEGER,
                    new_stock INTEGER,
                    FOREIGN KEY (worker_barcode) REFERENCES workers(barcode)
                );
            ''')
            
        print("✓ Alle Datenbanken erfolgreich initialisiert")
        return True
        
    except Exception as e:
        print(f"✗ Fehler bei der Datenbankinitialisierung: {str(e)}")
        return False

def clear_existing_data():
    """Löscht alle vorhandenen Daten"""
    print("Lösche bestehende Daten...")
    try:
        with sqlite3.connect(WORKERS_DB) as conn:
            conn.execute('DELETE FROM workers')
            conn.execute('DELETE FROM workers_history')
        with sqlite3.connect(TOOLS_DB) as conn:
            conn.execute('DELETE FROM tools')
            conn.execute('DELETE FROM tools_history')
            conn.execute('DELETE FROM tool_status_history')
            conn.execute('DELETE FROM deleted_tools')
        with sqlite3.connect(LENDINGS_DB) as conn:
            conn.execute('DELETE FROM lendings')
        with sqlite3.connect(CONSUMABLES_DB) as conn:
            conn.execute('DELETE FROM consumables')
    except Exception as e:
        print(f"Fehler beim Löschen: {str(e)}")

def check_if_empty(conn, table_name):
    """Prüft ob eine Tabelle leer ist"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    return count == 0

def create_random_date(start_date, end_date):
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)

def create_test_data():
    try:
        # Mitarbeiter-Testdaten
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            if check_if_empty(conn, 'workers'):
                first_names = ['Max', 'Anna', 'Peter', 'Lisa', 'Tom', 'Sarah', 'Paul', 'Marie', 
                             'Felix', 'Laura', 'David', 'Julia', 'Simon', 'Emma', 'Lucas', 
                             'Sophie', 'Michael', 'Elena', 'Andreas', 'Katharina']
                last_names = ['Müller', 'Schmidt', 'Weber', 'Meyer', 'Wagner', 'Becker', 'Schulz', 
                            'Hoffmann', 'Koch', 'Richter', 'Klein', 'Wolf', 'Schröder', 'Neumann',
                            'Schwarz', 'Zimmermann', 'Braun', 'Krüger', 'Hofmann', 'Hartmann']
                bereiche = ['APE', 'Medien und Digitales', 'Kaufmännisch', 'Service', 'Technik']
                bereich_weights = [0.3, 0.2, 0.2, 0.15, 0.15]  # Gewichtung der Abteilungen
                
                test_workers = []
                for i in range(250):
                    barcode = f'M{str(i+1).zfill(4)}'
                    name = random.choice(first_names)
                    lastname = random.choice(last_names)
                    bereich = random.choices(bereiche, weights=bereich_weights)[0]
                    email = f"{name.lower()}.{lastname.lower()}@btz.de"
                    test_workers.append((barcode, name, lastname, bereich, email))
                
                conn.executemany('''
                    INSERT OR IGNORE INTO workers 
                    (barcode, name, lastname, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', test_workers)
                conn.commit()
                logging.info("250 Mitarbeiter-Testdaten erfolgreich eingefügt")

        # Werkzeug-Testdaten für Holz- und Metallwerkstatt
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            if check_if_empty(conn, 'tools'):
                werkzeuge = [
                    # Holzwerkstatt
                    ('Handhobel', 'Holzwerkzeug', 15),
                    ('Stechbeitel', 'Holzwerkzeug', 20),
                    ('Holzraspel', 'Holzwerkzeug', 15),
                    ('Schreinerwinkel', 'Messwerkzeug', 10),
                    ('Bandschleifer', 'Elektrowerkzeug', 5),
                    ('Kreissäge', 'Elektrowerkzeug', 3),
                    ('Dekupiersäge', 'Elektrowerkzeug', 4),
                    ('Drechselbank', 'Maschine', 2),
                    # Metallwerkstatt
                    ('Metallfeile', 'Metallwerkzeug', 25),
                    ('Schraubstock', 'Metallwerkzeug', 15),
                    ('Metallsäge', 'Metallwerkzeug', 10),
                    ('Schweißgerät', 'Elektrowerkzeug', 5),
                    ('Metallbohrer-Set', 'Metallwerkzeug', 8),
                    ('Drehmaschine', 'Maschine', 2),
                    ('Fräsmaschine', 'Maschine', 2),
                    # Allgemein
                    ('Akkuschrauber', 'Elektrowerkzeug', 20),
                    ('Messschieber', 'Messwerkzeug', 15),
                    ('Hammer', 'Handwerkzeug', 30),
                    ('Schraubendreher-Set', 'Handwerkzeug', 25),
                    ('Wasserwaage', 'Messwerkzeug', 10)
                ]
                
                test_tools = []
                ausgeliehene_werkzeuge = []
                tool_counter = 1

                for werkzeug, typ, anzahl in werkzeuge:
                    for i in range(anzahl):
                        barcode = f'W{str(tool_counter).zfill(4)}'
                        tool_counter += 1
                        
                        status = random.choices(
                            ['Verfügbar', 'Ausgeliehen', 'In Reparatur', 'Defekt'],
                            weights=[0.6, 0.25, 0.1, 0.05]
                        )[0]
                        
                        test_tools.append((barcode, f"{werkzeug} {i+1}", 
                                         f"Werkstatt {random.choice(['A','B','C'])}", 
                                         typ, status, None))
                        
                        if status == 'Ausgeliehen':
                            ausgeliehene_werkzeuge.append(barcode)

                conn.executemany('''
                    INSERT OR IGNORE INTO tools 
                    (barcode, gegenstand, ort, typ, status, image_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', test_tools)
                conn.commit()
                logging.info(f"{len(test_tools)} Werkzeug-Testdaten erfolgreich eingefügt")

        # Verbrauchsmaterial mit realistischen Beständen
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            if check_if_empty(conn, 'consumables'):
                materialien = [
                    # Holzwerkstatt
                    ('Holzschrauben', 'Befestigung', 1000, 'Stück', 'hoch'),
                    ('Holzdübel', 'Befestigung', 500, 'Stück', 'mittel'),
                    ('Schleifpapier', 'Verbrauch', 200, 'Stück', 'hoch'),
                    ('Holzleim', 'Klebstoff', 20, 'Flasche', 'mittel'),
                    # Metallwerkstatt
                    ('Metallschrauben', 'Befestigung', 1000, 'Stück', 'hoch'),
                    ('Schweißdraht', 'Schweißen', 50, 'Rolle', 'mittel'),
                    ('Metallbohrer', 'Werkzeug', 100, 'Stück', 'hoch'),
                    ('Kühlmittel', 'Verbrauch', 30, 'Liter', 'niedrig'),
                    # Allgemein
                    ('Arbeitshandschuhe', 'Schutz', 100, 'Paar', 'hoch'),
                    ('Schutzbrillen', 'Schutz', 50, 'Stück', 'niedrig'),
                    ('Reinigungstücher', 'Reinigung', 200, 'Stück', 'hoch'),
                    ('Maschinenöl', 'Wartung', 20, 'Liter', 'niedrig')
                ]
                
                test_consumables = []
                for material, typ, min_bestand, einheit, verbrauch in materialien:
                    for i in range(random.randint(3, 8)):
                        barcode = f'V{str(len(test_consumables)+1).zfill(4)}'
                        bezeichnung = f"{material} Typ-{random.randint(1,5)}"
                        ort = f"Lager {random.choice(['A','B','C'])}-{random.randint(1,5)}"
                        
                        if verbrauch == 'hoch':
                            aktueller_bestand = random.randint(
                                int(min_bestand * 0.2), 
                                int(min_bestand * 1.5)
                            )
                        elif verbrauch == 'mittel':
                            aktueller_bestand = random.randint(
                                int(min_bestand * 0.5), 
                                int(min_bestand * 2)
                            )
                        else:  # niedrig
                            aktueller_bestand = random.randint(
                                int(min_bestand * 0.8), 
                                int(min_bestand * 3)
                            )
                        
                        test_consumables.append((
                            barcode, bezeichnung, ort, typ, 'Verfügbar',
                            min_bestand, aktueller_bestand, einheit
                        ))

                conn.executemany('''
                    INSERT OR IGNORE INTO consumables 
                    (barcode, bezeichnung, ort, typ, status, 
                     mindestbestand, aktueller_bestand, einheit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', test_consumables)
                conn.commit()
                logging.info(f"{len(test_consumables)} Verbrauchsmaterial-Testdaten erfolgreich eingefügt")

        # Gemeinsame Ausleihen/Ausgaben-Tabelle
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute('DELETE FROM lendings')  # Lösche alte Testdaten
            
            # Hole alle Worker-Barcodes
            with get_db_connection(DBConfig.WORKERS_DB) as worker_conn:
                workers = [row['barcode'] for row in worker_conn.execute('SELECT barcode FROM workers').fetchall()]
            
            all_lendings = []
            
            # Werkzeug-Ausleihen
            with get_db_connection(DBConfig.TOOLS_DB) as tool_conn:
                tools = [row['barcode'] for row in 
                        tool_conn.execute("SELECT barcode FROM tools WHERE status = 'Ausgeliehen'").fetchall()]
                
                for tool_barcode in tools:
                    worker_barcode = random.choice(workers)
                    days_ago = random.randint(1, 30)
                    checkout_date = datetime.now() - timedelta(days=days_ago)
                    
                    all_lendings.append((
                        worker_barcode, 
                        tool_barcode,
                        'tool',
                        checkout_date,
                        None,  # return_time
                        1,     # amount
                        None,  # old_stock
                        None   # new_stock
                    ))
            
            # Verbrauchsmaterial-Ausgaben
            with get_db_connection(DBConfig.CONSUMABLES_DB) as cons_conn:
                consumables = [dict(row) for row in cons_conn.execute('SELECT * FROM consumables').fetchall()]
                
                for consumable in consumables:
                    num_ausgaben = random.randint(1, 5)
                    current_stock = max(0, consumable['aktueller_bestand'])  # Stelle sicher, dass der Anfangsbestand nicht negativ ist
                    
                    for _ in range(num_ausgaben):
                        worker_barcode = random.choice(workers)
                        days_ago = random.randint(1, 30)
                        ausgabe_date = datetime.now() - timedelta(days=days_ago)
                        
                        # Berechne maximale Entnahmemenge
                        if current_stock > 0:
                            max_amount = min(
                                int(current_stock * 0.2),  # Maximal 20% des aktuellen Bestands
                                current_stock  # Aber nie mehr als verfügbar ist
                            )
                            amount = random.randint(1, max(1, max_amount))
                            
                            old_stock = current_stock
                            current_stock = max(0, current_stock - amount)  # Verhindere negative Bestände
                            
                            all_lendings.append((
                                worker_barcode,
                                consumable['barcode'],
                                'consumable',
                                ausgabe_date,
                                ausgabe_date,  # return_time gleich checkout_time bei Verbrauchsmaterial
                                amount,
                                old_stock,
                                current_stock
                            ))
                            
                            # Aktualisiere den Bestand in der Consumables-Tabelle
                            cons_conn.execute('''
                                UPDATE consumables 
                                SET aktueller_bestand = ? 
                                WHERE barcode = ?
                            ''', (current_stock, consumable['barcode']))
            
            # Füge alle Ausleihen/Ausgaben ein
            conn.executemany('''
                INSERT INTO lendings 
                (worker_barcode, item_barcode, item_type, checkout_time, 
                 return_time, amount, old_stock, new_stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', all_lendings)
            conn.commit()
            logging.info(f"{len(all_lendings)} Ausleihen/Ausgaben erstellt")

    except Exception as e:
        logging.error(f"Fehler beim Erstellen der Testdaten: {str(e)}")
        raise

if __name__ == "__main__":
    print("Initialisiere Datenbanken...")
    init_dbs()
    print("\nLösche alte Daten...")
    clear_existing_data()
    print("\nErstelle neue Testdaten...")
    create_test_data() 