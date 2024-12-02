from routes import tools_bp
from flask import render_template, redirect, url_for, flash, request, session
from database import get_db_connection, DBConfig
from auth import admin_required
import logging
import traceback
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@tools_bp.route('/tools')
def tools():
    print("\n=== TOOLS ROUTE ===")
    try:
        print("Hole Filter-Parameter...")
        filter_status = request.args.get('filter_status')
        filter_ort = request.args.get('filter_ort')
        filter_typ = request.args.get('filter_typ')
        print(f"Filter: Status={filter_status}, Ort={filter_ort}, Typ={filter_typ}")
        
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            query = 'SELECT * FROM tools WHERE 1=1'
            params = []
            
            if filter_status:
                query += ' AND status = ?'
                params.append(filter_status)
            if filter_ort:
                query += ' AND ort = ?'
                params.append(filter_ort)
            if filter_typ:
                query += ' AND typ = ?'
                params.append(filter_typ)
            
            tools = conn.execute(query + ' ORDER BY gegenstand', params).fetchall()
            
            orte = conn.execute(
                'SELECT DISTINCT ort FROM tools WHERE ort IS NOT NULL ORDER BY ort'
            ).fetchall()
            typen = conn.execute(
                'SELECT DISTINCT typ FROM tools WHERE typ IS NOT NULL ORDER BY typ'
            ).fetchall()
            
            return render_template('tools.html',
                                tools=tools,
                                orte=orte,
                                typen=typen,
                                current_filters={
                                    'status': filter_status,
                                    'ort': filter_ort,
                                    'typ': filter_typ
                                },
                                is_admin=session.get('is_admin', False))
                                
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Laden der Werkzeuge', 'error')
        return redirect(url_for('index'))

@tools_bp.route('/tools/<barcode>')
def tool_details(barcode):
    print(f"\n=== TOOL DETAILS für {barcode} ===")
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            tool = conn.execute('''
                SELECT * FROM tools 
                WHERE barcode = ?
            ''', (barcode,)).fetchone()
            
            if not tool:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('tools'))
            
            # Hole Ausleihhistorie
            with get_db_connection(DBConfig.LENDINGS_DB) as lendings_conn:
                lendings_conn.execute(f"ATTACH DATABASE '{DBConfig.WORKERS_DB}' AS workers_db")
                lendings = lendings_conn.execute('''
                    SELECT 
                        l.*,
                        strftime('%d.%m.%Y %H:%M', l.checkout_time) as checkout_time,
                        strftime('%d.%m.%Y %H:%M', l.return_time) as return_time,
                        w.name || ' ' || w.lastname as worker_name
                    FROM lendings l
                    LEFT JOIN workers_db.workers w ON l.worker_barcode = w.barcode
                    WHERE l.item_barcode = ?
                    ORDER BY l.checkout_time DESC
                ''', (barcode,)).fetchall()
            
            # Hole Statusänderungshistorie
            status_history = conn.execute('''
                SELECT 
                    strftime('%d.%m.%Y %H:%M', timestamp) as timestamp,
                    old_status,
                    new_status,
                    comment,
                    changed_by
                FROM tool_status_history
                WHERE tool_barcode = ?
                ORDER BY timestamp DESC
            ''', (barcode,)).fetchall()
            
            return render_template('tool_details.html',
                                tool=tool,
                                lendings=lendings,
                                status_history=status_history,
                                is_admin=session.get('is_admin', False))
                                
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Laden der Details', 'error')
        return redirect(url_for('tools'))

@tools_bp.route('/tools/<barcode>/edit', methods=['GET', 'POST'])
@admin_required
def edit_tool(barcode):
    print(f"\n=== EDIT TOOL für {barcode} ===")
    try:
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            if request.method == 'POST':
                # Bild-Upload
                if 'image' in request.files:
                    file = request.files['image']
                    if file and allowed_file(file.filename):
                        filename = secure_filename(f"{barcode}_{file.filename}")
                        if not os.path.exists(UPLOAD_FOLDER):
                            os.makedirs(UPLOAD_FOLDER)
                        file.save(os.path.join(UPLOAD_FOLDER, filename))
                        image_path = os.path.join(UPLOAD_FOLDER, filename)
                    else:
                        image_path = None
                else:
                    image_path = None
                
                # Update Tool
                conn.execute('''
                    UPDATE tools 
                    SET gegenstand = ?,
                        ort = ?,
                        typ = ?,
                        status = ?,
                        image_path = COALESCE(?, image_path)
                    WHERE barcode = ?
                ''', (
                    request.form.get('gegenstand'),
                    request.form.get('ort'),
                    request.form.get('typ'),
                    request.form.get('status'),
                    image_path,
                    barcode
                ))
                
                # Füge Änderung zur Historie hinzu
                conn.execute('''
                    INSERT INTO tools_history 
                    (tool_barcode, action, changed_fields, changed_by)
                    VALUES (?, 'update', ?, ?)
                ''', (
                    barcode,
                    'Werkzeug bearbeitet',
                    session.get('username', 'admin')
                ))
                
                conn.commit()
                flash('Werkzeug erfolgreich aktualisiert', 'success')
                return redirect(url_for('tool_details', barcode=barcode))
            
            # GET Request
            tool = conn.execute(
                'SELECT * FROM tools WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not tool:
                flash('Werkzeug nicht gefunden', 'error')
                return redirect(url_for('tools'))
                
            return render_template('edit_tool.html', tool=tool)
                                
    except Exception as e:
        print(f"FEHLER: {str(e)}")
        print(traceback.format_exc())
        flash('Fehler beim Bearbeiten des Werkzeugs', 'error')
        return redirect(url_for('tools'))

@tools_bp.route('/tools/add', methods=['GET', 'POST'])
@admin_required
def add_tool():
    print("\n=== ADD TOOL ===")
    if request.method == 'POST':
        try:
            barcode = request.form.get('barcode')
            gegenstand = request.form.get('gegenstand')
            ort = request.form.get('ort')
            typ = request.form.get('typ')
            
            # Bild-Upload
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{barcode}_{file.filename}")
                    if not os.path.exists(UPLOAD_FOLDER):
                        os.makedirs(UPLOAD_FOLDER)
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    image_path = os.path.join(UPLOAD_FOLDER, filename)
            
            with get_db_connection(DBConfig.TOOLS_DB) as conn:
                # Prüfe ob Barcode bereits existiert
                existing = conn.execute(
                    'SELECT 1 FROM tools WHERE barcode = ?', 
                    (barcode,)
                ).fetchone()
                
                if existing:
                    flash('Ein Werkzeug mit diesem Barcode existiert bereits', 'error')
                    return redirect(url_for('add_tool'))
                
                conn.execute('''
                    INSERT INTO tools (barcode, gegenstand, ort, typ, image_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (barcode, gegenstand, ort, typ, image_path))
                
                conn.execute('''
                    INSERT INTO tools_history 
                    (tool_barcode, action, changed_fields, changed_by)
                    VALUES (?, 'create', ?, ?)
                ''', (
                    barcode,
                    'Werkzeug erstellt',
                    session.get('username', 'admin')
                ))
                
                conn.commit()
                
            flash('Werkzeug erfolgreich hinzugefügt', 'success')
            return redirect(url_for('tools'))
            
        except Exception as e:
            print(f"FEHLER: {str(e)}")
            print(traceback.format_exc())
            flash('Fehler beim Hinzufügen des Werkzeugs', 'error')
            return redirect(url_for('add_tool'))
    
    return render_template('add_tool.html') 