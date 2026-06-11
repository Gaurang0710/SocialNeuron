"""Django ORM models for authentication and onboarding."""
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import EmailValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Manager for the custom SaaS user model."""

    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email).lower().strip()
        EmailValidator()(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """SaaS-ready custom user."""

    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    @property
    def password_hash(self) -> str:
        return self.password

    def __str__(self) -> str:  # pragma: no cover - representation only
        return self.email


class BrandProfile(models.Model):
    """Onboarding profile for a brand."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="brand_profile")
    brand_name = models.CharField(max_length=255)
    niche = models.CharField(max_length=255)
    audience = models.TextField()
    platforms = models.JSONField(default=list)
    tone = models.CharField(max_length=120)
    goals = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - representation only
        return self.brand_name


class PasswordResetToken(models.Model):
    """Secure reset token with expiry."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def build_token() -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return token, token_hash

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
