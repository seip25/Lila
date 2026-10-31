"""Lila Database Backup CLI.

Hot, atomic SQLite backups using Python's native sqlite3.Connection.backup() API.
Takes consistent zero-lock backups of SQLite WAL databases in milliseconds without
blocking writes or taking down the web server.
"""

import os
import sys
import time
import sqlite3
import typer
from typing import Optional

from lila.core.config import ConfigLoader, ENV_CONFIG, get_data_path

app = typer.Typer(help="Hot atomic SQLite database backup using native sqlite3.backup().")


def run_sqlite_backup(
    source_db_path: Optional[str] = None,
    output_path: Optional[str] = None,
    max_backups: int = 7,
) -> dict:
    """Executes an online zero-downtime backup of the active SQLite database."""
    ConfigLoader.load()

    # 1. Resolve source SQLite database path
    if source_db_path and os.path.isfile(source_db_path):
        src_path = os.path.abspath(source_db_path)
    else:
        db_name = str(ENV_CONFIG.get("DB_NAME") or ENV_CONFIG.get("DB_DATABASE") or "lila")
        candidates = [
            get_data_path(f"{db_name}.sqlite"),
            get_data_path(f"{db_name}.db"),
            os.path.join(os.getcwd(), f"{db_name}.sqlite"),
            os.path.join(os.getcwd(), f"{db_name}.db"),
            os.path.join(os.getcwd(), "lila.sqlite"),
            os.path.join(os.getcwd(), "app.sqlite"),
        ]
        src_path = None
        for cand in candidates:
            if os.path.isfile(cand):
                src_path = os.path.abspath(cand)
                break
        if not src_path:
            src_path = os.path.abspath(candidates[0])

    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Database file not found at: {src_path}")

    # 2. Resolve destination path
    timestamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{int((time.time() % 1) * 1000000):06d}"
    base_name = os.path.splitext(os.path.basename(src_path))[0]
    default_backup_dir = get_data_path("backups")
    os.makedirs(default_backup_dir, exist_ok=True)

    if output_path:
        is_target_dir = (
            os.path.isdir(output_path)
            or output_path.endswith(("/", "\\"))
            or not os.path.splitext(output_path)[1]
        )
        if is_target_dir:
            os.makedirs(output_path, exist_ok=True)
            dst_path = os.path.abspath(os.path.join(output_path, f"backup_{base_name}_{timestamp}.sqlite"))
        else:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            dst_path = os.path.abspath(output_path)
    else:
        dst_path = os.path.join(default_backup_dir, f"backup_{base_name}_{timestamp}.sqlite")

    # 3. Perform native hot backup
    start_time = time.perf_counter()
    src_conn = sqlite3.connect(src_path)
    dst_conn = sqlite3.connect(dst_path)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    file_size_bytes = os.path.getsize(dst_path)
    file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

    # 4. Rotation policy
    rotated_count = 0
    if max_backups > 0:
        backup_dir = os.path.dirname(dst_path)
        existing = []
        for fname in os.listdir(backup_dir):
            if fname.startswith(f"backup_{base_name}_") and fname.endswith(".sqlite"):
                full_cand = os.path.join(backup_dir, fname)
                try:
                    existing.append((os.path.getmtime(full_cand), full_cand))
                except Exception:
                    pass
        existing.sort(key=lambda x: x[0])
        while len(existing) > max_backups:
            oldest = existing.pop(0)[1]
            try:
                os.remove(oldest)
                rotated_count += 1
            except Exception:
                pass

    return {
        "source": src_path,
        "destination": dst_path,
        "size_bytes": file_size_bytes,
        "size_mb": file_size_mb,
        "duration_ms": duration_ms,
        "rotated": rotated_count,
    }


@app.callback(invoke_without_command=True)
def backup(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Target backup file or directory"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source SQLite file (default: from .env)"),
    max_backups: int = typer.Option(7, "--max-backups", "-m", help="Max backups to retain in target folder (default: 7)"),
):
    """
    Takes an online, zero-downtime hot backup of SQLite using sqlite3.Connection.backup().
    """
    try:
        info = run_sqlite_backup(source_db_path=source, output_path=output, max_backups=max_backups)
        typer.secho("✅ Hot SQLite Backup Complete!", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  • Source:      {info['source']}")
        typer.echo(f"  • Destination: {info['destination']}")
        typer.echo(f"  • Size:        {info['size_mb']} MB ({info['size_bytes']} bytes)")
        typer.echo(f"  • Duration:    {info['duration_ms']} ms (0 web downtime)")
        if info['rotated'] > 0:
            typer.echo(f"  • Rotated:     {info['rotated']} old backup(s) pruned")
    except Exception as exc:
        typer.secho(f"❌ Backup failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
