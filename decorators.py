from functools import wraps
from flask import redirect, url_for, flash, session

def admin_required(f):
    """Decorator für Routen, die Admin-Rechte erfordern"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin-Rechte erforderlich', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorator für Routen, die einen Login erfordern"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Login erforderlich', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function 