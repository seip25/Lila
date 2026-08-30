import re
import html
from typing import Any, Dict, List, Union


class Security:
    """
    Security utilities for Lila Framework.
    Provides HTML sanitization and string escaping without breaking URL parameters.
    """

    _DANGEROUS_TAGS_PATTERN = re.compile(
        r"<\s*(script|iframe|object|embed|applet|meta|link|style)[^>]*>.*?<\s*/\s*\1\s*>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    _DANGEROUS_SELF_CLOSING = re.compile(
        r"<\s*(script|iframe|object|embed|applet|meta|link|style)[^>]*/>",
        flags=re.IGNORECASE,
    )
    _JAVASCRIPT_URI = re.compile(r"javascript:\s*", flags=re.IGNORECASE)

    @staticmethod
    def escape_html(value: str) -> str:
        """Escape HTML special characters to prevent XSS in rendered outputs."""
        if not isinstance(value, str):
            return value
        return html.escape(value)

    @staticmethod
    def sanitize_string(value: str) -> str:
        """
        Removes dangerous executable HTML tags (<script>, <iframe>, etc.) and javascript: URIs.
        Safe for text processing without false-positive blocking of valid URL query parameters.
        """
        if not isinstance(value, str):
            return value

        sanitized = Security._DANGEROUS_TAGS_PATTERN.sub("", value)
        sanitized = Security._DANGEROUS_SELF_CLOSING.sub("", sanitized)
        sanitized = Security._JAVASCRIPT_URI.sub("", sanitized)
        return sanitized

    @staticmethod
    def sanitize_data(data: Any) -> Any:
        """Recursively sanitizes dictionaries, lists, or strings."""
        if isinstance(data, str):
            return Security.sanitize_string(data)
        elif isinstance(data, dict):
            return {k: Security.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Security.sanitize_data(item) for item in data]
        return data
