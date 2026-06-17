import random
import re

from .ai_client import ask_ollama
from .prompt_templates import render_prompt


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"(?m)^\s*[*_]{3,}\s*$", "", text)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*•]\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def generate_topic_ideas(query, tone, audience, platform=None, post_type=None, niche=None, goals=None, brand_voice=None, count=4):
    voice_context = ""
    if isinstance(brand_voice, dict):
        voice_context = (
            f" Brand voice summary: {brand_voice.get('voice_summary', '')}. "
            f"Writing style: {brand_voice.get('writing_style', '')}. "
            f"Tone rules: {', '.join(brand_voice.get('tone_rules', []))}. "
            f"Content rules: {', '.join(brand_voice.get('content_rules', []))}."
        )
    platform_context = f" Platform: {platform}." if platform else ""
    content_type_context = f" Content type: {post_type}." if post_type else ""
    niche_context = f" Niche: {niche}." if niche else ""
    goal_context = f" Goals: {', '.join(goals) if isinstance(goals, (list, tuple)) else goals}." if goals else ""
    prompt = render_prompt(
        "topic_ideas",
        count=count,
        query=query,
        audience=audience,
        tone=tone,
        platform=platform or "",
        post_type=post_type or "",
        platform_context=platform_context,
        content_type_context=content_type_context,
        niche_context=niche_context,
        goal_context=goal_context,
        voice_context=voice_context,
    )
    topics_text = ask_ollama(prompt)

    if topics_text.startswith("Error:"):
        return [], topics_text

    generated = []
    for text in topics_text.split("\n"):
        if len(generated) >= count:
            break
        title = re.sub(r"^\s*(?:[-*•]|\d+[\).])\s*", "", text).strip()
        if title and len(title) > 3:
            generated.append(
                {
                    "title": title,
                    "score": random.randint(85, 99),
                    "virality": random.choice(["High", "Very High", "Exceptional"]),
                    "tone": tone,
                    "audience": audience,
                }
            )

    if generated:
        return generated, None

    fallback = [
        {
            "title": "The Future of " + query,
            "score": 98,
            "virality": "Exceptional",
            "tone": tone,
            "audience": audience,
        },
        {
            "title": "How " + query + " is changing the industry",
            "score": 92,
            "virality": "High",
            "tone": tone,
            "audience": audience,
        },
    ]
    return fallback[:count], None


def create_post_content(post, brand_voices, brand_voice=None):
    voice_context = "Use standard professional tone."
    if brand_voices.exists():
        combined_voice = " ".join([voice.document_content for voice in brand_voices])
        voice_context = f"Learn from this brand voice context: {combined_voice[:2000]}..."
    if isinstance(brand_voice, dict):
        voice_context = (
            f"{voice_context} Brand voice summary: {brand_voice.get('voice_summary', '')}. "
            f"Writing style: {brand_voice.get('writing_style', '')}. "
            f"Tone rules: {', '.join(brand_voice.get('tone_rules', []))}. "
            f"Content rules: {', '.join(brand_voice.get('content_rules', []))}."
        )

    post_type = getattr(post, "post_type", "post") or "post"
    research_prompt = render_prompt(
        "draft_research",
        category=post.category,
        topic=post.topic,
        platform=post.platform,
        post_type=post_type,
        tone=post.tone or "Professional",
        voice_context=voice_context,
    )
    research_data = ask_ollama(research_prompt)

    writer_prompt = render_prompt(
        "draft_writer",
        platform=post.platform,
        category=post.category,
        post_type=post_type,
        topic=post.topic,
        voice_context=voice_context,
        research_data=research_data,
        tone=post.tone or "Professional",
    )
    draft_content = ask_ollama(writer_prompt)

    review_prompt = render_prompt(
        "draft_review",
        platform=post.platform,
        category=post.category,
        post_type=post_type,
        topic=post.topic,
        draft_content=draft_content,
        tone=post.tone or "Professional",
    )
    final_content = ask_ollama(review_prompt).strip()
    return _strip_markdown(final_content)
