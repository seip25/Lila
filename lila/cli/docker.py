import typer
import subprocess
import os
import sys

# Ensure the current directory is in sys.path
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer()

@app.command()
def start(service: str = typer.Argument("all", help="Database service to start: 'mysql', 'postgres', or 'all'")):
    """
    Start database containers ('mysql', 'postgres', or 'all').
    """
    if service not in ("mysql", "postgres", "all"):
        print("❌ Error: Service must be 'mysql', 'postgres', or 'all'")
        raise typer.Exit(code=1)
    
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found in the current directory.")
        raise typer.Exit(code=1)
    
    print(f"🚀 Starting {service} database services...")
    try:
        cmd = ["docker", "compose", "up", "-d"]
        if service != "all":
            cmd.append(service)
        subprocess.run(cmd, check=True)
        print(f"✅ {service} services started successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting database services: {e}")
        raise typer.Exit(code=1)

@app.command()
def stop(service: str = typer.Argument("all", help="Database service to stop: 'mysql', 'postgres', or 'all'")):
    """
    Stop and remove database containers ('mysql', 'postgres', or 'all').
    """
    if service not in ("mysql", "postgres", "all"):
        print("❌ Error: Service must be 'mysql', 'postgres', or 'all'")
        raise typer.Exit(code=1)
        
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found in the current directory.")
        raise typer.Exit(code=1)
        
    print(f"🛑 Stopping {service} database services...")
    try:
        if service == "all":
            subprocess.run(["docker", "compose", "down"], check=True)
        else:
            subprocess.run(["docker", "compose", "stop", service], check=True)
            subprocess.run(["docker", "compose", "rm", "-f", service], check=True)
        print(f"✅ {service} services stopped successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error stopping database services: {e}")
        raise typer.Exit(code=1)

@app.command("ps")
def show():
    """
    List active Lila database containers and their status.
    """
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found in the current directory.")
        raise typer.Exit(code=1)
    
    print("📋 Active Lila Database Containers:")
    try:
        subprocess.run(["docker", "compose", "ps"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error listing container status: {e}")
        raise typer.Exit(code=1)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        show()

if __name__ == "__main__":
    app()
