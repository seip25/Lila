# Changelog

All notable changes to Lila Framework. The format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [2.2.4] — 2026-11-23

### Added

- **Opt-in Desktop LAN Gateway with OTP Pairing** (`lila.core.desktop_lan`):
  - Keeps desktop servers strictly bound to `127.0.0.1` behind
    `LILA_DESKTOP_TOKEN`, and exposes an opt-in LAN reverse proxy (`0.0.0.0`)
    for mobile/QR pairing or local Three.js/game peers (`--lan`, `--lan-port`,
    `--lan-otp-ttl`, or `.env` `DESKTOP_LAN=True`).
  - Pairs devices via `/_lila/lan/pair` using a time-limited 6-digit OTP PIN
    (with 5-attempt lockout), sets a signed `HttpOnly` `lila_lan` cookie tied to
    revocable sessions, strips client-spoofed forwarding headers, injects
    trusted `X-Forwarded-For`, `request.state.is_lan` / `lan_client_ip()`,
    supports `DESKTOP_LAN_ALLOW` / `DESKTOP_LAN_DENY`, and proxies HTTP, SSE, and
    WebSockets seamlessly.
  - Added runtime controls to `DesktopBridge` and `@lila/desktop`:
    `desktop.lanStatus()`, `desktop.startLan()`, `desktop.stopLan()`,
    `desktop.rotateLanOtp()`, `desktop.revokeLanSessions()`, and
    `desktop.createBackup()`.
- **Pre-Migration Hot SQLite Backups & Versioned Migration Scripts**
  (`lila.core.migrations`):
  - Before applying schema changes or migration scripts on existing SQLite
    databases, `lila migrate` and frozen `auto_migrate_async()` automatically
    take a hot `sqlite3.Connection.backup()` into `backups/pre_migrate/` with
    configurable retention (`LILA_MIGRATE_BACKUP=True`,
    `LILA_MIGRATE_BACKUP_KEEP=10`).
  - Added ordered Python migration scripts in `app/migrations/*.py`
    (`upgrade(db)`, sync or async), tracked in `lila_script_migrations`, shown
    in `lila migrate --plan`, and bundled automatically into desktop builds via
    `LILA_DESKTOP_MIGRATIONS`.

## [2.2.3] — 2026-11-23

### Fixed

- **Clean SSE & Uvicorn shutdown (no hanging process on open browser tabs)**:
  - `lila run`, `lila dev`, scaffolded `main.py`, and `lila desktop dev|build`
    now pass `timeout_graceful_shutdown` (`LILA_GRACEFUL_TIMEOUT`, default
    `5`s, overridable via `--graceful-timeout`) to Uvicorn so open SSE/WebSocket
    tabs never block `Ctrl+C` or service restarts indefinitely.
  - Added cooperative `signal_shutdown()` / `reset_shutdown()` /
    `is_shutting_down()` in `lila.core.sse`, wired into `App` lifecycle and CLI
    runners, and suppressed noisy `asyncio.CancelledError` tracebacks on stream
    close in `EventStream` and `_dev_reload_endpoint`.
- **`from __future__ import annotations` in route modules**: `RouteInspector`
  now resolves postponed string annotations via `typing.get_type_hints()` (with
  fallback promotion when `model=` is explicitly passed), preventing false
  `422 data: Field required` errors on Pydantic body parameters.
- **Dual-targeted routes on the same path**: `App._apply_targets` no longer
  marks a path as unavailable when one handler is `desktop=False` and another
  active handler on the same path is `desktop="only"` (e.g. web `/` vs desktop
  `/`).

## [2.2.2] — 2026-11-23

### Added

