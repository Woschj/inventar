import sqlite3
import logging

def get_db_connection(db_path):
    """Erstellt eine neue Datenbankverbindung"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logging.error(f"Fehler beim Verbindungsaufbau zu {db_path}: {str(e)}")
        raise 