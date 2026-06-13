import random
from celery import shared_task

from approval.approval_service import notify_content_ready, save_draft
from .models import PostSchedule, BrandVoice, ContentItem
from .services.content_generation import create_post_content
from users.onboarding import build_brand_voice, get_brand_profile


def generate_post_draft(post_id):
    try:
        post = PostSchedule.objects.get(id=post_id)
    except PostSchedule.DoesNotExist:
        return None

    post.status = 'pending'
    post.save()

    brand_profile = get_brand_profile(post.user_id) if post.user_id else None
    brand_voice = build_brand_voice(brand_profile) if brand_profile else None
    post.generated_content = create_post_content(post, BrandVoice.objects.all(), brand_voice=brand_voice).strip()
    if not post.tone:
        post.tone = random.choice(["Professional", "Founder", "Recruiter", "Technical", "Gen-Z", "Storytelling"])

    post.engagement_score = random.randint(70, 99)
    post.readability_score = random.randint(65, 95)
    post.virality_score = random.randint(50, 98)
    post.sentiment = random.choice(["Positive", "Neutral", "Excited", "Professional"])
    post.is_duplicate = False # Could use embeddings/vector db query here
    post.save()
    if post.user_id:
        existing_draft = ContentItem.objects.filter(
            user_id=post.user_id,
            topic=post.topic,
            platform=post.platform,
            post_type="Post",
            generated_content=post.generated_content,
        ).first()
        if existing_draft is None:
            draft = save_draft(
                user_id=post.user_id,
                topic=post.topic,
                platform=post.platform,
                post_type="Post",
                generated_content=post.generated_content,
            )
            notify_content_ready(post.user_id, draft)
    return post


@shared_task
def run_ai_workflow(post_id):
    post = generate_post_draft(post_id)
    return post.id if post else None
