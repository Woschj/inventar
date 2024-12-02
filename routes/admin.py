from routes import admin_bp
from flask import render_template, redirect, url_for, flash, request, session
from database import get_db_connection, DBConfig
from auth import admin_required, check_admin_password
import logging
import traceback

@admin_bp.route('/admin')
@admin_required
def admin_panel():
    """Admin-Dashboard anzeigen"""
    return render_template('admin.html')

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin Login verarbeiten"""
    if request.method == 'POST':
        password = request.form.get('password')
        
        if check_admin_password(password):
            session['is_admin'] = True
            flash('Admin-Login erfolgreich', 'success')
            return redirect(url_for('admin_panel'))
        else:
            flash('Falsches Passwort', 'error')
            
    return render_template('admin_login.html')

@admin_bp.route('/admin/logout')
def admin_logout():
    """Admin ausloggen"""
    session.pop('is_admin', None)
    flash('Admin-Logout erfolgreich', 'success')
    return redirect(url_for('index'))

@admin_bp.route('/admin/trash')
@admin_required
def trash():
    """Papierkorb anzeigen"""
    try:
        deleted_items = {
            'workers': [],
            'tools': [],
            'consumables': []
        }
        
        # Gelöschte Mitarbeiter
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            deleted_items['workers'] = conn.execute('''
                SELECT *, 
                strftime('%d.%m.%Y %H:%M', deleted_at) as deleted_at_formatted 
                FROM deleted_workers 
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        # Gelöschte Werkzeuge
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            deleted_items['tools'] = conn.execute('''
                SELECT *,
                strftime('%d.%m.%Y %H:%M', deleted_at) as deleted_at_formatted
                FROM deleted_tools
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        # Gelöschte Verbrauchsmaterialien
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            deleted_items['consumables'] = conn.execute('''
                SELECT *,
                strftime('%d.%m.%Y %H:%M', deleted_at) as deleted_at_formatted
                FROM deleted_consumables
                ORDER BY deleted_at DESC
            ''').fetchall()
            
        return render_template('trash.html', deleted_items=deleted_items)
        
    except Exception as e:
        print(f"FEHLER beim Laden des Papierkorbs: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Laden des Papierkorbs', 'error')
        return redirect(url_for('admin_panel'))

@admin_bp.route('/admin/restore/worker/<int:id>')
@admin_required
def restore_worker(id):
    """Mitarbeiter aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.WORKERS_DB) as conn:
            item = conn.execute(
                'SELECT * FROM deleted_workers WHERE id=?', (id,)
            ).fetchone()
            
            if item:
                # Prüfen ob Barcode bereits wieder existiert
                existing = conn.execute(
                    'SELECT 1 FROM workers WHERE barcode=?',
                    (item['barcode'],)
                ).fetchone()
                
                if existing:
                    flash('Ein Mitarbeiter mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('trash'))
                
                conn.execute('''
                    INSERT INTO workers 
                    (name, lastname, barcode, bereich, email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item['name'], item['lastname'], item['barcode'],
                      item['bereich'], item['email']))
                conn.commit()
                
                flash('Mitarbeiter wiederhergestellt', 'success')
            else:
                flash('Gelöschter Mitarbeiter nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler bei Wiederherstellung: {str(e)}")
        traceback.print_exc()
        flash('Fehler bei der Wiederherstellung', 'error')
        
    return redirect(url_for('trash'))

@admin_bp.route('/admin/restore/tool/<int:id>')
@admin_required
def restore_tool(id):
    """Werkzeug aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            item = conn.execute(
                'SELECT * FROM deleted_tools WHERE id=?', (id,)
            ).fetchone()
            
            if item:
                # Prüfen ob Barcode bereits wieder existiert
                existing = conn.execute(
                    'SELECT 1 FROM tools WHERE barcode=?',
                    (item['barcode'],)
                ).fetchone()
                
                if existing:
                    flash('Ein Werkzeug mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('trash'))
                
                conn.execute('''
                    INSERT INTO tools 
                    (barcode, gegenstand, ort, typ, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item['barcode'], item['gegenstand'], item['ort'],
                      item['typ'], item['status']))
                conn.commit()
                
                flash('Werkzeug wiederhergestellt', 'success')
            else:
                flash('Gelöschtes Werkzeug nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler bei Wiederherstellung: {str(e)}")
        traceback.print_exc()
        flash('Fehler bei der Wiederherstellung', 'error')
        
    return redirect(url_for('trash'))

@admin_bp.route('/admin/restore/consumable/<int:id>')
@admin_required
def restore_consumable(id):
    """Verbrauchsmaterial aus dem Papierkorb wiederherstellen"""
    try:
        with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
            item = conn.execute(
                'SELECT * FROM deleted_consumables WHERE id=?', (id,)
            ).fetchone()
            
            if item:
                # Prüfen ob Barcode bereits wieder existiert
                existing = conn.execute(
                    'SELECT 1 FROM consumables WHERE barcode=?',
                    (item['barcode'],)
                ).fetchone()
                
                if existing:
                    flash('Ein Material mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('trash'))
                
                conn.execute('''
                    INSERT INTO consumables 
                    (barcode, bezeichnung, ort, typ, mindestbestand, einheit)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (item['barcode'], item['bezeichnung'], item['ort'],
                      item['typ'], item['mindestbestand'], item['einheit']))
                conn.commit()
                
                flash('Material wiederhergestellt', 'success')
            else:
                flash('Gelöschtes Material nicht gefunden', 'error')
                
    except Exception as e:
        print(f"Fehler bei Wiederherstellung: {str(e)}")
        traceback.print_exc()
        flash('Fehler bei der Wiederherstellung', 'error')
        
    return redirect(url_for('trash')) 