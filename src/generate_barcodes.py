from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import sqlite3
from pathlib import Path
import math

# Pfade zu den Datenbanken
DB_PATH = Path.cwd()
WORKERS_DB = DB_PATH / 'workers.db'
TOOLS_DB = DB_PATH / 'lager.db'
CONSUMABLES_DB = DB_PATH / 'consumables.db'

# Ausgabeverzeichnis
OUTPUT_DIR = Path('barcodes')
OUTPUT_DIR.mkdir(exist_ok=True)

def get_db_connection(db_path):
    """Erstellt eine neue Datenbankverbindung"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Fehler beim Verbinden mit {db_path}: {e}")
        return None

def create_barcode_image(code, name):
    """Erstellt ein einzelnes Barcode-Bild mit Text"""
    # Barcode generieren
    code128 = barcode.get('code128', code, writer=ImageWriter())
    
    # Barcode als Bild erstellen
    img = code128.render()
    
    # Neues Bild mit zusätzlichem Platz für Text
    final_img = Image.new('RGB', (img.width, img.height + 30), 'white')
    final_img.paste(img, (0, 0))
    
    # Text hinzufügen
    draw = ImageDraw.Draw(final_img)
    try:
        font = ImageFont.truetype("Arial", 12)
    except:
        font = ImageFont.load_default()
    
    # Text zentriert unter dem Barcode
    text = f"{name[:30]} - {code}"  # Name auf 30 Zeichen begrenzen
    text_width = draw.textlength(text, font=font)
    text_position = ((final_img.width - text_width) // 2, img.height + 5)
    draw.text(text_position, text, fill='black', font=font)
    
    return final_img

def create_barcode_sheet(items, filename, title):
    """Erstellt ein A4-Blatt mit mehreren Barcodes"""
    if not items:
        print(f"Keine Daten für {filename}")
        return False

    # A4 Größe in Pixeln bei 300dpi
    page_width = int(8.27 * 300)  # A4 Breite in Zoll * DPI
    page_height = int(11.69 * 300)  # A4 Höhe in Zoll * DPI
    
    # Weißes A4-Blatt erstellen
    page = Image.new('RGB', (page_width, page_height), 'white')
    draw = ImageDraw.Draw(page)
    
    try:
        font = ImageFont.truetype("Arial", 20)
    except:
        font = ImageFont.load_default()
    
    # Titel hinzufügen
    draw.text((50, 30), title, fill='black', font=font)
    
    # Barcode-Größe und Layout
    barcode_width = page_width // 3 - 60  # 3 Spalten mit Abstand
    barcode_height = 120  # Feste Höhe für jeden Barcode
    
    current_x = 30
    current_y = 100  # Start unter dem Titel
    
    for i, item in enumerate(items):
        # Neuer Barcode
        barcode_img = create_barcode_image(item['barcode'], item['name'])
        
        # Barcode auf gewünschte Größe skalieren
        scaled_barcode = barcode_img.resize(
            (barcode_width, barcode_height), 
            Image.Resampling.LANCZOS
        )
        
        # Barcode einfügen
        page.paste(scaled_barcode, (current_x, current_y))
        
        # Position für nächsten Barcode
        current_x += barcode_width + 30
        
        # Neue Zeile nach 3 Barcodes
        if (i + 1) % 3 == 0:
            current_x = 30
            current_y += barcode_height + 30
            
            # Neue Seite wenn nötig
            if current_y + barcode_height > page_height - 30:
                # Aktuelle Seite speichern
                page.save(str(OUTPUT_DIR / f"{filename}_{(i+1)//30}.pdf"))
                # Neue Seite beginnen
                page = Image.new('RGB', (page_width, page_height), 'white')
                draw = ImageDraw.Draw(page)
                current_y = 30
    
    # Letzte Seite speichern
    page.save(str(OUTPUT_DIR / f"{filename}_{(len(items)-1)//30 + 1}.pdf"))
    return True

def main():
    print("Starte Barcode-Generierung...")
    
    # Werkzeuge und Verbrauchsmaterial
    items = []
    
    # Werkzeuge laden
    if TOOLS_DB.exists():
        conn = get_db_connection(TOOLS_DB)
        if conn:
            try:
                tools = conn.execute('''
                    SELECT barcode, gegenstand as name
                    FROM tools 
                    ORDER BY gegenstand
                ''').fetchall()
                items.extend([dict(tool) for tool in tools])
                print(f"{len(tools)} Werkzeuge geladen")
            except Exception as e:
                print(f"Fehler beim Laden der Werkzeuge: {e}")
            finally:
                conn.close()
    
    # Verbrauchsmaterial laden
    if CONSUMABLES_DB.exists():
        conn = get_db_connection(CONSUMABLES_DB)
        if conn:
            try:
                consumables = conn.execute('''
                    SELECT barcode, bezeichnung as name
                    FROM consumables 
                    ORDER BY bezeichnung
                ''').fetchall()
                items.extend([dict(cons) for cons in consumables])
                print(f"{len(consumables)} Verbrauchsmaterialien geladen")
            except Exception as e:
                print(f"Fehler beim Laden der Verbrauchsmaterialien: {e}")
            finally:
                conn.close()
    
    # Werkzeuge und Verbrauchsmaterial PDF erstellen
    if items:
        if create_barcode_sheet(items, 'werkzeuge_material', 'Werkzeuge und Verbrauchsmaterial'):
            print(f"PDFs für {len(items)} Werkzeuge und Materialien erstellt")
    
    # Mitarbeiter separat
    if WORKERS_DB.exists():
        conn = get_db_connection(WORKERS_DB)
        if conn:
            try:
                workers = conn.execute('''
                    SELECT barcode, name || ' ' || lastname as name
                    FROM workers 
                    ORDER BY name, lastname
                ''').fetchall()
                if workers:
                    if create_barcode_sheet(
                        [dict(worker) for worker in workers],
                        'mitarbeiter',
                        'Mitarbeiter'
                    ):
                        print(f"PDFs für {len(workers)} Mitarbeiter erstellt")
            except Exception as e:
                print(f"Fehler beim Laden der Mitarbeiter: {e}")
            finally:
                conn.close()

    print(f"\nPDF-Dateien wurden im Verzeichnis '{OUTPUT_DIR}' erstellt")

if __name__ == '__main__':
    main() 