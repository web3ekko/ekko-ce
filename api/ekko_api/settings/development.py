"""
Development settings for Ekko API
"""
from .base import *
import os
import dj_database_url

# Debug mode
DEBUG = True

# Security settings for development
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Database
DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://ekko:ekko123@postgres:5432/ekko_dev',
        conn_max_age=600
    )
}

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://:redis123@redis:6379/0')

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,  # Helpful for development
        }
    }
}

# Email backend configuration - supports multiple providers via environment variables
EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'console').lower()

if EMAIL_PROVIDER == 'resend':
    # Resend configuration
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    if RESEND_API_KEY:
        # Resend uses its own SDK, not Django email backend
        # We set a marker so authentication/utils.py knows to use Resend
        EMAIL_BACKEND = 'resend'  # Marker for custom handling
        DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')
        print(f"✅ Resend configured - From: {DEFAULT_FROM_EMAIL}")
    else:
        print("⚠️  RESEND_API_KEY not found. Falling back to console backend.")
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

elif EMAIL_PROVIDER == 'smtp':
    # Generic SMTP configuration (Gmail, etc.)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@ekko.dev')
    
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        print("⚠️  SMTP credentials not found. Using console email backend.")
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    else:
        print(f"✅ SMTP configured - Host: {EMAIL_HOST}, User: {EMAIL_HOST_USER}")

else:
    # Default to console backend for development
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@ekko.dev')
    print("📧 Using console email backend (emails will be printed to console)")

# WebAuthn settings for development
WEBAUTHN_RP_ID = 'localhost'
WEBAUTHN_RP_NAME = 'Ekko Development'
WEBAUTHN_ORIGIN = 'http://localhost:3000'
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'ekko': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Disable SSL redirect for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False

# Firebase settings (optional for development)
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'ekko-testing')
FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY', '')
FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN', 'ekko-testing.firebaseapp.com')

# Development-specific apps
if DEBUG:
    INSTALLED_APPS += [
        'django_extensions',
    ]

# Channel layers for WebSocket support
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(REDIS_URL.replace('redis://', '').split('@')[1].split(':')[0], 6379)],
        },
    },
}

print("Loading development settings...")
print(f"Database: {DATABASES['default']}")
print(f"Redis: {REDIS_URL}")
print(f"Debug: {DEBUG}")
print(f"Allowed Hosts: {ALLOWED_HOSTS}")