# Project Structure

```text
Ai-event/
├── content_os/              # Django project configuration
│   ├── settings.py          # Environment-driven settings
│   ├── urls.py              # Project URL routing
│   ├── celery.py            # Celery app setup
│   ├── asgi.py
│   └── wsgi.py
├── core/                    # Main content automation app
│   ├── services/            # Business logic used by views and tasks
│   │   ├── ai_client.py
│   │   ├── content_generation.py
│   │   └── schedule_import.py
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tasks.py
│   ├── urls.py
│   └── views.py
├── templates/               # Shared and app templates
│   ├── base.html
│   └── core/
├── static/                  # Project static assets
├── media/                   # Uploaded/generated media in local development
├── manage.py
├── requirements.txt         # Python package dependencies
├── .env                     # Local runtime configuration
└── .env.example             # Safe template for environment variables
```

One-time patch scripts were removed from the root because their behavior now belongs in normal app files and services.


# AI Social Media Content Automation Platform

This project is an AI-powered social media assistant designed to simplify content planning and creation for businesses and creators. Users can upload a content calendar with topics and posting dates, and the system automatically generates social media posts, reel scripts, captions, hashtags, and image ideas based on their brand style. During onboarding, users define their brand voice, audience, and goals so all content remains consistent and personalized. Generated content is saved as drafts, allowing users to review, approve, or reject it before publishing. The platform can also suggest future content ideas, create demo content calendars, send review notifications via email, and help maintain a steady social media presence with minimal manual effort.