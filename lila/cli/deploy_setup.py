"""Interactive Linux production setup: ``sudo lila deploy setup``.

Asks one question at a time (like ``lila init``), using the values in
``.env`` as defaults, then:

1. fixes ``.env`` for production (DEBUG=False, HOST=127.0.0.1, APP_URL)
   after asking, with a ``.env.bak`` backup (SECRET_KEY is never rotated
   here: it would sign out every user; a weak key only produces a warning);
2. generates ``deploy/`` (systemd units, Nginx site, start script);
3. installs and starts the systemd service(s);
4. installs the Nginx site, validates it with ``nginx -t`` (rolls back on
   failure) and reloads Nginx;
5. optionally requests a Let's Encrypt certificate with Certbot;
6. offers to fix permissions in the same session (project owner, Nginx
   access to ``public/``, ``.env`` readable only by the service user);
7. checks that the app answers on its internal port.

Every system command is printed before it runs. ``--dry-run`` only prints
them, ``--yes`` accepts every default (for automation).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

import typer

# ──────────────────────────────────────────────────────────────────────────────
# Messages (en/es). Picked from LANG_DEFAULT in .env, then $LANG.
# ──────────────────────────────────────────────────────────────────────────────
_MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Lila production setup (Linux)",
        "not_linux": "This assistant only supports Linux servers (systemd + Nginx). Use `lila deploy` to generate files.",
        "not_root": "Not running as root: files will be generated and every command printed, but nothing is installed.\nRun again with sudo to install:  sudo {lila} deploy setup",
        "no_env": "No .env found in {path}. Run this command from your project root.",
        "debug_on": "DEBUG is True in .env. Set DEBUG=False for production?",
        "host_public": "HOST is {host}. Bind the app to 127.0.0.1 (only Nginx can reach it)?",
        "secret_weak": "SECRET_KEY is empty, short or a placeholder. It is not changed here (a new key would sign out every user): Lila keeps a persistent .lila_secret; to set your own run `lila secret-key` before the first deploy.",
        "fix_owner": "{path} is owned by '{owner}' but the service runs as '{user}' (it writes the database, logs, cache and uploads). Run `chown -R {user}:{user} {path}` now?",
        "fix_public": "Nginx ({nginx_user}) cannot read {path}/public (a parent folder lacks the execute bit), static files would return 403. Run `chmod o+x` on {dirs} and `chmod -R o+rX public` now?",
        "fix_env": ".env is readable by other users (it contains secrets). Restrict it to '{user}' (`chown {user} .env && chmod 600 .env`) now?",
        "domain": "Domain (without http://)",
        "domain_required": "--yes needs a real domain: set APP_URL=\"https://your-domain.com\" in .env or run without --yes.",
        "www": "Also serve www.{domain}?",
        "port": "Internal port for the app",
        "service": "systemd service name",
        "service_from_env": "Use the service name from .env ({name})?",
        "user": "Linux user that runs the app",
        "workers": "Number of workers",
        "workers_warn": "More than 1 worker with CACHE_DRIVER={driver}: sessions and rate limits are per process. Redis is recommended.",
        "worker_unit": "Install the background worker (lila worker) service?",
        "nginx": "Install the Nginx site?",
        "nginx_missing": "Nginx is not installed. Install it now with apt-get?",
        "nginx_default": "Disable the Nginx default site (recommended when this is the only site)?",
        "https": "Request a free HTTPS certificate with Certbot (Let's Encrypt)?",
        "email": "E-mail for Let's Encrypt notices",
        "certbot_missing": "Certbot is not installed. Install certbot + python3-certbot-nginx with apt-get?",
        "summary": "Summary",
        "proceed": "Apply these changes?",
        "aborted": "Aborted, nothing was changed.",
        "env_saved": ".env updated (backup: .env.bak)",
        "files": "Deployment files generated in {path}",
        "perm_warn": "Nginx ({nginx_user}) may not be able to read {path} (missing execute permission on a parent folder). Static files would return 403; move the project (e.g. /srv/{name}) or run: chmod o+x on the parent folders.",
        "owner_warn": "{path} is owned by '{owner}', but the service runs as '{user}'. The app needs write access to its database, logs and uploads.",
        "nginx_test_failed": "nginx -t failed, the new site was disabled again. Check the output above.",
        "health_ok": "The app answers on http://127.0.0.1:{port}/ (HTTP {status}).",
        "health_fail": "The app does not answer on port {port} yet. Check: sudo journalctl -u {service} -n 50",
        "done": "Done! Your site: {url}",
        "dry_run": "Dry run: nothing was installed. Commands that would run are listed above.",
        "yes_no": "[Y/n]",
        "no_yes": "[y/N]",
    },
    "es": {
        "title": "Configuración de producción de Lila (Linux)",
        "not_linux": "Este asistente solo soporta servidores Linux (systemd + Nginx). Usá `lila deploy` para generar los archivos.",
        "not_root": "No se está ejecutando como root: se generan los archivos y se muestran los comandos, pero no se instala nada.\nEjecutá de nuevo con sudo para instalar:  sudo {lila} deploy setup",
        "no_env": "No se encontró .env en {path}. Ejecutá este comando desde la raíz del proyecto.",
        "debug_on": "DEBUG está en True en .env. ¿Cambiarlo a DEBUG=False para producción?",
        "host_public": "HOST es {host}. ¿Escuchar solo en 127.0.0.1 (solo Nginx accede a la app)?",
        "secret_weak": "SECRET_KEY está vacía, es corta o es de ejemplo. No se cambia aquí (una clave nueva cerraría la sesión de todos): Lila mantiene un .lila_secret persistente; para usar tu propia clave ejecutá `lila secret-key` antes del primer despliegue.",
        "fix_owner": "{path} pertenece a '{owner}' pero el servicio corre como '{user}' (escribe la base de datos, logs, caché y uploads). ¿Ejecutar `chown -R {user}:{user} {path}` ahora?",
        "fix_public": "Nginx ({nginx_user}) no puede leer {path}/public (a una carpeta padre le falta el permiso de ejecución), los estáticos darían 403. ¿Ejecutar `chmod o+x` en {dirs} y `chmod -R o+rX public` ahora?",
        "fix_env": ".env lo pueden leer otros usuarios (tiene secretos). ¿Restringirlo a '{user}' (`chown {user} .env && chmod 600 .env`) ahora?",
        "domain": "Dominio (sin http://)",
        "domain_required": "--yes necesita un dominio real: poné APP_URL=\"https://tu-dominio.com\" en .env o ejecutá sin --yes.",
        "www": "¿Servir también www.{domain}?",
        "port": "Puerto interno de la app",
        "service": "Nombre del servicio systemd",
        "service_from_env": "¿Usar el nombre de servicio de .env ({name})?",
        "user": "Usuario Linux que ejecuta la app",
        "workers": "Cantidad de workers",
        "workers_warn": "Más de 1 worker con CACHE_DRIVER={driver}: sesiones y rate limits son por proceso. Se recomienda Redis.",
        "worker_unit": "¿Instalar el servicio del worker en segundo plano (lila worker)?",
        "nginx": "¿Instalar el sitio de Nginx?",
        "nginx_missing": "Nginx no está instalado. ¿Instalarlo ahora con apt-get?",
        "nginx_default": "¿Desactivar el sitio por defecto de Nginx (recomendado si es el único sitio)?",
        "https": "¿Pedir un certificado HTTPS gratis con Certbot (Let's Encrypt)?",
        "email": "E-mail para avisos de Let's Encrypt",
        "certbot_missing": "Certbot no está instalado. ¿Instalar certbot + python3-certbot-nginx con apt-get?",
        "summary": "Resumen",
        "proceed": "¿Aplicar estos cambios?",
        "aborted": "Cancelado, no se cambió nada.",
        "env_saved": ".env actualizado (copia: .env.bak)",
        "files": "Archivos de despliegue generados en {path}",
        "perm_warn": "Nginx ({nginx_user}) puede no tener acceso de lectura a {path} (falta permiso de ejecución en una carpeta padre). Los estáticos darían 403; mové el proyecto (ej. /srv/{name}) o ejecutá chmod o+x en las carpetas padre.",
        "owner_warn": "{path} pertenece a '{owner}', pero el servicio corre como '{user}'. La app necesita escribir su base de datos, logs y uploads.",
        "nginx_test_failed": "nginx -t falló, se desactivó el sitio nuevo. Revisá la salida anterior.",
        "health_ok": "La app responde en http://127.0.0.1:{port}/ (HTTP {status}).",
        "health_fail": "La app todavía no responde en el puerto {port}. Revisá: sudo journalctl -u {service} -n 50",
        "done": "¡Listo! Tu sitio: {url}",
        "dry_run": "Simulación: no se instaló nada. Arriba están los comandos que se ejecutarían.",
        "yes_no": "[S/n]",
        "no_yes": "[s/N]",
    },
}

_YES = {"y", "yes", "s", "si", "sí", "1", "true"}
_NO = {"n", "no", "0", "false"}


def _pick_lang(env: Dict[str, str]) -> str:
    raw = (env.get("LANG_DEFAULT") or os.environ.get("LANG") or "en")[:2].lower()
    return raw if raw in _MESSAGES else "en"


# ──────────────────────────────────────────────────────────────────────────────
# .env helpers (keep comments/order; only touch the given keys)
# ──────────────────────────────────────────────────────────────────────────────
def read_env_file(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not os.path.isfile(path):
        return values
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip()
            if value[:1] in ("'", '"') and value.endswith(value[:1]) and len(value) >= 2:
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].strip()
            values[key] = value
    return values


def update_env_file(path: str, updates: Dict[str, str], backup: bool = True) -> None:
    """Sets ``KEY="value"`` for each update, preserving every other line."""
    lines: List[str] = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        if backup:
            shutil.copy2(path, f"{path}.bak")
    pending = dict(updates)
    pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match and match.group(1) in pending:
            key = match.group(1)
            lines[i] = f'{key}="{pending.pop(key)}"'
    for key, value in pending.items():
        lines.append(f'{key}="{value}"')
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def _is_weak_secret(value: str) -> bool:
    from lila.core.config import _is_placeholder_secret

    return not value or len(value) < 32 or _is_placeholder_secret(value)


def _slug(value: str, fallback: str = "lila-app") -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").lower()).strip("-_")
    return cleaned[:60] or fallback


def _domain_from(app_url: str) -> str:
    if not app_url:
        return ""
    parsed = urlparse(app_url if "://" in app_url else f"http://{app_url}")
    host = (parsed.netloc or "").split(":")[0]
    return "" if host in ("127.0.0.1", "localhost", "0.0.0.0") else host


# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Prompter:
    messages: Dict[str, str]
    assume_yes: bool = False
    input_fn: Callable[[str], str] = input

    def t(self, key: str, **kwargs) -> str:
        return self.messages[key].format(**kwargs)

    def confirm(self, key: str, default: bool = True, **kwargs) -> bool:
        question = self.t(key, **kwargs)
        hint = self.messages["yes_no"] if default else self.messages["no_yes"]
        if self.assume_yes:
            typer.echo(f"? {question} {hint} {'S' if default else 'N'}")
            return default
        while True:
            answer = self.input_fn(f"? {question} {hint} ").strip().lower()
            if not answer:
                return default
            if answer in _YES:
                return True
            if answer in _NO:
                return False

    def ask(self, key: str, default: str = "", validator: Optional[Callable[[str], bool]] = None, **kwargs) -> str:
        question = self.t(key, **kwargs)
        if self.assume_yes:
            typer.echo(f"? {question} [{default}] {default}")
            return default
        while True:
            answer = self.input_fn(f"? {question} [{default}] ").strip() or default
            if validator is None or validator(answer):
                return answer


# ──────────────────────────────────────────────────────────────────────────────
# System actions
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Runner:
    dry_run: bool = False
    log: List[str] = field(default_factory=list)

    def run(self, cmd: List[str], check: bool = True) -> bool:
        printable = " ".join(cmd)
        self.log.append(printable)
        typer.secho(f"  $ {printable}", fg=typer.colors.BRIGHT_BLACK)
        if self.dry_run:
            return True
        result = subprocess.run(cmd)
        if result.returncode != 0 and check:
            typer.secho(f"  ✗ exit code {result.returncode}", fg=typer.colors.RED)
        return result.returncode == 0

    def copy(self, src: str, dest: str) -> None:
        self.log.append(f"cp {src} {dest}")
        typer.secho(f"  $ cp {src} {dest}", fg=typer.colors.BRIGHT_BLACK)
        if not self.dry_run:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(src, dest)
            os.chmod(dest, 0o644)

    def symlink(self, src: str, dest: str) -> None:
        self.log.append(f"ln -sf {src} {dest}")
        typer.secho(f"  $ ln -sf {src} {dest}", fg=typer.colors.BRIGHT_BLACK)
        if not self.dry_run:
            if os.path.lexists(dest):
                os.remove(dest)
            os.symlink(src, dest)

    def remove(self, path: str) -> None:
        self.log.append(f"rm {path}")
        typer.secho(f"  $ rm {path}", fg=typer.colors.BRIGHT_BLACK)
        if not self.dry_run and os.path.lexists(path):
            os.remove(path)


def _untraversable_dirs(path: str) -> List[str]:
    """Folders (path and parents) that 'other' users (Nginx) cannot traverse."""
    blocked: List[str] = []
    current = os.path.abspath(path)
    if not os.path.isdir(current):
        current = os.path.dirname(current)
    while True:
        try:
            if not (os.stat(current).st_mode & 0o001):
                blocked.append(current)
        except OSError:
            pass
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return list(reversed(blocked))


def _nginx_readable(path: str) -> bool:
    """True when every parent folder is traversable by 'other' users."""
    return not _untraversable_dirs(path)


def _env_too_open(path: str) -> bool:
    try:
        return bool(os.stat(path).st_mode & 0o077)
    except OSError:
        return False


def _owner_name(path: str) -> str:
    try:
        import pwd

        return pwd.getpwuid(os.stat(path).st_uid).pw_name
    except Exception:
        return ""


def _default_user() -> str:
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "www-data"


def _healthcheck(port: int, attempts: int = 10) -> Optional[int]:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as res:
                return res.status
        except urllib.error.HTTPError as err:  # 404/401 still means "it's up"
            return err.code
        except Exception:
            time.sleep(1)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Wizard
# ──────────────────────────────────────────────────────────────────────────────
def run_setup(
    project_dir: str,
    assume_yes: bool = False,
    dry_run: bool = False,
    etc_root: str = "/etc",
    input_fn: Callable[[str], str] = input,
    is_root: Optional[bool] = None,
    skip_platform_check: bool = False,
) -> Dict[str, object]:
    """Runs the interactive setup. Returns the collected answers (for tests)."""
    from lila.cli.deploy import generate_deploy_files

    project_dir = os.path.abspath(project_dir)
    env_path = os.path.join(project_dir, ".env")
    env = read_env_file(env_path)
    p = Prompter(_MESSAGES[_pick_lang(env)], assume_yes=assume_yes, input_fn=input_fn)

    if not skip_platform_check and not sys.platform.startswith("linux"):
        typer.secho(p.t("not_linux"), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not os.path.isfile(env_path):
        typer.secho(p.t("no_env", path=project_dir), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if is_root is None:
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    if not is_root:
        dry_run = True
        typer.secho(p.t("not_root", lila=shutil.which("lila") or "lila"), fg=typer.colors.YELLOW)

    typer.secho(f"\n🌸 {p.t('title')}\n", fg=typer.colors.MAGENTA, bold=True)

    # 1. .env production values
    env_updates: Dict[str, str] = {}
    if str(env.get("DEBUG", "")).strip().lower() in ("true", "1", "yes", "on"):
        if p.confirm("debug_on", True):
            env_updates["DEBUG"] = "False"
    if env.get("APP_ENV", "") not in ("production",) and env_updates.get("DEBUG") == "False":
        env_updates["APP_ENV"] = "production"
    host = env.get("HOST", "127.0.0.1") or "127.0.0.1"
    if host not in ("127.0.0.1", "localhost"):
        if p.confirm("host_public", True, host=host):
            env_updates["HOST"] = "127.0.0.1"
    if _is_weak_secret(env.get("SECRET_KEY", "")):
        # Never rotated automatically: a new key invalidates every session.
        typer.secho(f"  ⚠️  {p.t('secret_weak')}", fg=typer.colors.YELLOW)

    # 2. Site / service values
    domain_default = _domain_from(env.get("APP_URL", ""))
    if not domain_default and assume_yes:
        typer.secho(p.t("domain_required"), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    domain_default = domain_default or "example.com"
    domain = p.ask(
        "domain",
        domain_default,
        validator=lambda v: bool(re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}|localhost", v)),
    )
    domain = domain.lower().replace("http://", "").replace("https://", "").strip("/")
    with_www = False
    if not domain.startswith("www.") and domain.count(".") == 1:
        with_www = p.confirm("www", True, domain=domain)

    port = int(p.ask("port", str(env.get("PORT") or 3002), validator=lambda v: v.isdigit() and 1 <= int(v) <= 65535))
    if str(port) != str(env.get("PORT", "")):
        env_updates["PORT"] = str(port)

    env_service = env.get("SERVICE_NAME", "")
    if env_service and p.confirm("service_from_env", True, name=env_service):
        service = _slug(env_service)
    else:
        default_service = _slug(env.get("TITLE_PROJECT") or os.path.basename(project_dir))
        service = _slug(p.ask("service", default_service))
    if service != env_service:
        env_updates["SERVICE_NAME"] = service

    run_user = p.ask("user", _default_user(), validator=lambda v: bool(re.fullmatch(r"[a-z_][a-z0-9_-]*\$?", v)))
    cache_driver = str(env.get("CACHE_DRIVER", "memory")).lower()
    workers = int(p.ask("workers", "2" if cache_driver == "redis" else "1", validator=lambda v: v.isdigit() and int(v) >= 1))
    if workers > 1 and cache_driver != "redis":
        typer.secho(f"  ⚠️  {p.t('workers_warn', driver=cache_driver)}", fg=typer.colors.YELLOW)
    with_worker = cache_driver == "redis" and p.confirm("worker_unit", False)

    use_nginx = p.confirm("nginx", True)
    install_nginx = use_nginx and not shutil.which("nginx") and p.confirm("nginx_missing", True)
    sites_enabled = os.path.join(etc_root, "nginx", "sites-enabled")
    disable_default = (
        use_nginx
        and os.path.lexists(os.path.join(sites_enabled, "default"))
        and p.confirm("nginx_default", False)
    )

    use_https = use_nginx and domain != "localhost" and p.confirm("https", True)
    email = ""
    install_certbot = False
    if use_https:
        email = p.ask("email", env.get("MAIL_FROM", "") or env.get("ADMIN_EMAIL", "") or f"admin@{domain}",
                      validator=lambda v: bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v)))
        install_certbot = not shutil.which("certbot") and p.confirm("certbot_missing", True)

    # Permissions (asked now, applied after the files are generated)
    fix_owner = False
    owner = _owner_name(project_dir)
    if owner and owner != run_user:
        fix_owner = p.confirm("fix_owner", True, path=project_dir, owner=owner, user=run_user)
    blocked_dirs = _untraversable_dirs(os.path.join(project_dir, "public")) if use_nginx else []
    fix_public = bool(blocked_dirs) and p.confirm(
        "fix_public", True, nginx_user="www-data", path=project_dir, dirs=" ".join(blocked_dirs)
    )
    fix_env = _env_too_open(env_path) and p.confirm("fix_env", True, user=run_user)

    scheme = "https" if use_https else "http"
    app_url = f"{scheme}://{domain}"
    if env.get("APP_URL", "").rstrip("/") != app_url:
        env_updates["APP_URL"] = app_url

    # 3. Summary
    typer.secho(f"\n{p.t('summary')}", fg=typer.colors.CYAN, bold=True)
    for label, value in (
        ("Project", project_dir),
        ("Domain", domain + (f" + www.{domain}" if with_www else "")),
        ("URL", app_url),
        ("Port", port),
        ("Service", f"{service}.service" + (f" + {service}-worker.service" if with_worker else "")),
        ("User", run_user),
        ("Workers", workers),
        ("Nginx", "yes" if use_nginx else "no"),
        ("HTTPS", f"certbot ({email})" if use_https else "no"),
        (".env", ", ".join(f"{k}={'***' if k == 'SECRET_KEY' else v}" for k, v in env_updates.items()) or "-"),
    ):
        typer.echo(f"  • {label:<8} {value}")
    if not p.confirm("proceed", True):
        typer.secho(p.t("aborted"), fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    runner = Runner(dry_run=dry_run)
    typer.echo("")

    # 4. .env (writes even in dry-run when not root? no: only when applying)
    if env_updates and not dry_run:
        update_env_file(env_path, env_updates)
        typer.secho(f"✅ {p.t('env_saved')}", fg=typer.colors.GREEN)

    # 5. Generate files
    out_dir = os.path.join(project_dir, "deploy")
    info = generate_deploy_files(
        output_dir=out_dir,
        domain=domain,
        port=port,
        user=run_user,
        group=run_user,
        workers=workers,
        service_name=service,
        with_worker=with_worker,
        project_dir=project_dir,
        extra_server_names=[f"www.{domain}"] if with_www else None,
    )
    typer.secho(f"✅ {p.t('files', path=out_dir)}", fg=typer.colors.GREEN)

    # Permissions: run the fixes the user accepted, warn about the rest.
    if fix_owner:
        runner.run(["chown", "-R", f"{run_user}:{run_user}", project_dir])
    elif owner and owner != run_user:
        typer.secho(f"  ⚠️  {p.t('owner_warn', path=project_dir, owner=owner, user=run_user)}", fg=typer.colors.YELLOW)
    if fix_public:
        runner.run(["chmod", "o+x", *blocked_dirs])
        public_dir = os.path.join(project_dir, "public")
        if os.path.isdir(public_dir):
            runner.run(["chmod", "-R", "o+rX", public_dir])
    elif blocked_dirs:
        typer.secho(
            f"  ⚠️  {p.t('perm_warn', nginx_user='www-data', path=project_dir, name=service)}",
            fg=typer.colors.YELLOW,
        )
    if fix_env:
        runner.run(["chown", f"{run_user}:{run_user}", env_path])
        runner.run(["chmod", "600", env_path])
        if os.path.isfile(f"{env_path}.bak"):
            runner.run(["chmod", "600", f"{env_path}.bak"])

    # 6. systemd
    systemd_dir = os.path.join(etc_root, "systemd", "system")
    runner.copy(info["service_path"], os.path.join(systemd_dir, f"{service}.service"))
    if info.get("worker_service_path"):
        runner.copy(str(info["worker_service_path"]), os.path.join(systemd_dir, f"{service}-worker.service"))
    runner.run(["systemctl", "daemon-reload"])
    runner.run(["systemctl", "enable", "--now", f"{service}.service"])
    runner.run(["systemctl", "restart", f"{service}.service"])
    if with_worker:
        runner.run(["systemctl", "enable", "--now", f"{service}-worker.service"])

    # 7. Nginx
    nginx_ok = True
    if use_nginx:
        if install_nginx:
            runner.run(["apt-get", "update"])
            runner.run(["apt-get", "install", "-y", "nginx"])
        available = os.path.join(etc_root, "nginx", "sites-available")
        conf_name = f"{domain}.conf"
        if os.path.isdir(available) or dry_run or install_nginx:
            target = os.path.join(available, conf_name)
            enabled = os.path.join(sites_enabled, conf_name)
            runner.copy(info["nginx_path"], target)
            runner.symlink(target, enabled)
        else:  # RHEL/Fedora/Alpine layout
            enabled = os.path.join(etc_root, "nginx", "conf.d", conf_name)
            runner.copy(info["nginx_path"], enabled)
        if disable_default:
            runner.remove(os.path.join(sites_enabled, "default"))
        if runner.run(["nginx", "-t"]):
            runner.run(["systemctl", "reload", "nginx"])
        else:
            nginx_ok = False
            runner.remove(enabled)
            typer.secho(f"  ✗ {p.t('nginx_test_failed')}", fg=typer.colors.RED)

    # 8. Certbot
    if use_https and nginx_ok:
        if install_certbot:
            runner.run(["apt-get", "install", "-y", "certbot", "python3-certbot-nginx"])
        cmd = ["certbot", "--nginx", "--non-interactive", "--agree-tos", "--redirect", "-m", email, "-d", domain]
        if with_www:
            cmd += ["-d", f"www.{domain}"]
        runner.run(cmd)

    # 9. Health check
    if not dry_run:
        status = _healthcheck(port)
        if status is None:
            typer.secho(f"  ⚠️  {p.t('health_fail', port=port, service=service)}", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"✅ {p.t('health_ok', port=port, status=status)}", fg=typer.colors.GREEN)
        typer.secho(f"\n🚀 {p.t('done', url=app_url)}", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho(f"\nℹ️  {p.t('dry_run')}", fg=typer.colors.CYAN)

    return {
        "domain": domain,
        "with_www": with_www,
        "port": port,
        "service": service,
        "user": run_user,
        "workers": workers,
        "with_worker": with_worker,
        "nginx": use_nginx,
        "https": use_https,
        "email": email,
        "env_updates": env_updates,
        "commands": runner.log,
        "dry_run": dry_run,
    }
