# Ekko API

Django REST Framework API for the Ekko blockchain monitoring platform with alert management, WebAuthn/passkey authentication, and NATS-based event processing.

## 🚀 Features

- **🎯 Natural Language Alerts**: Create blockchain monitoring alerts using plain English
- **📋 Alert Templates**: Reusable alert patterns with versioning and sharing
- **🔐 WebAuthn/Passkey Authentication**: Passwordless authentication with email fallback
- **👥 Organization Management**: Multi-tenant support with teams and role-based access
- **⚡ Real-Time Processing**: NATS-based event processing with integrated NLP pipeline
- **🔗 Multi-Chain Support**: Monitor wallets across Ethereum, Bitcoin, Solana, and more
- **📊 Admin Dashboard**: Django admin interface for system management
- **🐳 Docker Ready**: Containerized deployment with PostgreSQL, Redis, and NATS

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React         │    │    Mobile       │    │  wasmCloud      │
│   Dashboard     │    │    Apps         │    │  Actors         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Django REST    │
                    │   Framework     │
                    └─────────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
        ┌───────────┐  ┌──────────┐  ┌──────────┐
        │PostgreSQL │  │  Redis   │  │   NATS   │
        │ Database  │  │  Cache   │  │ Message  │
        └───────────┘  └──────────┘  │  Broker  │
                                      └──────────┘
```

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 14+
- Redis 6+
- NATS Server 2.10+
- Docker & Docker Compose (optional)
- Firebase project (for email services)

## 🛠️ Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ekko-cluster/apps/api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Start dependencies**
   ```bash
   # Using Docker Compose
   docker-compose up postgres redis nats -d
   
   # Or install locally
   brew install postgresql redis nats-server  # macOS
   # Start services as needed
   ```

6. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

7. **Create a superuser (for admin access)**
   ```bash
   python manage.py createsuperuser
   ```

8. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

9. **Start the development server**
   ```bash
   python manage.py runserver
   ```

### Docker Development

1. **Build and start all services**
   ```bash
   docker-compose up --build
   ```

2. **Run migrations in container**
   ```bash
   docker-compose exec api python manage.py migrate
   ```

3. **Create superuser in container**
   ```bash
   docker-compose exec api python manage.py createsuperuser
   ```

4. **Access the services**
   - API: http://localhost:8000/api/
   - Admin: http://localhost:8000/admin/
   - Health: http://localhost:8000/health/

## 🔐 Authentication

The API uses a passwordless authentication system with WebAuthn/passkeys as the primary method and email verification codes as a fallback.

### Authentication Methods

1. **WebAuthn/Passkeys** (Primary)
   - Phishing-resistant passwordless authentication
   - Support for platform authenticators (Face ID, Touch ID, Windows Hello)
   - Cross-platform authenticator support

2. **Email Verification Codes** (Fallback)
   - 6-digit verification codes sent via Firebase
   - 10-minute expiry with rate limiting
   - Used for account recovery and cross-device access

### Registration Flow
```bash
# 1. Begin signup with email
POST /api/auth/signup/begin/
{
  "email": "user@example.com"
}

# 2. Verify email with code
POST /api/auth/signup/verify-email/
{
  "email": "user@example.com",
  "code": "123456"
}

# 3. Get WebAuthn registration options
POST /api/auth/webauthn/register/begin/
{
  "email": "user@example.com"
}

# 4. Complete WebAuthn registration
POST /api/auth/webauthn/register/complete/
{
  "email": "user@example.com",
  "credential": { /* WebAuthn credential response */ }
}
```

### Login Flow
```bash
# 1. WebAuthn login (if passkey exists)
POST /api/auth/webauthn/login/begin/
{
  "email": "user@example.com"
}

POST /api/auth/webauthn/login/complete/
{
  "email": "user@example.com",
  "credential": { /* WebAuthn assertion response */ }
}

# 2. Email verification login (fallback)
POST /api/auth/login/email/
{
  "email": "user@example.com"
}

