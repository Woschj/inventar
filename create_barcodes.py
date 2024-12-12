from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import barcode
from barcode.writer import ImageWriter
import sqlite3
import os
from io import BytesIO
from PIL import Image as PILImage

# Konfiguration
DB_DIR = 'db'
OUTPUT_DIR = 'barcodes'
WORKERS_DB = os.path.join(DB_DIR, 'workers.db')
TOOLS_DB = os.path.join(DB_DIR, 'lager.db')
CONSUMABLES_DB = os.path.join(DB_DIR, 'consumables.db')

def get_db_connection(db_path):
    """Erstellt eine Datenbankverbindung"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_barcode_image(code):
    """Erstellt ein Barcode-Bild"""
    code128 = barcode.get('code128', code, writer=ImageWriter())
    buffer = BytesIO()
    code128.write(buffer)
    buffer.seek(0)
    image = PILImage.open(buffer)
    # Größe anpassen
    new_size = (int(50*mm), int(15*mm))  # Breite: 50mm, Höhe: 15mm
    image = image.resize(new_size)
    return image

def create_workers_pdf():
    """Erstellt PDF mit Mitarbeiter-Barcodes"""
    pdf_path = os.path.join(OUTPUT_DIR, 'mitarbeiter_barcodes.pdf')
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Mitarbeiter Barcodes", styles['Heading1']))

    with get_db_connection(WORKERS_DB) as conn:
        workers = conn.execute('''
            SELECT barcode, name, lastname, bereich 
            FROM workers 
            ORDER BY lastname, name
        ''').fetchall()

        for worker in workers:
            # Erstelle Barcode direkt im Speicher
            code128 = barcode.get('code128', worker['barcode'], writer=ImageWriter())
            buffer = BytesIO()
            code128.write(buffer)
            buffer.seek(0)
            
            data = [
                [f"{worker['lastname']}, {worker['name']}", worker['bereich']],
                [ReportLabImage(buffer, width=50*mm, height=15*mm), worker['barcode']]
            ]
            
            t = Table(data, colWidths=[90*mm, 90*mm])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('FONTSIZE', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 5*mm))

    doc.build(elements)

def create_tools_pdf():
    """Erstellt PDF mit Werkzeug-Barcodes"""
    pdf_path = os.path.join(OUTPUT_DIR, 'werkzeug_barcodes.pdf')
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Werkzeug Barcodes", styles['Heading1']))

    with get_db_connection(TOOLS_DB) as conn:
        tools = conn.execute('''
            SELECT barcode, gegenstand, typ, ort 
            FROM tools 
            ORDER BY gegenstand
        ''').fetchall()

        for tool in tools:
            # Erstelle Barcode direkt im Speicher
            code128 = barcode.get('code128', tool['barcode'], writer=ImageWriter())
            buffer = BytesIO()
            code128.write(buffer)
            buffer.seek(0)
            
            data = [
                [tool['gegenstand'], f"{tool['typ']} ({tool['ort']})"],
                [ReportLabImage(buffer, width=50*mm, height=15*mm), tool['barcode']]
            ]
            
            t = Table(data, colWidths=[90*mm, 90*mm])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('FONTSIZE', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 5*mm))

    doc.build(elements)

def create_consumables_pdf():
    """Erstellt PDF mit Verbrauchsmaterial-Barcodes"""
    pdf_path = os.path.join(OUTPUT_DIR, 'verbrauchsmaterial_barcodes.pdf')
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Verbrauchsmaterial Barcodes", styles['Heading1']))

    with get_db_connection(CONSUMABLES_DB) as conn:
        items = conn.execute('''
            SELECT barcode, bezeichnung, typ, ort 
            FROM consumables 
            ORDER BY bezeichnung
        ''').fetchall()

        for item in items:
            # Erstelle Barcode direkt im Speicher
            code128 = barcode.get('code128', item['barcode'], writer=ImageWriter())
            buffer = BytesIO()
            code128.write(buffer)
            buffer.seek(0)
            
            data = [
                [item['bezeichnung'], f"{item['typ']} ({item['ort']})"],
                [ReportLabImage(buffer, width=50*mm, height=15*mm), item['barcode']]
            ]
            
            t = Table(data, colWidths=[90*mm, 90*mm])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('FONTSIZE', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 5*mm))

    doc.build(elements)

def main():
    # Erstelle Output-Verzeichnis
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Erstelle PDFs mit Barcodes...")
    create_workers_pdf()
    create_tools_pdf()
    create_consumables_pdf()
    print(f"PDFs wurden im Verzeichnis '{OUTPUT_DIR}' erstellt.")

if __name__ == '__main__':
    main()
