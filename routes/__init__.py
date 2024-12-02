from flask import Blueprint

# Blueprints erstellen
consumables_bp = Blueprint('consumables', __name__)
tools_bp = Blueprint('tools', __name__)
workers_bp = Blueprint('workers', __name__)
admin_bp = Blueprint('admin', __name__)
export_bp = Blueprint('export', __name__)

# Importiere die Routen nach der Blueprint-Erstellung
from .consumables import *
from .tools import *
from .workers import *
from .admin import *
from .export import *

# Exportiere die Blueprints
__all__ = ['consumables_bp', 'tools_bp', 'workers_bp', 'admin_bp', 'export_bp'] 