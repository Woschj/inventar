import sqlite3
import logging
from config import DBConfig
from core.database.connection import get_db_connection

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
            
            CREATE TABLE IF NOT EXISTS deleted_tools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                gegenstand TEXT NOT NULL,
                ort TEXT,
                typ TEXT,
                status TEXT,
                image_path TEXT,
                deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_by TEXT
            );
        ''')
        conn.commit()

def init_consumables_db():
    with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
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
        conn.commit()

def init_workers_db():
    with get_db_connection(DBConfig.WORKERS_DB) as conn:
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
        conn.commit()

def init_lendings_db():
    with get_db_connection(DBConfig.LENDINGS_DB) as conn:
        conn.execute('''
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
            )
        ''')
        conn.commit()
