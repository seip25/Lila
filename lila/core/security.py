import re
from typing import Any, Dict, List, Union

class Security:
    """
    Core security utilities for Lila Framework with pre-compiled XSS regex.
    """
    _COMPILED_XSS_PATTERNS = [
        (re.compile(r"<script.*?>.*?</script>", flags=re.IGNORECASE | re.DOTALL), ""),
        (re.compile(r"on\w+\s*=", flags=re.IGNORECASE | re.DOTALL), ""),
        (re.compile(r"javascript:", flags=re.IGNORECASE | re.DOTALL), ""),
        (re.compile(r"<iframe.*?>.*?</iframe>", flags=re.IGNORECASE | re.DOTALL), ""),
        (re.compile(r"<object.*?>.*?</object>", flags=re.IGNORECASE | re.DOTALL), ""),
        (re.compile(r"expression\s*\(", flags=re.IGNORECASE | re.DOTALL), ""),
    ]

    @staticmethod
    def sanitize_string(value: str) -> str:
        """
        Removes potentially dangerous HTML/JS patterns from a string using pre-compiled regex.
        """
        if not isinstance(value, str):
            return value
        
        sanitized = value
        for pattern, replacement in Security._COMPILED_XSS_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        
        return sanitized

    @staticmethod
    def sanitize_data(data: Any) -> Any:
        """
        Recursively sanitizes dictionaries, lists, or strings.
        """
        if isinstance(data, str):
            return Security.sanitize_string(data)
        elif isinstance(data, dict):
            return {k: Security.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Security.sanitize_data(item) for item in data]
        return data

    @staticmethod
    def check_xss(text: str) -> bool:
        """
        Checks if a string contains potential XSS patterns using pre-compiled regex.
        Returns True if potential XSS is found.
        """
        if not text:
            return False
        for pattern, _ in Security._COMPILED_XSS_PATTERNS:
            if pattern.search(text):
                return True
        return False
