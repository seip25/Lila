import psutil
import os
import json
from core.helpers import lang
from core.responses import  RedirectResponse, JSONResponse
from core.request import Request
from core.routing import Router
from core.session import Session
from app.connections import connection
from argon2 import PasswordHasher
from functools import wraps
from core.responses import convert_to_serializable
from core.templates import render
 
connection = connection
ph = PasswordHasher()


def admin_required(func):
    """Middleware to ensure the user is authenticated as an admin."""

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        session_data = Session.unsign(key="auth_admin", request=request)
        if not session_data:
            return RedirectResponse(url="/admin/login")
        if session_data["id"] is None:
            return RedirectResponse(url="/admin/login")
        return await func(request, *args, **kwargs)

    return wrapper


def admin_metrics():
    lila_memory, lila_cpu_usage = get_lila_memory_usage()
    system_used_memory, system_total_memory, cpu_usage = get_system_memory_usage()
    metrics = {
        "lila_memory": lila_memory,
        "lila_cpu_usage": lila_cpu_usage,
        "system_used_memory": system_used_memory,
        "system_total_memory": system_total_memory,
        "cpu_usage": cpu_usage,
    }
    return JSONResponse(metrics)


def get_lila_memory_usage() -> tuple:
    """Get memory and CPU usage of the Lila Framework process."""
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss / (1024 * 1024)
    cpu_usage = process.cpu_percent()
    return memory_usage, cpu_usage


def get_system_memory_usage() -> tuple:
    """Get system memory and CPU usage."""
    memory_info = psutil.virtual_memory()
    used_memory = memory_info.used / (1024 * 1024)
    total_memory = memory_info.total / (1024 * 1024)
    cpu_usage = psutil.cpu_percent()
    return used_memory, total_memory, cpu_usage


def authenticate(username: str, password: str) -> dict:
    """Authenticate an admin user.

    Args:
        username (str): The username of the admin.
        password (str): The password of the admin.

    Returns:
        dict: The admin data if authentication is successful, otherwise None.
    """
    query = "SELECT id, username, password FROM admins WHERE username = :username AND active = 1 LIMIT 1"
    params = {"username": username}
    admin = connection.query(query=query, params=params, return_row=True)
    if not admin or not admin.get("password"):
        return None

    try:
        if ph.verify(admin["password"], password):
            admin["password"] = None
            return admin
    except Exception as e:
        print(f"Error verifying password: {e}")
        return None

    return None


async def admin_login(request: Request):
    """Handle admin login requests."""
    if request.method == "POST":
        try:
            form_data = await request.json()
            username = form_data.get("user")
            password = form_data.get("password")
            admin = authenticate(username=username, password=password)
            if admin:
                response = JSONResponse(
                    {"success": True, "redirect": "/admin"}, serialize=False
                )
                admin_val = {"id": admin["id"]}
                Session.setSession(
                    new_val=admin_val, response=response, name_cookie="auth_admin"
                )
                return response
            return JSONResponse(
                {"success": False, "message": "Invalid credentials"},
                status_code=401,
            )
        except Exception as e:
            print(e)
            return JSONResponse({"success": False, "message": "Error"}, status_code=500)

    return render(request=request, template="admin/login")


async def admin_dashboard(request: Request, menu: str = "") -> str:
    """Generate the HTML for the admin dashboard."""
    lila_memory, lila_cpu_usage = get_lila_memory_usage()
    system_used_memory, system_total_memory, cpu_usage = get_system_memory_usage()

    logs = {}
    log_base_dir = "app/logs"
    logs_html = ""

    if os.path.exists(log_base_dir):
        for log_folder in os.listdir(log_base_dir):
            log_folder_path = os.path.join(log_base_dir, log_folder)
            if os.path.isdir(log_folder_path):
                logs[log_folder] = {}
                for log_file in os.listdir(log_folder_path):
                    if log_file.endswith(".log"):
                        with open(os.path.join(log_folder_path, log_file), "r") as f:
                            logs[log_folder][log_file] = f.readlines()

        logs_html = """
        <details class="logs-container container ">
            <summary class="logs-summary">📁 Logs</summary>
            <ul class="logs-list">
        """
        for log_folder, log_files in logs.items():
            logs_html += f"""
            <li class="log-item mt-2">
                <details class="log-folder">
                    <summary class="log-folder-summary">📁 {log_folder}</summary>
                    <ul class="log-files-list">
            """
            for log_file, log_lines in log_files.items():
                logs_html += f"""
                <li class="log-file-item">
                    <details class="log-file mt-2">
                        <summary class="log-summary">📄 {log_file}</summary>
                        <pre class="log-content">{"".join(log_lines)}</pre>
                    </details>
                </li>
                """
            logs_html += """
                    </ul>
                </details>
            </li>
            """
        logs_html += """
            </ul>
        </details>
        """

    menu_html = menu

    context = {
        "lila_memory": lila_memory,
        "lila_cpu_usage": lila_cpu_usage,
        "system_used_memory": system_used_memory,
        "system_total_memory": system_total_memory,
        "cpu_usage": cpu_usage,
        "logs_html": logs_html,
        "menu": menu_html,
    }

    return render(request=request,template="admin/dashboard",context=context)


def menu(models: list = []) -> str:
    """Generate the admin menu."""

    m = ""
    for model in models:
        model_name = model.__name__.lower()
        model_plural = f"{model_name}s"
        m += f"<li><a href='/admin/{model_plural}' class='secondary mt-2'>{model_name.capitalize()}</a></li>"

    return f"""
        <header class="shadow p-4  ">
        <nav class="container  ">
        <ul>
       <li>  <h3> <a href="/admin/" class="secondary" >Admin Dashboard</a> </h3></li>
</ul>
       <ul>
        <li>
            <details class="dropdown">
            <summary>Menu</summary>
            <ul>
                {m}
               <li>
                 <a href="/admin/logout" class="mt-2 secondary">Logout</a>
                </li>
            </ul>
            </details>

        </li>
       </ul>

        
         
       
       
        </nav>
        </header>

        """


def admin_routes(models: list, router: Router,default_route: str = "admin") -> Router:

    @router.route(path=f"/{default_route}/logout", methods=["GET"])
    async def admin_logout(request: Request):
        """Handle admin logout requests."""
        response = RedirectResponse(url=f"/{default_route}/login")
        response.delete_cookie("auth_admin")
        return response

    @router.route(path=f"/{default_route}/login", methods=["GET", "POST"])
    async def admin_login_route(request: Request):
        """Handle admin login requests."""
        return await admin_login(request=request)

    @router.route(path=f"/{default_route}/metrics", methods=["GET"])
    @admin_required
    async def get_metrics(request: Request):
        return admin_metrics()

    @router.route(path=f"/{default_route}", methods=["GET"])
    @admin_required
    async def admin_route(request: Request):
        menu_html = menu(models=models)
        return await admin_dashboard(request=request, menu=menu_html)

    for model in models:
        model_name = model.__name__.lower()
        model_plural = f"{model_name}s"

        @router.route(path=f"/{default_route}/{model_plural}", methods=["GET"])
        @admin_required
        async def model_list(request: Request, model=model, model_name=model_name):
            items = model.get_all()
            items = convert_to_serializable(items)

            headers = items[0].keys() if items else []
            html_lang = lang(request=request)

            context = {
                "request": request,
                "items_json": json.dumps(items),
                "model_name": model_name,
                "headers": headers,
                "html_lang": html_lang,
                "menu": menu(models=models),
            }

            return render(request=request,template="admin/model_table", context=context)

    return router
