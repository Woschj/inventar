from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.exceptions import BadRequest
import sqlite3
from datetime import datetime
import os
import traceback
from functools import wraps
import logging
from logging.handlers import TimedRotatingFileHandler

# Absolute Pfade zu den Datenbanken
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKERS_DB = os.path.join(BASE_DIR, 'workers.db')
TOOLS_DB = os.path.join(BASE_DIR, 'lager.db')
LENDINGS_DB = os.path.join(BASE_DIR, 'lendings.db')
CONSUMABLES_DB = os.path.join(BASE_DIR, 'consumables.db')

# Konstanten
ADMIN_PASSWORD = "1234"
SECRET_KEY = "ein-zufaelliger-string-1234"

# Hilfsfunktionen
def get_db_connection(db_path):
    """Erstellt eine Datenbankverbindung"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_dbs():
    """Initialisiert alle Datenbanken"""
    databases = {
        TOOLS_DB: '''
            CREATE TABLE IF NOT EXISTS tools (
                barcode TEXT PRIMARY KEY,
                gegenstand TEXT NOT NULL,
                ort TEXT DEFAULT 'Lager',
                typ TEXT,
                status TEXT DEFAULT 'Verfügbar',
                image_path TEXT
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
        ''',
        WORKERS_DB: '''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lastname TEXT NOT NULL,
                barcode TEXT NOT NULL UNIQUE,
                bereich TEXT,
                email TEXT
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
        ''',
        CONSUMABLES_DB: '''
            CREATE TABLE IF NOT EXISTS consumables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                bezeichnung TEXT NOT NULL,  
                ort TEXT DEFAULT 'Lager',
                typ TEXT,
                status TEXT DEFAULT 'Verfügbar',
                mindestbestand INTEGER DEFAULT 1,
                aktueller_bestand INTEGER DEFAULT 0,
                einheit TEXT DEFAULT 'Stück',
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS deleted_consumables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                barcode TEXT,
                bezeichnung TEXT NOT NULL,  
                ort TEXT,
                typ TEXT,
                status TEXT,
                mindestbestand INTEGER,
                aktueller_bestand INTEGER,
                einheit TEXT,
                deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_by TEXT
            );
        '''
    }
    
    for db_path, schema in databases.items():
        try:
            with get_db_connection(db_path) as conn:
                conn.executescript(schema)
                conn.commit()
        except Exception as e:
            print(f"Fehler beim Initialisieren von {db_path}: {str(e)}")
            traceback.print_exc()

def init_test_data():
    """Fügt Testdaten für Verbrauchsmaterial ein"""
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
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
    app = Flask(__name__, static_folder='static')
    app.secret_key = SECRET_KEY
    
    with app.app_context():
        init_dbs()
    
    return app

app = create_app()
app.debug = True  # Aktiviert Debug-Modus

# Routen
@app.route('/')
def index():
    """Hauptseite mit Werkzeugübersicht"""
    try:
        with get_db_connection(TOOLS_DB) as conn:
            tools = conn.execute('''
                SELECT * FROM tools 
                ORDER BY gegenstand ASC
            ''').fetchall()
            
            orte = conn.execute('SELECT DISTINCT ort FROM tools WHERE ort IS NOT NULL').fetchall()
            typen = conn.execute('SELECT DISTINCT typ FROM tools WHERE typ IS NOT NULL').fetchall()
            
        return render_template('index.html',
                             tools=tools,
                             orte=[ort[0] for ort in orte],
                             typen=[typ[0] for typ in typen])
    except Exception as e:
        print(f"Fehler in index: {str(e)}")
        traceback.print_exc()
        return render_template('index.html', tools=[], orte=[], typen=[])

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
    """Mitarbeiterübersicht anzeigen"""
    try:
        with get_db_connection(WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers').fetchall()
        return render_template('workers.html', workers=workers)
    except Exception as e:
        print(f"Fehler beim Laden der Mitarbeiter: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Laden der Mitarbeiter', 'error')
        return redirect(url_for('index'))

@app.route('/consumables')
def consumables():
    """Verbrauchsmaterialübersicht anzeigen"""
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
            # Debug-Ausgabe
            print("Versuche Daten zu laden...")
            
            # Hole alle Verbrauchsmaterialien
            consumables = conn.execute('''
                SELECT id, barcode, bezeichnung, ort, typ, status,
                       mindestbestand, aktueller_bestand, einheit, last_updated 
                FROM consumables
            ''').fetchall()
            
            # Debug: Zeige die ersten Einträge
            if consumables:
                print(f"Gefundene Einträge: {len(consumables)}")
                print(f"Erster Eintrag: {dict(consumables[0])}")
            else:
                print("Keine Einträge gefunden")
            
            # Hole eindeutige Orte und Typen für die Filter
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
    """Details eines Verbrauchsmaterials"""
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not consumable:
                flash('Verbrauchsmaterial nicht gefunden', 'error')
                return redirect(url_for('consumables'))
            
            # Füge den Status dynamisch hinzu
            if consumable['aktueller_bestand'] == 0:
                status = 'Leer'
            elif consumable['aktueller_bestand'] <= consumable['mindestbestand']:
                status = 'Nachbestellen'
            else:
                status = 'Verfügbar'
                
            # Konvertiere SQLite Row zu dict und füge Status hinzu
            consumable_dict = dict(consumable)
            consumable_dict['status'] = status
            
            return render_template('consumable_details.html', 
                                 consumable=consumable_dict,
                                 is_admin=session.get('is_admin', False))
            
    except Exception as e:
        print(f"Fehler in consumable_details: {str(e)}")
        traceback.print_exc()
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

            with get_db_connection(CONSUMABLES_DB) as conn:
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

@app.route('/consumables/<barcode>/edit', methods=['GET', 'POST'])
@admin_required
def edit_consumable(barcode):
    """Verbrauchsmaterial bearbeiten"""
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
            if request.method == 'POST':
                name = request.form.get('name')
                description = request.form.get('description')
                category = request.form.get('category')
                min_quantity = request.form.get('min_quantity', 0, type=int)
                current_quantity = request.form.get('current_quantity', 0, type=int)
                unit = request.form.get('unit', 'Stück')
                location = request.form.get('location')

                conn.execute('''
                    UPDATE consumables 
                    SET name=?, description=?, category=?, 
                        min_quantity=?, current_quantity=?, unit=?, location=?,
                        last_updated=CURRENT_TIMESTAMP
                    WHERE barcode=?
                ''', (name, description, category, min_quantity,
                      current_quantity, unit, location, barcode))
                conn.commit()
                
                flash('Verbrauchsmaterial erfolgreich aktualisiert', 'success')
                return redirect(url_for('consumables'))
            
            consumable = conn.execute(
                'SELECT * FROM consumables WHERE barcode=?', (barcode,)
            ).fetchone()
            
            if consumable is None:
                flash('Verbrauchsmaterial nicht gefunden', 'error')
                return redirect(url_for('consumables'))
                
            return render_template('consumable_form.html', consumable=consumable)
            
    except Exception as e:
        print(f"Fehler beim Bearbeiten: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Bearbeiten des Verbrauchsmaterials', 'error')
        return redirect(url_for('consumables'))

@app.route('/consumables/<barcode>/delete')
@admin_required
def delete_consumable(barcode):
    """Verbrauchsmaterial in den Papierkorb verschieben"""
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
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
        
        with get_db_connection(CONSUMABLES_DB) as conn:
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
        with get_db_connection(CONSUMABLES_DB) as conn:
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
            
            with get_db_connection(TOOLS_DB) as conn:
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
        with get_db_connection(TOOLS_DB) as conn:
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
        with get_db_connection(TOOLS_DB) as conn:
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

@app.route('/tools/<barcode>')
def tool_details(barcode):
    """Details eines Werkzeugs"""
    try:
        with get_db_connection(TOOLS_DB) as conn:
            tool = conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not tool:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('index'))
                
            return render_template('tool_details.html', 
                                 tool=tool,
                                 is_admin=session.get('is_admin', False))
            
    except Exception as e:
        print(f"Fehler in tool_details: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Laden der Details', 'error')
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
            
            with get_db_connection(WORKERS_DB) as conn:
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
        with get_db_connection(WORKERS_DB) as conn:
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
        with get_db_connection(WORKERS_DB) as conn:
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

@app.route('/workers/<barcode>')
def worker_details(barcode):
    """Details eines Mitarbeiters"""
    try:
        with get_db_connection(WORKERS_DB) as conn:
            worker = conn.execute('''
                SELECT * FROM workers 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not worker:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers'))
                
            return render_template('worker_details.html', 
                                worker=worker,
                                is_admin=session.get('is_admin', False))
            
    except Exception as e:
        print(f"Fehler in worker_details: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Laden der Details', 'error')
        return redirect(url_for('workers'))

@app.route('/admin/restore/tool/<string:barcode>')
@admin_required
def restore_tool(barcode):
    """Werkzeug aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(TOOLS_DB) as conn:
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
        with get_db_connection(WORKERS_DB) as conn:
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
        with get_db_connection(TOOLS_DB) as conn:
            conn.execute('DELETE FROM deleted_tools')
            conn.commit()
            
        with get_db_connection(WORKERS_DB) as conn:
            conn.execute('DELETE FROM deleted_workers')
            conn.commit()
            
        with get_db_connection(CONSUMABLES_DB) as conn:
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
        
        with get_db_connection(TOOLS_DB) as conn:
            deleted_items['tools'] = conn.execute('''
                SELECT *, datetime(deleted_at, 'localtime') as deleted_at_local
                FROM deleted_tools 
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        with get_db_connection(WORKERS_DB) as conn:
            deleted_items['workers'] = conn.execute('''
                SELECT *, datetime(deleted_at, 'localtime') as deleted_at_local
                FROM deleted_workers 
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        with get_db_connection(CONSUMABLES_DB) as conn:
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
        
        with get_db_connection(CONSUMABLES_DB) as conn:
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
@admin_required
def update_tool(barcode):
    """Werkzeug aktualisieren"""
    try:
        gegenstand = request.form.get('gegenstand')
        typ = request.form.get('typ')
        ort = request.form.get('ort')
        status = request.form.get('status')
        
        with get_db_connection(TOOLS_DB) as conn:
            conn.execute('''
                UPDATE tools 
                SET gegenstand = ?,
                    typ = ?,
                    ort = ?,
                    status = ?
                WHERE barcode = ?
            ''', (gegenstand, typ, ort, status, barcode))
            conn.commit()
            
        flash('Werkzeug aktualisiert', 'success')
        
    except Exception as e:
        print(f"Fehler beim Update: {str(e)}")
        traceback.print_exc()
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
        
        with get_db_connection(WORKERS_DB) as conn:
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

if __name__ == '__main__':
    app.run(debug=True)