from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import get_db_connection
from config import DBConfig
import logging

# Blueprint definieren
workers_bp = Blueprint('workers', __name__)

@workers_bp.route('/delete/<barcode>')
def delete_worker(barcode):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Prüfe ob Mitarbeiter existiert
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not worker:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers.list_workers'))
            
            # Prüfe auf aktive Ausleihen
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            active_lendings = conn.execute('''
                SELECT COUNT(*) as count 
                FROM lendings_db.lendings 
                WHERE worker_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()['count']
            
            if active_lendings > 0:
                flash('Mitarbeiter hat noch aktive Ausleihen', 'error')
                return redirect(url_for('workers.list_workers'))
            
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
        
    return redirect(url_for('workers.list_workers'))

@workers_bp.route('/<barcode>')
def worker_details(barcode):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not worker:
                flash('Mitarbeiter nicht gefunden', 'error')
                return redirect(url_for('workers.list_workers'))

            # Verbinde die Datenbanken
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            conn.execute(f"ATTACH DATABASE '{DBConfig.CONSUMABLES_DB}' AS consumables_db")
            
            # Debug-Ausgabe der Tabellenspalten
            logging.info("Lendings Tabellen-Schema:")
            schema = conn.execute("PRAGMA table_info(lendings_db.lendings)").fetchall()
            logging.info(str(schema))
            
            # Hole aktuelle Ausleihen
            current_lendings = conn.execute('''
                SELECT 
                    l.id,
                    l.worker_barcode,
                    l.item_barcode,
                    l.item_type,
                    l.checkout_time,
                    l.amount,
                    CASE 
                        WHEN l.item_type = 'tool' THEN t.gegenstand
                        WHEN l.item_type = 'consumable' THEN c.bezeichnung
                    END as item_name,
                    CASE 
                        WHEN l.item_type = 'consumable' THEN l.amount || ' ' || c.einheit
                        ELSE '1'
                    END as amount_display,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_checkout_time
                FROM lendings_db.lendings l
                LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                WHERE l.worker_barcode = ? AND l.return_time IS NULL
            ''', (barcode,)).fetchall()
            
            # Hole Ausleihhistorie
            lending_history = conn.execute('''
                SELECT 
                    l.id,
                    l.worker_barcode,
                    l.item_barcode,
                    l.item_type,
                    l.checkout_time,
                    l.return_time,
                    l.amount,
                    CASE 
                        WHEN l.item_type = 'tool' THEN t.gegenstand
                        WHEN l.item_type = 'consumable' THEN c.bezeichnung
                    END as item_name,
                    CASE 
                        WHEN l.item_type = 'consumable' THEN l.amount || ' ' || c.einheit
                        ELSE '1'
                    END as amount_display,
                    strftime('%d.%m.%Y %H:%M', l.checkout_time) as formatted_checkout_time,
                    strftime('%d.%m.%Y %H:%M', l.return_time) as formatted_return_time
                FROM lendings_db.lendings l
                LEFT JOIN tools_db.tools t ON l.item_barcode = t.barcode AND l.item_type = 'tool'
                LEFT JOIN consumables_db.consumables c ON l.item_barcode = c.barcode AND l.item_type = 'consumable'
                WHERE l.worker_barcode = ? AND l.return_time IS NOT NULL
                ORDER BY l.checkout_time DESC
            ''', (barcode,)).fetchall()
            
            return render_template('worker_details.html', 
                                 worker=worker,
                                 current_lendings=current_lendings,
                                 lending_history=lending_history)
            
    except Exception as e:
        logging.error(f"Datenbankfehler in worker_details: {str(e)}")
        flash('Fehler beim Laden der Mitarbeiterdetails', 'error')
        return redirect(url_for('workers.list_workers'))
@workers_bp.route('/<barcode>/delete', methods=['POST'])
def delete_worker(barcode):
    try:
        user = session.get('username', 'System')
        
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            # Get worker data before deletion
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not worker:
                return jsonify({'success': False, 'error': 'Mitarbeiter nicht gefunden'})

            # Check for active lendings
            conn.execute(f"ATTACH DATABASE '{DBConfig.LENDINGS_DB}' AS lendings_db")
            active_lendings = conn.execute('''
                SELECT COUNT(*) as count 
                FROM lendings_db.lendings 
                WHERE worker_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()['count']

            if active_lendings > 0:
                return jsonify({
                    'success': False, 
                    'error': 'Mitarbeiter hat noch aktive Ausleihen'
                })

            # Insert into deleted_workers
            conn.execute('''
                INSERT INTO deleted_workers 
                (barcode, name, lastname, bereich, email, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (worker['barcode'], worker['name'], worker['lastname'],
                 worker['bereich'], worker['email'], user))

            # Delete the worker
            conn.execute('DELETE FROM workers WHERE barcode = ?', (barcode,))
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}) 

@workers_bp.route('/update/<barcode>', methods=['POST'])
def update_worker(barcode):
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            name = request.form.get('name')
            lastname = request.form.get('lastname')
            bereich = request.form.get('bereich', '')
            email = request.form.get('email', '')  # Leerer String als Default
            
            # Aktualisiere den Mitarbeiter
            conn.execute('''
                UPDATE workers 
                SET name = ?, lastname = ?, bereich = ?, email = ?
                WHERE barcode = ?
            ''', (name, lastname, bereich, email if email else None, barcode))
            
            conn.commit()
            flash('Mitarbeiter erfolgreich aktualisiert', 'success')
            
        return redirect(url_for('workers.worker_details', barcode=barcode))
        
    except Exception as e:
        logging.error(f"Fehler beim Aktualisieren des Mitarbeiters: {str(e)}")
        flash('Fehler beim Aktualisieren des Mitarbeiters', 'error')
        return redirect(url_for('workers.list_workers')) 
