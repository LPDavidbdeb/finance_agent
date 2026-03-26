import os
from pathlib import Path
from dotenv import load_dotenv

# Load remote environment variables before base.py reads them
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env.remote', override=True)

from .base import *

DEBUG = False

# Lock down to the server's actual hostname/IP — set SERVER_HOSTNAME in .env.remote
_hostname = os.environ.get('SERVER_HOSTNAME', '')
ALLOWED_HOSTS = ['localhost', '127.0.0.1'] + ([_hostname] if _hostname else [])

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', 'finance_agent'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# CORS: allow requests from the frontend running on the local network
_frontend_origin = os.environ.get('FRONTEND_ORIGIN', '')
if _frontend_origin:
    CORS_ALLOWED_ORIGINS = [_frontend_origin]
else:
    CORS_ALLOW_ALL_ORIGINS = True  # fallback until FRONTEND_ORIGIN is set

# No HTTPS on a home server — disable SSL-related redirects
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
