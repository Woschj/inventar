from routes import workers_bp
from flask import render_template, redirect, url_for, flash, request, session
from database import get_db_connection, DBConfig
from auth import admin_required
import logging
import traceback

@workers_bp.route('/workers')
def workers():
    print("\n=== WORKERS ROUTE ===")
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers ORDER BY lastname, name').fetchall()
            
            # Hole aktuelle Ausleihen für jeden Mitarbeiter
            with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
                lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
                lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
                
                for worker in workers:
                    # Hole Werkzeug-Ausleihen
                    current_tools = lendings_conn.execute('''
                        SELECT l.*, t.gegenstand
                        FROM lendings l
                        JOIN tools_db.tools t ON l.item_barcode = t.barcode
                        WHERE l.worker_barcode = ? 
                        AND l.return_time IS NULL
                        AND l.item_type = 'tool'
                    ''', (worker['barcode'],)).fetchall()
                    
                    # Hole letzte Materialentnahmen
                    recent_consumables = lendings_conn.execute('''
                        SELECT l.*, c.bezeichnung
                        FROM lendings l
                        JOIN consumables_db.consumables c ON l.item_barcode = c.barcode
                        WHERE l.worker_barcode = ?
                        AND l.item_type = 'consumable'
                        ORDER BY l.checkout_time DESC
                        LIMIT 5
                    ''', (worker['barcode'],)).fetchall()
                    
                    # Füge die Informationen zum Worker-Dict hinzu
                    worker_dict = dict(worker)
                    worker_dict['current_tools'] = current_tools
                    worker_dict['recent_consumables'] = recent_consumables
                    
            return render_template('workers.html',
                                workers=workers,
                                is_admin=session.get('is_admin', False))
                                
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Laden der Mitarbeiter', 'error')
        return redirect(url_for('index'))

@workers_bp.route('/workers/<barcode>')
def worker_details(barcode):
    print(f"\n=== WORKER DETAILS für {barcode} ===")
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?',
                (barcode,)
            ).fetchone()
            
            if not worker:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers'))
            
            # Hole Ausleihhistorie
            with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
                lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
                lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
                
                # Hole alle Ausleihen
                lendings = lendings_conn.execute('''
                    SELECT 
                        l.*,
                        strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                        strftime('%d.%m.%Y %H:%M', l.return_time) as return_time,
                        CASE 
                            WHEN l.item_type = 'tool' THEN t.gegenstand
                            WHEN l.item_type = 'consumable' THEN c.bezeichnung
                        END as item_name
                    FROM lendings l
                    LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                    LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                    WHERE l.worker_barcode = ?
                    ORDER BY l.checkout_time DESC
                ''', (barcode,)).fetchall()
                
            return render_template('worker_details.html',
                                worker=worker,
                                lendings=lendings,
                                is_admin=session.get('is_admin', False))
                                
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Laden der Details', 'error')
        return redirect(url_for('workers'))

@workers_bp.route('/workers/add', methods=['GET', 'POST'])
@admin_required
def add_worker():
    print("\n=== ADD WORKER ===")
    if request.method == 'POST':
        try:
            barcode = request.form.get('barcode')
            name = request.form.get('name')
            lastname = request.form.get('lastname')
            bereich = request.form.get('bereich')
            email = request.form.get('email')
            
            with get_db_connection(DBConfig.WORKERS_DB) as conn:
                # Prüfe ob Barcode bereits existiert
                existing = conn.execute(
                    'SELECT 1 FROM workers WHERE barcode = ?',
                    (barcode,)
                ).fetchone()
                
                if existing:
                    flash('Ein Mitarbeiter mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('add_worker'))
                
                conn.execute('''
                    INSERT INTO workers (barcode, name, lastname, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (barcode, name, lastname, bereich, email))
                
                conn.execute('''
                    INSERT INTO workers_history 
                    (worker_barcode, action, changed_fields, changed_by)
                    VALUES (?, 'create', ?, ?)
                ''', (
                    barcode,
                    'Mitarbeiter erstellt',
                    session.get('username', 'admin')
                ))
                
                conn.commit()
                
            flash('Mitarbeiter erfolgreich hinzugefügt', 'success')
            return redirect(url_for('workers'))
            
        except Exception as e:
            print(f"FEHLER: {str(e)}")
            print(traceback.format_exc())
            flash('Fehler beim Hinzufügen des Mitarbeiters', 'error')
            return redirect(url_for('add_worker'))
    
    return render_template('add_worker.html')

@workers_bp.route('/workers/<barcode>/edit', methods=['GET', 'POST'])
@admin_required
def edit_worker(barcode):
    print(f"\n=== EDIT WORKER für {barcode} ===")
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            if request.method == 'POST':
                conn.execute('''
                    UPDATE workers 
                    SET name = ?,
                        lastname = ?,
                        bereich = ?,
                        email = ?
                    WHERE barcode = ?
                ''', (
                    request.form.get('name'),
                    request.form.get('lastname'),
                    request.form.get('bereich'),
                    request.form.get('email'),
                    barcode
                ))
                
                conn.execute('''
                    INSERT INTO workers_history 
                    (worker_barcode, action, changed_fields, changed_by)
                    VALUES (?, 'update', ?, ?)
                ''', (
                    barcode,
                    'Mitarbeiter bearbeitet',
                    session.get('username', 'admin')
                ))
                
                conn.commit()
                flash('Mitarbeiter erfolgreich aktualisiert', 'success')
                return redirect(url_for('worker_details', barcode=barcode))
            
            # GET Request
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?',
                (barcode,)
            ).fetchone()
            
            if not worker:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers'))
                
            return render_template('edit_worker.html', worker=worker)
                                
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Bearbeiten des Mitarbeiters', 'error')
        return redirect(url_for('workers')) 
