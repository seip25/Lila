from .login import routes as _login_routes
from .register import routes as _register_routes
from .logout import routes as _logout_routes
from .forgot_password import routes as _forgot_routes
from .change_password import routes as _change_routes
import itertools

# English: All auth routes collected in a single list for easy import in main.py
# Español: Todas las rutas de autenticación recolectadas en una lista para importar fácilmente en main.py
routes = list(itertools.chain(
    _login_routes,
    _register_routes,
    _logout_routes,
    _forgot_routes,
    _change_routes,
))
