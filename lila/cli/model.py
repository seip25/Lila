import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer
import os
from pathlib import Path

app = typer.Typer()

# Template for model generation
MODEL_TEMPLATE = '''from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from lila.core.base_model import BaseModel

class {model_name}(BaseModel):
    """
    {model_name} Model
    
    Inherits standard CRUD and helper methods from BaseModel:
    - get_all(select, limit, **filters)
    - get_by_id(db, id)
    - insert(db, params)
    - update(db, id, params)
    - delete(db, id)
    - get_all_without_orm(select, limit, **filters)
    - get_by_id_without_orm(id, select)
    - get_related(model_class, foreign_key_field)
    - get_related_many(model_class, foreign_key_field, limit)
    
    Example column types you can use:
    - Integer: Column(Integer, primary_key=True, autoincrement=True, index=True)
    - String: Column(String(length=50), nullable=False)
    - Unique String: Column(String(length=50), unique=True)
    - TIMESTAMP: Column(TIMESTAMP, nullable=False, server_default=func.now())
    - Boolean/Active: Column(Integer, nullable=False, default=1)
    - Float: Column(Float, nullable=True)
    - Text: Column(Text, nullable=True)
    - Date: Column(Date, nullable=True)
    - DateTime: Column(DateTime, nullable=True)
    - Boolean: Column(Boolean, default=True)
    - ForeignKey: Column(Integer, ForeignKey('other_table.id'))
    """
    __tablename__ = "{table_name}"
    
    # Define your columns here
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(length=100), nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Example of additional columns (uncomment and modify as needed):
    # description = Column(String(length=255), nullable=True)
    # email = Column(String(length=100), unique=True)
    # price = Column(Float, nullable=True)
    # is_available = Column(Integer, default=1)
    # updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
'''


def capitalize_first(text: str) -> str:
    """Capitalize first letter of a string (ucfirst)"""
    if not text:
        return text
    return text[0].upper() + text[1:]


def to_snake_case(text: str) -> str:
    """Convert CamelCase to snake_case for table names"""
    import re
    # Insert underscore before uppercase letters and convert to lowercase
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()





