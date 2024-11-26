import sqlite3
import random
import os

# Absolute Pfade zu den Datenbanken
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKERS_DB = os.path.join(BASE_DIR, 'workers.db')
TOOLS_DB = os.path.join(BASE_DIR, 'lager.db')
LENDINGS_DB = os.path.join(BASE_DIR, 'lendings.db')
CONSUMABLES_DB = os.path.join(BASE_DIR, 'consumables.db')

def init_dbs():
    """Erstellt alle notwendigen Datenbanktabellen"""
    databases = {
        WORKERS_DB: '''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lastname TEXT NOT NULL,
                barcode TEXT NOT NULL UNIQUE,
                bereich TEXT,
                email TEXT
            )
        ''',
        TOOLS_DB: '''
            CREATE TABLE IF NOT EXISTS tools (
                barcode TEXT PRIMARY KEY,
                gegenstand TEXT NOT NULL,
                ort TEXT DEFAULT 'Lager',
                typ TEXT,
                status TEXT DEFAULT 'Verfügbar',
                image_path TEXT
            )
        ''',
        LENDINGS_DB: '''
            CREATE TABLE IF NOT EXISTS lendings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_barcode TEXT NOT NULL,
                worker_barcode TEXT NOT NULL,
                checkout_time DATETIME NOT NULL,
                return_time DATETIME,
                amount INTEGER DEFAULT 1,
                FOREIGN KEY (tool_barcode) REFERENCES tools (barcode),
                FOREIGN KEY (worker_barcode) REFERENCES workers (barcode)
            )
        ''',
        CONSUMABLES_DB: '''
            CREATE TABLE IF NOT EXISTS consumables (
                barcode TEXT PRIMARY KEY,
                bezeichnung TEXT NOT NULL,
                ort TEXT DEFAULT 'Lager',
                typ TEXT,
                status TEXT DEFAULT 'Verfügbar',
                mindestbestand INTEGER DEFAULT 1,
                aktueller_bestand INTEGER DEFAULT 0,
                einheit TEXT DEFAULT 'Stück'
            )
        '''
    }
    
    for db_name, query in databases.items():
        try:
            conn = sqlite3.connect(db_name)
            conn.execute(query)
            conn.commit()
            conn.close()
            print(f"✓ {db_name} erfolgreich initialisiert")
        except Exception as e:
            print(f"✗ Fehler bei {db_name}: {str(e)}")

def clear_existing_data():
    """Löscht alle vorhandenen Daten"""
    print("Lösche bestehende Daten...")
    try:
        with sqlite3.connect(WORKERS_DB) as conn:
            conn.execute('DELETE FROM workers')
        with sqlite3.connect(TOOLS_DB) as conn:
            conn.execute('DELETE FROM tools')
        with sqlite3.connect(LENDINGS_DB) as conn:
            conn.execute('DELETE FROM lendings')
        with sqlite3.connect(CONSUMABLES_DB) as conn:
            conn.execute('DELETE FROM consumables')
    except Exception as e:
        print(f"Fehler beim Löschen: {str(e)}")

