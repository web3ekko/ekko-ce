"""
Django settings for ekko_api project.

Passwordless Authentication System with Django Allauth
"""

import environ
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ''),
    DATABASE_URL=(str, ''),
    REDIS_URL=(str, 'redis://localhost:6379/0'),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    # NATS Configuration
    NATS_URL=(str, 'nats://localhost:4222'),
    NATS_USER=(str, ''),
    NATS_PASSWORD=(str, ''),
    NATS_TOKEN=(str, ''),
    NATS_MAX_RECONNECT_ATTEMPTS=(int, 10),
    NATS_RECONNECT_TIME_WAIT=(int, 2),
    # Firebase Configuration
    FIREBASE_PROJECT_ID=(str, ''),
    FIREBASE_CREDENTIALS_PATH=(str, ''),
    FIREBASE_SERVICE_ACCOUNT_KEY=(str, ''),
    FIREBASE_WEB_API_KEY=(str, ''),
    FIREBASE_AUTH_DOMAIN=(str, ''),
)

# Read .env file
environ.Env.read_env(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default="django-insecure-z6ef2111lz@5qdua=2hmb5sakdv3d%#u0ng_wdbxke1l*v!18_")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG', default=True)

ALLOWED_HOSTS = env('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '0.0.0.0'])


# Application definition

INSTALLED_APPS = [
    # Unfold admin theme - MUST be before django.contrib.admin
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',  # Required for WebAuthn templates
    'django.contrib.postgres',  # Required for GinIndex in Django 6.0+

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'knox',
    'corsheaders',

    # Allauth
    'allauth',
    'allauth.account',
    'allauth.mfa',
    # 'allauth.mfa.webauthn',  # Temporarily disabled while migrating to new passkeys app

    # 2FA
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',

    # Our apps
    'authentication',
    'blockchain',
    'organizations',
    'app',  # Main app with alerts and admin models
    'passkeys',  # New clean WebAuthn implementation
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add WhiteNoise after SecurityMiddleware
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Custom logging for all requests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'authentication': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

ROOT_URLCONF = "ekko_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ekko_api.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# Use SQLite for development if PostgreSQL is not available
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': env.db_url(
            'DATABASE_URL',
            default='postgresql://ekko:ekko@localhost:5432/ekko_api'
        )
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise configuration for serving static files
# STORAGES is required in Django 6.0+ (introduced in 4.2)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# WhiteNoise settings
WHITENOISE_AUTOREFRESH = True  # Auto refresh static files in development
WHITENOISE_USE_FINDERS = True  # Use Django's static file finders
WHITENOISE_COMPRESS_OFFLINE = True  # Compress static files during build

# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'authentication.backends.MultiAuthBackend',
]

# Django Allauth Configuration (Passwordless)
# Note: ACCOUNT_AUTHENTICATION_METHOD, ACCOUNT_EMAIL_REQUIRED, ACCOUNT_USERNAME_REQUIRED
# are deprecated in django-allauth 65.x - use ACCOUNT_LOGIN_METHODS and ACCOUNT_SIGNUP_FIELDS instead
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
ACCOUNT_LOGIN_METHODS = {'email'}  # New format: use set instead of list
ACCOUNT_SIGNUP_FIELDS = ['email*', 'first_name*', 'last_name*']  # No password fields for passwordless

# Compatibility for django-allauth versions that still enforce legacy settings in assertions.
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True  # Required for passkey signup
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 900  # 15 minutes
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGIN_REDIRECT_URL = '/'

# WebAuthn/Passkey settings (django-allauth)
MFA_SUPPORTED_TYPES = ['webauthn', 'totp', 'recovery_codes']
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_PASSKEY_SIGNUP_ENABLED = True
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = env('MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN', default=True)  # For development
MFA_WEBAUTHN_RP_ID = env('MFA_WEBAUTHN_RP_ID', default='localhost')
MFA_WEBAUTHN_RP_NAME = env('MFA_WEBAUTHN_RP_NAME', default='Ekko')
MFA_WEBAUTHN_ORIGIN = env('MFA_WEBAUTHN_ORIGIN', default='http://localhost:3000')

