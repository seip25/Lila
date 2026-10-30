"""Lila Framework v2.0.1 Two-Factor Authentication (TOTP / RFC 6238).
Generates secrets, computes and validates 6-digit TOTP tokens,
and produces real scannable QR codes for Google Authenticator / Authy.
"""

import base64
import hmac
import hashlib
import struct
import time
import os
import html
import urllib.parse
from typing import Optional


class TwoFactor:
    """RFC 6238 TOTP Engine."""

    @staticmethod
    def generate_secret(length: int = 20) -> str:
        """Generates a random Base32 secret (160 bits by default)."""
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        random_bytes = os.urandom(length)
        return "".join(alphabet[b % 32] for b in random_bytes)

    @staticmethod
    def get_totp_code(secret: str, interval: int = 30, for_time: Optional[float] = None) -> str:
        """Computes 6-digit TOTP code for timestamp according to RFC 6238."""
        if for_time is None:
            for_time = time.time()

        secret_clean = secret.upper().replace(" ", "").rstrip("=")
        missing_padding = len(secret_clean) % 8
        if missing_padding:
            secret_clean += "=" * (8 - missing_padding)

        key = base64.b32decode(secret_clean, casefold=True)
        time_counter = int(for_time // interval)
        msg = struct.pack(">Q", time_counter)
        hmac_digest = hmac.new(key, msg, hashlib.sha1).digest()

        offset = hmac_digest[-1] & 0x0F
        code_int = struct.unpack(">I", hmac_digest[offset:offset + 4])[0] & 0x7FFFFFFF
        otp = code_int % 1000000
        return f"{otp:06d}"

    @classmethod
    def verify_code(cls, secret: str, code: str, window: int = 1, interval: int = 30) -> bool:
        """Verifies 6-digit TOTP code with time drift window."""
        if not secret or not code:
            return False

        clean_code = str(code).strip()
        if len(clean_code) != 6 or not clean_code.isdigit():
            return False

        now = time.time()
        for i in range(-window, window + 1):
            target_time = now + (i * interval)
            expected = cls.get_totp_code(secret, interval=interval, for_time=target_time)
            if hmac.compare_digest(expected, clean_code):
                return True
        return False

    @staticmethod
    def get_otpauth_url(secret: str, user_label: str, issuer: str = "LilaApp") -> str:
        """Returns otpauth:// URI for authenticator apps."""
        label_encoded = urllib.parse.quote(f"{issuer}:{user_label}")
        issuer_encoded = urllib.parse.quote(issuer)
        return (
            f"otpauth://totp/{label_encoded}?secret={secret}"
            f"&issuer={issuer_encoded}&algorithm=SHA1&digits=6&period=30"
        )

    @classmethod
    def generate_qr_svg(cls, otpauth_uri: str, size: int = 240) -> str:
        """Generates scannable QR Code SVG string for Google Authenticator."""
        # 1. Try qrcode library if installed
        try:
            import qrcode
            import qrcode.image.svg
            import io
            factory = qrcode.image.svg.SvgPathImage
            img = qrcode.make(otpauth_uri, image_factory=factory, box_size=10)
            buf = io.BytesIO()
            img.save(buf)
            return buf.getvalue().decode("utf-8")
        except ImportError:
            pass

        # 2. Try segno library if installed
        try:
            import segno
            import io
            qr = segno.make(otpauth_uri)
            buf = io.BytesIO()
            qr.save(buf, kind="svg", border=2, dark="#0f172a", light="#ffffff")
            return buf.getvalue().decode("utf-8")
        except ImportError:
            pass

        # 3. No third-party network call: never send a TOTP secret to a QR API.
        #    Render the otpauth URI + secret so the user can add it manually.
        return (
            '<div class="flex flex-col items-center justify-center gap-3 p-4 bg-white rounded-2xl border border-slate-200 dark:border-slate-800">'
            '<p class="text-xs text-slate-500 m-0">Install the <code>qrcode</code> or <code>segno</code> extra for an inline QR code, '
            "or add this account manually in your authenticator app:</p>"
            f'<code class="text-[11px] break-all bg-slate-50 p-2 rounded">{html.escape(otpauth_uri)}</code>'
            "</div>"
        )


TOTP = TwoFactor

