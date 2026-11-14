"""Basic tests for the email service."""

from datetime import UTC, datetime
from email.message import EmailMessage

import pytest

from app.services import email as email_service


def test_formatters() -> None:
    assert email_service.format_money(150000, "INR") == "₹1,500.00"
    assert email_service.format_money(5, "XYZ") == "0.05 XYZ"
    when = datetime(2026, 11, 15, 13, 30, tzinfo=UTC)
    assert email_service.format_local(when, "Asia/Kolkata") == "Sun, 15 Nov 2026 · 7:00 PM"


@pytest.mark.parametrize("template", sorted(email_service.TEMPLATES))
def test_render_all_templates(template: str) -> None:
    ctx = {
        "recipient_name": "<A>",
        "action_url": "http://x",
        "expires_text": "1 hour",
        "booking_ref": "TS7K2M9Q",
        "turf_name": "Turf",
        "start_local": "s",
        "end_local": "e",
        "amount": "₹1.00",
    }
    subject, html, text = email_service.render_email(template, ctx)
    assert subject and "TurfSlot" in html and "&lt;A&gt;" in html and "<A>" in text


def test_send_email_never_raises(email_outbox: list[EmailMessage]) -> None:
    email_service.send_email_sync("a@example.com", "unknown_template", {})
    assert email_outbox == []
    email_service.send_email_sync(
        "a@example.com",
        "verify_email",
        {"recipient_name": "A", "action_url": "u", "expires_text": "1 hour"},
    )
    assert len(email_outbox) == 1 and email_outbox[0]["To"] == "a@example.com"
