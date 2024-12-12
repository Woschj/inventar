from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.exceptions import BadRequest
import sqlite3
from datetime import datetime
import os
import traceback
from functools import wraps
import logging
from logging.handlers import TimedRotatingFileHandler
import json
from routes import export_bp
import sys
import sqlite3
import logging
import traceback
from flask import jsonify, session
import time



app = Flask(__name__)
app.secret_key = 'dein_geheimer_schlüssel'
app.config['ADMIN_PASSWORD'] = 'admin'




# Logging Setup
def setup_logging():
    # Erstelle logs Verzeichnis, falls es nicht existiert
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Konfiguriere verschiedene Logger für unterschiedliche Zwecke
    loggers = {
        'user_actions': setup_logger('user_actions', os.path.join(log_dir, 'user_actions.log')),
        'errors': setup_logger('errors', os.path.join(log_dir, 'errors.log')),
        'database': setup_logger('database', os.path.join(log_dir, 'database.log')),
        'security': setup_logger('security', os.path.join(log_dir, 'security.log'))
    }
    return loggers

def setup_logger(name, log_file):
    """Erstellt einen konfigurierten Logger"""
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    return logger

# Erstelle die Logger
loggers = setup_logging()

# Decorator für Route-Logging
def log_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Log vor der Ausführung
        loggers['user_actions'].info(
            f"Route aufgerufen: {request.endpoint} - "
            f"Methode: {request.method} - "
            f"IP: {request.remote_addr} - "
            f"User-Agent: {request.user_agent} - "
            f"Args: {kwargs}"
        )
        
        # Log Form-Daten, falls vorhanden
        if request.form:
            # Filtere sensitive Daten
            safe_form = {k: v for k, v in request.form.items() if 'password' not in k.lower()}
            loggers['user_actions'].info(f"Form-Daten: {safe_form}")
            
        # Log Query-Parameter
        if request.args:
            loggers['user_actions'].info(f"Query-Parameter: {dict(request.args)}")
            
        try:
            result = f(*args, **kwargs)
            return result
        except Exception as e:
            # Log Fehler
            loggers['errors'].error(
                f"Fehler in {request.endpoint}: {str(e)}",
                exc_info=True
            )
            raise
    return decorated_function

# Decorator für DB-Operationen
def log_db_operation(operation):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = f(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                loggers['database'].info(
                    f"DB Operation: {operation} - "
                    f"Dauer: {duration:.2f}s - "
                    f"Erfolgreich: Ja"
                )
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                loggers['database'].error(
                    f"DB Operation: {operation} - "
                    f"Dauer: {duration:.2f}s - "
                    f"Fehler: {str(e)}"
                )
                raise
        return wrapper
    return decorator

def get_tool_lendings(barcode):
    try:
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            
            lendings = conn.execute('''
                SELECT 
                    l.*,
                    w.name || ' ' || w.lastname as worker_name,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                    strftime('%d.%m.%Y %H:%M', l.return_time) as return_time
                FROM lendings l
                LEFT JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                WHERE l.item_barcode = ? AND l.item_type = 'tool'
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()
            
            return lendings
    except Exception as e:
        logging.error(f"Fehler beim Laden der Ausleihhistorie: {str(e)}")
        return []

def get_tool_status_history(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            history = conn.execute('''
                SELECT 
                    *,
                    strftime('%d.%m.%Y %H:%M', timestamp) as formatted_time
                FROM tool_status_history 
                WHERE tool_barcode = ?
                ORDER BY timestamp DESC
            ''', (barcode,)).fetchall()
            
            return history
    except Exception as e:
        logging.error(f"Fehler beim Laden des Statusverlaufs: {str(e)}")
        return []

@app.route('/tool/<barcode>')
@log_route
def tool_details(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', (barcode,)).fetchone()
            if not tool:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('index'))
                
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers ORDER BY name').fetchall()
            
        lendings = get_tool_lendings(barcode)
        status_history = get_tool_status_history(barcode)
        
        return render_template('tool_details.html', 
                             tool=tool,
                             workers=workers,
                             lendings=lendings,
                             status_history=status_history)
                             
    except Exception as e:
        logging.error(f"Fehler beim Laden der Werkzeugdetails: {str(e)}")
        flash('Fehler beim Laden der Werkzeugdetails', 'error')
        return redirect(url_for('index'))


# Konstanten für Datenbank
class DBConfig:
    # Pfad zum src-Verzeichnis
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    # Pfad zum db-Verzeichnis innerhalb von src
    DB_DIR = os.path.join(SRC_DIR, 'db')
    
    # Stelle sicher, dass der db Ordner existiert
    os.makedirs(DB_DIR, exist_ok=True)
    
    WORKERS_DB = os.path.join(DB_DIR, 'workers.db')
    TOOLS_DB = os.path.join(DB_DIR, 'lager.db')
    LENDINGS_DB = os.path.join(DB_DIR, 'lendings.db')
    CONSUMABLES_DB = os.path.join(DB_DIR, 'consumables.db')
    SYSTEM_DB = os.path.join(DB_DIR, 'system_logs.db')
    
    # Schema Definitionen
    SCHEMAS = {
        WORKERS_DB: {
            'workers': '''
                CREATE TABLE IF NOT EXISTS workers (
                    barcode TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    bereich TEXT,
                    email TEXT
                );
            ''',
            'deleted_workers': '''
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
            '''
        },
        TOOLS_DB: {
            'tools': '''
                CREATE TABLE IF NOT EXISTS tools (
                    barcode TEXT PRIMARY KEY,
                    gegenstand TEXT NOT NULL,
                    ort TEXT DEFAULT 'Lager',
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    image_path TEXT,
                    defect_date DATETIME
                );
            ''',
            'deleted_tools': '''
                CREATE TABLE IF NOT EXISTS deleted_tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT NOT NULL,
                    gegenstand TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    status TEXT,
                    image_path TEXT,
                    defect_date DATETIME,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            ''',
            'tools_history': '''
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
            ''',
            'tool_status_history': '''
                CREATE TABLE IF NOT EXISTS tool_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_barcode TEXT NOT NULL,
                    action TEXT NOT NULL,
                    worker_barcode TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''',
        },
        LENDINGS_DB: {
            'lendings': '''
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
            '''
        },
        CONSUMABLES_DB: {
            'consumables': '''
                CREATE TABLE IF NOT EXISTS consumables (
                    barcode TEXT PRIMARY KEY,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT DEFAULT 'Lager',
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    mindestbestand INTEGER DEFAULT 0,
                    aktueller_bestand INTEGER DEFAULT 0,
                    einheit TEXT DEFAULT 'Stück'
                );
            ''',
            'deleted_consumables': '''
                CREATE TABLE IF NOT EXISTS deleted_consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_barcode TEXT NOT NULL,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    mindestbestand INTEGER,
                    aktueller_bestand INTEGER,
                    einheit TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            '''
        },
        SYSTEM_DB: {
            'system_logs': '''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    user TEXT,
                    affected_item TEXT,
                    item_type TEXT,
                    details TEXT
                );
            '''
        }
    }

    @classmethod
    def init_database(cls, db_path):
        """Initialisiert eine einzelne Datenbank mit allen ihren Tabellen"""
        try:
            with sqlite3.connect(db_path) as conn:
                for table_name, schema in cls.SCHEMAS[db_path].items():
                    conn.execute(schema)
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Fehler bei der Initialisierung von {db_path}: {str(e)}")
            return False

    @classmethod
    def verify_database_structure(cls, db_path):
        """Überprüft und aktualisiert die Datenbankstruktur"""
        try:
            with sqlite3.connect(db_path) as conn:
                # Hole existierende Tabellen
                existing_tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                existing_tables = [table[0] for table in existing_tables]

                # Überprüfe und erstelle fehlende Tabellen
                for table_name, schema in cls.SCHEMAS[db_path].items():
                    if table_name not in existing_tables:
                        logging.info(f"Erstelle fehlende Tabelle: {table_name}")
                        conn.execute(schema)

                # Überprüfe und füge fehlende Spalten hinzu
                for table_name in existing_tables:
                    if table_name in cls.SCHEMAS[db_path]:
                        # Extrahiere Spalten aus Schema
                        schema_columns = set()
                        schema = cls.SCHEMAS[db_path][table_name]
                        start_idx = schema.find('(') + 1
                        end_idx = schema.rfind(')')
                        columns_text = schema[start_idx:end_idx]
                        for line in columns_text.split(','):
                            if line.strip():
                                col_name = line.strip().split()[0]
                                if col_name != 'FOREIGN':
                                    schema_columns.add(col_name)

                        # Hole existierende Spalten
                        existing_columns = set()
                        for row in conn.execute(f"PRAGMA table_info({table_name})"):
                            existing_columns.add(row[1])

                        # Füge fehlende Spalten hinzu
                        for col in schema_columns - existing_columns:
                            logging.info(f"Füge fehlende Spalte hinzu: {table_name}.{col}")
                            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col}")

                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Fehler bei der Strukturüberprüfung von {db_path}: {str(e)}")
            return False

    @classmethod
    def init_all_dbs(cls):
        """Initialisiert alle Datenbanken"""
        try:
            # Stelle sicher, dass der Datenbankordner existiert
            os.makedirs(cls.DB_DIR, exist_ok=True)
            
            # Initialisiere jede Datenbank
            all_dbs = [
                cls.WORKERS_DB,
                cls.TOOLS_DB,
                cls.LENDINGS_DB,
                cls.CONSUMABLES_DB,
                cls.SYSTEM_DB
            ]
            
            for db_path in all_dbs:
                if not os.path.exists(db_path):
                    if not cls.init_database(db_path):
                        return False
                if not cls.verify_database_structure(db_path):
                    return False
                logging.info(f"Datenbank {db_path} erfolgreich initialisiert")
                
            return True
            
        except Exception as e:
            logging.error(f"Fehler bei der Datenbankinitialisierung: {str(e)}")
            return False

class DatabaseManager:
    _instances = {}
    
    @classmethod
    def get_connection(cls, db_path):
        """Gibt eine bestehende oder neue DB-Verbindung zurück"""
        if db_path not in cls._instances:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cls._instances[db_path] = conn
        return cls._instances[db_path]
    
    @classmethod
    def init_db(cls, db_path):
        """Initialisiert die Datenbank mit dem entsprechenden Schema"""
        try:
            conn = cls.get_connection(db_path)
            if db_path in DBConfig.SCHEMAS:
                for table_name, schema in DBConfig.SCHEMAS[db_path].items():
                    conn.executescript(schema)
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Fehler bei DB-Initialisierung {db_path}: {str(e)}")
            return False
            
    @classmethod
    def close_all(cls):
        """Schließt alle DB-Verbindungen"""
        for conn in cls._instances.values():
            conn.close()
        cls._instances.clear()

# Konstanten
ADMIN_PASSWORD = "1234"
SECRET_KEY = "ein-zufaelliger-string-1234"

# Hilfsfunktionen
def get_db_connection(db_path):
    """Erstellt eine neue Datenbankverbindung mit verbessertem Error Handling"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Setze row_factory für alle Verbindungen
        return conn
    except Exception as e:
        logging.error(f"Fehler beim Verbindungsaufbau zu {db_path}: {str(e)}")
        raise

def init_dbs():
    try:
        # Tools (Lager) DB
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS tools (
                    barcode TEXT PRIMARY KEY,
                    gegenstand TEXT NOT NULL,
                    ort TEXT DEFAULT 'Lager',
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    image_path TEXT,
                    defect_date DATETIME
                );
            ''')
            logging.info(f"Tools-Tabelle in {DBConfig.TOOLS_DB} erstellt")
            
        # Rest der Initialisierung...
        
    except Exception as e:
        logging.error(f"Fehler bei DB-Initialisierung: {str(e)}")
        return False

