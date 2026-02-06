# Ekko Authentication App
## Passwordless Authentication System

A Django app implementing passwordless authentication with **Passkeys → Email Magic Links → Optional TOTP** flow.

## 🔑 Features

### ✅ Passwordless Authentication
- **Primary**: WebAuthn/Passkey authentication
- **Fallback**: Email magic links
- **Optional**: TOTP 2FA for enhanced security
- **Recovery**: Account recovery with new passkey setup

### ✅ Multi-Platform Support
- **Web**: WebAuthn with SimpleWebAuthn
- **iOS**: AuthenticationServices framework
- **Android**: Credential Manager API
- **Cross-device**: Magic link authentication

### ✅ Security Features
- **Device tracking** and trust management
- **Rate limiting** for authentication attempts
- **Audit logging** for security monitoring
- **Recovery codes** for account recovery
- **Session management** with secure tokens

## 📁 File Structure

```
authentication/
├── models.py              # Django ORM models
├── views.py               # DRF API endpoints
├── serializers.py         # Data validation
├── backends.py            # Custom auth backends
├── utils.py               # Helper functions
├── urls.py                # URL routing
├── admin.py               # Django admin
├── migrations/            # Database migrations
├── CLIENT_INTEGRATION.md  # Client integration guide
├── API_DOCUMENTATION.md   # API documentation
└── README.md             # This file
```

## 🗄️ Models

### Core Models
- **User** - Custom user model with passwordless fields
- **UserDevice** - Device tracking and trust management
- **PasskeyCredential** - WebAuthn credential storage
- **UserSession** - Active session tracking

### Authentication Models
- **EmailMagicLink** - Passwordless email authentication
- **RecoveryCode** - Account recovery codes
- **CrossDeviceSession** - Cross-device authentication
- **AuthenticationLog** - Security audit trail

## 🌐 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/signup/begin/` | POST | Start passwordless signup |
| `/api/auth/signup/complete/` | POST | Complete signup |
| `/api/auth/login/` | POST | Passwordless login |
| `/api/auth/login/magic-link/` | POST | Verify magic link |
| `/api/auth/recovery/` | POST | Account recovery |
| `/api/auth/logout/` | POST | User logout |
| `/api/auth/devices/` | GET | List user devices |
| `/api/auth/totp/setup/` | POST | Setup TOTP 2FA |

## 🔧 Configuration

### Django Settings
```python
# settings.py
INSTALLED_APPS = [
    'authentication',
    'allauth',
    'allauth.account',
    'allauth.mfa',
    'rest_framework',
]

# Custom user model
AUTH_USER_MODEL = 'authentication.User'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'authentication.backends.MultiAuthBackend',
    'authentication.backends.EmailMagicLinkBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth configuration
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
```

### Environment Variables
```bash
# .env
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Ekko API
WEBAUTHN_ORIGIN=http://localhost:3000

AUTH_PASSKEY_ENABLED=True
AUTH_EMAIL_MAGIC_LINK_ENABLED=True
AUTH_2FA_REQUIRED=False
AUTH_CROSS_DEVICE_TIMEOUT=300
AUTH_RECOVERY_CODE_COUNT=10
AUTH_DEVICE_TRUST_DURATION=90
AUTH_SESSION_TIMEOUT=30
AUTH_RATE_LIMIT_ATTEMPTS=5
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install django djangorestframework django-allauth django-otp
```

### 2. Run Migrations
```bash
python manage.py makemigrations authentication
python manage.py migrate
```

### 3. Create Superuser
```bash
python manage.py createsuperuser
```

### 4. Start Development Server
```bash
python manage.py runserver
```

### 5. Test API
```bash
curl -X POST http://localhost:8000/api/auth/signup/begin/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "device_info": {"webauthn_supported": true}}'
```

## 📱 Client Integration

### Web Client
```javascript
import { PasswordlessAuth } from './auth';

const auth = new PasswordlessAuth('http://localhost:8000');
await auth.signUp('user@example.com');
```

### iOS Client
```swift
let authManager = PasswordlessAuthManager()
await authManager.signUp(email: "user@example.com", firstName: "John", lastName: "Doe")
```

### Android Client
```kotlin
val authManager = PasswordlessAuthManager(context)
authManager.signUp("user@example.com", "John", "Doe")
```

See [CLIENT_INTEGRATION.md](CLIENT_INTEGRATION.md) for complete integration guides.

## 📚 Documentation

- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference
- **[Client Integration](CLIENT_INTEGRATION.md)** - Web, iOS, Android integration
- **[Django Admin](http://localhost:8000/admin/)** - Admin interface
- **[API Docs](http://localhost:8000/api/docs/)** - Interactive API documentation

## 🔒 Security Considerations

### Best Practices
1. **Always use HTTPS** in production
2. **Configure proper CORS** settings
3. **Set up rate limiting** for authentication endpoints
4. **Monitor authentication logs** for suspicious activity
5. **Regularly rotate** session tokens
6. **Implement proper** error handling

### Production Checklist
- [ ] HTTPS enabled
- [ ] CORS configured
- [ ] Rate limiting active
- [ ] Logging configured
- [ ] Email service configured
- [ ] WebAuthn domain verified
- [ ] Security headers enabled

## 🧪 Testing

### Run Tests
```bash
python manage.py test authentication
```

### Test Coverage
```bash
coverage run --source='.' manage.py test authentication
coverage report
```

### Manual Testing
1. **Signup Flow**: Test email → passkey → completion
2. **Login Flow**: Test passkey → fallback → magic link
3. **Recovery Flow**: Test lost passkey → email → new passkey
4. **Cross-device**: Test magic link on different device
5. **2FA Flow**: Test TOTP setup and verification

## 🐛 Troubleshooting

### Common Issues

**WebAuthn not working**
- Ensure HTTPS is enabled
- Check `WEBAUTHN_RP_ID` matches domain
- Verify browser support

**Magic links not working**
- Check email configuration
- Verify URL scheme handling
- Check token expiration

**Rate limiting issues**
- Check rate limit settings
- Clear rate limit cache
- Verify IP detection

### Debug Mode
```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'authentication': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For support and questions:
- Check the [API Documentation](API_DOCUMENTATION.md)
- Review [Client Integration](CLIENT_INTEGRATION.md) guides
- Open an issue on GitHub
- Contact the development team
