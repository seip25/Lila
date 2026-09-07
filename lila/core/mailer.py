"""
English: Async SMTP Mailer for Lila Framework.
         Supports HTML templates, background execution via Starlette BackgroundTask,
         and configuration via ENV_CONFIG (.env).
Español: Motor de correo SMTP asíncrono para Lila Framework.
         Soporta plantillas HTML, ejecución en segundo plano via Starlette BackgroundTask,
         y configuración via ENV_CONFIG (.env).
"""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Union, List
from starlette.background import BackgroundTask
from lila.core.config import ENV_CONFIG
from lila.core.logger import Logger


class Mailer:
    """
    English: Core Mailer utility for sending HTML emails asynchronously.
    Español: Utilidad Mailer central para enviar correos HTML de forma asíncrona.
    """

    @classmethod
    def get_config(cls) -> dict:
        return {
            "host": ENV_CONFIG.get("SMTP_HOST", "127.0.0.1"),
            "port": int(ENV_CONFIG.get("SMTP_PORT", 587)),
            "user": ENV_CONFIG.get("SMTP_USER", ""),
            "password": ENV_CONFIG.get("SMTP_PASSWORD", ""),
            "tls": ENV_CONFIG.get("SMTP_TLS", True),
            "from_email": ENV_CONFIG.get("SMTP_FROM", "noreply@lila.local"),
        }

    @classmethod
    def _send_sync(cls, to: Union[str, List[str]], subject: str, body_html: str, body_text: Optional[str] = None, from_email: Optional[str] = None) -> bool:
        """
        Synchronous SMTP send implementation.
        """
        cfg = cls.get_config()
        sender = from_email or cfg["from_email"]
        recipients = [to] if isinstance(to, str) else to

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            if cfg["tls"]:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)

            if cfg["user"] and cfg["password"]:
                server.login(cfg["user"], cfg["password"])

            server.sendmail(sender, recipients, msg.as_string())
            server.quit()
            Logger.info(f"Email sent successfully to {recipients}")
            return True
        except Exception as e:
            Logger.error(f"Failed to send email to {recipients}: {e}", exception=e)
            return False

    @classmethod
    async def send_email(cls, to: Union[str, List[str]], subject: str, body_html: str, body_text: Optional[str] = None, from_email: Optional[str] = None) -> bool:
        """
        Sends an HTML email asynchronously without blocking the event loop.
        """
        return await asyncio.to_thread(cls._send_sync, to, subject, body_html, body_text, from_email)

    @classmethod
    def send_background(cls, to: Union[str, List[str]], subject: str, body_html: str, body_text: Optional[str] = None, from_email: Optional[str] = None) -> BackgroundTask:
        """
        Returns a Starlette BackgroundTask to send the email in the background after the HTTP response is sent.
        Usage:
            return JSONResponse({"status": "sent"}, background=Mailer.send_background("user@test.com", "Subject", "<h1>Hello</h1>"))
        """
        return BackgroundTask(cls._send_sync, to, subject, body_html, body_text, from_email)
