# Changelog

All notable changes to Lila Framework. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [2.0.2] — 2026-10-31

### Added

- **High-Performance Core Dependencies**: Added `httptools>=0.6.0` and `uvloop>=0.20.0; sys_platform != 'win32'` to `pyproject.toml`, giving +35% to +50% RPS boost on Linux/macOS out-of-the-box.
- **Pre-Compiled Routing Validations (`TypeAdapter`)**: Parameter validation in `RouteInspector` (`RouteParam`) builds `pydantic.TypeAdapter` once at route registration time, running request-time validation directly in Rust (`pydantic-core`).
- **Memory Optimization (`__slots__`)**: Added `__slots__` to `Request`, `RouteInspector`, `RouteParam`, and all Pure ASGI Middlewares (`PureASGICSRFMiddleware`, `PureASGISecurityHeadersMiddleware`, `PureASGIGZipMiddleware`, `PureASGIStaticCacheMiddleware`, `PureASGIRateLimitMiddleware`, `PureASGILoggingMiddleware`), significantly reducing `__dict__` allocations and GC pressure.
- **SQLite Performance Pragmas**: Added `PRAGMA mmap_size = 67108864;` (64 MB memory-mapped I/O) and verified `PRAGMA temp_store = MEMORY;` on connection setup.
- **Vary Headers for Safe SPA Caching**: Responses on cached routes and partial SPA templates now emit `Vary: Accept, X-Lila-Partial, Cookie`, preventing CDNs and browser caches from showing partial or stale responses.
- **Hot SQLite Backups (`lila backup`)**: Online, zero-downtime hot backups using native `sqlite3.Connection.backup()` with automatic retention rotation (`--max-backups`).
- **Pre-Compressed Static Assets (`.gz`)**: `lila optimize` automatically generates `.gz` (and `.br` when available) files for static assets, and `lila deploy` enables `gzip_static on;` in Nginx for 0% CPU static delivery.
- **Desktop Single Instance Lock & Security**: Mutex/flock locking prevents starting duplicate desktop instances, binds strictly to `127.0.0.1`, generates local session security tokens (`_dt`), and exposes a native `DesktopBridge` via `window.pywebview.api`.
- **Unified Zero-Dependency Telemetry**: `get_system_metrics()` in `lila.core.debug` with 1.0s monotonic caching, psutil singleton, and native OS fallbacks (Windows `ctypes`, Linux `/proc`, macOS `resource.getrusage`).
- **Live `/debug` Console**: Real-time reactive metrics cards, status and method filters, multi-column sorting (newest, slowest, highest RAM, status code), error counter, and per-request process RAM tracking (`ram_mb`).
- **Production CLI (`lila deploy`)**: Generates production-ready configurations in `deploy/` including `start_lila.sh`, systemd service unit, background worker service unit, optimized Nginx reverse proxy with WebSocket support, and Windows Server `start_lila.ps1`.
- **Proxy Headers in `lila run`**: Added `--proxy-headers` and `--forwarded-allow-ips` to respect `X-Forwarded-*` headers behind Nginx and Cloudflare.
- **Portuguese Locale (`pt.json`)**: Full 100% key parity and zero empty values across all 4 built-in locales (`en`, `es`, `pt`, `zh`).
- **Expanded Test Suite**: 14 new regression tests covering Admin CRUD coercion, hot SQLite backups, desktop bridge/locking, native metrics fallbacks, 4-locale parity, and deploy configuration generation (39 tests total).

### Fixed

- **Admin Panel Modals**: Centered dialogs (`m-auto fixed inset-0`) preventing Tailwind margin reset issues; moved modal and scripts inside `[data-lila-outlet]` for seamless SPA navigation.
- **Admin CRUD Coercion**: Implemented `_coerce_payload_for_model` for robust SQLite and MySQL type casting (integers, booleans, floats, dates, auto-hashing passwords, and preserving password hashes on updates with empty string inputs).
- **Dark Mode & Tailwind Styles**: Added `@custom-variant dark`, defined missing `--shadow-lila-*` CSS variables, unified duplicate `.card` and `.btn` classes, and synchronized `data-theme` attribute with `.dark` class.
- **Eliminated Spanglish**: Replaced all hardcoded English strings in `lila auth` scaffolds and 404 templates with localized translation keys; added `LANG_FORCE` support in `Translate.lang()`.
- **Desktop Mode Startup & Bundling**: Fixed secondary thread signal handler crash on Windows (`server.install_signal_handlers = lambda: None`), added loopback TCP polling, robust browser process fallback with graceful shutdown, persistent OS-specific frozen data paths, and fixed PyInstaller bundle packaging by registering `lila` root paths (`--paths`, `--collect-all lila`) and runtime `sys._MEIPASS` setup in bootstrap code to eliminate `ModuleNotFoundError: No module named 'lila.core'`.
- **Landing Page Route Discovery**: Dynamically discovers `/docs`, `/admin`, `/login`, and `/debug` routes from `request.app` to conditionally render navbar and CTA links.

