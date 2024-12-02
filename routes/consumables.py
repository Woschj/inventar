from flask import render_template, redirect, url_for, flash, request, jsonify, session
from database import get_db_connection, DBConfig
from auth import admin_required
from routes import consumables_bp
import logging
import traceback

@consumables_bp.route('/consumables')
def consumables():
    print("\n=== CONSUMABLES ROUTE ===")
    try:
        print("Hole Filter-Parameter...")
        filter_status = request.args.get('filter_status')
        filter_ort = request.args.get('filter_ort')
        filter_typ = request.args.get('filter_typ')
        print(f"Filter: Status={filter_status}, Ort={filter_ort}, Typ={filter_typ}")
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            print("Baue SQL-Query...")
            query = '''
                SELECT *,
                CASE 
                    WHEN aktueller_bestand = 0 OR aktueller_bestand IS NULL THEN 'Leer'
                    WHEN aktueller_bestand <= mindestbestand THEN 'Nachbestellen'
                    ELSE 'Verfügbar'
                END as status
                FROM consumables
                WHERE 1=1
            '''
            
            params = []
            print("Wende Filter an...")
            if filter_status:
                query += ''' AND CASE 
                    WHEN aktueller_bestand = 0 OR aktueller_bestand IS NULL THEN 'Leer'
                    WHEN aktueller_bestand <= mindestbestand THEN 'Nachbestellen'
                    ELSE 'Verfügbar'
                END = ? '''
                params.append(filter_status)
                
            if filter_ort:
                query += ' AND ort = ?'
                params.append(filter_ort)
                
            if filter_typ:
                query += ' AND typ = ?'
                params.append(filter_typ)
            
            print("Führe Hauptabfrage aus...")
            consumables = conn.execute(query + ' ORDER BY bezeichnung', params).fetchall()
            print(f"Gefundene Verbrauchsmaterialien: {len(consumables)}")
            
            # Konvertiere Row-Objekte zu Dictionaries und setze Standardwerte
            consumables = [dict(item) for item in consumables]
            for item in consumables:
                item['aktueller_bestand'] = item.get('aktueller_bestand', 0) or 0
                item['mindestbestand'] = item.get('mindestbestand', 0) or 0
            
            print("Hole Filter-Optionen...")
            orte = conn.execute(
                'SELECT DISTINCT ort FROM consumables WHERE ort IS NOT NULL ORDER BY ort'
            ).fetchall()
            typen = conn.execute(
                'SELECT DISTINCT typ FROM consumables WHERE typ IS NOT NULL ORDER BY typ'
            ).fetchall()
            print(f"Verfügbare Orte: {len(orte)}, Verfügbare Typen: {len(typen)}")
            
            print("Render Template...")
            return render_template('consumables.html',
                                consumables=consumables,
                                orte=orte,
                                typen=typen,
                                current_filters={
                                    'status': filter_status,
                                    'ort': filter_ort,
                                    'typ': filter_typ
                                },
                                is_admin=session.get('is_admin', False))
                                
    except Exception as e:
        print(f"\nFEHLER in Consumables-Route:")
        print(f"Fehlertyp: {type(e).__name__}")
        print(f"Fehlermeldung: {str(e)}")
        print("Stacktrace:")
        print(traceback.format_exc())
        flash('Fehler beim Laden der Verbrauchsmaterialien', 'error')
        return redirect(url_for('index'))

@consumables_bp.route('/consumables/<barcode>')
def consumable_details(barcode):
    print(f"\n=== CONSUMABLE DETAILS für {barcode} ===")
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            consumable = conn.execute('''
                SELECT * FROM consumables 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not consumable:
                print(f"FEHLER: Verbrauchsmaterial {barcode} nicht gefunden")
                flash('Verbrauchsmaterial nicht gefunden', 'error')
                return redirect(url_for('consumables'))

            consumable = dict(consumable)
            consumable['aktueller_bestand'] = int(consumable.get('aktueller_bestand', 0) or 0)
            consumable['mindestbestand'] = int(consumable.get('mindestbestand', 0) or 0)
            
            # Hole Ausleihhistorie
            with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
                lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
                lendings = lendings_conn.execute('''
                    SELECT 
                        l.*,
                        strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                        w.name || ' ' || w.lastname as worker_name
                    FROM lendings l
                    LEFT JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                    WHERE l.item_barcode = ?
                    ORDER BY l.checkout_time DESC
                ''', (barcode,)).fetchall()
            
            return render_template('consumable_details.html', 
                                consumable=consumable,
                                lendings=lendings,
                                is_admin=session.get('is_admin', False))
                                 
    except Exception as e:
        print(f"FEHLER beim Laden der Details: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Laden der Details', 'error')
        return redirect(url_for('consumables'))

@consumables_bp.route('/api/update_stock', methods=['POST'])
def update_stock():
    print("\n=== UPDATE STOCK API ===")
    try:
        data = request.get_json()
        barcode = data.get('barcode')
        new_stock = int(data.get('stock', 0) or 0)
        
        print(f"Update Stock: Barcode={barcode}, Neuer Bestand={new_stock}")
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            old_stock = conn.execute(
                'SELECT aktueller_bestand FROM consumables WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if old_stock:
                old_stock = old_stock['aktueller_bestand'] or 0
                print(f"Alter Bestand: {old_stock}")
                
                conn.execute('''
                    UPDATE consumables 
                    SET aktueller_bestand = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE barcode = ?
                ''', (new_stock, barcode))
                conn.commit()
                print("Bestand erfolgreich aktualisiert")
                
                return jsonify({
                    'success': True,
                    'old_stock': old_stock,
                    'new_stock': new_stock
                })
            
            print("WARNUNG: Item nicht gefunden")
            return jsonify({'error': 'Item nicht gefunden'})
            
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        return jsonify({'error': str(e)})