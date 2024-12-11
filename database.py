def add_amount_column():
    with get_db_connection(DBConfig.CONSUMABLES_DB) as conn:
        try:
            conn.execute('''
                ALTER TABLE consumables_history
                ADD COLUMN amount INTEGER DEFAULT 0;
            ''')
            conn.commit()
            print("Spalte 'amount' erfolgreich hinzugefügt")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Spalte 'amount' existiert bereits")
            else:
                raise e