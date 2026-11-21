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

SENSITIVE_FIELDS = {"password", "token", "hash"}
AUTO_FIELDS = {"id", "created_at", "updated_at", "active"}


def private_fields(model_class) -> set:
    """``__private_fields__`` of the model plus password/token/hash."""
    return set(getattr(model_class, "__private_fields__", ()) or ()) | SENSITIVE_FIELDS


def generate_web_route_file(model_name: str, route_name: str, react: bool = False, auth: bool = False) -> str:
    auth_arg = ", auth=True" if auth else ""
    if react:
        return f'''from lila.core.request import Request
from lila.core.routing import Router
from lila.core.react import react_render
from app.routes.api.{route_name} import router as api_{route_name}_router

router = Router()


@router.get("/{route_name}"{auth_arg})
async def {route_name}_index(request: Request):
    """React management page (resources/react/pages/Crud/{model_name}.tsx)."""
    return react_render(
        request,
        "Crud/{model_name}",
        {{"api": "/api/{route_name}", "title": "{model_name}"}},
        title="{model_name} Management",
        robots="noindex",
    )


# Merged routes for inclusion
routes = router.get_routes() + api_{route_name}_router.get_routes()
'''
    return f'''from lila.core.request import Request
from lila.core.routing import Router
from lila.core.templates import render
from app.routes.api.{route_name} import router as api_{route_name}_router

router = Router()

@router.get("/{route_name}"{auth_arg})
async def {route_name}_index(request: Request):
    """Render the management page with ResponsiveDataTable for {model_name}"""
    return render(request, "{route_name}/index", csrf=True, title="{model_name} Management")

# Merged routes for inclusion
routes = router.get_routes() + api_{route_name}_router.get_routes()
'''