@app.command()
def create(
    name: str = typer.Option(None, "--name", "-n", help="Name of the model (e.g., User, Product, Category)"),
    table: str = typer.Option(None, "--table", "-t", help="Table name (defaults to snake_case of model name)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Force interactive mode")
):
    """
    Create a new SQLAlchemy model skeleton (interactively or via options)
    
    Examples:
        python -m cli.model create --name User
        python -m cli.model create --name Product --table products
        python -m cli.model create -n Category
        python -m cli.model create (triggers interactive mode)
    """
    is_interactive = interactive or (name is None)
    
    if is_interactive:
        typer.echo("Welcome to the Lila Interactive Model Builder!\n")
        if not name:
            name = typer.prompt("Enter model name (e.g., Product, Customer)").strip()
            if not name:
                typer.echo("Model name cannot be empty.")
                raise typer.Exit(code=1)
                
    # Capitalize first letter of model name
    model_name = capitalize_first(name)
    
    if is_interactive and table is None:
        default_table = to_snake_case(model_name) + "s"
        table_name = typer.prompt("Enter table name", default=default_table).strip()
    elif table:
        table_name = table
    else:
        table_name = to_snake_case(model_name) + "s"
        
    has_id = True
    has_active = True
    has_created = True
    has_updated = False
    custom_columns = []
    
    if is_interactive:
        has_id = typer.confirm("Include standard primary key 'id' column?", default=True)
        has_active = typer.confirm("Enable soft delete logic (adds 'active' column)?", default=True)
        has_created = typer.confirm("Add 'created_at' timestamp column?", default=True)
        has_updated = typer.confirm("Add 'updated_at' timestamp column?", default=True)
        
        add_columns = typer.confirm("\nWould you like to add custom columns interactively?", default=False)
        while add_columns:
            col_name = typer.prompt("   Name of the column").strip()
            if not col_name:
                break
                
            col_type = typer.prompt(
                "   Type (String, Integer, Float, Text, Boolean)",
                default="String"
            ).strip().capitalize()
            
            # Normalize type
            if col_type in ("String", "Str"):
                col_type = "String"
            elif col_type in ("Integer", "Int"):
                col_type = "Integer"
            elif col_type in ("Float", "Double", "Decimal"):
                col_type = "Float"
            elif col_type in ("Text", "Txt"):
                col_type = "Text"
            elif col_type in ("Boolean", "Bool"):
                col_type = "Boolean"
            else:
                col_type = "String"
                
            length_str = ""
            if col_type == "String":
                length = typer.prompt("   String length", default=100, type=int)
                length_str = f"length={length}"
                
            nullable = typer.confirm("   Nullable?", default=True)
            unique = typer.confirm("   Unique?", default=False)
            
            default_val = typer.prompt("   Default value (leave empty for None)", default="").strip()
            
            col_def = {
                "name": col_name,
                "type": col_type,
                "length": length_str,
                "nullable": nullable,
                "unique": unique,
                "default": default_val
            }
            custom_columns.append(col_def)
            
            add_columns = typer.confirm("\nAdd another column?", default=False)
            
    # Create models directory if it doesn't exist
    models_dir = Path("app/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename (snake_case)
    filename = to_snake_case(model_name) + ".py"
    file_path = models_dir / filename
    
    # Check if file already exists
    if file_path.exists():
        overwrite = typer.confirm(f"File {filename} already exists. Overwrite?")
        if not overwrite:
            typer.echo("Operation cancelled.")
            raise typer.Exit()
            
    # Generate model content
    if not is_interactive:
        model_content = MODEL_TEMPLATE.format(
            model_name=model_name,
            table_name=table_name
        )
    else:
        lines = []
        lines.append("from sqlalchemy import Column, Integer, String, TIMESTAMP, Float, Text, Boolean, func")
        lines.append("from lila.core.base_model import BaseModel")
        lines.append("")
        lines.append(f"class {model_name}(BaseModel):")
        lines.append('    """')
        lines.append(f"    {model_name} Model")
        lines.append('    """')
        lines.append(f'    __tablename__ = "{table_name}"')
        
        if not has_active:
            lines.append("    _delete_logic = False")
            
        lines.append("")
        
        if has_id:
            lines.append("    id = Column(Integer, primary_key=True, autoincrement=True, index=True)")
            
        for col in custom_columns:
            col_type_str = col["type"]
            if col["length"]:
                col_type_str += f"({col['length']})"
                
            col_args = [col_type_str]
            if not col["nullable"]:
                col_args.append("nullable=False")
            if col["unique"]:
                col_args.append("unique=True")
                
            if col["default"]:
                def_val = col["default"]
                if col["type"] == "Boolean":
                    def_val = "True" if def_val.lower() in ("true", "1", "yes") else "False"
                elif col["type"] in ("Integer", "Float"):
                    # Check if numeric
                    pass
                else:
                    def_val = f"'{def_val}'"
                col_args.append(f"default={def_val}")
                
            col_str = f"    {col['name']} = Column({', '.join(col_args)})"
            lines.append(col_str)
            
        if has_active:
            lines.append("    active = Column(Integer, nullable=False, default=1)")
            
        if has_created:
            lines.append("    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())")
            
        if has_updated:
            lines.append("    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())")
            
        model_content = "\n".join(lines) + "\n"
        
    # Write to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(model_content)
        
    typer.echo("Model created successfully!")
    typer.echo(f"Location: app/models/{filename}")
    typer.echo(f"Model name: {model_name}")
    typer.echo(f"Table name: {table_name}")
    
    typer.echo("\nNext steps:")
    typer.echo(f"   1. Edit app/models/{filename} to review your custom columns")
    typer.echo(f"   2. Run migrations: python -m cli.migrations")


@app.command()
def list_models():
    """List all existing models in app/models/"""
    models_dir = Path("app/models")
    
    if not models_dir.exists():
        typer.echo("❌ Models directory not found!")
        raise typer.Exit(code=1)
    
    model_files = [f for f in models_dir.glob("*.py") if f.name != "__init__.py"]
    
    if not model_files:
        typer.echo("📭 No models found in app/models/")
    else:
        typer.echo(f"📚 Found {len(model_files)} model(s):\n")
        for model_file in sorted(model_files):
            typer.echo(f"   • {model_file.name}")


if __name__ == "__main__":
    app()
