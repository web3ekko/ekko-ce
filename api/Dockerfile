# Django Ekko API Dockerfile
# Django 6.0 requires Python 3.12+
FROM python:3.12-slim

# Build arguments
ARG SECRET_KEY=django-insecure-build-key-only
ARG DJANGO_SETTINGS_MODULE=ekko_api.settings.production
ARG DEBUG=false
ARG NLP_ENABLED=true
ARG NLP_REQUIRE_DSPY=true
ARG NLP_FALLBACK_ON_DSPY_FAILURE=false
ARG NLP_TIMEOUT=30
ARG NLP_TEMPERATURE=0.1
ARG NLP_MAX_TOKENS=4096
ARG LLM_MAX_RETRIES=3
ARG NLP_SUPPORTED_NETWORKS=ETH:mainnet,AVAX:mainnet
ARG GEMINI_MODEL=gemini/gemini-3.0-flash

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SECRET_KEY=${SECRET_KEY} \
    DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} \
    DEBUG=${DEBUG} \
    # NLP/DSPy runtime settings (safe defaults; override at runtime via K8s/compose env)
    NLP_ENABLED=${NLP_ENABLED} \
    NLP_REQUIRE_DSPY=${NLP_REQUIRE_DSPY} \
    NLP_FALLBACK_ON_DSPY_FAILURE=${NLP_FALLBACK_ON_DSPY_FAILURE} \
    NLP_TIMEOUT=${NLP_TIMEOUT} \
    NLP_TEMPERATURE=${NLP_TEMPERATURE} \
    NLP_MAX_TOKENS=${NLP_MAX_TOKENS} \
    LLM_MAX_RETRIES=${LLM_MAX_RETRIES} \
    NLP_SUPPORTED_NETWORKS=${NLP_SUPPORTED_NETWORKS} \
    GEMINI_MODEL=${GEMINI_MODEL}

# Secrets MUST be provided at runtime (do not bake into image layers).
ENV GEMINI_API_KEY=""

# Set working directory
WORKDIR /app

# Install system dependencies (with date check workaround)
RUN apt-get -o Acquire::Check-Valid-Until=false update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (with SSL bypass and time fix for build)
ENV SOURCE_DATE_EPOCH=1695484800
RUN pip install --no-cache-dir --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    && pip install --no-cache-dir poetry-core --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    && pip install --no-cache-dir -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Create runtime directories (collectstatic + file logging)
RUN mkdir -p /app/staticfiles /app/logs \
    && chown -R app:app /app

# Switch to non-root user after setup
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Run the application
CMD ["gunicorn", "ekko_api.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
