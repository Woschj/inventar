from flask import Blueprint, request, jsonify
import logging
from core.database import get_db_connection
from config import DBConfig
from flask import session

tools_bp = Blueprint('tools', __name__, url_prefix='/tools')

@tools_bp.route('/<barcode>/update', methods=['POST'])
def update_tool_status(barcode):
    try:
        new_status = request.form.get('status')
        comment = request.form.get('comment', '')
        user = session.get('username', 'System')
        
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Get current status
            current = conn.execute(
                'SELECT status FROM tools WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not current:
                return jsonify({'success': False, 'error': 'Werkzeug nicht gefunden'})
            
            # Update tool status
            conn.execute('''
                UPDATE tools 
                SET status = ?
                WHERE barcode = ?
            ''', (new_status, barcode))
            
            # Add history entry
            conn.execute('''
                INSERT INTO tool_status_history 
                (tool_barcode, old_status, new_status, comment, changed_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (barcode, current['status'], new_status, comment, user))
            
            conn.commit()
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Update: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}) 

@tools_bp.route('/<barcode>/delete', methods=['POST'])
def delete_tool(barcode):
    try:
        user = session.get('username', 'System')
        
        with get_db_connection(DBConfig.TOOLS_DB) as conn:
            # Get tool data before deletion
            tool = conn.execute(
                'SELECT * FROM tools WHERE barcode = ?', 
                (barcode,)
            ).fetchone()
            
            if not tool:
                return jsonify({'success': False, 'error': 'Werkzeug nicht gefunden'})

            # Insert into deleted_tools
            conn.execute('''
                INSERT INTO deleted_tools 
                (barcode, gegenstand, ort, typ, status, deleted_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tool['barcode'], tool['gegenstand'], tool['ort'], 
                 tool['typ'], tool['status'], user))

            # Delete the tool
            conn.execute('DELETE FROM tools WHERE barcode = ?', (barcode,))
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Fehler beim Löschen: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}) 