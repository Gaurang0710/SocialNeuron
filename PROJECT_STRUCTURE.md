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
