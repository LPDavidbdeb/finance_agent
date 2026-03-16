import os
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Make sure to set this via environment variables in production
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database
# In production, we'll generally pull this from the environment as well
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Ensure STATIC_ROOT is set for proper static file gathering in prod
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
