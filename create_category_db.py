import sqlite3
import os

def create_category_management():
    # Stelle sicher, dass der inventar-Ordner existiert
    os.makedirs('inventar', exist_ok=True)
    
    # Verbindung zur Hauptdatenbank für Kategorien
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Tabelle für Kategorien
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabelle für die Felder der Kategorien
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS category_fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        field_name TEXT NOT NULL,
        field_type TEXT NOT NULL,
        is_required BOOLEAN NOT NULL DEFAULT 0,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Kategorie-Management-Datenbank erfolgreich erstellt!")

if __name__ == "__main__":
    create_category_management() 