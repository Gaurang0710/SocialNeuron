from django.core.management.base import BaseCommand

from core.models import PromptTemplate
from core.services.prompt_templates import get_default_prompt_configs


class Command(BaseCommand):
    help = "Seed the recommended SocialNEURON AI prompts into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Overwrite existing prompt templates with the recommended defaults.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for prompt in get_default_prompt_configs():
            existing = PromptTemplate.objects.filter(key=prompt["key"]).first()
            if existing and not reset:
                skipped_count += 1
                continue

            _, created = PromptTemplate.objects.update_or_create(
                key=prompt["key"],
                defaults={
                    "name": prompt["name"],
                    "description": prompt["description"],
                    "template": prompt["template"],
                    "is_active": True,
                },
            )
            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Prompt seed complete. Created: {created_count}, updated: {updated_count}, skipped: {skipped_count}."
            )
        )
