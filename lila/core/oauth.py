"""Lila Framework v2.0.1 OAuth 2.0 Engine.
Preconfigured for Google, GitHub, and Discord with built-in official SVG icons,
fully asynchronous token exchange, auto-mounted routes, and user synchronization.
"""

import asyncio
import secrets
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any, List, Type
from starlette.requests import Request
from starlette.responses import RedirectResponse
from lila.core.config import ENV_CONFIG
from lila.core.responses import orjson_loads
from lila.core.logger import Logger
from lila.core.session import Session
from lila.core.auth import PasswordHasher


BUILTIN_SVGS = {
    "google": (
        '<svg class="w-5 h-5" viewBox="0 0 24 24">'
        '<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>'
        '<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>'
        '<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>'
        '<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>'
        '</svg>'
    ),
    "github": (
        '<svg class="w-5 h-5 fill-current" viewBox="0 0 24 24">'
        '<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>'
        '</svg>'
    ),
    "discord": (
        '<svg class="w-5 h-5 fill-[#5865F2]" viewBox="0 0 24 24">'
        '<path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.893.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>'
        '</svg>'
    ),
    "microsoft": (
        '<svg class="w-5 h-5" viewBox="0 0 23 23">'
        '<path fill="#f35325" d="M1 1h10v10H1z"/>'
        '<path fill="#81bc06" d="M12 1h10v10H12z"/>'
        '<path fill="#05a6f0" d="M1 12h10v10H1z"/>'
        '<path fill="#ffba08" d="M12 12h10v10H12z"/>'
        '</svg>'
    ),
}


