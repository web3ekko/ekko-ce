"""
Utility functions for Passwordless Authentication System

Provides helper functions for:
- Magic link generation
- Firebase email link integration
- Recovery code generation
- Device tracking
- Authentication event logging
"""

import secrets
import string
import logging
import os
from datetime import timedelta
from typing import List, Dict, Any, Optional

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import EmailVerificationCode, UserDevice, AuthenticationLog
from .firebase_utils import firebase_auth_manager, create_action_code_settings

User = get_user_model()
logger = logging.getLogger(__name__)


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token
    """
    return secrets.token_urlsafe(length)


def get_device_info(request) -> Dict[str, Any]:
    """
    Extract device information from request
    
    Args:
        request: Django request object
    
    Returns:
        Dictionary containing device information
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Basic device type detection
    device_type = 'web'
    if 'iPhone' in user_agent or 'iPad' in user_agent:
        device_type = 'ios'
    elif 'Android' in user_agent:
        device_type = 'android'
    elif 'Windows' in user_agent or 'Macintosh' in user_agent or 'Linux' in user_agent:
        device_type = 'desktop'
    
    return {
        'user_agent': user_agent,
        'device_type': device_type,
        'ip_address': request.META.get('REMOTE_ADDR'),
        'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
        'webauthn_supported': False,  # This would be set by client
        'biometric_supported': False,  # This would be set by client
    }


def track_user_device(user: User, device_info: Dict[str, Any], request) -> Optional[UserDevice]:
    """
    Track and manage user device for trust and security
    
    Args:
        user: User instance
        device_info: Device information dictionary
        request: Django request object
    
    Returns:
        UserDevice instance or None
    """
    if not device_info:
        return None
    
    # Generate device fingerprint
    device_fingerprint = generate_device_fingerprint(device_info, request)
    
    # Try to find existing device
    device = user.devices.filter(device_fingerprint=device_fingerprint).first()
    
    if device:
        # Update existing device
        device.last_used = timezone.now()
        device.save(update_fields=['last_used'])
    else:
        # Create new device
        device_name = generate_device_name(device_info)
        device = UserDevice.objects.create(
            user=user,
            device_name=device_name,
            device_type=device_info.get('device_type', 'web'),
            device_id=generate_secure_token(16),
            device_fingerprint=device_fingerprint,
            supports_passkey=device_info.get('webauthn_supported', False),
            supports_biometric=device_info.get('biometric_supported', False),
            is_trusted=False,  # New devices start untrusted
            trust_expires_at=None
        )
    
    return device


def generate_device_fingerprint(device_info: Dict[str, Any], request) -> str:
    """
    Generate a device fingerprint for identification
    
    Args:
        device_info: Device information dictionary
        request: Django request object
    
    Returns:
        Device fingerprint string
    """
    # Combine various device characteristics
    fingerprint_data = [
        device_info.get('user_agent', ''),
        device_info.get('accept_language', ''),
        device_info.get('device_type', ''),
        request.META.get('HTTP_ACCEPT_ENCODING', ''),
        # Note: In production, you might include more sophisticated fingerprinting
        # but be mindful of privacy implications
    ]
    
    # Create hash of combined data
    import hashlib
    combined = '|'.join(fingerprint_data)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def generate_device_name(device_info: Dict[str, Any]) -> str:
    """
    Generate a human-readable device name
    
    Args:
        device_info: Device information dictionary
    
    Returns:
        Human-readable device name
    """
    device_type = device_info.get('device_type', 'Unknown')
    user_agent = device_info.get('user_agent', '')
    
    # Extract browser/app info
    if 'Chrome' in user_agent:
        browser = 'Chrome'
    elif 'Firefox' in user_agent:
        browser = 'Firefox'
    elif 'Safari' in user_agent:
        browser = 'Safari'
    elif 'Edge' in user_agent:
        browser = 'Edge'
    else:
        browser = 'Browser'
    
    # Generate name based on device type
    if device_type == 'ios':
        if 'iPhone' in user_agent:
            return f"iPhone ({browser})"
        elif 'iPad' in user_agent:
            return f"iPad ({browser})"
        else:
            return f"iOS Device ({browser})"
    elif device_type == 'android':
        return f"Android Device ({browser})"
    elif device_type == 'desktop':
        if 'Windows' in user_agent:
            return f"Windows Computer ({browser})"
        elif 'Macintosh' in user_agent:
            return f"Mac ({browser})"
        elif 'Linux' in user_agent:
            return f"Linux Computer ({browser})"
        else:
            return f"Desktop ({browser})"
    else:
        return f"Web Browser ({browser})"


