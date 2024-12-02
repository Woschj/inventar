from flask import session, redirect, url_for, flash
from functools import wraps

def admin_required(f):
    """Decorator für Admin-geschützte Routen"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Zugriff verweigert. Admin-Rechte erforderlich.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorator für Login-geschützte Routen"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Bitte zuerst einloggen.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_admin_password(password):
    """Überprüft das Admin-Passwort"""
    # In einer echten Anwendung würde hier eine sichere Passwort-Überprüfung stattfinden
    return password == "admin123"  # Beispiel-Passwort, sollte in der Produktion geändert werden 