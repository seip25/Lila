import psutil
import os
from lila.core.responses import orjson_dumps
from lila.core.translate import Translate
from lila.core.responses import  RedirectResponse, JSONResponse
from lila.core.request import Request
from lila.core.routing import Router
from lila.core.session import Session
from app.connections import connection
from argon2 import PasswordHasher
from functools import wraps
from lila.core.templates import render
from app.config import PATH_LOG_BASE_DIR as PATH_LOG_BASE_DIR_ADMIN
 
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
            username = form_data.get("user",None)
            password = form_data.get("password",None)
            admin = authenticate(username=username, password=password)
            if admin:
                response = JSONResponse(
                    {"success": True, "redirect": "/admin"} 
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
    PATH_LOG_BASE_DIR = PATH_LOG_BASE_DIR_ADMIN
    logs_html = ""
    if os.path.exists(PATH_LOG_BASE_DIR):
        for log_folder in os.listdir(PATH_LOG_BASE_DIR):
            log_folder_path = os.path.join(PATH_LOG_BASE_DIR, log_folder)
            if os.path.isdir(log_folder_path):
                logs[log_folder] = {}
                for log_file in os.listdir(log_folder_path):
                    if log_file.endswith(".log"):
                        with open(os.path.join(log_folder_path, log_file), "r", encoding="utf-8") as f:
                            logs[log_folder][log_file] = f.readlines()[-500:]

        logs_html = f"""
        <details class="bg-gray-50 dark:bg-gray-700 rounded-lg p-2 border border-gray-200 dark:border-gray-600">
            <summary class="logs-summary font-bold cursor-pointer p-2 bg-gray-200 dark:bg-gray-600 rounded-md text-gray-800 dark:text-gray-200 flex items-center space-x-2">
                📁 Logs
            </summary>
            <ul class="logs-list list-none pl-0 mt-2 space-y-2">
        """
        for log_folder, log_files in logs.items():
            logs_html += f"""
            <li class="log-item">
                <details class="log-folder bg-white dark:bg-gray-800 rounded-lg shadow-sm">
                    <summary class="log-folder-summary font-medium cursor-pointer p-2 border-b dark:border-gray-700 flex items-center space-x-2">
                        📁 {log_folder}
                    </summary>
                    <ul class="log-files-list list-none pl-0 mt-2 space-y-2">
            """
            for log_file, log_lines in log_files.items():
                logs_html += f"""
                <li class="log-file-item">
                    <details class="log-file bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-2">
                        <summary class="log-summary font-medium cursor-pointer flex items-center space-x-2">
                            📄 {log_file}
                        </summary>
                        <pre class="log-content mt-2 p-2 border border-gray-300 dark:border-gray-600 rounded-md max-h-96 overflow-y-auto font-mono text-sm whitespace-pre-wrap break-words bg-black text-lime-400">{"".join(log_lines)}</pre>
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


def menu(models: list = [], request: Request = None) -> str:
    """Generate the admin menu as an <aside> component with Tailwind CSS."""
    current_path = request.url.path if request else ""
    
    active_dash = "flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-xl font-bold shadow-material transition-all text-sm cursor-pointer" if current_path == "/admin" else "flex items-center gap-2 px-3 py-2 text-slate-650 dark:text-slate-405 hover:bg-gray-800 dark:hover:bg-gray-200 font-medium hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl transition-all text-sm cursor-pointer"
    
    m = f'<a href="/admin" class="{active_dash}"><span>📊</span> Dashboard</a>'
    
    if models:
        m += '<h6 class="text-[10px] font-black uppercase text-slate-400 dark:text-slate-500 mt-6 px-3 tracking-wider mb-2">Models</h6>'
        m += '<div class="space-y-1">'
        for model in models:
            model_name = model.__name__.lower()
            model_plural = f"{model_name}s"
            path = f"/admin/{model_plural}"
            is_active = current_path == path
            active_class = "flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-xl font-bold shadow-material transition-all text-sm cursor-pointer" if is_active else "flex items-center gap-2 px-3 py-2 text-slate-650 dark:text-slate-405 hover:text-gray-800 dark:hover:text-gray-200 font-medium hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl transition-all text-sm cursor-pointer"
            m += f'<a href="{path}" class="{active_class}"><span>📁</span> {model_name.capitalize()}</a>'
        m += '</div>'

    m += '<h6 class="text-[10px] font-black uppercase text-slate-400 dark:text-slate-500 mt-6 px-3 tracking-wider mb-2">System</h6>'
    m += '<div class="space-y-1">'
    m += '<a href="/admin/logout" class="flex items-center gap-2 px-3 py-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20 font-medium rounded-xl transition-all text-sm cursor-pointer"><span>🚪</span> Logout</a>'
    m += '</div>'

    return f"""
    <aside class="w-full  flex-shrink-0">
        <div class="bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
            <div class="flex items-center p-2 mb-6 border-b border-slate-100 dark:border-slate-850 pb-4">
                 <img src="/img/lila.png" alt="Lila" width="36" height="36" class="mr-3 bg-white p-1 rounded-full shadow-sm">
                 <div>
                     <h4 class="m-0 text-md font-black bg-gradient-to-r from-gray-800 to-gray-200 dark:from-gray-200 dark:to-gray-800 bg-clip-text text-transparent">Lila Admin</h4>
                     <p class="text-[9px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">Control Panel</p>
                 </div>
            </div>
            <nav class="flex flex-col gap-1">
                {m}
            </nav>
        </div>
    </aside>
    """
def admin_routes(models: list, router: Router,default_route: str = "admin") -> Router:

    @router.route(path=f"/{default_route}/logout", methods=["GET"], cache_ttl=0)
    async def admin_logout(request: Request):
        """Handle admin logout requests."""
        response = RedirectResponse(url=f"/{default_route}/login")
        await Session.delete(response=response, key="auth_admin", request=request)
        return response

    @router.route(path=f"/{default_route}/login", methods=["GET", "POST"], cache_ttl=0)
    async def admin_login_route(request: Request):
        """Handle admin login requests."""
        return await admin_login(request=request)

    @router.route(path=f"/{default_route}/metrics", methods=["GET"], cache_ttl=0)
    @admin_required
    async def get_metrics(request: Request):
        return admin_metrics()

    @router.route(path=f"/{default_route}", methods=["GET"], cache_ttl=0)
    @admin_required
    async def admin_route(request: Request):
        menu_html = menu(models=models, request=request)
        return await admin_dashboard(request=request, menu=menu_html)

    for model in models:
        model_name = model.__name__.lower()
        model_plural = f"{model_name}s"

        @router.route(path=f"/{default_route}/{model_plural}", methods=["GET"], cache_ttl=0)
        @admin_required
        async def model_list(request: Request, model=model, model_name=model_name):
            items = await model.get_all_async()

            headers = items[0].keys() if items else []
            html_lang = Translate.lang(request=request)

            context = {
                "request": request,
                "items_json": orjson_dumps(items).decode(),
                "model_name": model_name,
                "headers": headers,
                "html_lang": html_lang,
                "menu": menu(models=models, request=request),
            }

            return render(request=request,template="admin/model_table", context=context)

    return router
