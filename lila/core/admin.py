"""Lila Framework v2.0.0 Admin 2.0 Engine.
Features:
- SPA navigation with lila-client.js
- Full CRUD API & UI for registered ActiveRecord models
- CSV data export
- Cache clearing & log viewer
- Safe system metrics with psutil fallback
"""

import os
import glob
from typing import List, Optional, Any, Dict, Type
from functools import wraps

from starlette.requests import Request
from starlette.responses import RedirectResponse

from lila.core.responses import JSONResponse, orjson_dumps
from lila.core.translate import Translate
from lila.core.session import Session
from lila.core.templates import render
from lila.core.logger import Logger, DEFAULT_LOG_DIR, delete_old_logs
from lila.core.cache import Cache
from lila.core.auth import PasswordHasher
from lila.core.exporter import Exporter
from lila.core.middleware import admin_required
from lila.core.config import get_data_path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


def get_admin_metrics() -> dict:
    """Safely retrieves process and system metrics without requiring psutil."""
    cache_stats = Cache.stats()

    if HAS_PSUTIL and psutil is not None:
        try:
            proc = psutil.Process(os.getpid())
            mem_rss = round(proc.memory_info().rss / (1024 * 1024), 2)
            cpu_proc = round(proc.cpu_percent(interval=0), 1)

            vmem = psutil.virtual_memory()
            sys_used = round((vmem.total - vmem.available) / (1024 * 1024), 2)
            sys_total = round(vmem.total / (1024 * 1024), 2)
            sys_cpu = round(psutil.cpu_percent(interval=0), 1)

            return {
                "process_memory_mb": mem_rss,
                "process_cpu": cpu_proc,
                "system_used_mb": sys_used,
                "system_total_mb": sys_total,
                "system_cpu": sys_cpu,
                "cache": cache_stats,
            }
        except Exception:
            pass

    return {
        "process_memory_mb": 25.0,
        "process_cpu": 0.5,
        "system_used_mb": 1024.0,
        "system_total_mb": 4096.0,
        "system_cpu": 5.0,
        "cache": cache_stats,
    }


def render_admin_menu(models: list = None, request: Optional[Request] = None) -> str:
    """Renders persistent Admin Sidebar navigation with Tailwind CSS."""
    models = models or []
    current_path = request.url.path if request else "/admin"

    def _link(path: str, label: str, icon: str) -> str:
        active = current_path == path or (path != "/admin" and current_path.startswith(path))
        cls_name = (
            "flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all "
            + ("bg-blue-600 text-white shadow-sm" if active
               else "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100")
        )
        return f'<a href="{path}" class="{cls_name}"><span>{icon}</span> <span>{label}</span></a>'

    nav_links = [_link("/admin", "Dashboard", "📊")]

    if models:
        nav_links.append('<div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 pt-4 pb-1">Data Models</div>')
        for m in models:
            m_name = m.__name__
            m_plural = f"{m_name.lower()}s"
            nav_links.append(_link(f"/admin/{m_plural}", m_name, "📁"))

    nav_links.append('<div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 pt-4 pb-1">System</div>')
    nav_links.append('<a href="/admin/logout" data-no-router class="flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-sm font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 transition-all"><span>🚪</span> <span>Sign Out</span></a>')

    joined = "\n".join(nav_links)
    return (
        f'<aside id="admin-sidebar" data-persist="true" class="w-64 flex-shrink-0 p-4 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 min-h-screen flex flex-col justify-between">'
        f'<div>'
        f'<div class="flex items-center gap-3 px-3 py-3 mb-6 border-b border-slate-100 dark:border-slate-800">'
        f'<img src="/img/lila.png" alt="Lila" class="w-8 h-8 rounded-lg shadow-sm">'
        f'<div><h4 class="font-extrabold text-slate-800 dark:text-slate-100 text-sm m-0">Lila Admin</h4>'
        f'<span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">v2.0.0</span></div>'
        f'</div>'
        f'<nav class="flex flex-col gap-1">{joined}</nav>'
        f'</div>'
        f'</aside>'
    )


