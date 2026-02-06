# Email Configuration Guide

The Ekko API supports multiple email providers through environment variables. You can choose between SendGrid (recommended), SMTP (Gmail, etc.), or console output for development.

## Quick Start

### Option 1: Console Backend (Development)
```bash
# Prints emails to console - no actual sending
export EMAIL_PROVIDER=console
```

### Option 2: SendGrid (Recommended for Production)
```bash
export EMAIL_PROVIDER=sendgrid
export SENDGRID_API_KEY="your-sendgrid-api-key"
export DEFAULT_FROM_EMAIL="noreply@yourdomain.com"
```

### Option 3: SMTP (Gmail, etc.)
```bash
export EMAIL_PROVIDER=smtp
export EMAIL_HOST="smtp.gmail.com"
export EMAIL_PORT=587
export EMAIL_USE_TLS=True
export EMAIL_HOST_USER="your-email@gmail.com"
export EMAIL_HOST_PASSWORD="your-app-specific-password"
export DEFAULT_FROM_EMAIL="noreply@yourdomain.com"
```

## SendGrid Setup

1. **Create a SendGrid Account**
   - Sign up at [sendgrid.com](https://sendgrid.com)
   - Free tier includes 100 emails/day

2. **Generate API Key**
   - Go to Settings → API Keys
   - Click "Create API Key"
   - Give it a name (e.g., "Ekko Development")
   - Select "Restricted Access"
   - Enable "Mail Send" permission
   - Copy the API key (you won't see it again!)

3. **Configure Environment**
   ```bash
   export EMAIL_PROVIDER=sendgrid
   export SENDGRID_API_KEY="SG.xxxxxxxxxxxxxxxxxxxx"
   export DEFAULT_FROM_EMAIL="noreply@yourdomain.com"
   ```

4. **Verify Sender (Optional but Recommended)**
   - Go to Settings → Sender Authentication
   - Add and verify your sending domain or email address

## Gmail SMTP Setup

1. **Enable 2-Factor Authentication**
   - Go to your Google Account settings
   - Security → 2-Step Verification
   - Follow the setup process

2. **Generate App Password**
   - Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Select "Mail" as the app
   - Select your device
   - Copy the generated 16-character password

3. **Configure Environment**
   ```bash
   export EMAIL_PROVIDER=smtp
   export EMAIL_HOST_USER="your-email@gmail.com"
   export EMAIL_HOST_PASSWORD="your-16-char-app-password"
   ```

## Testing Your Configuration

Run the included test script:

```bash
cd apps/api
python test_email.py
```

The script will:
- Show your current configuration
- Send a test email
- Provide troubleshooting tips if it fails

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `EMAIL_PROVIDER` | Yes | Email backend to use | `sendgrid`, `smtp`, `console` |
| `DEFAULT_FROM_EMAIL` | Yes | Default sender email | `noreply@ekko.dev` |
| **SendGrid Settings** |
| `SENDGRID_API_KEY` | If using SendGrid | Your SendGrid API key | `SG.xxxxx` |
| `SENDGRID_SANDBOX_MODE` | No | Test without sending | `True` or `False` |
| **SMTP Settings** |
| `EMAIL_HOST` | If using SMTP | SMTP server address | `smtp.gmail.com` |
| `EMAIL_PORT` | If using SMTP | SMTP server port | `587` |
| `EMAIL_USE_TLS` | If using SMTP | Use TLS encryption | `True` |
| `EMAIL_HOST_USER` | If using SMTP | SMTP username | `user@gmail.com` |
| `EMAIL_HOST_PASSWORD` | If using SMTP | SMTP password | App-specific password |

## Integration with Authentication

The email system is used by the authentication module to send:
- 6-digit verification codes for signup
- 6-digit verification codes for signin
- Account recovery codes

Example email sent:
```
Subject: Your Ekko verification code: 123456

Hi there,

Your Ekko verification code is:

123456

This code expires in 10 minutes.

Enter this code at app.ekko.zone to continue.

If you didn't request this code, you can safely ignore this email.

Best,
The Ekko Team
```

## Troubleshooting

### SendGrid Issues
- **401 Unauthorized**: Check your API key is correct
- **403 Forbidden**: Verify API key has "Mail Send" permission
- **400 Bad Request**: Check sender email is verified
- **Emails not arriving**: Check SendGrid dashboard for bounces/blocks

### Gmail SMTP Issues
- **Authentication failed**: Use app password, not regular password
- **Connection timeout**: Check firewall allows outbound port 587
- **Less secure app error**: Must use app passwords with 2FA enabled

### General Issues
- **Module not found**: Run `pip install sendgrid-django`
- **Settings not loading**: Ensure you're using the correct Django settings module
- **Emails in spam**: Verify sender domain, use proper from address

## Production Recommendations

1. **Use SendGrid or similar service** - Better deliverability than SMTP
2. **Verify your domain** - Improves deliverability and trust
3. **Set up SPF/DKIM/DMARC** - Prevents spoofing
4. **Monitor your sending** - Watch for bounces and complaints
5. **Use templates** - SendGrid supports dynamic templates
6. **Set reasonable rate limits** - Prevent abuse

## Docker Configuration

Add to your `docker-compose.yml`:

```yaml
services:
  api:
    environment:
      - EMAIL_PROVIDER=sendgrid
      - SENDGRID_API_KEY=${SENDGRID_API_KEY}
      - DEFAULT_FROM_EMAIL=noreply@ekko.dev
```

Or for Gmail:

```yaml
services:
  api:
    environment:
      - EMAIL_PROVIDER=smtp
      - EMAIL_HOST=smtp.gmail.com
      - EMAIL_PORT=587
      - EMAIL_USE_TLS=True
      - EMAIL_HOST_USER=${GMAIL_USER}
      - EMAIL_HOST_PASSWORD=${GMAIL_APP_PASSWORD}
      - DEFAULT_FROM_EMAIL=${GMAIL_USER}
```