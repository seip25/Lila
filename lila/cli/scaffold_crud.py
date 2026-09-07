import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer
import os
from pathlib import Path
import importlib.util
import sys

app = typer.Typer()

project_root = os.getcwd()


def capitalize_first(text: str) -> str:
    """Capitalize first letter of a string (ucfirst)"""
    if not text:
        return text
    return text[0].upper() + text[1:]


def to_snake_case(text: str) -> str:
    """Convert CamelCase to snake_case for table names"""
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def get_model_class(model_name: str):
    """
    Dynamically import and return the model class
    
    Args:
        model_name: Name of the model class (e.g., 'User', 'Product')
        
    Returns:
        Model class or None if not found
    """
    try:
        # Convert model name to file name
        file_name = to_snake_case(model_name)
        model_path = os.path.join(project_root, "app", "models", f"{file_name}.py")
        
        if not os.path.exists(model_path):
            return None
        
        # Import the module dynamically
        spec = importlib.util.spec_from_file_location(f"app.models.{file_name}", model_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"app.models.{file_name}"] = module
        spec.loader.exec_module(module)
        
        # Get the model class
        if hasattr(module, model_name):
            return getattr(module, model_name)
        
        return None
    except Exception as e:
        typer.echo(f"❌ Error loading model: {e}")
        return None


def get_model_columns(model_class) -> list:
    """
    Extract column names from SQLAlchemy model
    
    Args:
        model_class: SQLAlchemy model class
        
    Returns:
        List of column names
    """
    try:
        if hasattr(model_class, '__table__'):
            return [col.name for col in model_class.__table__.columns]
        return []
    except Exception as e:
        typer.echo(f"⚠️ Warning: Could not extract columns: {e}")
        return []


def generate_web_route_file(model_name: str, route_name: str) -> str:
    """Generate the web (HTML) route file — renders the template and pulls api routes in"""
    return f'''# English: Web route for {model_name} — renders the HTML page
# Español: Ruta web para {model_name} — renderiza la página HTML

from lila.core.request import Request
from lila.core.routing import Router
from lila.core.templates import render
from app.routes.api.{route_name} import routes as api_{route_name}_routes
import itertools

router = Router()


@router.get("/{route_name}")
async def {route_name}_index(request: Request):
    """
    Render the main HTML page with DataTable for {model_name} management
    """
    return render(request=request, template="{route_name}/index")


# English: Merge api routes so main.py only needs to import this file
# Español: Combinar rutas api para que main.py solo necesite importar este archivo
routes = list(itertools.chain(router.get_routes(), api_{route_name}_routes))
'''


