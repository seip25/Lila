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
from core.base_model import BaseModel

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
    name: str = typer.Option("Model", "--name", "-n", help="Name of the model (e.g., User, Product, Category)"),
    table: str = typer.Option(None, "--table", "-t", help="Table name (defaults to snake_case of model name)")
):
    """
    Create a new SQLAlchemy model skeleton
    
    Examples:
        python -m cli.model create --name User
        python -m cli.model create --name Product --table products
        python -m cli.model create -n Category
    
    The generated model will include:
    - Basic CRUD methods (get_all, get_by_id, insert, update, delete)
    - ORM and raw SQL query examples
    - Common column types as comments for reference
    - Soft delete functionality (active column)
    """
    # Capitalize first letter of model name
    model_name = capitalize_first(name)
    
    # Generate table name (snake_case by default)
    if table is None:
        table_name = to_snake_case(model_name) + "s"  # Pluralize by adding 's'
    else:
        table_name = table
    
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
    model_content = MODEL_TEMPLATE.format(
        model_name=model_name,
        table_name=table_name
    )
    
    # Write to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(model_content)
    
    typer.echo(f"✅ Model created successfully!")
    typer.echo(f"📁 Location: app/models/{filename}")
    typer.echo(f"📝 Model name: {model_name}")
    typer.echo(f"🗄️  Table name: {table_name}")
    

    
    typer.echo(f"\n💡 Next steps:")
    typer.echo(f"   1. Edit app/models/{filename} to add your custom columns")
    typer.echo(f"   2. Run migrations: python -m cli.migrations migrate")


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
