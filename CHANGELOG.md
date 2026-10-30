# Changelog

All notable changes to Lila Framework. The format follows [Keep a Changelog](https://keepachangelog.com/).

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
