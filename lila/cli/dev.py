import os
import sys
import subprocess
import socket
import time
import typer
from lila.core.config import ENV_CONFIG

app = typer.Typer(help="Start Lila local development server.")


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 3.0) -> None:
    """
    Wait for a specific host port to open before continuing execution.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)


@app.command()
def start(
    without_mysql: bool = typer.Option(
        False,
        "--without-mysql",
        "--no-mysql",
        help="Do not start the MySQL database container."
    ),
    without_redis: bool = typer.Option(
        False,
        "--without-redis",
        "--no-redis",
        help="Do not start the Redis container."
    ),
):
    """
    Start the Lila local development server by executing main.py and booting Docker dev services.
    """
    if not os.path.exists("main.py"):
        print(" Error: main.py not found in the current directory.")
        print("   Make sure you are in the root directory of your Lila project.")
        sys.exit(1)

    if os.path.exists("docker-compose.yml"):
        db_started = False
        redis_started = False

        if not without_mysql:
            print("🚀 Starting MySQL container (dev)...")
            try:
                subprocess.run(["docker", "compose", "up", "-d", "mysql"], check=True)
                db_started = True
            except Exception as e:
                print(f"⚠️ Warning: Could not start MySQL: {e}")

        if not without_redis:
            print("🚀 Starting Redis container (dev)...")
            try:
                subprocess.run(["docker", "compose", "up", "-d", "redis"], check=True)
                redis_started = True
            except Exception as e:
                print(f"⚠️ Warning: Could not start Redis: {e}")

        if db_started:
            db_port = int(ENV_CONFIG.get("DB_PORT", 3306))
            wait_for_port(db_port)

        if redis_started:
            redis_port = int(ENV_CONFIG.get("REDIS_PORT", 6379))
            wait_for_port(redis_port)

    print("🚀 Starting Lila development server...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n Lila server stopped.")
    except Exception as e:
        print(f" Error starting server: {e}")
        sys.exit(1)


def main():
    app()


if __name__ == "__main__":
    main()