def init_test_data():
    """Fügt Testdaten für Mitarbeiter und Verbrauchsmaterial ein"""
    try:
        # Mitarbeiter-Testdaten
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Erstelle workers-Tabelle falls nicht existiert
            conn.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    barcode TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    bereich TEXT,
                    email TEXT
                )
            ''')
            
            # Prüfe ob bereits Daten existieren
            existing = conn.execute('SELECT COUNT(*) FROM workers').fetchone()[0]
            if existing == 0:  # Nur einfügen wenn keine Daten existieren
                test_workers = [
                    ('M0001', 'Max', 'Mustermann', 'Elektro', 'max@example.com'),
                    ('M0002', 'Anna', 'Schmidt', 'Mechanik', 'anna@example.com'),
                    ('M0003', 'Peter', 'Meyer', 'Elektro', 'peter@example.com'),
                    ('M0004', 'Lisa', 'Weber', 'Mechanik', 'lisa@example.com'),
                    ('M0005', 'Tom', 'Fischer', 'Lager', 'tom@example.com')
                ]
                
                conn.executemany('''
                    INSERT OR IGNORE INTO workers 
                    (barcode, name, lastname, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', test_workers)
                
                conn.commit()
                logging.info("Mitarbeiter-Testdaten erfolgreich eingefügt")
            else:
                print("Mitarbeiter-Testdaten bereits vorhanden")

        # Verbrauchsmaterial-Testdaten
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Prüfe ob bereits Daten existieren
            existing = conn.execute('SELECT COUNT(*) FROM consumables').fetchone()[0]
            if existing == 0:  # Nur einfügen wenn keine Daten existieren
                test_data = [
                    ('V0001', 'Schrauben 4x30', 'Regal A1', 'Schrauben', 'Verfügbar', 100, 500, 'Stück'),
                    ('V0002', 'Dübel 8mm', 'Regal A2', 'Dübel', 'Verfügbar', 50, 200, 'Stück'),
                    ('V0003', 'Klebeband', 'Regal B1', 'Klebebänder', 'Verfügbar', 5, 20, 'Rolle'),
                    ('V0004', 'Kupferrohr', 'Regal C1', 'Rohre', 'Verfügbar', 10, 50, 'Meter'),
                    ('V0005', 'Isolierung', 'Regal C2', 'Isolierung', 'Verfügbar', 20, 100, 'Meter')
                ]
                
                conn.executemany('''
                    INSERT OR IGNORE INTO consumables 
                    (barcode, bezeichnung, ort, typ, status, 
                     mindestbestand, aktueller_bestand, einheit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', test_data)
                
                conn.commit()
                print("Verbrauchsmaterial-Testdaten erfolgreich eingefügt")
            else:
                print("Verbrauchsmaterial-Testdaten bereits vorhanden")
            
    except Exception as e:
        print(f"Fehler beim Erstellen der Testdaten: {str(e)}")
        traceback.print_exc()

# Login-Überprüfung Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Bitte melden Sie sich an, um diese Funktion zu nutzen.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Flask-App initialisieren
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    
    # Initialisiere Datenbanken
    if not DBConfig.init_all_dbs():
        logging.error("Fehler bei der Datenbankinitialisierung")
        sys.exit(1)
    
    # Logging Setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            TimedRotatingFileHandler(
                'app.log',
                when='midnight',
                interval=1,
                backupCount=7
            )
        ]
    )
    
    # Datenbank-Initialisierung
    with app.app_context():
        if not DBConfig.init_all_dbs():
            logging.error("Kritischer Fehler bei der Datenbank-Initialisierung")
            raise SystemExit(1)
    
    return app

app = create_app()
app.debug = True  # Aktiviert Debug-Modus

# Überprüfe, ob der Blueprint bereits registriert ist
if not any(bp.name == export_bp.name for bp in app.blueprints.values()):
    logging.info("Registriere Export Blueprint...")
    app.register_blueprint(export_bp, url_prefix='/export')
    logging.info(f"Export Blueprint '{export_bp.name}' registriert")

# Zeige alle registrierten Routen
@app.before_request
def init_app():
    if not hasattr(app, '_initialized'):
        logging.info("Initialisiere App...")
        # Hier kommt deine Initialisierungslogik
        app._initialized = True

# Routen
@app.route('/')
@log_route
def index():
    try:
        filter_status = request.args.get('filter')
        
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            # Verbinde die anderen Datenbanken
            tools_conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            tools_conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            
            query = '''
                SELECT t.*,
                    CASE 
                        WHEN t.status = 'Defekt' THEN (
                            SELECT strftime('%d.%m.%Y %H:%M', timestamp)
                            FROM tool_status_history
                            WHERE tool_barcode = t.barcode
                            AND status = 'Defekt'
                            ORDER BY timestamp DESC
                            LIMIT 1
                        )
                        WHEN t.status = 'Ausgeliehen' THEN (
                            SELECT strftime('%d.%m.%Y %H:%M', l.checkout_time)
                            FROM lendings_db.lendings l
                            WHERE l.item_barcode = t.barcode
                            AND l.return_time IS NULL
                            ORDER BY l.checkout_time DESC
                            LIMIT 1
                        )
                        ELSE NULL
                    END as status_date,
                    CASE 
                        WHEN t.status = 'Ausgeliehen' THEN (
                            SELECT w.name || ' ' || w.lastname
                            FROM lendings_db.lendings l
                            JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                            WHERE l.item_barcode = t.barcode
                            AND l.return_time IS NULL
                            ORDER BY l.checkout_time DESC
                            LIMIT 1
                        )
                        ELSE NULL
                    END as current_worker
                FROM tools t
            '''
            
            if filter_status:
                if filter_status == 'ausgeliehen':
                    query += " WHERE t.status = 'Ausgeliehen'"
                elif filter_status == 'defekt':
                    query += " WHERE t.status = 'Defekt'"
                    
            query += " ORDER BY t.gegenstand"
            
            tools = tools_conn.execute(query).fetchall()
            
            return render_template('index.html', tools=tools, active_filter=filter_status)
            
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler: {str(e)}")
        flash('Fehler beim Laden der Werkzeuge', 'error')
        return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    stats = {
        'total_tools': 0,
        'borrowed_tools': 0,
        'defect_tools': 0,
        'deleted_tools': 0,
        'total_consumables': 0,
        'reorder_consumables': 0,
        'empty_consumables': 0,
        'deleted_consumables': 0,
        'total_workers': 0,
        'deleted_workers': 0,
        'workers_by_area': []
    }
    
    try:
        # Werkzeug-Statistiken
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            stats['total_tools'] = conn.execute(
                'SELECT COUNT(*) FROM tools'
            ).fetchone()[0]
            
            stats['borrowed_tools'] = conn.execute(
                "SELECT COUNT(*) FROM tools WHERE status = 'Ausgeliehen'"
            ).fetchone()[0]
            
            stats['defect_tools'] = conn.execute(
                "SELECT COUNT(*) FROM tools WHERE status = 'Defekt'"
            ).fetchone()[0]
            
            # Gelöschte Werkzeuge
            try:
                stats['deleted_tools'] = conn.execute(
                    'SELECT COUNT(*) FROM deleted_tools'
                ).fetchone()[0]
            except sqlite3.OperationalError:
                stats['deleted_tools'] = 0
                
    except Exception as e:
        logging.error(f"Fehler beim Laden der Werkzeug-Statistiken: {str(e)}")
        
    try:
        # Verbrauchsmaterial-Statistiken
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            stats['total_consumables'] = conn.execute(
                'SELECT COUNT(*) FROM consumables'
            ).fetchone()[0]
            
            stats['reorder_consumables'] = conn.execute(
                'SELECT COUNT(*) FROM consumables WHERE aktueller_bestand <= mindestbestand'
            ).fetchone()[0]
            
            stats['empty_consumables'] = conn.execute(
                'SELECT COUNT(*) FROM consumables WHERE aktueller_bestand = 0'
            ).fetchone()[0]
            
            # Gelöschtes Verbrauchsmaterial
            try:
                stats['deleted_consumables'] = conn.execute(
                    'SELECT COUNT(*) FROM deleted_consumables'
                ).fetchone()[0]
            except sqlite3.OperationalError:
                stats['deleted_consumables'] = 0
                
    except Exception as e:
        logging.error(f"Fehler beim Laden der Verbrauchsmaterial-Statistiken: {str(e)}")
        
    try:
        # Mitarbeiter-Statistiken
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            stats['total_workers'] = conn.execute(
                'SELECT COUNT(*) FROM workers'
            ).fetchone()[0]
            
            # Mitarbeiter nach Bereich
            workers_by_area = conn.execute('''
                SELECT bereich, COUNT(*) as count 
                FROM workers 
                WHERE bereich IS NOT NULL 
                GROUP BY bereich
            ''').fetchall()
            
            stats['workers_by_area'] = [
                (row['bereich'], row['count']) 
                for row in workers_by_area
            ]
            
            # Gelöschte Mitarbeiter
            try:
                stats['deleted_workers'] = conn.execute(
                    'SELECT COUNT(*) FROM deleted_workers'
                ).fetchone()[0]
            except sqlite3.OperationalError:
                stats['deleted_workers'] = 0
                
    except Exception as e:
        logging.error(f"Fehler beim Laden der Mitarbeiter-Statistiken: {str(e)}")
    
    # Auch wenn es Fehler gab, zeigen wir die Seite mit den verfügbaren Daten an
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/workers')
@admin_required
@log_route
def workers():
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers').fetchall()
        return render_template('workers.html', workers=workers)
    except Exception as e:
        logging.error(f"Fehler beim Laden der Mitarbeiter: {str(e)}")
        flash('Fehler beim Laden der Mitarbeiter', 'error')
        return redirect(url_for('index'))

@app.route('/consumables')
@log_route
def consumables():
    try:
        filter_status = request.args.get('filter')
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Zuerst alle Status aktualisieren
            conn.execute('''
                UPDATE consumables 
                SET status = CASE 
                    WHEN aktueller_bestand = 0 THEN 'Leer'
                    WHEN aktueller_bestand <= mindestbestand THEN 'Nachbestellen'
                    ELSE 'Verfügbar'
                END
            ''')
            conn.commit()
            
            # Dann die Daten abrufen
            query = '''
                SELECT *, 
                    CASE 
                        WHEN aktueller_bestand = 0 THEN 'Leer'
                        WHEN aktueller_bestand <= mindestbestand THEN 'Nachbestellen'
                        ELSE 'Verfügbar'
                    END as status
                FROM consumables
            '''
            
            if filter_status:
                query += ' WHERE status = ?'
                consumables = conn.execute(query, (filter_status,)).fetchall()
            else:
                consumables = conn.execute(query).fetchall()
            
            # Hole unique Orte und Typen für Filter
            orte = [row[0] for row in conn.execute('SELECT DISTINCT ort FROM consumables WHERE ort IS NOT NULL').fetchall()]
            typen = [row[0] for row in conn.execute('SELECT DISTINCT typ FROM consumables WHERE typ IS NOT NULL').fetchall()]
            
        return render_template('consumables.html', 
                             consumables=consumables,
                             orte=orte,
                             typen=typen,
                             active_filter=filter_status)
                             
    except Exception as e:
        logging.error(f"Fehler beim Laden der Verbrauchsmaterialien: {str(e)}")
        logging.error(traceback.format_exc())
        flash('Fehler beim Laden der Verbrauchsmaterialien', 'error')
        return redirect(url_for('index'))

@app.route('/consumables/<barcode>')
@admin_required  # Sicherstellen, dass nur Admins Zugriff haben
@log_route
def consumable_details(barcode):
    logging.info(f"Lade Details für Verbrauchsmaterial {barcode}")
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            
            # Hole Verbrauchsmaterial-Details
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not consumable:
                flash('Verbrauchsmaterial nicht gefunden', 'error')
                return redirect(url_for('consumables'))
            
            # Hole Ausgabehistorie mit Mitarbeiterdaten
            lendings = conn.execute('''
                SELECT 
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                    l.amount,
                    w.name || ' ' || w.lastname as worker_name,
                    l.return_time
                FROM lendings_db.lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                WHERE l.item_barcode = ?
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()
            
            # Status berechnen
            if consumable['aktueller_bestand'] == 0:
                status = 'Leer'
            elif consumable['aktueller_bestand'] <= consumable['mindestbestand']:
                status = 'Nachbestellen'
            else:
                status = 'Verfügbar'
            
            consumable = dict(consumable)
            consumable['status'] = status
            
            return render_template('consumable_details.html', 
                                consumable=consumable,
                                lendings=lendings,
                                is_admin=session.get('is_admin', False))
            
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler in consumable_details: {str(e)}")
        flash('Fehler beim Laden der Details', 'error')
        return redirect(url_for('consumables'))

@app.route('/consumables/<barcode>/edit', methods=['GET', 'POST'])
def edit_consumable(barcode):
    logging.info(f"Bearbeite Verbrauchsmaterial {barcode}, Methode: {request.method}")
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            
            # POST-Handling für Updates
            if request.method == 'POST':
                # Bestehende Update-Logik...
                bezeichnung = request.form.get('bezeichnung')
                typ = request.form.get('typ')
                ort = request.form.get('ort')
                mindestbestand = request.form.get('mindestbestand', type=int)
                aktueller_bestand = request.form.get('aktueller_bestand', type=int)
                einheit = request.form.get('einheit')
                
                conn.execute('''
                    UPDATE consumables 
                    SET bezeichnung = ?,
                        typ = ?,
                        ort = ?,
                        mindestbestand = ?,
                        aktueller_bestand = ?,
                        einheit = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE barcode = ?
                ''', (bezeichnung, typ, ort, mindestbestand, aktueller_bestand, einheit, barcode))
                
                conn.commit()
                flash('Verbrauchsmaterial erfolgreich aktualisiert', 'success')
                return redirect(url_for('consumables'))
            
            # GET-Handling für Anzeige
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not consumable:
                flash('Verbrauchsmaterial nicht gefunden', 'error')
                return redirect(url_for('consumables'))
            
            # Hole Ausgabehistorie
            lendings = conn.execute('''
                SELECT 
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                    l.amount,
                    w.name || ' ' || w.lastname as worker_name,
                    strftime('%d.%m.%Y %H:%M', l.return_time) as return_time
                FROM lendings_db.lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                WHERE l.item_barcode = ?
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()
            
            logging.info(f"Geladene Historie für {barcode}: {lendings}")
            
            # Status berechnen
            if consumable['aktueller_bestand'] == 0:
                status = 'Leer'
            elif consumable['aktueller_bestand'] <= consumable['mindestbestand']:
                status = 'Nachbestellen'
            else:
                status = 'Verfügbar'
            
            consumable = dict(consumable)
            consumable['status'] = status
            
            return render_template('consumable_details.html', 
                                consumable=consumable,
                                lendings=lendings,
                                is_admin=session.get('is_admin', False))
            
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler in edit_consumable: {str(e)}")
        flash('Fehler beim Laden der Details', 'error')
        return redirect(url_for('consumables'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == "1234":  # Sicheres Abrufen des Passworts
            session['is_admin'] = True
            flash('Erfolgreich eingeloggt', 'success')
            return redirect(url_for('index'))
        else:
            flash('Falsches Passwort', 'error')
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)  # Entfernt die is_admin Variable aus der Session
    flash('Erfolgreich ausgeloggt', 'success')
    return redirect(url_for('index'))

@app.route('/consumables/add', methods=['GET', 'POST'])
@admin_required
def add_consumable():
    if request.method == 'POST':
        logging.info(f"Füge neues Verbrauchsmaterial hinzu: {request.form}")
        try:
            barcode = request.form.get('barcode')
            bezeichnung = request.form.get('bezeichnung')
            ort = request.form.get('ort', 'Lager')
            typ = request.form.get('typ')
            mindestbestand = request.form.get('mindestbestand', 1, type=int)
            aktueller_bestand = request.form.get('aktueller_bestand', 0, type=int)
            einheit = request.form.get('einheit', 'Stück')
            
            # Überprüfe ob required Felder ausgefüllt sind
            if not barcode or not bezeichnung:
                if not bezeichnung:
                    flash('Bezeichnung ist erforderlich', 'error')
                if not barcode:
                    flash('Barcode ist erforderlich', 'error')
                return render_template('add_consumable.html')

            # Status wird automatisch basierend auf den Beständen gesetzt
            status = 'Verfügbar'
            if aktueller_bestand == 0:
                status = 'Leer'
            elif aktueller_bestand <= mindestbestand:
                status = 'Nachbestellen'

            with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
                # Prüfe zuerst ob der Barcode bereits existiert
                existing = conn.execute('SELECT 1 FROM consumables WHERE barcode = ?', (barcode,)).fetchone()
                if existing:
                    flash('Barcode existiert bereits', 'error')
                    return render_template('add_consumable.html')

                conn.execute('''
                    INSERT INTO consumables 
                    (barcode, bezeichnung, ort, typ, status,
                     mindestbestand, aktueller_bestand, einheit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (barcode, bezeichnung, ort, typ, status,
                      mindestbestand, aktueller_bestand, einheit))
                conn.commit()
                
            flash('Verbrauchsmaterial erfolgreich hinzugefügt', 'success')
            return redirect(url_for('consumables'))
            
        except Exception as e:
            logging.error(f"Fehler beim Hinzufügen: {str(e)}")
            traceback.print_exc()
            flash('Fehler beim Hinzufügen des Verbrauchsmaterials', 'error')
            
    return render_template('add_consumable.html')


def check_table_structure(table_name):
    """Überprüft die Struktur einer Tabelle und gibt die Spaltennamen zurück"""
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            return [col[1] for col in columns]  # Gibt Liste der Spaltennamen zurück
    except Exception as e:
        logging.error(f"Fehler beim Prüfen der Tabellenstruktur von {table_name}: {str(e)}")
        return []

@app.route('/consumable/delete/<barcode>', methods=['POST'])
@log_db_operation("Verbrauchsmaterial löschen")
def delete_consumable(barcode):
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.row_factory = sqlite3.Row
            
            # Hole das zu löschende Verbrauchsmaterial
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not consumable:
                logging.error(f"Verbrauchsmaterial mit Barcode {barcode} nicht gefunden")
                return jsonify({'error': 'Verbrauchsmaterial nicht gefunden'})
            
            # Verschiebe in deleted_consumables
            conn.execute('''
                INSERT INTO deleted_consumables 
                (barcode, bezeichnung, ort, typ, mindestbestand, 
                 aktueller_bestand, einheit, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                consumable['barcode'],          # barcode
                consumable['bezeichnung'],       # bezeichnung
                consumable['ort'],              # ort
                consumable['typ'],              # typ
                consumable['mindestbestand'],   # mindestbestand
                consumable['aktueller_bestand'], # aktueller_bestand
                consumable['einheit'],          # einheit
                session.get('username', 'System') # deleted_by
            ))
            
            # Lösche das Original
            conn.execute('DELETE FROM consumables WHERE barcode = ?', (barcode,))
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': 'Datenbankfehler'})

@app.route('/consumables/<barcode>/adjust', methods=['POST'])
@admin_required
def adjust_quantity(barcode):
    adjustment = request.form.get('adjustment', type=int)
    logging.info(f"Passe Menge an für {barcode}: {adjustment}")
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('''
                UPDATE consumables 
                SET current_quantity = current_quantity + ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE barcode = ?
            ''', (adjustment, barcode))
            conn.commit()
            
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Fehler bei Mengenanpassung für {barcode}: {str(e)}")
        logging.error(traceback.format_exc())
        raise

@app.route('/admin/restore/consumable/<int:id>')
@admin_required
@log_route
def restore_consumable(id):
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Hole gelöschtes Item
            deleted_item = conn.execute(
                'SELECT * FROM deleted_consumables WHERE id = ?', 
                (id,)
            ).fetchone()
            
            if not deleted_item:
                flash('Gelöschter Artikel nicht gefunden', 'error')
                return redirect(url_for('trash'))
                
            # Prüfe ob Barcode bereits existiert
            existing = conn.execute(
                'SELECT barcode FROM consumables WHERE barcode = ?',
                (deleted_item['barcode'],)
            ).fetchone()
            
            if existing:
                # Generiere neuen Barcode
                new_barcode = f"{deleted_item['barcode']}_restored_{int(time.time())}"
                flash(f'Barcode bereits vergeben. Neuer Barcode: {new_barcode}', 'warning')
            else:
                new_barcode = deleted_item['barcode']
            
            # Stelle Item wieder her
            conn.execute('''
                INSERT INTO consumables 
                (barcode, bezeichnung, typ, ort, aktueller_bestand, 
                mindestbestand, einheit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (new_barcode, deleted_item['bezeichnung'], deleted_item['typ'],
                  deleted_item['ort'], deleted_item['aktueller_bestand'],
                  deleted_item['mindestbestand'], deleted_item['einheit']))
            
            # Lösche aus deleted_consumables
            conn.execute('DELETE FROM deleted_consumables WHERE id = ?', (id,))
            conn.commit()
            
            flash('Artikel erfolgreich wiederhergestellt', 'success')
            
    except Exception as e:
        logging.error(f"Fehler beim Wiederherstellen: {str(e)}")
        flash('Fehler beim Wiederherstellen des Artikels', 'error')
        
    return redirect(url_for('trash'))

# Werkzeug-Routen
@app.route('/tool/add', methods=['GET', 'POST'])
@admin_required
def add_tool():
    """Neues Werkzeug hinzufügen"""
    if request.method == 'POST':
        try:
            barcode = request.form.get('barcode')
            gegenstand = request.form.get('gegenstand')
            ort = request.form.get('ort')
            typ = request.form.get('typ')
            
            with get_db_connection(DBConfig.TOOLS_DB) as conn:
                conn.execute('''
                    INSERT INTO tools (barcode, gegenstand, ort, typ)
                    VALUES (?, ?, ?, ?)
                ''', (barcode, gegenstand, ort, typ))
                conn.commit()
                
            flash('Werkzeug erfolgreich hinzugefügt', 'success')
            return redirect(url_for('index'))
            
        except sqlite3.IntegrityError:
            flash('Barcode existiert bereits', 'error')
        except Exception as e:
            print(f"Fehler beim Hinzufügen: {str(e)}")
            traceback.print_exc()
            flash('Fehler beim Hinzufügen des Werkzeugs', 'error')
            
    return render_template('add_tool.html', tool=None)

@app.route('/tool/edit/<string:barcode>', methods=['GET', 'POST'])
@admin_required
def edit_tool(barcode):
    """Werkzeug bearbeiten"""
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            if request.method == 'POST':
                gegenstand = request.form.get('gegenstand')
                ort = request.form.get('ort')
                typ = request.form.get('typ')
                
                conn.execute('''
                    UPDATE tools 
                    SET gegenstand=?, ort=?, typ=?
                    WHERE barcode=?
                ''', (gegenstand, ort, typ, barcode))
                conn.commit()
                
                flash('Werkzeug erfolgreich aktualisiert', 'success')
                return redirect(url_for('index'))
            
            tool = conn.execute(
                'SELECT * FROM tools WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if tool is None:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('index'))
                
            return render_template('tool_form.html', tool=tool)
            
    except Exception as e:
        print(f"Fehler beim Bearbeiten: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Bearbeiten des Werkzeugs', 'error')
        return redirect(url_for('index'))

@app.route('/tool/delete/<string:barcode>')
@admin_required
def delete_tool(barcode):
    """Werkzeug in den Papierkorb verschieben"""
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tool = conn.execute(
                'SELECT * FROM tools WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if tool:
                try:
                    # In deleted_tools verschieben
                    conn.execute('''
                        INSERT INTO deleted_tools 
                        (barcode, gegenstand, ort, typ, status, image_path, 
                         defect_date, deleted_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (tool['barcode'], tool['gegenstand'], tool['ort'],
                          tool['typ'], tool['status'], tool['image_path'],
                          tool['defect_date'], session.get('username', 'admin')))
                    
                    # Original löschen
                    conn.execute('DELETE FROM tools WHERE barcode=?', (barcode,))
                    conn.commit()
                    
                    flash('Werkzeug in den Papierkorb verschoben', 'success')
                    
                except Exception as db_error:
                    conn.rollback()
                    logging.error(f"Datenbankfehler beim Löschen: {str(db_error)}")
                    flash('Fehler beim Löschen des Werkzeugs', 'error')
            else:
                flash('Werkzeug nicht gefunden', 'error')
                
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        flash('Fehler beim Löschen des Werkzeugs', 'error')
        
    return redirect(url_for('index'))

@app.route('/tool/<barcode>')
@log_route
def tool_details(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', (barcode,)).fetchone()
            if not tool:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('index'))
                
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers ORDER BY name').fetchall()
            
        lendings = get_tool_lendings(barcode)
        status_history = get_tool_status_history(barcode)
        
        return render_template('tool_details.html', 
                             tool=tool,
                             workers=workers,
                             lendings=lendings,
                             status_history=status_history)
                             
    except Exception as e:
        logging.error(f"Fehler beim Laden der Werkzeugdetails: {str(e)}")
        flash('Fehler beim Laden der Werkzeugdetails', 'error')
        return redirect(url_for('index'))

# Mitarbeiter-Routen
@app.route('/worker/add', methods=['GET', 'POST'])
@admin_required
def add_worker():
    """Neuen Mitarbeiter hinzufügen"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            lastname = request.form.get('lastname')
            barcode = request.form.get('barcode')
            bereich = request.form.get('bereich')
            email = request.form.get('email')
            
            with get_db_connection(DBConfig.WORKERS_DB) as conn:
                conn.execute('''
                    INSERT INTO workers (name, lastname, barcode, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, lastname, barcode, bereich, email))
                conn.commit()
                
            flash('Mitarbeiter erfolgreich hinzugefügt', 'success')
            return redirect(url_for('workers'))
            
        except sqlite3.IntegrityError:
            flash('Barcode existiert bereits', 'error')
        except Exception as e:
            print(f"Fehler beim Hinzufgen: {str(e)}")
            traceback.print_exc()
            flash('Fehler beim Hinzufügen des Mitarbeiters', 'error')
            
    return render_template('add_worker.html', worker=None)

@app.route('/worker/edit/<string:barcode>', methods=['GET', 'POST'])
@admin_required
def edit_worker(barcode):
    """Mitarbeiter bearbeiten"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            if request.method == 'POST':
                name = request.form.get('name')
                lastname = request.form.get('lastname')
                bereich = request.form.get('bereich')
                email = request.form.get('email')
                
                conn.execute('''
                    UPDATE workers 
                    SET name=?, lastname=?, bereich=?, email=?
                    WHERE barcode=?
                ''', (name, lastname, bereich, email, barcode))
                conn.commit()
                
                flash('Mitarbeiter erfolgreich aktualisiert', 'success')
                return redirect(url_for('workers'))
            
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if worker is None:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers'))
                
            return render_template('worker_form.html', worker=worker)
            
    except Exception as e:
        logging.error(f"Fehler beim Bearbeiten: {str(e)}")
        flash('Fehler beim Bearbeiten des Mitarbeiters', 'error')
        return redirect(url_for('workers'))

@app.route('/worker/delete/<string:barcode>', methods=['GET', 'POST'])
@admin_required
def delete_worker(barcode):
    """Mitarbeiter löschen"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Hole Mitarbeiterdaten
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not worker:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers'))
            
            # Prüfe auf aktive Ausleihen
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            active_lendings = conn.execute('''
                SELECT COUNT(*) as count 
                FROM lendings_db.lendings 
                WHERE worker_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()['count']
            
            if active_lendings > 0:
                flash('Mitarbeiter hat noch aktive Ausleihen', 'error')
                return redirect(url_for('workers'))
            
            # Verschiebe in deleted_workers
            conn.execute('''
                INSERT INTO deleted_workers 
                (barcode, name, lastname, bereich, email, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (worker['barcode'], worker['name'], worker['lastname'],
                 worker['bereich'], worker['email'], 
                 session.get('username', 'System')))
            
            # Lösche Mitarbeiter
            conn.execute('DELETE FROM workers WHERE barcode = ?', (barcode,))
            conn.commit()
            
            flash('Mitarbeiter erfolgreich gelöscht', 'success')
            
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        flash('Fehler beim Löschen des Mitarbeiters', 'error')
        
    return redirect(url_for('workers'))

@app.route('/worker/<barcode>')
@admin_required
@log_route
def worker_details(barcode):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as workers_conn:
            workers_conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            workers_conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            workers_conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
            
            # Hole Mitarbeiterdetails
            worker = dict(workers_conn.execute('SELECT * FROM workers WHERE barcode = ?', 
                                          (barcode,)).fetchone())
            
            # Hole aktuelle Ausleihen
            current_lendings = [dict(row) for row in workers_conn.execute('''
                SELECT 
                    l.*,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_checkout_time,
                    COALESCE(t.gegenstand, c.bezeichnung) as item_name,
                    CASE 
                        WHEN t.barcode IS NOT NULL THEN 'Werkzeug'
                        ELSE 'Verbrauchsmaterial'
                    END as item_type
                FROM lendings_db.lendings l
                LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode
                LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode
                WHERE l.worker_barcode = ? AND l.return_time IS NULL
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()]
            
            # Hole Ausleihhistorie
            lending_history = [dict(row) for row in workers_conn.execute('''
                SELECT 
                    l.*,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_checkout_time,
                    strftime('%d.%m.%Y %H:%M', l.return_time) as formatted_return_time,
                    COALESCE(t.gegenstand, c.bezeichnung) as item_name,
                    CASE 
                        WHEN t.barcode IS NOT NULL THEN 'Werkzeug'
                        ELSE 'Verbrauchsmaterial'
                    END as item_type,
                    CASE 
                        WHEN c.barcode IS NOT NULL THEN l.amount || ' ' || c.einheit
                        ELSE '1'
                    END as amount_display
                FROM lendings_db.lendings l
                LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode
                LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode
                WHERE l.worker_barcode = ? AND l.return_time IS NOT NULL
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()]
            
        return render_template('worker_details.html', 
                             worker=worker, 
                             current_lendings=current_lendings,
                             lending_history=lending_history)
                             
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler in worker_details: {str(e)}")
        flash('Fehler beim Laden der Mitarbeiterdetails', 'error')
        return redirect(url_for('workers'))

@app.route('/admin/restore/tool/<int:id>')
@admin_required
def restore_tool(id):
    """Werkzeug aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Prüfen ob das Werkzeug im Papierkorb ist
            deleted_tool = conn.execute(
                'SELECT * FROM deleted_tools WHERE id=?', (id,)
            ).fetchone()
            
            if not deleted_tool:
                flash('Werkzeug nicht im Papierkorb gefunden', 'error')
                return redirect(url_for('trash'))
            
            # Prüfen ob die Barcode-Nummer bereits wieder vergeben ist
            existing = conn.execute(
                'SELECT 1 FROM tools WHERE barcode=?', ((deleted_tool['barcode'],))
            ).fetchone()
            
            if existing:
                flash('Barcode bereits vergeben. Wiederherstellung nicht möglich.', 'error')
                return redirect(url_for('trash'))
            
            # Werkzeug wiederherstellen
            conn.execute('''
                INSERT INTO tools 
                (barcode, gegenstand, ort, typ, status, image_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (deleted_tool['barcode'], deleted_tool['gegenstand'], 
                  deleted_tool['ort'], deleted_tool['typ'], 
                  'Verfügbar', deleted_tool['image_path']))
            
            # Aus dem Papierkorb löschen
            conn.execute('DELETE FROM deleted_tools WHERE id=?', (id,))
            conn.commit()
            
            flash('Werkzeug erfolgreich wiederhergestellt', 'success')
            
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler bei Werkzeug-Wiederherstellung: {str(e)}")
        flash('Datenbankfehler bei der Wiederherstellung', 'error')
    except Exception as e:
        logging.error(f"Fehler bei Werkzeug-Wiederherstellung: {str(e)}")
        flash('Fehler bei der Wiederherstellung', 'error')
        
    return redirect(url_for('trash'))

@app.route('/admin/restore/worker/<int:id>')
@admin_required
def restore_worker(id):
    """Mitarbeiter aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Hole den gelöschten Mitarbeiter
            item = conn.execute(
                'SELECT * FROM deleted_workers WHERE id=?', (id,)
            ).fetchone()
            
            if item:
                # Prüfen ob Barcode bereits wieder existiert
                existing = conn.execute(
                    'SELECT 1 FROM workers WHERE barcode=?', (item['barcode'],)
                ).fetchone()
                
                if existing:
                    flash('Ein Mitarbeiter mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('trash'))
                
                # Mitarbeiter wiederherstellen
                conn.execute('''
                    INSERT INTO workers 
                    (name, lastname, barcode, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item['name'], item['lastname'], item['barcode'],
                      item['bereich'], item['email']))
                
                # Aus dem Papierkorb löschen
                conn.execute('DELETE FROM deleted_workers WHERE id=?', (id,))
                conn.commit()
                
                flash('Mitarbeiter wiederhergestellt', 'success')
            else:
                flash('Gelöschter Mitarbeiter nicht gefunden', 'error')
                
    except Exception as e:
        logging.error(f"Fehler bei Wiederherstellung: {str(e)}")
        flash('Fehler bei der Wiederherstellung', 'error')
        
    return redirect(url_for('trash'))


@app.route('/admin/permanent_delete/<string:type>/<int:id>', methods=['GET', 'POST'])
@admin_required
def permanent_delete(type, id):  # Entfernen Sie @log_route hier, wenn es Probleme verursacht
    """Element permanent aus dem Papierkorb löschen"""
    try:
        if type == 'consumable':
            db_path = DBConfig.CONSUMABLES_DB
            table = 'deleted_consumables'
            item_type = 'Verbrauchsmaterial'
        elif type == 'tool':
            db_path = DBConfig.TOOLS_DB
            table = 'deleted_tools'
            item_type = 'Werkzeug'
        elif type == 'worker':
            db_path = DBConfig.WORKERS_DB
            table = 'deleted_workers'
            item_type = 'Mitarbeiter'
        else:
            flash('Ungültiger Elementtyp', 'error')
            return redirect(url_for('trash'))

        with get_db_connection(db_path) as conn:
            item = conn.execute(
                f'SELECT * FROM {table} WHERE id = ?', 
                (id,)
            ).fetchone()
            
            if not item:
                flash(f'{item_type} nicht gefunden', 'error')
                return redirect(url_for('trash'))
            
            conn.execute(f'DELETE FROM {table} WHERE id = ?', (id,))
            conn.commit()
            
            flash(f'{item_type} wurde permanent gelöscht', 'success')
            
    except Exception as e:
        logging.error(f"Fehler beim permanenten Löschen: {str(e)}")
        flash('Fehler beim Löschen', 'error')
        
    return redirect(url_for('trash'))


@app.route('/admin/trash/empty', methods=['POST'])
@admin_required
def empty_trash():
    """Papierkorb leeren"""
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            conn.execute('DELETE FROM deleted_tools')
            conn.commit()
            
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            conn.execute('DELETE FROM deleted_workers')
            conn.commit()
            
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('DELETE FROM deleted_consumables')
            conn.commit()
            
        flash('Papierkorb geleert', 'success')
    except Exception as e:
        print(f"Fehler beim Leeren des Papierkorbs: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Leeren des Papierkorbs', 'error')
        
    return redirect(url_for('trash'))

@app.route('/admin/trash')
@admin_required
def trash():
    """Papierkorb mit gelöschten Items anzeigen"""
    deleted_items = {
        'workers': [],
        'tools': [],
        'consumables': []  # Neu hinzugefügt
    }
    
    try:
        # Gelöschte Mitarbeiter laden
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            deleted_items['workers'] = conn.execute(
                'SELECT *, datetime(deleted_at, "localtime") as deleted_at_local FROM deleted_workers'
            ).fetchall()
        
        # Gelöschte Werkzeuge laden
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            deleted_items['tools'] = conn.execute(
                'SELECT *, datetime(deleted_at, "localtime") as deleted_at_local FROM deleted_tools'
            ).fetchall()
            
        # Gelöschte Verbrauchsgegenstände laden
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            deleted_items['consumables'] = conn.execute(
                'SELECT *, datetime(deleted_at, "localtime") as deleted_at_local FROM deleted_consumables'
            ).fetchall()
            
    except Exception as e:
        logging.error(f"Fehler beim Laden des Papierkorbs: {str(e)}")
        flash('Fehler beim Laden des Papierkorbs', 'error')
        
    return render_template('admin/trash.html', deleted_items=deleted_items)

@app.route('/consumables/<barcode>/update', methods=['POST'])
@admin_required
def update_consumable(barcode):
    try:
        bezeichnung = request.form.get('bezeichnung')
        ort = request.form.get('ort')
        typ = request.form.get('typ')
        mindestbestand = request.form.get('mindestbestand', type=int)
        aktueller_bestand = request.form.get('aktueller_bestand', type=int)
        einheit = request.form.get('einheit')
        
        # Status basierend auf Beständen setzen
        status = 'Verfügbar'
        if aktueller_bestand == 0:
            status = 'Leer'
        elif aktueller_bestand <= mindestbestand:
            status = 'Nachbestellen'
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('''
                UPDATE consumables 
                SET bezeichnung=?, 
                    ort=?, 
                    typ=?,
                    mindestbestand=?,
                    aktueller_bestand=?,
                    einheit=?,
                    status=?
                WHERE barcode=?
            ''', (bezeichnung, ort, typ, mindestbestand, 
                  aktueller_bestand, einheit, status, barcode))
            conn.commit()
            
        flash('Verbrauchsmaterial erfolgreich aktualisiert', 'success')
        
    except Exception as e:
        logging.error(f"Fehler beim Update: {str(e)}")
        logging.error(traceback.format_exc())
        flash('Fehler beim Aktualisieren des Verbrauchsmaterials', 'error')
        
    return redirect(url_for('consumable_details', barcode=barcode))

@app.route('/tools/<barcode>/update', methods=['POST'])
def update_tool(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Hole alten Status
            old_status = conn.execute('SELECT status FROM tools WHERE barcode = ?', 
                                   (barcode,)).fetchone()['status']
            
            # Neue Daten
            new_status = request.form.get('status')
            comment = request.form.get('comment', '')
            
            # Update Tool
            conn.execute('''
                UPDATE tools 
                SET gegenstand = ?,
                    typ = ?,
                    ort = ?,
                    status = ?
                WHERE barcode = ?
            ''', (request.form.get('gegenstand'),
                 request.form.get('typ'),
                 request.form.get('ort'),
                 new_status,
                 barcode))
            
            # Wenn sich der Status geändert hat, protokolliere es
            if old_status != new_status:
                conn.execute('''
                    INSERT INTO tool_status_history 
                    (tool_barcode, old_status, new_status, comment, changed_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (barcode, old_status, new_status, comment, 
                      session.get('username', 'System')))
            
            conn.commit()
            flash('Werkzeug erfolgreich aktualisiert', 'success')
            
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Update: {str(e)}")
        flash('Fehler beim Aktualisieren', 'error')
        
    return redirect(url_for('tool_details', barcode=barcode))

@app.route('/workers/<barcode>/update', methods=['POST'])
@admin_required
def update_worker(barcode):
    """Mitarbeiter aktualisieren"""
    try:
        name = request.form.get('name')
        lastname = request.form.get('lastname')
        bereich = request.form.get('bereich')
        email = request.form.get('email')
        
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            conn.execute('''
                UPDATE workers 
                SET name = ?,
                    lastname = ?,
                    bereich = ?,
                    email = ?
                WHERE barcode = ?
            ''', (name, lastname, bereich, email, barcode))
            conn.commit()
            
        flash('Mitarbeiter aktualisiert', 'success')
        
    except Exception as e:
        print(f"Fehler beim Update: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Aktualisieren', 'error')
        
    return redirect(url_for('worker_details', barcode=barcode))

@app.route('/quick-scan')
def quick_scan():
    """Quick-Scan Seite"""
    return render_template('quick_scan.html')

@app.route('/api/recent_lendings')
def get_recent_lendings():
    """Letzte 10 Ausleihen"""
    try:
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            lendings = conn.execute('''
                SELECT l.*, w.name || ' ' || w.lastname as worker_name,
                       CASE 
                           WHEN l.item_type = 'tool' THEN t.gegenstand
                           ELSE c.bezeichnung
                       END as item_name,
                       CASE
                           WHEN l.return_time IS NULL THEN 'Ausgeliehen'
                           ELSE 'Zurückgegeben'
                       END as status
                FROM lendings l
                LEFT JOIN workers w ON l.worker_barcode = w.barcode
                LEFT JOIN tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                LEFT JOIN consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                ORDER BY l.lending_time DESC
                LIMIT 10
            ''').fetchall()
            
            return jsonify({
                'success': True,
                'lendings': [dict(lending) for lending in lendings]
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/process_lending', methods=['POST'])
def process_lending():
    try:
        data = request.get_json()
        print(f"Empfangene Daten: {data}")
        
        worker_barcode = data.get('worker_barcode')
        item_barcode = data.get('item_barcode')
        is_consumable = data.get('is_consumable', False)
        quantity = data.get('quantity')

        if is_consumable:
            with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
                conn.row_factory = sqlite3.Row
                
                item = conn.execute('''
                    SELECT * FROM consumables 
                    WHERE barcode = ?
                ''', (item_barcode,)).fetchone()

                if not item:
                    return jsonify({
                        'success': False,
                        'error': f'Verbrauchsmaterial mit Barcode {item_barcode} nicht gefunden'
                    })

                item_dict = dict(item)

                if not quantity or quantity < 1:
                    return jsonify({
                        'success': False,
                        'error': 'Ungültige Menge'
                    })

                if item_dict['aktueller_bestand'] < quantity:
                    return jsonify({
                        'success': False,
                        'error': 'Nicht genügend Bestand verfügbar'
                    })

                # Bestand reduzieren
                conn.execute('''
                    UPDATE consumables 
                    SET aktueller_bestand = aktueller_bestand - ? 
                    WHERE barcode = ?
                ''', (quantity, item_barcode))

                # Historie eintragen - OHNE amount Spalte
                conn.execute('''
                    INSERT INTO consumables_history
                    (consumable_barcode, worker_barcode, action, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (item_barcode, worker_barcode, f'entnahme: {quantity}'))

                conn.commit()

                return jsonify({
                    'success': True,
                    'message': f"{quantity} {item_dict.get('einheit', 'Stück')} {item_dict['bezeichnung']} entnommen"
                })

        else:
            with get_db_connection(DBConfig.TOOLS_DB) as conn:
                item = conn.execute('''
                    SELECT * FROM tools 
                    WHERE barcode = ?
                ''', (item_barcode,)).fetchone()

                if not item:
                    return jsonify({
                        'success': False,
                        'error': 'Werkzeug nicht gefunden'
                    })

                action = data.get('action', 'ausleihen')
                new_status = 'Ausgeliehen' if action == 'ausleihen' else 'Verfügbar'

                conn.execute('''
                    UPDATE tools 
                    SET status = ? 
                    WHERE barcode = ?
                ''', (new_status, item_barcode))

                conn.execute('''
                    INSERT INTO tool_status_history
                    (tool_barcode, action, worker_barcode, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (item_barcode, action, worker_barcode))

                conn.commit()

                return jsonify({
                    'success': True,
                    'message': f"{item['gegenstand']} wurde {action}"
                })

    except Exception as e:
        print(f"Fehler beim Verarbeiten: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/manual_lending')
@admin_required  # oder @login_required, je nachdem welchen Decorator du verwendest
def manual_lending():
    try:
        logging.info("Starte Laden der Ausleihseite...")
        with get_db_connection(DBConfig.WORKERS_DB) as workers_conn:
            workers = [dict(row) for row in workers_conn.execute('''
                SELECT barcode, name, lastname 
                FROM workers 
                ORDER BY lastname, name
            ''').fetchall()]
            
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            tools = [dict(row) for row in tools_conn.execute('''
                SELECT barcode, gegenstand 
                FROM tools 
                WHERE status = 'Verfügbar'
                ORDER BY gegenstand
            ''').fetchall()]
            
        with get_db_connection(DBConfig.CONSUMABLES_DB) as cons_conn:
            consumables = [dict(row) for row in cons_conn.execute('''
                SELECT barcode, bezeichnung, aktueller_bestand, einheit
                FROM consumables 
                WHERE aktueller_bestand > 0
                ORDER BY bezeichnung
            ''').fetchall()]
            
        with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
            lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
            
            active_lendings = [dict(row) for row in lendings_conn.execute('''
                SELECT l.*, 
                       w.name || ' ' || w.lastname as worker_name,
                       CASE 
                           WHEN l.item_type = 'tool' THEN t.gegenstand
                           ELSE c.bezeichnung
                       END as item_name,
                       l.amount,
                       datetime(l.checkout_time, 'localtime') as formatted_time
                FROM lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                WHERE l.return_time IS NULL
                ORDER BY l.checkout_time DESC
            ''').fetchall()]
            
        return render_template('manual_lending.html', 
                             workers=workers,
                             tools=tools, 
                             consumables=consumables,
                             active_lendings=active_lendings)
                             
    except Exception as e:
        logging.error(f"Fehler beim Laden der Ausleihseite: {str(e)}")
        flash('Fehler beim Laden der Ausleihseite', 'error')
        return redirect(url_for('index'))

@app.route('/mark_tool_defect/<barcode>', methods=['POST'])
def mark_tool_defect(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Prüfen ob das Werkzeug existiert und den aktuellen Status holen
            current = conn.execute('SELECT status FROM tools WHERE barcode = ?', (barcode,)).fetchone()
            
            if not current:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('index'))
            
            # Status und Datum aktualisieren
            conn.execute('''
                UPDATE tools 
                SET status = 'Defekt',
                    defect_date = CURRENT_TIMESTAMP
                WHERE barcode = ?
            ''', (barcode,))
            conn.commit()
            
            # Debug-Log hinzufügen
            logging.info(f"Werkzeug {barcode} als defekt markiert mit Timestamp")
            flash('Werkzeug wurde als defekt markiert', 'success')
            
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Markieren als defekt: {str(e)}")
        flash('Fehler beim Markieren als defekt', 'error')
    return redirect(url_for('index'))

def add_defect_date_column():
    """Fügt die defect_date Spalte zur tools Tabelle hinzu, falls sie nicht existiert"""
    try:
        with sqlite3.connect(DBConfig.TOOLS_DB) as conn:
            # Prüfe ob die Spalte bereits existiert
            cursor = conn.execute("PRAGMA table_info(tools)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'defect_date' not in columns:
                conn.execute('''
                    ALTER TABLE tools 
                    ADD COLUMN defect_date DATETIME
                ''')
                logging.info("defect_date Spalte erfolgreich hinzugefügt")
                
    except Exception as e:
        logging.error(f"Fehler beim Hinzufügen der defect_date Spalte: {str(e)}")

@app.route('/consumables/<barcode>/checkout', methods=['POST'])
def checkout_consumable(barcode):
    try:
        amount = request.form.get('amount', type=int)
        worker_barcode = request.form.get('worker_barcode')
        
        if not amount or amount <= 0:
            flash('Ungültige Menge', 'error')
            return redirect(url_for('consumable_details', barcode=barcode))
            
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Prüfe aktuellen Bestand
            current = conn.execute('''
                SELECT aktueller_bestand FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if current['aktueller_bestand'] < amount:
                flash('Nicht genügend Bestand verfügbar', 'error')
                return redirect(url_for('consumable_details', barcode=barcode))
            
            # Bestand aktualisieren
            conn.execute('''
                UPDATE consumables 
                SET aktueller_bestand = aktueller_bestand - ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE barcode = ?
            ''', (amount, barcode))
            
            # Historie eintragen
            conn.execute('''
                INSERT INTO consumables_history 
                (consumable_barcode, worker_barcode, action, amount, old_stock, new_stock, changed_by)
                VALUES (?, ?, 'checkout', ?, ?, ?, ?)
            ''', (
                barcode,
                worker_barcode,
                amount,
                current['aktueller_bestand'],
                current['aktueller_bestand'] - amount,
                session.get('username', 'System')
            ))
            
            conn.commit()
            flash('Ausgabe erfolgreich verbucht', 'success')
            
    except Exception as e:
        logging.error(f"Fehler bei Materialausgabe: {str(e)}")
        flash('Fehler bei der Ausgabe', 'error')
        
    return redirect(url_for('consumable_details', barcode=barcode))

@app.route('/api/get_item/<barcode>')
def get_item(barcode):
    try:
        # Erst in Werkzeugen suchen
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', 
                              (barcode,)).fetchone()
            if tool:
                return jsonify({
                    'type': 'tool',
                    'barcode': tool['barcode'],
                    'gegenstand': tool['gegenstand'],
                    'status': tool['status']
                })
        
        # Dann in Verbrauchsmaterial
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            item = conn.execute('SELECT * FROM consumables WHERE barcode = ?', 
                              (barcode,)).fetchone()
            if item:
                return jsonify({
                    'type': 'consumable',
                    'barcode': item['barcode'],
                    'gegenstand': item['bezeichnung'],
                    'bestand': item['aktueller_bestand']
                })
                
        return jsonify({'error': 'Artikel nicht gefunden'})
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/get_worker/<barcode>')
def get_worker(barcode):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            worker = conn.execute('''
                SELECT barcode, name, lastname, bereich, email 
                FROM workers 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if worker:
                return jsonify(dict(worker))
            return jsonify({'error': 'Mitarbeiter nicht gefunden'})
            
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/process_scan', methods=['POST'])
def process_scan():
    try:
        data = request.json
        tool_barcode = data['tool_barcode']
        worker_barcode = data['worker_barcode']
        action = data['action']
        
        if action == 'checkout':
            return process_checkout(tool_barcode, worker_barcode)
        elif action == 'return':
            return process_return(tool_barcode)
        else:
            return jsonify({'error': 'Ungültige Aktion'})
            
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/search_worker/<barcode>')
def search_worker(barcode):
    try:
        # Debug-Ausgabe
        print(f"Suche Mitarbeiter mit Barcode: {barcode}")
        
        # Mitarbeiter in der Datenbank suchen
        worker = Worker.query.filter_by(barcode=barcode).first()
        
        if worker:
            return jsonify({
                'worker': {
                    'id': worker.id,
                    'name': worker.name,
                    'lastname': worker.lastname,
                    'barcode': worker.barcode,
                    'bereich': worker.bereich
                }
            })
        else:
            return jsonify({'error': 'Mitarbeiter nicht gefunden'})
            
    except Exception as e:
        print(f"Fehler bei der Mitarbeitersuche: {str(e)}")  # Debug-Ausgabe
        return jsonify({'error': 'Fehler bei der Suche nach dem Mitarbeiter'})


@app.route('/admin/system_logs')
@admin_required
def system_logs():
    """Systemlogs der letzten 14 Tage anzeigen"""
    try:
        with get_db_connection(DBConfig.SYSTEM_DB) as conn:
            logs = conn.execute('''
                SELECT *, datetime(timestamp, 'localtime') as local_time
                FROM system_logs 
                WHERE timestamp >= datetime('now', '-14 days')
                ORDER BY timestamp DESC
            ''').fetchall()
            
        return render_template('admin/logs.html', logs=logs)
        
    except Exception as e:
        logging.error(f"Fehler beim Laden der Logs: {str(e)}")
        flash('Fehler beim Laden der Systemlogs', 'error')
        return redirect(url_for('admin'))

def init_all_databases():
    try:
        # Workers DB
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    abteilung TEXT,
                    status TEXT DEFAULT 'Aktiv'
                );
            ''')
            
        # Tools DB
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT UNIQUE NOT NULL,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT,
                    bereich TEXT,
                    status TEXT DEFAULT 'Verfügbar'
                );
            ''')
            
        # Lendings DB
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS lendings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_barcode TEXT NOT NULL,
                    item_barcode TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    amount INTEGER DEFAULT 1,
                    lending_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    return_time DATETIME
                );
            ''')
            
        # Consumables DB
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT UNIQUE NOT NULL,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    mindestbestand INTEGER,
                    aktueller_bestand INTEGER,
                    einheit TEXT
                );
            ''')
            
        logging.info("Alle Datenbanken erfolgreich initialisiert")
        return True
        
    except Exception as e:
        logging.error(f"Fehler bei Datenbankinitialisierung: {str(e)}")
        return False

def add_last_updated_column():
    try:
        with sqlite3.connect(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('''
                ALTER TABLE consumables 
                ADD COLUMN last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            ''')
            logging.info("last_updated Spalte erfolgreich hinzugefügt")
    except Exception as e:
        logging.error(f"Fehler beim Hinzufügen der last_updated Spalte: {str(e)}")

@app.route('/api/get_lendings')
def get_lendings():
    logging.info("Hole aktuelle Ausleihdaten")
    try:
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            
            active_lendings = [dict(row) for row in conn.execute('''
                SELECT l.*, 
                       w.name || ' ' || w.lastname as worker_name,
                       CASE 
                           WHEN l.item_type = 'tool' THEN t.gegenstand
                           ELSE c.bezeichnung
                       END as item_name,
                       l.item_type,
                       COALESCE(c.einheit, 'Stück') as einheit,
                       datetime(l.checkout_time) as checkout_time
                FROM lendings l
                LEFT JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                WHERE (l.item_type = 'tool' AND l.return_time IS NULL)
                   OR (l.item_type = 'consumable')
                ORDER BY l.checkout_time DESC
            ''').fetchall()]
            
            # Formatiere Zeitstempel
            for lending in active_lendings:
                lending['formatted_time'] = datetime.strptime(
                    lending['checkout_time'], '%Y-%m-%d %H:%M:%S'
                ).strftime('%d.%m.%Y %H:%M')
            
            # Trenne nach Typ
            tools = [l for l in active_lendings if l['item_type'] == 'Werkzeug']
            consumables = [l for l in active_lendings if l['item_type'] == 'Verbrauchsmaterial']
            
            logging.info(f"Gefunden: {len(tools)} Werkzeuge, {len(consumables)} Verbrauchsmaterial")
            
            return jsonify({
                'success': True,
                'tools': tools,
                'consumables': consumables
            })
            
    except Exception as e:
        logging.error(f"Fehler beim Laden der Ausleihdaten: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': 'Fehler beim Laden der Daten'
        })

@app.route('/return_tool', methods=['POST'])
def return_tool():
    try:
        data = request.form
        barcode = data.get('barcode')
        
        if not barcode:
            return jsonify({'success': False, 'message': 'Kein Barcode übermittelt'})
            
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
            
            # Hole Ausleihinformationen
            lending = conn.execute('''
                SELECT * FROM lendings 
                WHERE item_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()
            
            if not lending:
                return jsonify({'success': False, 'message': 'Keine aktive Ausleihe gefunden'})
            
            # Aktualisiere Ausleihe
            conn.execute('''
                UPDATE lendings 
                SET return_time = CURRENT_TIMESTAMP 
                WHERE item_barcode = ? AND return_time IS NULL
            ''', (barcode,))
            
            # Aktualisiere Status je nach Typ
            if lending['item_type'] == 'tool':
                conn.execute('''
                    UPDATE tools_db.tools 
                    SET status = 'Verfügbar' 
                    WHERE barcode = ?
                ''', (barcode,))
            else:  # consumable
                conn.execute('''
                    UPDATE consumables_db.consumables 
                    SET aktueller_bestand = aktueller_bestand + ?
                    WHERE barcode = ?
                ''', (lending['amount'], barcode))
            
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Artikel erfolgreich zurückgegeben'})
            
    except Exception as e:
        logging.error(f"Fehler bei Rückgabe: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/consume_item', methods=['POST'])
def consume_item():
    try:
        barcode = request.form.get('barcode')
        amount = int(request.form.get('amount'))
        worker_barcode = request.form.get('worker_barcode')
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            item = conn.execute('SELECT * FROM consumables WHERE barcode = ?', 
                              (barcode,)).fetchone()
            
            if item:
                old_stock = item['aktueller_bestand']
                new_stock = old_stock - amount
                
                # Prüfe ob genug Bestand vorhanden ist
                if new_stock < 0:
                    return jsonify({
                        'success': False, 
                        'message': f'Nicht genügend Bestand vorhanden. Verfügbar: {old_stock}'
                    })
                
                # Aktualisiere Bestand
                conn.execute('''
                    UPDATE consumables 
                    SET aktueller_bestand = ? 
                    WHERE barcode = ?
                ''', (new_stock, barcode))
                
                # Erstelle Ausgabe-Eintrag
                with get_db_connection(DBConfig.LENDINGS_DB) as lending_conn:
                    lending_conn.execute('''
                        INSERT INTO lendings 
                        (worker_barcode, item_barcode, item_type, amount, 
                         old_stock, new_stock, return_time)
                        VALUES (?, ?, 'consumable', ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (worker_barcode, barcode, amount, old_stock, new_stock))
                
                conn.commit()
                return jsonify({'success': True})
                
    except Exception as e:
        logging.error(f"Fehler beim Verbrauchen: {str(e)}")
        return jsonify({'success': False, 'message': 'Fehler beim Verbrauchen'})

@app.route('/update_consumable_stock', methods=['POST'])
def update_consumable_stock():
    try:
        barcode = request.form.get('barcode')
        if not barcode:
            flash('Barcode fehlt', 'error')
            return redirect(url_for('consumables'))
            
        aktueller_bestand = int(request.form.get('aktueller_bestand', 0))
        mindestbestand = int(request.form.get('mindestbestand', 0))
        
        # Validiere die Werte
        if aktueller_bestand < 0:
            flash('Der aktuelle Bestand darf nicht negativ sein.', 'error')
            return redirect(url_for('consumable_details', barcode=barcode))
            
        if mindestbestand < 0:
            flash('Der Mindestbestand darf nicht negativ sein.', 'error')
            return redirect(url_for('consumable_details', barcode=barcode))
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('''
                UPDATE consumables 
                SET aktueller_bestand = ?, mindestbestand = ?
                WHERE barcode = ?
            ''', (aktueller_bestand, mindestbestand, barcode))
            conn.commit()
            
            flash('Verbrauchsmaterial erfolgreich aktualisiert', 'success')
            return redirect(url_for('consumable_details', barcode=barcode))
            
    except Exception as e:
        logging.error(f"Fehler beim Aktualisieren des Verbrauchsmaterials: {str(e)}")
        flash('Fehler beim Aktualisieren des Verbrauchsmaterials', 'error')
        return redirect(url_for('consumables'))  # Fallback zur Übersicht bei Fehler

@app.route('/history')
def history():
    try:
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            history = conn.execute('''
                SELECT l.*, w.name, w.lastname,
                    CASE 
                        WHEN l.item_type = 'tool' THEN t.gegenstand
                        WHEN l.item_type = 'consumable' THEN c.bezeichnung
                    END as item_name,
                    CASE 
                        WHEN l.item_type = 'tool' THEN t.typ
                        WHEN l.item_type = 'consumable' THEN c.typ
                    END as item_type_name
                FROM lendings l
                LEFT JOIN workers w ON l.worker_barcode = w.barcode
                LEFT JOIN tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                LEFT JOIN consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                ORDER BY l.checkout_time DESC
            ''').fetchall()
            
        return render_template('history.html', history=history)
    except Exception as e:
        logging.error(f"Fehler beim Laden der Historie: {str(e)}")
        flash('Fehler beim Laden der Historie', 'error')
        return redirect(url_for('index'))

# Diese Funktion beim Startup aufrufen
if __name__ == '__main__':
    # Konfiguriere Logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialisiere Datenbanken
    if init_all_databases():
        logging.info("Datenbanken erfolgreich initialisiert")
        # Erstelle Testdaten
        #import create_test_data
        #create_test_data.create_test_data()
        # Starte App
        app.run(host='0.0.0.0', port=5000)  # Ändere die IP-Adresse hier
    else:
        logging.error("Fehler bei der Datenbankinitialisierung")

@log_db_operation("Werkzeug Status ändern")
def update_tool_status(barcode, new_status, changed_by=None):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Prüfe ob das Werkzeug existiert
            tool = conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not tool:
                return jsonify({'error': 'Werkzeug nicht gefunden'})
            
            # Markiere als verfügbar
            conn.execute('''
                UPDATE tools 
                SET status = ?
                WHERE barcode = ?
            ''', (new_status, barcode))
            
            # Wenn sich der Status geändert hat, protokolliere es
            if tool['status'] != new_status:
                conn.execute('''
                    INSERT INTO tool_status_history 
                    (tool_barcode, old_status, new_status, changed_by)
                    VALUES (?, ?, ?, ?)
                ''', (barcode, tool['status'], new_status, changed_by))
            
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Statusändern: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Verbrauchsmaterial Status ändern")
def update_consumable_status(barcode, new_status, changed_by=None):
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Prüfe ob das Verbrauchsmaterial existiert
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not consumable:
                return jsonify({'error': 'Verbrauchsmaterial nicht gefunden'})
            
            # Markiere als verfügbar
            conn.execute('''
                UPDATE consumables 
                SET status = ?
                WHERE barcode = ?
            ''', (new_status, barcode))
            
            # Wenn sich der Status geändert hat, protokolliere es
            if consumable['status'] != new_status:
                conn.execute('''
                    INSERT INTO consumables_history 
                    (consumable_barcode, old_status, new_status, changed_by)
                    VALUES (?, ?, ?, ?)
                ''', (barcode, consumable['status'], new_status, changed_by))
            
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Statusändern: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Werkzeug ausleihen")
def process_checkout(tool_barcode, worker_barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            # Prüfe ob das Werkzeug verfügbar ist
            tool = tools_conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ? AND status = 'Verfügbar'
            ''', (tool_barcode,)).fetchone()
            
            if not tool:
                return jsonify({'error': 'Werkzeug nicht verfügbar'})
            
            # Markiere als ausgeliehen
            tools_conn.execute('''
                UPDATE tools 
                SET status = 'Ausgeliehen' 
                WHERE barcode = ?
            ''', (tool_barcode,))
            tools_conn.commit()
        
        # Erstelle Ausleihvorgang
        with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
            lendings_conn.execute('''
                INSERT INTO lendings 
                (worker_barcode, item_barcode, item_type, checkout_time)
                VALUES (?, ?, 'tool', CURRENT_TIMESTAMP)
            ''', (worker_barcode, tool_barcode))
            lendings_conn.commit()
            
        return jsonify({'success': True, 'message': 'Ausleihe erfolgreich'})
        
    except Exception as e:
        logging.error(f"Fehler bei Werkzeugausleihe: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Werkzeug zurückgeben")
def process_return(tool_barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            # Prüfe ob das Werkzeug existiert
            tool = tools_conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ?
            ''', (tool_barcode,)).fetchone()
            
            if not tool:
                return jsonify({'error': 'Werkzeug nicht gefunden'})
            
            # Markiere als verfügbar
            tools_conn.execute('''
                UPDATE tools 
                SET status = 'Verfügbar' 
                WHERE barcode = ?
            ''', (tool_barcode,))
            tools_conn.commit()
        
        # Aktualisiere Ausleihvorgang
        with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
            lendings_conn.execute('''
                UPDATE lendings 
                SET return_time = CURRENT_TIMESTAMP
                WHERE item_barcode = ? 
                AND item_type = 'tool'
                AND return_time IS NULL
            ''', (tool_barcode,))
            lendings_conn.commit()
            
        return jsonify({'success': True, 'message': 'Rückgabe erfolgreich'})
        
    except Exception as e:
        logging.error(f"Fehler bei Werkzeugrückgabe: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Verbrauchsmaterial ausgeben")
def process_consumable_checkout(consumable_barcode, worker_barcode, amount):
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Prüfe ob das Verbrauchsmaterial existiert
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (consumable_barcode,)).fetchone()
            
            if not consumable:
                return jsonify({'error': 'Verbrauchsmaterial nicht gefunden'})
            
            # Prüfe ob genug Bestand vorhanden ist
            if consumable['aktueller_bestand'] < amount:
                return jsonify({
                    'success': False,
                    'message': f'Nicht genügend Bestand verfügbar. Verfügbar: {consumable["aktueller_bestand"]}'
                })
            
            # Bestand aktualisieren
            conn.execute('''
                UPDATE consumables 
                SET aktueller_bestand = aktueller_bestand - ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE barcode = ?
            ''', (amount, consumable_barcode))
            
            # Historie eintragen
            conn.execute('''
                INSERT INTO consumables_history 
                (consumable_barcode, worker_barcode, action, amount, old_stock, new_stock, changed_by)
                VALUES (?, ?, 'checkout', ?, ?, ?, ?)
            ''', (
                consumable_barcode,
                worker_barcode,
                amount,
                consumable['aktueller_bestand'],
                consumable['aktueller_bestand'] - amount,
                session.get('username', 'System')
            ))
            
            conn.commit()
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Ausgeben: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Mitarbeiter erstellen")
def create_worker(barcode, name, lastname, bereich=None, email=None):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            conn.execute('''
                INSERT INTO workers (barcode, name, lastname, bereich, email)
                VALUES (?, ?, ?, ?, ?)
            ''', (barcode, name, lastname, bereich, email))
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Mitarbeiter erfolgreich erstellt'})
        
    except Exception as e:
        logging.error(f"Fehler beim Erstellen: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Mitarbeiter aktualisieren")
def update_worker(barcode, **updates):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            conn.execute('''
                UPDATE workers 
                SET name = ?,
                    lastname = ?,
                    bereich = ?,
                    email = ?
                WHERE barcode = ?
            ''', (updates['name'], updates['lastname'], updates['bereich'],
                  updates['email'], barcode))
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Mitarbeiter erfolgreich aktualisiert'})
        
    except Exception as e:
        logging.error(f"Fehler beim Aktualisieren: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@log_db_operation("Mitarbeiter löschen")
def delete_worker(barcode):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Hole Mitarbeiterdaten
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not worker:
                return jsonify({'error': 'Mitarbeiter nicht gefunden'})
            
            # Prüfe auf aktive Ausleihen
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            active_lendings = conn.execute('''
                SELECT COUNT(*) as count 
                FROM lendings_db.lendings 
                WHERE worker_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()['count']
            
            if active_lendings > 0:
                return jsonify({
                    'success': False,
                    'message': 'Mitarbeiter hat noch aktive Ausleihen'
                })
            
            # Verschiebe in deleted_workers
            conn.execute('''
                INSERT INTO deleted_workers 
                (barcode, name, lastname, bereich, email, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (worker['barcode'], worker['name'], worker['lastname'],
                 worker['bereich'], worker['email'], 
                 session.get('username', 'System')))
            
            # Lösche Mitarbeiter
            conn.execute('DELETE FROM workers WHERE barcode = ?', (barcode,))
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Mitarbeiter erfolgreich gelöscht'})
            
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

app.logger.info("Test-Logeintrag: Überprüfung des Loggings")

def create_history_tables():
    try:
        # Tools History
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tool_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_barcode TEXT NOT NULL,
                    action TEXT NOT NULL,
                    worker_barcode TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("Tool History Tabelle erstellt/aktualisiert")
            
        # Consumables History
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS consumables_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consumable_barcode TEXT NOT NULL,
                    action TEXT NOT NULL,
                    worker_barcode TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("Consumables History Tabelle erstellt/aktualisiert")
            
    except Exception as e:
        print(f"Fehler beim Erstellen der History-Tabellen: {str(e)}")

def create_deleted_tables():
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Lösche existierende Tabelle (optional)
            conn.execute('DROP TABLE IF EXISTS deleted_consumables')
            
            # Erstelle neue Tabelle mit korrekter Struktur
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deleted_consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT NOT NULL,
                    bezeichnung TEXT,
                    typ TEXT,
                    ort TEXT,
                    aktueller_bestand INTEGER DEFAULT 0,
                    mindestbestand INTEGER DEFAULT 0,
                    einheit TEXT,
                    deleted_by TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logging.info("deleted_consumables Tabelle erfolgreich erstellt/aktualisiert")
            
    except Exception as e:
        logging.error(f"Fehler beim Erstellen der deleted_consumables Tabelle: {str(e)}")
        raise e

def reinitialize_deleted_consumables():
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Backup der existierenden Daten (falls vorhanden)
            try:
                backup_data = conn.execute('SELECT * FROM deleted_consumables').fetchall()
                logging.info(f"Backup von {len(backup_data)} Einträgen erstellt")
            except:
                backup_data = []
                logging.info("Keine existierenden Daten zum Backup gefunden")
            
            # Tabelle neu erstellen
            conn.execute('DROP TABLE IF EXISTS deleted_consumables')
            conn.execute('''
                CREATE TABLE deleted_consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT NOT NULL,
                    bezeichnung TEXT,
                    typ TEXT,
                    ort TEXT,
                    aktueller_bestand INTEGER DEFAULT 0,
                    mindestbestand INTEGER DEFAULT 0,
                    einheit TEXT,
                    deleted_by TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Backup-Daten wiederherstellen falls vorhanden
            if backup_data:
                for row in backup_data:
                    try:
                        conn.execute('''
                            INSERT INTO deleted_consumables 
                            (id, barcode, bezeichnung, typ, ort, aktueller_bestand, 
                             mindestbestand, einheit, deleted_by, deleted_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', row)
                    except Exception as e:
                        logging.error(f"Fehler beim Wiederherstellen von Eintrag: {str(e)}")
                        continue
            
            conn.commit()
            logging.info("deleted_consumables Tabelle erfolgreich neu initialisiert")
            return True
            
    except Exception as e:
        logging.error(f"Fehler bei der Neuinitialisierung: {str(e)}")
        return False

# Fügen Sie dies am Ende der Datei hinzu:
if __name__ == '__main__':
    create_history_tables()  # Tabellen erstellen/aktualisieren
    if reinitialize_deleted_consumables():
        logging.info("Datenbank erfolgreich aktualisiert")
        app.run(debug=True)
    else:
        logging.error("Fehler bei der Datenbankaktualisierung")

# Admin-Überprüfung Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin-Rechte erforderlich', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin-Route für Datenbank-Reinitialisierung
@app.route('/admin/reinitialize_db', methods=['GET'])
@admin_required
def reinitialize_database():
    try:
        if reinitialize_deleted_consumables():
            flash('Datenbank erfolgreich aktualisiert', 'success')
            logging.info("Datenbank wurde erfolgreich reinitialisiert")
        else:
            flash('Fehler bei der Datenbankaktualisierung', 'error')
            logging.error("Fehler bei der Datenbank-Reinitialisierung")
    except Exception as e:
        logging.error(f"Fehler bei der Datenbank-Reinitialisierung: {str(e)}")
        flash('Fehler bei der Datenbankaktualisierung', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/get_consumable/<barcode>', methods=['GET'])
def get_consumable(barcode):
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            item = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if item:
                return jsonify({
                    'valid': True,
                    'data': dict(item)
                })
            return jsonify({'valid': False})
    except Exception as e:
        print(f"Fehler: {str(e)}")
        return jsonify({'valid': False, 'error': str(e)})

@app.route('/api/get_tool/<barcode>', methods=['GET'])
def get_tool(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            item = conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if item:
                return jsonify({
                    'valid': True,
                    'data': dict(item)
                })
            return jsonify({'valid': False})
    except Exception as e:
        print(f"Fehler: {str(e)}")
        return jsonify({'valid': False, 'error': str(e)})

@app.route('/api/process_consumable', methods=['POST'])
def process_consumable():
    try:
        data = request.get_json()
        worker_barcode = data.get('worker_barcode')
        consumable_barcode = data.get('consumable_barcode')
        quantity = data.get('quantity')

        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Prüfe Bestand
            item = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (consumable_barcode,)).fetchone()

            if not item:
                return jsonify({
                    'success': False,
                    'error': 'Verbrauchsmaterial nicht gefunden'
                })

            if item['bestand'] < quantity:
                return jsonify({
                    'success': False,
                    'error': 'Nicht genügend Bestand verfügbar'
                })

            # Bestand reduzieren
            conn.execute('''
                UPDATE consumables 
                SET bestand = bestand - ? 
                WHERE barcode = ?
            ''', (quantity, consumable_barcode))

            # Historie eintragen
            conn.execute('''
                INSERT INTO consumables_history
                (consumable_barcode, action, worker_barcode, timestamp, quantity)
                VALUES (?, 'entnehmen', ?, CURRENT_TIMESTAMP, ?)
            ''', (consumable_barcode, worker_barcode, quantity))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f"{quantity} {item['einheit'] or 'Stk'} {item['bezeichnung']} entnommen"
            })

    except Exception as e:
        print(f"Fehler beim Verarbeiten: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/process_tool', methods=['POST'])
def process_tool():
    try:
        data = request.get_json()
        worker_barcode = data.get('worker_barcode')
        tool_barcode = data.get('tool_barcode')
        action = data.get('action')

        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            item = conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ?
            ''', (tool_barcode,)).fetchone()

            if not item:
                return jsonify({
                    'success': False,
                    'error': 'Werkzeug nicht gefunden'
                })

            new_status = 'Ausgeliehen' if action == 'ausleihen' else 'Verfügbar'

            # Status aktualisieren
            conn.execute('''
                UPDATE tools 
                SET status = ? 
                WHERE barcode = ?
            ''', (new_status, tool_barcode))

            # Historie eintragen
            conn.execute('''
                INSERT INTO tool_status_history
                (tool_barcode, action, worker_barcode, timestamp)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (tool_barcode, action, worker_barcode))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f"{item['gegenstand']} wurde {action}"
            })

    except Exception as e:
        print(f"Fehler beim Verarbeiten: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

def init_db():
    # Bestehender Code für Tabellenerstellung
    
    # Neue Spalte zur consumables_history hinzufügen
    with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
        try:
            conn.execute('''
                ALTER TABLE consumables_history
                ADD COLUMN amount INTEGER DEFAULT 0;
            ''')
            conn.commit()
            print("Spalte 'amount' erfolgreich hinzugefügt")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Spalte 'amount' existiert bereits")
            else:
                print(f"Fehler beim Hinzufügen der Spalte: {e}")

@app.route('/add_amount_column', methods=['GET'])
@login_required
@admin_required
def add_amount_column():
    with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
        try:
            conn.execute('''
                ALTER TABLE consumables_history
                ADD COLUMN amount INTEGER DEFAULT 0;
            ''')
            conn.commit()
            flash('Spalte "amount" erfolgreich hinzugefügt', 'success')
            return redirect(url_for('admin_panel'))
        except sqlite3.OperationalError as e:
            flash(f'Fehler: {str(e)}', 'error')
            return redirect(url_for('admin_panel'))
