import typer
import subprocess
import os
import sys

# Ensure the current directory is in sys.path
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Manage Lila Docker containers for dev and production.")


def _check_compose_file():
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found in the current directory.")
        raise typer.Exit(code=1)


@app.command()
def start(
    service: str = typer.Argument(
        "dev",
        help="Service to start: 'dev' (mysql + redis, default), 'mysql', 'redis', 'prod' (complete production stack), 'postgres'"
    )
):
    """
    Start Docker containers.

    \b
    DEV  (default): lila-docker start       → starts MySQL and Redis containers
    PROD          : lila-docker start prod  → starts complete production stack
    """
    _check_compose_file()

    if service == "dev":
        print("🚀 Starting MySQL and Redis containers (dev mode)...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", "mysql", "redis"], check=True)
            print("✅ MySQL and Redis started. Run your app locally with: lila-dev")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting dev containers: {e}")
            raise typer.Exit(code=1)

    elif service == "mysql":
        print("🚀 Starting MySQL container...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", "mysql"], check=True)
            print("✅ MySQL started.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting MySQL: {e}")
            raise typer.Exit(code=1)

    elif service == "redis":
        print("🚀 Starting Redis container...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", "redis"], check=True)
            print("✅ Redis started.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting Redis: {e}")
            raise typer.Exit(code=1)

    elif service == "prod":
        print("🚀 Starting production stack (MySQL, Redis, App, Nginx)...")
        try:
            subprocess.run(["docker", "compose", "--profile", "prod", "up", "-d"], check=True)
            print("✅ Production stack started.")
            print("   📋 View logs with: lila-docker logs")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting production stack: {e}")
            raise typer.Exit(code=1)

    elif service == "postgres":
        print("🚀 Starting PostgreSQL container...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", "postgres"], check=True)
            print("✅ PostgreSQL started. Run your app locally with: python main.py")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting PostgreSQL: {e}")
            raise typer.Exit(code=1)

    else:
        print(f"❌ Unknown service '{service}'. Use: dev (default), mysql, redis, prod, postgres")
        raise typer.Exit(code=1)


@app.command()
def stop(
    service: str = typer.Argument(
        "all",
        help="Service to stop: 'all' (default), 'mysql', 'redis', 'app', 'postgres'"
    )
):
    """
    Stop Docker containers.
    """
    _check_compose_file()

    try:
        if service == "all":
            print("🛑 Stopping all Lila containers...")
            subprocess.run(["docker", "compose", "--profile", "prod", "down"], check=True)
            print("✅ All containers stopped.")

        elif service == "mysql":
            print("🛑 Stopping MySQL...")
            subprocess.run(["docker", "compose", "stop", "mysql"], check=True)
            subprocess.run(["docker", "compose", "rm", "-f", "mysql"], check=True)
            print("✅ MySQL stopped.")

        elif service == "redis":
            print("🛑 Stopping Redis...")
            subprocess.run(["docker", "compose", "stop", "redis"], check=True)
            subprocess.run(["docker", "compose", "rm", "-f", "redis"], check=True)
            print("✅ Redis stopped.")

        elif service == "app":
            print("🛑 Stopping Python app container...")
            subprocess.run(["docker", "compose", "--profile", "prod", "stop", "app"], check=True)
            subprocess.run(["docker", "compose", "--profile", "prod", "rm", "-f", "app"], check=True)
            print("✅ App container stopped.")

        elif service == "postgres":
            print("🛑 Stopping PostgreSQL...")
            subprocess.run(["docker", "compose", "stop", "postgres"], check=True)
            subprocess.run(["docker", "compose", "rm", "-f", "postgres"], check=True)
            print("✅ PostgreSQL stopped.")

        else:
            print(f"❌ Unknown service '{service}'. Use: all, mysql, redis, app, postgres")
            raise typer.Exit(code=1)

    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def build(
    no_cache: bool = typer.Option(
        False, "--no-cache", "-n", help="Force rebuild without using Docker layer cache"
    )
):
    """
    Build the Python app Docker image.
    Run this after installing new packages or modifying requirements.txt.
    By default, uses Docker layer cache for fast builds.
    """
    _check_compose_file()
    print("🔨 Building Lila app Docker image...")
    cmd = ["docker", "compose", "--profile", "prod", "build"]
    if no_cache:
        cmd.append("--no-cache")
    cmd.append("app")

    try:
        subprocess.run(cmd, check=True)
        print("✅ Image built successfully. Start with: lila-docker start prod")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build error: {e}")
        raise typer.Exit(code=1)


