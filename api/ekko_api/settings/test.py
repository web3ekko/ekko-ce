"""
Django test settings for authentication app testing
Uses testcontainers for PostgreSQL, Redis, and NATS
"""

import os

from .base import *

# Test environment
DEBUG = True
TESTING = True

# Staticfiles: avoid manifest requirements in tests (admin pages render static assets).
STORAGES = {
    **STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
WHITENOISE_MANIFEST_STRICT = False

# Test database
#
# Default to SQLite so the test suite is runnable without external services.
# If you want to run tests against PostgreSQL (recommended for integration coverage),
# set DATABASE_URL to a Postgres DSN (e.g. from docker-compose).
import dj_database_url

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)}
    DATABASES["default"]["TEST"] = {"NAME": "test_ekko_api"}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Test Redis - use docker-compose Redis
#
# Default to LocMemCache so the unit test suite runs without external services.
# If you want Redis-backed tests (closer to production), set:
# - EKKO_TEST_USE_REDIS=1
# - REDIS_URL=redis://...
REDIS_URL = os.environ.get("REDIS_URL", "redis://:redis123@localhost:6379/1")
USE_REDIS = os.environ.get("EKKO_TEST_USE_REDIS", "").strip() == "1"

if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "test_ekko",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-ekko-locmem",
            "TIMEOUT": 300,
        }
    }

# Session configuration for testing
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Test email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Migrations are enabled by default for proper test database schema
# This ensures M2M tables and complex constraints are created correctly
# pytest-django handles migration execution automatically

# Test-specific authentication settings
AUTH_PASSKEY_ENABLED = True
AUTH_EMAIL_MAGIC_LINK_ENABLED = True
AUTH_2FA_REQUIRED = False
AUTH_CROSS_DEVICE_TIMEOUT = 300
AUTH_RECOVERY_CODE_COUNT = 10
AUTH_DEVICE_TRUST_DURATION = 90
AUTH_SESSION_TIMEOUT = 30
AUTH_RATE_LIMIT_ATTEMPTS = 5

# WebAuthn test configuration
WEBAUTHN_RP_ID = "localhost"
WEBAUTHN_RP_NAME = "Ekko Test API"
WEBAUTHN_ORIGIN = "http://localhost:3000"

# NATS test configuration - use environment variables if available (for Docker), fallback to localhost
NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
NATS_SUBJECT_PREFIX = "test_ekko"
NATS_ENABLED = os.environ.get("EKKO_TEST_USE_NATS", "").strip() == "1"

# wasmCloud runtime Redis projection is out-of-scope for unit tests; disable by default.
ALERT_RUNTIME_REDIS_SYNC_ENABLED = os.environ.get("EKKO_TEST_RUNTIME_REDIS_SYNC", "").strip() == "1"

# Security settings for testing
SECRET_KEY = "test-secret-key-for-testing-only-not-for-production"
ALLOWED_HOSTS = (
    os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if os.environ.get("ALLOWED_HOSTS") != "*"
    else ["*"]
)

# Authentication for API testing - include Knox
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
    "knox.auth.TokenAuthentication",
    "rest_framework.authentication.SessionAuthentication",
]

# Test logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "authentication": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "blockchain": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "organizations": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Celery test configuration
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Django Allauth test configuration
# Note: Using new settings format (deprecated settings removed for Django 6.0)
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'first_name*', 'last_name*']

# Test-specific middleware (remove some security middleware for testing)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Test file storage
# DEFAULT_FILE_STORAGE is removed in Django 6.0+, using STORAGES in base.py instead
# DEFAULT_FILE_STORAGE = 'django.core.files.storage.InMemoryStorage'

# Password hashing for tests
# Note: MD5PasswordHasher is removed in Django 6.0+
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# Test-specific CORS settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
