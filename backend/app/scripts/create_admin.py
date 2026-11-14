"""Create a verified admin account, or promote an existing account to admin.

Usage::

    python -m app.scripts.create_admin --email admin@example.com --password 'S3curePass' \
        --full-name "Site Admin"

If the email already exists the user is promoted to ``admin``, activated, verified and
its password is replaced with the one given. There is no API path to become an admin.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.database import SessionLocal
from app.models import User, UserRole
from app.schemas.auth import normalize_email, validate_password_policy

logger = logging.getLogger("app.scripts.create_admin")


def create_or_promote_admin(db: Session, email: str, password: str, full_name: str) -> User:
    """Create a verified, active admin or promote an existing user (commits).

    Raises:
        ValueError: If the password does not satisfy the password policy.
    """
    validate_password_policy(password)
    email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.admin,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        action = "Created"
    else:
        user.role = UserRole.admin
        user.is_active = True
        user.is_verified = True
        user.hashed_password = hash_password(password)
        if full_name:
            user.full_name = full_name
        action = "Promoted"
    db.commit()
    db.refresh(user)
    logger.info("%s admin user id=%s email=%s", action, user.id, user.email)
    return user


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or promote a TurfSlot admin user.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Password (min 8, letter + digit)")
    parser.add_argument("--full-name", default="Administrator", help="Display name")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args(argv)
    full_name = args.full_name.strip() or "Administrator"
    db = SessionLocal()
    try:
        create_or_promote_admin(db, args.email, args.password, full_name)
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        return 2
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