# New passkeys app settings (python-fido2)
WEBAUTHN_RP_ID = env('WEBAUTHN_RP_ID', default='localhost')
WEBAUTHN_RP_NAME = env('WEBAUTHN_RP_NAME', default='Ekko Cluster')
WEBAUTHN_ORIGIN = env('WEBAUTHN_ORIGIN', default='http://localhost:3000')
WEBAUTHN_ALLOWED_ORIGINS = env.list('WEBAUTHN_ALLOWED_ORIGINS', default=['http://localhost:3000', 'http://localhost:8000'])
WEBAUTHN_CHALLENGE_TIMEOUT = env.int('WEBAUTHN_CHALLENGE_TIMEOUT', default=300)  # 5 minutes

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'knox.auth.TokenAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # High defaults; tighten per-endpoint via custom throttles/scopes.
        'user': '10000/min',
        'anon': '1000/min',
    },
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:3000',
    'http://127.0.0.1:3000',
])
CORS_ALLOW_CREDENTIALS = True

# Redis Configuration
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            # Remove CLIENT_CLASS as it's not compatible with newer Redis cache backend
            # 'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# Django 6.0 Tasks Configuration (async background tasks)
# Phase 1: Async NLP parse pipeline
TASKS = {
    "default": {
        # Use ImmediateBackend for development (sync execution)
        # For production: use DatabaseBackend from django-tasks package
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
        # Queue names for task routing
        "QUEUES": ["default", "nlp"],
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60  # 30 days
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# CSRF Configuration
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Email Configuration - supports multiple providers
EMAIL_PROVIDER = env('EMAIL_PROVIDER', default='console')

# SendGrid configuration
if EMAIL_PROVIDER == 'sendgrid':
    SENDGRID_API_KEY = env('SENDGRID_API_KEY', default='')
    if SENDGRID_API_KEY:
        EMAIL_BACKEND = 'sgbackend.SendGridBackend'
        SENDGRID_SANDBOX_MODE_IN_DEBUG = env('SENDGRID_SANDBOX_MODE', default=False)
    else:
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
        
# SMTP configuration (Gmail, etc.)
elif EMAIL_PROVIDER == 'smtp':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', default='localhost')
    EMAIL_PORT = env('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
    
# Default console backend
else:
    EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')

# Common email settings
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@ekko.dev')

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
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
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'authentication': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Passwordless Authentication Settings
AUTH_PASSKEY_ENABLED = env('AUTH_PASSKEY_ENABLED', default=True)
AUTH_EMAIL_MAGIC_LINK_ENABLED = env('AUTH_EMAIL_MAGIC_LINK_ENABLED', default=True)
AUTH_2FA_REQUIRED = env('AUTH_2FA_REQUIRED', default=False)
AUTH_CROSS_DEVICE_TIMEOUT = env('AUTH_CROSS_DEVICE_TIMEOUT', default=300)  # 5 minutes
AUTH_RECOVERY_CODE_COUNT = env('AUTH_RECOVERY_CODE_COUNT', default=10)
AUTH_DEVICE_TRUST_DURATION = env('AUTH_DEVICE_TRUST_DURATION', default=90)  # 90 days
AUTH_SESSION_TIMEOUT = env('AUTH_SESSION_TIMEOUT', default=30)  # 30 days
AUTH_RATE_LIMIT_ATTEMPTS = env('AUTH_RATE_LIMIT_ATTEMPTS', default=5)

# NATS Configuration (for wasmCloud integration)
NATS_URL = env('NATS_URL', default='nats://localhost:4222')
NATS_USER = env('NATS_USER', default='')
NATS_PASSWORD = env('NATS_PASSWORD', default='')
NATS_TOKEN = env('NATS_TOKEN', default='')
NATS_MAX_RECONNECT_ATTEMPTS = env('NATS_MAX_RECONNECT_ATTEMPTS', default=10)
NATS_RECONNECT_TIME_WAIT = env('NATS_RECONNECT_TIME_WAIT', default=2)
NATS_SUBJECT_PREFIX = env('NATS_SUBJECT_PREFIX', default='ekko')

# NLP Service Configuration (Gemini API for natural language alert processing)
NLP_ENABLED = env.bool('NLP_ENABLED', default=True)
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GEMINI_MODEL = env('GEMINI_MODEL', default='gemini/gemini-1.5-flash')
GEMINI_TIMEOUT = env.int('GEMINI_TIMEOUT', default=30)
GEMINI_TEMPERATURE = env.float('GEMINI_TEMPERATURE', default=0.2)
# The compiler/runtime reads these settings (not GEMINI_* tuning fields).
NLP_TIMEOUT = env.int('NLP_TIMEOUT', default=GEMINI_TIMEOUT)
NLP_TEMPERATURE = env.float('NLP_TEMPERATURE', default=GEMINI_TEMPERATURE)
NLP_MAX_TOKENS = env.int('NLP_MAX_TOKENS', default=4096)
# Hard prod preference: use DSPy and do not silently fall back to a different inference path.
NLP_REQUIRE_DSPY = env.bool('NLP_REQUIRE_DSPY', default=True)
NLP_FALLBACK_ON_DSPY_FAILURE = env.bool('NLP_FALLBACK_ON_DSPY_FAILURE', default=DEBUG)
LLM_MAX_RETRIES = env.int('LLM_MAX_RETRIES', default=3)
# Canonical `{NETWORK}:{subnet}` keys the platform supports (hinted to NLP/compiler).
# Keep this list in config (env) so adding chains doesn't require code changes.
NLP_SUPPORTED_NETWORKS = env.list('NLP_SUPPORTED_NETWORKS', default=['ETH:mainnet', 'AVAX:mainnet'])

# DuckLake Schema Registry Configuration (NATS-based)
DUCKLAKE_SCHEMA_NATS_SUBJECT = env('DUCKLAKE_SCHEMA_NATS_SUBJECT', default='ducklake.schema.list')
DUCKLAKE_SCHEMA_NATS_TIMEOUT = env.int('DUCKLAKE_SCHEMA_NATS_TIMEOUT', default=5)
DUCKLAKE_SCHEMA_FALLBACK_ENABLED = env.bool('DUCKLAKE_SCHEMA_FALLBACK_ENABLED', default=True)

# DuckLake Direct Connection Configuration (requires DuckDB 1.3.0+)
# Catalog type: 'duckdb', 'postgresql', or 'sqlite'
DUCKLAKE_CATALOG_TYPE = env('DUCKLAKE_CATALOG_TYPE', default='duckdb')
# Path to metadata catalog file (for duckdb/sqlite)
DUCKLAKE_METADATA_PATH = env('DUCKLAKE_METADATA_PATH', default='metadata.ducklake')
# Path to Parquet data files (local path or S3 URL)
DUCKLAKE_DATA_PATH = env('DUCKLAKE_DATA_PATH', default='data/')
# PostgreSQL DSN (only needed if catalog_type is 'postgresql')
DUCKLAKE_POSTGRES_DSN = env('DUCKLAKE_POSTGRES_DSN', default=None)
# Catalog name when attached to DuckDB
DUCKLAKE_CATALOG_NAME = env('DUCKLAKE_CATALOG_NAME', default='ekko_lake')
# Performance settings
DUCKLAKE_THREADS = env.int('DUCKLAKE_THREADS', default=4)
DUCKLAKE_MEMORY_LIMIT = env('DUCKLAKE_MEMORY_LIMIT', default='2GB')

# Firebase Configuration (for email delivery and optional features)
FIREBASE_PROJECT_ID = env("FIREBASE_PROJECT_ID", default="")
FIREBASE_API_KEY = env("FIREBASE_API_KEY", default="")
FIREBASE_AUTH_DOMAIN = env("FIREBASE_AUTH_DOMAIN", default="")

FIREBASE_CONFIG = {
    'apiKey': FIREBASE_API_KEY,
    'authDomain': FIREBASE_AUTH_DOMAIN,
    'projectId': FIREBASE_PROJECT_ID,
}

# Firebase Admin SDK Configuration
FIREBASE_ADMIN_CONFIG = {
    'project_id': FIREBASE_PROJECT_ID,
    'credentials_path': env('FIREBASE_CREDENTIALS_PATH', default=''),
    'service_account_key': env('FIREBASE_SERVICE_ACCOUNT_KEY', default=''),
}

# Knox Configuration
from datetime import timedelta
import hashlib
from cryptography.hazmat.primitives import hashes
from rest_framework.settings import api_settings

# Knox Token Settings (48-hour expiry with auto-refresh)
class KnoxSHA512(hashes.HashAlgorithm):
    name = "sha512"
    digest_size = 64
    block_size = 128

    def __init__(self) -> None:
        self._hash = hashlib.sha512()

    def update(self, data: bytes) -> None:
        self._hash.update(data)

    def hexdigest(self) -> str:
        return self._hash.hexdigest()


REST_KNOX = {
    # Compatible with Knox implementations using hashlib-style or cryptography HashAlgorithm.
    'SECURE_HASH_ALGORITHM': KnoxSHA512,
    'AUTH_TOKEN_CHARACTER_LENGTH': 64,
    'TOKEN_TTL': timedelta(hours=48),  # 48-hour expiry as per spec
    'USER_SERIALIZER': 'authentication.serializers.UserSerializer',
    'TOKEN_LIMIT_PER_USER': None,  # Unlimited tokens per user (multi-device support)
    'AUTO_REFRESH': True,
    'EXPIRY_DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
}

# Email Verification Code Settings
VERIFICATION_CODE_TTL_MINUTES = int(env('VERIFICATION_CODE_TTL_MINUTES', default=30))

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': 'ekko-api',
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=15),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=30),
}