- **Opt-in Desktop Bug Reports & Anonymous Telemetry** (`lila.core.desktop_reports`):
  - `App(..., desktop_reports=True | {...})` mounts `POST /api/desktop/bug`,
    `POST /api/desktop/telemetry`, `GET /api/desktop/reports`, and
    `GET /api/desktop/reports/stats` (disabled by default, tagged `desktop=False`
    so `.exe` builds exclude them and `lila desktop routes` shows them).
  - Isolated SQLite WAL database in `app/desktop/database/reports.db` with
    unique deduplication on `(kind, app_version, install_id, period_key, content_hash)`.
  - Security hardening: streaming 256 KB body-size limit (`413`), per-IP rate
    limiting (`429`), strict Pydantic validation (`422`), optional
    `X-Lila-Report-Token` auth (`401`), PII redaction, and automatic
    background retention pruning (`retention_days=90`) on every upload.
  - Native Desktop menu `Help -> Report Bug / Issue...` + opt-in
    `Anonymous diagnostics` toggle in `File -> Preferences...`, `DesktopBridge`
    methods, `@lila/desktop` TypeScript helpers, `--report-url` /
    `--report-token` / `--telemetry-interval` flags on `lila desktop dev|build`,
    and periodic `DesktopTelemetryScheduler`.
- **Automatic safe migrations for Desktop `.exe`**: `auto_migrate_async()`
  discovers `app.models.*` inside PyInstaller bundles (`LILA_DESKTOP_MODELS` /
  `pkgutil`) and applies safe schema operations (`create_table`, `add_column`,
  `rename_column`, `create_index`) on startup when `sys.frozen` or
  `LILA_AUTO_MIGRATE=1`.

### Fixed

- `lila init` no longer copies internal `resources/react_scaffold/` into new projects.
- `lila-client.js` (and `.min.js`) now triggers a full browser navigation when
  clicking links from Jinja pages to React pages (`data-layout="react"`),
  preventing blank screens without needing `data-no-router`.
- `Router(prefix="/api/x")` + `@router.get("")` now resolves to `/api/x`
  without a trailing slash (eliminates `307 Temporary Redirect` responses).
- `BaseModel._read_stmt` / `count_async` now respect explicit `active=0` (or
  `active__*`) filters and support `get_by_id_async(..., include_deleted=True)`.

## [2.2.1] — 2026-11-23

### Fixed

- Silence Uvicorn/Granian `INFO` and HTTP access logs in the terminal when
  `DEBUG=False` (`App(debug=False)`, `python main.py`, `lila run`, and direct
  `uvicorn main:app` launches). Added opt-in `LILA_ACCESS_LOG` /
  `LILA_LOG_LEVEL` settings and `--access-log` / `--log-level` options on
  `lila run`.

## [2.2.0] — 2026-11-21

### Security, CRUD/admin in React, real-time, desktop releases and infrastructure

### Added

- **Content-Security-Policy**: `App(csp=True|"report-only"|{...})` with a
  per-response nonce and `'strict-dynamic'` (route caches and ETags keep
  working: templates write a placeholder the middleware fills). Framework
  templates, Swagger, the React shell and Vite tags carry the nonce; new
  projects enable it. Use `<script{{ nonce_attr }}>` for inline scripts and
  `data-onclick="fn"` / `data-onchange` / `data-oninput` instead of inline
  handlers (`button[data-toast]` too).
- `lila-client.min.js` / `ws.min.js` ship in the package and are served when
  `rjsmin` is not installed (`python -m lila.core.static` regenerates them).
- **CRUD/admin**: `search=`/`search_fields=` in `get_all_async`/`count_async`/
  `paginate_async`; `rest_crud_generate` and the admin API accept
  `?page=&per_page=&search=&sort=&order=`; `lila crud --react` (DataTable +
  Modal form) and `--auth`; `lila admin --react` (dashboard, CRUD for every
  model, export, cache/logs).
- **Templates**: `lila init --template web|react|auth|react-auth|full|desktop`
  with `--yes` and `--install`.
- **Real-time React hooks** (`@lila/realtime`): `useSSE`, `useWebSocket`
  (rooms, heartbeat, reconnect with backoff, offline queue).