def create_test_data():
    """Erstellt Testdaten"""
    try:
        # Eindeutige Mitarbeiterdaten
        mitarbeiter_daten = [
            ('Alexander', 'Müller'), ('Barbara', 'Schmidt'), ('Christian', 'Weber'),
            ('Diana', 'Meyer'), ('Erik', 'Wagner'), ('Franziska', 'Becker'),
            ('Georg', 'Hoffmann'), ('Hannah', 'Koch'), ('Igor', 'Fischer'),
            ('Julia', 'Schäfer'), ('Klaus', 'Richter'), ('Laura', 'Klein'),
            ('Michael', 'Wolf'), ('Nina', 'Schröder'), ('Oliver', 'Neumann'),
            ('Patricia', 'Schwarz'), ('Quentin', 'Zimmermann'), ('Rebecca', 'Braun'),
            ('Stefan', 'Krüger'), ('Tanja', 'Hofmann'), ('Uwe', 'Werner'),
            ('Vera', 'Schmitz'), ('Walter', 'König'), ('Xenia', 'Lang'),
            ('Yvonne', 'Berger')
        ]
        
        abteilungen = ['Technik', 'Werkstatt', 'Lager', 'Büro', 'Produktion', 'Qualitätssicherung']
        
        # Komplette Werkzeugliste (100 Einträge)
        werkzeuge = [
            # Handwerkzeuge (35)
            ('Schlosserhammer 300g', 'Handwerkzeug'),
            ('Fäustel 1000g', 'Handwerkzeug'),
            ('Kreuzschlitz-Schraubendreher PH2', 'Handwerkzeug'),
            ('Schlitz-Schraubendreher 5.5mm', 'Handwerkzeug'),
            ('Wasserpumpenzange 250mm', 'Handwerkzeug'),
            ('Kombizange 180mm', 'Handwerkzeug'),
            ('Seitenschneider 160mm', 'Handwerkzeug'),
            ('Spitzzange 200mm', 'Handwerkzeug'),
            ('Bügelsäge 300mm', 'Handwerkzeug'),
            ('Metallsäge HSS', 'Handwerkzeug'),
            ('Gummihammer 450g', 'Handwerkzeug'),
            ('Vorschlaghammer 3kg', 'Handwerkzeug'),
            ('Schraubendreher-Set Torx 8-teilig', 'Handwerkzeug'),
            ('Innensechskant-Satz 1.5-10mm', 'Handwerkzeug'),
            ('Rollgabelschlüssel 300mm', 'Handwerkzeug'),
            ('Rohrzange 2"', 'Handwerkzeug'),
            ('Gripzange 250mm', 'Handwerkzeug'),
            ('Blechschere 260mm', 'Handwerkzeug'),
            ('Federspanner-Set', 'Handwerkzeug'),
            ('Schraubstock 125mm', 'Handwerkzeug'),
            ('Messschieber Digital 150mm', 'Handwerkzeug'),
            ('Wasserwaage 600mm', 'Handwerkzeug'),
            ('Wasserwaage 2000mm', 'Handwerkzeug'),
            ('Richtscheit 2m', 'Handwerkzeug'),
            ('Schonhammer Kunststoff', 'Handwerkzeug'),
            ('Ringschlüssel-Satz 6-22mm', 'Handwerkzeug'),
            ('Maulschlüssel-Satz 6-22mm', 'Handwerkzeug'),
            ('Ratschenschlüssel-Set 8-19mm', 'Handwerkzeug'),
            ('Steckschlüssel-Satz 1/2"', 'Handwerkzeug'),
            ('Steckschlüssel-Satz 1/4"', 'Handwerkzeug'),
            ('Bördelgerät', 'Handwerkzeug'),
            ('Rohrentgrater Innen/Außen', 'Handwerkzeug'),
            ('Feilen-Set 5-teilig', 'Handwerkzeug'),
            ('Drahtbürste Stahl', 'Handwerkzeug'),
            ('Drahtbürste Messing', 'Handwerkzeug'),

            # Elektrowerkzeuge (35)
            ('Akku-Bohrschrauber 18V', 'Elektrowerkzeug'),
            ('Schlagbohrmaschine 750W', 'Elektrowerkzeug'),
            ('Winkelschleifer 125mm', 'Elektrowerkzeug'),
            ('Stichsäge 650W', 'Elektrowerkzeug'),
            ('Handkreissäge 1200W', 'Elektrowerkzeug'),
            ('Bandschleifer 900W', 'Elektrowerkzeug'),
            ('Exzenterschleifer 300W', 'Elektrowerkzeug'),
            ('Heißluftpistole 2000W', 'Elektrowerkzeug'),
            ('Akku-Schlagschrauber 18V', 'Elektrowerkzeug'),
            ('Bohrhammer SDS-Plus 800W', 'Elektrowerkzeug'),
            ('Kombihammer SDS-Max 1500W', 'Elektrowerkzeug'),
            ('Tischkreissäge 2000W', 'Elektrowerkzeug'),
            ('Kappsäge 1800W', 'Elektrowerkzeug'),
            ('Dekupiersäge 120W', 'Elektrowerkzeug'),
            ('Oberfräse 1200W', 'Elektrowerkzeug'),
            ('Schwingschleifer 180W', 'Elektrowerkzeug'),
            ('Deltaschleifer 200W', 'Elektrowerkzeug'),
            ('Multifunktionswerkzeug 300W', 'Elektrowerkzeug'),
            ('Akku-Säbelsäge 18V', 'Elektrowerkzeug'),
            ('Elektrohobel 850W', 'Elektrowerkzeug'),
            ('Bandschleifer Stationär 750W', 'Elektrowerkzeug'),
            ('Tellerschleifer 600W', 'Elektrowerkzeug'),
            ('Doppelschleifer 520W', 'Elektrowerkzeug'),
            ('Poliermaschine 1200W', 'Elektrowerkzeug'),
            ('Kompressor 50L 1500W', 'Elektrowerkzeug'),
            ('Druckluft-Nagler', 'Elektrowerkzeug'),
            ('Druckluft-Tacker', 'Elektrowerkzeug'),
            ('Industriestaubsauger 1200W', 'Elektrowerkzeug'),
            ('Nass-Trockensauger 1400W', 'Elektrowerkzeug'),
            ('Schweißgerät MIG 200A', 'Elektrowerkzeug'),
            ('Schweißgerät WIG 200A', 'Elektrowerkzeug'),
            ('Plasmaschneider 40A', 'Elektrowerkzeug'),
            ('Akku-Winkelschleifer 18V', 'Elektrowerkzeug'),
            ('Akku-Kettensäge 36V', 'Elektrowerkzeug'),
            ('Akku-Heckenschere 18V', 'Elektrowerkzeug'),

            # Messwerkzeuge und Prüfgeräte (15)
            ('Digitales Multimeter', 'Messwerkzeug'),
            ('Spannungsprüfer', 'Messwerkzeug'),
            ('Laser-Entfernungsmesser', 'Messwerkzeug'),
            ('Kreuzlinienlaser', 'Messwerkzeug'),
            ('Rotationslaser', 'Messwerkzeug'),
            ('Wärmebildkamera', 'Messwerkzeug'),
            ('Endoskop-Kamera', 'Messwerkzeug'),
            ('Schallpegelmessgerät', 'Messwerkzeug'),
            ('Feuchtigkeitsmessgerät', 'Messwerkzeug'),
            ('Infrarot-Thermometer', 'Messwerkzeug'),
            ('Druckmessgerät', 'Messwerkzeug'),
            ('Drehzahlmesser', 'Messwerkzeug'),
            ('pH-Messgerät', 'Messwerkzeug'),
            ('Leitungssuchgerät', 'Messwerkzeug'),
            ('Materialstärkenmessgerät', 'Messwerkzeug'),

            # Spezialwerkzeuge (15)
            ('Hydraulischer Wagenheber 3t', 'Spezialwerkzeug'),
            ('Kettenzug 1000kg', 'Spezialwerkzeug'),
            ('Rohrbieger hydraulisch', 'Spezialwerkzeug'),
            ('Kernbohrmaschine', 'Spezialwerkzeug'),
            ('Rohrreinigungsmaschine', 'Spezialwerkzeug'),
            ('Schweißpositionierer', 'Spezialwerkzeug'),
            ('Magnetbohrständer', 'Spezialwerkzeug'),
            ('Gewindeschneidmaschine', 'Spezialwerkzeug'),
            ('Blechrundbiegemaschine', 'Spezialwerkzeug'),
            ('Plattenheber', 'Spezialwerkzeug'),
            ('Glashebervorrichtung', 'Spezialwerkzeug'),
            ('Rohrbiegewerkzeug-Set', 'Spezialwerkzeug'),
            ('Abpressvorrichtung', 'Spezialwerkzeug'),
            ('Drehmomentschlüssel 40-200Nm', 'Spezialwerkzeug'),
            ('Nietpistole Hydraulisch', 'Spezialwerkzeug')
        ]
        
        # Verbrauchsmaterial (20 Einträge)
        verbrauchsmaterial = [
            ('Holzschrauben 4x30', 'Schrauben', 1000, 'Stück'),
            ('Spanplattenschrauben 4x40', 'Schrauben', 800, 'Stück'),
            ('Dübel 6mm Kunststoff', 'Dübel', 500, 'Stück'),
            ('Dübel 8mm Kunststoff', 'Dübel', 500, 'Stück'),
            ('Isolierband schwarz', 'Elektromaterial', 50, 'Rolle'),
            ('Gewebeband silber', 'Klebeband', 30, 'Rolle'),
            ('Malerkrepp 50mm', 'Klebeband', 40, 'Rolle'),
            ('Arbeitshandschuhe Gr. 9', 'Schutzausrüstung', 100, 'Paar'),
            ('Einweghandschuhe Nitril Gr. M', 'Schutzausrüstung', 200, 'Stück'),
            ('Schutzbrille klar', 'Schutzausrüstung', 50, 'Stück'),
            ('Gehörschutz 27dB', 'Schutzausrüstung', 40, 'Stück'),
            ('Staubmaske FFP2', 'Schutzausrüstung', 100, 'Stück'),
            ('WD-40 400ml', 'Schmiermittel', 24, 'Dose'),
            ('Mehrzweckfett 400g', 'Schmiermittel', 20, 'Kartusche'),
            ('Reinigungstücher', 'Reinigung', 150, 'Stück'),
            ('Baumwolllappen', 'Reinigung', 100, 'kg'),
            ('Kabelbinder 200mm', 'Befestigung', 500, 'Stück'),
            ('Schleifpapier K80', 'Schleifmittel', 100, 'Bogen'),
            ('Schleifpapier K120', 'Schleifmittel', 100, 'Bogen'),
            ('Schleifpapier K240', 'Schleifmittel', 100, 'Bogen')
        ]

        # Mitarbeiter einfügen
        with sqlite3.connect(WORKERS_DB) as conn:
            for i, (vorname, nachname) in enumerate(mitarbeiter_daten):
                barcode = f'M{str(i+1).zfill(4)}'
                bereich = random.choice(abteilungen)
                email = f"{vorname.lower()}.{nachname.lower()}@firma.de"
                
                conn.execute('''
                    INSERT INTO workers (name, lastname, barcode, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (vorname, nachname, barcode, bereich, email))
        
        # Werkzeuge einfügen
        with sqlite3.connect(TOOLS_DB) as conn:
            for i, (name, typ) in enumerate(werkzeuge):
                barcode = f'W{str(i+1).zfill(4)}'
                conn.execute('''
                    INSERT INTO tools (barcode, gegenstand, typ, status)
                    VALUES (?, ?, ?, 'Verfügbar')
                ''', (barcode, name, typ))
        
        # Verbrauchsmaterial einfügen
        with sqlite3.connect(CONSUMABLES_DB) as conn:
            for i, (name, typ, bestand, einheit) in enumerate(verbrauchsmaterial):
                barcode = f'V{str(i+1).zfill(4)}'
                conn.execute('''
                    INSERT INTO consumables 
                    (barcode, bezeichnung, typ, aktueller_bestand, mindestbestand, einheit)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (barcode, name, typ, bestand, bestand//5, einheit))
        
        print("✓ Testdaten erfolgreich erstellt")
        
    except Exception as e:
        print(f"Fehler beim Erstellen der Testdaten: {str(e)}")

if __name__ == "__main__":
    print("Initialisiere Datenbanken...")
    init_dbs()
    print("\nLösche alte Daten...")
    clear_existing_data()
    print("\nErstelle neue Testdaten...")
    create_test_data() 