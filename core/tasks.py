import random
from celery import shared_task

from .models import PostSchedule, BrandVoice
from .services.content_generation import create_post_content


def generate_post_draft(post_id):
    try:
        post = PostSchedule.objects.get(id=post_id)
    except PostSchedule.DoesNotExist:
        return None

    post.status = 'pending'
    post.save()

    post.generated_content = create_post_content(post, BrandVoice.objects.all()).strip()
    if not post.tone:
        post.tone = random.choice(["Professional", "Founder", "Recruiter", "Technical", "Gen-Z", "Storytelling"])

    post.engagement_score = random.randint(70, 99)
    post.readability_score = random.randint(65, 95)
    post.virality_score = random.randint(50, 98)
    post.sentiment = random.choice(["Positive", "Neutral", "Excited", "Professional"])
    post.is_duplicate = False # Could use embeddings/vector db query here
    post.save()
    return post


@shared_task
def run_ai_workflow(post_id):
    post = generate_post_draft(post_id)
    return post.id if post else None
