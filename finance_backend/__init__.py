"""Finance backend package init.

Import the Celery app if available. We import lazily/guarded so that
management commands and test runs don't fail when Celery isn't present in
the active interpreter (common when multiple virtualenvs are used).
"""

# Try to import the project Celery application. If Celery or its
# dependencies are not installed in the currently active Python
# environment, avoid raising an ImportError — callers can handle
# celery_app being None.
try:
	from .celery import app as celery_app  # type: ignore
except Exception:
	# Keep a stable name available for imports elsewhere. Code that
	# requires Celery should check for None and surface a clear error
	# if necessary.
	celery_app = None

__all__ = ("celery_app",)

