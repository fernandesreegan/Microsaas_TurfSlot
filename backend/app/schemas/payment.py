"""Payment webhook response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WebhookAck(BaseModel):
    """Acknowledgement returned to the payment provider."""

    status: Literal["processed", "duplicate", "ignored"]
