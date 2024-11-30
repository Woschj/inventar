import sqlite3
import logging
from database import get_db_connection
from config import DBConfig

def init_all_databases():
    try:
        init_tools_db()
        init_consumables_db()
        init_workers_db()
        init_lendings_db()
        logging.info("Alle Datenbanken erfolgreich initialisiert")
        return True
    except Exception as e:
        logging.error(f"Fehler bei der Datenbankinitialisierung: {str(e)}")
        return False

def init_tools_db():
    with get_db_connection(DBConfig.TOOLS_DB) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS tools (
                barcode TEXT PRIMARY KEY,
                gegenstand TEXT NOT NULL,
                ort TEXT DEFAULT 'Lager',
                typ TEXT,
                status TEXT DEFAULT 'Verfügbar',
                image_path TEXT
            );
            
            CREATE TABLE IF NOT EXISTS tool_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_barcode TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                comment TEXT,
                FOREIGN KEY (tool_barcode) REFERENCES tools (barcode)
            );
        ''')
        conn.commit()

def init_consumables_db():
    with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS consumables (
                barcode TEXT PRIMARY KEY,
                artikel TEXT NOT NULL,
                menge INTEGER DEFAULT 0,
                einheit TEXT,
                mindestbestand INTEGER DEFAULT 0,
                ort TEXT DEFAULT 'Lager',
                status TEXT DEFAULT 'Verfügbar'
            );
            
            CREATE TABLE IF NOT EXISTS consumables_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumable_barcode TEXT NOT NULL,
                aenderung INTEGER NOT NULL,
                neue_menge INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                kommentar TEXT,
                FOREIGN KEY (consumable_barcode) REFERENCES consumables (barcode)
            );
        ''')
        conn.commit()

def init_workers_db():
    with get_db_connection(DBConfig.WORKERS_DB) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vorname TEXT NOT NULL,
                nachname TEXT NOT NULL,
                personalnummer TEXT UNIQUE,
                abteilung TEXT,
                aktiv BOOLEAN DEFAULT 1
            );
        ''')
        conn.commit()

def init_lendings_db():
    with get_db_connection(DBConfig.LENDINGS_DB) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS lendings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_barcode TEXT NOT NULL,
                worker_id INTEGER NOT NULL,
                ausleih_datum DATETIME DEFAULT CURRENT_TIMESTAMP,
                rueckgabe_datum DATETIME,
                status TEXT DEFAULT 'Ausgeliehen',
                FOREIGN KEY (tool_barcode) REFERENCES tools (barcode),
                FOREIGN KEY (worker_id) REFERENCES workers (id)
            );
        ''')
        conn.commit()

# ... Rest der Funktionen bleiben gleich ... 