# Firebase Configuration
# Production-ready configuration that works with environment variables
FIREBASE_ADMIN_CONFIG = {}

# Firebase project ID (required)
if env('FIREBASE_PROJECT_ID'):
    FIREBASE_ADMIN_CONFIG['project_id'] = env('FIREBASE_PROJECT_ID')

# Firebase credentials - prioritize JSON string over file path for production
if env('FIREBASE_SERVICE_ACCOUNT_KEY'):
    # Production: Use JSON string from environment variable
    import json
    service_account_key = env('FIREBASE_SERVICE_ACCOUNT_KEY')

    # Check if it's already a dict (parsed by environ) or a string that needs parsing
    if isinstance(service_account_key, dict):
        FIREBASE_ADMIN_CONFIG['service_account_key'] = service_account_key
    else:
        try:
            FIREBASE_ADMIN_CONFIG['service_account_key'] = json.loads(service_account_key)
        except json.JSONDecodeError:
            # If it's not valid JSON, treat it as a string
            FIREBASE_ADMIN_CONFIG['service_account_key'] = service_account_key
elif env('FIREBASE_CREDENTIALS_PATH'):
    # Development: Use file path
    FIREBASE_ADMIN_CONFIG['credentials_path'] = env('FIREBASE_CREDENTIALS_PATH')

