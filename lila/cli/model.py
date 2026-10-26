import sys
import os
import re
from pathlib import Path
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Generate SQLAlchemy ActiveRecord models for Lila.")

MODEL_TEMPLATE = '''from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from lila.core.base_model import BaseModel

class {model_name}(BaseModel):
    """
    {model_name} Model - Inherits standard CRUD methods from BaseModel.
    """
    __tablename__ = "{table_name}"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(length=100), nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
'''

def capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]

def to_snake_case(text: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

@app.command()
def create(
    name: str = typer.Option(None, "--name", "-n", help="Name of the model (e.g., Product)"),
    table: str = typer.Option(None, "--table", "-t", help="Table name (defaults to pluralized snake_case)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Force interactive mode")
):
    """
    Create a new SQLAlchemy model file in app/models/.
    """
    is_interactive = interactive or (name is None)

    if is_interactive:
        typer.echo("🛠️  Lila Interactive Model Builder\n")
        if not name:
            name = typer.prompt("Model name (e.g. Product, Order)").strip()
            if not name:
                typer.secho("❌ Model name cannot be empty.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    model_name = capitalize_first(name)
    default_table = to_snake_case(model_name) + "s"
    table_name = table or default_table

    models_dir = Path("app/models")
    models_dir.mkdir(parents=True, exist_ok=True)

    filename = to_snake_case(model_name) + ".py"
    file_path = models_dir / filename

    if file_path.exists():
        overwrite = typer.confirm(f"File {filename} already exists. Overwrite?", default=False)
        if not overwrite:
            typer.echo("Operation cancelled.")
            raise typer.Exit()

    content = MODEL_TEMPLATE.format(model_name=model_name, table_name=table_name)
    file_path.write_text(content, encoding="utf-8")

    typer.secho(f"✅ Model '{model_name}' created at app/models/{filename}", fg=typer.colors.GREEN)
    typer.echo("➡️  Run 'lila migrate' or 'lila-migrations' to sync database tables.")

@app.command()
def list_models():
    """List all models in app/models/"""
    models_dir = Path("app/models")
    if not models_dir.exists():
        typer.echo("Models directory not found.")
        return
    model_files = [f for f in models_dir.glob("*.py") if f.name != "__init__.py"]
    typer.echo(f"📚 Models found ({len(model_files)}):")
    for f in sorted(model_files):
        typer.echo(f"   • {f.name}")

def main():
    app()

if __name__ == "__main__":
    main()