- **Desktop**: code signing (`codesign` + notarization, `signtool`), in-app
  updates (`--update-url`, `lila desktop release` → `latest.json` with SHA-256,
  `useDesktopUpdate()`), bridge `notify`, `open_external`, `app_info`,
  `set_title` (`@lila/desktop`).
- **Migrations**: batches and `lila migrate rollback [--steps] [--dry-run] [--yes]`.
- **Storage**: `STORAGE_DRIVER=local|s3` (AWS, R2, MinIO, Spaces), presigned
  or CDN URLs; `upload(..., folder=)`. Extra `[s3]`.
- **OpenTelemetry**: `App(telemetry=True)` / `OTEL_ENABLED` — HTTP spans by
  route template, SQL spans without parameters, task spans, `traceparent`.
  Extra `[otel]`.
- CI: lint (syntax/undefined names for Python 3.10), `lila --help`, and a
  React job (TS and JS) that scaffolds, typechecks, builds and smoke-tests.

### Fixed

- The `lila` CLI crashed with a SyntaxError on Python 3.10/3.11 (backslashes
  inside f-string expressions in `lila/cli/deploy.py`).
- WebSockets returned 404 on a default install: uvicorn had no WebSocket
  library. `websockets` is now a dependency and `lila doctor` checks it.
- `lila crud` generated APIs that returned `str(exc)` to clients and ignored
  `__private_fields__`; errors are now logged and private columns respected.
