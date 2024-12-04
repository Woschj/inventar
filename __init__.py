def create_app():
    app = Flask(__name__)
    # ... andere Initialisierungen ...
    
    # Initialisiere Kategorie-System
    init_category_database()
    create_category_routes()
    
    return app 