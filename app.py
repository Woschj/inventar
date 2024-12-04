from flask import Flask
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
from config import Config, DBConfig
from routes import init_routes

def create_app():
    # Initialisiere Konfiguration
    Config.init()
    
    # Erstelle Flask App
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Logging Setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            TimedRotatingFileHandler(
                os.path.join(Config.INSTANCE_PATH, 'app.log'),
                when='midnight',
                interval=1,
                backupCount=7
            )
        ]
    )
    
    # Initialisiere Datenbanken
    if not DBConfig.init_all_dbs():
        logging.error("Fehler bei der Datenbankinitialisierung")
        return None
        
    # Initialisiere Routen
    init_routes(app)
    
    return app

# App-Initialisierung
app = create_app()

if __name__ == '__main__':
    if app:
        app.run(debug=True)
    else:
        logging.error("App konnte nicht gestartet werden")
        sys.exit(1)