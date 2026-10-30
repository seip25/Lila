"""Lila Framework v2.0.x Async Mailer.

Sends HTML & plain-text emails asynchronously or via background tasks.
Supports STARTTLS and implicit SSL (port 465), verifies TLS certificates and
blocks CR/LF header injection.
"""

import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Union, List

from starlette.background import BackgroundTask

from lila.core.config import ENV_CONFIG
from lila.core.logger import Logger


def _clean_header(value: str) -> str:
    return str(value or "").replace("\r", "").replace("\n", "").strip()


class Mailer:
    """Core Mailer utility for asynchronous SMTP email sending."""

    @classmethod
    def get_config(cls) -> dict:
        try:
            port = int(ENV_CONFIG.get("SMTP_PORT", 587))
        except (TypeError, ValueError):
            port = 587
        return {
            "host": _clean_header(ENV_CONFIG.get("SMTP_HOST", "127.0.0.1")),
            "port": port,
            "user": str(ENV_CONFIG.get("SMTP_USER", "") or ""),
            "password": str(ENV_CONFIG.get("SMTP_PASSWORD", "") or ""),
            "tls": ENV_CONFIG.get_bool("SMTP_TLS", True),
            "ssl": ENV_CONFIG.get_bool("SMTP_SSL", False) or port == 465,
            "from_email": _clean_header(ENV_CONFIG.get("SMTP_FROM", "noreply@lila.local")),
        }

    @classmethod
    def _send_sync(
        cls,
        to: Union[str, List[str]],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> bool:
        cfg = cls.get_config()
        sender = _clean_header(from_email or cfg["from_email"])
        recipients = [to] if isinstance(to, str) else list(to or [])
        recipients = [_clean_header(addr) for addr in recipients if _clean_header(addr)]
        if not recipients:
            Logger.error("Mailer: no valid recipients")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = _clean_header(subject)
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        server = None
        try:
            context = ssl.create_default_context()
            if cfg["ssl"]:
                server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15, context=context)
            else:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
                server.ehlo()
                if cfg["tls"]:
                    server.starttls(context=context)
                    server.ehlo()
            if cfg["user"] and cfg["password"]:
                server.login(cfg["user"], cfg["password"])
            server.sendmail(sender, recipients, msg.as_string())
            Logger.info(f"Email sent successfully to {recipients}")
            return True
        except Exception as exc:
            Logger.error(f"Failed to send email to {recipients}: {exc}", exception=exc)
            return False
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass

    @classmethod
    async def send_email(
        cls,
        to: Union[str, List[str]],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> bool:
        """Sends an HTML email without blocking the event loop."""
        return await asyncio.to_thread(cls._send_sync, to, subject, body_html, body_text, from_email)

    @classmethod
    def send_background(
        cls,
        to: Union[str, List[str]],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> BackgroundTask:
        """Returns a Starlette BackgroundTask for post-response execution."""
        return BackgroundTask(cls._send_sync, to, subject, body_html, body_text, from_email)
