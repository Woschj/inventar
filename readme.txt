INVENTARVERWALTUNG - BENUTZERHANDBUCH
=====================================

INHALTSVERZEICHNIS
-----------------
1. Installation
2. Ersteinrichtung
3. Bedienung
4. Fehlerbehebung
5. Funktionsweise
6. Backup & Wartung

1. INSTALLATION
--------------
Voraussetzungen:
- Python 3.8 oder höher (https://www.python.org/downloads/)
- Git (optional, für Updates: https://git-scm.com/downloads)
- Webbrowser (Chrome, Firefox, Edge)
- Internetzugang für die Installation

Installationsschritte:

a) Python installieren:
   - Python-Installer von python.org herunterladen
   - "Add Python to PATH" während der Installation aktivieren
   - Installation durchführen

b) Programm installieren:
   1. Ordner für das Programm erstellen (z.B. C:\Inventar)
   2. Kommandozeile öffnen (Windows-Taste + R, dann "cmd" eingeben)
   3. Folgende Befehle nacheinander ausführen:
      cd C:\Inventar
      python -m venv venv
      venv\Scripts\activate
      pip install flask sqlite3 logging

c) Programmdateien kopieren:
   - Alle .py Dateien in den Programmordner kopieren
   - Den "templates" Ordner mit allen HTML-Dateien kopieren
   - Den "static" Ordner mit CSS/JS-Dateien kopieren

2. ERSTEINRICHTUNG
-----------------
a) Datenbank initialisieren:
   1. Kommandozeile im Programmordner öffnen
   2. venv\Scripts\activate
   3. python app.py
   - Die Datenbanken werden automatisch erstellt

b) Admin-Zugang einrichten:
   - Standardpasswort ist "1234"
   - Kann in der app.py geändert werden (ADMIN_PASSWORD)

c) Erststart:
   1. http://localhost:5000 im Browser öffnen
   2. Mit Admin-Passwort anmelden
   3. Grunddaten eingeben:
      - Mitarbeiter anlegen
      - Werkzeuge erfassen
      - Lagerorte definieren

3. BEDIENUNG
-----------
a) Hauptfunktionen:

   WERKZEUGE VERWALTEN:
   - Neues Werkzeug: "+" Button oben rechts
   - Werkzeug bearbeiten: Auf Werkzeugname klicken
   - Werkzeug löschen: Mülleimer-Symbol
   - Werkzeug suchen: Suchfeld oben
   - Filter nutzen: Dropdown-Menüs für Ort/Typ/Status

   AUSLEIHE:
   - Schnellscan: Scanner-Symbol oben
   - Manuelle Ausleihe: "Ausleihe" im Menü
   - Rückgabe: "Rückgabe" Button oder Scan
   
   MITARBEITER:
   - Neuer Mitarbeiter: "+" Button in Mitarbeiterliste
   - Mitarbeiter bearbeiten: Auf Namen klicken
   - Mitarbeiter suchen: Suchfeld in Mitarbeiterliste

b) Scanner-Funktion:
   - Funktioniert mit Webcam/Handyscanner
   - QR-Codes oder Barcodes möglich
   - Bei Problemen manuellen Modus nutzen

4. FEHLERBEHEBUNG
----------------
a) Häufige Probleme:

   PROGRAMM STARTET NICHT:
   - Prüfen ob Python läuft (python --version)
   - Virtuelle Umgebung aktiviert? (venv\Scripts\activate)
   - Alle Abhängigkeiten installiert? (pip list)
   - Fehlermeldungen in app.log prüfen

   SCANNER FUNKTIONIERT NICHT:
   - HTTPS aktivieren oder localhost nutzen
   - Kamerazugriff im Browser erlauben
   - Anderen Browser testen
   - Beleuchtung verbessern

   DATENBANK-FEHLER:
   - Backup einspielen (siehe Punkt 6)
   - Datenbank neu initialisieren
   - Berechtigungen prüfen

b) Logs prüfen:
   - app.log im Programmordner enthält Details
   - Bei Fehlern Zeitstempel notieren
   - Vollständige Fehlermeldung für Support

5. FUNKTIONSWEISE
---------------
Das Programm besteht aus mehreren Komponenten:

a) Datenbanken (im db/ Ordner):
   - workers.db: Mitarbeiterdaten
   - tools.db: Werkzeuge und Geräte
   - lendings.db: Ausleihvorgänge
   - consumables.db: Verbrauchsmaterial
   - system_logs.db: Systemprotokoll

b) Weboberfläche:
   - Läuft im Browser
   - Responsive Design (PC/Tablet/Smartphone)
   - Einfache Bedienung durch Scan-Funktion

c) Automatische Funktionen:
   - Backup täglich um Mitternacht
   - Protokollierung aller Vorgänge
   - Bestandsüberwachung
   - Statusaktualisierungen

6. BACKUP & WARTUNG
-----------------
a) Automatisches Backup:
   - Täglich im backup/ Ordner
   - 7 Tage werden aufbewahrt
   - Format: YYYY-MM-DD_backup.zip

b) Manuelles Backup:
   1. Programm beenden
   2. Ordner db/ kopieren
   3. Sicher aufbewahren

c) Backup einspielen:
   1. Programm beenden
   2. Aktuellen db/ Ordner umbenennen
   3. Backup-Ordner als db/ einsetzen
   4. Programm starten

d) Regelmäßige Wartung:
   - Logs prüfen (app.log)
   - Alte Backups löschen
   - Datenbank optimieren
   - Updates einspielen

SUPPORT & HILFE
--------------
Bei Problemen oder Fragen:
1. Dieses Handbuch konsultieren
2. Logs prüfen (app.log)


Version: 0.1
Letzte Aktualisierung: 01.12.2024