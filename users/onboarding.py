"""Brand onboarding and voice utilities."""
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from users.models import BrandProfile

logger = logging.getLogger(__name__)


def save_brand_profile(
    user_id: int,
    brand_name: str,
    niche: str,
    target_audience: str,
    preferred_platforms: list[str] | str,
    writing_tone: str,
    content_goals: list[str] | str,
) -> BrandProfile:
    """Persist onboarding answers as a brand profile."""
    platforms_list = preferred_platforms if isinstance(preferred_platforms, list) else [preferred_platforms]
    goals_list = content_goals if isinstance(content_goals, list) else [content_goals]
    with transaction.atomic():
        profile, _ = BrandProfile.objects.update_or_create(
            user_id=user_id,
            defaults={
                "brand_name": brand_name.strip(),
                "niche": niche.strip(),
                "audience": target_audience.strip(),
                "platforms": platforms_list,
                "tone": writing_tone.strip(),
                "goals": goals_list,
            },
        )
    logger.info("Saved brand profile for user_id=%s", user_id)
    return profile


def get_brand_profile(user_id: int) -> BrandProfile | None:
    """Return the onboarding profile for a user."""
    return BrandProfile.objects.filter(user_id=user_id).first()


def build_brand_voice(profile: BrandProfile | dict[str, Any]) -> dict[str, Any]:
    """Create a reusable brand voice payload."""
    data = profile if isinstance(profile, dict) else {
        "brand_name": profile.brand_name,
        "niche": profile.niche,
        "audience": profile.audience,
        "platforms": profile.platforms,
        "tone": profile.tone,
        "goals": profile.goals,
    }
    platforms = data.get("platforms", [])
    goals = data.get("goals", [])
    voice_summary = (
        f"{data.get('brand_name', '')} speaks to {data.get('audience', '')} in the {data.get('niche', '')} niche "
        f"with a {data.get('tone', '')} tone across {', '.join(platforms) if platforms else 'selected platforms'}."
    ).strip()
    return {
        "voice_summary": voice_summary,
        "writing_style": f"Write clearly, with platform-native structure for {', '.join(platforms) if platforms else 'the target platform'}.",
        "tone_rules": [
            f"Maintain a {data.get('tone', 'professional')} tone.",
            f"Speak directly to {data.get('audience', 'the target audience')}.",
        ],
        "content_rules": [f"Support goals: {', '.join(goals) if goals else 'brand growth' }."],
    }


def onboarding_payload_to_profile(user_id: int, payload: dict[str, Any]) -> BrandProfile:
    """Convert raw onboarding answers into a stored profile."""
    return save_brand_profile(
        user_id=user_id,
        brand_name=str(payload.get("brand_name", "")).strip(),
        niche=str(payload.get("niche", "")).strip(),
        target_audience=str(payload.get("target_audience", "")).strip(),
        preferred_platforms=payload.get("preferred_platforms", []),
        writing_tone=str(payload.get("writing_tone", "")).strip(),
        content_goals=payload.get("content_goals", []),
    )
