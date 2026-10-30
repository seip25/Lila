"""Lila Framework v2.0.1 Security Utilities.
Provides optional sanitization, path traversal checks, and security headers.
"""

import html
import os
import re
from typing import Any, Union


DANGEROUS_PATTERNS = re.compile(
    r"(<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>|"
    r"javascript:[^\s\"'>]+|"
    r"on(?:click|load|error|mouseover|submit|focus|blur)\s*=)",
    re.IGNORECASE,
)


class Security:
    """Security utility class for sanitization and vulnerability prevention."""

    @staticmethod
    def escape(val: str) -> str:
        """HTML escapes untrusted input."""
        return html.escape(str(val))

    @staticmethod
    def check_xss(text: str) -> bool:
        """Returns True if input contains malicious script patterns."""
        if not text:
            return False
        return bool(DANGEROUS_PATTERNS.search(str(text)))

    @staticmethod
    def sanitize_str(text: str) -> str:
        """Sanitizes text removing potential injection tags while preserving normal characters."""
        if not text:
            return ""
        # Remove direct script tags and inline events
        clean = DANGEROUS_PATTERNS.sub("", str(text))
        return clean

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """Recursively sanitizes dict, list or string payloads when explicitly requested."""
        if isinstance(data, str):
            return cls.sanitize_str(data)
        if isinstance(data, dict):
            return {k: cls.sanitize_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        return data

    @staticmethod
    def is_safe_path(path_str: str) -> bool:
        """Checks if a path attempts directory traversal or escapes the base."""
        if not path_str:
            return False
        normalized = os.path.normpath(str(path_str).replace("\\", "/"))
        if normalized in ("..", ".") or normalized.startswith("../") or "/../" in normalized:
            return False
        if os.path.isabs(path_str):
            return False
        if len(normalized) > 1 and normalized[1] == ":":
            return False
        return True

    @staticmethod
    def default_security_headers() -> dict[str, str]:
        """Returns recommended security headers for ASGI responses."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

