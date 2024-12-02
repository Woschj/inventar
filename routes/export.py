from flask import send_file, flash, redirect, url_for
from database import get_db_connection, DBConfig
from auth import admin_required
from routes import export_bp
import csv
import io
import traceback

@export_bp.route('/export/workers')
@admin_required
def export_workers():
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            workers = conn.execute('SELECT * FROM workers ORDER BY lastname, name').fetchall()
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Schreibe Header
            writer.writerow(['Barcode', 'Name', 'Nachname', 'Bereich', 'Email'])
            
            # Schreibe Daten
            for worker in workers:
                writer.writerow([
                    worker['barcode'],
                    worker['name'],
                    worker['lastname'],
                    worker['bereich'],
                    worker['email']
                ])
            
            # Bereite Download vor
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='mitarbeiter.csv'
            )
            
    except Exception as e:
        print(f"FEHLER beim Export: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Export der Mitarbeiter', 'error')
        return redirect(url_for('admin_panel'))

@export_bp.route('/export/tools')
@admin_required
def export_tools():
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tools = conn.execute('SELECT * FROM tools ORDER BY gegenstand').fetchall()
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Schreibe Header
            writer.writerow(['Barcode', 'Gegenstand', 'Ort', 'Typ', 'Status'])
            
            # Schreibe Daten
            for tool in tools:
                writer.writerow([
                    tool['barcode'],
                    tool['gegenstand'],
                    tool['ort'],
                    tool['typ'],
                    tool['status']
                ])
            
            # Bereite Download vor
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='werkzeuge.csv'
            )
            
    except Exception as e:
        print(f"FEHLER beim Export: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Export der Werkzeuge', 'error')
        return redirect(url_for('admin_panel'))

@export_bp.route('/export/consumables')
@admin_required
def export_consumables():
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            consumables = conn.execute('SELECT * FROM consumables ORDER BY bezeichnung').fetchall()
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Schreibe Header
            writer.writerow(['Barcode', 'Bezeichnung', 'Ort', 'Typ', 'Status', 'Mindestbestand', 'Aktueller Bestand', 'Einheit'])
            
            # Schreibe Daten
            for item in consumables:
                writer.writerow([
                    item['barcode'],
                    item['bezeichnung'],
                    item['ort'],
                    item['typ'],
                    item['status'],
                    item['mindestbestand'],
                    item['aktueller_bestand'],
                    item['einheit']
                ])
            
            # Bereite Download vor
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='verbrauchsmaterial.csv'
            )
            
    except Exception as e:
        print(f"FEHLER beim Export: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Export der Verbrauchsmaterialien', 'error')
        return redirect(url_for('admin_panel')) 