# Firebase Web Configuration (for frontend)
FIREBASE_WEB_CONFIG = {}
if env('FIREBASE_WEB_API_KEY'):
    FIREBASE_WEB_CONFIG.update({
        'apiKey': env('FIREBASE_WEB_API_KEY'),
        'authDomain': env('FIREBASE_AUTH_DOMAIN') or f"{env('FIREBASE_PROJECT_ID')}.firebaseapp.com",
        'projectId': env('FIREBASE_PROJECT_ID'),
    })

# Django Unfold Admin Theme Configuration
UNFOLD = {
    "SITE_TITLE": "Ekko Admin",
    "SITE_HEADER": "Ekko Blockchain Monitoring",
    "SITE_URL": "/",
    "SITE_ICON": None,  # Can add icon URL here
    "SITE_LOGO": None,  # Can add logo URL here
    "SITE_SYMBOL": "speed",  # Material icon name
    "SHOW_HISTORY": True,  # Show history button in change forms
    "SHOW_VIEW_ON_SITE": True,  # Show "View on site" link
    "ENVIRONMENT": env('ENVIRONMENT', default='development'),
    "DASHBOARD_CALLBACK": None,  # Custom dashboard callback
    "LOGIN": {
        "image": None,  # Background image for login page
        "redirect_after": None,  # Redirect after login
    },
    "STYLES": [
        # Custom CSS can be added here
    ],
    "SCRIPTS": [
        # Custom JavaScript can be added here
    ],
    "COLORS": {
        # Customize colors (optional)
        "primary": {
            "50": "239 246 255",
            "100": "219 234 254",
            "200": "191 219 254",
            "300": "147 197 253",
            "400": "96 165 250",
            "500": "59 130 246",
            "600": "37 99 235",
            "700": "29 78 216",
            "800": "30 64 175",
            "900": "30 58 138",
        },
    },
    "EXTENSIONS": {
        "modeltranslation": {
            "flags": {
                "en": "🇬🇧",
                "fr": "🇫🇷",
                "es": "🇪🇸",
            },
        },
    },
    "SIDEBAR": {
        "show_search": True,  # Show search bar in sidebar
        "show_all_applications": True,  # Show all apps
        "navigation": [
            {
                "title": "Alerts & Monitoring",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Alert Instances",
                        "icon": "notifications",
                        "link": "/admin/app/alertinstance/",
                    },
                    {
                        "title": "Alert Groups",
                        "icon": "folder",
                        "link": "/admin/app/alertgroup/",
                    },
                    {
                        "title": "Alert Templates",
                        "icon": "description",
                        "link": "/admin/app/alerttemplate/",
                    },
                    {
                        "title": "Alert Executions",
                        "icon": "play_arrow",
                        "link": "/admin/app/alertexecution/",
                    },
                ],
            },
            {
                "title": "Blockchain",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Blockchain Nodes",
                        "icon": "dns",
                        "link": "/admin/blockchain/blockchainnode/",
                    },
                ],
            },
            {
                "title": "Authentication",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "people",
                        "link": "/admin/authentication/user/",
                    },
                    {
                        "title": "User Groups",
                        "icon": "groups",
                        "link": "/admin/app/usergroup/",
                    },
                ],
            },
            {
                "title": "Infrastructure",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "NATS Streams",
                        "icon": "stream",
                        "link": "/admin/app/natsstream/",
                    },
                    {
                        "title": "Redis Metrics",
                        "icon": "memory",
                        "link": "/admin/app/redismetrics/",
                    },
                    {
                        "title": "WasmCloud Actors",
                        "icon": "cloud",
                        "link": "/admin/app/wasmcloudactor/",
                    },
                ],
            },
        ],
    },
    "TABS": [
        {
            "models": [
                "app.alertinstance",
                "app.alertgroup",
            ],
            "items": [
                {
                    "title": "Alert Instances",
                    "link": "/admin/app/alertinstance/",
                },
                {
                    "title": "Alert Groups",
                    "link": "/admin/app/alertgroup/",
                },
                {
                    "title": "Alert Templates",
                    "link": "/admin/app/alerttemplate/",
                },
            ],
        },
    ],
}
