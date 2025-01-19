# Lila

Lila is a minimalist Python framework based on Starlette and Pydantic. Designed for developers seeking simplicity, flexibility, and robustness, it enables efficient and customizable web or API application development. Its modular structure and support for advanced configurations make it suitable for both beginners and experienced developers.

## Key Features

- **Simplicity**: Intuitive and minimalist design.
- **Flexibility**: Support for multiple databases (MySQL, SQLite) and adaptation to various environments.
- **Speed**: Built on Starlette, known for its high performance in asynchronous applications.
- **Robust Validation**: Uses Pydantic to ensure consistent data.
- **Editable and Configurable**: Ready to use but fully customizable.
- **Multi-language Support**: Integrated support for multilingual applications.
- **Compatibility**: Can be used with frameworks like Next.js, Remix, and others.
- **Easy Migrations**: Quick and straightforward database configuration.
- **Jinja2 and HTML Sessions**: Ready-to-use with dynamic templates and session handling, while remaining compatible with React, Angular, Vue, and other frontend frameworks.

---

# Lila (Español)

Lila es un framework minimalista de Python basado en Starlette y Pydantic. Diseñado para desarrolladores que buscan simplicidad, flexibilidad y robustez, permite crear aplicaciones web o APIs de manera eficiente y personalizable. Su estructura modular y soporte para configuraciones avanzadas lo hacen ideal tanto para principiantes como para desarrolladores experimentados.

## Características principales

- **Simplicidad**: Diseño intuitivo y minimalista.
- **Flexibilidad**: Soporte para múltiples bases de datos (MySQL, SQLite) y adaptación a diversos entornos.
- **Rapidez**: Basado en Starlette, conocido por su alto rendimiento en aplicaciones asíncronas.
- **Validación robusta**: Uso de Pydantic para garantizar datos consistentes.
- **Editable y configurable**: Todo está listo para usar, pero también es completamente personalizable.
- **Multi-idioma**: Soporte integrado para aplicaciones multilingües.
- **Compatibilidad**: Puede ser utilizado con frameworks como Next.js, Remix js, entre otros.
- **Migraciones sencillas**: Configuración rápida y fácil para bases de datos.
- **Jinja2 y sesiones HTML**: Listo para usar con plantillas dinámicas y manejo de sesiones, pero compatible con React, Angular, Vue, entre otros frameworks frontend.

---

## Installation (Instalación)

### English

1. Clone the repository:

   ```bash
   git clone https://github.com/seip25/Lila.git
   ```

2. Navigate to the project directory:

   ```bash
   cd Lila
   ```

3. Create a virtual environment and activate it:

   ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

4. Install dependencies:

   ```bash
   pip install -r requeriments.txt
   ```

5. Run application:

   ```bash
   python3 app.py #Or python app.py
   ```

### Español

1. Clona el repositorio:

   ```bash
   git clone https://github.com/seip25/Lila.git
   ```

2. Navega al directorio del proyecto:

   ```bash
   cd Lila
   ```

3. Crea un entorno virtual y actívalo:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Windows usa `venv\Scripts\activate`
   ```

4. Instala las dependencias:

   ```bash
   pip install -r requeriments.txt
   ```

5. Ejecutar la aplicación:

   ```bash
   python3 app.py #O python app.py
   ```

---
# API Documentation (Swagger)

- **Swagger UI and OpenAPI Documentation / Interfaz Swagger y Documentación OpenAPI**
```python
    router.swagger_ui()
    router.openapi_json()

```
- These two functions enable automatic generation of interactive API documentation via Swagger. You can access the documentation by navigating to /docs in your browser. /
Estas dos funciones habilitan la generación automática de documentación interactiva de la API a través de Swagger. Puedes acceder a la documentación navegando a /docs en tu navegador.

-Documentation is automatically generated after calling the 2 methods of the "Router" class, for all routes with their corresponding methods, as shown in the code.

If you use a Pydantic Model, pass it as a parameter to the "route" function, as "model", as detailed below in the code. 
/La documentación se genera automáticamente luego de llamar a los 2 métodos de la clase "Router", para todas las rutas con sus métodos correspondientes, como se muestra en el código.

Si utiliza un Modelo Pydantic, páselo como parámetro a la función "ruta", como "modelo", como se detalla a continuación en el código.
```python
class LoginModel(BaseModel):
    email : EmailStr
    password: str
    
