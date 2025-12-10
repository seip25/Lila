import typer
import os
from pathlib import Path
import importlib.util
import sys

app = typer.Typer()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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


def generate_route_file(model_name: str, route_name: str, table_name: str, columns: list) -> str:
    """Generate the route file content with CRUD endpoints"""
    
    # Filter sensitive fields
    sensitive_fields = {"password", "token", "hash"}
    display_columns = [col for col in columns if col not in sensitive_fields]
    
    # Generate Pydantic model fields
    pydantic_fields = []
    for col in columns:
        if col not in {"id", "created_at", "updated_at"}:
            pydantic_fields.append(f'#     {col}: str  # TODO: Adjust type as needed')
    
    pydantic_fields_str = "\n".join(pydantic_fields)
    
    route_content = f'''# English: Routes for {model_name} CRUD operations
# Español: Rutas para operaciones CRUD de {model_name}

from core.request import Request
from core.routing import Router
from core.templates import render
from core.responses import JSONResponse
from app.connections import connection
from app.models.{to_snake_case(model_name)} import {model_name}
from pydantic import BaseModel, ValidationError
from typing import Optional

# English: Creating router instance for {route_name}
# Español: Creando instancia del router para {route_name}
router = Router()

# English: Pydantic model for validation (uncomment and adjust as needed)
# Español: Modelo Pydantic para validación (descomentar y ajustar según necesidad)
# class {model_name}Create(BaseModel):
{pydantic_fields_str}
# 
# class {model_name}Update(BaseModel):
{pydantic_fields_str}


# English: HTML page with DataTable for {model_name}
# Español: Página HTML con DataTable para {model_name}
@router.get("/{route_name}")
async def {route_name}_index(request: Request):
    """
    Render the main HTML page with DataTable for {model_name} management
    """
    response = render(request=request, template="{route_name}/index")
    return response


# English: API endpoint to get all {model_name} records
# Español: Endpoint API para obtener todos los registros de {model_name}
@router.get("/api/{route_name}")
async def get_all_{route_name}(request: Request):
    """
    Get all active {model_name} records
    
    Returns:
        JSON response with list of {model_name} records
    """
    try:
        # Get all active records
        items = {model_name}.get_all(select="{','.join(display_columns)}", limit=1000)
        return JSONResponse(items)
    except Exception as e:
        return JSONResponse({{"success": False, "message": "Error fetching data"}}, status_code=500)


# English: API endpoint to get a single {model_name} by ID
# Español: Endpoint API para obtener un {model_name} por ID
@router.get("/api/{route_name}/{{id}}")
async def get_{route_name}_by_id(request: Request):
    """
    Get a single {model_name} record by ID
    
    Args:
        id: {model_name} ID from path parameters
        
    Returns:
        JSON response with {model_name} data or 404
    """
    try:
        id = int(request.path_params.get("id"))
        db = connection.get_session()
        
        try:
            item = {model_name}.get_by_id(db, id)
            if item is None:
                return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
            
            # Convert to dict
            result = {{col: getattr(item, col) for col in {display_columns}}}
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({{"success": False, "message": "Error fetching data"}}, status_code=500)


# English: API endpoint to create a new {model_name}
# Español: Endpoint API para crear un nuevo {model_name}
@router.post("/api/{route_name}")
async def create_{route_name}(request: Request):
    """
    Create a new {model_name} record
    
    Request body should contain {model_name} data
    
    Returns:
        JSON response with success status and new record ID
    """
    try:
        body = await request.json()
        
        # Uncomment to use Pydantic validation:
        # try:
        #     validated_data = {model_name}Create(**body)
        #     body = validated_data.dict()
        # except ValidationError as e:
        #     errors = []
        #     for err in e.errors():
        #         field = err["loc"][0]
        #         msg = err["msg"]
        #         errors.append({{field: msg}})
        #     return JSONResponse(
        #         {{"success": False, "errors": errors}},
        #         status_code=400
        #     )
        
        db = connection.get_session()
        try:
            new_item = {model_name}.insert(db, body)
            db.commit()
            db.refresh(new_item)
            
            return JSONResponse(
                {{"success": True, "id": new_item.id}},
                status_code=201
            )
        finally:
            db.close()
            
    except Exception as e:
        return JSONResponse({{"success": False, "message": "Error creating record"}}, status_code=500)


# English: API endpoint to update a {model_name}
# Español: Endpoint API para actualizar un {model_name}
@router.put("/api/{route_name}/{{id}}")
async def update_{route_name}(request: Request):
    """
    Update an existing {model_name} record
    
    Args:
        id: {model_name} ID from path parameters
        
    Request body should contain fields to update
    
    Returns:
        JSON response with success status
    """
    try:
        id = int(request.path_params.get("id"))
        body = await request.json()
        
        # Uncomment to use Pydantic validation:
        # try:
        #     validated_data = {model_name}Update(**body)
        #     body = validated_data.dict(exclude_unset=True)
        # except ValidationError as e:
        #     errors = []
        #     for err in e.errors():
        #         field = err["loc"][0]
        #         msg = err["msg"]
        #         errors.append({{field: msg}})
        #     return JSONResponse(
        #         {{"success": False, "errors": errors}},
        #         status_code=400
        #     )
        
        db = connection.get_session()
        try:
            success = {model_name}.update(db, id, body)
            if not success:
                return JSONResponse({{"success": False, "message": "Not found"}}, status_code=404)
            
            db.commit()
            return JSONResponse({{"success": True}})
        finally:
            db.close()
            
    except Exception as e:
        return JSONResponse({{"success": False, "message": "Error updating record"}}, status_code=500)


# English: API endpoint to delete a {model_name} (soft delete)
# Español: Endpoint API para eliminar un {model_name} (borrado lógico)
@router.delete("/api/{route_name}/{{id}}")
async def delete_{route_name}(request: Request):
    """
    Soft delete a {model_name} record (sets active = 0)
    
    Args:
        id: {model_name} ID from path parameters
        
    Returns:
        JSON response with success status
    """
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
        return JSONResponse({{"success": False, "message": "Error deleting record"}}, status_code=500)


# English: Get all defined routes
# Español: Obtener todas las rutas definidas
routes = router.get_routes()
'''
    
    return route_content


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
                f'        <label class="block text-sm">{col.capitalize()}</label>\n'
                f'        <input name="{col}" type="{field_type}" class="w-full p-2 border rounded" />\n'
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
    <link rel="stylesheet" href="{{{{ public('css/lila.css') }}}}" />
    <script src="{{{{ public('js/utils.js') }}}}"></script>
  </head>
  <body>
    <header class="shadow">
      <nav class="container">
        <h2 class="mt-4 mb-4">{model_name.capitalize()} CRUD</h2>
      </nav>
    </header>
    <main class="container mt-4">
      <div class="flex justify-between items-center mb-4">
        <button id="create-btn" class="mb-4" onclick="openDialog('{{{{translate['Create']}}}}')">
          {{{{translate['Create']}}}}
        </button>
        <button class="mb-4 outline" onclick="fetchData{model_name}()">
          {{{{translate['Refresh']}}}}
        </button>
      </div>

      <div id="datatable-container"></div>

      <dialog id="crud-dialog" class="p-4 rounded w-full max-w-md">
        <article>
          <h2 id="crud-title" class="text-xl font-semibold mb-4"></h2>
          <form id="crud-form" method="dialog" class="space-y-4">
{form_fields_html}

            <div class="text-right mt-4" id="form_messages"></div>
            <div class="flex justify-end gap-4 space-x-2">
              <button type="button" id="cancel-btn" class="ghost">
                {{{{translate['Cancel']}}}}
              </button>
              <button type="submit">{{{{translate['Save']}}}}</button>
            </div>
          </form>
        </article>
      </dialog>
    </main>

    <footer class="bg-surface py-4 mt-auto">
      <div class="container mx-auto px-4 flex justify-between items-center">
        <a href="/set-language/es" class="underline">Español (Esp)</a>
        <a href="/set-language/en" class="underline">English (US)</a>
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
    """Add route import to main.py using marker system"""
    main_file = os.path.join(project_root, "main.py")
    
    if not os.path.exists(main_file):
        typer.echo("❌ main.py not found.")
        return False
    
    with open(main_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    import_statement = f"from app.routes.{route_name} import routes as {route_name}_routes"
    
    # Check if already imported
    if any(import_statement in line for line in lines):
        typer.echo(f"⚠️ Routes for {route_name} already imported in main.py")
        return True
    
    # Find all_routes line and marker
    all_routes_idx = -1
    marker_idx = -1
    
    for i, line in enumerate(lines):
        if "all_routes = list(itertools.chain(" in line:
            all_routes_idx = i
        if "# api_marker" in line:
            marker_idx = i
    
    if marker_idx == -1:
        typer.echo(f"⚠️ Marker '# api_marker' not found in main.py. Please add routes manually.")
        return False
    
    # Add import before marker
    lines.insert(marker_idx, f"{import_statement}\n")
    
    # Update all_routes line (now at all_routes_idx since we inserted before)
    if all_routes_idx != -1:
        old_line = lines[all_routes_idx]
        # Extract existing routes from the chain
        import re
        match = re.search(r"all_routes = list\(itertools\.chain\((.*?)\)\)", old_line)
        if match:
            existing_routes = match.group(1)
            if route_name not in existing_routes:
                new_routes = f"{existing_routes}, {route_name}_routes"
                lines[all_routes_idx] = f"all_routes = list(itertools.chain({new_routes}))\n"
    
    with open(main_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    typer.echo(f"✅ Routes imported in main.py")
    return True


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
    
    # Generate route file
    typer.echo(f"\n📝 Generating route file...")
    route_content = generate_route_file(model_name, route_name, table_name, columns)
    
    routes_dir = Path("app/routes")
    routes_dir.mkdir(parents=True, exist_ok=True)
    
    route_file = routes_dir / f"{route_name}.py"
    
    if route_file.exists():
        overwrite = typer.confirm(f"Route file {route_name}.py already exists. Overwrite?")
        if not overwrite:
            typer.echo("Operation cancelled.")
            raise typer.Exit()
    
    with open(route_file, 'w', encoding='utf-8') as f:
        f.write(route_content)
    
    typer.echo(f"✅ Route file created: app/routes/{route_name}.py")
    
    # Generate HTML template
    typer.echo(f"\n🎨 Generating HTML template...")
    template_content = generate_html_template(model_name, route_name, columns)
    
    template_dir = Path(f"templates/html/{route_name}")
    template_dir.mkdir(parents=True, exist_ok=True)
    
    template_file = template_dir / "index.html"
    
    if template_file.exists():
        overwrite = typer.confirm(f"Template {route_name}/index.html already exists. Overwrite?")
        if not overwrite:
            typer.echo("Skipping template generation.")
        else:
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(template_content)
            typer.echo(f"✅ Template created: templates/html/{route_name}/index.html")
    else:
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_content)
        typer.echo(f"✅ Template created: templates/html/{route_name}/index.html")
    
    # Add import to main.py
    typer.echo(f"\n🔗 Adding routes to main.py...")
    add_route_import_to_main(route_name, model_name)
    
    typer.echo(f"\n🎉 Scaffold created successfully!")
    typer.echo(f"\n📍 Routes available:")
    typer.echo(f"   • GET  /{route_name}           - HTML page with DataTable")
    typer.echo(f"   • GET  /api/{route_name}       - Get all records (JSON)")
    typer.echo(f"   • GET  /api/{route_name}/{{id}} - Get by ID (JSON)")
    typer.echo(f"   • POST /api/{route_name}       - Create new record")
    typer.echo(f"   • PUT  /api/{route_name}/{{id}} - Update record")
    typer.echo(f"   • DELETE /api/{route_name}/{{id}} - Delete record (soft delete)")
    typer.echo(f"\n💡 Next steps:")
    typer.echo(f"   1. Review and customize app/routes/{route_name}.py")
    typer.echo(f"   2. Uncomment Pydantic validation if needed")
    typer.echo(f"   3. Customize the HTML template if needed")
    typer.echo(f"   4. Restart your server to see the changes")


if __name__ == "__main__":
    main()