## [2.0.1] — 2026-10-30

### Fixed

- CLI no longer corrupts `main.py`: safe bracket-aware patching is compiled before
  writing, with backups for overwritten scaffold files.
- Empty/placeholder `SECRET_KEY` can no longer forge sessions, admin cookies or
  CSRF tokens; Lila persists `.lila_secret` (0600) and warns.
- Admin login uses the project database, CSRF, rate limiting and Argon2id; the
  dashboard renders real metrics and logs. Admin CRUD applies a column whitelist,
  hides password fields and exports CSV with formula escaping and UTF-8 BOM.
- OAuth sessions never contain password hashes; only id/email/name/avatar.
- `DEBUG` is parsed as a boolean. `DEBUG=False` no longer leaks tracebacks.
- CSRF works for classic forms, JSON bodies and `X-CSRF-Token`; query-string
  tokens are rejected.
- Migrations create missing tables **and add missing columns** (including
  `NOT NULL` columns with scalar defaults). `--refresh` really drops tables and
  asks for confirmation unless `--yes` is given.
- Uploads are streamed to `public/uploads`, served at `/uploads`, return no
  absolute paths, block SVG by default and convert supported images to WebP.
- The Redis worker uses JSON tasks, retries and a dead-letter queue; it no longer
  requires pickle or a nonexistent cache method.
- Desktop builds statically include `main`, `app`, Lila data files and `public/`.
- Cache drivers: memory by default, Redis only when the package is installed and
  the server responds, file fallback. Cache clearing preserves sessions by default.
- Route caches are isolated per identity; typed path/query parameters return 422
  instead of 500; `include_router(prefix=...)` works and list routes appear in
  OpenAPI.
- `lila optimize` output is consumed by `public()`; assets get a `?v=mtime`
  cache-busting query. JS/CSS minification requires `rjsmin`/`rcssmin` and is
  skipped rather than corrupted when absent.
- `lila seo` discovers public GET routes, escapes XML and serves
  `/sitemap.xml` + `/robots.txt` from the site root.
- `lila worker`, `lila run`, `lila doctor` and `lila routes` are real commands.
- SQLite uses WAL, `busy_timeout`, a smaller per-connection cache, and URL-encoded
  database credentials for MySQL/PostgreSQL.
- Static assets get `Cache-Control`; gzip is available; the dev SSE stream is not
  compressed.
- Removed Google Fonts and the Chart.js CDN from bundled templates; the logo is
  served as a small WebP.

### Added

- `@seo` / `SEO_CONFIG`, `RequestParser` compatibility module, `create_decorator`
  and `validate_token` exports.
- `lila doctor`, `lila routes`, `lila run`, `lila secret-key`, file cache driver,
  `py.typed`, `SECURITY.md`, this changelog and a unittest suite.
- `/debug` dashboard (`debug_html=True`) with request history and system metrics.
- Simplified Chinese locale (`zh`) and flat JSON locale files.

### Changed

- Minimum Python is **3.10**; Starlette is capped at `<2` and Uvicorn at `<1`.
- `import lila` is lazy (PEP 562); `App` loads `.env` by itself.
- `BaseModel.to_dict()` returns only loaded columns and skips `__private_fields__`;
  sync methods work outside an event loop, async methods are preferred.
- `Session` payloads over ~3 KB are stored server-side with a signed `sid` cookie.
- Default `DEBUG` is `False` when no `.env` is present; scaffolds still create a
  development `.env` with `DEBUG=True`.

## [2.0.0] — 2026-10-01

Initial 2.0 rewrite: pure ASGI app, typed routing, SQLite WAL, SPA client,
Jinja templates, admin and auth scaffolds, AI helper and desktop mode.