class OAuth:
    """OAuth 2.0 Engine for Lila Framework."""

    PROVIDERS = {
        "google": {
            "name": "Google",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
            "scope": "openid email profile",
            "client_id_env": "GOOGLE_CLIENT_ID",
            "client_secret_env": "GOOGLE_CLIENT_SECRET",
        },
        "github": {
            "name": "GitHub",
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "emails_url": "https://api.github.com/user/emails",
            "scope": "read:user user:email",
            "client_id_env": "GITHUB_CLIENT_ID",
            "client_secret_env": "GITHUB_CLIENT_SECRET",
        },
        "discord": {
            "name": "Discord",
            "auth_url": "https://discord.com/api/oauth2/authorize",
            "token_url": "https://discord.com/api/oauth2/token",
            "userinfo_url": "https://discord.com/api/users/@me",
            "scope": "identify email",
            "client_id_env": "DISCORD_CLIENT_ID",
            "client_secret_env": "DISCORD_CLIENT_SECRET",
        },
    }

    @classmethod
    def register_provider(cls, name: str, config: dict) -> None:
        cls.PROVIDERS[name.lower()] = config

    @classmethod
    def get_auth_url(cls, provider: str, redirect_uri: str, state: str) -> Optional[str]:
        conf = cls.PROVIDERS.get(provider.lower())
        if not conf:
            return None
        client_id = ENV_CONFIG.get(conf["client_id_env"], "")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": conf["scope"],
            "state": state,
        }
        if provider == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        return f"{conf['auth_url']}?{urllib.parse.urlencode(params)}"

    @classmethod
    async def exchange_code(
        cls, provider: str, code: str, redirect_uri: str
    ) -> Optional[Dict[str, Any]]:
        """Asynchronously exchanges authorization code for normalized user profile."""
        conf = cls.PROVIDERS.get(provider.lower())
        if not conf:
            return None

        client_id = ENV_CONFIG.get(conf["client_id_env"], "")
        client_secret = ENV_CONFIG.get(conf["client_secret_env"], "")

        def _do_http():
            post_data = urllib.parse.urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }).encode("utf-8")

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "Lila-Framework-2.0",
            }
            req = urllib.request.Request(conf["token_url"], data=post_data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                token_res = orjson_loads(resp.read())

            access_token = token_res.get("access_token")
            if not access_token:
                return None

            user_headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Lila-Framework-2.0",
                "Accept": "application/json",
            }
            user_req = urllib.request.Request(conf["userinfo_url"], headers=user_headers)
            with urllib.request.urlopen(user_req, timeout=10) as user_resp:
                raw_user = orjson_loads(user_resp.read())

            # Normalization
            if provider == "google":
                return {
                    "provider": "google",
                    "id": str(raw_user.get("id")),
                    "email": raw_user.get("email"),
                    "email_verified": bool(raw_user.get("verified_email", True)),
                    "name": raw_user.get("name") or raw_user.get("email", "").split("@")[0],
                    "avatar_url": raw_user.get("picture"),
                }
            elif provider == "github":
                email = raw_user.get("email")
                verified = False
                if not email and "emails_url" in conf:
                    # Fetch primary verified email
                    try:
                        em_req = urllib.request.Request(conf["emails_url"], headers=user_headers)
                        with urllib.request.urlopen(em_req, timeout=10) as em_resp:
                            emails = orjson_loads(em_resp.read())
                            for em in emails:
                                if em.get("primary") and em.get("verified"):
                                    email = em.get("email")
                                    verified = True
                                    break
                    except Exception:
                        pass
                return {
                    "provider": "github",
                    "id": str(raw_user.get("id")),
                    "email": email or f"{raw_user.get('login')}@users.noreply.github.com",
                    "email_verified": verified or bool(email),
                    "name": raw_user.get("name") or raw_user.get("login"),
                    "avatar_url": raw_user.get("avatar_url"),
                }
            elif provider == "discord":
                user_id = str(raw_user.get("id"))
                avatar_hash = raw_user.get("avatar")
                avatar_url = (
                    f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
                    if avatar_hash
                    else None
                )
                return {
                    "provider": "discord",
                    "id": user_id,
                    "email": raw_user.get("email"),
                    "email_verified": bool(raw_user.get("verified", True)),
                    "name": raw_user.get("global_name") or raw_user.get("username"),
                    "avatar_url": avatar_url,
                }
            return None

        try:
            return await asyncio.to_thread(_do_http)
        except Exception as e:
            Logger.error(f"OAuth exchange failed for {provider}: {e}", exception=e)
            return None

    @classmethod
    def render_buttons(
        cls,
        providers: Optional[List[str]] = None,
        custom_icons: Optional[Dict[str, str]] = None,
        prefix: str = "/auth",
        label_prefix: Optional[str] = None,
    ) -> str:
        """Renders Tailwind CSS styled OAuth buttons for templates."""
        if label_prefix is None:
            try:
                from lila.core.translate import Translate
                label_prefix = Translate.t("continue_with", default="Continue with")
            except Exception:
                label_prefix = "Continue with"
        if providers is None:
            # Detect configured providers
            active = []
            for p, conf in cls.PROVIDERS.items():
                if ENV_CONFIG.get(conf["client_id_env"]) and ENV_CONFIG.get(conf["client_secret_env"]):
                    active.append(p)
            providers = active or ["google", "github"]

        custom_icons = custom_icons or {}
        html_parts = ['<div class="flex flex-col gap-2.5 w-full">']

        for p in providers:
            p_key = p.lower()
            name = cls.PROVIDERS.get(p_key, {}).get("name", p.title())
            icon_svg = custom_icons.get(p_key) or BUILTIN_SVGS.get(p_key, "")
            href = f"{prefix}/{p_key}"

            btn = (
                f'<a href="{href}" data-no-router '
                f'class="flex items-center justify-center gap-3 w-full px-4 py-2.5 rounded-xl border '
                f'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 '
                f'hover:bg-slate-50 dark:hover:bg-slate-800/80 font-semibold text-sm '
                f'text-slate-700 dark:text-slate-200 transition-all shadow-sm cursor-pointer">'
                f'{icon_svg}<span>{label_prefix} {name}</span></a>'
            )
            html_parts.append(btn)

        html_parts.append("</div>")
        return "".join(html_parts)

    @classmethod
    def mount_routes(
        cls,
        router: Any,
        user_model: Optional[Type] = None,
        redirect_to: str = "/dashboard",
        login_url: str = "/login",
    ) -> None:
        """Mounts /auth/{provider} and /auth/{provider}/callback in 1 line."""

        @router.get("/auth/{provider}")
        async def oauth_redirect(request: Request, provider: str):
            p = provider.lower()
            if p not in cls.PROVIDERS:
                return RedirectResponse(login_url)

            state = secrets.token_urlsafe(32)
            # Determine base redirect_uri
            base_url = ENV_CONFIG.get("APP_URL") or str(request.base_url).rstrip("/")
            route_prefix = str(getattr(router, "prefix", "") or "").rstrip("/")
            callback_uri = f"{base_url}{route_prefix}/auth/{p}/callback"

            auth_url = cls.get_auth_url(p, callback_uri, state)
            if not auth_url:
                return RedirectResponse(login_url)

            response = RedirectResponse(auth_url)
            response.set_cookie(
                f"_oauth_state_{p}",
                state,
                max_age=600,
                httponly=True,
                secure=str(ENV_CONFIG.get("APP_URL", "") or "").lower().startswith("https://"),
                samesite="lax",
                path="/",
            )
            return response

        @router.get("/auth/{provider}/callback")
        async def oauth_callback(request: Request, provider: str):
            p = provider.lower()
            if p not in cls.PROVIDERS:
                return RedirectResponse(login_url)

            code = request.query_params.get("code")
            state = request.query_params.get("state")
            cookie_state = request.cookies.get(f"_oauth_state_{p}")

            if not code or not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
                return RedirectResponse(f"{login_url}?error=invalid_state")

            base_url = ENV_CONFIG.get("APP_URL") or str(request.base_url).rstrip("/")
            route_prefix = str(getattr(router, "prefix", "") or "").rstrip("/")
            callback_uri = f"{base_url}{route_prefix}/auth/{p}/callback"

            profile = await cls.exchange_code(p, code, callback_uri)
            if not profile or not profile.get("email"):
                return RedirectResponse(f"{login_url}?error=oauth_failed")
            if not profile.get("email_verified", True):
                return RedirectResponse(f"{login_url}?error=email_not_verified")
            profile["email"] = str(profile["email"]).strip().lower()

            # Resolve User Model
            target_model = user_model
            if target_model is None:
                try:
                    from app.models.user import User
                    target_model = User
                except Exception:
                    pass
            if target_model is None:
                return RedirectResponse(f"{login_url}?error=user_model_missing")

            user_dict = None
            # Find user by email
            users = await target_model.get_all_async(limit=1, email=profile["email"])
            if users:
                user_dict = users[0]
                await target_model.update_async(
                    user_dict["id"],
                    oauth_provider=p,
                    oauth_id=profile["id"],
                    avatar_url=profile.get("avatar_url") or user_dict.get("avatar_url"),
                )
            else:
                # Register new user
                rand_pwd = await PasswordHasher.hash_async(secrets.token_urlsafe(32))
                user_dict = await target_model.insert_async(
                    name=profile.get("name") or profile["email"].split("@")[0],
                    email=profile["email"],
                    password=rand_pwd,
                    oauth_provider=p,
                    oauth_id=profile["id"],
                    avatar_url=profile.get("avatar_url"),
                    active=1,
                )

            response = RedirectResponse(redirect_to, status_code=303)
            response.delete_cookie(f"_oauth_state_{p}", path="/")
            if user_dict:
                # Never store password hashes or arbitrary model fields in a cookie.
                session_payload = {
                    key: user_dict.get(key)
                    for key in ("id", "email", "name", "avatar_url")
                    if user_dict.get(key) is not None
                }
                session_payload["user_id"] = session_payload.pop("id", None)
                await Session.set_async(session_payload, response)
            return response

