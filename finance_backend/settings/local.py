import os
from pathlib import Path
from dotenv import load_dotenv

# Load local environment variables before base.py reads them
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env.local', override=True)

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

X_FRAME_OPTIONS = 'ALLOWALL'

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
