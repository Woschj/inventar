from flask import render_template, request, redirect, url_for, flash, g, session
import logging
import sqlite3
from functools import wraps
from decorators import admin_required
from config import Config, DBConfig
import os

def get_db_connection(db_path):
    """Erstellt eine Datenbankverbindung"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_menu_categories():
    """Holt alle Kategorien für das Menü, gruppiert nach Abteilungen"""
    try:
        system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
        with get_db_connection(system_db) as conn:
            categories = conn.execute('''
                SELECT c.*, d.name as department_name 
                FROM categories c
                LEFT JOIN departments d ON c.department = d.id
                ORDER BY d.name, c.name
            ''').fetchall()
            
            menu = {}
            for cat in categories:
                dept = cat['department_name'] or 'Sonstige'
                if dept not in menu:
                    menu[dept] = []
                menu[dept].append({
                    'id': cat['id'],
                    'name': cat['name'],
                    'db_name': cat['db_name']
                })
            return menu
    except Exception as e:
        logging.error(f"Fehler beim Laden der Menü-Kategorien: {str(e)}")
        return {}

def init_routes(app):
    """Initialisiert alle Routen der App"""
    
    @app.before_request
    def before_request():
        """Wird vor jeder Anfrage ausgeführt"""
        g.menu_categories = get_menu_categories()

    @app.route('/')
    def index():
        """Zeigt die Startseite mit allen Kategorien"""
        return render_template('index.html')

    @app.route('/category/<int:category_id>')
    def list_category_items(category_id):
        try:
            system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
            with get_db_connection(system_db) as conn:
                category = conn.execute('''
                    SELECT c.*, d.name as department_name 
                    FROM categories c
                    LEFT JOIN departments d ON c.department = d.id
                    WHERE c.id = ?
                ''', [category_id]).fetchone()
                
                if not category:
                    flash('Kategorie nicht gefunden', 'error')
                    return redirect(url_for('index'))
                
                db_path = os.path.join(Config.INSTANCE_PATH, category['db_name'])
                with get_db_connection(db_path) as cat_conn:
                    table_info = cat_conn.execute("""
                        SELECT sql FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        LIMIT 1
                    """).fetchone()
                    
                    # Parse Schema und hole Daten
                    schema = parse_table_schema(table_info['sql'])
                    
                    # Hole distinkte Werte für Filter
                    table_name = cat_conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' LIMIT 1
                    """).fetchone()['name']
                    
                    # Füge distinkte Werte zum Schema hinzu
                    for column in schema:
                        if column.get('filterable'):
                            distinct_values = cat_conn.execute(
                                f'SELECT DISTINCT {column["name"]} FROM {table_name}'
                            ).fetchall()
                            column['distinct_values'] = [row[0] for row in distinct_values if row[0]]
                    
                    items = cat_conn.execute(f'SELECT * FROM {table_name}').fetchall()
                
                return render_template('category/list.html',
                                    category=category,
                                    items=items,
                                    schema=schema)
        except Exception as e:
            logging.error(f"Fehler beim Laden der Kategorie-Items: {str(e)}")
            flash('Fehler beim Laden der Items', 'error')
            return redirect(url_for('index'))

    @app.route('/category/<int:category_id>/add', methods=['GET', 'POST'])
    @admin_required
    def add_category_item(category_id):
        try:
            system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
            with get_db_connection(system_db) as conn:
                category = conn.execute('''
                    SELECT c.*, d.name as department_name, c.schema as schema
                    FROM categories c
                    LEFT JOIN departments d ON c.department = d.id
                    WHERE c.id = ?
                ''', [category_id]).fetchone()
                
                if not category:
                    flash('Kategorie nicht gefunden', 'error')
                    return redirect(url_for('index'))
                
                db_path = os.path.join(Config.INSTANCE_PATH, category['db_name'])
                with get_db_connection(db_path) as cat_conn:
                    table_info = cat_conn.execute("""
                        SELECT sql FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        LIMIT 1
                    """).fetchone()
                    
                    try:
                        if request.method == 'POST':
                            columns = []
                            values = []
                            for key in request.form:
                                if key != 'csrf_token':
                                    columns.append(key)
                                    values.append(request.form[key])
                            
                            table_name = cat_conn.execute("""
                                SELECT name FROM sqlite_master 
                                WHERE type='table' 
                                LIMIT 1
                            """).fetchone()['name']
                            
                            placeholders = ','.join(['?' for _ in values])
                            columns_str = ','.join(columns)
                            
                            cat_conn.execute(f'''
                                INSERT INTO {table_name} ({columns_str})
                                VALUES ({placeholders})
                            ''', values)
                            cat_conn.commit()
                            
                            flash('Eintrag erfolgreich hinzugefügt', 'success')
                            return redirect(url_for('list_category_items', category_id=category_id))
                    except Exception as e:
                        flash(f'Fehler beim Hinzufügen: {str(e)}', 'error')
                    
                    schema = parse_table_schema(table_info['sql'])
                    return render_template('category/add_item.html', 
                                         category=category,
                                         schema=schema)
                                         
        except Exception as e:
            logging.error(f"Fehler beim Laden des Add-Formulars: {str(e)}")
            flash('Fehler beim Laden', 'error')
            return redirect(url_for('index'))

    @app.route('/category/<int:category_id>/edit/<int:item_id>', methods=['GET', 'POST'])
    @admin_required
    def edit_category_item(category_id, item_id):
        try:
            system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
            with get_db_connection(system_db) as conn:
                category = conn.execute('''
                    SELECT c.*, d.name as department_name, c.schema as schema
                    FROM categories c
                    LEFT JOIN departments d ON c.department = d.id
                    WHERE c.id = ?
                ''', [category_id]).fetchone()
                
                if not category:
                    flash('Kategorie nicht gefunden', 'error')
                    return redirect(url_for('index'))
                
                db_path = os.path.join(Config.INSTANCE_PATH, category['db_name'])
                with get_db_connection(db_path) as cat_conn:
                    table_name = cat_conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        LIMIT 1
                    """).fetchone()['name']
                    
                    if request.method == 'POST':
                        try:
                            updates = []
                            values = []
                            for key in request.form:
                                if key != 'csrf_token':
                                    updates.append(f"{key} = ?")
                                    values.append(request.form[key])
                            values.append(item_id)  # für WHERE id = ?
                            
                            cat_conn.execute(f'''
                                UPDATE {table_name}
                                SET {', '.join(updates)}
                                WHERE id = ?
                            ''', values)
                            cat_conn.commit()
                            
                            flash('Eintrag erfolgreich aktualisiert', 'success')
                            return redirect(url_for('list_category_items', category_id=category_id))
                            
                        except Exception as e:
                            flash(f'Fehler beim Aktualisieren: {str(e)}', 'error')
                    
                    item = cat_conn.execute(f'SELECT * FROM {table_name} WHERE id = ?', 
                                          [item_id]).fetchone()
                    
                    if not item:
                        flash('Eintrag nicht gefunden', 'error')
                        return redirect(url_for('list_category_items', category_id=category_id))
                    
                    table_info = cat_conn.execute("""
                        SELECT sql FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        LIMIT 1
                    """).fetchone()
                    
                    schema = parse_table_schema(table_info['sql'])
                    
                    return render_template('category/edit_item.html', 
                                         category=category,
                                         item=item,
                                         schema=schema)
                                         
        except Exception as e:
            logging.error(f"Fehler beim Laden des Edit-Formulars: {str(e)}")
            flash('Fehler beim Laden', 'error')
            return redirect(url_for('index'))

    def parse_table_schema(sql):
        """Hilfsfunktion zum Parsen des Schemas"""
        try:
            columns_part = sql.split('(', 1)[1].rsplit(')', 1)[0]
            columns = []
            for col in columns_part.split(','):
                col = col.strip()
                if col and not col.startswith(('PRIMARY KEY', 'FOREIGN KEY')):
                    name = col.split()[0]
                    type_ = col.split()[1]
                    
                    # Bestimme Spaltentyp und Eigenschaften
                    column = {
                        'name': name,
                        'type': 'text',  # Standard-Typ
                        'label': name.replace('_', ' ').title(),
                        'width': None,
                        'filterable': True  # Standardmäßig filterbar
                    }
                    
                    # Spezielle Spaltentypen
                    if 'barcode' in name.lower():
                        column['type'] = 'barcode'
                    elif 'status' in name.lower():
                        column['type'] = 'status'
                    elif name == 'name':
                        column['type'] = 'link'
                        column['width'] = '1/4'
                    elif type_.startswith('VARCHAR'):
                        column['type'] = 'badge'
                    
                    columns.append(column)
            return columns
        except Exception as e:
            logging.error(f"Fehler beim Parsen des Schemas: {str(e)}")
            return []
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            password = request.form.get('password')
            if password == app.config['ADMIN_PASSWORD']:
                session['is_admin'] = True
                flash('Erfolgreich als Admin eingeloggt', 'success')
                return redirect(url_for('index'))
            flash('Falsches Passwort', 'error')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.pop('is_admin', None)
        flash('Erfolgreich ausgeloggt', 'success')
        return redirect(url_for('index'))

    @app.route('/admin/categories')
    @admin_required
    def admin_categories():
        """Zeigt die Kategorieverwaltung"""
        try:
            system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
            with get_db_connection(system_db) as conn:
                categories = conn.execute('''
                    SELECT c.*, d.name as department_name 
                    FROM categories c
                    LEFT JOIN departments d ON c.department = d.id
                    ORDER BY d.name, c.name
                ''').fetchall()
                
                departments = conn.execute('SELECT * FROM departments').fetchall()
                
            return render_template('admin/categories.html',
                                categories=categories,
                                departments=departments)
        except Exception as e:
            logging.error(f"Fehler beim Laden der Kategorien: {str(e)}")
            flash('Fehler beim Laden der Kategorien', 'error')
            return redirect(url_for('index'))

    @app.route('/admin/categories/create', methods=['GET', 'POST'])
    @admin_required
    def create_category():
        """Erstellt eine neue Kategorie mit eigener Datenbank"""
        if request.method == 'POST':
            name = request.form.get('name')
            department = request.form.get('department')
            schema = request.form.get('schema')
            
            if DBConfig.create_category_db(name, schema):
                flash('Kategorie erfolgreich erstellt', 'success')
                return redirect(url_for('admin_categories'))
            else:
                flash('Fehler beim Erstellen der Kategorie', 'error')
        
        system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
        with get_db_connection(system_db) as conn:
            departments = conn.execute('SELECT * FROM departments').fetchall()
            
        return render_template('admin/create_category.html',
                             departments=departments)

    @app.route('/category/<int:category_id>/item/<int:item_id>')
    def item_details(category_id, item_id):
        """Zeigt die Details eines Items"""
        try:
            system_db = os.path.join(Config.INSTANCE_PATH, 'system.db')
            with get_db_connection(system_db) as conn:
                category = conn.execute('''
                    SELECT c.*, d.name as department_name 
                    FROM categories c
                    LEFT JOIN departments d ON c.department = d.id
                    WHERE c.id = ?
                ''', [category_id]).fetchone()
                
                if not category:
                    flash('Kategorie nicht gefunden', 'error')
                    return redirect(url_for('index'))
                
                db_path = os.path.join(Config.INSTANCE_PATH, category['db_name'])
                with get_db_connection(db_path) as cat_conn:
                    table_name = cat_conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        LIMIT 1
                    """).fetchone()['name']
                    
                    item = cat_conn.execute(f'SELECT * FROM {table_name} WHERE id = ?', 
                                          [item_id]).fetchone()
                    
                    if not item:
                        flash('Item nicht gefunden', 'error')
                        return redirect(url_for('list_category_items', category_id=category_id))
                    
                return render_template('category/details.html', 
                                     category=category,
                                     item=item)
        except Exception as e:
            logging.error(f"Fehler beim Laden der Item-Details: {str(e)}")
            flash('Fehler beim Laden der Details', 'error')
            return redirect(url_for('list_category_items', category_id=category_id))

    return app