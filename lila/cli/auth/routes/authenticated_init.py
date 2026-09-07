from .dashboard import routes as _dashboard_routes
from .profile import routes as _profile_routes
import itertools

# English: All authenticated routes collected in a single list for easy import in main.py
# Español: Todas las rutas autenticadas recolectadas en una lista para importar fácilmente en main.py
routes = list(itertools.chain(
    _dashboard_routes,
    _profile_routes,
))