POST /api/auth/login/verify/
{
  "email": "user@example.com",
  "code": "123456"
}
```

### Token Management
- **Knox Tokens**: Device-specific tokens with 48-hour expiry
- **Token Format**: `Token <knox_token>`
- **Header**: `Authorization: Token <knox_token>`
- **Logout**: `POST /api/auth/logout/`

## 🎯 Alert Management

### Alert Templates
Alert templates are reusable patterns for creating alerts. They support natural language descriptions and parameter placeholders.

```bash
# List alert templates
GET /api/alerts/templates/
# Query params: event_type, sub_event, is_public, is_verified, search

# Get popular templates
GET /api/alerts/templates/popular/

# Get templates by event type
GET /api/alerts/templates/by_event_type/?event_type=ACCOUNT_EVENT

# Create a template
POST /api/alerts/templates/
{
  "name": "Balance Threshold Alert",
  "description": "Alert when wallet balance exceeds threshold",
  "nl_template": "Alert me when {{wallet}} balance goes above {{threshold}} {{token}}",
  "spec_blueprint": {
    "event_type": "BALANCE_THRESHOLD",
    "conditions": "balance > {{threshold}}"
  },
  "variables": [
    {"name": "wallet", "type": "address"},
    {"name": "threshold", "type": "number"},
    {"name": "token", "type": "string"}
  ],
  "event_type": "ACCOUNT_EVENT",
  "sub_event": "BALANCE_THRESHOLD",
  "is_public": true
}

# Instantiate a template to create an alert
POST /api/alerts/templates/{template_id}/instantiate/
{
  "params": {
    "wallet": "0x123...",
    "threshold": 100,
    "token": "AVAX"
  },
  "name": "My AVAX Balance Alert"
}
```

### Alerts
```bash
# List alerts
GET /api/alerts/
# Query params: enabled, version, event_type, sub_event, template, chain, latest_only

# Create alert
POST /api/alerts/
{
  "name": "AVAX Balance Alert",
  "nl_description": "Alert me when my AVAX balance goes above 10",
  "event_type": "ACCOUNT_EVENT",
  "sub_event": "BALANCE_THRESHOLD"
}

# Get alert details
GET /api/alerts/{alert_id}/

# Update alert
PUT /api/alerts/{alert_id}/
{
  "name": "Updated Alert Name",
  "enabled": true
}

# Enable/Disable alert
POST /api/alerts/{alert_id}/enable/
POST /api/alerts/{alert_id}/disable/

# Get alert versions
GET /api/alerts/{alert_id}/versions/

# Get alert changelog
GET /api/alerts/{alert_id}/changelog/

# Get alert execution history
GET /api/alerts/{alert_id}/executions/
```

## 👥 Organization & Team Management

### Organizations
Organizations provide multi-tenant support with configurable limits and team management.

```bash
# Organization structure is managed through Django Admin
# Teams are created and managed within organizations
```

### Teams
```bash
# Teams are managed through the Django Admin interface
# API endpoints for team operations are planned for future releases
```

## 🔗 NATS Integration

The API integrates with NATS for event-driven processing:

### Alert Processing Flow
1. User creates alert via natural language input
2. Django queues NLP parsing tasks and publishes progress events via NATS
3. NLP pipeline generates alert specification
4. Processed alert is stored in database
5. wasmCloud actors monitor blockchain for alert conditions

### NATS Subjects
```
# Alert lifecycle events
alerts.created
alerts.updated
alerts.enabled
alerts.disabled

# Job processing
jobs.{job_id}.created
jobs.{job_id}.completed
jobs.{job_id}.failed

# NLP progress
nlp.status
nlp.complete
nlp.error

