import sys
import os
import time
import importlib
import pickle
import asyncio
import inspect
import typer
from lila.core.cache import Cache

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Lila Background Task Worker for Redis Queue.")

@app.command()
def start():
    """Start the Lila background worker process listening on 'lila:tasks'."""
    client = Cache.get_redis_client()
    if client is None:
        typer.secho("❌ Error: Redis is not configured or offline. Set CACHE_DRIVER=redis in .env.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("⚙️  Lila Background Worker active. Listening on 'lila:tasks'...", fg=typer.colors.CYAN)
    while True:
        try:
            client = Cache.get_redis_client()
            if client is None:
                time.sleep(3)
                continue
            item = client.brpop("lila:tasks", timeout=5)
            if not item:
                continue
            _, task_data = item
            try:
                payload = pickle.loads(task_data)
                func_path = payload["func_path"]
                args = payload.get("args", ())
                kwargs = payload.get("kwargs", {})

                module_name, qualname = func_path.split(":")
                module = importlib.import_module(module_name)
                obj = module
                for attr in qualname.split("."):
                    obj = getattr(obj, attr)

                typer.echo(f"  ▶️ Executing: {func_path}")
                res = obj(*args, **kwargs)
                if inspect.isawaitable(res):
                    asyncio.run(res)
                typer.secho(f"  ✅ Finished: {func_path}", fg=typer.colors.GREEN)
            except Exception as task_err:
                typer.secho(f"  ❌ Task error: {task_err}", fg=typer.colors.RED)
        except KeyboardInterrupt:
            typer.echo("\n🛑 Worker stopped.")
            break
        except Exception as e:
            time.sleep(2)

def main():
    app()

if __name__ == "__main__":
    main()
