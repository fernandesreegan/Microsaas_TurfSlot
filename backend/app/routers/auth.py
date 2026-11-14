"""Authentication endpoints (``/api/v1/auth``)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.rate_limit import limiter
from app.schemas.auth import (
    AuthConfig,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.schemas.common import ErrorResponse
from app.schemas.user import UserRead, UserUpdate
from app.services import auth_service
from app.services.auth_service import EmailLink
from app.services.email import queue_email

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_LINK_SENT_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)


def _queue_link_email(background_tasks: BackgroundTasks, template: str, link: EmailLink) -> None:
    queue_email(
        background_tasks,
        link.user.email,
        template,
        {
            "recipient_name": link.user.full_name,
            "action_url": link.action_url,
            "expires_text": link.expires_text,
        },
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> User:
    """Create a player/owner account and email a verification link."""
    user, link = auth_service.register_user(db, body)
    _queue_link_email(background_tasks, "verify_email", link)
    return user


@router.post(
    "/login",
    response_model=TokenPair,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Exchange email + password (JSON body) for an access/refresh token pair."""
    user = auth_service.authenticate(db, body.email, body.password)
    return auth_service.issue_token_pair(db, user)


@router.post(
    "/google",
    response_model=TokenPair,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
async def google_login(
    request: Request, body: GoogleLoginRequest, db: Session = Depends(get_db)
) -> TokenPair:
    """Sign in or sign up with a Google Identity Services ID token."""
    return auth_service.google_login(db, body.credential, body.role)


@router.get("/config", response_model=AuthConfig)
async def auth_config() -> AuthConfig:
    """Public auth configuration (e.g. the Google OAuth client id, or null if disabled)."""
    client_id = settings.GOOGLE_CLIENT_ID.strip()
    return AuthConfig(google_client_id=client_id or None)


@router.post(
    "/refresh",
    response_model=TokenPair,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Rotate a refresh token. Reusing a revoked token revokes all of the user's tokens."""
    return auth_service.rotate_refresh_token(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    body: LogoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the given refresh token (idempotent)."""
    auth_service.logout(db, user, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(get_current_user)) -> User:
    """Return the current user."""
    return user


@router.put("/me", response_model=UserRead)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update the current user's ``full_name`` and/or ``phone``."""
    return auth_service.update_profile(db, user, body)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}},
)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Change password; revokes all refresh tokens except ``refresh_token`` (if sent)."""
    auth_service.change_password(
        db, user, body.current_password, body.new_password, body.refresh_token
    )
    return MessageResponse(message="Password changed")


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Email a password-reset link if the account exists. Always returns 200."""
    link = auth_service.create_password_reset_link(db, body.email)
    if link is not None:
        _queue_link_email(background_tasks, "password_reset", link)
    return MessageResponse(message=RESET_LINK_SENT_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}},
)
async def reset_password(
    body: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    """Set a new password using a single-use reset token (revokes all sessions)."""
    auth_service.reset_password(db, body.token, body.new_password)
    return MessageResponse(message="Password has been reset. You can now log in.")


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}},
)
async def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Mark the email verified using a single-use verification token."""
    auth_service.verify_email(db, body.token)
    return MessageResponse(message="Email verified")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}},
)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Send a fresh verification email (400 ``ALREADY_VERIFIED`` if already verified)."""
    link = auth_service.create_verification_link(db, user)
    _queue_link_email(background_tasks, "verify_email", link)
    return MessageResponse(message="Verification email sent")