@router.route(path='/login',methods=['POST'],model=LoginModel)
async def login(request:Request):
    """Login function"""  
    msg= translate(file_name='guest',request=request)
    msg_error=msg['Incorrect email or password']
    body = await request.json()
    try:
        input=LoginModel(**body)
    except Exception as e:
        return JSONResponse({"success":False,"msg":f"Invalid JSON Body: {e}"},status_code=400)
    email = input.email
    password = input.password 
    response=JSONResponse({"success":False,"email":email,"password":password,"msg":msg_error})
    return response


```
---

## Project Structure (Estructura del proyecto)

### `app.py`

- **Purpose / Propósito**: Configure and start the application / Configurar y arrancar la aplicación.
- **Use / Uso**: Defines main routes and middlewares / Define las rutas y los middlewares principales.

### `core/`

- **Global configuration / Configuración global**: Includes application settings, such as environment variable handling and general configurations / Incluye la configuración de la aplicación, como el manejo de variables de entorno y configuraciones generales.
- **Utilities / Utilidades**: Shared functions for use in different modules / Funciones compartidas para uso en diferentes módulos.

### `database/`

- **Connection / Conexión**: Configures and manages MySQL or SQLite connections / Configura y gestiona las conexiones con MySQL o SQLite.
- **Models / Modelos**: The models module defines the data models used to interact with the database. These models represent your database tables and can be used to perform CRUD (Create, Read, Update, Delete) operations. / El módulo models define los modelos de datos utilizados para interactuar con la base de datos. Estos modelos representan las tablas de la base de datos y pueden utilizarse para realizar operaciones CRUD (Crear, Leer, Actualizar, Eliminar),etc.
- **Configurable ORMs / ORMs configurables**: This framework allows you to integrate easily with popular ORMs such as SQLModel or SQLAlchemy. You can configure it to suit your needs and use either of them for managing database operations./ Este framework permite integrar fácilmente ORMs populares como SQLModel o SQLAlchemy. Puedes configurarlo para adaptarse a tus necesidades y utilizar cualquiera de ellos para gestionar las operaciones en la base de datos.


- **Migrations /migraciones**
- Example of Migration Script / Ejemplo de Script de Migración
- The script defines a migration for the users table and a User model. The migration script creates the users table with columns such as id, name, email, etc. It also includes a migrate function that performs the migration using the configured connection. The refresh parameter can be set to True to drop and recreate the tables from scratch./
El script define una migración para la tabla users y un modelo User. El script de migración crea la tabla users con columnas como id, name, email, etc. También incluye una función migrate que realiza la migración utilizando la conexión configurada. El parámetro refresh puede configurarse como True para eliminar y recrear las tablas desde cero.



migrations.py

```python
from sqlalchemy import Table, Column, Integer, String, TIMESTAMP
from database.connections import connection
from core.database import Base


# Example of creating migrations for 'users' table
table_users = Table(
    'users', connection.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('name', String(length=50), nullable=False),
    Column('email', String(length=50), unique=True),
    Column('password', String(length=150), nullable=False),
    Column('token', String(length=150), nullable=False),
    Column('active', Integer, default=1, nullable=False),
    Column('created_at', TIMESTAMP), 
)

# Model for 'users'
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=50), nullable=False)
    email = Column(String(length=50), unique=True)
    password = Column(String(length=150), nullable=False)
    token = Column(String(length=150), nullable=False)
    active = Column(Integer, default=1, nullable=False)
    created_at = Column(TIMESTAMP)

async def migrate(connection, refresh: bool = False) -> bool:
    try:
        if refresh:
            connection.metadata.drop_all(connection.engine)  # Drops all tables
        connection.prepare_migrate([table_users])  # Prepare migration for 'users' table
        connection.migrate()  # Perform migration for tables
        connection.migrate(use_base=True)  # Perform migration for models
        print("Migrations completed")
        
        return True
    except RuntimeError as e:
        print(e)

