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
        "mysql",
        help="Service to start: 'mysql' (dev, default), 'prod' (mysql + app), 'postgres'"
    )
):
    """
    Start Docker containers.

    \b
    DEV  (default): lila-docker start       → starts MySQL only
    PROD          : lila-docker start prod  → starts MySQL + Python app container
    """
    _check_compose_file()

    if service in ("mysql", "dev"):
        print("🚀 Starting MySQL container (dev mode)...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", "mysql"], check=True)
            print("✅ MySQL started. Run your app locally with: python main.py")
            print("   ℹ️  To also run the app in Docker (production), use: lila-docker start prod")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting MySQL: {e}")
            raise typer.Exit(code=1)

    elif service == "prod":
        print("🚀 Starting production stack (MySQL + Python app)...")
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
        print(f"❌ Unknown service '{service}'. Use: mysql (default), prod, postgres")
        raise typer.Exit(code=1)


@app.command()
def stop(
    service: str = typer.Argument(
        "all",
        help="Service to stop: 'all' (default), 'mysql', 'app', 'postgres'"
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
            print(f"❌ Unknown service '{service}'. Use: all, mysql, app, postgres")
            raise typer.Exit(code=1)

    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def build():
    """
    Build the Python app Docker image.
    Run this after installing new packages or modifying requirements.txt.
    """
    _check_compose_file()
    print("🔨 Building Lila app Docker image...")
    try:
        subprocess.run(
            ["docker", "compose", "--profile", "prod", "build", "--no-cache", "app"],
            check=True
        )
        print("✅ Image built successfully. Start with: lila-docker start prod")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build error: {e}")
        raise typer.Exit(code=1)


@app.command()
def logs(
    service: str = typer.Argument("app", help="Service to tail logs for: 'app', 'mysql'"),
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
    if service == "app":
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
    service: str = typer.Argument("app", help="Container to exec into: 'app', 'mysql'"),
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
    if service == "app":
        cmd += ["--profile", "prod"]
    cmd += ["exec", service, command]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        show()


if __name__ == "__main__":
    app()
