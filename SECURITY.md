# Security Policy

## Supported versions

| Version | Supported |
| :--- | :--- |
| 2.0.x | ✅ |
| 1.x | ❌ |

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Send a private
report to the maintainer with:

- affected version and Python version;
- a minimal reproduction (no real credentials or personal data);
- impact and whether the issue is already public.

You should receive an acknowledgement within a few days. Please allow time for a
fix and release before disclosing details publicly.

## Security defaults in Lila 2.0

- `SECRET_KEY` is never used empty: Lila generates `.lila_secret` (mode 0600) and
  logs a warning when the value is missing, too short or a placeholder. Set a
  real secret in `.env` for production and rotate it with `lila secret-key`.
- Sessions are **signed, not encrypted**. Never store passwords, API keys or
  tokens in a session. `Session.set` strips password-like keys, and models can
  use `__private_fields__` to hide fields from `to_dict()`.
- CSRF: HTML forms must send `_csrf`; JSON requests can send `X-CSRF-Token`.
  Tokens are not accepted from the query string.
- Cache entries created by route caching include a per-identity fingerprint by
  default; use `cache_public=True` only for public content.
- Admin mutations require an authenticated admin session and a CSRF token.
- Uploads are streamed, limited to 15 MB by default, stored under
  `public/uploads` in a web deployment (OS app-data `uploads` in a frozen desktop
  build), and SVG is blocked unless explicitly enabled.
- Passwords use Argon2id when `argon2-cffi` is installed and are verified in a
  worker thread so the event loop is not blocked.
- Password-reset tokens are stored as SHA-256 hashes and are single-use after a
  successful password change.
- Desktop mode binds only to `127.0.0.1`, allows one instance, and gates every
  request/WebSocket with a per-run token exchanged for an HttpOnly cookie.
- `lila deploy` sanitizes unsafe service/domain/user tokens and serves static
  files from the real `/public`, `/js`, `/img`, `/swagger` and `/uploads` paths.

## Production checklist

1. `DEBUG=False` and `APP_URL=https://your-domain`.
2. Strong `SECRET_KEY`; never commit `.lila_secret` or `.env`.
3. `WORKERS=1` or `2` with memory cache; use Redis for shared sessions/cache
   across workers.
4. Serve over HTTPS and forward `X-Forwarded-Proto` only from a trusted proxy.
5. Use `pip install "lila-framework[metrics]"` only if you want psutil metrics.
6. Keep dependencies updated and review the changelog before upgrading.