def generate_api_route_file(model_name: str, route_name: str, table_name: str, columns: list) -> str:
    """Generate the API (JSON) route file with full CRUD endpoints using modern Pydantic pattern"""

    # Filter sensitive fields
    sensitive_fields = {"password", "token", "hash"}
    display_columns = [col for col in columns if col not in sensitive_fields]

    # Generate Pydantic model fields
    pydantic_fields = []
    for col in columns:
        if col not in {"id", "created_at", "updated_at"}:
            pydantic_fields.append(f'    {col}: str  # TODO: Adjust type as needed')

    pydantic_create_fields = "\n".join(pydantic_fields) or "    pass"
    pydantic_update_fields = "\n".join(
        [f.replace("    ", "    ") for f in pydantic_fields]
    ) or "    pass"

    return f'''# English: API routes for {model_name} CRUD operations
# Español: Rutas API para operaciones CRUD de {model_name}

from lila.core.request import Request
from lila.core.routing import Router
from lila.core.responses import JSONResponse
from app.connections import connection
from app.models.{to_snake_case(model_name)} import {model_name}
from pydantic import BaseModel
from typing import Optional

router = Router(prefix="api/v1")


# English: Pydantic models for validation — adjust field types as needed
# Español: Modelos Pydantic para validación — ajustar tipos según necesidad
class {model_name}Create(BaseModel):
{pydantic_create_fields}


class {model_name}Update(BaseModel):
{pydantic_update_fields}


# English: Get all {model_name} records
# Español: Obtener todos los registros de {model_name}
@router.get("/{route_name}")
async def get_all_{route_name}(request: Request):
    """Get all active {model_name} records"""
    try:
        items = await {model_name}.get_all_async(select="{','.join(display_columns)}", limit=1000)
        return JSONResponse(items)
    except Exception as e:
        print(str(e))
        return JSONResponse({{"success": False, "message": "Error fetching data"}}, status_code=500)


# English: Get a single {model_name} by ID
# Español: Obtener un {model_name} por ID
@router.get("/{route_name}/{{{{id}}}}")
async def get_{route_name}_by_id(request: Request):
    """Get a single {model_name} record by ID"""
    try:
        id = int(request.path_params.get("id"))
        item = await {model_name}.get_by_id_async(id)
        if item is None:
            return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
        result = {{col: getattr(item, col) for col in {display_columns}}}
        return JSONResponse(result)
    except Exception as e:
        print(str(e))
        return JSONResponse({{"success": False, "message": "Error fetching data"}}, status_code=500)


# English: Create a new {model_name}
# Español: Crear un nuevo {model_name}
@router.post("/{route_name}", model={model_name}Create)
async def create_{route_name}(request: Request):
    """Create a new {model_name} record"""
    input = request.state.data
    db = connection.get_session()
    try:
        new_item = {model_name}.insert(db, input.dict())
        db.commit()
        db.refresh(new_item)
        return JSONResponse({{"success": True, "id": new_item.id}}, status_code=201)
    except Exception as e:
        db.rollback()
        print(str(e))
        return JSONResponse({{"success": False, "message": "Error creating record"}}, status_code=500)
    finally:
        db.close()


# English: Update an existing {model_name}
# Español: Actualizar un {model_name} existente
@router.put("/{route_name}/{{{{id}}}}", model={model_name}Update)
async def update_{route_name}(request: Request):
    """Update an existing {model_name} record"""
    id = int(request.path_params.get("id"))
    input = request.state.data
    db = connection.get_session()
    try:
        success = {model_name}.update(db, id, input.dict(exclude_unset=True))
        if not success:
            return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
        db.commit()
        return JSONResponse({{"success": True}})
    except Exception as e:
        db.rollback()
        print(str(e))
        return JSONResponse({{"success": False, "message": "Error updating record"}}, status_code=500)
    finally:
        db.close()


# English: Soft-delete a {model_name} (sets active = 0)
# Español: Borrado lógico de un {model_name} (pone active = 0)
@router.delete("/{route_name}/{{{{id}}}}")
async def delete_{route_name}(request: Request):
    """Soft delete a {model_name} record"""
    try:
        id = int(request.path_params.get("id"))
        db = connection.get_session()
        try:
            success = {model_name}.delete(db, id)
            if not success:
                return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
            db.commit()
            return JSONResponse({{"success": True}})
        finally:
            db.close()
    except Exception as e:
        print(str(e))
        return JSONResponse({{"success": False, "message": "Error deleting record"}}, status_code=500)


routes = router.get_routes()
'''