# Template matching
templates.match.request
templates.match.response
```

## 📊 Django Admin Interface

The Django Admin provides comprehensive management capabilities:

### Access Admin Interface
```
http://localhost:8000/admin/
```

### Admin Features
- **User Management**: Create and manage users, devices, and sessions
- **Organization Management**: Configure organizations and teams
- **Alert Administration**: View and manage alerts, templates, and executions
- **Blockchain Configuration**: Configure chains and subchains
- **NATS Monitoring**: View NATS connections and message activity
- **Audit Logs**: Track all system changes and user actions

### Custom Admin Actions
- Bulk enable/disable alerts
- Export alert templates
- View real-time NATS activity
- Monitor job execution status
- Audit trail for compliance

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test authentication
python manage.py test app

# Run with coverage
coverage run --source='.' manage.py test
coverage report

# Run pytest (if configured)
pytest

# Run specific test file
python manage.py test app.tests.test_views

# Run integration tests
python manage.py test tests.integration
```

## 🚀 Deployment

### Production Environment
```bash
# Set environment variables
export DJANGO_SETTINGS_MODULE=ekko_api.settings.production
export DEBUG=False

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Start with gunicorn
gunicorn ekko_api.wsgi:application --bind 0.0.0.0:8000
```

### Docker Production
```bash
# Build production image
docker build -f Dockerfile -t ekko-api:latest .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d

# Run migrations in production
docker-compose -f docker-compose.prod.yml exec api python manage.py migrate
```

### Environment Variables
Key environment variables for production:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com

# Database
DATABASE_URL=postgres://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# NATS
NATS_URL=nats://host:4222
NATS_USER=nats_user
NATS_PASSWORD=nats_password

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=/path/to/credentials.json
FIREBASE_WEB_API_KEY=your-web-api-key

# CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

## 📝 Development

### Code Style
```bash
# Format code
black .
isort .

# Linting
flake8 .

# Type checking (if mypy is configured)
mypy .
```

### Django Management Commands
```bash
# Create new app
python manage.py startapp app_name

# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Shell access
python manage.py shell

# Database shell
python manage.py dbshell

# Show migrations
python manage.py showmigrations

# Check for issues
python manage.py check
```

### Custom Management Commands
```bash
# Setup Firebase
python manage.py setup_firebase

# Check static files
python manage.py check_static
```

## 🏗️ Project Structure

```
apps/api/
├── app/                    # Main alert management app
│   ├── models/            # Alert, Template, Job models
│   ├── serializers.py     # DRF serializers
│   ├── views.py          # Alert API views
│   ├── admin.py          # Django admin configuration
│   └── services/         # NATS and template services
├── authentication/        # Auth app with WebAuthn support
│   ├── models.py         # User, Device, Session models
│   ├── views.py          # Auth endpoints
│   └── firebase_utils.py # Firebase integration
├── blockchain/           # Blockchain configuration
│   └── models.py        # Chain and SubChain models
├── organizations/        # Multi-tenancy support
│   └── models.py        # Organization and Team models
├── ekko_api/            # Django project settings
│   ├── settings/        # Environment-specific settings
│   ├── urls.py         # URL configuration
│   └── wsgi.py         # WSGI application
├── tests/              # Test suite
├── manage.py           # Django management script
└── requirements.txt    # Python dependencies
```

## 🔒 Security Considerations

- **Passwordless by Default**: No passwords stored or transmitted
- **WebAuthn/Passkeys**: Phishing-resistant authentication
- **Knox Tokens**: Device-specific tokens with automatic expiry
- **Rate Limiting**: Protection against brute force attacks
- **CORS Configuration**: Strict origin validation
- **Input Validation**: Comprehensive input sanitization
- **Audit Logging**: All actions tracked for compliance

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [WebAuthn Guide](https://webauthn.guide/)
- [NATS Documentation](https://docs.nats.io/)
- [Knox Documentation](https://james1345.github.io/django-rest-knox/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is part of the Ekko Cluster platform. See the main repository for license details.

## 🆘 Support

For support and questions:
- Check the [main documentation](/docs/Index.md)
- Review the [API PRD](/docs/prd/apps/api/PRD-Alert-System.md)
- Open an issue in the repository
