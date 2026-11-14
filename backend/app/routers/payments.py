"""Payment provider webhook endpoint."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_payment_gateway
from app.exceptions import UnauthorizedError
from app.schemas.payment import WebhookAck
from app.services.booking_notifications import dispatch
from app.services.payment_gateway import InvalidWebhookSignature, PaymentGateway
from app.services.webhook_service import process_webhook

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhooks/dodo", response_model=WebhookAck)
async def dodo_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> WebhookAck:
    """Verify (Standard Webhooks), de-duplicate by ``webhook-id`` and process an event."""
    body = await request.body()
    try:
        outcome = process_webhook(db, gateway, body, dict(request.headers))
    except InvalidWebhookSignature as exc:
        raise UnauthorizedError("Invalid webhook signature", code="INVALID_SIGNATURE") from exc
    dispatch(background_tasks, outcome.emails)
    return WebhookAck(status=outcome.status)
