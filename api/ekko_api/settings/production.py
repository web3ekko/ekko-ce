"""
Django production settings for Ekko API
Optimized for containerized deployment with security best practices
"""

import os
from .base import *

# Production environment
DEBUG = False
TESTING = False

# Security settings
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required in production")

# Allowed hosts
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
    raise ValueError("ALLOWED_HOSTS environment variable is required in production")

# Database configuration
DATABASES = {
    'default': env.db_url(
        'DATABASE_URL',
        default='postgresql://ekko:ekko@postgres:5432/ekko_api'
    )
}

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            # Remove CLIENT_CLASS as it's not compatible with newer Redis cache backend
            # 'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'ekko_api',
        'TIMEOUT': 300,
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400  # 24 hours

# CSRF protection
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True').lower() == 'true'
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host and not host.startswith('localhost')
]

# Security middleware
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Handle proxy headers for HTTPS behind load balancer/ingress
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = os.environ.get('USE_X_FORWARDED_HOST', 'True').lower() == 'true'
USE_X_FORWARDED_PORT = os.environ.get('USE_X_FORWARDED_PORT', 'True').lower() == 'true'

# Email configuration (Resend only)
EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'resend').lower()
if EMAIL_PROVIDER != 'resend':
    raise ValueError("Production email must use Resend (EMAIL_PROVIDER=resend)")

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY is required in production")

# Resend uses its own SDK; authentication/utils.py checks for EMAIL_BACKEND == 'resend'
EMAIL_BACKEND = 'resend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')

# Authentication settings
AUTH_PASSKEY_ENABLED = os.environ.get('AUTH_PASSKEY_ENABLED', 'True').lower() == 'true'
AUTH_EMAIL_MAGIC_LINK_ENABLED = os.environ.get('AUTH_EMAIL_MAGIC_LINK_ENABLED', 'True').lower() == 'true'
AUTH_2FA_REQUIRED = os.environ.get('AUTH_2FA_REQUIRED', 'False').lower() == 'true'
AUTH_CROSS_DEVICE_TIMEOUT = int(os.environ.get('AUTH_CROSS_DEVICE_TIMEOUT', '300'))
AUTH_RECOVERY_CODE_COUNT = int(os.environ.get('AUTH_RECOVERY_CODE_COUNT', '10'))
AUTH_DEVICE_TRUST_DURATION = int(os.environ.get('AUTH_DEVICE_TRUST_DURATION', '90'))
AUTH_SESSION_TIMEOUT = int(os.environ.get('AUTH_SESSION_TIMEOUT', '30'))
AUTH_RATE_LIMIT_ATTEMPTS = int(os.environ.get('AUTH_RATE_LIMIT_ATTEMPTS', '5'))

# WebAuthn configuration
WEBAUTHN_RP_ID = os.environ.get('WEBAUTHN_RP_ID')
WEBAUTHN_RP_NAME = os.environ.get('WEBAUTHN_RP_NAME', 'Ekko API')
WEBAUTHN_ORIGIN = os.environ.get('WEBAUTHN_ORIGIN')

if not WEBAUTHN_RP_ID or not WEBAUTHN_ORIGIN:
    raise ValueError("WEBAUTHN_RP_ID and WEBAUTHN_ORIGIN are required in production")

# NATS configuration
NATS_URL = os.environ.get('NATS_URL', 'nats://nats:4222')
NATS_SUBJECT_PREFIX = os.environ.get('NATS_SUBJECT_PREFIX', 'ekko')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/ekko_api.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'authentication': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'blockchain': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'organizations': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'

# WhiteNoise production settings
WHITENOISE_AUTOREFRESH = False  # Don't auto refresh in production
WHITENOISE_USE_FINDERS = False  # Don't use finders in production
WHITENOISE_COMPRESS_OFFLINE = True  # Compress during build

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/mediafiles'

# Celery configuration (if using background tasks)
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Django Allauth production configuration
# Note: Using new settings format (deprecated settings removed for Django 6.0)
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'first_name*', 'last_name*']

# CORS configuration for production
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # Never allow all origins in production

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# Performance optimizations
CONN_MAX_AGE = 60  # Database connection pooling

# Health check endpoint
HEALTH_CHECK_URL = '/health/'

# Monitoring and metrics
ENABLE_METRICS = os.environ.get('ENABLE_METRICS', 'True').lower() == 'true'
METRICS_ENDPOINT = '/metrics/'
