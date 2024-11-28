from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.exceptions import BadRequest
import sqlite3
from datetime import datetime
import os
import traceback
from functools import wraps
import logging
from logging.handlers import TimedRotatingFileHandler

# Konstanten für Datenbank
class DBConfig:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WORKERS_DB = os.path.join(BASE_DIR, 'workers.db')
    TOOLS_DB = os.path.join(BASE_DIR, 'lager.db')
    LENDINGS_DB = os.path.join(BASE_DIR, 'lendings.db')
    CONSUMABLES_DB = os.path.join(BASE_DIR, 'consumables.db')
    
    # Schema Definitionen
    SCHEMAS = {
        WORKERS_DB: {
            'workers': '''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    barcode TEXT NOT NULL UNIQUE,
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
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            ''',
            'tool_status_history': '''
                CREATE TABLE IF NOT EXISTS tool_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_barcode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    changed_by TEXT,
                    FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
                );
            '''
        },
        LENDINGS_DB: {
            'lendings': '''
                CREATE TABLE IF NOT EXISTS lendings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_barcode TEXT NOT NULL,
                    tool_barcode TEXT NOT NULL,
                    checkout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    return_time DATETIME,
                    amount INTEGER DEFAULT 1,
                    FOREIGN KEY (worker_barcode) REFERENCES workers(barcode),
                    FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
                );
            '''
        },
        CONSUMABLES_DB: {
            'consumables': '''
                CREATE TABLE IF NOT EXISTS consumables (
                    barcode TEXT PRIMARY KEY,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    mindestbestand INTEGER DEFAULT 0,
                    aktueller_bestand INTEGER DEFAULT 0,
                    einheit TEXT,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''',
            'deleted_consumables': '''
                CREATE TABLE IF NOT EXISTS deleted_consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT NOT NULL,
                    bezeichnung TEXT NOT NULL,
                    ort TEXT,
                    typ TEXT,
                    mindestbestand INTEGER,
                    aktueller_bestand INTEGER,
                    einheit TEXT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_by TEXT
                );
            ''',
            'consumables_history': '''
                CREATE TABLE IF NOT EXISTS consumables_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consumable_barcode TEXT NOT NULL,
                    worker_barcode TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    checkout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (consumable_barcode) REFERENCES consumables(barcode),
                    FOREIGN KEY (worker_barcode) REFERENCES workers(barcode)
                )
            '''
        }
    }

    @classmethod
    def init_db(cls, db_path):
        """Initialisiert eine spezifische Datenbank"""
        try:
            if db_path in cls.SCHEMAS:
                with sqlite3.connect(db_path) as conn:
                    for schema in cls.SCHEMAS[db_path].values():
                        conn.executescript(schema)
                logging.info(f"Datenbank {db_path} erfolgreich initialisiert")
                return True
            return False
        except Exception as e:
            logging.error(f"Fehler bei DB-Initialisierung {db_path}: {str(e)}")
            return False

    @classmethod
    def init_all_dbs(cls):
        """Initialisiert alle Datenbanken"""
        success = True
        for db_path in cls.SCHEMAS:
            if not cls.init_db(db_path):
                success = False
        return success

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
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logging.error(f"Fehler beim Verbindungsaufbau zu {db_path}: {str(e)}")
        raise

def init_dbs():
    """Initialisiert alle Datenbanken"""
    try:
        # Tools DB (lager.db)
        with sqlite3.connect(DBConfig.TOOLS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tools (
                    barcode TEXT PRIMARY KEY,
                    gegenstand TEXT NOT NULL,
                    ort TEXT DEFAULT 'Lager',
                    typ TEXT,
                    status TEXT DEFAULT 'Verfügbar',
                    image_path TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tool_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_barcode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    changed_by TEXT,
                    FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
                )
            ''')
            
        # Lendings DB
        with sqlite3.connect(DBConfig.LENDINGS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS lendings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_barcode TEXT NOT NULL,
                    tool_barcode TEXT NOT NULL,
                    checkout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    return_time DATETIME,
                    amount INTEGER DEFAULT 1,
                    FOREIGN KEY (worker_barcode) REFERENCES workers(barcode),
                    FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
                )
            ''')
            
        logging.info("Datenbanken erfolgreich initialisiert")
        return True
        
    except Exception as e:
        logging.error(f"Fehler bei DB-Initialisierung: {str(e)}")
        return False

