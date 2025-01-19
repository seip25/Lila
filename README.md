# Lila

Lila is a minimalist Python framework based on Starlette and Pydantic. Designed for developers seeking simplicity, flexibility, and robustness, it enables efficient and customizable Web or API application development. Its modular structure and support for advanced configurations make it suitable for both beginners and experienced developers.

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
- **SQLAlchemy** :For the ORM or you can also use the connectors directly (mysql.connector, sqlite3, etc...)
- **JWT** :It comes integrated with helpers to generate tokens and the middleware already has a function that validates it.
---

# Lila (Español)

Lila es un framework minimalista de Python basado en Starlette y Pydantic. Diseñado para desarrolladores que buscan simplicidad, flexibilidad y robustez, permite crear aplicaciones Web o APIs de manera eficiente y personalizable. Su estructura modular y soporte para configuraciones avanzadas lo hacen ideal tanto para principiantes como para desarrolladores experimentados.

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
- **SQLAlchemy** :Para la ORM o también se puede utilizar los connectores directamente(mysql.connector,sqlite3,etc...)
- **JWT** :Viene integrado con helpers para generar token y en el middleware ya viene una función que válida el mismo.


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

---
- ***Free customization***

- You can use Lila with any styling framework you prefer, such as Tailwind CSS, Bootstrap, PicoCSS, or others.
- By default in the example templates, use Beer CSS.

- If you want to start clean and build from scratch:

- Delete all folders except 'core' and 'locales'

- Empty the templates and static folders.

- Configure the framework as you wish, modifying or extending the core, which is flexible and can adapt to any development pattern.
---

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
- ***Personalización Libre***

- Puedes usar Lila con cualquier framework de estilos que prefieras, como Tailwind CSS, Bootstrap, PicoCSS, u otros. 
- Por defecto en los templates de ejemplo, utiliza Beer CSS.

- Si deseas empezar limpio y construir desde cero:

- Elimina todas las carpetas excepto 'core' and 'locales'

- Vacía las carpetas templates y static.

- Configura el framework según lo desees, modificando o ampliando el core, que es flexible y puede adaptarse a cualquier patrón de desarrollo.

---

## Project Structure (Estructura del proyecto)

### `app.py`

- **Purpose / Propósito**: Configure and start the application / Configurar y arrancar la aplicación.
- **Use / Uso**: Defines main routes and middlewares / Define las rutas y los middlewares principales.

### `core/`

- **Global configuration / Configuración global**: Includes application settings, such as environment variable handling and general configurations / Incluye la configuración de la aplicación, como el manejo de variables de entorno y configuraciones generales.
- **Utilities / Utilidades**: Shared functions for use in different modules / Funciones compartidas para uso en diferentes módulos.



### `locales/`

- **Translations / Traducciones**:
- Default the 'Render' method loads the translations file 'translations.json'.
To use it anywhere in the application, you can use the 'translate' helper, passing it the name of the file you want to open to get the translations, returning a dictionary./
De forma predeterminada, el método 'Render' carga el archivo de traducciones 'translations.json'.
Para usarlo en cualquier parte de la aplicación, puedes usar el helper 'translate', pasándole el nombre del archivo que quieres abrir para obtener las traducciones y devolviendo un diccionario.

core/helpers.py

```python
from core.helpers import translate
translate(file_name='guest' , request: Request)

```

- example file . / archivo de ejemplo
```json
{
  "Send": {
    "es": "Enviar",
    "en": "Send"
  },
  "Cancel": {
    "es": "Cancelar",
    "en": "Cancel"
  },
  "Accept":{
    "es": "Aceptar",
    "en": "Accept"
  },
  "Email":{
    "es":"Email",
    "en":"Email"
  },
  "Name":{
    "es":"Nombre",
    "en":"Name"
  }

}

```

### `database/`

