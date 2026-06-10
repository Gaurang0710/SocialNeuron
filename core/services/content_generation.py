import random
import re

from .ai_client import ask_ollama


def generate_topic_ideas(query, tone, audience):
    prompt = (
        f"Provide 4 high-converting LinkedIn topic ideas about: '{query}'. "
        f"Audience: {audience}. Tone: {tone}. "
        "Return only one topic per line as bullet points. Do not include an intro or explanation."
    )
    topics_text = ask_ollama(prompt)

    if topics_text.startswith("Error:"):
        return [], topics_text

    generated = []
    for text in topics_text.split("\n"):
        if len(generated) >= 4:
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

    return [
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
    ], None


def create_post_content(post, brand_voices):
    voice_context = "Use standard professional tone."
    if brand_voices.exists():
        combined_voice = " ".join([voice.document_content for voice in brand_voices])
        voice_context = f"Learn from this brand voice context: {combined_voice[:2000]}..."

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
        "Return ONLY the optimized final post."
    )
    return ask_ollama(review_prompt).strip()
