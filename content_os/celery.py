import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'content_os.settings')

app = Celery('content_os')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
