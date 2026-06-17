from django.db import migrations, models


DEFAULT_PROMPTS = [
    {
        "key": "topic_ideas",
        "name": "Topic Ideas",
        "description": "Generates platform-specific and content-type-specific topic ideas.",
        "template": (
            "Provide {count} high-converting content topic ideas about: '{query}'. "
            "Audience: {audience}. Tone: {tone}.{platform_context}{content_type_context}"
            "{niche_context}{goal_context}{voice_context} "
            "Make the ideas platform- and content-type-specific and avoid generic suggestions. "
            "Return only one topic per line as bullet points. Do not include an intro or explanation."
        ),
    },
    {
        "key": "draft_research",
        "name": "Draft Research Agent",
        "description": "Finds short trend angles before draft writing.",
        "template": (
            "Act as a professional Trend Research Agent for {category}. "
            "Topic: {topic}. List 3 current trending angles."
        ),
    },
    {
        "key": "draft_writer",
        "name": "Draft Writer Agent",
        "description": "Writes the first content draft using brand voice and research context.",
        "template": (
            "Act as an expert Content Writer. Platform: {platform}. Category: {category}. "
            "Content type: {post_type}. Topic: {topic}. {voice_context} "
            "Research context: {research_data}. Tone: {tone}. "
            "Write a highly engaging {platform} {post_type}. Include a strong hook, useful body, "
            "and short CTA. Keep it ready for review."
        ),
    },
    {
        "key": "draft_review",
        "name": "Draft Review Agent",
        "description": "Optimizes the draft and removes unwanted markdown artifacts.",
        "template": (
            "Act as a Review & Optimization Agent. Fix grammar, improve readability, "
            "optimize for {platform} {post_type}.\n\n"
            "Draft:\n{draft_content}\n\n"
            "Return ONLY the optimized final post. Do not add markdown emphasis or divider lines."
        ),
    },
    {
        "key": "advanced_hashtag",
        "name": "Advanced Hashtag Tool",
        "description": "Suggests hashtags from the post detail quick action.",
        "template": "Suggest 8 {platform} hashtags for this topic: {topic}",
    },
    {
        "key": "advanced_hook",
        "name": "Advanced Hook Tool",
        "description": "Suggests stronger hooks from the post detail quick action.",
        "template": "Write 5 stronger {platform} hooks for this post topic: {topic}",
    },
    {
        "key": "advanced_rewrite",
        "name": "Advanced Rewrite Tool",
        "description": "Rewrites generated content from the post detail quick action.",
        "template": (
            "Rewrite this {platform} {post_type} in a sharper professional tone:\n\n"
            "{generated_content}"
        ),
    },
]


def seed_default_prompts(apps, schema_editor):
    PromptTemplate = apps.get_model("core", "PromptTemplate")
    for prompt in DEFAULT_PROMPTS:
        PromptTemplate.objects.update_or_create(
            key=prompt["key"],
            defaults={
                "name": prompt["name"],
                "description": prompt["description"],
                "template": prompt["template"],
                "is_active": True,
            },
        )


def remove_default_prompts(apps, schema_editor):
    PromptTemplate = apps.get_model("core", "PromptTemplate")
    PromptTemplate.objects.filter(key__in=[prompt["key"] for prompt in DEFAULT_PROMPTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_contactinquiry"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromptTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "key",
                    models.CharField(
                        choices=[
                            ("topic_ideas", "Topic Ideas"),
                            ("draft_research", "Draft Research Agent"),
                            ("draft_writer", "Draft Writer Agent"),
                            ("draft_review", "Draft Review Agent"),
                            ("advanced_hashtag", "Advanced Hashtag Tool"),
                            ("advanced_hook", "Advanced Hook Tool"),
                            ("advanced_rewrite", "Advanced Rewrite Tool"),
                        ],
                        help_text="Stable key used by the application. Keep one active template per key.",
                        max_length=80,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "template",
                    models.TextField(
                        help_text=(
                            "Use Python format placeholders such as {topic}, {platform}, {tone}, "
                            "{audience}, {count}, {brand_voice}, {research_data}, and {draft_content}."
                        )
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["key"],
            },
        ),
        migrations.RunPython(seed_default_prompts, remove_default_prompts),
    ]
