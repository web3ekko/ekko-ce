# Development Setup and Deployment Guide

This guide covers setting up the Ekko API for local development and deploying to production environments.

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Local Development Workflow](#local-development-workflow)
3. [Docker Development](#docker-development)
4. [Testing Strategy](#testing-strategy)
5. [Production Deployment](#production-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Troubleshooting](#troubleshooting)

## Development Environment Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 14+
- Redis 6+
- NATS Server 2.10+
- Node.js 18+ (for frontend development)
- Docker & Docker Compose (optional but recommended)
- Firebase project with Admin SDK

### Initial Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/your-org/ekko-cluster.git
cd ekko-cluster/apps/api
```

#### 2. Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt  # For testing
```

#### 3. Database Setup

```bash
# Using Docker
docker run -d \
  --name ekko-postgres \
  -e POSTGRES_USER=ekko \
  -e POSTGRES_PASSWORD=ekko_dev \
  -e POSTGRES_DB=ekko_api \
  -p 5432:5432 \
  postgres:14-alpine

# Or install PostgreSQL locally
brew install postgresql@14  # macOS
sudo apt-get install postgresql-14  # Ubuntu

# Create database
createdb ekko_api
```

#### 4. Redis Setup

```bash
# Using Docker
docker run -d \
  --name ekko-redis \
  -p 6379:6379 \
  redis:6-alpine

# Or install Redis locally
brew install redis  # macOS
sudo apt-get install redis-server  # Ubuntu
```

#### 5. NATS Setup

```bash
# Using Docker with JetStream
docker run -d \
  --name ekko-nats \
  -p 4222:4222 \
  -p 8222:8222 \
  nats:latest -js

# Or install NATS locally
brew install nats-server  # macOS
# Download from https://github.com/nats-io/nats-server/releases

# Run with JetStream enabled
nats-server -js
```

#### 6. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your settings
vim .env
```

Required environment variables:

```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://ekko:ekko_dev@localhost:5432/ekko_api

# Redis
REDIS_URL=redis://localhost:6379/0

# NATS
NATS_URL=nats://localhost:4222

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=path/to/service-account-key.json
FIREBASE_WEB_API_KEY=your-web-api-key

# CORS (for frontend development)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

#### 7. Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new project or select existing
3. Enable Authentication with Email provider
4. Generate service account key:
   - Project Settings → Service Accounts → Generate New Private Key
   - Save as `firebase-service-account.json`
   - Update `FIREBASE_CREDENTIALS_PATH` in `.env`

#### 8. Database Migrations

```bash
# Create migrations for any model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
```

#### 9. Static Files

```bash
# Collect static files
python manage.py collectstatic --noinput

# Verify static files
python manage.py check_static
```

## Local Development Workflow

### Running the Development Server

```bash
# Standard Django development server
python manage.py runserver

# With custom port
python manage.py runserver 0.0.0.0:8080

# With Gunicorn (production-like)
gunicorn ekko_api.wsgi:application --bind 0.0.0.0:8000 --reload
```

### Running Background Services

```bash
# NATS subscriber (in separate terminal)
python manage.py nats_subscriber

# Celery worker (if using Celery)
celery -A ekko_api worker -l info

# Celery beat (for scheduled tasks)
celery -A ekko_api beat -l info
```

### Development Tools

#### Django Shell

```bash
# Interactive Python shell with Django context
python manage.py shell

# With IPython (if installed)
python manage.py shell_plus
```

#### Database Access

```bash
# PostgreSQL shell
python manage.py dbshell

# SQL migrations
python manage.py sqlmigrate app 0001
```

#### Django Extensions

```bash
# Install django-extensions
pip install django-extensions

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ...
    'django_extensions',
]

# Useful commands
python manage.py show_urls  # List all URLs
python manage.py graph_models -a -o models.png  # Generate model diagram
python manage.py validate_templates  # Check templates
```

### Code Quality Tools

#### Formatting

```bash
# Black for code formatting
black .

# isort for import sorting
isort .

# Combined
black . && isort .
```

#### Linting

```bash
# Flake8
flake8 .

# Pylint
pylint app authentication

# mypy for type checking
mypy .
```

#### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

Install pre-commit:

```bash
pip install pre-commit
pre-commit install
```

## Docker Development

### Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: ekko
      POSTGRES_PASSWORD: ekko_dev
      POSTGRES_DB: ekko_api
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  nats:
    image: nats:latest
    command: -js
    ports:
      - "4222:4222"
      - "8222:8222"

  api:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
      - nats
    environment:
      - DATABASE_URL=postgres://ekko:ekko_dev@db:5432/ekko_api
      - REDIS_URL=redis://redis:6379/0
      - NATS_URL=nats://nats:4222
      - DEBUG=True
    env_file:
      - .env

  nats-subscriber:
    build: .
    command: python manage.py nats_subscriber
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
      - nats
      - api
    environment:
      - DATABASE_URL=postgres://ekko:ekko_dev@db:5432/ekko_api
      - REDIS_URL=redis://redis:6379/0
      - NATS_URL=nats://nats:4222
    env_file:
      - .env

volumes:
  postgres_data:
```

### Docker Commands

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f api

# Run migrations
docker-compose exec api python manage.py migrate

# Create superuser
docker-compose exec api python manage.py createsuperuser

# Run tests
docker-compose exec api python manage.py test

# Shell access
docker-compose exec api bash

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Testing Strategy

### Test Structure

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_serializers.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/
│   ├── test_auth_flow.py
│   ├── test_alert_creation.py
│   └── test_nats_integration.py
├── e2e/
│   └── test_user_journeys.py
├── fixtures/
│   ├── users.json
│   └── alerts.json
└── conftest.py
```

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test authentication
python manage.py test app

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report

# Run with pytest
pytest

# Run specific test file
pytest tests/unit/test_models.py

# Run with markers
pytest -m "not slow"

# Parallel testing
pytest -n auto
```

### Test Configuration

Create `pytest.ini`:

```ini
[tool:pytest]
DJANGO_SETTINGS_MODULE = ekko_api.settings.test
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --tb=short
    --reuse-db
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

### Test Database

```python
# settings/test.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ekko_api_test',
        'USER': 'ekko',
        'PASSWORD': 'ekko_dev',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'NAME': 'ekko_api_test',
        }
    }
}

# Faster password hasher for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
```

## Production Deployment

### Production Checklist

1. **Security**
   - [ ] Set `DEBUG = False`
   - [ ] Generate new `SECRET_KEY`
   - [ ] Configure `ALLOWED_HOSTS`
   - [ ] Enable HTTPS only
   - [ ] Set secure cookie settings
   - [ ] Configure CORS properly

2. **Database**
   - [ ] Use connection pooling
   - [ ] Set up regular backups
   - [ ] Configure read replicas
   - [ ] Optimize indexes

3. **Static Files**
   - [ ] Use CDN for static files
   - [ ] Enable compression
   - [ ] Set cache headers

4. **Monitoring**
   - [ ] Set up error tracking (Sentry)
   - [ ] Configure application monitoring
   - [ ] Set up log aggregation
   - [ ] Configure alerts

### Dockerfile

```dockerfile
# Multi-stage build
FROM python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Runtime stage
FROM python:3.9-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN useradd -m -u 1000 ekko

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=ekko:ekko . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Switch to app user
USER ekko

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health/')"

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--worker-class", "gthread", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "ekko_api.wsgi:application"]
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ekko-api
  labels:
    app: ekko-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ekko-api
  template:
    metadata:
      labels:
        app: ekko-api
    spec:
      containers:
      - name: api
        image: ekko/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DJANGO_SETTINGS_MODULE
          value: ekko_api.settings.production
        envFrom:
        - secretRef:
            name: ekko-api-secrets
        - configMapRef:
            name: ekko-api-config
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: ekko-api
spec:
  selector:
    app: ekko-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### CI/CD Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: ""

test:
  stage: test
  image: python:3.9
  services:
    - postgres:14
    - redis:6
  variables:
    POSTGRES_DB: ekko_test
    POSTGRES_USER: ekko
    POSTGRES_PASSWORD: ekko_test
    DATABASE_URL: postgres://ekko:ekko_test@postgres:5432/ekko_test
    REDIS_URL: redis://redis:6379/0
  before_script:
    - pip install -r requirements.txt
    - pip install -r requirements-test.txt
  script:
    - python manage.py migrate
    - pytest --cov=. --cov-report=xml
    - black --check .
    - isort --check .
    - flake8 .
  coverage: '/TOTAL.+?(\d+\%)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA $CI_REGISTRY_IMAGE:latest
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE:latest
  only:
    - main

deploy:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl set image deployment/ekko-api api=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - kubectl rollout status deployment/ekko-api
  environment:
    name: production
    url: https://api.ekko.com
  only:
    - main
```

## Environment Configuration

### Settings Structure

```
ekko_api/settings/
├── __init__.py
├── base.py       # Common settings
├── development.py # Local development
├── test.py       # Test settings
└── production.py # Production settings
```

### Production Settings

```python
# settings/production.py
from .base import *

DEBUG = False

# Security
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Database connection pooling
DATABASES['default']['CONN_MAX_AGE'] = 60

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        }
    }
}

# Static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
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
        'app': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT', default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')

# Sentry
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=env('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
    environment='production',
)
```

### Environment Variables

Create `.env.production`:

```bash
# Django
SECRET_KEY=your-production-secret-key
DJANGO_SETTINGS_MODULE=ekko_api.settings.production
ALLOWED_HOSTS=api.ekko.com,*.ekko.com

# Database
DATABASE_URL=postgres://user:pass@db-host:5432/ekko_prod

# Redis
REDIS_URL=redis://:password@redis-host:6379/0

# NATS
NATS_URL=nats://nats-cluster:4222
NATS_USER=ekko_api
NATS_PASSWORD=secure-password

# Firebase
FIREBASE_PROJECT_ID=ekko-production
FIREBASE_CREDENTIALS_PATH=/secrets/firebase-service-account.json

# CORS
CORS_ALLOWED_ORIGINS=https://app.ekko.com,https://www.ekko.com

# Sentry
SENTRY_DSN=https://xxx@sentry.io/yyy

# Email
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@ekko.com
```

## Monitoring and Logging

### Application Monitoring

#### Prometheus Metrics

```python
# monitoring.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
request_count = Counter(
    'ekko_api_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'ekko_api_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

active_users = Gauge(
    'ekko_api_active_users',
    'Number of active users'
)

# Middleware
class PrometheusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        
        request_count.labels(
            method=request.method,
            endpoint=request.path,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=request.path
        ).observe(duration)
        
        return response
```

#### Health Checks

```python
# health.py
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis
import time

def health_check(request):
    """Basic health check"""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': time.time()
    })

def detailed_health_check(request):
    """Detailed health check with dependencies"""
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'dependencies': {}
    }
    
    # Check database
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['dependencies']['database'] = {
            'status': 'healthy',
            'response_time_ms': (time.time() - start) * 1000
        }
    except Exception as e:
        health_status['dependencies']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    # Check Redis
    try:
        start = time.time()
        cache.set('health_check', 'ok', 1)
        health_status['dependencies']['redis'] = {
            'status': 'healthy',
            'response_time_ms': (time.time() - start) * 1000
        }
    except Exception as e:
        health_status['dependencies']['redis'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    # Check NATS
    # Add NATS health check here
    
    return JsonResponse(health_status)
```

### Logging Configuration

```python
# Custom logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Usage
logger = structlog.get_logger()
logger.info("user_logged_in", user_id=user.id, ip=request.META.get('REMOTE_ADDR'))
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Problem**: Can't connect to PostgreSQL

**Solutions**:
```bash
# Check if PostgreSQL is running
ps aux | grep postgres

# Check connection
psql -U ekko -d ekko_api -h localhost

# Check pg_hba.conf for authentication
# Add: host all all 127.0.0.1/32 md5
```

#### 2. Static Files Not Loading

**Problem**: 404 errors for static files

**Solutions**:
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check STATIC_ROOT setting
python manage.py shell
>>> from django.conf import settings
>>> print(settings.STATIC_ROOT)

# Verify WhiteNoise middleware is installed
# In settings.py MIDDLEWARE list
```

#### 3. NATS Connection Issues

**Problem**: Can't connect to NATS

**Solutions**:
```bash
# Check if NATS is running
telnet localhost 4222

# Test with nats-cli
nats-cli server info

# Check JetStream is enabled
nats-cli stream list
```

#### 4. Firebase Authentication Errors

**Problem**: Firebase credentials not working

**Solutions**:
```python
# Verify credentials file exists
import os
print(os.path.exists(settings.FIREBASE_CREDENTIALS_PATH))

# Test Firebase connection
from authentication.firebase_utils import firebase_auth_manager
firebase_auth_manager.verify_connection()
```

### Debug Commands

```bash
# Django debug toolbar (development only)
pip install django-debug-toolbar

# Shell debugging
python manage.py shell_plus --print-sql

# Database queries
from django.db import connection
print(connection.queries)

# Check migrations
python manage.py showmigrations

# Validate project
python manage.py check --deploy

# Find issues
python manage.py diffsettings
```

### Performance Debugging

```python
# Profile view performance
from django.test.utils import override_settings
from django.test import Client
import cProfile

profiler = cProfile.Profile()
profiler.enable()

client = Client()
response = client.get('/api/alerts/')

profiler.disable()
profiler.print_stats(sort='cumulative')

# SQL query analysis
from django.db import connection
from django.test.utils import override_settings

with override_settings(DEBUG=True):
    # Your code here
    print(len(connection.queries))
    for query in connection.queries:
        print(f"{query['time']}s - {query['sql'][:50]}...")
```

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [NATS Documentation](https://docs.nats.io/)
- [PostgreSQL Optimization](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes Django Guide](https://kubernetes.io/docs/tutorials/)