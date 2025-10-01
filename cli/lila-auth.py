import typer
from pathlib import Path
import os

app = typer.Typer()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _create_templates():
    templates_dir = Path("templates/html/auth")
    templates_dir.mkdir(parents=True, exist_ok=True)

    templates = {
        "login.html": login_template_content,
        "register.html": register_template_content,
        "forgot-password.html": forgot_password_template_content,
    }

    for filename, content in templates.items():
        file_path = templates_dir / filename
        file_path.write_text(content)
        print(f" Template created: {file_path}")

    print("\n Auth templates generated successfully")

def _create_routes():
    main_file = os.path.join(project_root, "main.py")
    marker = "auth_marker"

    if not os.path.exists(main_file):
        typer.echo("main.py not found.")
        raise typer.Exit(code=1)

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if "from app.routes.auth import auth_routes" in content:
        typer.echo("Auth routes already added.")
        return

    replace_text = f'''# {marker}
from app.routes.auth import auth_routes
import itertools
all_routes = list(itertools.chain(routes, api_routes, auth_routes))'''

    new_content = content.replace(f"# {marker}", replace_text)

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(new_content)

    typer.echo("Auth routes added to main.py.")

def _create_auth_file():
    auth_file_path = os.path.join(project_root, "app/routes/auth.py")
    with open(auth_file_path, "w", encoding="utf-8") as file:
        file.write(auth_file_content)
    typer.echo("Auth file created/updated successfully.")

def _overwrite_user_model():
    user_model_path = os.path.join(project_root, "app/models/user.py")
    with open(user_model_path, "w", encoding="utf-8") as file:
        file.write(user_model_content)
    typer.echo("User model overwritten successfully.")


@app.command()
def main(template: str = "True", route: str = "True"):
    if template.lower() == "true":
        _create_templates()

    if route.lower() == "true":
        _create_routes()
        _create_auth_file()
        _overwrite_user_model()

auth_file_content = '''from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.templates import render
from lila.core.session import Session
from app.models.user import User
from app.helpers.helpers import translate_
from pydantic import BaseModel, EmailStr, constr, Field

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class RegisterModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: constr(min_length=8, max_length=20)
    password_2: constr(min_length=8, max_length=20)

    def validate_passwords(self, request):
        if self.password != self.password_2:
            msg = translate_("Passwords not match", request)
            return JSONResponse({"success": False, "msg": msg}, status_code=400)
        return None

router = Router()

@router.get("/login")
async def login_page(request):
    return render(request=request, template="auth/login")

@router.get("/register")
async def register_page(request):
    return render(request=request, template="auth/register")

@router.get("/forgot-password")
async def forgot_password_page(request):
    return render(request=request, template="auth/forgot-password")


@router.post("/login")
async def login(request):
    try:
        data = await request.json()
        login_data = LoginModel(**data)
    except Exception as e:
        return JSONResponse({"msg": translate_("Invalid data", request)}, status_code=400)

    check_login = User.check_login(email=login_data.email)
    if check_login:
        user = check_login
        password_db = user["password"]
        if User.validate_password(password_db, login_data.password):
            response = JSONResponse({"success": True, "msg": translate_("Login successful", request)})
            user_token = user['token']
            token = {"token": user_token}
            Session.setSession(new_val=token, name_cookie="auth", response=response)
            return response

    return JSONResponse({"success": False, "msg": translate_("Incorrect email or password", request)}, status_code=401)


@router.post("/register")
async def register(request):
    try:
        data = await request.json()
        model = RegisterModel(**data)
        validate = model.validate_passwords(request=request)
        if isinstance(validate, JSONResponse):
            return validate
    except Exception as e:
        return JSONResponse({"success": False, "msg": translate_("Error creating account, check your entered data", request)}, status_code=400)

    if User.check_for_email(email=model.email):
        return JSONResponse({"success": False, "msg": translate_("Email already exists", request)}, status_code=400)

    result = User.insert({"name": model.name, "email": model.email, "password": model.password})
    if result:
        return JSONResponse({"success": True, "msg": translate_("User created successfully", request)})
    
    return JSONResponse({"success": False, "msg": translate_("Error creating account", request)}, status_code=500)


@router.post("/forgot-password")
async def forgot_password(request):
    data = await request.json()
    email = data.get("email")

    if User.check_for_email(email=email):
        # In a real application, you would generate a unique token, save it, 
        # and send an email with the reset link.
        print(f"Password reset link for {email}: /reset-password?token=some_token")

    return JSONResponse({"msg": translate_("If an account with that email exists, a password reset link has been sent.", request)})

auth_routes = router.get_routes()
'''

