"""Lila Framework regression tests (stdlib unittest, no extra dependencies).

Run with:
    python -m unittest discover -s tests -v
"""

import os

# Keep tests hermetic: never generate .lila_secret in the repository root.
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")
os.environ.setdefault("CACHE_DRIVER", "memory")
