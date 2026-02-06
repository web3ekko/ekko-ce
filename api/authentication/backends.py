"""
Authentication Backends for Passwordless Authentication System

Implements multiple authentication methods:
- Email verification codes
- Passkey authentication (via Allauth)
- Knox token authentication
"""

import logging
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import EmailVerificationCode

User = get_user_model()
logger = logging.getLogger(__name__)


class MultiAuthBackend(BaseBackend):
    """
    Unified authentication backend for passwordless authentication
    
    Handles multiple authentication methods in the passwordless flow:
    Passkeys → Email Magic Links → Optional TOTP
    """
    
    def authenticate(self, request, **credentials):
        """
        Authenticate user based on the provided credentials
        """
        auth_method = credentials.get('auth_method')
        
        if auth_method == 'email_code':
            return self.authenticate_email_code(request, credentials)
        elif auth_method == 'passkey':
            return self.authenticate_passkey(request, credentials)
        
        return None
    
    
    def authenticate_email_code(self, request, credentials):
        """
        Authenticate using email verification code (6-digit)
        """
        email = credentials.get('email')
        code = credentials.get('code')
        purpose = credentials.get('purpose', 'signin')
        
        if not email or not code:
            return None
        
        try:
            # Verify the code
            verification_code = EmailVerificationCode.objects.filter(
                email=email,
                code=code,
                purpose=purpose,
                used_at__isnull=True
            ).order_by('-created_at').first()
            
            if not verification_code or verification_code.is_expired:
                logger.warning(f"Invalid or expired code for {email}")
                return None
            
            # Mark code as used
            verification_code.used_at = timezone.now()
            verification_code.save()
            
            # Get user
            user = User.objects.get(email=email)
            
            if hasattr(user, 'last_login_method'):
                user.last_login_method = 'email_code'
                user.save(update_fields=['last_login_method'])
            
            logger.info(f"Successful email code authentication for {user.email}")
            return user
            
        except User.DoesNotExist:
            logger.warning(f"User not found for email code auth: {email}")
            return None
        except Exception as e:
            logger.error(f"Email code authentication failed: {e}")
            return None
    
    
    
    def authenticate_passkey(self, request, credentials):
        """
        Authenticate using passkey (handled by Allauth)
        This method tracks the login method for passkey authentication
        """
        user = credentials.get('user')
        if user and hasattr(user, 'last_login_method'):
            user.last_login_method = 'passkey'
            user.save(update_fields=['last_login_method'])
            logger.info(f"Successful passkey authentication for {user.email}")
        return user
    
    def get_user(self, user_id):
        """
        Get user by ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None




class RateLimitMixin:
    """
    Mixin to add rate limiting to authentication backends
    """
    
    def check_rate_limit(self, request, identifier, max_attempts=5, window_minutes=15):
        """
        Check if the request is within rate limits
        """
        # This would typically use Redis or cache framework
        # For now, we'll implement a simple in-memory check
        # In production, use Django's cache framework with Redis
        
        from django.core.cache import cache
        
        cache_key = f"auth_attempts:{identifier}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= max_attempts:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return False
        
        # Increment attempts
        cache.set(cache_key, attempts + 1, window_minutes * 60)
        return True
    
    def reset_rate_limit(self, identifier):
        """
        Reset rate limit for successful authentication
        """
        from django.core.cache import cache
        cache_key = f"auth_attempts:{identifier}"
        cache.delete(cache_key)
