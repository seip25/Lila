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
        file_path.write_text(content,encoding="utf-8")
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

def _create_login_attempt_model():
    model_path = os.path.join(project_root, "app/models/login_attempt.py")
    with open(model_path, "w", encoding="utf-8") as file:
        file.write(login_attempt_model_content)
    typer.echo("LoginAttempt model created successfully.")

@app.command()
def main(template: str = "True", route: str = "True"):
    if template.lower() == "true":
        _create_templates()

    if route.lower() == "true":
        _create_routes()
        _create_auth_file()
        _overwrite_user_model()
        _create_login_attempt_model()

auth_file_content = '''from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.templates import render
from lila.core.session import Session
from app.models.user import User
from app.models.login_attempt import LoginAttempt
from app.connections import connection
from app.helpers.helpers import translate_
from pydantic import BaseModel, EmailStr,  Field
import datetime

class RegisterModel(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str= Field(...,min_length=8, max_length=20)
    password_2: str =Field(...,min_length=8, max_length=20)

class LoginModel(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)

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

    db = connection.get_session()
    try:
        login_attempt = db.query(LoginAttempt).filter_by(email=login_data.email).first()
        if login_attempt and login_attempt.is_locked():
            return JSONResponse({"msg": translate_("Account locked. Try again in 5 minutes.", request)}, status_code=429)

        user = User.check_login(db, email=login_data.email)
        if user and User.validate_password(user.password, login_data.password):
            if login_attempt:
                login_attempt.attempts = 0
                login_attempt.locked_at = None
                db.commit()

            response = JSONResponse({"success": True, "msg": translate_("Login successful", request)})
            token = {"token": user.token}
            Session.setSession(new_val=token, name_cookie="auth", response=response)
            return response
        else:
            if not login_attempt:
                login_attempt = LoginAttempt(email=login_data.email)
                db.add(login_attempt)
            
            login_attempt.attempts += 1
            if login_attempt.attempts >= 5:
                login_attempt.locked_at = datetime.datetime.utcnow()
            
            db.commit()
            return JSONResponse({"success": False, "msg": translate_("Incorrect email or password", request)}, status_code=401)
    finally:
        db.close()

@router.post("/register")
async def register(request):
    db = connection.get_session()
    try:
        data = await request.json()
        model = RegisterModel(**data)
        validate = model.validate_passwords(request=request)
        if isinstance(validate, JSONResponse):
            return validate
        
        if User.check_for_email(db, email=model.email):
            return JSONResponse({"success": False, "msg": translate_("Email already exists", request)}, status_code=400)

        user = User.insert(db, {"name": model.name, "email": model.email, "password": model.password})
        db.commit() 
        if user:
            return JSONResponse({"success": True, "msg": translate_("User created successfully", request)})
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "msg": translate_("Error creating account, check your entered data", request)}, status_code=400)
    finally:
        db.close()
    
    return JSONResponse({"success": False, "msg": translate_("Error creating account", request)}, status_code=500)

@router.post("/forgot-password")
async def forgot_password(request):
    data = await request.json()
    email = data.get("email")
    db = connection.get_session()
    try:
        if User.check_for_email(db, email=email):
            print(f"Password reset link for {email}: /reset-password?token=some_secure_token")
    finally:
        db.close()

    return JSONResponse({"msg": translate_("If an account with that email exists, a password reset link has been sent.", request)})

auth_routes = router.get_routes()
'''

user_model_content = '''from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import Session, load_only
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

    @classmethod
    def get_users(cls, db: Session, select: str = "id,email,name", limit: int = 1000):
        columns_to_load = [c.strip() for c in select.split(',')]
        return db.query(cls).options(load_only(*columns_to_load)).filter(cls.active == 1).limit(limit).all()

    @classmethod
    def get_by_id(cls, db: Session, id: int):
        return db.query(cls).filter(cls.id == id, cls.active == 1).first()

    @classmethod
    def check_login(cls, db: Session, email: str):
        return db.query(cls).filter(cls.email == email, cls.active == 1).first()

    @classmethod
    def check_for_email(cls, db: Session, email: str) -> bool:
        return db.query(cls).filter(cls.email == email).first() is not None

    @classmethod
    def insert(cls, db: Session, params: dict) -> 'User':
        hashed_password = cls.hash_password(params["password"])
        user = cls(
            name=params["name"],
            email=params["email"],
            password=hashed_password,
            token=hashlib.sha256(secrets.token_hex(16).encode()).hexdigest(),
            active=1,
            created_at=datetime.datetime.now()
        )
        db.add(user)
        return user

    @staticmethod
    def hash_password(password: str) -> str:
        return ph.hash(password)

    @staticmethod
    def validate_password(stored_hash: str, password: str) -> bool:
        try:
            return ph.verify(stored_hash, password)
        except VerifyMismatchError:
            return False

    @classmethod
    def get_all(select: str = "id,email,name", limit: int = 1000) -> list:
        query = f"SELECT {select}  FROM users WHERE active =1  LIMIT {limit}"
        result = connection.query(query=query,return_rows=True)
        return result 
    @staticmethod
    def get_all_without_orm(select: str = "id,email,name,created_at", limit: int = 1000) -> list:
        return connection.query(query=f"SELECT {select}  FROM users WHERE active = 1 LIMIT {limit}", return_rows=True)

    @staticmethod
    def get_by_id_without_orm(id: int, select="id,email,name") -> dict:
        params = {"id": id}
        return connection.query(query=f"SELECT {select}  FROM users WHERE id = :id AND active = 1 LIMIT 1", params=params, return_row=True)
'''