```

app.py
```python
from core.app import App
from routes.routes import routes
from routes.api import routes as api_routes
from core.env import PORT, HOST
import itertools
import uvicorn
import asyncio
from database.migrations import migrate
from database.connections import connection


all_routes = list(itertools.chain(routes, api_routes))  # Combining regular and API routes

app = App(debug=True, routes=all_routes)  # Initialize app with routes

async def main():
    migrations = await migrate(connection, refresh=False)  # Execute migrations (no refresh)
   
    uvicorn.run("app:app.start", host=HOST, port=PORT, reload=True)  # Start the server

if __name__ == "__main__":
    asyncio.run(main())  # Run the main function


```
- In this script, we initialize the App object with routes and set up the server to run using uvicorn. The migrate function is called asynchronously to apply any pending migrations before starting the server. The server is run with the specified HOST and PORT settings./
En este script, inicializamos el objeto App con las rutas y configuramos el servidor para que se ejecute con uvicorn. La función migrate se llama de forma asincrónica para aplicar cualquier migración pendiente antes de iniciar el servidor. El servidor se ejecuta con los parámetros de HOST y PORT especificados.

### `middlewares/`

- **Purpose / Propósito**: Perform operations before or after requests reach routes, such as authentication or logging / Realizar operaciones antes o después de que las solicitudes lleguen a las rutas, como autenticación o registro de logs.
- **Use / Uso**: Defines and configures middlewares tailored to application needs / Define y configura middlewares adaptados a las necesidades de la aplicación.

### `routes/`

- **Organization / Organización**: Logically groups endpoints by functionality / Agrupa lógicamente los endpoints por funcionalidad.
- **Main functions / Funciones principales**: Defines how HTTP requests (GET, POST, etc.) are handled / Define cómo se manejan las solicitudes HTTP (GET, POST, etc.).


 ```python
from core.request import Request
from core.routing import Router
from core.templates import render,renderMarkdown
from core.session import Session
from core.responses import RedirectResponse
from middlewares.middlewares import login_required
from core.env import LANG_DEFAULT

#Example of routes

router = Router()

router.mount()

@router.route(path='/',methods=['GET'])
async def home(request : Request):
    response=render(request=request,template='index',files_translate=['guest'])
    return response

@router.route(path='/mardown',methods=['GET'])
async def home(request : Request):
    css=["/public/css/app.css"]
    response =renderMarkdown(request=request,file='test',css_files=css)
    return response

@router.route(path='/login',methods=['GET'])
async def login(request : Request):
    response =render(request=request,template='login',files_translate=['guest'])
    return response

#Example middleware "login_required" (session web)
@router.route(path='/dashboard',methods=['GET'])
@login_required
async def dashboard(request: Request):
    response = render(request=request, template='auth/dashboard')
    return response

#Delete cookie for session
@router.route(path='/logout', methods=['GET'])
async def logout(request: Request) :
    response = RedirectResponse(url='/')
    response.delete_cookie("session")  
    response.delete_cookie("auth")    
    response.delete_cookie("admin")
    return response

#Change language (session)
@router.route(path='/set-language/{lang}',methods=['GET'])
async def set_language(request :Request):
    lang= request.path_params.get('lang',LANG_DEFAULT)
    if not lang:
        lang=request.query_params.get('lang',LANG_DEFAULT)

    referer= request.headers.get('Referer','/')
    response = RedirectResponse(url=referer)
    Session.setSession(name_cookie='lang',new_val=lang,response=response)
    return response

routes = router.get_routes()

 ```

- Create Router 
Crear Router 
```python
   router = Router()
```

-Use mount() to serve public files, in this case by default it will take "public" as the folder and url to serve them. /
Usar mount() para servir archivos publicos, en este caso por defecto tomara "public" como carpeta y url para servirlos.
```python
   router.mount()
```
- Render with context in jinja2 /Renderizar html con jinja2, pasandole un datos
```python
@router.route(path='/',methods=['GET'])
async def home(request : Request):
    response=render(request=request,template='index',files_translate=['guest'])
    return response
