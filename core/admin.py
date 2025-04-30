import psutil
import os 
import json
from core.helpers import lang, translate_, generate_token_value
from core.responses import HTMLResponse, RedirectResponse, JSONResponse
from core.request import Request
from core.routing import Router
from core.session import Session
from database.connections import connection
from argon2 import PasswordHasher
from functools import wraps 
from core.responses import convert_to_serializable

def Admin(models:list,user_default:str="admin"):
    router=Router()
    admin=AdminClass(models=models,router=router,connection=connection)
    admin._check_and_create_table()
    admin._create_default_admin(user_default)
    admin._generate_admin_routes()
    routes=admin.router.get_routes() 
    return routes

def admin_required(func):
    """Middleware to ensure the user is authenticated as an admin."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        session_data = Session.unsign(key="auth_admin", request=request)
        if not session_data:
            return RedirectResponse(url="/admin/login")
        if session_data["id"] is None   :
            return RedirectResponse(url="/admin/login")
        return await func(request, *args, **kwargs)
    return wrapper

class AdminClass:
    """A class to handle admin functionality, including authentication, routes, and model management."""

    def __init__(self, models: list, router: Router, connection):
        """
        Initialize the Admin class.

        Args:
            models (list): List of models to be managed in the admin panel.
            router (Router): The router instance to register admin routes.
            connection: The database connection instance.
            password_default (str, optional): Default password for the admin user. Defaults to None.
        """
        self.models = models
        self.router = router
        self.connection = connection 
        self.ph = PasswordHasher()
        self.password_default=None

    def _check_and_create_table(self):
        """Check if the 'admins' table exists and create it if it doesn't."""
        db_type = self.connection.engine.url.drivername

        if db_type == "sqlite":
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name='admins'"
        elif db_type in {"postgresql", "mysql","mysql+mysqlconnector"}:
            query = """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'admins'
            )
            """
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

        table_exists = self.connection.query(query=query, return_row=True)
        if db_type == "sqlite":
            table_exists = bool(table_exists)
        elif db_type in {"postgresql", "mysql", "mysql+mysqlconnector"}:
            table_exists = table_exists.get("table_exists", 0) == 1
        
        
        if not table_exists :
            if db_type == "sqlite":
                column_definition = "id INTEGER PRIMARY KEY AUTOINCREMENT"
            elif db_type == "mysql" or "mysql+mysqlconnector":
                column_definition = "id INTEGER PRIMARY KEY AUTO_INCREMENT"
            elif db_type == "postgresql":
                column_definition = "id SERIAL PRIMARY KEY"
            else:
                raise ValueError(f"Unsupported database type: {db_type}")
            create_table_query = f"""
            CREATE TABLE admins (
                 {column_definition},
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(150) NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            self.connection.query(query=create_table_query)

    def _create_default_admin(self,user_default:str="admin"):
        """Create a default admin user if it doesn't exist."""
        query = "SELECT id FROM admins WHERE username = :user_params LIMIT 1"
        params= {"user_params":user_default}
        admin = self.connection.query(query=query,params=params, return_row=True)
        if not admin:
            password = generate_token_value(2)
            self._create_admin(user_default, password)
            self.password_default = password
            print(f"Default admin password: '{password}' and user is '{user_default}'")

    def _create_admin(self, username: str, password: str) -> bool:
        """Create a new admin user.

        Args:
            username (str): The username of the admin.
            password (str): The password of the admin.

        Returns:
            bool: True if the admin was created successfully, False otherwise.
        """
        hashed_password = self.ph.hash(password)
        query = "INSERT INTO admins (username, password, active) VALUES (:username, :password, 1)"
        params = {"username": username, "password": hashed_password}
        result = self.connection.query(query=query, params=params)
        return result

    def _generate_admin_routes(self):
        """Generate routes for the admin panel, including model management."""
        
        self.router.route(path=f"/admin/login", methods=["GET", "POST"])(self.admin_login)

        self.router.route(path=f"/admin/logout", methods=["GET"])(self.admin_logout)

        @self.router.route(path=f"/admin/change_password", methods=["GET","POST"])
        @admin_required
        async def change_password_route(request: Request):
            return await self.change_password(request)

        @self.router.route(path=f"/admin", methods=["GET"])
        @admin_required
        async def admin_route(request: Request):
            return await self.admin_dashboard(request)

        for model in self.models:
            model_name = model.__name__.lower()
            model_plural = f"{model_name}s"
                
            @self.router.route(path=f"/admin/{model_plural}", methods=["GET"])
            @admin_required
            async def model_list(request: Request, model=model):
                items = model.get_all()  
                items=convert_to_serializable(items)
                return HTMLResponse(content=self._model_table_view(items, model_name, request))
        

        @self.router.route(path=f"/admin/metrics", methods=["GET"])
        @admin_required
        async def get_metrics(request: Request):
            lila_memory, lila_cpu_usage = self._get_lila_memory_usage()
            system_used_memory, system_total_memory, cpu_usage = self._get_system_memory_usage()
            
            metrics = {
                "lila_memory": lila_memory,
                "lila_cpu_usage": lila_cpu_usage,
                "system_used_memory": system_used_memory,
                "system_total_memory": system_total_memory,
                "cpu_usage": cpu_usage
            }
            
            return JSONResponse(metrics)

        return self.router
    
    async def admin_login(self, request: Request):
        """Handle admin login requests."""
        if request.method == "POST":
            try:
                form_data = await request.json()
                username = form_data.get("user")
                password = form_data.get("password")
                admin = self._authenticate(username, password)
                if admin:
                    response = JSONResponse({"success": True, "redirect": "/admin"},serialize=False)
                    admin_val={"id":admin["id"]}
                    Session.setSession(new_val=admin_val, response=response, name_cookie="auth_admin")
                    return response
                return JSONResponse({"success": False, "message": "Invalid credentials"}, status_code=401)
            except Exception as e:
                print(e)
                return JSONResponse({"success": False, "message": "Error"}, status_code=500)
        return HTMLResponse(self._login_form(request))

    async def admin_logout(self, request: Request):
        """Handle admin logout requests."""
        response = RedirectResponse(url="/admin/login")
        response.delete_cookie("auth_admin")
        return response

    async def change_password(self, request: Request):
        """Handle password change requests."""
        if request.method == "POST":
            try:
                data = await request.json()
                new_password = data.get("new_password")
                if not new_password:
                    return JSONResponse({"success": False, "message": "New password not provided"}, status_code=400)

                session_data = Session.unsign(key="auth_admin", request=request)
                admin_id = session_data.get("id") if session_data else None

                if admin_id:
                    hashed_password = self.ph.hash(new_password)
                    query = "UPDATE admins SET password = :password WHERE id = :id"
                    params = {"password": hashed_password, "id": admin_id}
                    self.connection.query(query=query, params=params)
                    return JSONResponse({"success": True, "message": "Password changed successfully"})
                return JSONResponse({"success": False, "message": "Admin not found"}, status_code=404)
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)
        else:
            html_lang = lang(request=request)
            content= f"""
        <!DOCTYPE html>
        <html lang="{html_lang}">
        <head>
            <meta charset="UTF-8">
            <link rel="icon" type="image" href="/public/img/lila.png" alt="Admin Lila Framework" />
            
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Admin Dashboard</title>
            <link rel="stylesheet" href="/public/css/pico.css">
        </head>
        <body>
           {self.menu()}
            <main class="container">
                {self._change_password_form()}
            </main>
            </body>
            </html>

            """
            return HTMLResponse(content)

    async def admin_dashboard(self, request: Request):
        
        """Render the admin dashboard.""" 
        return HTMLResponse(content=self._admin_dashboard_view( request))

    def _authenticate(self, username: str, password: str) -> dict:
        """Authenticate an admin user.

        Args:
            username (str): The username of the admin.
            password (str): The password of the admin.

        Returns:
            dict: The admin data if authentication is successful, otherwise None.
        """
        query = "SELECT id, username, password FROM admins WHERE username = :username AND active = 1 LIMIT 1"
        params = {"username": username}
        admin = self.connection.query(query=query, params=params, return_row=True)
        if not admin or not admin.get("password"):
            return None 

        try:
            if self.ph.verify(admin["password"], password):
                admin["password"]=None
                return admin
        except Exception as e:
            print(f"Error verifying password: {e}")
            return None

        return None

    def _login_form(self, request: Request) -> str:
        """Generate the HTML for the login form."""
        html_login = translate_(key="Login", request=request)
        html_user = translate_(key="User", request=request)
        html_send = translate_(key="Send", request=request)
        html_password = translate_(key="Password", request=request)
        html_lang = lang(request=request)
        return f"""
        <!DOCTYPE html>
        <html lang="{html_lang}">
        <head>
            <meta charset="UTF-8">
            <link rel="icon" type="image" href="/public/img/lila.png" alt="Admin Lila Framework" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Admin Login</title>
            <link rel="stylesheet" href="/public/css/pico.css" />
        </head>
        <body>
            <main class="container mx-m">
                
                    <article class="shadow  ">
                       
                            <h4 class="flex center">{html_login}</h4>
                         
                        <form id="loginForm">
                            
                               <div class="mt-2">
                                    <i class="icon icon-person"></i> 
                                    <input type="text" name="user" id="user" required minlength="2" maxlength="255" placeholder="" />
                                    <label>{html_user}</label>
                               </div>
                                 <div class="mt-2">
                                    <i class="icon icon-lock"></i> 
                                     <input type="password" name="password" id="password" required minlength="2" maxlength="255" placeholder="" />
                                     <label>{html_password}</label>
                             
                               </div>
                                 <button type="submit" class="w-full">
                                    <i class="icon icon-login"></i> 
                                    {html_send}
                                </button>
                            
                        </form>
                    </article> 
            </main>
            <script>
                document.getElementById("loginForm").addEventListener("submit", async function (event) {{
                    event.preventDefault();
                    const formData = Object.fromEntries(new FormData(event.target));
                    try {{
                        const r = await fetch("/admin/login", {{
                            method: "POST",
                            headers: {{
                                "Content-Type": "application/json",
                            }},
                            body: JSON.stringify(formData),
                        }});
                        const response = await r.json();
                        if (response.success) {{
                            window.location.href = response.redirect;
                        }} else {{
                            document.getElementById('password').value = '';
                            alert(response.message || "Error");
                        }}
                    }} catch (error) {{
                        alert("Error");
                        console.error("Error:", error);
                    }}
                }});
            </script>
        </body>
        </html>
        """
   
    def _change_password_form(self):
        return """
                <article class="shadow">
                    <h4>Change Password</h4>
                    <form id="changePasswordForm">
                    
                        <div class="mt-2">
                            <i class="icon icon icon-lock"></i>
                            <input type="password" name="new_password" id="new_password" required minlength="2" maxlength="255" placeholder="" />
                            <label>New Password</label>
                        </div>
                        <button type="submit" class="w-full">
                           <i class="icon icon-check-circle"></i>
                        Change Password
                        </button>
                    
                    </form>
                </article>
                <script>
                    document.getElementById("changePasswordForm").addEventListener("submit", async function (event) {
                        event.preventDefault();
                        const formData = {
                            new_password: document.getElementById("new_password").value,
                        };
                        try {
                            const response = await fetch("/admin/change_password", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                },
                                body: JSON.stringify(formData),
                            });
                            const result = await response.json();
                            if (result.success) {
                                alert("Password changed successfully.");
                                window.location.reload();
                            } else {
                                alert(result.message || "Error changing password");
                            }
                        } catch (error) {
                            console.error("Error:", error);
                        }
                    });
                </script>
                """

    def menu(self):
        """Generate the admin menu."""
        
        m=""
        for model in self.models:
            model_name = model.__name__.lower()
            model_plural = f"{model_name}s"
            m+=f"<li><a href='/admin/{model_plural}' class='underline-none'>{model_name.capitalize()}</a></li>"
            
            menu_=f"""
            <details>
                <summary>
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M0 0h24v24H0z" fill="none"/>
                    <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
                </svg>
                </summary>
                <ul >
                {m}
                <li><a href="/admin/change_password" class="underline-none">Change Password</a></li>
                <li><a href="/admin/logout" class="underline-none">Logout</a></li>
                </ul>
            </details>
        """
        return  f"""
      <header class=" shadow">
                <nav class="container">
                  <h1>Admin Dashboard</h1>
                   <a href="/admin/" class='underline-none'>Dashboard</a> 
                       {menu_} 
                </nav>
            </header>

        """
   
    def _admin_dashboard_view(self, request: Request) -> str:
        """Generate the HTML for the admin dashboard."""
    
        html_lang = lang(request=request)
        lila_memory, lila_cpu_usage = self._get_lila_memory_usage()
        system_used_memory, system_total_memory, cpu_usage = self._get_system_memory_usage()

        logs = {}
        log_base_dir = "logs"
        logs_html = ""

        if os.path.exists(log_base_dir):
            for log_folder in os.listdir(log_base_dir):
                log_folder_path = os.path.join(log_base_dir, log_folder)
                if os.path.isdir(log_folder_path):  
                    logs[log_folder] = {}
                    for log_file in os.listdir(log_folder_path):
                        if log_file.endswith(".log"):  
                            with open(os.path.join(log_folder_path, log_file), "r") as f:
                                logs[log_folder][log_file] = f.readlines()
                                

            logs_html = """
            <details class="logs-container container ">
                <summary class="logs-summary">📁 Logs</summary>
                <ul class="logs-list">
            """
            for log_folder, log_files in logs.items():
                logs_html += f"""
                <li class="log-item">
                    <details class="log-folder">
                        <summary class="log-folder-summary">📁 {log_folder}</summary>
                        <ul class="log-files-list">
                """
                for log_file, log_lines in log_files.items():
                    logs_html += f"""
                    <li class="log-file-item">
                        <details class="log-file">
                            <summary class="log-summary">📄 {log_file}</summary>
                            <pre class="log-content">{"".join(log_lines)}</pre>
                        </details>
                    </li>
                    """
                logs_html += """
                        </ul>
                    </details>
                </li>
                """
            logs_html += """
                </ul>
            </details>
            """ 
     
        return f"""
        <!DOCTYPE html>
        <html lang="{html_lang}">
        <head>
            <meta charset="UTF-8">
            <link rel="icon" type="image" href="/public/img/lila.png" alt="Admin Lila Framework" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Admin Dashboard</title>
            <link rel="stylesheet" href="/public/css/pico.css">
            <script src="/public/js/chart.js"></script>
            <style>
            li {{
                list-style: none !important;
            }}
            :root {{
                --logs-container-bg: #f9f9f9;
                --logs-container-border: #e0e0e0;
                --logs-summary-bg: #e0e0e0;
                --logs-summary-color: #333;
                --log-file-bg: #ffffff;
                --log-file-border: #d0d0d0;
                --log-summary-color: #333;
                --log-content-bg: #000;
                --log-content-color: #36f936;
                --log-content-border: #e0e0e0;
            }}

            @media (prefers-color-scheme: dark) {{
                :root {{
                    --logs-container-bg: #2d2d2d;
                    --logs-container-border: #444;
                    --logs-summary-bg: #444;
                    --logs-summary-color: #f5f5f5;
                    --log-file-bg: #1e1e1e;
                    --log-file-border: #444;
                    --log-summary-color: #f5f5f5;
                    --log-content-bg: #000;
                    --log-content-color: #36f936;
                    --log-content-border: #444;
                }}
            }}

            
            .logs-container {{
                margin-top: 1rem;
                border: 1px solid var(--logs-container-border);
                border-radius: 8px;
                padding: 0.5rem;
                background-color: var(--logs-container-bg);
            }}

            .logs-summary {{
                font-weight: bold;
                cursor: pointer;
                padding: 0.5rem;
                background-color: var(--logs-summary-bg);
                border-radius: 4px;
                color: var(--logs-summary-color);
            }}

            .logs-list {{
                list-style-type: none;
                padding-left: 0;
                margin-top: 0.5rem;
            }}

            .log-item {{
                margin-bottom: 0.5rem;
            }}

            .log-file {{
                border: 1px solid var(--log-file-border);
                border-radius: 4px;
                padding: 0.5rem;
                background-color: var(--log-file-bg);
            }}

            .log-summary {{
                cursor: pointer;
                font-weight: 500;
                color: var(--log-summary-color);
            }}

            .log-content {{
                margin-top: 0.5rem;
                padding: 0.5rem;
                border: 1px solid var(--log-content-border);
                border-radius: 4px;
                max-height: 600px;
                overflow-y: auto;
                font-family: monospace;
                font-size: 0.9rem;
                white-space: pre-wrap;
                word-wrap: break-word;
                color: var(--log-content-color);
                background-color: var(--log-content-bg);
            }}
            </style>
        </head>
        <body>
        {self.menu()}
            <main class="container"> 
                <article class="shadow">
                    <h4>Server Metrics</h4>
                    <div class="flex between">
                        <div>
                            <p>Lila Framework Memory Used: <span id="lilaMemory">{lila_memory:.0f}</span> MB</p>
                            <p>Lila Framework CPU Used: <span id="lilaCpuUsage">{lila_cpu_usage:.0f}</span> %</p>
                            <p>Server Memory Used: <span id="systemUsedMemory">{system_used_memory:.0f}</span> MB / <span id="systemTotalMemory">{system_total_memory:.0f}</span> MB</p>
                            <p>Server CPU Used: <span id="cpuUsage">{cpu_usage:.0f}</span> %</p>
                        </div>
                    </div>
                    <div class="flex between">
                        <div style="width: 25%;">
                            <canvas id="memoryDoughnutChart"></canvas>
                        </div>
                        <div style="width: 25%;">
                            <canvas id="cpuDoughnutChart"></canvas>
                        </div>
                    </div>
                </article>
                <br />
            
                <article class="shadow">
                    <h4>Logs</h4>
                    {logs_html}
                </article>
            </main> 
             
            <script>
                let memoryChart, cpuChart;

                function updateCharts() {{
                    fetch('/admin/metrics')
                        .then(response => response.json())
                        .then(data => {{
                            document.getElementById('lilaMemory').textContent = data.lila_memory.toFixed(0);
                            document.getElementById('lilaCpuUsage').textContent = data.lila_cpu_usage.toFixed(0);
                            document.getElementById('systemUsedMemory').textContent = data.system_used_memory.toFixed(0);
                            document.getElementById('systemTotalMemory').textContent = data.system_total_memory.toFixed(0);
                            document.getElementById('cpuUsage').textContent = data.cpu_usage.toFixed(0);

                            memoryChart.data.datasets[0].data = [data.system_used_memory, data.system_total_memory - data.system_used_memory];
                            cpuChart.data.datasets[0].data = [data.cpu_usage, 100 - data.cpu_usage];

                            memoryChart.update();
                            cpuChart.update();
                        }});
                }}

                document.addEventListener('DOMContentLoaded', function () {{
                    const memoryCtx = document.getElementById('memoryDoughnutChart').getContext('2d');
                    const cpuCtx = document.getElementById('cpuDoughnutChart').getContext('2d');

                    memoryChart = new Chart(memoryCtx, {{
                        type: 'doughnut',
                        data: {{
                            labels: ['Used Memory', 'Free Memory'],
                            datasets: [{{
                                label: 'Memory Usage',
                                data: [{system_used_memory}, {system_total_memory - system_used_memory}],
                                backgroundColor: ['#FF6384', '#36A2EB']
                            }}]
                        }}
                    }});

                    cpuChart = new Chart(cpuCtx, {{
                        type: 'doughnut',
                        data: {{
                            labels: ['CPU Used', 'CPU Free'],
                            datasets: [{{
                                label: 'CPU Usage',
                                data: [{cpu_usage}, {100 - cpu_usage}],
                                backgroundColor: ['#FFCE56', '#4BC0C0']
                            }}]
                        }}
                    }});

                     
                    setInterval(updateCharts, 10000);
                }});
            </script>
        </body>
        </html>
        """

    def _model_table_view(self, items: list, model_name: str, request: Request) -> str:
        """Generate the HTML for a model table view with Tabulator."""
        headers = items[0].keys() if items else []
         
        items_json = json.dumps(items)
        html_lang = lang(request=request)
        return f"""
        <!DOCTYPE html>
        <html lang="{html_lang}">
        <head>
            <meta charset="UTF-8">
            <link rel="icon" type="image" href="/public/img/lila.png" alt="Admin Lila Framework" />
            
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Admin - {model_name.capitalize()}</title>
            <link rel="stylesheet" href="/public/css/pico.css">
        
            <link href="https://unpkg.com/tabulator-tables@6.3.1/dist/css/tabulator.min.css" rel="stylesheet">
            <script type="text/javascript" src="https://unpkg.com/tabulator-tables@6.3.1/dist/js/tabulator.min.js"></script>
        
            <style>
            #tabulator-table button {{
             all: unset;  
            }}
            .tabulator-paginator{{
                display:flex !important;
                justify-content: space-between !important;
            }}
            </style>
        </head>
        <body>
             {self.menu()}
            <main class="container">
                <article>
                    <h2 class='flex center'>{model_name.capitalize()}</h2>
                    <div id="tabulator-table"></div>
                </article>
            </main>
            <script>
                
                let table = new Tabulator("#tabulator-table", {{
                    data: {items_json}, 
                    layout: "fitColumns", 
                    columns: [
                        {{
                            title: "ID",
                            field: "id",
                            visible: false 
                        }},
                        {",".join([
                            f'{{title: "{header.capitalize()}", field: "{header}"}}' for header in headers
                        ])}
                    ],
                    pagination: "local", 
                    paginationSize: 10, 
                    paginationSizeSelector: [10, 20, 50, 100], 
                    movableColumns: true, 
                    responsiveLayout: "hide", 
                }});
            </script>
        </body>
        </html>
        """
   
    def _get_lila_memory_usage(self) -> tuple:
        """Get memory and CPU usage of the Lila Framework process."""
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / (1024 * 1024)
        cpu_usage = process.cpu_percent()
        return memory_usage, cpu_usage

    def _get_system_memory_usage(self) -> tuple:
        """Get system memory and CPU usage."""
        memory_info = psutil.virtual_memory()
        used_memory = memory_info.used / (1024 * 1024)
        total_memory = memory_info.total / (1024 * 1024)
        cpu_usage = psutil.cpu_percent()
        return used_memory, total_memory, cpu_usage

    def _get_admin_by_id(self, id: int, select: str = "id,password") -> dict:
        """Get an admin by ID."""
        query = f"SELECT {select} FROM admins WHERE id = :id AND active = 1 LIMIT 1"
        params = {"id": id}
        row=self.connection.query(query=query, params=params, return_row=True)
        return row

    def _scripts(self, system_used_memory, cpu_usage, system_total_memory) -> str:
        """Generate JavaScript for the admin panel."""
        return f"""
        <script>
            document.addEventListener('DOMContentLoaded', function () {{
                const memoryDoughnutData = {{
                    labels: ['Used Memory', 'Free Memory'],
                    datasets: [{{
                        label: 'Memory',
                        data: [{system_used_memory}, {system_total_memory - system_used_memory}],
                        backgroundColor: [
                            'rgba(54, 162, 235, 0.6)',
                            'rgba(75, 192, 192, 0.6)'
                        ],
                        borderColor: [
                            'rgba(54, 162, 235, 1)',
                            'rgba(75, 192, 192, 1)'
                        ],
                        borderWidth: 1
                    }}]
                }};

                const memoryDoughnutCtx = document.getElementById('memoryDoughnutChart').getContext('2d');
                const memoryDoughnutChart = new Chart(memoryDoughnutCtx, {{
                    type: 'doughnut',
                    data: memoryDoughnutData,
                    options: {{
                        responsive: true,
                        plugins: {{
                            legend: {{
                                position: 'bottom',
                            }},
                            title: {{
                                display: true,
                                text: 'Memory Usage'
                            }}
                        }}
                    }}
                }});

                const cpuDoughnutData = {{
                    labels: ['Used CPU', 'Free CPU'],
                    datasets: [{{
                        label: 'CPU',
                        data: [{cpu_usage}, {100 - cpu_usage}],
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.6)',
                            'rgba(255, 206, 86, 0.6)'
                        ],
                        borderColor: [
                            'rgba(255, 99, 132, 1)',
                            'rgba(255, 206, 86, 1)'
                        ],
                        borderWidth: 1
                    }}]
                }};

                const cpuDoughnutCtx = document.getElementById('cpuDoughnutChart').getContext('2d');
                const cpuDoughnutChart = new Chart(cpuDoughnutCtx, {{
                    type: 'doughnut',
                    data: cpuDoughnutData,
                    options: {{
                        responsive: true,
                        plugins: {{
                            legend: {{
                                position: 'bottom',
                            }},
                            title: {{
                                display: true,
                                text: 'CPU Usage'
                            }}
                        }}
                    }}
                }});
            }});
        </script>
        """