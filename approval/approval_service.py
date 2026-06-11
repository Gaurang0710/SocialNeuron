"""Content approval workflow."""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from auth.auth_service import get_user_by_id
from core.models import ContentItem

logger = logging.getLogger(__name__)


def save_draft(user_id: int, topic: str, platform: str, post_type: str, generated_content: str) -> ContentItem:
    """Persist a draft content item."""
    return ContentItem.objects.create(
        user_id=user_id,
        topic=topic,
        platform=platform,
        post_type=post_type,
        generated_content=generated_content,
        status="DRAFT",
    )


def notify_content_ready(user_id: int, content_item: ContentItem) -> bool:
    """Send a review email for a newly generated draft."""
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found.")
    subject = "Content Ready For Review"
    message = (
        f"Topic: {content_item.topic}\n"
        f"Platform: {content_item.platform}\n"
        f"Generated content:\n{content_item.generated_content}\n\n"
        f"Current status: {content_item.status}"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    logger.info("Sent review email to %s for content_id=%s", user.email, content_item.id)
    return True


def approve_content(content_id: int, user_id: int) -> bool:
    """Approve a content item only for the owning user."""
    updated = ContentItem.objects.filter(id=content_id, user_id=user_id).update(status="APPROVED")
    if not updated:
        raise ValueError("Content not found for user.")
    return True


def reject_content(content_id: int, user_id: int) -> bool:
    """Reject a content item only for the owning user."""
    updated = ContentItem.objects.filter(id=content_id, user_id=user_id).update(status="REJECTED")
    if not updated:
        raise ValueError("Content not found for user.")
    return True


def _list_by_status(user_id: int, status: str) -> list[ContentItem]:
    return list(ContentItem.objects.filter(user_id=user_id, status=status).order_by("-created_at"))


def list_drafts(user_id: int) -> list[ContentItem]:
    return _list_by_status(user_id, "DRAFT")


def list_approved(user_id: int) -> list[ContentItem]:
    return _list_by_status(user_id, "APPROVED")


def list_rejected(user_id: int) -> list[ContentItem]:
    return _list_by_status(user_id, "REJECTED")


def get_content_item(content_id: int, user_id: int) -> ContentItem | None:
    """Fetch a content item scoped to a user."""
    return ContentItem.objects.filter(id=content_id, user_id=user_id).first()