- **Connection / Conexión**: Configures and manages MySQL or SQLite connections / Configura y gestiona las conexiones con MySQL o SQLite.
- **Models / Modelos**: The models module defines the data models used to interact with the database. These models represent your database tables and can be used to perform CRUD (Create, Read, Update, Delete) operations. / El módulo models define los modelos de datos utilizados para interactuar con la base de datos. Estos modelos representan las tablas de la base de datos y pueden utilizarse para realizar operaciones CRUD (Crear, Leer, Actualizar, Eliminar),etc.
- **Configurable ORMs / ORMs configurables**: This framework allows you to integrate easily with popular ORMs such as SQLModel or SQLAlchemy. You can configure it to suit your needs and use either of them for managing database operations./ Este framework permite integrar fácilmente ORMs populares como SQLModel o SQLAlchemy. Puedes configurarlo para adaptarse a tus necesidades y utilizar cualquiera de ellos para gestionar las operaciones en la base de datos.

### `models/`

- **Models /Modelos** :These models represent the database tables and can be used to perform CRUD operations (Create, Read, Update, Delete), etc.

The code provided establishes the 'users' model, along with a function to execute queries, in this case an insert, thanks to SQLAlchemy. /Estos modelos representan las tablas de la base de datos y pueden utilizarse para realizar operaciones CRUD (Crear, Leer, Actualizar, Eliminar), etc.

El código proporcionado establece el modelo 'users', junto con una función para ejecutar consultas, en este caso una inserción, gracias a SQLAlchemy.


```python
from sqlalchemy import Table,Column,Integer,String,TIMESTAMP
from sqlalchemy.orm import validates
from core.database import Base
from database.connections import connection
import secrets
import hashlib
import bcrypt

class User(Base):
    __tablename__='users'
    id = Column(Integer, primary_key=True,autoincrement=True)
    name=Column( String(length=50), nullable=False)
    email=Column( String(length=50), unique=True)
    password=Column(String(length=150), nullable=False)
    token=Column(String(length=150), nullable=False)
    active=Column( Integer, nullable=False,default=1)
    created_at=Column( TIMESTAMP)

    def validate_password(stored_hash :str, password:str)->bool:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

    def insert(params :dict )->bool:
        params["token"]=hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()
        params["active"]=1
        params["password"]=bcrypt.hashpw(params["password"].encode('utf-8'),bcrypt.gensalt())
        placeholders =' ,'.join(f":{key}" for key in params.keys())
        columns =','.join(f"{key}" for key in params.keys() )
        
        query =f"INSERT INTO users ({columns}) VALUES({placeholders})"
        return connection.query(query,params)

#Example to execute querys with models SQLAlchemy
#usage mode for running queries (insert, select, update, etc.)
User.insert({"name":"name","email":"example@example.com","password":"password"})

```

- **Migrations /migraciones**
- Example of Migration Script / Ejemplo de Script de Migración
- The script defines a migration for the users table and a User model. The migration script creates the users table with columns such as id, name, email, etc. It also includes a migrate function that performs the migration using the configured connection. The refresh parameter can be set to True to drop and recreate the tables from scratch./
El script define una migración para la tabla users y un modelo User. El script de migración crea la tabla users con columnas como id, name, email, etc. También incluye una función migrate que realiza la migración utilizando la conexión configurada. El parámetro refresh puede configurarse como True para eliminar y recrear las tablas desde cero.

- You can use either the migrations form and take advantage of the created models to avoid repeating code or if you just want to create the table you can use the first form with 'Table' from SQLAlchemy./Puedes utilizar tanto la forma de las migraciones y aprovechar los modelos creados para no repetir código o si solo quieres crear la tabla puedes usar la primera forma con 'Table' de SQLAlchemy.



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

middlewares/middlewares.py