def track_authentication_event(
    user: Optional[User],
    method: str,
    success: bool,
    ip_address: str,
    user_agent: str,
    device_info: Dict[str, Any],
    failure_reason: str = ''
) -> AuthenticationLog:
    """
    Log authentication events for security monitoring
    
    Args:
        user: User instance (can be None for failed attempts)
        method: Authentication method used
        success: Whether authentication was successful
        ip_address: IP address of the request
        user_agent: User agent string
        device_info: Device information dictionary
        failure_reason: Reason for failure (if applicable)
    
    Returns:
        AuthenticationLog instance
    """
    return AuthenticationLog.objects.create(
        user=user,
        method=method,
        success=success,
        failure_reason=failure_reason,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info
    )


def is_rate_limited(identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
    """
    Check if an identifier (IP, email, etc.) is rate limited
    
    Args:
        identifier: Unique identifier to check
        max_attempts: Maximum attempts allowed
        window_minutes: Time window in minutes
    
    Returns:
        True if rate limited, False otherwise
    """
    from django.conf import settings
    if getattr(settings, "TESTING", False):
        return False
    from django.core.cache import cache
    
    cache_key = f"rate_limit:{identifier}"
    attempts = cache.get(cache_key, 0)
    
    return attempts >= max_attempts


def increment_rate_limit(identifier: str, window_minutes: int = 15) -> int:
    """
    Increment rate limit counter for an identifier
    
    Args:
        identifier: Unique identifier
        window_minutes: Time window in minutes
    
    Returns:
        Current attempt count
    """
    from django.conf import settings
    if getattr(settings, "TESTING", False):
        return 0
    from django.core.cache import cache
    
    cache_key = f"rate_limit:{identifier}"
    attempts = cache.get(cache_key, 0) + 1
    cache.set(cache_key, attempts, window_minutes * 60)
    
    return attempts


def reset_rate_limit(identifier: str) -> None:
    """
    Reset rate limit for an identifier (typically after successful auth)
    
    Args:
        identifier: Unique identifier to reset
    """
    from django.core.cache import cache
    
    cache_key = f"rate_limit:{identifier}"
    cache.delete(cache_key)


def validate_webauthn_credential(credential_data: Dict[str, Any]) -> bool:
    """
    Validate WebAuthn credential data structure
    
    Args:
        credential_data: WebAuthn credential data
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['id', 'rawId', 'response', 'type']
    
    for field in required_fields:
        if field not in credential_data:
            return False
    
    if credential_data.get('type') != 'public-key':
        return False
    
    # Additional validation would go here in a real implementation
    # This would include cryptographic verification of the attestation
    
    return True


def get_firebase_continue_url(request, path: str) -> str:
    """
    Build Firebase-compatible continue URL using environment variables if available.
    
    This handles the case where Django is running in a container (e.g., api:8000)
    but Firebase needs to generate email links with the external URL (e.g., localhost:8001).
    
    Args:
        request: Django request object
        path: The path to append to the base URL (e.g., '/auth/signup/complete/')
    
    Returns:
        Full URL for Firebase to use in email links
    """
    # Check if we have a custom Firebase action URL host configured
    firebase_host = os.environ.get('FIREBASE_ACTION_URL_HOST')
    
    if firebase_host:
        # Use the custom host for Firebase URLs
        protocol = 'https' if request.is_secure() else 'http'
        # Ensure firebase_host doesn't already have protocol
        if firebase_host.startswith('http://') or firebase_host.startswith('https://'):
            return f"{firebase_host}{path}"
        else:
            return f"{protocol}://{firebase_host}{path}"
    else:
        # Fall back to Django's default behavior
        return request.build_absolute_uri(path)


def generate_verification_code() -> str:
    """
    Generate a 6-digit verification code
    
    Returns:
        6-digit string code
    """
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def create_verification_code(
    email: str,
    purpose: str,
    ip_address: str,
    user_agent: str,
    user: Optional[User] = None
) -> EmailVerificationCode:
    """
    Create a verification code for email authentication
    
    Args:
        email: User's email address
        purpose: Purpose of the code ('signup', 'signin', 'recovery')
        ip_address: Requesting IP address
        user_agent: User agent string
        user: Optional User instance (for existing users)
    
    Returns:
        EmailVerificationCode instance
    """
    # Generate 6-digit code
    code = generate_verification_code()

    # Set expiration using configurable TTL (default 30 minutes)
    ttl_minutes = getattr(settings, 'VERIFICATION_CODE_TTL_MINUTES', 30)
    expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
    
    # Create verification code
    verification_code = EmailVerificationCode.objects.create(
        user=user,
        email=email,
        code=code,
        purpose=purpose,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at
    )
    
    logger.info(f"Created verification code for {email} ({purpose})")
    return verification_code


def send_verification_code_email(email: str, code: str, purpose: str):
    """
    Send verification code via email using configured provider (Resend or Django backend)

    Args:
        email: Recipient email address
        code: 6-digit verification code
        purpose: Purpose of the code for context in email
    """
    subject_map = {
        'signup': 'Your Ekko verification code',
        'signin': 'Your Ekko sign-in code',
        'recovery': 'Your Ekko recovery code'
    }

    subject = subject_map.get(purpose, 'Your Ekko verification code') + f': {code}'

    # Get TTL from settings for email messaging
    ttl_minutes = getattr(settings, 'VERIFICATION_CODE_TTL_MINUTES', 30)

    message = f"""Hi there,

Your Ekko verification code is:

{code}

This code expires in {ttl_minutes} minutes.

Enter this code at app.ekko.zone to continue.

If you didn't request this code, you can safely ignore this email.

Best,
The Ekko Team"""

    html_message = f"""
<div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">Your Ekko Verification Code</h2>
    <p>Hi there,</p>
    <p>Your verification code is:</p>
    <div style="background: #f5f5f5; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #333;">{code}</span>
    </div>
    <p>This code expires in {ttl_minutes} minutes.</p>
    <p>If you didn't request this code, you can safely ignore this email.</p>
    <p>Best,<br>The Ekko Team</p>
</div>
"""

    try:
        # Check if we're using Resend
        if getattr(settings, 'EMAIL_BACKEND', '') == 'resend':
            import resend
            resend.api_key = settings.RESEND_API_KEY

            resend.Emails.send({
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": email,
                "subject": subject,
                "html": html_message,
                "text": message,
            })
            logger.info(f"Sent verification code {code} to {email} via Resend")
        else:
            # Fallback to Django email backend
            from django.core.mail import send_mail
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            logger.info(f"Sent verification code {code} to {email} via Django backend")
    except Exception as e:
        logger.error(f"Failed to send verification code to {email}: {e}")
        raise


def verify_code(email: str, code: str, purpose: str) -> tuple[Optional[EmailVerificationCode], Optional[str]]:
    """
    Verify a user-entered verification code

    Args:
        email: Email address associated with the code
        code: User-entered 6-digit code
        purpose: Expected purpose of the code

    Returns:
        Tuple of (EmailVerificationCode, error_reason):
        - (code, None) if valid
        - (None, 'not_found') if code doesn't exist or wrong code
        - (None, 'expired') if code is expired
        - (None, 'used') if code was already used
    """
    # Find the most recent code for this email, code, and purpose
    verification_code = EmailVerificationCode.objects.filter(
        email=email,
        code=code,
        purpose=purpose,
    ).order_by('-created_at').first()

    if not verification_code:
        return None, 'not_found'

    if verification_code.is_used:
        return None, 'used'

    if verification_code.is_expired:
        return None, 'expired'

    return verification_code, None


def invalidate_previous_codes(email: str, purpose: str):
    """
    Invalidate all previous unused codes for an email and purpose
    
    Args:
        email: Email address
        purpose: Purpose of the codes to invalidate
    """
    EmailVerificationCode.objects.filter(
        email=email,
        purpose=purpose,
        used_at__isnull=True
    ).update(used_at=timezone.now())
