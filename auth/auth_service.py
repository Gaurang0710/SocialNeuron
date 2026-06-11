"""Authentication service built on Django ORM."""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.core.validators import EmailValidator
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from users.models import PasswordResetToken, User

logger = logging.getLogger(__name__)


def _validate_email(email: str) -> str:
    email = email.strip().lower()
    EmailValidator()(email)
    return email


def _validate_password(password: str) -> None:
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters.")


def create_user(email: str, password: str, is_active: bool = True) -> User:
    """Create a new user with a hashed password."""
    email = _validate_email(email)
    _validate_password(password)
    user = User.objects.create_user(email=email, password=password, is_active=is_active)
    logger.info("Created user %s", email)
    return user


def authenticate_user(email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    email = _validate_email(email)
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return None
    if not user.is_active or not check_password(password, user.password):
        return None
    return user


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """Validate the old password and update to a new bcrypt-hashed password."""
    _validate_password(new_password)
    user = User.objects.get(id=user_id)
    if not check_password(old_password, user.password):
        raise ValueError("Old password is invalid.")
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    logger.info("Password changed for user_id=%s", user_id)
    return True


def create_reset_token(email: str, expiry_minutes: int = 30) -> str:
    """Create a secure reset token with expiry."""
    email = _validate_email(email)
    user = User.objects.get(email=email)
    token, token_hash = PasswordResetToken.build_token()
    expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
    PasswordResetToken.objects.create(user=user, token_hash=token_hash, expires_at=expires_at)
    logger.info("Created reset token for %s", email)
    return token


def reset_password(email: str, token: str, new_password: str) -> bool:
    """Reset password using a token and email verification."""
    email = _validate_email(email)
    _validate_password(new_password)
    user = User.objects.get(email=email)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    reset_token = PasswordResetToken.objects.filter(
        user=user,
        token_hash=token_hash,
        used_at__isnull=True,
    ).order_by("-created_at").first()
    if reset_token is None:
        raise ValueError("Invalid reset token.")
    if reset_token.expires_at <= timezone.now():
        raise ValueError("Reset token expired.")

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        reset_token.used_at = timezone.now()
        reset_token.save(update_fields=["used_at"])
    logger.info("Password reset completed for %s", email)
    return True


def send_password_reset_email(email: str, reset_url: str) -> str:
    """Create a reset token and send the reset URL via email."""
    token = create_reset_token(email)
    message = (
        "We received a request to reset your password.\n\n"
        f"Reset link: {reset_url}?email={email}&token={token}\n\n"
        "If you did not request this, you can ignore this message."
    )
    send_mail(
        subject="Reset your SocialNEURON password",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[_validate_email(email)],
        fail_silently=False,
    )
    return token


def get_user_by_id(user_id: int) -> User | None:
    """Return a user by primary key."""
    return User.objects.filter(id=user_id).first()
