"""
English: OAuth 2.0 Authentication Helper for Google and GitHub in Lila Framework.
         Provides simple authorization URL generation and token exchange helpers.
Español: Helper de Autenticación OAuth 2.0 para Google y GitHub en Lila Framework.
         Provee generación de URLs de autorización e intercambio de tokens en 2 líneas.
"""

import urllib.parse
from typing import Any, Dict, Optional
from starlette.requests import Request
from lila.core.config import ENV_CONFIG
from lila.core.responses import JSONResponse
from lila.core.logger import Logger


class GoogleAuth:
    """
    English: Lightweight Google OAuth 2.0 helper.
    Español: Helper ligero para Google OAuth 2.0.
    """

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    @classmethod
    def get_client_id(cls) -> str:
        return ENV_CONFIG.get("GOOGLE_CLIENT_ID", "")

    @classmethod
    def get_client_secret(cls) -> str:
        return ENV_CONFIG.get("GOOGLE_CLIENT_SECRET", "")

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: Optional[str] = None, scope: str = "email profile") -> str:
        """
        Generates the Google OAuth 2.0 authorization redirect URL.
        """
        params = {
            "client_id": cls.get_client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent"
        }
        if state:
            params["state"] = state
        return f"{cls.AUTH_URL}?{urllib.parse.urlencode(params)}"

    @classmethod
    async def get_user_info(cls, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchanges code for access token and retrieves Google user profile.
        Returns dict with email, name, picture, google_id, etc.
        """
        import urllib.request
        import urllib.parse
        from lila.core.responses import orjson_loads

        try:
            # Exchange code for token
            post_data = urllib.parse.urlencode({
                "code": code,
                "client_id": cls.get_client_id(),
                "client_secret": cls.get_client_secret(),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }).encode("utf-8")

            req = urllib.request.Request(cls.TOKEN_URL, data=post_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req) as resp:
                token_data = orjson_loads(resp.read())

            access_token = token_data.get("access_token")
            if not access_token:
                return None

            # Fetch User Profile
            user_req = urllib.request.Request(cls.USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(user_req) as user_resp:
                profile = orjson_loads(user_resp.read())

            return {
                "id": profile.get("id"),
                "email": profile.get("email"),
                "name": profile.get("name"),
                "given_name": profile.get("given_name"),
                "family_name": profile.get("family_name"),
                "picture": profile.get("picture"),
                "verified_email": profile.get("verified_email", False),
                "raw": profile
            }
        except Exception as e:
            Logger.error(f"Google OAuth Error: {e}", exception=e)
            return None


class GitHubAuth:
    """
    English: Lightweight GitHub OAuth 2.0 helper.
    Español: Helper ligero para GitHub OAuth 2.0.
    """

    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"

    @classmethod
    def get_client_id(cls) -> str:
        return ENV_CONFIG.get("GITHUB_CLIENT_ID", "")

    @classmethod
    def get_client_secret(cls) -> str:
        return ENV_CONFIG.get("GITHUB_CLIENT_SECRET", "")

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: Optional[str] = None, scope: str = "user:email") -> str:
        """
        Generates the GitHub OAuth 2.0 authorization redirect URL.
        """
        params = {
            "client_id": cls.get_client_id(),
            "redirect_uri": redirect_uri,
            "scope": scope
        }
        if state:
            params["state"] = state
        return f"{cls.AUTH_URL}?{urllib.parse.urlencode(params)}"

    @classmethod
    async def get_user_info(cls, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchanges code for access token and retrieves GitHub user profile.
        """
        import urllib.request
        import urllib.parse
        from lila.core.responses import orjson_loads

        try:
            post_data = urllib.parse.urlencode({
                "code": code,
                "client_id": cls.get_client_id(),
                "client_secret": cls.get_client_secret(),
                "redirect_uri": redirect_uri
            }).encode("utf-8")

            req = urllib.request.Request(cls.TOKEN_URL, data=post_data, headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            })
            with urllib.request.urlopen(req) as resp:
                token_data = orjson_loads(resp.read())

            access_token = token_data.get("access_token")
            if not access_token:
                return None

            # Fetch User Profile
            user_req = urllib.request.Request(cls.USERINFO_URL, headers={
                "Authorization": f"token {access_token}",
                "User-Agent": "Lila-Framework"
            })
            with urllib.request.urlopen(user_req) as user_resp:
                profile = orjson_loads(user_resp.read())

            return {
                "id": str(profile.get("id")),
                "email": profile.get("email"),
                "name": profile.get("name") or profile.get("login"),
                "username": profile.get("login"),
                "picture": profile.get("avatar_url"),
                "raw": profile
            }
        except Exception as e:
            Logger.error(f"GitHub OAuth Error: {e}", exception=e)
            return None
