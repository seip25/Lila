import typer
import os
from pathlib import Path

app = typer.Typer()

# Template for model generation
MODEL_TEMPLATE = '''from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import Session, load_only
from core.database import Base
from app.connections import connection
import secrets
import hashlib
import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

class {model_name}(Base):
    """
    {model_name} Model
    
    Example column types you can use:
    - Integer: Column(Integer, primary_key=True, autoincrement=True)
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
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=100), nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Example of additional columns (uncomment and modify as needed):
    # description = Column(String(length=255), nullable=True)
    # email = Column(String(length=100), unique=True)
    # price = Column(Float, nullable=True)
    # is_available = Column(Integer, default=1)
    # updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    @classmethod
    def get_all(cls, select: str = "id,name", limit: int = 1000):
        """
        Get all active records with selected columns
        
        Args:
            select: Comma-separated column names to select
            limit: Maximum number of records to return
            
        Returns:
            List of dictionaries with selected columns
        """
        db = connection.get_session()
        try:
            column_names = [c.strip() for c in select.split(',')]
            columns_to_load = [getattr(cls, c) for c in column_names]
            result = db.query(cls).options(load_only(*columns_to_load)).filter(cls.active == 1).limit(limit).all()
            items = [
                {{col: getattr(row, col) for col in column_names}}
                for row in result
            ]
            return items
        finally:
            db.close()

    @classmethod
    def get_by_id(cls, db: Session, id: int):
        """
        Get a single record by ID
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            Model instance or None
        """
        return db.query(cls).filter(cls.id == id, cls.active == 1).first()

    @classmethod
    def insert(cls, db: Session, params: dict) -> '{model_name}':
        """
        Insert a new record
        
        Args:
            db: Database session
            params: Dictionary with column values
            
        Returns:
            Created model instance
        """
        record = cls(
            name=params.get("name"),
            active=params.get("active", 1),
            created_at=datetime.datetime.now()
            # Add more fields as needed
        )
        db.add(record)
        return record

    @classmethod
    def update(cls, db: Session, id: int, params: dict) -> bool:
        """
        Update a record by ID
        
        Args:
            db: Database session
            id: Record ID
            params: Dictionary with column values to update
            
        Returns:
            True if updated, False otherwise
        """
        record = cls.get_by_id(db, id)
        if record:
            for key, value in params.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            return True
        return False

    @classmethod
    def delete(cls, db: Session, id: int) -> bool:
        """
        Soft delete a record by ID (sets active to 0)
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            True if deleted, False otherwise
        """
        record = cls.get_by_id(db, id)
        if record:
            record.active = 0
            return True
        return False

    @staticmethod
    def get_all_without_orm(select: str = "id,name,created_at", limit: int = 1000) -> list:
        """
        Get all records using raw SQL (without ORM)
        
        Args:
            select: Comma-separated column names
            limit: Maximum number of records
            
        Returns:
            List of dictionaries
        """
        return connection.query(
            query=f"SELECT {{select}} FROM {table_name} WHERE active = 1 LIMIT {{limit}}", 
            return_rows=True
        )

    @staticmethod
    def get_by_id_without_orm(id: int, select: str = "id,name") -> dict:
        """
        Get a single record by ID using raw SQL (without ORM)
        
        Args:
            id: Record ID
            select: Comma-separated column names
            
        Returns:
            Dictionary with record data or None
        """
        params = {{"id": id}}
        return connection.query(
            query=f"SELECT {{select}} FROM {table_name} WHERE id = :id AND active = 1 LIMIT 1", 
            params=params, 
            return_row=True
        )
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


def _add_model_import_to_migrations(model_name: str, filename: str) -> None:
    """
    Add model import to cli/migrations.py using model_marker
    
    Args:
        model_name: Name of the model class
        filename: Name of the model file (without .py)
    """
    migrations_file = Path("cli/migrations.py")
    
    if not migrations_file.exists():
        typer.echo("⚠️ Warning: cli/migrations.py not found. Skipping auto-import.")
        return
    
    with open(migrations_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    import_statement = f"from app.models.{filename.replace('.py', '')} import {model_name}"
    
    # Check if already imported
    if import_statement in content:
        typer.echo(f"ℹ️ Model {model_name} already imported in migrations.py")
        return
    
    # Find marker and add import
    marker = "# model_marker"
    if marker not in content:
        typer.echo(f"⚠️ Warning: Marker '{marker}' not found in migrations.py. Please add import manually:")
        typer.echo(f"   {import_statement}")
        return
    
    # Add import before marker
    new_content = content.replace(marker, f"{import_statement}\n{marker}")
    
    with open(migrations_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    typer.echo(f"✅ Model imported in cli/migrations.py")


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
    
    # Auto-import model in migrations.py
    _add_model_import_to_migrations(model_name, filename)
    
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
