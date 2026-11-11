# Changelog

All notable changes to Lila Framework. The format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
