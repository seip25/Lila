import sys
import time
import importlib
import pickle
import typer
from lila.core.cache import _get_redis_client

app = typer.Typer(help="Lila Background Task Worker CLI.")


@app.command()
def start():
    """Start the Lila background worker process."""
    client = _get_redis_client()
    if client is None:
        print("Error: Redis client is not configured or offline. Cannot start worker.")
        sys.exit(1)

    print("Lila Background Worker started. Listening on 'lila:tasks'...")
    while True:
        try:
            client = _get_redis_client()
            if client is None:
                print("Warning: Redis offline, attempting reconnection...")
                time.sleep(5)
                continue
            _, task_data = client.brpop("lila:tasks")
            try:
                payload = pickle.loads(task_data)
                func_path = payload["func_path"]
                args = payload["args"]
                kwargs = payload["kwargs"]

                module_name, qualname = func_path.split(":")
                module = importlib.import_module(module_name)

                obj = module
                for attr in qualname.split("."):
                    obj = getattr(obj, attr)

                print(f"Running task: {func_path}")
                obj(*args, **kwargs)
                print(f"Completed task: {func_path}")
            except Exception as e:
                print(f"Error executing task: {e}")
        except KeyboardInterrupt:
            print("\nWorker stopped.")
            break
        except Exception as e:
            if "Timeout reading from socket" in str(e):
                continue
            print(f"Worker error: {e}")
            time.sleep(1)


def main():
    """CLI entrypoint for Lila background worker."""
    app()


if __name__ == "__main__":
    main()