def generate_api_route_file(
    model_name: str,
    route_name: str,
    table_name: str,
    columns: list,
    column_types: Optional[dict] = None,
    private: Optional[set] = None,
    auth: bool = False,
) -> str:
    sensitive_fields = set(private or ()) | SENSITIVE_FIELDS
    display_columns = [col for col in columns if col not in sensitive_fields]
    column_types = column_types or {}
    type_names = {int: "int", float: "float", bool: "bool", str: "str", bytes: "str"}

    create_fields = []
    update_fields = []
    for col in columns:
        if col in sensitive_fields:
            continue
        py_type = type_names.get(column_types.get(col), "str")
        if col not in AUTO_FIELDS:
            create_fields.append(f'    {col}: Optional[{py_type}] = None')
            update_fields.append(f'    {col}: Optional[{py_type}] = None')
        elif col == "active":
            create_fields.append('    active: int = 1')
            update_fields.append('    active: Optional[int] = None')

    pydantic_create_fields = "\n".join(create_fields) or "    pass"
    pydantic_update_fields = "\n".join(update_fields) or "    pass"
    select_expr = ",".join(display_columns) if display_columns else "id"
    sortable = sorted(display_columns)
    auth_arg = ", auth=True" if auth else ""

    return f'''from typing import Literal, Optional

from pydantic import BaseModel

from lila.core.logger import Logger
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.routing import Router
from app.models.{to_snake_case(model_name)} import {model_name}

router = Router(prefix="/api")

SORTABLE = {sortable!r}


class {model_name}Create(BaseModel):
{pydantic_create_fields}


class {model_name}Update(BaseModel):
{pydantic_update_fields}


@router.get("/{route_name}"{auth_arg})
async def get_all_{route_name}(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    order: Literal["asc", "desc"] = "asc",
):
    """List {model_name}: ?page=1&per_page=20&search=x&sort=col&order=desc
    returns {{items, total, pages...}} (React DataTable); without page, a list."""
    if sort is not None and sort not in SORTABLE:
        return JSONResponse({{"success": False, "errors": [{{"sort": "Unknown column"}}]}}, status_code=422)
    try:
        if page is not None:
            return await {model_name}.paginate_async(
                page=page, per_page=per_page or limit, max_per_page=200, select="{select_expr}",
                order_by=sort, desc=order == "desc", search=(search or "")[:200] or None,
            )
        return await {model_name}.get_all_async(
            select="{select_expr}", limit=max(1, min(limit, 500)), offset=max(0, offset),
            order_by=sort, desc=order == "desc", search=(search or "")[:200] or None,
        )
    except Exception as exc:
        Logger.error(f"{model_name} list failed: {{exc}}", exception=exc)
        return JSONResponse({{"success": False, "message": "Could not load records"}}, status_code=500)


@router.get("/{route_name}/{{id:int}}"{auth_arg})
async def get_{route_name}_by_id(request: Request, id: int):
    """Get a single {model_name} by ID"""
    item = await {model_name}.get_by_id_async(id, select="{select_expr}")
    if item is None:
        return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
    return item


@router.post("/{route_name}", model={model_name}Create, csrf=True{auth_arg})
async def create_{route_name}(request: Request, data: {model_name}Create = None):
    """Create a new {model_name} record"""
    input_data = data.model_dump(exclude_none=True) if data else request.state.data.model_dump(exclude_none=True)
    try:
        new_item = await {model_name}.insert_async(**input_data)
        return JSONResponse({{"success": True, "message": "Created", "id": new_item.get("id")}}, status_code=201)
    except Exception as exc:
        Logger.error(f"{model_name} create failed: {{exc}}", exception=exc)
        return JSONResponse({{"success": False, "message": "Could not create the record"}}, status_code=400)


@router.put("/{route_name}/{{id:int}}", model={model_name}Update, csrf=True{auth_arg})
async def update_{route_name}(request: Request, id: int, data: {model_name}Update = None):
    """Update an existing {model_name}"""
    input_data = data.model_dump(exclude_unset=True, exclude_none=True) if data else request.state.data.model_dump(exclude_unset=True, exclude_none=True)
    try:
        success = await {model_name}.update_async(id, **input_data)
        if not success:
            return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
        return {{"success": True, "message": "Saved"}}
    except Exception as exc:
        Logger.error(f"{model_name} update failed: {{exc}}", exception=exc)
        return JSONResponse({{"success": False, "message": "Could not update the record"}}, status_code=400)


@router.delete("/{route_name}/{{id:int}}", csrf=True{auth_arg})
async def delete_{route_name}(request: Request, id: int):
    """Delete a {model_name} record"""
    try:
        success = await {model_name}.delete_async(id)
        if not success:
            return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
        return {{"success": True, "message": "Deleted"}}
    except Exception as exc:
        Logger.error(f"{model_name} delete failed: {{exc}}", exception=exc)
        return JSONResponse({{"success": False, "message": "Could not delete the record"}}, status_code=400)


routes = router.get_routes()
'''


_TS_TYPES = {int: "number", float: "number", bool: "boolean", str: "string"}