- New projects defaulted `VERSION_PROJECT` to the framework version; it is
  now `1.0.0` (your app's version, used by desktop builds).

### React, desktop targets and fixes

### Added

- **React (Vite)**: `lila react init|dev|build|status`; `react_render(request,
  "Page", props, title=, description=, jsonld=, meta=, canonical=...)` with
  client navigation (`<Link>`, `visit`, JSON pages, `<head>` swap, history,
  409 reload on new builds); `router.spa("/app", meta={...})` for React Router
  apps with per-route meta (dicts or sync/async callables, `useLilaHead`);
  `{{ vite("entry.jsx") }}` for Jinja pages. Dev uses the Vite server through
  `public/build/hot` (only with `DEBUG=True`); production reads
  `public/build/.vite/manifest.json` (CSS, modulepreload, hashed scripts).
- **Desktop targets**: `desktop=False` / `desktop="only"` on routes, websockets
  and `Router(...)`; `DESKTOP_EXCLUDE` patterns (`/x`, globs, `name:`);
  `lila desktop build|dev --exclude --auto-exclude` (patterns baked into the
  executable); `lila desktop routes`; removed routes are 404, hidden from
  OpenAPI and exposed to React (`<WebOnly>`, `<DesktopOnly>`, `isAvailable`) and
  Jinja (`is_desktop()`, `route_available()`). `lila desktop build` runs the
  React build first; `--width/--height`.
- `lila doctor` checks React assets and a stale `public/build/hot`.
- **TypeScript by default**: `lila react init` writes `.tsx`, `tsconfig.json`
  (strict) and `vite.config.ts`; `--js` keeps `.jsx`. The `@lila` client is
  typed (`Page`, `Head`, `HttpError`, `LinkProps`...) and shared by both.
- `useForm(initial)` (CSRF, `processing`, per-field 422 errors, `transform`,
  `redirect`), `useT()` with `react_render(translations=True|[keys])`.
- `lila react types` → `resources/react/types/lila.ts` from Pydantic schemas and
  models in `app/` (private fields excluded); refreshed by `react dev/build`.
- React pages reload when the Python dev server restarts.
- `lila auth --react`: login, register, forgot/reset password, invalid token,
  dashboard and profile as React pages over the same JSON endpoints, throttles
  and lockouts; `OAuth.configured_providers()`.
- **React UI kit** copied into `resources/react/components/ui` (editable, Lila
  palette and classes, dark mode shared with Jinja via `lila-theme`): Button
  (variants/sizes/loading, `url` actions), Form/Input/Textarea/Select/Checkbox/
  SubmitButton/FormError/FormMessage (`validate`, 422 per field), Card, Badge,
  Modal, Drawer (native `<dialog>`), Carousel, Toaster/toast, ThemeToggle/
  useTheme, Spinner/Skeleton/PageSkeleton/ProgressBar and DataTable (search,
  sort, pagination, edit/delete, server mode compatible with `paginate_async`);
  `lila react ui [--force]`.
- `@lila/auth` (`AuthProvider`, `useAuth`, `RequireAuth` with roles and
  `?next=` redirects, `GuestOnly`), `@lila/router` (`createRouter`
  browser/hash/memory, lazy `page()`, `LilaHead`); `lila auth` adds
  `GET /api/auth/me` (public fields + roles, `no-store`) and
  `permissions.resolve_roles`. `<Link activeClassName exact>` sets
  `aria-current`; `lila:navigate-start/end` events.
- `lila desktop build --installer auto|dmg|msi`: macOS `.dmg` (hdiutil, with an
  Applications link) and Windows `.msi` (WiX v4+: Program Files, Start
  menu/desktop shortcuts, icon, in-place upgrades); `--version`,
  `--publisher`, `--bundle-id`; icons auto-detected and converted with Pillow.

### Fixed

- `public("css/lila.css")` resolved to `/css/lila.css`, which was never served:
  the compiled Tailwind CSS (and any other `public/<dir>`) 404'd in
  production. Top-level `public/` directories are now served at the root as
  fallbacks (matched after application routes).
- Desktop builds did not bundle the project's `app/locales/*.json`.
- `lila react types` discovers modules in folders without `__init__.py`.
- The JSON fallback without orjson produced spaced output (different SSE
  payloads/ETags than with orjson).
- Static prefixes for rate limiting/cache headers include `/css`, `/fonts`, `/build`.

### Performance, background work and security

### Added

- **Performance**: `lila css build` (official Tailwind standalone binary,
  SHA-256 verified, no Node) with `TAILWIND_MODE`; `LilaStaticFiles` serves
  `.br`/`.gz` siblings and compresses text assets once; minified + compressed
  `/js/lila-client.js` and `/js/ws.js` (94 KB → 19 KB); `App(etag=True)` weak
  ETag/304; `CACHE_MAX_MB`; Jinja bytecode cache; `LOG_RETENTION_DAYS`;
  `lila backup --compress`; `lila run --server granian [--max-rss]`; `lila bench`.
- **Models**: Core-based reads (≈1.8× faster, private columns never selected),
  rich filters (`__gte`, `__in`, `__contains`, ...), `paginate_async`,
  `db.write_transaction()` (SQLite write queue), `PRAGMA optimize` on close.
- **Templates**: `{{ form(PydanticModel) }}`, `ui.*` components,
  `{{ pagination(page) }}`, `{{ image(...) }}` responsive WebP, `can()`/`has_role()`.
- **Migrations**: `lila migrate --plan`, renames (`__renamed_columns__`),
  indexes, `--drop-columns`, `lila migrate history` (separate `lila_system.db`).
- **DX**: `lila.testing`, `lila i18n check`, `.env` validation at startup and in
  `lila doctor`.
- **Background**: SQLite task queue (`@task`, `.delay()`, `lila worker --driver
  sqlite`, `lila tasks`), scheduler (`@every`, `@cron`, `lila schedule`),
  `Mailer.send_template` with `emails/base.jinja`, SSE (`EventStream`,
  `Channel`, `lilaSSE`, `data-sse`).
- **Security**: roles/permissions (router `roles=`/`permissions=`), per-user API
  keys (router `api_key=`), rotating JWT refresh tokens with reuse detection.
- **Observability**: `/health`, `/health/details`, `/metrics` protected by
  token, direct-loopback-only access and optional one-time codes (`METRICS_OTP`).

### Changed

- GZip level 5 by default and never applied to static paths.
- SEO data in templates is `page_meta` (`page` is free for pagination).
- The default layout loads `lila-client.js` in `<head>` (inline page scripts can
  use it on the first load).
- `lila worker` uses the SQLite queue unless `CACHE_DRIVER=redis`.

### Templates, client, deploy and fixes (earlier in this cycle)

### Added

- **Automatic layouts**: page templates contain only their HTML. `render()`
  wraps them in the default layout and builds the `<head>` from new keyword
  arguments: `title` (translation keys are translated), `description`,
  `keywords`, `author`, `image`, `icon`, `canonical`, `robots`, `og_type`,
  `jsonld`, `meta`, `styles`, `scripts`, `head`, `body_class`; `layout=False`
  renders fragments. Shared `lila/head.jinja` for custom layouts;
  `TITLE_TEMPLATE` in `.env`. Templates using `{% extends %}` are unchanged.
- Jinja helpers `datatable()` (embedded rows or `url=`, unique id, sensitive
  keys excluded) and `carousel()` (autoplay, loop, indicators, swipe,
  keyboard), auto-initialized by `lila-client.js` after each navigation.
- `sudo lila deploy setup`: interactive Linux install (`.env` production
  values, systemd, Nginx with `nginx -t` rollback, Certbot, health check),
  `--dry-run` and `--yes`. `SERVICE_NAME` in `.env`.
- Declarative forms and actions in `lila-client.js`: `data-lila-form`,
  `data-action`, `data-snackbar`/`data-toast`/`[data-message]`, `data-match`,
  `data-loading-text`, `data-timeout`, `data-redirect`, `data-reset`,
  `data-reload`, `data-target`/`data-swap`, `data-refresh`, `data-callback`,
  `data-toggle-hidden`; 422 errors are shown under each field. The auth
  scaffold templates no longer contain page scripts.
- UI attributes: `data-drawer` + `data-drawer-panel data-orientation=
  "left|right|top|bottom"` (focus handling, Escape, closes on navigation),
  `data-dropdown`, `data-toggle-class`, `data-remove`, `data-password-toggle`,
  `data-tab-target`, `data-scroll`, `data-autosubmit`, `form[data-navigate]`,
  `data-char-count`, `data-filter`, `<time data-local-time>`;
  `data-copy` works on http:// and accepts `data-copy-message`.
- Plain-HTML carousel: `data-carousel`, `data-carousel-slide`,
  `data-carousel-autoplay|loop|arrows|indicators|pause`;
  `lila('carousel', ...)` returns controllers.
- `sudo lila deploy setup` offers `chown`/`chmod` fixes (project owner, Nginx
  access to `public/`, `.env` 600) and never rotates `SECRET_KEY`.
- `WebSocketHub.can_join` to authorize client room joins; `lilaWS` gains
  `once()`, `connected`, `persist` and relative URLs.

### Changed

- Auth scaffold, `index`, `404` and `lila crud` templates use the automatic
  layout; their routes pass `title`/`robots`.
- `/js/ws.js` is served from the installed package (like `lila-client.js`);
  `lila deploy` proxies both to the app instead of aliasing stale copies.
- `render(scripts=...)` tags load in order (no `defer`) so inline page
  scripts can use them.

### Fixed

- SPA router: `[data-lila-head]` tags and `<html lang>` are synchronized,
  external scripts finish loading before the next inline script runs,
  prefetch is de-duplicated and never caches redirects, same-page `#hash`
  links scroll natively, `lila:before-swap` event added.
- `ws.js`: no reconnect after `disconnect()` (pending timer), bounded
  offline queue, no duplicate room joins, no reconnect loop on 1008/1009,
  sockets closed when the SPA leaves their page.
- `WebSocketHub.disconnect` is idempotent (handlers ran twice after a
  failed send); room names/counts are limited.
- `ResponsiveDataTable` releases its resize listener when removed by an SPA
  navigation; `lila crud` pages work on repeated SPA visits.
- `lila deploy`: `WorkingDirectory` without quotes (systemd), `www.` server
  names.
- Sync `get_all()` supports `order_by`/`desc`.
- A closed drawer's transparent backdrop kept intercepting every click on the
  page (`.drawer-backdrop` had `pointer-events: auto`); left drawers opened on
  the right.
- Admin sidebar: the active item follows SPA navigation (persisted links are
  synchronized), no nested duplicate `#admin-sidebar`, active matching works
  with custom prefixes and does not confuse `/user` with `/users`.

- Route cache keys now use the concrete request path: `/items/1` and `/items/2`
  no longer share the same cached response.
- `q: Optional[str]` (no default) receives `None` when missing instead of
  raising a 500.
- Malformed request bodies no longer echo the internal exception to clients.
- `rest_crud_generate`: rejects primary key, `__private_fields__` and unknown
  fields (422), clamps `limit` (`max_limit=500`) and logs DB errors instead of
  returning `str(exc)`.
- `BaseModel` filters/`order_by`/`select` only resolve real table columns;
  unknown filter names raise `ValueError` instead of being ignored (which
  returned every row).
- Cached model reads are returned as copies, so mutating a result no longer
  pollutes the shared in-memory cache.
- `Session.get` honours the `max_age` used in `Session.set` (the lifetime is
  stored inside the signed cookie); a 30-day session no longer expires after
  one day. Cookies from 2.0.0 remain readable.
- Memory LRU evicts expired and non-session entries before sessions, and
  `incr` (rate-limit counters) is bounded by `CACHE_MAX_ITEMS`.
- File cache prefix deletes (`model:<table>:*`) only remove that table's
  entries instead of wiping the whole file cache on every write.
- Route `csrf=True` is verified before body validation, so requests without a
  token get 403 instead of validation details.
- `update_async`/`update` skip soft-deleted rows unless the payload restores
  the active field explicitly.

## [2.0.0] — 2026-10-31

Lila 2.0 is the lightweight full-stack release: Starlette + Pydantic v2 +
SQLAlchemy 2.0 Async + Jinja2, with 1–2 worker deployments as the primary target.

### Added

- Typed routing with pre-compiled Pydantic `TypeAdapter`s, 422 validation
  responses, path/query casting, Pydantic body/query models and per-identity
  response caching.
- Pure ASGI middleware stack: security headers, rate limiting, CSRF, gzip,
  static cache headers, optional debug history and desktop token guard.
- **`lila deploy`**: generates `start_lila.sh`, systemd application/worker units,
  an Nginx reverse proxy with WebSocket support and direct static/upload paths,
  and a Windows Server PowerShell starter.
- **`lila backup`**: online SQLite backups using `sqlite3.Connection.backup()`,
  retention rotation, explicit source/output paths and remote-DB safeguards.
- **Desktop 2.0**: single-instance lock, local token session (`_dt` → HttpOnly
  cookie), native `DesktopBridge`, loopback-only server, PyInstaller bootstrap
  that bundles `main`, `app`, Lila data files and project `public/`/`resources/`.
- **`lila optimize`** generates a manifest consumed by `public()`, appends
  `?v=mtime`, converts PNG/JPG to WebP and pre-compresses `.gz`/`.br` assets.
- **`lila seo`** discovers public GET routes and serves `/sitemap.xml` and
  `/robots.txt` from the site root.
- **`lila worker`** Redis JSON task queue with allowlist, retries and a
  dead-letter queue.
- **`lila doctor`**, **`lila routes`**, **`lila run`** with proxy-header support.
- `/debug` dashboard (`debug=True, debug_html=True`) with in-memory request
  history, filters, sorting and native/psutil telemetry.
- Built-in locales `en`, `es`, `pt` and `zh`; flat project JSON overrides.
- `@seo`/`SEO_CONFIG`, `RequestParser`, `validate_token`, `create_decorator`,
  `py.typed`, `SECURITY.md`, CI and a regression test suite.

### Fixed

- **CLI safety**: bracket-aware `main.py` patching is compiled before writing;
  `lila init` is non-destructive; auth/admin/crud keep backups of replaced files.
- **Secrets**: empty/placeholder `SECRET_KEY` can never sign sessions, CSRF or
  admin cookies. Lila persists `.lila_secret` (0600) and warns.
- **Admin**: project database, Argon2id login, CSRF on mutations, per-IP rate
  limiting, whitelisted CRUD, hidden password fields, CSV escaping/BOM and
  session-preserving cache purge.
- **Auth**: HTML-form/JSON/header CSRF, password reset with hashed single-use
  tokens, login lockout, async password hashing, OAuth without secrets in the
  session cookie, verified-email checks and localized templates. `login_required`,
  `session_active`, `admin_required`, `rate_limit` and `validate_token` now
  recognize Starlette's real `Request` instance, so successful logins no longer
  bounce back to `/login`; `auth_required` is available as an alias.
- **Migrations**: create tables and add missing columns, including `NOT NULL`
  scalar defaults; `--refresh` really drops tables and asks for confirmation.
- **Uploads**: streamed writes under `public/uploads`, `/uploads` serving, no
  absolute paths, 15 MB limit, SVG blocked by default, optional WebP.
- **Cache**: memory by default; Redis only when installed and reachable; file
  fallback; clear preserves sessions; route cache isolated per identity.
- **Database**: SQLite WAL, `busy_timeout`, bounded page cache, 64 MB mmap,
  URL-encoded MySQL/PostgreSQL credentials and real async transactions.
- **Desktop**: secondary-thread signal handler crash, module resolution in the
  frozen bundle, persistent OS data paths, input token enforcement, and reliable
  fallback browser shutdown.
- **Deploy/Nginx**: static locations now match Lila's real `/public`, `/js`,
  `/img`, `/swagger` and `/uploads` routes; `gzip_static`, proxy headers and
  request-size limits are generated consistently.
- **Templates/frontend**: CSRF meta on every page, XSS escape fixes, DataTable
  cleanup, full-document partial navigation fallback, dark-mode persistence and
  no Google Fonts/Chart.js CDNs.
- **Dev reload**: `lila dev` forces the development flag, enables Jinja
  auto-reload and adds an SSE watcher for `.jinja`, `.html`, `.json`, CSS and JS
  edits. The browser reloads and the locale/asset caches are cleared without
  requiring `watchfiles`; Python edits keep using Uvicorn's reloader.
- **Locales**: completed key parity and removed hardcoded Spanglish; force mode
  (`LANG_FORCE`) now overrides request detection consistently.
- **Debug/telemetry**: `/debug` endpoints match the dashboard payload, static
  assets are excluded from history, and metrics use native fallbacks.
- **Performance**: lazy `import lila`, lazy Redis, static cache headers, gzip,
  smaller logos, pre-compressed assets and fewer per-request allocations.

### Changed

- Package version is **2.0.0**; requires **Python 3.10+**.
- `import lila` is lazy (PEP 562); `App` loads `.env` itself.
- `BaseModel.to_dict()` returns only loaded columns and hides
  `__private_fields__`.
- Signed sessions over ~3 KB use server-side storage with a signed `sid` cookie.
- Default `DEBUG` is `False` without `.env`; scaffolds create a development
  `.env` with `DEBUG=True`.
- Starlette is capped at `<2`, Uvicorn at `<1`; `uvicorn[standard]` is optional.
- Documentation is versioned for 2.0.0 and includes the new deploy/backup/desktop,
  localization, migration and security behavior.