user_model_content = '''from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from core.database import Base
from app.connections import connection
import secrets
import hashlib
import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=50), nullable=False)
    email = Column(String(length=50), unique=True)
    password = Column(String(length=150), nullable=False)
    token = Column(String(length=150), nullable=True)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # English : Example of how to use SQLAlchemy to make queries to the database
    # Español : Ejemplo de como poder utilizar SQLAlchemy para hacer consultas a la base de datos
    @staticmethod
    def get_all(select: str = "id,email,name,created_at", limit: int = 1000) -> list:
        query = f"SELECT {select}  FROM users WHERE active = 1 LIMIT {limit}"
        result = connection.query(query=query, return_rows=True)
        return result

    # English : Example of how to use SQLAlchemy to make queries to the database
    # Español : Ejemplo de como poder utilizar SQLAlchemy para hacer consultas a la base de datos
    @staticmethod
    def get_by_id(id: int, select="id,email,name") -> dict:
        query = f"SELECT {select}  FROM users WHERE id = :id AND active = 1 LIMIT 1"
        params = {"id": id}
        row = connection.query(query=query, params=params, return_row=True)
        return row

    # English: Example using ORM abstraction in SQLAlchemy
    # Español : Ejemplo usando abstracción de ORM en SQLAlchemy
    @classmethod
    def get_all_orm(cls, db: Session, limit: int = 1000):
        result = db.query(cls).filter(cls.active == 1).limit(limit).all()
        return result

    @classmethod
    def hash_password(cls, password: str):
        return ph.hash(password)

    @staticmethod
    def validate_password(stored_hash: str, password: str) -> bool:
        try:
            return ph.verify(stored_hash, password)
        except VerifyMismatchError:
            return False

    @classmethod
    def insert(cls, params: dict) -> bool | dict:
        params["token"] = hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()
        params["active"] = 1
        params["password"] = cls.hash_password(params["password"])
        params["created_at"] = datetime.datetime.now()
        placeholders = ", ".join(f":{key}" for key in params.keys())
        columns = ", ".join(params.keys())

        query = f"INSERT INTO users ({columns}) VALUES ({placeholders})"
        result = connection.query(query=query, params=params)
        if result and result.lastrowid:
            return {"token": params["token"], "id": result.lastrowid}
        return False

    @staticmethod
    def check_for_email(email: str) -> bool:
        query = f"SELECT id FROM users WHERE email = :email LIMIT 1"
        params = {"email": email}
        result = connection.query(query=query, params=params, return_row=True)
        return result is not None

    @staticmethod
    def check_login(email: str) -> dict | None:
        query = f"SELECT id, token, password FROM users WHERE email = :email AND active = 1 LIMIT 1"
        params = {"email": email}
        return connection.query(query=query, params=params, return_row=True)

# English : Example of how to use the class to make queries to the database
# Español : Ejemplo de como usar la clase para realizar consultas a la base de datos
# users = User.get_all()
# user = User.get_by_id(1)
'''

login_template_content = '''<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/public/lila.css">
</head>
<body>
    <main class="flex justify-center items-center h-screen">
        <div class="w-mx-500-px p-4 shadow">
            <h3 class=" text-center mb-4">{{translate['Login']}}</h3>

            <form id="login-form">
                <div class="mb-4">
                    <label for="email" >Email</label>
                    <input type="email" id="email" name="email" class="w-full" required>
                </div>
                <div class="mb-4">
                    <label for="password" >{{translate['password']}}</label>
                    <input type="password" id="password" name="password" class="w-full" required>
                </div>
                <div class="flex items-center justify-between mb-4">
                    <a href="/forgot-password" class="underline">{{translate['forgot your password']}}</a>
                </div>
                <button type="submit" class="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600">{{translate['Login']}}</button>
                 <div class="mt-4 text-center">
                    <p> <a href="/register" class="underline">{{translate['create account']}}</a></p>
                </div>
                <p id="error-message" class="text-red-500 mt-2 text-center"></p>
            </form>
        </div>
    </main>
    <script>
        document.getElementById('login-form').addEventListener('submit', async function(event) {
            event.preventDefault();

            const form = event.target;
            const formData = new FormData(form);
            const errorMessage = document.getElementById('error-message');

            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    body: JSON.stringify(Object.fromEntries(formData)),
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    window.location.replace('/');
                } else {
                    errorMessage.textContent = result.msg  || 'An unknown error occurred.';
                }
            } catch (error) {
                errorMessage.textContent = 'Failed to connect to the server.';
            }
        });
    </script>
</body>
</html>
'''

