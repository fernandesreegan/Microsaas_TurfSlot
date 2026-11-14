"""Transactional email: Jinja2 rendering + SMTP delivery via ``aiosmtplib``.

Public API (used by auth, bookings, payments webhook and the scheduler)::

    render_email(template, context) -> (subject, html, text)
    await send_email(to, template, context)          # never raises
    queue_email(background_tasks, to, template, context)
    send_email_sync(to, template, context)            # for sync / thread contexts; never raises
    format_money(minor, currency) -> "₹1,500.00"
    format_local(dt_utc, tz) -> "Sat, 15 Nov 2026 · 7:00 PM"

Templates live in ``app/templates/email/`` as ``<name>.html`` and ``<name>.txt``.
The **subject** is defined once, in the ``.txt`` template, inside a
``{% block subject %}...{% endblock %}`` block (whitespace is collapsed). Both bodies
extend a shared base layout and receive the rendered ``subject`` in their context.

Available templates: ``verify_email``, ``password_reset``, ``booking_confirmed``,
``booking_cancelled``, ``refund_processed``, ``refund_failed``, ``late_payment_refunded``.

Only ``_deliver`` talks to SMTP; tests monkeypatch it (see ``tests/conftest.py``).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import aiosmtplib
from fastapi import BackgroundTasks
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
TEMPLATES: frozenset[str] = frozenset(
    {
        "verify_email",
        "password_reset",
        "booking_confirmed",
        "booking_cancelled",
        "refund_processed",
        "refund_failed",
        "late_payment_refunded",
    }
)
SMTP_TIMEOUT_SECONDS = 15

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

# Booking context keys that are optional; default to None so templates can test them.
_OPTIONAL_KEYS: tuple[str, ...] = (
    "refund_amount",
    "cancelled_by",
    "reason",
    "is_owner",
    "booking_url",
    "turf_address",
)

_CURRENCY_SYMBOLS: dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AUD": "A$",
    "CAD": "C$",
    "SGD": "S$",
    "AED": "AED ",
    "JPY": "¥",
}
_ZERO_DECIMAL_CURRENCIES: frozenset[str] = frozenset({"JPY", "KRW", "VND", "CLP", "ISK"})


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_money(minor: int, currency: str) -> str:
    """Format an amount in minor units with its currency, e.g. ``(150000, "INR") -> "₹1,500.00"``.

    Unknown currencies render as ``"1,500.00 XYZ"``; negative amounts get a leading ``-``.
    """
    code = (currency or settings.DEFAULT_CURRENCY).upper()
    sign = "-" if minor < 0 else ""
    value = abs(minor)
    if code in _ZERO_DECIMAL_CURRENCIES:
        number = f"{value:,}"
    else:
        number = f"{value // 100:,}.{value % 100:02d}"
    symbol = _CURRENCY_SYMBOLS.get(code)
    if symbol is None:
        return f"{sign}{number} {code}"
    return f"{sign}{symbol}{number}"


def format_local(dt_utc: datetime, tz: str) -> str:
    """Format a UTC datetime in an IANA timezone, e.g. ``"Sat, 15 Nov 2026 · 7:00 PM"``.

    Naive datetimes are treated as UTC.
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC)
    local = dt_utc.astimezone(ZoneInfo(tz))
    hour12 = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return f"{local:%a}, {local.day} {local:%b %Y} · {hour12}:{local:%M} {meridiem}"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_email(template: str, context: dict[str, Any]) -> tuple[str, str, str]:
    """Render a named email template.

    Args:
        template: One of ``TEMPLATES``.
        context: Template variables (see module docstring for the expected keys).

    Returns:
        ``(subject, html_body, text_body)``.

    Raises:
        ValueError: Unknown template name.
        jinja2.TemplateError: Missing required context keys or template errors.
    """
    if template not in TEMPLATES:
        raise ValueError(f"Unknown email template: {template!r}")
    ctx: dict[str, Any] = dict.fromkeys(_OPTIONAL_KEYS)
    ctx.update(context)
    ctx.setdefault("app_name", "TurfSlot")
    ctx.setdefault("frontend_url", settings.FRONTEND_URL.rstrip("/"))

    text_tmpl = _env.get_template(f"{template}.txt")
    subject_block = text_tmpl.blocks.get("subject")
    if subject_block is None:  # pragma: no cover - guarded by template tests
        raise ValueError(f"Template {template!r} has no subject block")
    raw_subject = "".join(subject_block(text_tmpl.new_context(ctx)))
    subject = " ".join(raw_subject.split())
    ctx["subject"] = subject

    html = _env.get_template(f"{template}.html").render(ctx)
    text = text_tmpl.render(ctx)
    return subject, html, text


def _build_message(to: str, subject: str, html: str, text: str) -> EmailMessage:
    """Build a multipart/alternative message (text first, HTML preferred)."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = make_msgid(domain="turfslot.local")
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


async def _deliver(msg: EmailMessage) -> None:
    """Send a message over SMTP. The only function that performs network I/O.

    Port 465 uses implicit TLS; otherwise STARTTLS is used opportunistically when the
    server advertises it (Mailpit in dev does not).
    """
    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=settings.SMTP_PORT == 465,
        timeout=SMTP_TIMEOUT_SECONDS,
    )


async def send_email(to: str, template: str, context: dict[str, Any]) -> None:
    """Render and deliver an email. Never raises: all errors are logged and swallowed."""
    try:
        subject, html, text = render_email(template, context)
        msg = _build_message(to, subject, html, text)
        await _deliver(msg)
        logger.info("Sent %s email", template)
    except Exception:
        logger.exception("Failed to send %s email", template)


def queue_email(
    background_tasks: BackgroundTasks, to: str, template: str, context: dict[str, Any]
) -> None:
    """Schedule ``send_email`` to run after the response is sent."""
    background_tasks.add_task(send_email, to, template, dict(context))


def _run_in_new_thread(to: str, template: str, context: dict[str, Any]) -> None:
    """Run ``send_email`` on a fresh event loop in a worker thread and wait for it."""

    def _target() -> None:
        try:
            asyncio.run(send_email(to, template, context))
        except Exception:  # pragma: no cover - send_email already swallows errors
            logger.exception("Failed to send %s email from worker thread", template)

    worker = threading.Thread(target=_target, name="send-email", daemon=True)
    worker.start()
    worker.join(timeout=SMTP_TIMEOUT_SECONDS * 2)


def send_email_sync(to: str, template: str, context: dict[str, Any]) -> None:
    """Send an email from synchronous code (scheduler jobs, sync services). Never raises.

    If no event loop is running in this thread, ``asyncio.run`` is used directly;
    otherwise the send is performed on a new event loop in a short-lived thread so the
    running loop is not re-entered.
    """
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(send_email(to, template, context))
        else:
            _run_in_new_thread(to, template, context)
    except Exception:
        logger.exception("Failed to send %s email synchronously", template)