@app.command("df")
def df():
    """
    Display Docker disk space usage (images, containers, volumes, build cache).
    """
    print("📊 Docker Disk Usage:")
    try:
        subprocess.run(["docker", "system", "df"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error fetching Docker disk usage: {e}")
        raise typer.Exit(code=1)


@app.command("disk")
def disk():
    """
    Alias for 'lila-docker df'.
    """
    df()


@app.command("prune")
def prune(
    all_resources: bool = typer.Option(
        False, "--all", "-a", help="Remove all unused images, not just dangling ones"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Do not prompt for confirmation"
    ),
):
    """
    Clean up unused Docker resources (dangling volumes, images, and BuildKit cache).
    Frees up disk space on your VPS.
    """
    if not force:
        confirm = typer.confirm("⚠️ Clean unused volumes, dangling images, and BuildKit cache?")
        if not confirm:
            print("Operation cancelled.")
            raise typer.Exit()

    print("🧹 1/3 Cleaning orphaned Docker volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])

    print("🧹 2/3 Cleaning unused Docker images...")
    img_cmd = ["docker", "image", "prune"]
    if all_resources:
        img_cmd.append("-a")
    img_cmd.append("-f")
    subprocess.run(img_cmd)

    print("🧹 3/3 Cleaning BuildKit build cache...")
    subprocess.run(["docker", "builder", "prune", "-a", "-f"])

    print("\n✨ Docker cleanup completed successfully! Current disk usage:")
    subprocess.run(["docker", "system", "df"])


@app.command("clean")
def clean(
    all_resources: bool = typer.Option(
        False, "--all", "-a", help="Remove all unused images, not just dangling ones"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Do not prompt for confirmation"
    ),
):
    """
    Alias for 'lila-docker prune'.
    """
    prune(all_resources=all_resources, force=force)


@app.command()
def logs(
    service: str = typer.Argument("app", help="Service to tail logs for: 'app', 'nginx', 'mysql', 'redis'"),
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show from the end"),
):
    """
    View container logs.

    \b
    lila-docker logs           → tail Python app logs
    lila-docker logs mysql     → tail MySQL logs
    lila-docker logs --no-follow → print last 100 lines and exit
    """
    _check_compose_file()
    cmd = ["docker", "compose"]
    if service in ("app", "nginx"):
        cmd += ["--profile", "prod"]
    cmd += ["logs", f"--tail={tail}"]
    if follow:
        cmd.append("-f")
    cmd.append(service)

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as e:
        print(f"❌ Error fetching logs: {e}")
        raise typer.Exit(code=1)


@app.command("ps")
def show():
    """
    List active Lila containers and their status.
    """
    _check_compose_file()
    print("📋 Active Lila Containers:")
    try:
        subprocess.run(["docker", "compose", "--profile", "prod", "ps"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error listing container status: {e}")
        raise typer.Exit(code=1)


@app.command()
def exec(
    service: str = typer.Argument("app", help="Container to exec into: 'app', 'nginx', 'mysql', 'redis'"),
    command: str = typer.Argument("bash", help="Command to run inside the container"),
):
    """
    Execute a command inside a running container.

    \b
    lila-docker exec           → opens bash in the Python app container
    lila-docker exec app bash  → same
    lila-docker exec mysql bash → opens bash in MySQL container

    TIP: To run CLI commands inside the container:
         lila-docker exec app bash
         Then inside: lila-migrations migrate
    """
    _check_compose_file()
    cmd = ["docker", "compose"]
    if service in ("app", "nginx"):
        cmd += ["--profile", "prod"]
    cmd += ["exec", service, command]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


def _get_env_vars():
    env_vars = dict(os.environ)
    env_file = ".env"
    if os.path.exists(env_file):
        try:
            from dotenv import dotenv_values
            file_vars = dotenv_values(env_file)
            for k, v in file_vars.items():
                if v is not None:
                    env_vars[k] = str(v)
        except Exception:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


@app.command("mysql")
def mysql(
    user: str = typer.Option(None, "--user", "-u", help="MySQL user (defaults to DB_USER / MYSQL_USER from .env)"),
    password: str = typer.Option(None, "--password", "-p", help="MySQL password (defaults to DB_PASSWORD / MYSQL_ROOT_PASSWORD from .env)"),
    database: str = typer.Option(None, "--db", "-d", help="Database name (defaults to DB_NAME / MYSQL_DATABASE from .env)"),
    root: bool = typer.Option(False, "--root", help="Connect as root user"),
):
    """
    Open interactive MySQL terminal inside Docker container using credentials from .env.

    \b
    lila-docker mysql         → connects to MySQL using .env credentials
    lila-docker mysql --root  → connects as root user using root password from .env
    lila-docker db            → alias for lila-docker mysql
    """
    _check_compose_file()
    env = _get_env_vars()

    if root:
        db_user = "root"
        db_pass = env.get("MYSQL_ROOT_PASSWORD") or env.get("DB_PASSWORD") or "root"
    else:
        db_user = user or env.get("DB_USER") or env.get("MYSQL_USER") or "root"
        db_pass = password or env.get("DB_PASSWORD") or env.get("MYSQL_ROOT_PASSWORD") or env.get("MYSQL_PASSWORD") or "root"

    db_name = database or env.get("DB_NAME") or env.get("MYSQL_DATABASE") or ""

    cmd = ["docker", "compose", "exec", "mysql", "mysql", f"-u{db_user}"]
    if db_pass:
        cmd.append(f"-p{db_pass}")
    if db_name:
        cmd.append(db_name)

    target_db = f" (database: {db_name})" if db_name else ""
    print(f"🔌 Connecting to MySQL shell in container as '{db_user}'{target_db}...")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as e:
        print(f"❌ Error connecting to MySQL: {e}")
        print("💡 Make sure the MySQL container is running: lila-docker start mysql")
        raise typer.Exit(code=1)


@app.command("db")
def db(
    user: str = typer.Option(None, "--user", "-u", help="MySQL user (defaults to DB_USER / MYSQL_USER from .env)"),
    password: str = typer.Option(None, "--password", "-p", help="MySQL password (defaults to DB_PASSWORD / MYSQL_ROOT_PASSWORD from .env)"),
    database: str = typer.Option(None, "--db", "-d", help="Database name (defaults to DB_NAME / MYSQL_DATABASE from .env)"),
    root: bool = typer.Option(False, "--root", help="Connect as root user"),
):
    """
    Alias for 'lila-docker mysql'.
    """
    mysql(user=user, password=password, database=database, root=root)


@app.command("redis")
def redis():
    """
    Open interactive Redis CLI terminal inside Docker container.

    \b
    lila-docker redis  → connects to redis-cli in the running Redis container
    """
    _check_compose_file()
    cmd = ["docker", "compose", "exec", "redis", "redis-cli"]
    print("🔌 Connecting to Redis CLI...")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as e:
        print(f"❌ Error connecting to Redis: {e}")
        print("💡 Make sure the Redis container is running: lila-docker start redis")
        raise typer.Exit(code=1)


@app.command("redis-cli")
def redis_cli():
    """
    Alias for 'lila-docker redis'.
    """
    redis()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        show()


if __name__ == "__main__":
    app()