```
- `set_language`: Dynamically changes the application's language, storing the preference in a session cookie.

```python
   @router.route(path='/set-language/{lang}',methods=['GET'])
   async def set_language(request :Request):
      lang= request.path_params.get('lang',LANG_DEFAULT)
      if not lang:
         lang=request.query_params.get('lang',LANG_DEFAULT)

      referer= request.headers.get('Referer','/')
      response = RedirectResponse(url=referer)
      Session.setSession(name_cookie='lang',new_val=lang,response=response)
      return response
```

  - `login_required`: Middleware example for route protection.

    ```python
    @router.route(path='/dashboard',methods=['GET'])
    @login_required
    async def dashboard(request: Request):
        response = render(request=request, template='auth/dashboard')
        return response
    ```
-How it works: /Como funciona 

-This middleware checks the session data for a valid "auth" cookie. If the session data is missing or invalid, it will redirect the user to the login page (/login).
If the session is valid, it allows the request to proceed to the route handler./
Este middleware comprueba los datos de la sesión en busca de una cookie de "auth" válida. Si faltan datos de la sesión o no son válidos, redirigirá al usuario a la página de inicio de sesión (/login).
Si la sesión es válida, permite que la solicitud pase al controlador de ruta.
Código de ejemplo:
Example Code /Ejemplo:

```python
def login_required(func):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data = Session.unsign(key="auth", request=request)
        if not session_data:
            return RedirectResponse(url='/login')
        return await func(request, *args, **kwargs)
    return wrapper
```

# Example of JSON Response / Ejemplo de respuesta JSON
```python
@router.route(path='/api', methods=['GET', 'POST'])
async def api(request: Request):
    return JSONResponse({'api': True})
```
# Example of Pydantic model usage for input validation / Ejemplo de uso de modelo Pydantic para validación de entrada

```python
class InputModel(BaseModel):
    email: EmailStr
    password: str

@router.route(path='/input', methods=['POST'])
async def login(request: Request):
    msg = translate(file_name='guest', request=request)
    msg_error = msg['Incorrect email or password']
    body = await request.json()
    input = InputModel(**body)
    email = input.email
    password = input.password
    print(input)
    response = JSONResponse({"success": False, "email": email, "password": password, "msg": msg_error})
    return response
```
# Get all routes / Obtener todas las rutas
```python
routes = router.get_routes()
```

## Markdown Page Creation (Creación de páginas con Markdown)

Lila allows you to edit and generate pages in Markdown (`.md`) format, which are automatically converted to HTML. This simplifies website development and integrated documentation.

Lila permite editar y generar páginas en formato Markdown (`.md`), que se convierten automáticamente en HTML. Esto facilita el desarrollo de sitios web y documentación integrada.

### Usage Example (Ejemplo de uso):

1. Create a Markdown file / Crea un archivo Markdown:

   ```markdown
   # Welcome to Lila / Bienvenido a Lila

   This is an example of Markdown-generated content / Este es un ejemplo de contenido generado en Markdown.
   ```

2. Save it in the corresponding directory and configure its rendering / Guárdalo en el directorio correspondiente y configúralo para su renderización.

 
    ```python
   from core.templates import renderMarkdown
   @router.route(path='/mardown',methods=['GET'])
   async def home(request : Request):
      css=["/public/css/app.css"]
      response =renderMarkdown(request=request,file='README',css_files=css)
      return response
    ```
 

### `static/`

- **Purpose / Propósito**: Serve static resources for user interfaces / Servir recursos estáticos para las interfaces de usuario.
- **Location / Ubicación**: Store all necessary shared frontend resources here / Asegúrate de almacenar aquí todos los recursos compartidos necesarios para el frontend.

### `templates/`

- **Use / Uso**: Create dynamic HTML views / Crear vistas HTML dinámicas.
- **Support / Soporte**: Compatible with template engines like Jinja2 / Compatible con motores de plantillas como Jinja2.

---


---

## Contributions (Contribuciones)

At this stage, all official modifications to the framework will be made only by the original author. However, any feedback or suggestions to improve the project are welcome.

Actualmente, todas las modificaciones oficiales al framework serán realizadas únicamente por el autor original. Sin embargo, se agradece cualquier comentario o sugerencia que pueda mejorar el proyecto.

