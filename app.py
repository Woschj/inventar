from flask import Flask, session, render_template, request, jsonify, g
from logging.handlers import TimedRotatingFileHandler
import logging
import os
import sys

# Import Blueprints und Konfigurationen
from routes import consumables_bp, tools_bp, workers_bp, admin_bp, export_bp
from database import DBConfig, get_db_connection
from auth import admin_required, check_admin_password

# Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = 'dein_geheimer_schluessel_hier'  # In Produktion sicher speichern!
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
LOG_FOLDER = os.path.join(BASE_DIR, 'logs')

# Flask-App initialisieren
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    # Logging Setup
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            TimedRotatingFileHandler(
                os.path.join(LOG_FOLDER, 'app.log'),
                when='midnight',
                interval=1,
                backupCount=7
            )
        ]
    )
    
    # Stelle sicher, dass Upload-Ordner existiert
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # Datenbank-Initialisierung
    if not DBConfig.init_all_dbs():
        logging.error("Fehler bei der Datenbankinitialisierung")
        sys.exit(1)
    
    # Blueprints registrieren
    app.register_blueprint(consumables_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(workers_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(export_bp)
    
    return app

# App erstellen
app = create_app()

# Hauptrouten
@app.route('/')
def index():
    """Startseite"""
    return render_template('index.html', is_admin=session.get('is_admin', False))

@app.route('/scan')
def scan():
    """Barcode-Scanner-Seite"""
    return render_template('scan.html', is_admin=session.get('is_admin', False))

@app.route('/api/scan', methods=['POST'])
def handle_scan():
    """API-Endpunkt für Barcode-Scans"""
    try:
        data = request.get_json()
        barcode = data.get('barcode')
        
        if not barcode:
            return jsonify({'error': 'Kein Barcode übermittelt'})
        
        # Prüfe in allen Datenbanken
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            worker = conn.execute(
                'SELECT * FROM workers WHERE barcode = ?',
                (barcode,)
            ).fetchone()
            if worker:
                return jsonify({
                    'type': 'worker',
                    'data': dict(worker)
                })
        
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tool = conn.execute(
                'SELECT * FROM tools WHERE barcode = ?',
                (barcode,)
            ).fetchone()
            if tool:
                return jsonify({
                    'type': 'tool',
                    'data': dict(tool)
                })
        
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            consumable = conn.execute(
                'SELECT * FROM consumables WHERE barcode = ?',
                (barcode,)
            ).fetchone()
            if consumable:
                return jsonify({
                    'type': 'consumable',
                    'data': dict(consumable)
                })
        
        return jsonify({'error': 'Barcode nicht gefunden'})
        
    except Exception as e:
        print(f"FEHLER beim Scan: {str(e)}")
        return jsonify({'error': str(e)})

# Fehlerbehandlung
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# Teardown
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Development Server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)