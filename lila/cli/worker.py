"""Lila Framework v2.0.x Background Task Worker.

Consumes JSON tasks from Redis (``lila:tasks``). No pickle, one persistent
event loop, retries and a dead-letter queue.
"""

import os
import sys
import time
import asyncio
import importlib
import inspect
from typing import Any, Optional

import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.core.cache import Cache, has_redis
from lila.core.config import ConfigLoader, ENV_CONFIG
from lila.core.responses import orjson_dumps, orjson_loads

app = typer.Typer(help="Lila background task worker for the Redis queue.")

QUEUE_KEY = "lila:tasks"
DEAD_KEY = "lila:tasks:dead"


def _resolve_function(func_path: str):
    if ":" not in func_path:
        raise ValueError("Task function path must be 'module:qualname'")
    module_name, qualname = func_path.split(":", 1)
    allowed = tuple(
        p.strip()
        for p in str(os.environ.get("LILA_TASK_MODULES", "app.,lila.")).split(",")
        if p.strip()
    )
    if allowed and not module_name.startswith(allowed):
        raise ValueError(f"Module '{module_name}' is not allowed by LILA_TASK_MODULES")
    module = importlib.import_module(module_name)
    obj = module
    for attr in qualname.split("."):
        obj = getattr(obj, attr)
    return obj


def _handle_task(payload: dict, loop: asyncio.AbstractEventLoop, client) -> None:
    func_path = payload.get("func_path") or ""
    args = payload.get("args") or []
    kwargs = payload.get("kwargs") or {}
    attempts = int(payload.get("attempts", 0))
    max_attempts = int(os.environ.get("LILA_TASK_RETRIES", "3") or 3)

    try:
        func = _resolve_function(func_path)
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            loop.run_until_complete(result)
        typer.secho(f"  ✅ Finished: {func_path}", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho(f"  ❌ Task error ({attempts + 1}/{max_attempts}) {func_path}: {exc}", fg=typer.colors.RED)
        payload["attempts"] = attempts + 1
        if payload["attempts"] < max_attempts:
            try:
                client.rpush(QUEUE_KEY, orjson_dumps(payload))
            except Exception:
                pass
            time.sleep(1)
        else:
            try:
                client.rpush(DEAD_KEY, orjson_dumps(payload))
            except Exception:
                pass


def run_worker() -> None:
    ConfigLoader.load()
    Cache.configure()
    if not has_redis():
        typer.secho("❌ Redis package is not installed. Install 'lila-framework[redis]'.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    client = Cache.redis_client()
    if client is None:
        typer.secho(
            "❌ Redis is not reachable. Set CACHE_DRIVER=redis and check REDIS_HOST/REDIS_URL.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    typer.secho("⚙️  Lila worker active. Listening on 'lila:tasks'...", fg=typer.colors.CYAN)

    try:
        while True:
            try:
                item = client.brpop(QUEUE_KEY, timeout=5)
                if not item:
                    continue
                _, raw = item
                try:
                    payload = orjson_loads(raw)
                except Exception:
                    typer.secho("  ⚠️ Ignoring non-JSON task payload.", fg=typer.colors.YELLOW)
                    continue
                if not isinstance(payload, dict):
                    continue
                _handle_task(payload, loop, client)
            except KeyboardInterrupt:
                typer.echo("\n🛑 Worker stopped.")
                break
            except Exception as exc:
                typer.secho(f"  ⚠️ Worker connection error: {exc}", fg=typer.colors.YELLOW)
                time.sleep(2)
                client = Cache.redis_client()
                if client is None:
                    time.sleep(3)
    finally:
        try:
            loop.close()
        except Exception:
            pass


@app.callback(invoke_without_command=True)
def worker(ctx: typer.Context):
    """Start the worker (default command)."""
    if ctx.invoked_subcommand is None:
        run_worker()


@app.command("start")
def start():
    """Start the Lila background worker process."""
    run_worker()


def main():
    # Typer handles `lila worker`, `lila worker start` and `lila-worker start`.
    app()


if __name__ == "__main__":
    main()
