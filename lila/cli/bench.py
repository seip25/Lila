"""``lila bench`` — tiny dependency-free HTTP load generator.

Keep-alive HTTP/1.1 connections over asyncio streams, so the numbers measure
the server, not the client library::

    lila bench http://127.0.0.1:8000/ -c 50 -d 10
    lila bench http://127.0.0.1:8000/api/items -c 20 -d 5 --pid 12345   # + server RSS
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import List, Optional
from urllib.parse import urlsplit

import typer

def _rss_mb(pid: Optional[int]) -> Optional[float]:
    if not pid:
        return None
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


async def _worker(host, port, request: bytes, deadline: float, latencies: List[float], stats: dict, ssl):
    try:
        reader, writer = await asyncio.open_connection(host, port, ssl=ssl)
    except OSError:
        stats["errors"] += 1
        return
    try:
        while time.perf_counter() < deadline:
            start = time.perf_counter()
            writer.write(request)
            await writer.drain()
            status_line = await reader.readline()
            if not status_line:
                stats["errors"] += 1
                break
            status = int(status_line.split()[1])
            length = 0
            chunked = False
            close = False
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
                name, _, value = line.decode("latin-1").partition(":")
                lname = name.strip().lower()
                if lname == "content-length":
                    length = int(value.strip())
                elif lname == "transfer-encoding" and "chunked" in value.lower():
                    chunked = True
                elif lname == "connection" and "close" in value.lower():
                    close = True
            if chunked:
                while True:
                    size = int((await reader.readline()).strip() or b"0", 16)
                    await reader.readexactly(size + 2)
                    if size == 0:
                        break
            elif length:
                await reader.readexactly(length)
            latencies.append(time.perf_counter() - start)
            stats["status"][status] = stats["status"].get(status, 0) + 1
            if close:
                break
    except (OSError, asyncio.IncompleteReadError, ValueError):
        stats["errors"] += 1
    finally:
        writer.close()


async def run_bench(url: str, concurrency: int, duration: float, headers: List[str]) -> dict:
    parts = urlsplit(url)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    extra = "".join(f"{h}\r\n" for h in headers)
    request = (
        f"GET {path} HTTP/1.1\r\nHost: {parts.netloc}\r\nAccept: */*\r\n"
        f"Accept-Encoding: gzip\r\nConnection: keep-alive\r\n{extra}\r\n"
    ).encode("latin-1")
    ssl = True if parts.scheme == "https" else None
    latencies: List[float] = []
    stats = {"errors": 0, "status": {}}
    deadline = time.perf_counter() + duration
    started = time.perf_counter()
    await asyncio.gather(*(_worker(host, port, request, deadline, latencies, stats, ssl) for _ in range(concurrency)))
    elapsed = time.perf_counter() - started
    latencies.sort()

    def pct(p):
        return round(latencies[min(len(latencies) - 1, int(len(latencies) * p))] * 1000, 2) if latencies else None

    return {
        "requests": len(latencies),
        "rps": round(len(latencies) / elapsed, 1) if elapsed else 0,
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "errors": stats["errors"],
        "status": stats["status"],
    }


def bench(
    url: str = typer.Argument("http://127.0.0.1:8000/", help="URL to request (GET)."),
    concurrency: int = typer.Option(20, "--concurrency", "-c", help="Parallel keep-alive connections."),
    duration: float = typer.Option(5.0, "--duration", "-d", help="Seconds to run."),
    header: List[str] = typer.Option([], "--header", "-H", help='Extra header, e.g. -H "Cookie: session=..."'),
    pid: Optional[int] = typer.Option(None, "--pid", help="Server PID to report its RSS (Linux)."),
):
    """Measure requests/s and latency of a running server (no extra dependencies)."""
    rss_before = _rss_mb(pid)
    result = asyncio.run(run_bench(url, concurrency, duration, header))
    rss_after = _rss_mb(pid)
    typer.secho(f"\n⚡ {url}  ({concurrency} connections, {duration:g}s)", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  Requests:   {result['requests']}  ({result['rps']} req/s)")
    typer.echo(f"  Latency:    p50 {result['p50_ms']} ms · p95 {result['p95_ms']} ms · p99 {result['p99_ms']} ms")
    typer.echo(f"  Status:     {result['status']}  errors: {result['errors']}")
    if rss_after is not None:
        typer.echo(f"  Server RSS: {rss_before} MB → {rss_after} MB")
