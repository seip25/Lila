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

    # ── Jinja templates ──────────────────────────────────────────────────────
    @classmethod
    def render_template(cls, template: str, context: Optional[dict] = None,
                        lang: Optional[str] = None) -> tuple:
        """Renders ``resources/html/emails/<template>.jinja`` → ``(subject, html, text)``.

        Templates usually ``{% extends "emails/base.jinja" %}`` (inline styles,
        works in Gmail/Outlook) and may set ``{% set subject = "..." %}``.
        """
        from lila.core.templates import jinja_env, public
        from lila.core.translate import Translate

        name = template if template.endswith((".jinja", ".html")) else f"{template}.jinja"
        if not name.startswith("emails/"):
            name = f"emails/{name}"
        current_lang = (lang or str(ENV_CONFIG.get("LANG_DEFAULT", "en")))[:2].lower()
        app_url = str(ENV_CONFIG.get("APP_URL", "") or "").rstrip("/")
        ctx = {
            "app_url": app_url,
            "project": ENV_CONFIG.get("TITLE_PROJECT", "Lila"),
            "lang": current_lang,
            "translate": Translate.get_dict(current_lang),
            "absolute": lambda path: f"{app_url}{public(path)}" if not str(path).startswith("http") else path,
        }
        ctx.update(context or {})
        tmpl = jinja_env.get_template(name)
        module = tmpl.make_module(ctx)
        html_body = str(module)
        subject = str(ctx.get("subject") or getattr(module, "subject", "") or ctx["project"])
        return subject, html_body, _html_to_text(html_body)

    @classmethod
    async def send_template(cls, to: Union[str, List[str]], template: str, context: Optional[dict] = None,
                            subject: Optional[str] = None, lang: Optional[str] = None,
                            queue: bool = False, from_email: Optional[str] = None) -> Union[bool, int]:
        """Renders a Jinja email and sends it.

        ``queue=True`` stores it in the SQLite task queue (retries with
        backoff, survives restarts) and returns the task id; otherwise sends
        now in a thread and returns True/False.
        """
        rendered_subject, html_body, text_body = await asyncio.to_thread(
            cls.render_template, template, context, lang
        )
        final_subject = subject or rendered_subject
        if queue:
            from lila.core.tasks import enqueue

            return await enqueue("lila.core.mailer:send_queued_email",
                                 kwargs={"to": to, "subject": final_subject, "body_html": html_body,
                                         "body_text": text_body, "from_email": from_email},
                                 retries=int(ENV_CONFIG.get("MAIL_RETRIES", 4) or 4), timeout=60)
        return await cls.send_email(to, final_subject, html_body, text_body, from_email)

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


def _html_to_text(html_body: str) -> str:
    """Plain-text alternative (better deliverability, readable in any client)."""
    import html as _html
    import re

    text = re.sub(r"(?is)<(script|style|head).*?</\1>", "", html_body)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</h[1-6]>|</tr>|</li>|</div>", "\n", text)
    text = re.sub(r'(?is)<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def send_queued_email(to, subject, body_html, body_text=None, from_email=None):
    """Task used by ``Mailer.send_template(..., queue=True)``; raising makes the queue retry."""
    if not Mailer._send_sync(to, subject, body_html, body_text, from_email):
        raise RuntimeError("SMTP send failed")
