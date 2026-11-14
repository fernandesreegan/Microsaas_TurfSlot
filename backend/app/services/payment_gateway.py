"""Payment gateway abstraction.

All provider-specific code (Dodo Payments) lives behind :class:`PaymentGateway` so
tests and local development can use :class:`FakePaymentGateway`.

Routers obtain a gateway with ``gateway: PaymentGateway = Depends(get_payment_gateway)``;
tests override it via ``app.dependency_overrides[get_payment_gateway]``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from standardwebhooks import Webhook, WebhookVerificationError

from app.config import settings

if TYPE_CHECKING:
    from app.models import Booking, Payment, User

logger = logging.getLogger(__name__)


class InvalidWebhookSignature(Exception):  # noqa: N818 - name fixed by the shared contract
    """Raised when a webhook's signature/timestamp cannot be verified."""


class PaymentGatewayError(Exception):
    """Raised when the payment provider call fails (network/API error)."""


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    """Result of creating a hosted checkout session."""

    checkout_session_id: str
    checkout_url: str
    provider_payment_id: str | None = None


@dataclass(frozen=True, slots=True)
class RefundResult:
    """Result of requesting a refund. Final state arrives via ``refund.*`` webhooks."""

    provider_refund_id: str
    status: str = "pending"


@runtime_checkable
class PaymentGateway(Protocol):
    """Interface every payment provider implementation must satisfy."""

    def create_checkout(self, booking: Booking, customer: User) -> CheckoutResult:
        """Create a hosted checkout for ``booking.total_amount`` and return its id + URL."""
        ...

    def refund(self, payment: Payment, reason: str) -> RefundResult:
        """Request a full refund of a succeeded payment."""
        ...

    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
        """Verify the webhook signature and return the parsed JSON payload.

        Raises:
            InvalidWebhookSignature: On a bad signature, missing headers or stale timestamp.
        """
        ...


def verify_standard_webhook(secret: str, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
    """Verify a Standard Webhooks signed request (``webhook-id/-timestamp/-signature``).

    The ``standardwebhooks`` library rejects timestamps outside a 5-minute tolerance.

    Args:
        secret: The webhook signing secret (``whsec_...`` or raw base64).
        body: Raw request body bytes.
        headers: Request headers (case-insensitive lookup is handled here).

    Returns:
        The parsed JSON payload.

    Raises:
        InvalidWebhookSignature: If verification fails for any reason.
    """
    if not secret:
        raise InvalidWebhookSignature("Webhook secret is not configured")
    normalized = {k.lower(): v for k, v in headers.items()}
    try:
        payload = Webhook(secret).verify(body, normalized)
    except (WebhookVerificationError, ValueError, TypeError) as exc:
        raise InvalidWebhookSignature(str(exc) or "Invalid webhook signature") from exc
    if not isinstance(payload, dict):
        raise InvalidWebhookSignature("Webhook payload must be a JSON object")
    return payload


@dataclass
class FakePaymentGateway:
    """Deterministic in-memory gateway for tests and local development.

    - ``create_checkout`` returns ``fake_cs_{booking.id}`` and a URL to the frontend booking
      page with ``?fake_checkout=1``.
    - ``refund`` returns ``fake_rf_{payment.id}``.
    - ``verify_webhook`` verifies Standard Webhooks signatures when ``webhook_secret`` is
      set (sign test payloads with ``standardwebhooks.Webhook(secret).sign(...)``);
      otherwise it only requires a ``webhook-id`` header and valid JSON.

    Calls are recorded in ``checkouts`` / ``refunds`` for test assertions.
    """

    webhook_secret: str = ""
    frontend_url: str = field(default_factory=lambda: settings.FRONTEND_URL)
    checkouts: list[int] = field(default_factory=list)
    refunds: list[tuple[int, str]] = field(default_factory=list)

    def create_checkout(self, booking: Booking, customer: User) -> CheckoutResult:
        """Return a fake checkout session pointing back at the frontend booking page."""
        self.checkouts.append(booking.id)
        base = self.frontend_url.rstrip("/")
        return CheckoutResult(
            checkout_session_id=f"fake_cs_{booking.id}",
            checkout_url=f"{base}/bookings/{booking.id}?fake_checkout=1",
            provider_payment_id=None,
        )

    def refund(self, payment: Payment, reason: str) -> RefundResult:
        """Return a fake pending refund id."""
        self.refunds.append((payment.id, reason))
        return RefundResult(provider_refund_id=f"fake_rf_{payment.id}", status="pending")

    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
        """Verify (if a secret is set) and parse a webhook body."""
        if self.webhook_secret:
            return verify_standard_webhook(self.webhook_secret, body, headers)
        normalized = {k.lower(): v for k, v in headers.items()}
        if not normalized.get("webhook-id"):
            raise InvalidWebhookSignature("Missing webhook-id header")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidWebhookSignature("Invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise InvalidWebhookSignature("Webhook payload must be a JSON object")
        return payload


@lru_cache(maxsize=1)
def _build_gateway() -> PaymentGateway:
    """Construct the process-wide gateway once, based on settings."""
    if settings.uses_fake_payments:
        logger.info("Using FakePaymentGateway (DODO_PAYMENTS_API_KEY is empty or 'fake')")
        return FakePaymentGateway(webhook_secret=settings.DODO_PAYMENTS_WEBHOOK_SECRET)
    try:
        from app.services.dodo import DodoPaymentGateway  # lazy: optional module
    except ImportError:
        logger.exception("app.services.dodo is unavailable; falling back to FakePaymentGateway")
        return FakePaymentGateway(webhook_secret=settings.DODO_PAYMENTS_WEBHOOK_SECRET)
    gateway: PaymentGateway = DodoPaymentGateway()
    return gateway


def get_payment_gateway() -> PaymentGateway:
    """FastAPI dependency returning the configured payment gateway (singleton)."""
    return _build_gateway()
