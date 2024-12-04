import os
import sqlite3
import json
from config import Config

def migrate_existing_dbs():
    try:
        # Stelle sicher, dass das Instance-Verzeichnis existiert
        os.makedirs(Config.INSTANCE_PATH, exist_ok=True)
        
        # Setup System-DB
        system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
        with sqlite3.connect(system_db) as conn:
            # Departments
            conn.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            
            # Standard-Departments
            departments = [
                ("technik", "Technik"),
                ("verwaltung", "Verwaltung"),
                ("lager", "Lager")
            ]
            
            for dept in departments:
                conn.execute("INSERT OR IGNORE INTO departments (id, name) VALUES (?, ?)", dept)
            
            # Categories
            conn.execute("DROP TABLE IF EXISTS categories")
            conn.execute("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    db_name TEXT NOT NULL,
                    schema TEXT NOT NULL,
                    FOREIGN KEY (department) REFERENCES departments(id)
                )
            """)
            
            # Standard-Kategorien mit Schemas
            categories = [
                ("Werkzeuge", "technik", "tools.db", """
                    CREATE TABLE IF NOT EXISTS tools (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        status TEXT DEFAULT 'Verfügbar',
                        location TEXT
                    )
                """),
                ("Verbrauchsmaterial", "lager", "consumables.db", """
                    CREATE TABLE IF NOT EXISTS consumables (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        quantity INTEGER DEFAULT 0,
                        unit TEXT
                    )
                """),
                ("Mitarbeiter", "verwaltung", "workers.db", """
                    CREATE TABLE IF NOT EXISTS workers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        position TEXT,
                        department TEXT,
                        status TEXT DEFAULT 'Aktiv'
                    )
                """),
                ("Ausleihen", "verwaltung", "lendings.db", """
                    CREATE TABLE IF NOT EXISTS lendings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT NOT NULL,
                        worker_name TEXT NOT NULL,
                        lend_date DATE NOT NULL,
                        return_date DATE,
                        status TEXT DEFAULT 'Ausgeliehen'
                    )
                """)
            ]
            
            # Füge Kategorien ein und erstelle die Datenbanken
            for cat in categories:
                conn.execute("""
                    INSERT INTO categories (name, department, db_name, schema)
                    VALUES (?, ?, ?, ?)
                """, cat)
                
                # Erstelle die Kategorie-Datenbank und Tabelle
                db_path = os.path.join(Config.INSTANCE_PATH, cat[2])
                with sqlite3.connect(db_path) as cat_conn:
                    cat_conn.executescript(cat[3])
                    cat_conn.commit()
            
            conn.commit()
            
            # Beispieldaten für jede Kategorie
            example_data = {
                "tools.db": [
                    ("Hammer", "Standardhammer für allgemeine Arbeiten", "Verfügbar", "Werkzeugschrank 1"),
                    ("Schraubendreher-Set", "Phillips und Schlitz, verschiedene Größen", "Verfügbar", "Werkzeugschrank 2"),
                    ("Bohrmaschine", "Makita 18V", "Ausgeliehen", "Werkzeugschrank 3"),
                    ("Säge", "Handsäge für Holz", "Verfügbar", "Werkzeugschrank 1")
                ],
                "consumables.db": [
                    ("Schrauben 4x30", "Holzschrauben verzinkt", 500, "Stück"),
                    ("Klebeband", "Gewebeband silber", 20, "Rollen"),
                    ("Arbeitshandschuhe", "Größe L", 15, "Paar"),
                    ("Putzlappen", "Mikrofaser", 100, "Stück")
                ],
                "workers.db": [
                    ("Max Mustermann", "Ausbilder", "Technik", "Aktiv"),
                    ("Anna Schmidt", "Verwaltung", "Verwaltung", "Aktiv"),
                    ("Peter Meyer", "Lagerist", "Lager", "Aktiv")
                ],
                "lendings.db": [
                    ("Bohrmaschine", "Max Mustermann", "2024-12-01", None, "Ausgeliehen"),
                    ("Messgerät", "Anna Schmidt", "2024-12-02", "2024-12-03", "Zurückgegeben")
                ]
            }
            
            # Füge Beispieldaten in die Datenbanken ein
            for db_name, data in example_data.items():
                db_path = os.path.join(Config.INSTANCE_PATH, db_name)
                with sqlite3.connect(db_path) as cat_conn:
                    if db_name == "tools.db":
                        cat_conn.executemany("""
                            INSERT INTO tools (name, description, status, location)
                            VALUES (?, ?, ?, ?)
                        """, data)
                    elif db_name == "consumables.db":
                        cat_conn.executemany("""
                            INSERT INTO consumables (name, description, quantity, unit)
                            VALUES (?, ?, ?, ?)
                        """, data)
                    elif db_name == "workers.db":
                        cat_conn.executemany("""
                            INSERT INTO workers (name, position, department, status)
                            VALUES (?, ?, ?, ?)
                        """, data)
                    elif db_name == "lendings.db":
                        cat_conn.executemany("""
                            INSERT INTO lendings (item_name, worker_name, lend_date, return_date, status)
                            VALUES (?, ?, ?, ?, ?)
                        """, data)
                    cat_conn.commit()
            
            print("Migration und Beispieldaten erfolgreich eingefügt!")
            return True
            
    except Exception as e:
        print(f"Fehler bei der Migration: {str(e)}")
        return False

if __name__ == '__main__':
    migrate_existing_dbs() 