def generate_html_template(model_name: str, route_name: str, columns: list) -> str:
    """Generate the HTML template with DataTable and modals"""
    
    # Filter sensitive fields
    sensitive_fields = {"password", "token", "hash", "active"}
    display_columns = [col for col in columns if col not in sensitive_fields]
    
    # Generate DataTable columns
    cols_js = ",\n      ".join(
        [f"{{ key: '{col}', title: '{col.capitalize()}' }}" for col in display_columns]
    )
    
    # Generate form fields
    form_fields = []
    for col in columns:
        if col not in {"id", "created_at", "updated_at", "active"}:
            field_type = "password" if col == "password" else "text"
            form_fields.append(
                f'      <div>\n'
                f'        <label class="block text-sm font-bold text-slate-600 dark:text-slate-400 mb-2">{col.capitalize()}</label>\n'
                f'        <input name="{col}" type="{field_type}" class="input-lila" />\n'
                f'      </div>'
            )
    
    form_fields_html = "\n".join(form_fields)
    
    template_content = f'''<!DOCTYPE html>
<html lang="{{{{ lang }}}}" class="light">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light dark" />
    <meta http-equiv="X-UA-Compatible" content="ie=edge" />
    <title>{model_name.capitalize()} CRUD</title>
    <link rel="icon" type="image/x-icon" href="{{{{ public('img/lila.png') }}}}" />
    {{{{ asset('css/tailwind.css') | safe }}}}
    <script src="{{{{ public('js/utils.js') }}}}"></script>
  </head>
  <body class="bg-bg-body dark:bg-bg-body-dark text-slate-800 dark:text-slate-200 min-h-screen flex flex-col font-sans transition-colors duration-300">
    <header class="bg-surface dark:bg-surface-dark border-b border-slate-200 dark:border-slate-800 py-4 shadow-sm">
      <nav class="max-w-6xl mx-auto px-4 flex justify-between items-center">
        <h2 class="text-xl font-black bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">{model_name.capitalize()} CRUD</h2>
        <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Resource Scaffold</span>
      </nav>
    </header>
    <main class="max-w-6xl w-full mx-auto px-4 py-8 flex-1">
      <div class="flex justify-between items-center mb-6">
        <button id="create-btn" class="btn btn-primary" onclick="openDialog('{{{{translate['Create']}}}}')">
          <span>➕</span> {{{{translate['Create']}}}}
        </button>
        <button class="btn btn-outline" onclick="fetchData{model_name}()">
          <span>🔄</span> {{{{translate['Refresh']}}}}
        </button>
      </div>

      <div id="datatable-container" class="bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-material overflow-x-auto"></div>

      <dialog id="crud-dialog" class="p-6 rounded-2xl w-full max-w-md bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-850 shadow-material-lg backdrop:bg-slate-900/40 backdrop:backdrop-blur-sm">
        <article class="flex flex-col gap-6">
          <h2 id="crud-title" class="text-2xl font-black text-slate-850 dark:text-slate-100 tracking-tight"></h2>
          <form id="crud-form" method="dialog" class="space-y-4">
{form_fields_html}

            <div class="text-right mt-4" id="form_messages"></div>
            <div class="flex justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-850">
              <button type="button" id="cancel-btn" class="btn btn-light">
                {{{{translate['Cancel']}}}}
              </button>
              <button type="submit" class="btn btn-primary">{{{{translate['Save']}}}}</button>
            </div>
          </form>
        </article>
      </dialog>
    </main>

    <footer class="bg-surface dark:bg-surface-dark border-t border-slate-200 dark:border-slate-800 py-6 transition-colors duration-300 mt-auto">
      <div class="max-w-6xl mx-auto px-4 flex justify-center gap-2">
        <a href="?lang=es" class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-surface dark:bg-surface-dark hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold transition-all shadow-sm flex items-center gap-1">
          <span>🇪🇸</span> Español
        </a>
        <a href="?lang=en" class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-surface dark:bg-surface-dark hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold transition-all shadow-sm flex items-center gap-1">
          <span>🇺🇸</span> English
        </a>
      </div>
    </footer>

    <script>
      const dt = new ResponsiveDataTable('datatable-container', {{
        columns: [
          {cols_js}
        ],
        edit: onEdit{model_name},
        delete: onDelete{model_name}
      }});

      async function fetchData{model_name}() {{
        const res = await fetch('/api/{route_name}');
        const data = await res.json();
        dt.updateData(data);
      }}

      fetchData{model_name}();

      function onEdit{model_name}(e, id) {{
        openDialog('{{{{translate['Edit']}}}}', id);
        fetch(`/api/{route_name}/${{id}}`).then(r=>r.json()).then(d=>{{
          for(const k in d) {{
            const input = document.querySelector(`[name="${{k}}"]`);
            if(input) input.value = d[k] || '';
          }}
        }});
      }}

      function onDelete{model_name}(e, id) {{
        if(confirm('{{{{translate['Are you sure you want to delete this item?']}}}}')) {{
          fetch(`/api/{route_name}/${{id}}`, {{method: 'DELETE'}})
            .then(fetchData{model_name});
        }}
      }}

      function openDialog(mode, id=null) {{
        const dialog = document.getElementById('crud-dialog');
        document.getElementById('crud-title').textContent = mode;
        document.getElementById('crud-form').reset();
        const form_messages = document.getElementById('form_messages');
        form_messages.innerHTML = '';
        dialog.showModal();
        
        document.getElementById('crud-form').onsubmit = async (ev) => {{
          ev.preventDefault();
          const form_messages = document.getElementById('form_messages');
          form_messages.innerHTML = '';
          const data = Object.fromEntries(new FormData(ev.target));
          const url = id ? `/api/{route_name}/${{id}}` : '/api/{route_name}';
          const method = id ? 'PUT' : 'POST';
          const response = await fetch(url, {{
            method,
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(data)
          }});
          
          let msg = '';
          
          if(!response.ok) {{
            const err = await response.json();
            if(err.errors) {{
              for(const e of err.errors) {{
                for(const k in e) {{
                  msg += `<p class="text-red-600">${{k}}: ${{e[k]}}</p>`;
                }}
              }}
              form_messages.innerHTML = msg;
            }} else {{
              msg = err.message || '{{{{translate['Error occurred']}}}} ' + response.status;
              form_messages.innerHTML = `<p class="text-red-600">${{msg}}</p>`;
            }}
          }} else {{
            dialog.close();
            fetchData{model_name}();
          }}
        }};
      }}

      document.getElementById('cancel-btn').onclick = () => {{
        document.getElementById('crud-dialog').close();
      }};
    </script>
  </body>
</html>
'''
    
    return template_content


