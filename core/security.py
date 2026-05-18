import re
from typing import Any, Dict, List, Union

class Security:
    """
    Core security utilities for Lila Framework.
    """
    
    # XSS patterns to detect or remove
    XSS_PATTERNS = [
        (r"<script.*?>.*?</script>", ""),
        (r"on\w+\s*=", ""),  # HTML event handlers like onclick, onload
        (r"javascript:", ""),
        (r"<iframe.*?>.*?</iframe>", ""),
        (r"<object.*?>.*?</object>", ""),
        (r"expression\s*\(", ""), # CSS expressions
    ]

    @staticmethod
    def sanitize_string(value: str) -> str:
        """
        Removes potentially dangerous HTML/JS patterns from a string.
        """
        if not isinstance(value, str):
            return value
        
        sanitized = value
        for pattern, replacement in Security.XSS_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Basic escape for special characters if needed, 
        # but usually we want to keep some HTML for templates.
        # This is a safe middle ground.
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
        Checks if a string contains potential XSS patterns.
        Returns True if potential XSS is found.
        """
        for pattern, _ in Security.XSS_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                return True
        return False
