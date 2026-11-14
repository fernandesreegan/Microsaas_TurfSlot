"""Dodo Payments implementation of :class:`~app.services.payment_gateway.PaymentGateway`.

Verified against the installed ``dodopayments`` SDK (v1.126.0):

- Client: ``DodoPayments(bearer_token=..., environment="test_mode" | "live_mode")``.
- Checkout: ``client.checkout_sessions.create(product_cart=[{"product_id", "quantity",
  "amount"}], customer={"email", "name"}, metadata={...}, return_url=...)`` returns
  ``CheckoutSessionResponse(session_id, checkout_url, payment_id?)``. ``amount`` on a cart
  line is honoured only for a "pay what you want" product and is in minor units.
- Refund: ``client.refunds.create(payment_id=..., reason=..., metadata={...})`` returns
  ``Refund(refund_id, status, payment_id, ...)``. Omitting ``items`` refunds in full.
- Errors: every SDK error derives from ``dodopayments.DodoPaymentsError``.
- Webhooks use Standard Webhooks; we verify with our own helper so the behaviour is the
  same for the fake and real gateways.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from dodopayments import DodoPayments, DodoPaymentsError

from app.config import settings
from app.services.payment_gateway import (
    CheckoutResult,
    PaymentGatewayError,
    RefundResult,
    verify_standard_webhook,
)

if TYPE_CHECKING:
    from app.models import Booking, Payment, User

logger = logging.getLogger(__name__)

_REFUND_REASON_MAX = 3000


class DodoPaymentGateway:
    """Payment gateway backed by the Dodo Payments API."""

    def __init__(self, client: DodoPayments | None = None) -> None:
        """Build the gateway from settings (``client`` may be injected for tests)."""
        self._product_id = settings.DODO_BOOKING_PRODUCT_ID
        self._webhook_secret = settings.DODO_PAYMENTS_WEBHOOK_SECRET
        self._frontend_url = settings.FRONTEND_URL.rstrip("/")
        self._client = client or DodoPayments(
            bearer_token=settings.DODO_PAYMENTS_API_KEY,
            environment=settings.DODO_PAYMENTS_ENVIRONMENT,
        )

    def create_checkout(self, booking: Booking, customer: User) -> CheckoutResult:
        """Create a hosted checkout session charging ``booking.total_amount``.

        Raises:
            PaymentGatewayError: On any SDK/API failure or a response without a URL.
        """
        try:
            session = self._client.checkout_sessions.create(
                product_cart=[
                    {
                        "product_id": self._product_id,
                        "quantity": 1,
                        "amount": booking.total_amount,
                    }
                ],
                customer={"email": customer.email, "name": customer.full_name},
                metadata={"booking_id": str(booking.id), "booking_ref": booking.booking_ref},
                return_url=f"{self._frontend_url}/bookings/{booking.id}",
            )
        except DodoPaymentsError as exc:
            logger.error("Dodo checkout creation failed for booking %s: %s", booking.id, exc)
            raise PaymentGatewayError("Could not create checkout session") from exc
        if not session.checkout_url:
            raise PaymentGatewayError("Dodo returned a checkout session without a URL")
        return CheckoutResult(
            checkout_session_id=session.session_id,
            checkout_url=session.checkout_url,
            provider_payment_id=session.payment_id,
        )

    def refund(self, payment: Payment, reason: str) -> RefundResult:
        """Request a full refund of ``payment``.

        Raises:
            PaymentGatewayError: If the payment has no provider id or the API call fails.
        """
        if not payment.provider_payment_id:
            raise PaymentGatewayError("Payment has no provider payment id to refund")
        try:
            refund = self._client.refunds.create(
                payment_id=payment.provider_payment_id,
                reason=reason[:_REFUND_REASON_MAX],
                metadata={"booking_id": str(payment.booking_id)},
            )
        except DodoPaymentsError as exc:
            logger.error("Dodo refund failed for payment %s: %s", payment.id, exc)
            raise PaymentGatewayError("Could not create refund") from exc
        return RefundResult(provider_refund_id=refund.refund_id, status=str(refund.status))

    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
        """Verify a Standard Webhooks signature with ``DODO_PAYMENTS_WEBHOOK_SECRET``."""
        return verify_standard_webhook(self._webhook_secret, body, headers)
