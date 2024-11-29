from flask import send_file, flash, redirect, url_for, current_app
from . import export_bp
import os
import logging
import sqlite3
from datetime import datetime
import pandas as pd

# DBConfig direkt hier definieren
class DBConfig:
    SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_DIR = os.path.join(SRC_DIR, 'db')
    
    WORKERS_DB = os.path.join(DB_DIR, 'workers.db')
    TOOLS_DB = os.path.join(DB_DIR, 'lager.db')
    LENDINGS_DB = os.path.join(DB_DIR, 'lendings.db')
    CONSUMABLES_DB = os.path.join(DB_DIR, 'consumables.db')

# ExcelHandler direkt hier definieren
class ExcelHandler:
    @staticmethod
    def export_to_excel(db_path, output_dir='exports'):
        try:
            os.makedirs(output_dir, exist_ok=True)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            db_name = os.path.splitext(os.path.basename(db_path))[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_path = os.path.join(output_dir, f'{db_name}_{timestamp}.xlsx')
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                for table in tables:
                    table_name = table[0]
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                    df.to_excel(writer, sheet_name=table_name, index=False)
            
            return True, excel_path
            
        except Exception as e:
            return False, str(e)

@export_bp.route('/export_db/<db_name>', methods=['GET'])
def export_db(db_name):
    logging.info(f"Export-Route aufgerufen für DB: {db_name}")
    try:
        db_map = {
            'workers': DBConfig.WORKERS_DB,
            'tools': DBConfig.TOOLS_DB,
            'lendings': DBConfig.LENDINGS_DB,
            'consumables': DBConfig.CONSUMABLES_DB
        }
        
        if db_name not in db_map:
            flash('Ungültige Datenbank', 'error')
            return redirect(url_for('admin_panel'))
            
        export_dir = os.path.join(current_app.root_path, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        success, result = ExcelHandler.export_to_excel(db_map[db_name], export_dir)
        
        if success:
            return send_file(
                result,
                as_attachment=True,
                download_name=f"{db_name}_export.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            flash(f'Export fehlgeschlagen: {result}', 'error')
            return redirect(url_for('admin_panel'))
            
    except Exception as e:
        logging.error(f"Fehler beim Export: {str(e)}")
        flash(f'Export fehlgeschlagen: {str(e)}', 'error')
        return redirect(url_for('admin_panel')) 