def generate_react_page(model_name: str, route_name: str, columns: list, column_types: dict, private: set) -> str:
    """resources/react/pages/Crud/<Model>.tsx: DataTable (server mode) + Modal form."""
    visible = [c for c in columns if c not in private and c != "active"]  # active = soft-delete flag
    editable = [c for c in visible if c not in AUTO_FIELDS]
    ts = {c: _TS_TYPES.get(column_types.get(c), "string") for c in visible}

    def label(col: str) -> str:
        return col.replace("_", " ").capitalize()

    row_fields = "\n".join(f"  {c}: {ts[c]} | null;" for c in visible if c != "id")
    form_type = "\n".join(f"  {c}: {'boolean' if ts[c] == 'boolean' else 'string'};" for c in editable)
    empty = ", ".join(f"{c}: {'false' if ts[c] == 'boolean' else repr('')}" for c in editable)
    from_row = ",\n      ".join(
        f"{c}: Boolean(row.{c})" if ts[c] == "boolean" else f'{c}: row.{c} == null ? "" : String(row.{c})'
        for c in editable
    )
    numeric = [c for c in editable if ts[c] == "number"]
    columns_ts = ",\n          ".join(
        f'{{ key: "{c}", label: "{label(c)}", sortable: true'
        + (', align: "right"' if ts[c] == "number" else "")
        + (', render: (row) => (row.%s ? "✓" : "—")' % c if ts[c] == "boolean" else "")
        + " }"
        for c in visible
    )
    inputs = []
    for c in editable:
        if ts[c] == "boolean":
            inputs.append(f'            <Checkbox name="{c}" label="{label(c)}" />')
        elif ts[c] == "number":
            inputs.append(f'            <Input name="{c}" type="number" step="any" label="{label(c)}" />')
        else:
            inputs.append(f'            <Input name="{c}" label="{label(c)}" />')
    inputs_tsx = "\n".join(inputs) or "            {/* no editable columns */}"
    numeric_ts = ", ".join(repr(c) for c in numeric)

    return f'''// Generated by `lila crud --model {model_name} --react`. Edit freely.
// API: /api/{route_name} (app/routes/api/{route_name}.py)
import {{ useState, type ReactElement }} from "react";
import {{
  Button, Checkbox, DataTable, Form, Input, Modal, ProgressBar, SubmitButton, ThemeToggle, Toaster,
}} from "../../components/ui";

interface Row {{
  id: number;
{row_fields}
}}

type Values = {{
{form_type}
}};

const EMPTY: Values = {{ {empty} }};
const NUMERIC: string[] = [{numeric_ts}];

function toValues(row: Row): Values {{
  return {{
      {from_row}
  }};
}}

// "" -> null for optional fields, numeric strings -> numbers.
function toPayload(values: Values) {{
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => {{
      if (value === "") return [key, null];
      if (NUMERIC.includes(key)) return [key, Number(value)];
      return [key, value];
    }}),
  );
}}

export default function {model_name}Crud({{ api, title }}: {{ api: string; title: string }}) {{
  const [editing, setEditing] = useState<Row | null>(null);
  const [open, setOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const openForm = (row: Row | null) => {{
    setEditing(row);
    setOpen(true);
  }};
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <ProgressBar />
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black">{{title}}</h1>
          <p className="text-sm text-muted-foreground">Search, sort, create, edit and delete.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={{() => openForm(null)}}>+ New</Button>
          <ThemeToggle />
        </div>
      </header>

      <DataTable<Row>
        url={{api}}
        refreshKey={{refresh}}
        defaultSort={{{{ key: "id", desc: true }}}}
        columns={{[
          {columns_ts},
        ]}}
        onEdit={{(row) => openForm(row)}}
        onDelete={{`${{api}}/:id`}}
      />

      <Modal open={{open}} onClose={{() => setOpen(false)}} title={{editing ? `Edit #${{editing.id}}` : `New ${{title}}`}}>
        <Form<Values>
          key={{editing ? editing.id : "new"}}
          action={{editing ? `${{api}}/${{editing.id}}` : api}}
          method={{editing ? "PUT" : "POST"}}
          initial={{editing ? toValues(editing) : EMPTY}}
          transform={{toPayload}}
          successToast
          onSuccess={{() => {{
            setOpen(false);
            setRefresh((n) => n + 1);
          }}}}
        >
{inputs_tsx}
          <SubmitButton>Save</SubmitButton>
        </Form>
      </Modal>
      <Toaster />
    </div>
  );
}}

{model_name}Crud.layout = (page: ReactElement) => page;
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

    return f'''{{# Page template: render() wraps it in the default layout automatically. #}}
<div class="max-w-6xl w-full mx-auto px-4 py-8 flex-1 space-y-6">
    <header class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm">
      <div>
        <h2 class="text-2xl font-black bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
          {model_name} Management
        </h2>
        <p class="text-xs text-slate-400 mt-1 font-semibold">Active CRUD Table with View Transitions</p>
      </div>
      <div class="flex items-center gap-3">
        <button data-onclick="fetchData" class="btn bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs px-3.5 py-2">
          <span>🔄</span> Refresh
        </button>
        <button data-onclick="openModal" class="btn btn-primary text-xs px-4 py-2">
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
        <button data-close-modal class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
      </div>
      <form id="crud-form" class="space-y-3">
        <input type="hidden" id="recordId" name="id" value="" />
{form_fields_html}
        <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800 mt-4">
          <button type="button" data-close-modal class="btn bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs px-4 py-2">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary text-xs px-4 py-2">
            Save
          </button>
        </div>
      </form>
    </dialog>

  <script{{{{ nonce_attr }}}}>
    // ``var``/function declarations: the SPA router re-runs this script on
    // every visit, ``let``/``const`` at top level would throw on the 2nd visit.
    var dt = null;

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

    // Runs on full loads and SPA navigations (DOMContentLoaded only fires once).
    fetchData();
  </script>
</div>
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
    react: bool = typer.Option(False, "--react", help="React page (DataTable + Modal form) instead of Jinja"),
    auth: bool = typer.Option(False, "--auth", help="Require a logged-in session for the page and the API"),
):
    """
    Generate CRUD routes, Pydantic schemas, and HTML view with ResponsiveDataTable.
    """
    if ctx.invoked_subcommand is None:
        if not model:
            typer.echo(ctx.get_help())
            raise typer.Exit(code=0)
        generate(model=model, name=name, react=react, auth=auth)

@app.command()
def generate(
    model: str = typer.Option(..., "--model", "-m", help="Model name (e.g. Product)"),
    name: str = typer.Option(None, "--name", "-n", help="Route slug (defaults to snake_case)"),
    react: bool = typer.Option(False, "--react", help="React page (DataTable + Modal form) instead of Jinja"),
    auth: bool = typer.Option(False, "--auth", help="Require a logged-in session for the page and the API"),
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

    private = private_fields(model_class)

    # Web route
    web_dir = Path("app/routes/web")
    web_dir.mkdir(parents=True, exist_ok=True)
    _write_with_backup(web_dir / f"{route_name}.py", generate_web_route_file(model_name, route_name, react=react, auth=auth))

    # API route
    api_dir = Path("app/routes/api")
    api_dir.mkdir(parents=True, exist_ok=True)
    _write_with_backup(
        api_dir / f"{route_name}.py",
        generate_api_route_file(model_name, route_name, table_name, columns, column_types, private=private, auth=auth),
    )

    if react:
        from lila.cli.react import copy_ui, init as react_init, is_react_project

        if not is_react_project():
            typer.secho("  ⚛️  React is not set up yet: running `lila react init --no-routes`...", fg=typer.colors.CYAN)
            react_init(install=False, force=False, routes=False, js=False)
        else:
            copy_ui(quiet=True)
        page = Path(f"resources/react/pages/Crud/{model_name}.tsx")
        _write_with_backup(page, generate_react_page(model_name, route_name, columns, column_types, private))
        typer.echo(f"  ⚛️  {page}")
    else:
        # Template
        tmpl_dir = Path(f"resources/html/{route_name}")
        tmpl_dir.mkdir(parents=True, exist_ok=True)
        _write_with_backup(
            tmpl_dir / "index.jinja", generate_html_template(model_name, route_name, columns)
        )
    if not auth:
        typer.secho(
            f"  ⚠️ /{route_name} and /api/{route_name} are public: use --auth (or add auth=True/roles=[...]) before deploying.",
            fg=typer.colors.YELLOW,
        )

    add_route_import_to_main(route_name, model_name)
    typer.secho(f"🎉 CRUD scaffold for {model_name} generated successfully at /{route_name} and /api/{route_name}", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()
