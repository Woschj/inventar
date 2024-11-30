from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import logging
import traceback
import sqlite3
from config import DBConfig
from auth import admin_required
from core.database import get_db_connection

consumables_bp = Blueprint('consumables', __name__, url_prefix='/consumables')

@consumables_bp.route('/')
def consumables():
    try:
        filter_status = request.args.get('filter')
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
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
                query += ''' 
                    WHERE CASE 
                        WHEN aktueller_bestand = 0 THEN 'Leer'
                        WHEN aktueller_bestand <= mindestbestand THEN 'Nachbestellen'
                        ELSE 'Verfügbar'
                    END = ?
                '''
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

@consumables_bp.route('/<barcode>/delete', methods=['POST'])
def delete_consumable(barcode):
    try:
        user = session.get('username', 'System')
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            # Get consumable data before deletion
            consumable = conn.execute(
                'SELECT * FROM consumables WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not consumable:
                return jsonify({'success': False, 'error': 'Material nicht gefunden'})

            # Insert into deleted_consumables
            conn.execute('''
                INSERT INTO deleted_consumables 
                (original_barcode, bezeichnung, ort, typ, mindestbestand, 
                 aktueller_bestand, einheit, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (consumable['barcode'], consumable['bezeichnung'], 
                 consumable['ort'], consumable['typ'], consumable['mindestbestand'],
                 consumable['aktueller_bestand'], consumable['einheit'], user))

            # Delete the consumable
            conn.execute('DELETE FROM consumables WHERE barcode = ?', (barcode,))
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# ... weitere Consumables-Routen hier ... 