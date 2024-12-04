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
                    table_name = cat_conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        LIMIT 1
                    """).fetchone()['name']
                    
                    items = cat_conn.execute(f'SELECT * FROM {table_name}').fetchall()
                
                return render_template('category/list.html',
                                    category=category,
                                    items=items)
        except Exception as e:
            logging.error(f"Fehler beim Laden der Kategorie-Items: {str(e)}")
            flash('Fehler beim Laden der Items', 'error')
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

    @app.route('/category/<int:category_id>/item/<int:item_id>')
    def item_details(category_id, item_id):
        try:
            # Hole Kategorie-Informationen
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
                
                # Verbinde mit der Kategorie-DB
                db_path = os.path.join(Config.INSTANCE_PATH, category['db_name'])
                with get_db_connection(db_path) as cat_conn:
                    # Hole den Namen der ersten Tabelle
                    table_name = cat_conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        LIMIT 1
                    """).fetchone()['name']
                    
                    # Hole das spezifische Item
                    item = cat_conn.execute(f'SELECT * FROM {table_name} WHERE id = ?', [item_id]).fetchone()
                    
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