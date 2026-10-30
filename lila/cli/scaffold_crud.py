import sys
import os
import re
import shutil
from pathlib import Path
import importlib.util
from typing import Optional, List, Dict, Any
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.cli._patch import patch_main

app = typer.Typer(help="Generate complete CRUD scaffold (API endpoints, HTML view, ResponsiveDataTable).")
project_root = os.getcwd()


def _write_with_backup(path: Path, content: str) -> None:
    try:
        if path.exists():
            old = path.read_text(encoding="utf-8")
            if old != content:
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        typer.secho(f"  ⚠️ Could not write {path}: {exc}", fg=typer.colors.YELLOW)

def capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]

def to_snake_case(text: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def get_model_class(model_name: str):
    try:
        file_name = to_snake_case(model_name)
        model_path = os.path.join(project_root, "app", "models", f"{file_name}.py")
        if not os.path.exists(model_path):
            return None
        spec = importlib.util.spec_from_file_location(f"app.models.{file_name}", model_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"app.models.{file_name}"] = module
        spec.loader.exec_module(module)
        return getattr(module, model_name, None)
    except Exception as e:
        typer.echo(f"  ❌ Error loading model: {e}")
        return None

def get_model_columns(model_class) -> list:
    try:
        if hasattr(model_class, '__table__'):
            return [col.name for col in model_class.__table__.columns]
        return []
    except Exception:
        return []


def get_model_column_types(model_class) -> dict:
    types = {}
    try:
        for col in model_class.__table__.columns:
            py_type = getattr(col.type, "python_type", str)
            types[col.name] = py_type
    except Exception:
        pass
    return types

def generate_web_route_file(model_name: str, route_name: str) -> str:
    return f'''from lila.core.request import Request
from lila.core.routing import Router
from lila.core.templates import render
from app.routes.api.{route_name} import router as api_{route_name}_router

router = Router()

@router.get("/{route_name}")
async def {route_name}_index(request: Request):
    """Render the management page with ResponsiveDataTable for {model_name}"""
    return render(request=request, template="{route_name}/index", csrf=True)

# Merged routes for inclusion
routes = router.get_routes() + api_{route_name}_router.get_routes()
'''

def generate_api_route_file(
    model_name: str,
    route_name: str,
    table_name: str,
    columns: list,
    column_types: Optional[dict] = None,
) -> str:
    sensitive_fields = {"password", "token", "hash"}
    display_columns = [col for col in columns if col not in sensitive_fields]
    column_types = column_types or {}
    type_names = {int: "int", float: "float", bool: "bool", str: "str", bytes: "str"}

    create_fields = []
    update_fields = []
    for col in columns:
        if col in sensitive_fields:
            continue
        py_type = type_names.get(column_types.get(col), "str")
        if col not in {"id", "created_at", "updated_at", "active"}:
            create_fields.append(f'    {col}: Optional[{py_type}] = None')
            update_fields.append(f'    {col}: Optional[{py_type}] = None')
        elif col == "active":
            create_fields.append('    active: int = 1')
            update_fields.append('    active: Optional[int] = None')

    pydantic_create_fields = "\n".join(create_fields) or "    pass"
    pydantic_update_fields = "\n".join(update_fields) or "    pass"
    select_expr = ",".join(display_columns) if display_columns else "id"

    return f'''from lila.core.request import Request
from lila.core.routing import Router
from lila.core.responses import JSONResponse
from app.models.{to_snake_case(model_name)} import {model_name}
from pydantic import BaseModel
from typing import Optional, Any

router = Router(prefix="/api")

class {model_name}Create(BaseModel):
{pydantic_create_fields}

class {model_name}Update(BaseModel):
{pydantic_update_fields}

@router.get("/{route_name}")
async def get_all_{route_name}(request: Request, limit: int = 100, offset: int = 0):
    """Get active {model_name} records"""
    try:
        items = await {model_name}.get_all_async(
            select="{select_expr}", limit=limit, offset=offset
        )
        return items
    except Exception as e:
        return JSONResponse({{"success": False, "message": str(e)}}, status_code=500)

@router.get("/{route_name}/{{id:int}}")
async def get_{route_name}_by_id(request: Request, id: int):
    """Get a single {model_name} by ID"""
    item = await {model_name}.get_by_id_async(id, select="{select_expr}")
    if item is None:
        return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
    return item

@router.post("/{route_name}", model={model_name}Create, csrf=True)
async def create_{route_name}(request: Request, data: {model_name}Create = None):
    """Create a new {model_name} record"""
    input_data = data.model_dump(exclude_none=True) if data else request.state.data.model_dump(exclude_none=True)
    try:
        new_item = await {model_name}.insert_async(**input_data)
        return JSONResponse({{"success": True, "id": new_item.get("id")}}, status_code=201)
    except Exception as e:
        return JSONResponse({{"success": False, "message": str(e)}}, status_code=400)

@router.put("/{route_name}/{{id:int}}", model={model_name}Update, csrf=True)
async def update_{route_name}(request: Request, id: int, data: {model_name}Update = None):
    """Update an existing {model_name}"""
    input_data = data.model_dump(exclude_unset=True, exclude_none=True) if data else request.state.data.model_dump(exclude_unset=True, exclude_none=True)
    try:
        success = await {model_name}.update_async(id, **input_data)
        if not success:
            return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
        return {{"success": True}}
    except Exception as e:
        return JSONResponse({{"success": False, "message": str(e)}}, status_code=400)

@router.delete("/{route_name}/{{id:int}}", csrf=True)
async def delete_{route_name}(request: Request, id: int):
    """Delete a {model_name} record"""
    try:
        success = await {model_name}.delete_async(id)
        if not success:
            return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
        return {{"success": True}}
    except Exception as e:
        return JSONResponse({{"success": False, "message": str(e)}}, status_code=400)

routes = router.get_routes()
'''

def generate_html_template(model_name: str, route_name: str, columns: list) -> str:
    sensitive_fields = {"password", "token", "hash", "active"}
    display_columns = [col for col in columns if col not in sensitive_fields]

    cols_js = ",\n      ".join(
        [f"{{ key: '{col}', title: '{col.capitalize()}' }}" for col in display_columns]
    )

    form_fields = []
    for col in columns:
        if col in {"id", "created_at", "updated_at", "active", "password", "token", "hash"}:
            continue
        field_type = "text"
        form_fields.append(
            f'      <div>\n'
            f'        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">{col.capitalize()}</label>\n'
            f'        <input name="{col}" id="field_{col}" type="{field_type}" class="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20" />\n'
            f'      </div>'
        )
    form_fields_html = "\n".join(form_fields)

    return f'''<!DOCTYPE html>
<html lang="{{{{ lang | default('en') }}}}" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{model_name} Management | Lila</title>
  <link rel="icon" type="image/x-icon" href="{{{{ public('favicon.ico') }}}}" />
  {{% include "lila/tailwind.jinja" %}}
</head>
<body class="bg-bg-body dark:bg-bg-body-dark text-slate-800 dark:text-slate-100 min-h-screen flex flex-col font-sans transition-colors duration-300">
  <div id="lila-outlet" data-lila-outlet class="max-w-6xl w-full mx-auto px-4 py-8 flex-1 space-y-6">
    <header class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm">
      <div>
        <h2 class="text-2xl font-black bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
          {model_name} Management
        </h2>
        <p class="text-xs text-slate-400 mt-1 font-semibold">Active CRUD Table with View Transitions</p>
      </div>
      <div class="flex items-center gap-3">
        <button onclick="fetchData()" class="btn bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs px-3.5 py-2">
          <span>🔄</span> Refresh
        </button>
        <button onclick="openModal()" class="btn btn-primary text-xs px-4 py-2">
          <span>➕</span> New {model_name}
        </button>
      </div>
    </header>

    <article class="card p-6">
      <div id="datatable-container" class="overflow-x-auto"></div>
    </article>

    <dialog id="crud-dialog" class="m-auto fixed inset-0 rounded-2xl p-6 bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 shadow-xl max-w-md w-full backdrop:bg-slate-950/40">
      <div class="flex items-center justify-between mb-4 border-b border-slate-100 dark:border-slate-800 pb-3">
        <h3 id="modal-title" class="text-lg font-bold text-slate-900 dark:text-white">New {model_name}</h3>
        <button onclick="document.getElementById('crud-dialog').close()" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
      </div>
      <form id="crud-form" class="space-y-3">
        <input type="hidden" id="recordId" name="id" value="" />
{form_fields_html}
        <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800 mt-4">
          <button type="button" onclick="document.getElementById('crud-dialog').close()" class="btn bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs px-4 py-2">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary text-xs px-4 py-2">
            Save
          </button>
        </div>
      </form>
    </dialog>
  </div>

  <script src="{{{{ public('js/lila-client.js') }}}}"></script>
  <script>
    let dt = null;

    function renderTable(data) {{
      dt = new ResponsiveDataTable('datatable-container', {{
        data: data,
        columns: [
          {cols_js}
        ],
        rowsPerPage: 10,
        search: true,
        pagination: true,
        edit: (e, item) => onEdit(item),
        delete: (e, item) => onDelete(item)
      }});
    }}

    async function fetchData() {{
      try {{
        const res = await Http('/api/{route_name}');
        renderTable(res);
      }} catch (err) {{
        console.error(err);
      }}
    }}

    function openModal() {{
      document.getElementById('modal-title').textContent = 'New {model_name}';
      document.getElementById('recordId').value = '';
      document.getElementById('crud-form').reset();
      document.getElementById('crud-dialog').showModal();
    }}

    async function onEdit(item) {{
      const id = typeof item === 'object' ? item.id : item;
      try {{
        const data = await Http(`/api/{route_name}/${{id}}`);
        document.getElementById('modal-title').textContent = `Edit {model_name} #${{id}}`;
        document.getElementById('recordId').value = id;
        for (const [key, val] of Object.entries(data)) {{
          const el = document.getElementById(`field_${{key}}`);
          if (el) el.value = val !== null && val !== undefined ? val : '';
        }}
        document.getElementById('crud-dialog').showModal();
      }} catch (err) {{
        lila('toast', {{ title: 'Error', description: 'Failed to load details', type: 'error' }});
      }}
    }}

    async function onDelete(item) {{
      const id = typeof item === 'object' ? item.id : item;
      if (!confirm(`Are you sure you want to delete this {model_name}?`)) return;
      try {{
        const res = await Http(`/api/{route_name}/${{id}}`, 'DELETE');
        if (res.success) {{
          lila('toast', {{ title: 'Deleted', description: 'Record removed successfully', type: 'success' }});
          fetchData();
        }}
      }} catch (err) {{
        lila('toast', {{ title: 'Error', description: err.message, type: 'error' }});
      }}
    }}

    document.getElementById('crud-form').addEventListener('submit', async (e) => {{
      e.preventDefault();
      const formData = Object.fromEntries(new FormData(e.target));
      const id = formData.id;
      delete formData.id;
      for (const key of Object.keys(formData)) {{
        if (formData[key] === "") delete formData[key];
      }}
      try {{
        const url = id ? `/api/{route_name}/${{id}}` : '/api/{route_name}';
        const method = id ? 'PUT' : 'POST';
        const res = await Http(url, method, formData);
        if (res.success) {{
          lila('toast', {{ title: 'Success', description: 'Saved successfully', type: 'success' }});
          document.getElementById('crud-dialog').close();
          fetchData();
        }}
      }} catch (err) {{
        lila('toast', {{ title: 'Error', description: err.message, type: 'error' }});
      }}
    }});

    document.addEventListener('DOMContentLoaded', fetchData);
  </script>
</body>
</html>
'''

def add_route_import_to_main(route_name: str, model_name: str) -> bool:
    main_file = os.path.join(project_root, "main.py")
    if not os.path.exists(main_file):
        return False

    import_stmt = f"from app.routes.web.{route_name} import routes as {route_name}_routes"
    include_stmt = f"app.include_router({route_name}_routes)"

    changed = patch_main(main_file, import_stmt, include_stmt)
    if changed:
        typer.echo("  ✅ Routes linked in main.py")
    else:
        typer.echo("  ℹ️ Routes already linked (or main.py could not be patched safely).")
    return changed

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name (e.g. Product)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Route slug (defaults to snake_case)"),
):
    """
    Generate CRUD routes, Pydantic schemas, and HTML view with ResponsiveDataTable.
    """
    if ctx.invoked_subcommand is None:
        if not model:
            typer.echo(ctx.get_help())
            raise typer.Exit(code=0)
        generate(model=model, name=name)