def init_test_data():
    """Fügt Testdaten für Verbrauchsmaterial ein"""
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Prüfen ob bereits Daten existieren
            existing = conn.execute('SELECT COUNT(*) FROM consumables').fetchone()[0]
            if existing > 0:
                print("Testdaten bereits vorhanden")
                return
                
            test_data = [
                ('12345', 'Schrauben 4x30', 'Regal A1', 'Schrauben', 'Verfügbar', 100, 500, 'Stück'),
                ('12346', 'Dübel 8mm', 'Regal A2', 'Dübel', 'Verfügbar', 50, 200, 'Stück'),
                ('12347', 'Klebeband', 'Regal B1', 'Klebebänder', 'Verfügbar', 5, 20, 'Rolle'),
                ('12348', 'Kupferrohr', 'Regal C1', 'Rohre', 'Verfügbar', 10, 50, 'Meter'),
                ('12349', 'Isolierung', 'Regal C2', 'Isolierung', 'Verfügbar', 20, 100, 'Meter')
            ]
            
            conn.executemany('''
                INSERT INTO consumables 
                (barcode, bezeichnung, ort, typ, status, 
                 mindestbestand, aktueller_bestand, einheit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', test_data)
            
            conn.commit()
            print("Testdaten erfolgreich eingefügt")
            
    except Exception as e:
        print(f"Fehler beim Einfügen der Testdaten: {str(e)}")
        traceback.print_exc()

# Login-Überprüfung Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Bitte melden Sie sich als Administrator an', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Flask-App initialisieren
def create_app():
    """Initialisiert die Flask-App mit allen notwendigen Konfigurationen"""
    app = Flask(__name__, static_folder='static')
    app.secret_key = SECRET_KEY
    
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

# Routen
@app.route('/')
def index():
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            # Verbinde die anderen Datenbanken
            tools_conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            tools_conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            
            tools = tools_conn.execute('''
                SELECT t.*,
                    CASE 
                        WHEN t.status = 'Defekt' THEN (
                            SELECT strftime('%d.%m.%Y %H:%M', changed_at)
                            FROM tool_status_history
                            WHERE tool_barcode = t.barcode
                            AND status = 'Defekt'
                            ORDER BY changed_at DESC
                            LIMIT 1
                        )
                        WHEN t.status = 'Ausgeliehen' THEN (
                            SELECT strftime('%d.%m.%Y %H:%M', l.checkout_time)
                            FROM lendings_db.lendings l
                            WHERE l.tool_barcode = t.barcode
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
                            WHERE l.tool_barcode = t.barcode
                            AND l.return_time IS NULL
                            ORDER BY l.checkout_time DESC
                            LIMIT 1
                        )
                        ELSE NULL
                    END as current_worker
                FROM tools t
                ORDER BY t.gegenstand
            ''').fetchall()
            
            return render_template('index.html', tools=tools)
            
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler: {str(e)}")
        flash('Fehler beim Laden der Werkzeuge', 'error')
        return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    try:
        stats = {}
        # ... Rest der admin_panel Funktion ...
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        print(f"Fehler beim Laden des Dashboards: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Laden des Dashboards', 'error')
        return redirect(url_for('index'))

@app.route('/workers')
def workers():
    """Zeigt die Mitarbeiterübersicht"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            workers = conn.execute('''
                SELECT * FROM workers 
                ORDER BY name, lastname
            ''').fetchall()
            
            # Unique Bereiche für Filter
            bereiche = conn.execute(
                'SELECT DISTINCT bereich FROM workers WHERE bereich IS NOT NULL'
            ).fetchall()
            
        return render_template('workers.html',
                             workers=workers,
                             bereiche=[bereich['bereich'] for bereich in bereiche])
                             
    except Exception as e:
        logging.error(f"Fehler beim Laden der Mitarbeiter: {str(e)}")
        flash('Fehler beim Laden der Mitarbeiter', 'error')
        return redirect(url_for('index'))

@app.route('/consumables')
def consumables():
    """Verbrauchsmaterialübersicht anzeigen"""
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            consumables = conn.execute('''
                SELECT id, barcode, bezeichnung, ort, typ, status,
                       mindestbestand, aktueller_bestand, einheit, last_updated 
                FROM consumables
            ''').fetchall()
            
            orte = conn.execute('SELECT DISTINCT ort FROM consumables WHERE ort IS NOT NULL').fetchall()
            typen = conn.execute('SELECT DISTINCT typ FROM consumables WHERE typ IS NOT NULL').fetchall()
            
            # Berechne Status basierend auf Beständen
            for item in consumables:
                if item['aktueller_bestand'] == 0:
                    item = dict(item)
                    item['status'] = 'Leer'
                elif item['aktueller_bestand'] <= item['mindestbestand']:
                    item = dict(item)
                    item['status'] = 'Nachbestellen'
                else:
                    item = dict(item)
                    item['status'] = 'Verfügbar'
            
            return render_template('consumables.html', 
                                consumables=consumables,
                                orte=[o['ort'] for o in orte],
                                typen=[t['typ'] for t in typen])
                                
    except Exception as e:
        print(f"Fehler beim Laden des Verbrauchsmaterials: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Laden des Verbrauchsmaterials', 'error')
        return redirect(url_for('index'))

@app.route('/consumables/<barcode>')
def consumable_details(barcode):
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
                WHERE l.tool_barcode = ?
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
                WHERE l.tool_barcode = ?
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
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Erfolgreich als Administrator angemeldet', 'success')
            return redirect(url_for('index'))
        else:
            flash('Falsches Passwort', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Erfolgreich abgemeldet', 'success')
    return redirect(url_for('index'))

@app.route('/consumables/add', methods=['GET', 'POST'])
@admin_required
def add_consumable():
    """Neues Verbrauchsmaterial hinzufügen"""
    if request.method == 'POST':
        try:
            barcode = request.form.get('barcode')
            bezeichnung = request.form.get('bezeichnung')
            ort = request.form.get('ort', 'Lager')
            typ = request.form.get('typ')
            mindestbestand = request.form.get('mindestbestand', 1, type=int)
            aktueller_bestand = request.form.get('aktueller_bestand', 0, type=int)
            einheit = request.form.get('einheit', 'Stück')
            
            # Status wird automatisch basierend auf den Beständen gesetzt
            status = 'Verfügbar'
            if aktueller_bestand == 0:
                status = 'Leer'
            elif aktueller_bestand <= mindestbestand:
                status = 'Nachbestellen'

            with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
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
            
        except sqlite3.IntegrityError as e:
            print(f"Integritätsfehler: {str(e)}")
            flash('Barcode existiert bereits', 'error')
        except Exception as e:
            print(f"Fehler beim Hinzufügen: {str(e)}")
            traceback.print_exc()
            flash('Fehler beim Hinzufügen des Verbrauchsmaterials', 'error')
            
    return render_template('add_consumable.html')


@app.route('/consumables/<barcode>/delete')
@admin_required
def delete_consumable(barcode):
    """Verbrauchsmaterial in den Papierkorb verschieben"""
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Daten für Papierkorb speichern
            consumable = conn.execute(
                'SELECT * FROM consumables WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if consumable:
                conn.execute('''
                    INSERT INTO deleted_consumables 
                    (original_id, barcode, name, description, category,
                     min_quantity, current_quantity, unit, location, deleted_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (consumable['id'], consumable['barcode'], consumable['name'],
                      consumable['description'], consumable['category'],
                      consumable['min_quantity'], consumable['current_quantity'],
                      consumable['unit'], consumable['location'],
                      session.get('username', 'admin')))
                
                # Aus Haupttabelle löschen
                conn.execute('DELETE FROM consumables WHERE barcode=?', (barcode,))
                conn.commit()
                
                flash('Verbrauchsmaterial in den Papierkorb verschoben', 'success')
            else:
                flash('Verbrauchsmaterial nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler beim Löschen: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Löschen des Verbrauchsmaterials', 'error')
        
    return redirect(url_for('consumables'))

@app.route('/consumables/<barcode>/adjust', methods=['POST'])
@admin_required
def adjust_quantity(barcode):
    """Menge anpassen (für schnelle +/- Operationen)"""
    try:
        adjustment = request.form.get('adjustment', type=int)
        
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
        print(f"Fehler bei Mengenanpassung: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/restore/consumable/<barcode>')
@admin_required
def restore_consumable(barcode):
    """Verbrauchsmaterial aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            item = conn.execute(
                'SELECT * FROM deleted_consumables WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if item:
                conn.execute('''
                    INSERT INTO consumables 
                    (barcode, name, description, category,
                     min_quantity, current_quantity, unit, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item['barcode'], item['name'], item['description'],
                      item['category'], item['min_quantity'],
                      item['current_quantity'], item['unit'], item['location']))
                
                conn.execute('DELETE FROM deleted_consumables WHERE barcode=?', (barcode,))
                conn.commit()
                
                flash('Verbrauchsmaterial wiederhergestellt', 'success')
            else:
                flash('Gelöschtes Verbrauchsmaterial nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler bei Wiederherstellung: {str(e)}")
        traceback.print_exc()
        flash('Fehler bei der Wiederherstellung', 'error')
        
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
                conn.execute('''
                    INSERT INTO deleted_tools 
                    (barcode, gegenstand, ort, typ, status, image_path, deleted_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (tool['barcode'], tool['gegenstand'], tool['ort'],
                      tool['typ'], tool['status'], tool['image_path'],
                      session.get('username', 'admin')))
                
                conn.execute('DELETE FROM tools WHERE barcode=?', (barcode,))
                conn.commit()
                
                flash('Werkzeug in den Papierkorb verschoben', 'success')
            else:
                flash('Werkzeug nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler beim Löschen: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Löschen des Werkzeugs', 'error')
        
    return redirect(url_for('index'))

@app.route('/tool/<barcode>')
def tool_details(barcode):
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            tools_conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            tools_conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            
            # Hole Werkzeugdetails mit formatiertem Defekt-Datum
            tool = dict(tools_conn.execute('''
                SELECT t.*, 
                    CASE 
                        WHEN t.status = 'Defekt' THEN strftime('%d.%m.%Y %H:%M', t.defect_date)
                        WHEN t.status = 'Ausgeliehen' THEN (
                            SELECT w.name || ' ' || w.lastname
                            FROM lendings_db.lendings l
                            JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                            WHERE l.tool_barcode = t.barcode
                            AND l.return_time IS NULL
                            LIMIT 1
                        )
                    END as status_date,
                    CASE 
                        WHEN t.status = 'Ausgeliehen' THEN (
                            SELECT w.name || ' ' || w.lastname
                            FROM lendings_db.lendings l
                            JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                            WHERE l.tool_barcode = t.barcode
                            AND l.return_time IS NULL
                            LIMIT 1
                        )
                    END as current_worker
                FROM tools t
                WHERE t.barcode = ?
            ''', (barcode,)).fetchone())
            
            # Hole Ausleihhistorie
            lendings = [dict(row) for row in tools_conn.execute('''
                SELECT 
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                    strftime('%d.%m.%Y %H:%M', l.return_time) as return_time,
                    w.name || ' ' || w.lastname as worker_name,
                    w.bereich
                FROM lendings_db.lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                WHERE l.tool_barcode = ?
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()]
            
        return render_template('tool_details.html', tool=tool, lendings=lendings)
        
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler in tool_details: {str(e)}")
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
            print(f"Fehler beim Hinzufügen: {str(e)}")
            traceback.print_exc()
            flash('Fehler beim Hinzufügen des Mitarbeiters', 'error')
            
    return render_template('add_worker.html', worker=None)

@app.route('/worker/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_worker(id):
    """Mitarbeiter bearbeiten"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            if request.method == 'POST':
                name = request.form.get('name')
                lastname = request.form.get('lastname')
                barcode = request.form.get('barcode')
                bereich = request.form.get('bereich')
                email = request.form.get('email')
                
                conn.execute('''
                    UPDATE workers 
                    SET name=?, lastname=?, barcode=?, bereich=?, email=?
                    WHERE id=?
                ''', (name, lastname, barcode, bereich, email, id))
                conn.commit()
                
                flash('Mitarbeiter erfolgreich aktualisiert', 'success')
                return redirect(url_for('workers'))
            
            worker = conn.execute(
                'SELECT * FROM workers WHERE id=?', (id,)
            ).fetchone()
            
            if worker is None:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers'))
                
            return render_template('worker_form.html', worker=worker)
            
    except Exception as e:
        print(f"Fehler beim Bearbeiten: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Bearbeiten des Mitarbeiters', 'error')
        return redirect(url_for('workers'))

@app.route('/worker/delete/<int:id>')
@admin_required
def delete_worker(id):
    """Mitarbeiter in den Papierkorb verschieben"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            worker = conn.execute(
                'SELECT * FROM workers WHERE id=?', (id,)
            ).fetchone()
            
            if worker:
                conn.execute('''
                    INSERT INTO deleted_workers 
                    (original_id, name, lastname, barcode, bereich, email, deleted_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (worker['id'], worker['name'], worker['lastname'],
                      worker['barcode'], worker['bereich'], worker['email'],
                      session.get('username', 'admin')))
                
                conn.execute('DELETE FROM workers WHERE id=?', (id,))
                conn.commit()
                
                flash('Mitarbeiter in den Papierkorb verschoben', 'success')
            else:
                flash('Mitarbeiter nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler beim Löschen: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Löschen des Mitarbeiters', 'error')
        
    return redirect(url_for('workers'))

@app.route('/worker/<barcode>')
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
                LEFT JOIN tools_db.tools t ON l.tool_barcode = t.barcode
                LEFT JOIN consumables_db.consumables c ON l.tool_barcode = c.barcode
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
                LEFT JOIN tools_db.tools t ON l.tool_barcode = t.barcode
                LEFT JOIN consumables_db.consumables c ON l.tool_barcode = c.barcode
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

@app.route('/admin/restore/tool/<string:barcode>')
@admin_required
def restore_tool(barcode):
    """Werkzeug aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            item = conn.execute(
                'SELECT * FROM deleted_tools WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if item:
                # Prüfen ob Barcode bereits wieder existiert
                existing = conn.execute(
                    'SELECT 1 FROM tools WHERE barcode=?', (barcode,)
                ).fetchone()
                
                if existing:
                    flash('Ein Werkzeug mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('trash'))
                
                conn.execute('''
                    INSERT INTO tools 
                    (barcode, gegenstand, ort, typ, status, image_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (item['barcode'], item['gegenstand'], item['ort'],
                      item['typ'], 'Verfügbar', item['image_path']))
                
                conn.execute('DELETE FROM deleted_tools WHERE barcode=?', (barcode,))
                conn.commit()
                
                flash('Werkzeug wiederhergestellt', 'success')
            else:
                flash('Gelöschtes Werkzeug nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler bei Wiederherstellung: {str(e)}")
        traceback.print_exc()
        flash('Fehler bei der Wiederherstellung', 'error')
        
    return redirect(url_for('trash'))

@app.route('/admin/restore/worker/<int:id>')
@admin_required
def restore_worker(id):
    """Mitarbeiter aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
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
                
                conn.execute('''
                    INSERT INTO workers 
                    (name, lastname, barcode, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item['name'], item['lastname'], item['barcode'],
                      item['bereich'], item['email']))
                
                conn.execute('DELETE FROM deleted_workers WHERE id=?', (id,))
                conn.commit()
                
                flash('Mitarbeiter wiederhergestellt', 'success')
            else:
                flash('Gelöschter Mitarbeiter nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler bei Wiederherstellung: {str(e)}")
        traceback.print_exc()
        flash('Fehler bei der Wiederherstellung', 'error')
        
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
    """Papierkorb anzeigen"""
    try:
        deleted_items = {
            'tools': [],
            'workers': [],
            'consumables': []
        }
        
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            deleted_items['tools'] = conn.execute('''
                SELECT *, datetime(deleted_at, 'localtime') as deleted_at_local
                FROM deleted_tools 
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            deleted_items['workers'] = conn.execute('''
                SELECT *, datetime(deleted_at, 'localtime') as deleted_at_local
                FROM deleted_workers 
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            deleted_items['consumables'] = conn.execute('''
                SELECT *, datetime(deleted_at, 'localtime') as deleted_at_local
                FROM deleted_consumables 
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        return render_template('admin/trash.html', deleted_items=deleted_items)
        
    except Exception as e:
        print(f"Fehler beim Laden des Papierkorbs: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Laden des Papierkorbs', 'error')
        return redirect(url_for('index'))

@app.route('/consumables/<barcode>/update', methods=['POST'])
@admin_required
def update_consumable(barcode):
    """Verbrauchsmaterial aktualisieren"""
    try:
        bezeichnung = request.form.get('bezeichnung')
        typ = request.form.get('typ')
        ort = request.form.get('ort')
        mindestbestand = request.form.get('mindestbestand', type=int)
        aktueller_bestand = request.form.get('aktueller_bestand', type=int)
        einheit = request.form.get('einheit')
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
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
            ''', (bezeichnung, typ, ort, mindestbestand, 
                  aktueller_bestand, einheit, barcode))
            conn.commit()
            
        flash('Verbrauchsmaterial aktualisiert', 'success')
        
    except Exception as e:
        print(f"Fehler beim Update: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Aktualisieren', 'error')
        
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
                    (tool_barcode, status, changed_by)
                    VALUES (?, ?, ?)
                ''', (barcode, new_status, session.get('username', 'System')))
            
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
    """Verarbeitet Ausleihe/Rückgabe von Werkzeugen"""
    try:
        data = request.get_json()
        worker_barcode = data.get('worker_barcode')
        item_barcode = data.get('item_barcode')
        action = data.get('action')

        if not all([worker_barcode, item_barcode, action]):
            return jsonify({'error': 'Unvollständige Daten'})

        with get_db_connection(DBConfig.LENDINGS_DB) as lending_conn:
            if action == 'lend':
                # Prüfe ob das Werkzeug verfügbar ist
                with get_db_connection(DBConfig.TOOLS_DB) as tool_conn:
                    tool = tool_conn.execute(
                        'SELECT status FROM tools WHERE barcode = ?', 
                        (item_barcode,)
                    ).fetchone()
                    
                    if not tool or tool['status'] != 'Verfügbar':
                        return jsonify({'error': 'Werkzeug ist nicht verfügbar'})
                    
                    # Werkzeug als ausgeliehen markieren
                    tool_conn.execute('''
                        UPDATE tools 
                        SET status = 'Ausgeliehen'
                        WHERE barcode = ?
                    ''', (item_barcode,))
                    tool_conn.commit()

                # Ausleihe eintragen
                lending_conn.execute('''
                    INSERT INTO lendings 
                    (worker_barcode, tool_barcode, checkout_time, amount)
                    VALUES (?, ?, CURRENT_TIMESTAMP, 1)
                ''', (worker_barcode, item_barcode))
                
                lending_conn.commit()
                return jsonify({'success': True, 'message': 'Ausleihe erfolgreich verarbeitet'})

            elif action == 'return':
                # Rückgabe verarbeiten
                lending_conn.execute('''
                    UPDATE lendings 
                    SET return_time = CURRENT_TIMESTAMP
                    WHERE worker_barcode = ? 
                    AND tool_barcode = ?
                    AND return_time IS NULL
                ''', (worker_barcode, item_barcode))
                
                # Werkzeug als verfügbar markieren
                with get_db_connection(DBConfig.TOOLS_DB) as tool_conn:
                    tool_conn.execute('''
                        UPDATE tools 
                        SET status = 'Verfügbar'
                        WHERE barcode = ?
                    ''', (item_barcode,))
                    tool_conn.commit()
                
                lending_conn.commit()
                return jsonify({'success': True, 'message': 'Rückgabe erfolgreich verarbeitet'})

            return jsonify({'error': 'Ungültige Aktion'})

    except Exception as e:
        logging.error(f"Fehler bei Ausleihe/Rückgabe: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

@app.route('/manual_lending')
def manual_lending():
    """Manuelle Ausleihe Seite"""
    try:
        # Hole alle aktiven Mitarbeiter
        with get_db_connection(DBConfig.WORKERS_DB) as workers_conn:
            workers = [dict(row) for row in workers_conn.execute('''
                SELECT * FROM workers 
                ORDER BY name, lastname
            ''').fetchall()]
            
        # Hole alle verfügbaren Werkzeuge
        with get_db_connection(DBConfig.TOOLS_DB) as tools_conn:
            tools = [dict(row) for row in tools_conn.execute('''
                SELECT * FROM tools 
                WHERE status = 'Verfügbar' 
                ORDER BY gegenstand
            ''').fetchall()]
            
        # Hole verfügbares Verbrauchsmaterial
        with get_db_connection(DBConfig.CONSUMABLES_DB) as cons_conn:
            consumables = [dict(row) for row in cons_conn.execute('''
                SELECT * FROM consumables 
                WHERE aktueller_bestand > 0 
                ORDER BY bezeichnung
            ''').fetchall()]
            
        # Hole aktive Ausleihen mit ATTACH DATABASE
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
            
            active_lendings = [dict(row) for row in conn.execute('''
                SELECT 
                    l.*,
                    w.name || ' ' || w.lastname as worker_name,
                    CASE 
                        WHEN t.barcode IS NOT NULL THEN t.gegenstand
                        ELSE c.bezeichnung
                    END as item_name,
                    CASE 
                        WHEN t.barcode IS NOT NULL THEN 'Werkzeug'
                        ELSE 'Verbrauchsmaterial'
                    END as item_type,
                    c.einheit,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_time
                FROM lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                LEFT JOIN tools_db.tools t ON l.tool_barcode = t.barcode
                LEFT JOIN consumables_db.consumables c ON l.tool_barcode = c.barcode
                WHERE l.return_time IS NULL
                ORDER BY l.checkout_time DESC
            ''').fetchall()]
            
        return render_template('manual_lending.html',
                             workers=workers,
                             tools=tools,
                             consumables=consumables,
                             active_lendings=active_lendings)
                          
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler in manual_lending: {str(e)}")
        traceback.print_exc()
        flash('Datenbankfehler beim Laden der Seite', 'error')
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
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Prüfen ob die Spalte bereits existiert
            cursor = conn.execute("PRAGMA table_info(tools)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'defect_date' not in columns:
                conn.execute('''
                    ALTER TABLE tools
                    ADD COLUMN defect_date DATETIME;
                ''')
                conn.commit()
                logging.info("defect_date Spalte erfolgreich hinzugefügt")
    except sqlite3.Error as e:
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
                (consumable_barcode, worker_barcode, amount)
                VALUES (?, ?, ?)
            ''', (barcode, worker_barcode, amount))
            
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
                SELECT barcode, name, lastname, bereich 
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

@app.route('/api/search_worker/<query>')
def search_worker(query):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Suche nach Barcode
            if query.isdigit():
                worker = conn.execute('''
                    SELECT * FROM workers 
                    WHERE barcode = ?
                ''', (query,)).fetchone()
                
                if worker:
                    return jsonify({
                        'multiple': False,
                        'worker': dict(worker)
                    })
            
            # Suche nach Name
            workers = conn.execute('''
                SELECT * FROM workers 
                WHERE name || ' ' || lastname LIKE ? 
                OR lastname || ' ' || name LIKE ?
                OR name LIKE ? 
                OR lastname LIKE ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
            
            if len(workers) == 0:
                return jsonify({'error': 'Kein Mitarbeiter gefunden'})
            elif len(workers) == 1:
                return jsonify({
                    'multiple': False,
                    'worker': dict(workers[0])
                })
            else:
                return jsonify({
                    'multiple': True,
                    'workers': [dict(w) for w in workers]
                })
                
    except Exception as e:
        logging.error(f"Fehler bei Mitarbeitersuche: {str(e)}")
        return jsonify({'error': 'Datenbankfehler'})

# Diese Funktion beim Startup aufrufen
if __name__ == '__main__':
    init_dbs()
    add_defect_date_column()
    app.run(debug=True)