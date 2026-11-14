"""Shared slowapi rate limiter.

Usage in routers::

    from fastapi import Request
    from app.rate_limit import limiter

    @router.post("/login")
    @limiter.limit("10/minute")
    async def login(request: Request, ...): ...

The endpoint must accept a ``request: Request`` parameter for slowapi to work.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)