```python
from core.session import Session
from core.responses import RedirectResponse,JSONResponse
from core.env import SECRET_KEY
from core.request import Request
from functools import wraps 
import jwt

def login_required(func,key:str='auth'):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data= Session.unsign(key=key,request=request)
        if not session_data:
            return RedirectResponse(url='/login')
        return await func(request,*args,**kwargs)
    return wrapper

def session_active(func,key:str='auth',url_return:str ='/dashboard'):
    @wraps(func)
    async def wrapper(request,*args,**kwargs):
        session_data= Session.unsign(key=key,request=request)
        if session_data:
            return RedirectResponse(url=url_return)
        return await func(request,*args,**kwargs)
    return wrapper

def validate_token(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return JSONResponse({'message': 'Invalid token'},status_code=401)
        try:
            token = token.split(" ")[1] 
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return await func(request, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return JSONResponse({'message': 'Token has expired'}, status_code=401) 
        except jwt.InvalidTokenError:
            return JSONResponse({'message': 'Invalid token'},status_code=401)

    return wrapper

```
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

@router.route(path='/markdown',methods=['GET'])
async def home(request : Request):
    css=["/public/css/app.css"]
    response =renderMarkdown(request=request,file='test',css_files=css)
    return response

@router.route(path='/login',methods=['GET'])
@session_active #validate session ,redirect to dashboard
async def login(request : Request):
    response =render(request=request,template='auth/login',files_translate=['guest'])
    return response

@router.route(path='/register',methods=['GET'])
@session_active #validate session ,redirect to dashboard
async def login(request : Request):
    response =render(request=request,template='auth/register',files_translate=['guest'])
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
- **JWT**

-Helpers and middleware to generate and validate token / Helpers y middleware para generar , validar token .
 
-It is used in the following way /Se utiliza de la siguiente manera para la validación del mismo.
```python

from middlewares.middlewares import validate_token
@router.route(path='/login',methods=['POST'],model=LoginModel)
@validate_token #middleware validate token
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
- core/helpers.py

```python
import jwt
import datetime

def generate_token(name:str,value:str)->str :
    options={}
    options[name]=value
    options['exp']=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode(options,SECRET_KEY,algorithm='HS256')
    return token

def get_token(token:str):
    token = token.split(" ")[1] 
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


```

- Middleware for validate tokens / Middleware para validar tokens

```python
def validate_token(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return JSONResponse({'message': 'Invalid token'},status_code=401)
        try:
            token = token.split(" ")[1] 
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return await func(request, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return JSONResponse({'message': 'Token has expired'}, status_code=401) 
        except jwt.InvalidTokenError:
            return JSONResponse({'message': 'Invalid token'},status_code=401)

    return wrapper
```
- In the client there is code that can be helpful in /static/js/utils.js , both to send fetch, delete, generate and set cookies and to save the token or other application data in connection with the backend. /
En el lado del cliente hay  código que puede ser útil en /static/js/utils.js, tanto para enviar, obtener, eliminar, generar y configurar cookies, como para guardar el token u otros datos de la aplicación en conexión con el backend.

```javascript
const resp = await Http({ url: "/token_check", method: "POST", body: form,token:'token' });
  
async function Http({
  url = "/",
  method = "GET",
  body = false,
  token = false,
}) {
  const options = {
    method: method,
    headers: {},
  };
  if (body) options["body"] = JSON.stringify(body);

  if (token) options.headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Error fetch");
  }
  const resp = await response.json();
  return resp;
}


function setCookie({name='token', value, days=7, secure = false}) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    let cookieString = `${name}=${encodeURIComponent(
      value
    )}; expires=${expires}; path=/; SameSite=Lax`;
    if (secure) cookieString += "; Secure";
    
    document.cookie = cookieString;
  }
  
  function getCookie({name}) {
    return document.cookie.split("; ").reduce((r, v) => {
      const parts = v.split("=");
      return parts[0] === name ? decodeURIComponent(parts[1]) : r;
    }, "");
  }
  
  function deleteCookie({name}) {
    document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  }

```
---

## Contributions (Contribuciones)

At this stage, all official modifications to the framework will be made only by the original author. However, any feedback or suggestions to improve the project are welcome.

Actualmente, todas las modificaciones oficiales al framework serán realizadas únicamente por el autor original. Sin embargo, se agradece cualquier comentario o sugerencia que pueda mejorar el proyecto.

