import random
import re

from .ai_client import ask_ollama


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
    prompt = (
        f"Provide {count} high-converting content topic ideas about: '{query}'. "
        f"Audience: {audience}. Tone: {tone}.{platform_context}{content_type_context}{niche_context}{goal_context}{voice_context} "
        "Make the ideas platform- and content-type-specific and avoid generic suggestions. "
        "Return only one topic per line as bullet points. Do not include an intro or explanation."
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

    research_prompt = (
        f"Act as a professional Trend Research Agent for {post.category}. "
        f"Topic: {post.topic}. List 3 current trending angles."
    )
    research_data = ask_ollama(research_prompt)

    writer_prompt = (
        f"Act as an expert Content Writer. Platform: {post.platform}. Category: {post.category}. "
        f"Topic: {post.topic}. {voice_context} Research context: {research_data}. "
        f"Tone: {post.tone or 'Professional'}. Write a highly engaging LinkedIn post. "
        "Include a strong hook, useful body, and short CTA. Keep it ready for review."
    )
    draft_content = ask_ollama(writer_prompt)

    review_prompt = (
        "Act as a Review & Optimization Agent. Fix grammar, improve readability, "
        f"optimize for {post.platform}."
        f"\n\nDraft:\n{draft_content}\n\n"
        "Return ONLY the optimized final post. Do not add markdown emphasis or divider lines."
    )
    final_content = ask_ollama(review_prompt).strip()
    return _strip_markdown(final_content)