register_template_content = '''<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/public/lila.css">
</head>
<body>
    <main class="flex justify-center items-center h-screen">
        <div class="w-mx-500-px p-4 shadow">
            <h3 class=" text-center mb-4">{{translate['create account']}}</h3>
            <form id="register-form">
                <div class="mb-4">
                    <label for="name" >{{translate['name']}}</label>
                    <input type="text" id="name" name="name" class="w-full" required>
                </div>
                <div class="mb-4">
                    <label for="email" >Email</label>
                    <input type="email" id="email" name="email" class="w-full" required>
                </div>
                <div class="mb-4">
                    <label for="password" >{{translate['password']}}</label>
                    <input type="password" id="password" name="password" class="w-full" required>
                </div>
                 <div class="mb-4">
                    <label for="password_2" >{{translate['confirm_password']}}</label>
                    <input type="password" id="password_2" name="password_2" class="w-full" required>
                </div>
                <button type="submit" class="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600">{{translate['register']}}</button>
                <div class="mt-4 text-center">
                    <p>{{translate['Already have an account?']}} <a href="/login" class="underline">{{translate['login']}}</a></p>
                </div>
                <p id="error-message" class="text-red-500 mt-2 text-center"></p>
            </form>
        </div>
    </main>
    <script>
        document.getElementById('register-form').addEventListener('submit', async function(event) {
            event.preventDefault();

            const form = event.target;
            const formData = new FormData(form);
            const errorMessage = document.getElementById('error-message');

            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    body: JSON.stringify(Object.fromEntries(formData)),
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    window.location.replace('/login');
                } else {
                    errorMessage.textContent = result.msg  || 'Failed to register.';
                }
            } catch (error) {
                errorMessage.textContent = 'Failed to connect to the server.';
            }
        });
    </script>
</body>
</html>
'''

forgot_password_template_content = '''<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/public/lila.css">
</head>
<body>
    <main class="flex justify-center items-center h-screen">
        <div class="w-mx-500-px p-4 shadow">
            <h3 class=" text-center mb-4">{{translate['Recover password']}}</h3>
            <p>
                <small>
                    {{translate['Forgot your password? No problem. Just let us know your email address and we will email you a password reset link that will allow you to choose a new one']}}
                </small>
            </p>
            <form id="forgot-password-form">
                <div class="mb-4">
                    <label for="email" >Email</label>
                    <input type="email" id="email" name="email" class="w-full" required>
                </div>
                <button type="submit" class="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600">{{translate['Send']}}</button>
                <div class="mt-4 text-center">
                    <p><a href="/login" class="underline">{{translate['login']}}</a></p>
                </div>
                <p id="message" class="mt-2 text-center"></p>
            </form>
        </div>
    </main>
    <script>
        document.getElementById('forgot-password-form').addEventListener('submit', async function(event) {
            event.preventDefault();

            const form = event.target;
            const formData = new FormData(form);
            const message = document.getElementById('message');

            try {
                const response = await fetch('/forgot-password', {
                    method: 'POST',
                    body: JSON.stringify(Object.fromEntries(formData)),
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const result = await response.json();

                if (response.ok) {
                    message.className = 'text-green-500 mt-2 text-center';
                    message.textContent = result.msg  || 'If an account exists, a reset link has been sent.';
                } else {
                    message.className = 'text-red-500 mt-2 text-center';
                    message.textContent = result.msg  || 'An error occurred.';
                }
            } catch (error) {
                message.className = 'text-red-500 mt-2 text-center';
                message.textContent = 'Failed to connect to the server.';
            }
        });
    </script>
</body>
</html>
'''

if __name__ == "__main__":
    app()