def add_route_import_to_main(route_name: str, model_name: str) -> bool:
    """Add web route import to main.py using the api_marker system.
    Only the web route needs to be imported — it internally merges the api routes."""
    main_file = os.path.join(project_root, "main.py")

    if not os.path.exists(main_file):
        typer.echo("❌ main.py not found.")
        return False

    with open(main_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    import_statement = f"from app.routes.web.{route_name} import routes as {route_name}_routes"

    # Check if already imported
    if any(import_statement in line for line in lines):
        typer.echo(f"⚠️ Routes for {route_name} already imported in main.py")
        return True

    # Find all_routes line and api_marker
    all_routes_idx = -1
    marker_idx = -1

    for i, line in enumerate(lines):
        if "all_routes = list(itertools.chain(" in line:
            all_routes_idx = i
        if "# api_marker" in line:
            marker_idx = i

    if marker_idx == -1:
        typer.echo("⚠️ Marker '# api_marker' not found in main.py. Please add routes manually.")
        return False

    # Add import before marker
    lines.insert(marker_idx, f"{import_statement}\n")

    # Update all_routes line (index shifted by 1 after insert)
    if all_routes_idx != -1:
        old_line = lines[all_routes_idx]
        import re
        match = re.search(r"all_routes = list\(itertools\.chain\((.*?)\)\)", old_line)
        if match:
            existing_routes = match.group(1)
            if route_name not in existing_routes:
                new_routes = f"{existing_routes}, {route_name}_routes"
                lines[all_routes_idx] = f"all_routes = list(itertools.chain({new_routes}))\n"

    with open(main_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    typer.echo("✅ Routes imported in main.py")
    return True


@app.command()
def main(
    model: str = typer.Option(None, "--model", "-m", help="Name of the model class (e.g., User, Product)"),
    name: str = typer.Option(None, "--name", "-n", help="Name for routes and templates (defaults to snake_case of model)")
):
    """
    Create a complete CRUD scaffold for a model
    
    Examples:
        python -m cli.scaffold_crud --model User
        python -m cli.scaffold_crud --model Product --name products
        python -m cli.scaffold_crud -m Category -n categories
    
    This will generate:
    - Route file with GET, POST, PUT, DELETE endpoints
    - HTML template with DataTable and modals
    - Auto-import routes in main.py
    
    The model must already exist in app/models/
    """
    
    if not model:
        typer.echo("❌ Model name is required. Use --model or -m")
        raise typer.Exit(code=1)
    
    # Capitalize model name
    model_name = capitalize_first(model)
    
    # Generate route name
    if name is None:
        route_name = to_snake_case(model_name)
    else:
        route_name = name.lower()
    
    typer.echo(f"\n🔍 Validating model '{model_name}'...")
    
    # Check if model exists
    model_class = get_model_class(model_name)
    if model_class is None:
        typer.echo(f"❌ Model '{model_name}' not found in app/models/")
        typer.echo(f"💡 Create the model first using: python -m cli.model create --name {model_name}")
        raise typer.Exit(code=1)
    
    typer.echo(f"✅ Model '{model_name}' found")

    # Get model columns
    columns = get_model_columns(model_class)
    if not columns:
        typer.echo("⚠️ Warning: Could not extract columns from model. Using default columns.")
        columns = ["id", "name", "active", "created_at"]

    table_name = model_class.__tablename__ if hasattr(model_class, '__tablename__') else route_name

    typer.echo(f"📋 Columns: {', '.join(columns)}")
    typer.echo(f"🗄️  Table: {table_name}")

    # Generate web route file
    typer.echo(f"\n📝 Generating web route file...")
    web_route_content = generate_web_route_file(model_name, route_name)

    web_routes_dir = Path("app/routes/web")
    web_routes_dir.mkdir(parents=True, exist_ok=True)

    web_route_file = web_routes_dir / f"{route_name}.py"
    if web_route_file.exists():
        overwrite = typer.confirm(f"Web route file web/{route_name}.py already exists. Overwrite?")
        if not overwrite:
            typer.echo("Operation cancelled.")
            raise typer.Exit()

    with open(web_route_file, 'w', encoding='utf-8') as f:
        f.write(web_route_content)
    typer.echo(f"✅ Web route file created: app/routes/web/{route_name}.py")

    # Generate api route file
    typer.echo(f"\n📝 Generating api route file...")
    api_route_content = generate_api_route_file(model_name, route_name, table_name, columns)

    api_routes_dir = Path("app/routes/api")
    api_routes_dir.mkdir(parents=True, exist_ok=True)

    api_route_file = api_routes_dir / f"{route_name}.py"
    if api_route_file.exists():
        overwrite = typer.confirm(f"API route file api/{route_name}.py already exists. Overwrite?")
        if not overwrite:
            typer.echo("Skipping API route generation.")
        else:
            with open(api_route_file, 'w', encoding='utf-8') as f:
                f.write(api_route_content)
            typer.echo(f"✅ API route file created: app/routes/api/{route_name}.py")
    else:
        with open(api_route_file, 'w', encoding='utf-8') as f:
            f.write(api_route_content)
        typer.echo(f"✅ API route file created: app/routes/api/{route_name}.py")

    # Generate HTML template
    typer.echo(f"\n🎨 Generating HTML template...")
    template_content = generate_html_template(model_name, route_name, columns)

    template_dir = Path(f"resources/html/{route_name}")
    template_dir.mkdir(parents=True, exist_ok=True)

    template_file = template_dir / "index.jinja"
    if template_file.exists():
        overwrite = typer.confirm(f"Template {route_name}/index.jinja already exists. Overwrite?")
        if not overwrite:
            typer.echo("Skipping template generation.")
        else:
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(template_content)
            typer.echo(f"✅ Template created: resources/html/{route_name}/index.jinja")
    else:
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_content)
        typer.echo(f"✅ Template created: resources/html/{route_name}/index.jinja")

    # Add web route import to main.py (api routes come along automatically)
    typer.echo(f"\n🔗 Adding routes to main.py...")
    add_route_import_to_main(route_name, model_name)

    typer.echo(f"\n🎉 Scaffold created successfully!")
    typer.echo(f"\n📍 Routes available:")
    typer.echo(f"   • GET    /{route_name}                  - HTML page with DataTable")
    typer.echo(f"   • GET    /api/v1/{route_name}            - Get all records (JSON)")
    typer.echo(f"   • GET    /api/v1/{route_name}/{{id}}     - Get by ID (JSON)")
    typer.echo(f"   • POST   /api/v1/{route_name}            - Create new record")
    typer.echo(f"   • PUT    /api/v1/{route_name}/{{id}}     - Update record")
    typer.echo(f"   • DELETE /api/v1/{route_name}/{{id}}     - Delete record (soft delete)")
    typer.echo(f"\n💡 Next steps:")
    typer.echo(f"   1. Review app/routes/web/{route_name}.py and app/routes/api/{route_name}.py")
    typer.echo(f"   2. Adjust Pydantic field types in the Create/Update models")
    typer.echo(f"   3. Customize the HTML template if needed")
    typer.echo(f"   4. Restart your server to see the changes")


if __name__ == "__main__":
    app()
