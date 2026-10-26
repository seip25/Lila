"""Lila Framework v2.0.0 Unified AI Helper Engine.
Zero heavy SDK dependencies (native async urllib/httpx).
Supports OpenAI, DeepSeek, and Google Gemini with:
- Configurable Rate Limiting
- Cache Hit prompt deduplication
- Reversible Sensitive Data (PII) Masking & Restoration ([email_01])
"""

import asyncio
import hashlib
import json
import re
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List, Union

from lila.core.config import ENV_CONFIG
from lila.core.cache import Cache
from lila.core.responses import orjson_dumps, orjson_loads, JSONResponse
from lila.core.logger import Logger


class IARateLimitExceeded(Exception):
    def __init__(self, message: str = "AI rate limit exceeded", retry_after: int = 60):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class SensitiveMasker:
    """Masks sensitive fields before sending to AI and restores them in the response."""

    @classmethod
    def mask(
        cls,
        text: str,
        data: Optional[Union[dict, list]] = None,
        sensitive_keys: Optional[List[str]] = None,
    ) -> tuple[str, Optional[Union[dict, list]], Dict[str, str]]:
        if not sensitive_keys:
            return text, data, {}

        norm_keys = [k.lower().strip() for k in sensitive_keys]
        vault: Dict[str, str] = {}
        counts: Dict[str, int] = {}

        def _get_placeholder(k_name: str) -> str:
            clean_k = re.sub(r"[^a-zA-Z0-9_]", "", k_name.lower()) or "field"
            counts[clean_k] = counts.get(clean_k, 0) + 1
            idx = counts[clean_k]
            return f"[{clean_k}_{idx:02d}]"

        # 1. Collect from data
        def _scan(obj: Any):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_lower = str(k).lower().strip()
                    if any(target in k_lower or k_lower in target for target in norm_keys):
                        val_str = str(v).strip()
                        if val_str and val_str not in vault.values():
                            ph = _get_placeholder(k_lower)
                            vault[ph] = val_str
                    _scan(v)
            elif isinstance(obj, list):
                for item in obj:
                    _scan(item)

        if data:
            _scan(data)

        # 2. Scan text for known patterns if sensitive_keys contains generic types
        if "email" in norm_keys:
            for em in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text):
                if em not in vault.values():
                    ph = _get_placeholder("email")
                    vault[ph] = em

        if "phone" in norm_keys or "telefono" in norm_keys:
            for ph_num in re.findall(r"\+?[0-9]{2,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}", text):
                clean_num = ph_num.strip()
                if len(clean_num) >= 8 and clean_num not in vault.values():
                    ph = _get_placeholder("phone")
                    vault[ph] = clean_num

        if not vault:
            return text, data, {}

        # 3. Replace in prompt text
        anonymized_text = text
        for placeholder, original in vault.items():
            anonymized_text = re.sub(re.escape(original), placeholder, anonymized_text)

        # 4. Replace in data
        def _replace_in_data(obj: Any) -> Any:
            if isinstance(obj, str):
                s = obj
                for placeholder, original in vault.items():
                    s = re.sub(re.escape(original), placeholder, s)
                return s
            if isinstance(obj, dict):
                return {k: _replace_in_data(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_replace_in_data(i) for i in obj]
            return obj

        anonymized_data = _replace_in_data(data) if data else None
        return anonymized_text, anonymized_data, vault

    @classmethod
    def restore(cls, text: str, vault: Dict[str, str]) -> str:
        """Restores placeholders in AI response back to original sensitive values."""
        if not vault or not text:
            return text
        restored = text
        for placeholder, original in vault.items():
            # Allow minor AI variations like [ email_01 ] or [email_01]
            token = placeholder.strip("[]")
            pattern = re.compile(rf"\[\s*{re.escape(token)}\s*\]", re.IGNORECASE)
            restored = pattern.sub(original, restored)
        return restored


class IA:
    """Unified AI client for OpenAI, DeepSeek, and Gemini with PII masking, cache & rate limiting."""

    PROVIDER_CONFIGS = {
        "openai": {
            "env_key": "OPENAI_API_KEY",
            "url": "https://api.openai.com/v1/chat/completions",
            "default_model": "gpt-6",
        },
        "deepseek": {
            "env_key": "DEEPSEEK_API_KEY",
            "url": "https://api.deepseek.com/chat/completions",
            "default_model": "deepseek-flash",
        },
        "gemini": {
            "env_key": "GEMINI_API_KEY",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "default_model": "gemini-3.8-flash",
        },
    }

    def __init__(
        self,
        provider: str = "gemini",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        rate_limit: int = 20,
        rate_window: int = 60,
        cache_ttl: int = 3600,
        base_url: Optional[str] = None,
    ):
        self.provider = provider.lower().strip()
        conf = self.PROVIDER_CONFIGS.get(self.provider, self.PROVIDER_CONFIGS["openai"])
        self.api_key = api_key or str(ENV_CONFIG.get(conf["env_key"], "")).strip()

        env_model_key = f"{self.provider.upper()}_MODEL"
        self.model = model or str(ENV_CONFIG.get(env_model_key, conf["default_model"])).strip()
        self.endpoint = base_url or conf["url"]
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        self.cache_ttl = cache_ttl

    async def _check_rate_limit(self, identifier: str) -> None:
        """Enforces rate limit per IP or user identifier."""
        if self.rate_limit <= 0:
            return
        cache_key = f"ia:rl:{self.provider}:{identifier}"
        current = await Cache.incr_async(cache_key, ttl=self.rate_window)
        if current > self.rate_limit:
            raise IARateLimitExceeded(
                f"Rate limit exceeded for provider '{self.provider}'. Maximum {self.rate_limit} requests per {self.rate_window}s.",
                retry_after=self.rate_window,
            )

    async def ask(
        self,
        prompt: str,
        data: Optional[Union[dict, list]] = None,
        sensitive_keys: Optional[List[str]] = None,
        request: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        rate_limit_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends a single prompt with optional structured data and sensitive data masking."""
        # 1. Rate limiting
        identifier = rate_limit_key
        if not identifier and request is not None:
            identifier = getattr(request.client, "host", "unknown")
        if not identifier:
            identifier = "global"

        try:
            await self._check_rate_limit(identifier)
        except IARateLimitExceeded as e:
            return {
                "success": False,
                "error": "rate_limit_exceeded",
                "message": e.message,
                "retry_after": e.retry_after,
            }

        # 2. PII Masking
        anon_prompt, anon_data, vault = SensitiveMasker.mask(
            prompt, data=data, sensitive_keys=sensitive_keys
        )

        full_user_content = anon_prompt
        if anon_data:
            full_user_content += "\n\nContext Data:\n" + json.dumps(anon_data, ensure_ascii=False)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": full_user_content})

        # 3. Prompt Hash Cache Hit Check (includes anonymized prompt + anonymized context data)
        cache_hit_hash = hashlib.sha256(
            f"{self.provider}:{self.model}:{system_prompt}:{full_user_content}:{temperature}".encode("utf-8")
        ).hexdigest()
        cache_key = f"ia:cache:{cache_hit_hash}"

        cached_response = None
        if self.cache_ttl > 0:
            cached_response = await Cache.get_async(cache_key)

        if cached_response is not None:
            # Restore sensitive data to cached template!
            restored_text = SensitiveMasker.restore(cached_response, vault)
            return {
                "success": True,
                "text": restored_text,
                "cached": True,
                "masked": vault,
                "provider": self.provider,
                "model": self.model,
            }

        # 4. HTTP API Dispatch (Standardized OpenAI-compatible format)
        try:
            raw_ai_text = await self._call_api(messages, temperature=temperature)
        except Exception as err:
            Logger.error(f"AI API error with {self.provider}: {err}", exception=err)
            return {
                "success": False,
                "error": "api_error",
                "message": str(err),
                "provider": self.provider,
                "model": self.model,
            }

        # 5. Cache the anonymized response (so subsequent users can reuse it safely!)
        if self.cache_ttl > 0 and raw_ai_text:
            await Cache.set_async(cache_key, raw_ai_text, ttl=self.cache_ttl)

        # 6. Restore original sensitive values for this specific caller
        final_text = SensitiveMasker.restore(raw_ai_text, vault)

        return {
            "success": True,
            "text": final_text,
            "cached": False,
            "masked": vault,
            "provider": self.provider,
            "model": self.model,
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        sensitive_keys: Optional[List[str]] = None,
        request: Optional[Any] = None,
        temperature: float = 0.7,
        rate_limit_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Multi-turn chat with PII masking and rate limits."""
        identifier = rate_limit_key or (getattr(request.client, "host", "unknown") if request else "global")
        try:
            await self._check_rate_limit(identifier)
        except IARateLimitExceeded as e:
            return {
                "success": False,
                "error": "rate_limit_exceeded",
                "message": e.message,
                "retry_after": e.retry_after,
            }

        # Mask user messages
        vault: Dict[str, str] = {}
        masked_messages = []
        for msg in messages:
            if msg.get("role") == "user" and sensitive_keys:
                txt, _, v = SensitiveMasker.mask(msg["content"], sensitive_keys=sensitive_keys)
                vault.update(v)
                masked_messages.append({"role": "user", "content": txt})
            else:
                masked_messages.append(msg)

        try:
            raw_text = await self._call_api(masked_messages, temperature=temperature)
            final_text = SensitiveMasker.restore(raw_text, vault)
            return {
                "success": True,
                "text": final_text,
                "masked": vault,
                "provider": self.provider,
                "model": self.model,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "provider": self.provider}

    async def _call_api(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Executes API request in background thread without heavy client libraries."""
        if not self.api_key:
            raise ValueError(
                f"Missing API key for AI provider '{self.provider}'. "
                f"Set {self.provider.upper()}_API_KEY in .env"
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        # DeepSeek specific reasoning support if requested
        if self.provider == "deepseek":
            payload["stream"] = False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Lila-Framework-2.0",
        }

        # For Google Gemini native endpoints requiring ?key= parameter
        req_url = self.endpoint
        if "generativelanguage.googleapis.com" in req_url and "openai" not in req_url:
            req_url = f"{self.endpoint}?key={self.api_key}"

        def _sync_request() -> str:
            body_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(req_url, data=body_bytes, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # Extract output text
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"]
                if "text" in choice:
                    return choice["text"]

            # Fallback for Gemini native v1beta structure
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"]

            return json.dumps(data)

        return await asyncio.to_thread(_sync_request)

    @staticmethod
    def as_response(result: Dict[str, Any]) -> JSONResponse:
        """Returns JSONResponse with appropriate status code (429 for rate limit)."""
        status_code = 200
        if not result.get("success", False):
            if result.get("error") == "rate_limit_exceeded":
                status_code = 429
            else:
                status_code = 500
        return JSONResponse(result, status_code=status_code)