login_attempt_model_content = '''from sqlalchemy import Column, Integer, String, DateTime
from core.database import Base
import datetime

class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    attempts = Column(Integer, default=0)
    locked_at = Column(DateTime, nullable=True)

    def is_locked(self):
        if not self.locked_at:
            return False
        return datetime.datetime.utcnow() < self.locked_at + datetime.timedelta(minutes=5)
'''

login_template_content = '''<!DOCTYPE html>
<html lang="{{lang}}" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/public/css/lila.css">
</head>
<body>
    <main class="flex justify-center items-center    container">
        <article class="w-mx-500-px">
            <h3 class=" text-center mb-4">{{translate['login']}}</h3>

            <form id="login-form">
                <div class="mb-4">
                    <label for="email" >Email</label>
                    <input type="email" id="email" name="email" class="w-full" required>
                </div>
                <div class="mb-4">
                    <label for="password" >{{translate['password']}}</label>
                    <input type="password" id="password" name="password" class="w-full" required>
                </div>
                <div class="flex items-center justify-center mb-4">
                    <a href="/forgot-password" class="underline">{{translate['forgot your password']}}</a>
                </div>
                <button type="submit" class="w-full">{{translate['login']}}</button>
                 <div class="mt-4 text-center">
                    <p> <a href="/register" class="underline">{{translate['create account']}}</a></p>
                </div>
                <p id="error-message" class="text-red-500 mt-2 text-center"></p>
            </form>
        </article>
        
    </main>
    <footer>
             <div class="container mx-auto px-4 flex justify-between items-center">
        <a
          href="/set-language/es"
          class="text-secondary underline"
        >
          Español (Esp)
        </a>
        <a
          href="/set-language/en"
          class="text-secondary underline"
        >
          English (US)
        </a>
      </div>
        </footer>
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
                    headers: {'Content-Type': 'application/json'}
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
<html lang="{{lang}}" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/public/css/lila.css">
</head>
<body>
    <main class="flex justify-center items-center    container">
        <article class="w-mx-500-px">
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
                <button type="submit" class="w-full">{{translate['register']}}</button>
                <div class="mt-4 text-center">
                    <p>{{translate['Already have an account?']}} <a href="/login" class="underline">{{translate['login']}}</a></p>
                </div>
                <p id="error-message" class="text-red-500 mt-2 text-center"></p>
            </form>
        </article>
        
    </main>
     <footer>
             <div class="container mx-auto px-4 flex justify-between items-center">
        <a
          href="/set-language/es"
          class="text-secondary underline"
        >
          Español (Esp)
        </a>
        <a
          href="/set-language/en"
          class="text-secondary underline"
        >
          English (US)
        </a>
      </div>
        </footer>
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
                    headers: {'Content-Type': 'application/json'}
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
<html lang="{{lang}}" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="/public/css/lila.css">
</head>
<body>
    <main class="flex justify-center items-center    container">
        <article class="w-mx-500-px">
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
                <button type="submit" class="w-full">{{translate['Send']}}</button>
                <div class="mt-4 text-center">
                    <p><a href="/login" class="underline">{{translate['login']}}</a></p>
                </div>
                <p id="message" class="mt-2 text-center"></p>
            </form>
        </article>
        
    </main>
     <footer>
             <div class="container mx-auto px-4 flex justify-between items-center">
        <a
          href="/set-language/es"
          class="text-secondary underline"
        >
          Español (Esp)
        </a>
        <a
          href="/set-language/en"
          class="text-secondary underline"
        >
          English (US)
        </a>
      </div>
        </footer>
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
                    headers: {'Content-Type': 'application/json'}
                });
                const result = await response.json();
                if (response.ok) {
                    message.className = 'text-green-500 mt-2 text-center';
                    message.textContent = result.msg;
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
