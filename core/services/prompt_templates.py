from __future__ import annotations

from string import Formatter
from typing import Any


DEFAULT_PROMPT_CONFIGS = [
    {
        "key": "topic_ideas",
        "name": "Topic Ideas",
        "description": "Generates platform-specific and content-type-specific topic ideas.",
        "template": (
            "You are a senior social media strategist for a SaaS-style content workflow.\n\n"
            "Create exactly {count} high-quality content topic ideas for this request:\n"
            "- Core subject: {query}\n"
            "- Target audience: {audience}\n"
            "- Preferred tone: {tone}\n"
            "- Platform: {platform}\n"
            "- Content type: {post_type}\n"
            "{niche_context}{goal_context}{voice_context}\n\n"
            "Rules:\n"
            "1. Make every idea specific to the selected platform and content type.\n"
            "2. Avoid generic ideas, duplicate angles, and vague titles.\n"
            "3. Each idea should be practical enough to become a post immediately.\n"
            "4. Return only one topic per line as bullet points.\n"
            "5. Do not include intro text, numbering explanations, or markdown dividers."
        ),
    },
    {
        "key": "draft_research",
        "name": "Draft Research Agent",
        "description": "Finds useful angles before draft writing.",
        "template": (
            "Act as a practical Trend Research Agent.\n\n"
            "Research context:\n"
            "- Category/audience: {category}\n"
            "- Topic: {topic}\n"
            "- Platform: {platform}\n"
            "- Content type: {post_type}\n"
            "- Tone: {tone}\n"
            "{voice_context}\n\n"
            "Return 3 concise angles the writer can use. Include:\n"
            "- A current or timely angle\n"
            "- A pain point or audience insight\n"
            "- A useful takeaway or proof angle\n\n"
            "Keep it brief and do not write the final post."
        ),
    },
    {
        "key": "draft_writer",
        "name": "Draft Writer Agent",
        "description": "Writes the first content draft using brand voice and research context.",
        "template": (
            "Act as an expert social media content writer.\n\n"
            "Write a ready-to-review draft using this brief:\n"
            "- Platform: {platform}\n"
            "- Content type: {post_type}\n"
            "- Topic: {topic}\n"
            "- Category/audience: {category}\n"
            "- Tone: {tone}\n"
            "{voice_context}\n\n"
            "Research context:\n"
            "{research_data}\n\n"
            "Writing rules:\n"
            "1. Start with a strong hook.\n"
            "2. Keep the body useful, clear, and skimmable.\n"
            "3. Match the platform and content type format.\n"
            "4. Add a short CTA at the end.\n"
            "5. Do not use markdown dividers like ***.\n"
            "6. Do not wrap sentences in markdown bold unless the platform naturally needs it."
        ),
    },
    {
        "key": "draft_review",
        "name": "Draft Review Agent",
        "description": "Optimizes the draft and removes unwanted markdown artifacts.",
        "template": (
            "Act as a Review and Optimization Agent for {platform} {post_type} content.\n\n"
            "Improve this draft for clarity, readability, brand fit, and engagement:\n"
            "{draft_content}\n\n"
            "Rules:\n"
            "1. Return only the optimized final post.\n"
            "2. Remove markdown dividers, unnecessary bold markers, and filler text.\n"
            "3. Keep the meaning intact but make the writing sharper.\n"
            "4. Keep the tone {tone}."
        ),
    },
    {
        "key": "advanced_hashtag",
        "name": "Advanced Hashtag Tool",
        "description": "Suggests hashtags from the post detail quick action.",
        "template": (
            "Suggest 8 relevant hashtags for a {platform} {post_type} about this topic: {topic}.\n"
            "Mix broad, niche, and intent-based hashtags. Return only the hashtags."
        ),
    },
    {
        "key": "advanced_hook",
        "name": "Advanced Hook Tool",
        "description": "Suggests stronger hooks from the post detail quick action.",
        "template": (
            "Write 5 stronger opening hooks for a {platform} {post_type} about: {topic}.\n"
            "Make them punchy, clear, and suitable for a {tone} tone. Return only the hooks."
        ),
    },
    {
        "key": "advanced_rewrite",
        "name": "Advanced Rewrite Tool",
        "description": "Rewrites generated content from the post detail quick action.",
        "template": (
            "Rewrite this {platform} {post_type} in a sharper {tone} tone.\n\n"
            "Keep the original meaning, remove unnecessary markdown, improve clarity, and return only the rewritten content.\n\n"
            "{generated_content}"
        ),
    },
]

DEFAULT_PROMPTS = {
    prompt["key"]: prompt["template"]
    for prompt in DEFAULT_PROMPT_CONFIGS
}


class _SafeContext(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _format_prompt(template: str, context: dict[str, Any]) -> str:
    normalized_context = {
        key: "" if value is None else value
        for key, value in context.items()
    }
    return template.format_map(_SafeContext(normalized_context))


def validate_template_syntax(template: str) -> None:
    """Raise ValueError for malformed Python format templates."""

    # Parsing catches unbalanced braces while still allowing unknown placeholders.
    list(Formatter().parse(template))


def get_default_prompt_configs() -> list[dict[str, str]]:
    """Return copyable recommended prompt definitions for seeding and UI display."""

    return [prompt.copy() for prompt in DEFAULT_PROMPT_CONFIGS]


def render_prompt(key: str, **context: Any) -> str:
    """Render an active admin prompt, falling back safely to the built-in prompt."""

    fallback = DEFAULT_PROMPTS.get(key, "")
    try:
        from core.models import PromptTemplate

        prompt_template = PromptTemplate.objects.filter(key=key, is_active=True).first()
        template = prompt_template.template if prompt_template else fallback
        return _format_prompt(template, context)
    except Exception:
        return _format_prompt(fallback, context)
