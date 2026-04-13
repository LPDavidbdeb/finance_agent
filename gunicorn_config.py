import multiprocessing
import os

# Gunicorn configuration for iMac production
bind = "0.0.0.0:8001"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 120
keepalive = 5

# Logging
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)
