from flask import Flask, render_template, session, redirect, url_for, request, jsonify
import logging
import os
from src.config.database import DBConfig
from src.utils.database import init_all_databases
from src.routes.admin import admin_bp
from src.routes.tools import tools_bp
from src.routes.consumables import consumables_bp
from src.routes.lending import lending_bp
from src.routes.workers import workers_bp
from src.utils.excel_handler import ExcelHandler

# Setze das Arbeitsverzeichnis
os.chdir(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.register_blueprint(export_bp, url_prefix='/export')
app.secret_key = "dein-geheimer-schluessel"

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(tools_bp, url_prefix='/tools')
app.register_blueprint(consumables_bp, url_prefix='/consumables')
app.register_blueprint(lending_bp, url_prefix='/lending')
app.register_blueprint(workers_bp, url_prefix='/workers')

@app.route('/')
def index():
    if not session.get('is_admin'):
        return redirect(url_for('admin.login'))
    return redirect(url_for('tools.index'))

@app.route('/return_tool', methods=['POST'])
def return_tool():
    try:
        barcode = request.form.get('barcode')
        
        if not barcode:
            return jsonify({'success': False, 'message': 'Kein Barcode übermittelt'})
            
        with get_db_connection(DBConfig.LENDINGS_DB) as conn:
            conn.execute(f"ATTACH DATABASE '{DBConfig.TOOLS_DB}' AS tools_db")
            
            # Prüfe ob Ausleihe existiert
            lending = conn.execute('''
                SELECT * FROM lendings 
                WHERE item_barcode = ? AND return_time IS NULL
            ''', (barcode,)).fetchone()
            
            if not lending:
                return jsonify({'success': False, 'message': 'Keine aktive Ausleihe gefunden'})
            
            # Aktualisiere Ausleihe und Werkzeugstatus
            conn.execute('''
                UPDATE lendings 
                SET return_time = CURRENT_TIMESTAMP 
                WHERE item_barcode = ? AND return_time IS NULL
            ''', (barcode,))
            
            conn.execute('''
                UPDATE tools_db.tools 
                SET status = 'Verfügbar' 
                WHERE barcode = ?
            ''', (barcode,))
            
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Werkzeug erfolgreich zurückgegeben'})
            
    except Exception as e:
        logging.error(f"Fehler bei Werkzeugrückgabe: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/export_db/<db_name>')
def export_db(db_name):
    try:
        db_map = {
            'workers': DBConfig.WORKERS_DB,
            'tools': DBConfig.TOOLS_DB,
            'lendings': DBConfig.LENDINGS_DB,
            'consumables': DBConfig.CONSUMABLES_DB
        }
        
        if db_name not in db_map:
            return jsonify({'success': False, 'message': 'Ungültige Datenbank'})
            
        success, result = ExcelHandler.export_to_excel(db_map[db_name])
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'Export erfolgreich',
                'file_path': result
            })
        else:
            return jsonify({'success': False, 'message': result})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/import_db/<db_name>', methods=['POST'])
def import_db(db_name):
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Keine Datei übermittelt'})
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Keine Datei ausgewählt'})
            
        db_map = {
            'workers': DBConfig.WORKERS_DB,
            'tools': DBConfig.TOOLS_DB,
            'lendings': DBConfig.LENDINGS_DB,
            'consumables': DBConfig.CONSUMABLES_DB
        }
        
        if db_name not in db_map:
            return jsonify({'success': False, 'message': 'Ungültige Datenbank'})
            
        # Temporär speichern
        temp_path = os.path.join('temp', file.filename)
        os.makedirs('temp', exist_ok=True)
        file.save(temp_path)
        
        success, message = ExcelHandler.import_from_excel(temp_path, db_map[db_name])
        
        # Lösche temporäre Datei
        os.remove(temp_path)
        
        return jsonify({'success': success, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    print("Starting initialization...")
    if init_all_databases():
        logging.info("Datenbanken erfolgreich initialisiert")
        import src.create_test_data as create_test_data
        create_test_data.create_test_data()
        print("Server starting on http://127.0.0.1:5000")
        # Explizite Werkzeug-Konfiguration
        import werkzeug.serving
        werkzeug.serving.run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader=False)
    else:
        logging.error("Fehler bei der Datenbankinitialisierung")