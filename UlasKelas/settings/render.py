from .base import *  # noqa: F403


ALLOWED_HOSTS.append(".onrender.com")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Simplified static file serving.
# https://warehouse.python.org/project/whitenoise/

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
MIDDLEWARE.insert(0, "whitenoise.middleware.WhiteNoiseMiddleware")

SILENCED_SYSTEM_CHECKS = [
    "security.W004",  # SECURE_HSTS_SECONDS
    "security.W008",  # SECURE_SSL_REDIRECT
]