@app.command()
def generate(
    model: str = typer.Option(..., "--model", "-m", help="Model name (e.g. Product)"),
    name: str = typer.Option(None, "--name", "-n", help="Route slug (defaults to snake_case)"),
):
    """
    Generate CRUD routes, Pydantic schemas, and HTML view with ResponsiveDataTable.
    """
    model_name = capitalize_first(model)
    route_name = name.lower() if name else to_snake_case(model_name)

    model_class = get_model_class(model_name)
    if model_class is None:
        typer.secho(f"❌ Model '{model_name}' not found in app/models/", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    columns = get_model_columns(model_class) or ["id", "name", "created_at"]
    column_types = get_model_column_types(model_class)
    table_name = getattr(model_class, "__tablename__", route_name)

    # Web route
    web_dir = Path("app/routes/web")
    web_dir.mkdir(parents=True, exist_ok=True)
    _write_with_backup(web_dir / f"{route_name}.py", generate_web_route_file(model_name, route_name))

    # API route
    api_dir = Path("app/routes/api")
    api_dir.mkdir(parents=True, exist_ok=True)
    _write_with_backup(
        api_dir / f"{route_name}.py",
        generate_api_route_file(model_name, route_name, table_name, columns, column_types),
    )

    # Template
    tmpl_dir = Path(f"resources/html/{route_name}")
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    _write_with_backup(
        tmpl_dir / "index.jinja", generate_html_template(model_name, route_name, columns)
    )

    add_route_import_to_main(route_name, model_name)
    typer.secho(f"🎉 CRUD scaffold for {model_name} generated successfully at /{route_name} and /api/{route_name}", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()
