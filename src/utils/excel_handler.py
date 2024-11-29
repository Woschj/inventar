import pandas as pd
import sqlite3
import os
from datetime import datetime

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