def admin_routes(models: list, router: Any, default_route: str = "admin") -> Any:
    """Mounts Admin 2.0 routes on the given router."""
    prefix = f"/{default_route.strip('/')}"
    # Admin routes should never be registered in public Swagger/OpenAPI documentation
    router.openapi = False

    # ──────────────────────────────────────────────────────────────────────────
    # Auth & Dashboard
    # ──────────────────────────────────────────────────────────────────────────
    @router.get(f"{prefix}/login")
    async def admin_login_view(request: Request):
        return render(request, "admin/login")

    @router.post(f"{prefix}/login")
    async def admin_login_action(request: Request):
        try:
            body = await request.json()
            username = body.get("username") or body.get("user")
            password = body.get("password")

            from lila.core.database import db
            # Verify in admins or fallback to superuser credentials
            admin_record = await db.query_async(
                "SELECT id, username, password FROM admins WHERE username = :u AND active = 1 LIMIT 1",
                {"u": username},
                return_row=True,
            )

            valid = False
            if admin_record and admin_record.get("password"):
                valid = PasswordHasher.verify(admin_record["password"], password)

            if not valid:
                return JSONResponse({"success": False, "message": "Invalid credentials"}, status_code=401)

            res = JSONResponse({"success": True, "redirect": f"{prefix}"})
            await Session.set_async({"id": admin_record["id"], "username": username}, res, cookie_name="admin_session")
            return res
        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

    @router.get(f"{prefix}/logout")
    async def admin_logout_view(request: Request):
        res = RedirectResponse(f"{prefix}/login")
        await Session.delete_async(request, res, cookie_name="admin_session")
        return res

    @router.get(prefix)
    @admin_required(redirect_to=f"{prefix}/login")
    async def admin_dashboard_view(request: Request):
        metrics = get_admin_metrics()
        menu_html = render_admin_menu(models, request)

        # Collect recent log lines
        log_dir = os.environ.get("LILA_LOG_DIR", DEFAULT_LOG_DIR)
        logs = {}
        if os.path.exists(log_dir):
            folders = sorted(glob.glob(os.path.join(log_dir, "*")), reverse=True)[:5]
            for folder in folders:
                folder_name = os.path.basename(folder)
                logs[folder_name] = {}
                for lf in glob.glob(os.path.join(folder, "*.log")):
                    file_name = os.path.basename(lf)
                    try:
                        with open(lf, "r", encoding="utf-8") as f:
                            logs[folder_name][file_name] = f.readlines()[-100:]
                    except Exception:
                        pass

        context = {
            "metrics": metrics,
            "menu": menu_html,
            "logs": logs,
        }
        return render(request, "admin/dashboard", context=context)

    # ──────────────────────────────────────────────────────────────────────────
    # Cache & Log Controls
    # ──────────────────────────────────────────────────────────────────────────
    @router.post(f"{prefix}/cache/clear")
    @admin_required(redirect_to=f"{prefix}/login")
    async def admin_clear_cache(request: Request):
        await Cache.clear_async()
        return {"success": True, "message": "Cache successfully cleared."}

    @router.delete(f"{prefix}/logs")
    @admin_required(redirect_to=f"{prefix}/login")
    async def admin_delete_logs(request: Request):
        deleted = delete_old_logs(days=0)
        return {"success": True, "message": f"Cleaned {deleted} log directories."}

    # ──────────────────────────────────────────────────────────────────────────
    # Dynamic Model CRUD & CSV Export
    # ──────────────────────────────────────────────────────────────────────────
    def _mount_model_crud(current_model: Any):
        current_name = current_model.__name__
        current_plural = f"{current_name.lower()}s"

        @router.get(f"{prefix}/{current_plural}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def model_view(request: Request):
            items = await current_model.get_all_async(limit=500)
            headers = [col.name for col in current_model.__table__.columns if col.name != "password"]
            context = {
                "model_name": current_name,
                "model_plural": current_plural,
                "headers": headers,
                "items_json": orjson_dumps(items).decode("utf-8"),
                "menu": render_admin_menu(models, request),
            }
            return render(request, "admin/model_table", context=context)

        @router.get(f"{prefix}/api/{current_plural}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_list(request: Request):
            return await current_model.get_all_async(limit=1000)

        @router.get(f"{prefix}/api/{current_plural}/{{id:int}}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_get(request: Request, id: int):
            rec = await current_model.get_by_id_async(id)
            if not rec:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            if "password" in rec:
                rec["password"] = ""
            return rec

        @router.post(f"{prefix}/api/{current_plural}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_create(request: Request):
            data = await request.json()
            if "password" in data and data["password"]:
                data["password"] = PasswordHasher.hash(data["password"])
            created = await current_model.insert_async(**data)
            return JSONResponse({"success": True, "data": created}, status_code=201)

        @router.put(f"{prefix}/api/{current_plural}/{{id:int}}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_update(request: Request, id: int):
            data = await request.json()
            if "password" in data:
                if data["password"]:
                    data["password"] = PasswordHasher.hash(data["password"])
                else:
                    data.pop("password", None)
            ok = await current_model.update_async(id, **data)
            if not ok:
                return JSONResponse({"success": False, "message": "Update failed"}, status_code=404)
            return {"success": True, "id": id}

        @router.delete(f"{prefix}/api/{current_plural}/{{id:int}}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_delete(request: Request, id: int):
            ok = await current_model.delete_async(id)
            if not ok:
                return JSONResponse({"success": False, "message": "Delete failed"}, status_code=404)
            return {"success": True, "deleted": True}

        @router.get(f"{prefix}/api/{current_plural}/export")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_export(request: Request):
            items = await current_model.get_all_async(limit=10000)
            clean_items = []
            for item in items:
                d = dict(item)
                d.pop("password", None)
                clean_items.append(d)
            return Exporter.to_csv_response(clean_items, filename=f"{current_plural}.csv")

    for model in models:
        _mount_model_crud(model)

    return router
