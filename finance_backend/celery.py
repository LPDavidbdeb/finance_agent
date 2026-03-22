import os

from celery import Celery

# Default to local settings unless overridden in the environment.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finance_backend.settings.local")

app = Celery("finance_backend")

# Read Celery settings from Django settings using the CELERY_ namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py files from installed apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

