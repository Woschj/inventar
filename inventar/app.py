from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
from werkzeug.exceptions import BadRequest
import sqlite3
from datetime import datetime
import os
import traceback

# Flask-App initialisieren
app = Flask(__name__)
app.secret_key = 'deine_secret_key_hier'  # Wichtig für Flash-Messages

# Absolute Pfade zu den Datenbanken
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKERS_DB = os.path.join(BASE_DIR, 'workers.db')
TOOLS_DB = os.path.join(BASE_DIR, 'lager.db')  # tools-Tabelle
LENDINGS_DB = os.path.join(BASE_DIR, 'lendings.db')
CONSUMABLES_DB = os.path.join(BASE_DIR, 'consumables.db')

# Datenbankfunktionen
def get_db_connection(db_path):
    """Erstellt eine Datenbankverbindung"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.teardown_appcontext
def close_db(error):
    for attr in list(g):
        if attr.startswith('db_'):
            getattr(g, attr).close()

# Hauptroute
@app.route('/')
def index():
    try:
        with get_db_connection(TOOLS_DB) as conn:
            # Beide zusätzlichen Datenbanken anhängen
            conn.execute(f"ATTACH DATABASE '{LENDINGS_DB}' AS lendings_db")
            conn.execute(f"ATTACH DATABASE '{WORKERS_DB}' AS workers_db")
            
            # Hole Werkzeuge mit Verleihinformationen
            tools = conn.execute('''
                SELECT t.barcode,
                       t.gegenstand,
                       t.ort,
                       t.typ,
                       t.status,
                       strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                       w.name || ' ' || w.lastname as current_worker
                FROM tools t
                LEFT JOIN lendings_db.lendings l ON t.barcode = l.tool_barcode 
                    AND l.return_time IS NULL
                LEFT JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                ORDER BY t.gegenstand
            ''').fetchall()
            
            # Hole unique Werte für Filter
            orte = conn.execute('SELECT DISTINCT ort FROM tools WHERE ort IS NOT NULL ORDER BY ort').fetchall()
            typen = conn.execute('SELECT DISTINCT typ FROM tools WHERE typ IS NOT NULL ORDER BY typ').fetchall()
            
        return render_template('index.html', 
                             tools=tools,
                             orte=[ort[0] for ort in orte],
                             typen=[typ[0] for typ in typen])
    except Exception as e:
        print(f"Fehler in index: {str(e)}")
        traceback.print_exc()
        flash(f'Ein Fehler ist aufgetreten: {str(e)}', 'error')
        return render_template('index.html', tools=[], orte=[], typen=[])

# Datenbank-Initialisierung
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
                checkout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                return_time DATETIME,
                amount INTEGER DEFAULT 1,
                FOREIGN KEY (worker_barcode) REFERENCES workers(barcode),
                FOREIGN KEY (tool_barcode) REFERENCES tools(barcode)
            )
        ''',
        CONSUMABLES_DB: '''
            CREATE TABLE IF NOT EXISTS consumables (
                barcode TEXT PRIMARY KEY,
                bezeichnung TEXT NOT NULL,
                ort TEXT DEFAULT 'Lager',
                typ TEXT,
                status TEXT DEFAULT 'Verfügbar',
                mindestbestand INTEGER DEFAULT 0,
                aktueller_bestand INTEGER DEFAULT 0,
                einheit TEXT DEFAULT 'Stück'
            )
        '''
    }
    
    for db_path, query in databases.items():
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(query)
            conn.commit()
            conn.close()
            print(f"✓ {db_path} erfolgreich initialisiert")
        except Exception as e:
            print(f"✗ Fehler bei {db_path}: {str(e)}")

@app.route('/workers')
def workers():
    """Mitarbeiterübersicht"""
    try:
        with get_db_connection(WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers ORDER BY lastname, name').fetchall()
        return render_template('workers.html', workers=workers)
    except Exception as e:
        flash(f'Ein Fehler ist aufgetreten: {str(e)}', 'error')
        return render_template('workers.html', workers=[])

@app.route('/add_worker', methods=['GET', 'POST'])
def add_worker():
    """Neuen Mitarbeiter hinzufügen"""
    if request.method == 'POST':
        try:
            with get_db_connection(WORKERS_DB) as conn:
                conn.execute('''
                    INSERT INTO workers (name, lastname, barcode, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    request.form['name'],
                    request.form['lastname'],
                    request.form['barcode'],
                    request.form.get('bereich', ''),
                    request.form.get('email', '')
                ))
                conn.commit()
            flash('Mitarbeiter erfolgreich hinzugefügt', 'success')
            return redirect(url_for('workers'))
        except Exception as e:
            flash(f'Fehler beim Hinzufügen des Mitarbeiters: {str(e)}', 'error')
            return render_template('add_worker.html'), 500
    
    return render_template('add_worker.html')

@app.route('/manual_lending', methods=['GET', 'POST'])
def manual_lending():
    try:
        selected_worker = request.args.get('worker_barcode')

        # Hole alle Mitarbeiter
        with get_db_connection(WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers ORDER BY lastname, name').fetchall()

        # Hole alle Werkzeuge
        with get_db_connection(TOOLS_DB) as conn:
            tools = conn.execute('SELECT * FROM tools ORDER BY gegenstand').fetchall()

        # Hole alle Materialien
        with get_db_connection(CONSUMABLES_DB) as conn:
            consumables = conn.execute('SELECT * FROM consumables WHERE aktueller_bestand > 0 ORDER BY bezeichnung').fetchall()

        if request.method == 'POST':
            worker_barcode = request.form.get('worker_barcode')
            item_type = request.form.get('item_type')
            
            if item_type == 'tool':
                # Werkzeug-Logik (bereits vorhanden)
                tool_barcode = request.form.get('tool_barcode')
                action = request.form.get('action')
                # ... (bestehender Code für Werkzeuge)
            
            else:
                # Material-Logik
                consumable_barcode = request.form.get('consumable_barcode')
                amount = int(request.form.get('amount', 1))
                
                with get_db_connection(CONSUMABLES_DB) as conn:
                    # Prüfe verfügbare Menge
                    item = conn.execute('SELECT * FROM consumables WHERE barcode = ?', 
                                      (consumable_barcode,)).fetchone()
                    
                    if item and item['aktueller_bestand'] >= amount:
                        # Aktualisiere Bestand
                        new_amount = item['aktueller_bestand'] - amount
                        conn.execute('''
                            UPDATE consumables 
                            SET aktueller_bestand = ?,
                                status = CASE 
                                    WHEN ? <= 0 THEN 'Verbraucht'
                                    WHEN ? < mindestbestand THEN 'Kritisch'
                                    ELSE 'Verfügbar'
                                END
                            WHERE barcode = ?
                        ''', (new_amount, new_amount, new_amount, consumable_barcode))
                        
                        flash(f'{amount} {item["einheit"]} {item["bezeichnung"]} wurden ausgegeben', 'success')
                    else:
                        flash('Nicht genügend Material verfügbar', 'error')

        return render_template('manual_lending.html',
                             workers=workers,
                             tools=tools,
                             consumables=consumables,
                             selected_worker=selected_worker,
                             active_lendings=get_active_lendings())
                             
    except Exception as e:
        print(f"Fehler in manual_lending: {str(e)}")
        traceback.print_exc()
        flash(f'Ein Fehler ist aufgetreten: {str(e)}', 'error')
        return render_template('manual_lending.html', 
                             workers=[], 
                             tools=[], 
                             consumables=[],
                             active_lendings=[])

@app.route('/add_tool', methods=['GET', 'POST'])
def add_tool():
    """Neues Werkzeug hinzufügen"""
    if request.method == 'POST':
        try:
            # Bild verarbeiten falls vorhanden
            image_file = request.files.get('image')
            image_path = save_tool_image(image_file, request.form['barcode']) if image_file else None
            
            with get_db_connection(TOOLS_DB) as conn:
                conn.execute('''
                    INSERT INTO tools (barcode, gegenstand, ort, typ, status, image_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    request.form['barcode'],
                    request.form['gegenstand'],
                    request.form['ort'],
                    request.form['typ'],
                    'Verfügbar',
                    image_path
                ))
                conn.commit()
            flash('Werkzeug erfolgreich hinzugefügt', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Fehler beim Hinzufügen des Werkzeugs: {str(e)}', 'error')
    
    return render_template('add_tool.html')

def check_dbs():
    """Überprft den Status aller Datenbanken"""
    for db_path in [WORKERS_DB, TOOLS_DB, LENDINGS_DB, CONSUMABLES_DB]:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Hole alle Tabellen
            tables = cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ''').fetchall()
            
            print(f"\nTabellen in {db_path}:")
            for table in tables:
                # Hole Spalteninformationen
                columns = cursor.execute(f'PRAGMA table_info({table[0]})').fetchall()
                print(f"  ├─ {table[0]}")
                for col in columns:
                    print(f"  │  ├─ {col[1]} ({col[2]})")
            
            conn.close()
        except Exception as e:
            print(f"Fehler beim Überprüfen von {db_path}: {str(e)}")

@app.route('/process_scan', methods=['POST'])
def process_scan():
    try:
        data = request.get_json()
        barcode = data.get('barcode')
        
        # Prüfe Mitarbeiter
        with get_db_connection(WORKERS_DB) as conn:
            worker = conn.execute('SELECT * FROM workers WHERE barcode = ?', 
                                (barcode,)).fetchone()
            if worker:
                return jsonify({
                    'success': True,
                    'redirect': url_for('manual_lending', worker_barcode=barcode)
                })
        
        # Prüfe Werkzeug
        with get_db_connection(TOOLS_DB) as conn:
            tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', 
                              (barcode,)).fetchone()
            if tool:
                return jsonify({
                    'success': True,
                    'redirect': url_for('index', tool_barcode=barcode)
                })
                
        return jsonify({
            'success': False,
            'message': 'Barcode nicht gefunden'
        })
        
    except Exception as e:
        print(f"Fehler in process_scan: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ein Fehler ist aufgetreten: {str(e)}'
        })

# Neue Funktion zum Speichern von Bildern
def save_tool_image(image_file, barcode):
    """Speichert das Werkzeugbild und gibt den Pfad zurück"""
    if not image_file:
        return None
        
    # Erstelle Verzeichnis falls es nicht existiert
    upload_folder = os.path.join(app.static_folder, 'tool_images')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Generiere Dateinamen aus Barcode und Originalerweiterung
    filename = f"tool_{barcode}{os.path.splitext(image_file.filename)[1]}"
    filepath = os.path.join(upload_folder, filename)
    
    # Speichere Bild
    image_file.save(filepath)
    
    # Gebe relativen Pfad zurück
    return os.path.join('tool_images', filename)

@app.route('/worker_details/<worker_barcode>')
def worker_details(worker_barcode):
    try:
        # Hole Mitarbeiterdaten
        with get_db_connection(WORKERS_DB) as conn:
            worker = conn.execute('SELECT * FROM workers WHERE barcode = ?', 
                                (worker_barcode,)).fetchone()
            
        if not worker:
            flash('Mitarbeiter nicht gefunden', 'error')
            return redirect(url_for('workers'))
            
        # Hole aktive Ausleihen des Mitarbeiters mit ATTACH DATABASE
        with get_db_connection(LENDINGS_DB) as conn:
            # Verknüpfe die tools Datenbank
            conn.execute(f"ATTACH DATABASE '{TOOLS_DB}' AS tools_db")
            
            lendings = conn.execute('''
                SELECT l.*, 
                       strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_time,
                       t.gegenstand as tool_name,
                       t.barcode as tool_barcode,
                       t.ort as tool_location
                FROM lendings l
                JOIN tools_db.tools t ON l.tool_barcode = t.barcode
                WHERE l.worker_barcode = ? AND l.return_time IS NULL
                ORDER BY l.checkout_time DESC
            ''', (worker_barcode,)).fetchall()
            
        return render_template('worker_details.html', 
                             worker=worker,
                             lendings=lendings)
                             
    except Exception as e:
        print(f"Fehler in worker_details: {str(e)}")
        traceback.print_exc()
        flash(f'Ein Fehler ist aufgetreten: {str(e)}', 'error')
        return redirect(url_for('workers'))

@app.route('/worker/delete/<barcode>')
def delete_worker(barcode):
    try:
        # Prüfe ob Mitarbeiter aktive Ausleihen hat
        with get_db_connection(LENDINGS_DB) as conn:
            active_lendings = conn.execute('''
                SELECT COUNT(*) as count 
                FROM lendings 
                WHERE worker_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()['count']
            
        if active_lendings > 0:
            flash('Mitarbeiter kann nicht gelöscht werden, da noch aktive Ausleihen bestehen.', 'error')
            return redirect(url_for('workers'))
            
        # Lösche Mitarbeiter
        with get_db_connection(WORKERS_DB) as conn:
            conn.execute('DELETE FROM workers WHERE barcode = ?', (barcode,))
            conn.commit()
            
        flash('Mitarbeiter erfolgreich gelöscht', 'success')
    except Exception as e:
        print(f"Fehler beim Löschen des Mitarbeiters: {str(e)}")
        traceback.print_exc()
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
        
    return redirect(url_for('workers'))

@app.route('/tool/delete/<barcode>')
def delete_tool(barcode):
    try:
        # Prüfe ob Werkzeug ausgeliehen ist
        with get_db_connection(TOOLS_DB) as conn:
            tool = conn.execute('SELECT status FROM tools WHERE barcode = ?', 
                              (barcode,)).fetchone()
            
        if tool and tool['status'] == 'Ausgeliehen':
            flash('Ausgeliehene Werkzeuge können nicht gelöscht werden.', 'error')
            return redirect(url_for('index'))
            
        # Lösche Werkzeug
        with get_db_connection(TOOLS_DB) as conn:
            conn.execute('DELETE FROM tools WHERE barcode = ?', (barcode,))
            conn.commit()
            
        flash('Werkzeug erfolgreich gelöscht', 'success')
    except Exception as e:
        print(f"Fehler beim Löschen des Werkzeugs: {str(e)}")
        traceback.print_exc()
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
        
    return redirect(url_for('index'))

def calculate_consumable_status(bestand, mindestbestand):
    """Berechnet den Status eines Verbrauchsmaterials"""
    if bestand <= 0:
        return 'Verbraucht'
    elif bestand < mindestbestand:
        return 'Kritisch'
    else:
        return 'Verfügbar'

def update_consumable_status(conn, barcode):
    """Aktualisiert den Status eines Verbrauchsmaterials"""
    try:
        # Hole aktuelle Bestände
        item = conn.execute('''
            SELECT * FROM consumables 
            WHERE barcode = ?
        ''', (barcode,)).fetchone()
        
        if item:
            aktueller_bestand = item['aktueller_bestand']
            restbestand = aktueller_bestand - item['mindestbestand']
            
            # Status basierend auf Bestand berechnen
            if aktueller_bestand <= 0:
                status = 'Verbraucht'
            elif aktueller_bestand < item['mindestbestand']:
                status = 'Kritisch'
            else:
                status = 'Verfügbar'
            
            # Update Status und Restbestand
            conn.execute('''
                UPDATE consumables 
                SET status = ?,
                    restbestand = ?
                WHERE barcode = ?
            ''', (status, restbestand, barcode))
            
    except Exception as e:
        print(f"Fehler beim Aktualisieren des Status: {str(e)}")
        traceback.print_exc()

@app.route('/consumables')
def consumables():
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
            # Hole alle Verbrauchsmaterialien mit Filtern
            filter_status = request.args.get('status', '')
            filter_typ = request.args.get('typ', '')
            filter_ort = request.args.get('ort', '')
            filter_bestand = request.args.get('bestand', '')  # 'low', 'critical', 'normal'
            sort_by = request.args.get('sort', 'bezeichnung')  # Standard: nach Bezeichnung sortieren
            
            # Basis-Query
            query = '''
                SELECT c.*,
                       CASE 
                           WHEN aktueller_bestand <= 0 THEN 'Verbraucht'
                           WHEN aktueller_bestand <= mindestbestand THEN 'Kritisch'
                           ELSE 'Verfügbar'
                       END as bestand_status
                FROM consumables c
                WHERE 1=1
            '''
            params = []
            
            # Filter anwenden
            if filter_status:
                query += " AND status = ?"
                params.append(filter_status)
            if filter_typ:
                query += " AND typ = ?"
                params.append(filter_typ)
            if filter_ort:
                query += " AND ort = ?"
                params.append(filter_ort)
            if filter_bestand:
                if filter_bestand == 'low':
                    query += " AND aktueller_bestand <= mindestbestand"
                elif filter_bestand == 'critical':
                    query += " AND aktueller_bestand = 0"
                elif filter_bestand == 'normal':
                    query += " AND aktueller_bestand > mindestbestand"
            
            # Sortierung
            query += f" ORDER BY {sort_by}"
            
            consumables = conn.execute(query, params).fetchall()
            
            # Hole unique Werte für Filter
            orte = conn.execute('SELECT DISTINCT ort FROM consumables WHERE ort IS NOT NULL ORDER BY ort').fetchall()
            typen = conn.execute('SELECT DISTINCT typ FROM consumables WHERE typ IS NOT NULL ORDER BY typ').fetchall()
            
        return render_template('consumables.html',
                             consumables=consumables,
                             orte=[ort[0] for ort in orte],
                             typen=[typ[0] for typ in typen],
                             current_filters={
                                 'status': filter_status,
                                 'typ': filter_typ,
                                 'ort': filter_ort,
                                 'bestand': filter_bestand,
                                 'sort': sort_by
                             })
    except Exception as e:
        print(f"Fehler in consumables: {str(e)}")
        traceback.print_exc()
        flash(f'Ein Fehler ist aufgetreten: {str(e)}', 'error')
        return render_template('consumables.html', consumables=[], orte=[], typen=[])

@app.route('/consumable_details/<barcode>')
def consumable_details(barcode):
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
            # Datenbanken anhängen
            conn.execute(f"ATTACH DATABASE '{LENDINGS_DB}' AS lendings_db")
            conn.execute(f"ATTACH DATABASE '{WORKERS_DB}' AS workers_db")
            
            # Hole Verbrauchsmaterial-Details
            consumable = conn.execute('''
                SELECT * FROM consumables WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            # Hole Ausgabehistorie
            history = conn.execute('''
                SELECT 
                    l.checkout_time,
                    l.amount,
                    w.name || ' ' || w.lastname as worker_name,
                    w.bereich
                FROM lendings_db.lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                WHERE l.tool_barcode = ?
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()
            
            return render_template('consumable_details.html',
                                 consumable=consumable,
                                 history=history)
    except Exception as e:
        flash(f'Fehler beim Laden der Details: {str(e)}', 'error')
        return redirect(url_for('consumables'))

@app.route('/add_consumable', methods=['GET', 'POST'])
def add_consumable():
    if request.method == 'POST':
        barcode = request.form['barcode']
        bezeichnung = request.form['bezeichnung']
        typ = request.form['typ']
        ort = request.form['ort']
        mindestbestand = request.form['mindestbestand']
        aktueller_bestand = request.form['aktueller_bestand']
        einheit = request.form['einheit']
        
        try:
            with get_db_connection(CONSUMABLES_DB) as conn:
                conn.execute('''
                    INSERT INTO consumables 
                    (barcode, bezeichnung, ort, typ, mindestbestand, aktueller_bestand, einheit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (barcode, bezeichnung, ort, typ, mindestbestand, aktueller_bestand, einheit))
            flash('Verbrauchsmaterial erfolgreich hinzugefügt', 'success')
            return redirect(url_for('consumables'))
        except Exception as e:
            flash(f'Fehler beim Hinzufügen: {str(e)}', 'error')
    
    return render_template('add_consumable.html')

@app.route('/edit_consumable/<barcode>', methods=['GET', 'POST'])
def edit_consumable(barcode):
    with get_db_connection(CONSUMABLES_DB) as conn:
        if request.method == 'POST':
            bezeichnung = request.form['bezeichnung']
            typ = request.form['typ']
            ort = request.form['ort']
            mindestbestand = int(request.form['mindestbestand'])
            aktueller_bestand = int(request.form['aktueller_bestand'])
            einheit = request.form['einheit']
            status = request.form.get('status', None)  # Manueller Status (z.B. Defekt)
            
            if not status:  # Wenn kein manueller Status gesetzt wurde
                status = calculate_consumable_status(aktueller_bestand, mindestbestand)
            
            try:
                conn.execute('''
                    UPDATE consumables 
                    SET bezeichnung = ?, ort = ?, typ = ?, mindestbestand = ?, 
                        aktueller_bestand = ?, einheit = ?, status = ?
                    WHERE barcode = ?
                ''', (bezeichnung, ort, typ, mindestbestand, aktueller_bestand, 
                     einheit, status, barcode))
                flash('Verbrauchsmaterial erfolgreich aktualisiert', 'success')
                return redirect(url_for('consumables'))
            except Exception as e:
                flash(f'Fehler beim Aktualisieren: {str(e)}', 'error')
        
        item = conn.execute('SELECT * FROM consumables WHERE barcode = ?', 
                          (barcode,)).fetchone()
        if item is None:
            flash('Verbrauchsmaterial nicht gefunden', 'error')
            return redirect(url_for('consumables'))
            
        return render_template('edit_consumable.html', item=item)

@app.route('/consumable/delete/<barcode>')
def delete_consumable(barcode):
    try:
        with get_db_connection(CONSUMABLES_DB) as conn:
            conn.execute('DELETE FROM consumables WHERE barcode = ?', (barcode,))
            conn.commit()
        flash('Verbrauchsmaterial erfolgreich gelöscht', 'success')
    except Exception as e:
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
    return redirect(url_for('consumables'))

@app.route('/quick_scan')
def quick_scan():
    return render_template('quick_scan.html')

@app.route('/check_worker', methods=['POST'])
def check_worker():
    try:
        data = request.get_json()
        barcode = data.get('barcode')
        
        with get_db_connection(WORKERS_DB) as conn:
            worker = conn.execute('SELECT * FROM workers WHERE barcode = ?', 
                                (barcode,)).fetchone()
            
        if worker:
            return jsonify({
                'success': True,
                'worker_name': f"{worker['name']} {worker['lastname']}"
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Mitarbeiter nicht gefunden'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })

@app.route('/process_quick_scan', methods=['POST'])
def process_quick_scan():
    try:
        data = request.get_json()
        worker_barcode = data.get('worker_barcode')
        tool_barcode = data.get('tool_barcode')
        
        # Prüfe Werkzeug-Status
        with get_db_connection(TOOLS_DB) as conn:
            tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', 
                              (tool_barcode,)).fetchone()
            
            if not tool:
                return jsonify({
                    'success': False,
                    'message': 'Werkzeug nicht gefunden'
                })
            
            # Prüfe aktuelle Ausleihe
            with get_db_connection(LENDINGS_DB) as conn:
                active_lending = conn.execute('''
                    SELECT * FROM lendings 
                    WHERE tool_barcode = ? AND return_time IS NULL
                ''', (tool_barcode,)).fetchone()
                
                if active_lending:
                    # Werkzeug zurückgeben
                    conn.execute('''
                        UPDATE lendings 
                        SET return_time = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    ''', (active_lending['id'],))
                    
                    with get_db_connection(TOOLS_DB) as tools_conn:
                        tools_conn.execute('''
                            UPDATE tools 
                            SET status = 'Verfügbar' 
                            WHERE barcode = ?
                        ''', (tool_barcode,))
                    
                    return jsonify({
                        'success': True,
                        'message': f'{tool["gegenstand"]} wurde zurückgegeben'
                    })
                else:
                    # Neue Ausleihe
                    conn.execute('''
                        INSERT INTO lendings (worker_barcode, tool_barcode, checkout_time)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (worker_barcode, tool_barcode))
                    
                    with get_db_connection(TOOLS_DB) as tools_conn:
                        tools_conn.execute('''
                            UPDATE tools 
                            SET status = 'Ausgeliehen' 
                            WHERE barcode = ?
                        ''', (tool_barcode,))
                    
                    return jsonify({
                        'success': True,
                        'message': f'{tool["gegenstand"]} wurde ausgeliehen'
                    })
                
    except Exception as e:
        print(f"Fehler in process_quick_scan: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })

@app.route('/process_lending', methods=['POST'])
def process_lending():
    """Verarbeitet Ausleihen/Ausgaben von Werkzeugen und Verbrauchsmaterial"""
    try:
        print("\n=== Neue Ausleihe/Ausgabe ===")
        print("Empfangene Formulardaten:", request.form)
        
        worker_barcode = request.form.get('worker_barcode')
        item_type = request.form.get('item_type')
        item_barcode = request.form.get('item_barcode')
        amount = int(request.form.get('amount', 1))
        
        print(f"""
        Verarbeite Anfrage:
        - Typ: {item_type}
        - Artikel: {item_barcode}
        - Mitarbeiter: {worker_barcode}
        - Menge: {amount}
        """)
        
        if item_type == 'tool':
            with get_db_connection(TOOLS_DB) as conn:
                tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', 
                                 (item_barcode,)).fetchone()
                
                if not tool:
                    print(f"Werkzeug nicht gefunden: {item_barcode}")
                    flash('Werkzeug nicht gefunden', 'error')
                    return redirect(url_for('manual_lending'))
                
                print(f"Gefundenes Werkzeug: {dict(tool)}")
                
                if tool['status'] != 'Verfügbar':
                    print(f"Werkzeug nicht verfügbar: {tool['status']}")
                    flash('Werkzeug ist nicht verfügbar', 'error')
                    return redirect(url_for('manual_lending'))
                
                # Status aktualisieren
                conn.execute('''
                    UPDATE tools 
                    SET status = 'Ausgeliehen' 
                    WHERE barcode = ?
                ''', (item_barcode,))
                conn.commit()
                print(f"Werkzeug-Status aktualisiert: {item_barcode}")
            
            # Ausleihe dokumentieren
            with get_db_connection(LENDINGS_DB) as conn:
                conn.execute('''
                    INSERT INTO lendings 
                    (tool_barcode, worker_barcode, checkout_time, amount)
                    VALUES (?, ?, datetime('now', 'localtime'), 1)
                ''', (item_barcode, worker_barcode))
                conn.commit()
                print(f"Ausleihe dokumentiert für Werkzeug {item_barcode}")
            
            flash(f'Werkzeug {tool["gegenstand"]} erfolgreich ausgeliehen', 'success')
            
        # Verbrauchsmaterial-Ausgabe
        else:
            with get_db_connection(CONSUMABLES_DB) as conn:
                item = conn.execute('SELECT * FROM consumables WHERE barcode = ?', 
                                 (item_barcode,)).fetchone()
                
                if not item:
                    flash('Verbrauchsmaterial nicht gefunden', 'error')
                    return redirect(url_for('manual_lending'))
                
                new_bestand = item['aktueller_bestand'] - amount
                if new_bestand < 0:
                    flash('Nicht genügend Bestand verfügbar', 'error')
                    return redirect(url_for('manual_lending'))
                
                # Bestand aktualisieren
                conn.execute('''
                    UPDATE consumables 
                    SET aktueller_bestand = ?,
                        status = CASE 
                            WHEN ? <= 0 THEN 'Verbraucht'
                            WHEN ? <= mindestbestand THEN 'Kritisch'
                            ELSE 'Verfügbar'
                        END
                    WHERE barcode = ?
                ''', (new_bestand, new_bestand, new_bestand, item_barcode))
                conn.commit()
                print(f"Consumable stock updated for {item_barcode}")
            
            # Ausgabe dokumentieren
            with get_db_connection(LENDINGS_DB) as conn:
                conn.execute('''
                    INSERT INTO lendings 
                    (tool_barcode, worker_barcode, checkout_time, amount)
                    VALUES (?, ?, datetime('now', 'localtime'), ?)
                ''', (item_barcode, worker_barcode, amount))
                conn.commit()
                print(f"Lending recorded for consumable {item_barcode}")
            
            flash(f'{amount} {item["einheit"]} {item["bezeichnung"]} ausgegeben', 'success')
        
        return redirect(url_for('manual_lending'))
        
    except Exception as e:
        print(f"Fehler in process_lending: {str(e)}")
        traceback.print_exc()
        flash(f'Fehler bei der Ausgabe: {str(e)}', 'error')
        return redirect(url_for('manual_lending'))

@app.route('/admin')
def admin_panel():
    """Admin-Panel für Systemeinstellungen"""
    try:
        # Hole Tabellenstrukturen
        database_schemas = {}
        
        with get_db_connection(TOOLS_DB) as conn:
            cursor = conn.execute("SELECT * FROM sqlite_master WHERE type='table'")
            database_schemas['Werkzeuge'] = {
                'table': 'tools',
                'columns': [dict(name=row[1], type=row[2]) for row in conn.execute('PRAGMA table_info(tools)').fetchall()],
                'db_path': TOOLS_DB
            }
            
        with get_db_connection(WORKERS_DB) as conn:
            database_schemas['Mitarbeiter'] = {
                'table': 'workers',
                'columns': [dict(name=row[1], type=row[2]) for row in conn.execute('PRAGMA table_info(workers)').fetchall()],
                'db_path': WORKERS_DB
            }
            
        with get_db_connection(CONSUMABLES_DB) as conn:
            database_schemas['Verbrauchsmaterial'] = {
                'table': 'consumables',
                'columns': [dict(name=row[1], type=row[2]) for row in conn.execute('PRAGMA table_info(consumables)').fetchall()],
                'db_path': CONSUMABLES_DB
            }
            
        return render_template('admin.html', schemas=database_schemas)
                             
    except Exception as e:
        print(f"Fehler im Admin-Panel: {str(e)}")
        traceback.print_exc()
        flash('Ein Fehler ist aufgetreten', 'error')
        return redirect(url_for('index'))

@app.route('/admin/add_column', methods=['POST'])
def add_column():
    """Neue Spalte zu einer Tabelle hinzufügen"""
    try:
        table_name = request.form.get('table')
        column_name = request.form.get('column_name')
        column_type = request.form.get('column_type')
        default_value = request.form.get('default_value')
        db_path = request.form.get('db_path')
        
        with get_db_connection(db_path) as conn:
            # Prüfe ob Spalte bereits existiert
            existing_columns = [row[1] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()]
            if column_name in existing_columns:
                flash(f'Spalte {column_name} existiert bereits', 'error')
                return redirect(url_for('admin_panel'))
            
            # Spalte hinzufügen
            if default_value:
                conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}')
            else:
                conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}')
            
            flash(f'Spalte {column_name} wurde hinzugefügt', 'success')
            
        return redirect(url_for('admin_panel'))
        
    except Exception as e:
        flash(f'Fehler beim Hinzufügen der Spalte: {str(e)}', 'error')
        return redirect(url_for('admin_panel'))

@app.route('/validate_barcode/<barcode>/<int:step>')
def validate_barcode(barcode, step):
    """Überprüft ob ein Barcode in der entsprechenden Datenbank existiert"""
    try:
        if step == 1:
            # Prüfe Werkzeug/Material
            with get_db_connection(TOOLS_DB) as conn:
                tool = conn.execute('SELECT barcode FROM tools WHERE barcode = ?', 
                                  (barcode,)).fetchone()
                if tool:
                    return jsonify({'valid': True})
                    
            with get_db_connection(CONSUMABLES_DB) as conn:
                consumable = conn.execute('SELECT barcode FROM consumables WHERE barcode = ?', 
                                        (barcode,)).fetchone()
                if consumable:
                    return jsonify({'valid': True})
                    
            return jsonify({'valid': False})
            
        elif step == 2:
            # Prüfe Mitarbeiter
            with get_db_connection(WORKERS_DB) as conn:
                worker = conn.execute('SELECT barcode FROM workers WHERE barcode = ?', 
                                    (barcode,)).fetchone()
                return jsonify({'valid': bool(worker)})
                
    except Exception as e:
        print(f"Validierungsfehler: {str(e)}")
        return jsonify({'valid': False})

def get_active_lendings():
    """Holt alle aktiven Ausleihen mit Werkzeug- und Mitarbeiterdaten"""
    try:
        with get_db_connection(LENDINGS_DB) as conn:
            # Datenbanken anhängen
            conn.execute(f"ATTACH DATABASE '{TOOLS_DB}' AS tools_db")
            conn.execute(f"ATTACH DATABASE '{WORKERS_DB}' AS workers_db")
            conn.execute(f"ATTACH DATABASE '{CONSUMABLES_DB}' AS consumables_db")
            
            # Aktive Ausleihen abfragen
            active_lendings = conn.execute('''
                SELECT 
                    l.id,
                    COALESCE(t.gegenstand, c.bezeichnung) as tool_name,
                    w.name || ' ' || w.lastname as worker_name,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_time,
                    l.amount,
                    CASE 
                        WHEN t.barcode IS NOT NULL THEN 'Werkzeug'
                        ELSE 'Verbrauchsmaterial'
                    END as item_type,
                    COALESCE(c.einheit, '') as einheit
                FROM lendings l
                JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                LEFT JOIN tools_db.tools t ON l.tool_barcode = t.barcode
                LEFT JOIN consumables_db.consumables c ON l.tool_barcode = c.barcode
                WHERE l.return_time IS NULL
                ORDER BY l.checkout_time DESC
            ''').fetchall()
            
            return active_lendings
            
    except Exception as e:
        print(f"Fehler in get_active_lendings: {str(e)}")
        traceback.print_exc()
        return []

@app.route('/lend_tool/<barcode>', methods=['POST'])
def lend_tool(barcode):
    """Werkzeug ausleihen"""
    try:
        worker_barcode = request.form.get('worker_barcode')
        print(f"Versuche Ausleihe: Werkzeug {barcode} an Mitarbeiter {worker_barcode}")
        
        if not worker_barcode:
            flash('Mitarbeiter-Barcode fehlt', 'error')
            return redirect(url_for('index'))
        
        # Prüfe ob Werkzeug verfügbar
        with get_db_connection(TOOLS_DB) as conn:
            tool = conn.execute('SELECT * FROM tools WHERE barcode = ?', (barcode,)).fetchone()
            
            if not tool:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('index'))
            
            print(f"Werkzeug gefunden: {dict(tool)}")
            
            if tool['status'] != 'Verfügbar':
                flash('Werkzeug ist nicht verfügbar', 'error')
                return redirect(url_for('index'))
            
            # Status auf "Ausgeliehen" setzen
            conn.execute('''
                UPDATE tools 
                SET status = 'Ausgeliehen' 
                WHERE barcode = ?
            ''', (barcode,))
            conn.commit()
            print("Werkzeug-Status aktualisiert")
        
        # Ausleihe in lendings Tabelle dokumentieren
        with get_db_connection(LENDINGS_DB) as conn:
            conn.execute('''
                INSERT INTO lendings 
                (tool_barcode, worker_barcode, checkout_time, amount)
                VALUES (?, ?, datetime('now', 'localtime'), 1)
            ''', (barcode, worker_barcode))
            conn.commit()
            print("Ausleihe in Datenbank dokumentiert")
        
        flash(f'Werkzeug {tool["gegenstand"]} erfolgreich ausgeliehen', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"Fehler beim Ausleihen: {str(e)}")
        traceback.print_exc()
        flash('Fehler beim Ausleihen', 'error')
        return redirect(url_for('index'))

# App starten
if __name__ == '__main__':
    # Nur Tabellen erstellen falls sie nicht existieren
    print("Initialisiere Datenbanken...")
    init_dbs()
    
    print("\nPrüfe Datenbankstatus:")
    check_dbs()
    
    app.run(debug=True)