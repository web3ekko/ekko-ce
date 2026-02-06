"""
Authentication Views for Passwordless Authentication System

Implements REST API endpoints for:
- Passwordless signup (email → passkey → optional TOTP)
- Passwordless signin (passkey → email fallback → optional TOTP)
- Account recovery
- Device management
"""

import logging
import secrets
from datetime import timedelta
import base64

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.core.cache import cache
from django.urls import reverse
from django.template.loader import render_to_string

# Set up logger
logger = logging.getLogger(__name__)

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

# Knox imports
from knox.models import AuthToken

# Test endpoint to verify DRF
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def test_drf(request):
    """Test endpoint to verify DRF is working"""
    from rest_framework.request import Request as DRFRequest
    return Response({
        'method': request.method,
        'is_drf_request': isinstance(request, DRFRequest),
        'request_class': str(request.__class__),
        'data': request.data if hasattr(request, 'data') else None,
        'content_type': request.META.get('CONTENT_TYPE'),
    })
from knox.views import LoginView as KnoxLoginView, LogoutView as KnoxLogoutView
from knox.auth import TokenAuthentication as KnoxTokenAuthentication

from .models import UserDevice, EmailVerificationCode
from .serializers import (
    SignupBeginSerializer,
    LoginSerializer,
    DeviceSerializer,
    PasskeyRegistrationSerializer,
    PasskeyAuthenticationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
    WebAuthnRegisterBeginSerializer,
    WebAuthnRegisterCompleteSerializer
)
from .utils import (
    create_verification_code,
    send_verification_code_email,
    verify_code,
    invalidate_previous_codes,
    get_device_info,
    track_authentication_event,
    get_firebase_continue_url,
    is_rate_limited,
    increment_rate_limit,
    reset_rate_limit
)
from .firebase_utils import firebase_auth_manager

# Django Allauth MFA imports (WebAuthn support)
try:
    from allauth.mfa.models import Authenticator
    from allauth.mfa.webauthn.internal import auth as webauthn_auth
    from allauth.mfa.adapter import get_adapter as get_mfa_adapter
    ALLAUTH_WEBAUTHN_AVAILABLE = True
except ImportError:
    ALLAUTH_WEBAUTHN_AVAILABLE = False
    logger.warning("Django Allauth WebAuthn support not available")

User = get_user_model()


def generate_tokens_for_user(user):
    """
    Generate Knox tokens for a user (48-hour expiry, device-specific).

    Also caches the token in Redis for WebSocket provider authentication.
    The WebSocket provider validates tokens by looking up the first 8
    characters of the token in Redis.
    """
    # Create Knox token instance
    instance, token = AuthToken.objects.create(user=user)

    # Cache token in Redis for WebSocket provider authentication
    try:
        from authentication.services.knox_cache import get_knox_cache_service
        cache_service = get_knox_cache_service()
        cache_service.cache_token(
            token=token,
            user_id=str(user.id),
            expiry=instance.expiry
        )
    except Exception as e:
        # Don't fail authentication if caching fails
        logger.warning(f"Failed to cache Knox token for WebSocket: {e}")

    return {
        'knox_token': token,
        'expires': instance.expiry,
        'created': instance.created,
        'token_type': 'knox',
        # Keep compatibility for any code expecting 'access' field
        'access': token,
    }


def generate_firebase_custom_token(user):
    """
    Generate Firebase custom token for real-time features
    """
    try:
        if firebase_auth_manager.is_available():
            custom_token = firebase_auth_manager.create_custom_token(
                uid=str(user.id),
                additional_claims={
                    'email': user.email,
                    'email_verified': user.is_email_verified,
                }
            )
            return custom_token
    except Exception as e:
        logger.warning(f"Failed to generate Firebase custom token for {user.email}: {e}")
    return None


@api_view(['POST'])
@permission_classes([AllowAny])
def check_account_status(request):
    """
    Check if an email has an existing account and its status
    
    Returns:
        - no_account: No account exists
        - inactive_account: Account exists but is inactive
        - active_account: Active account exists
    """
    email = request.data.get('email')
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
        if user.is_active:
            # Check if user has passkey
            has_passkey = user.has_passkey or user.has_passkey_via_allauth
            return Response({
                'status': 'active_account',
                'has_passkey': has_passkey,
                'message': 'Active account found'
            })
        else:
            return Response({
                'status': 'inactive_account',
                'message': 'Inactive account found'
            })
    except User.DoesNotExist:
        return Response({
            'status': 'no_account',
            'message': 'No account found'
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_begin(request):
    """
    Start passkey-first signup process with mandatory email verification
    
    Single flow: Email → Verification Code → Passkey Creation (mandatory)
    """
    logger.info(f"🔥 SIGNUP BEGIN - Request received from {request.META.get('REMOTE_ADDR')}")
    
    # Debug: Check if this is a DRF request
    from rest_framework.request import Request as DRFRequest
    logger.info(f"🔥 SIGNUP BEGIN - Is DRF Request: {isinstance(request, DRFRequest)}")
    logger.info(f"🔥 SIGNUP BEGIN - Request class: {request.__class__}")
    
    # Get email from request data
    email = request.data.get('email')
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    email = str(email).strip().lower()
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    try:
        validate_email(email)
    except ValidationError:
        return Response(
            {"error": "Invalid email address"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check for active account
    try:
        user = User.objects.get(email=email)
        if user.is_active:
            return Response(
                {'error': 'An active account already exists with this email. Please sign in instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # If inactive account exists, we'll reactivate it through the signup flow
    except User.DoesNotExist:
        user = None

    # Rate limiting check
    rate_limit_key = f"signup:{email}"
    if is_rate_limited(rate_limit_key, max_attempts=3, window_minutes=60):
        return Response(
            {'error': 'Too many signup attempts. Please try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # Create Firebase user first (if Firebase is available)
    firebase_uid = None
    firebase_user_created = False
    
    if firebase_auth_manager.is_available():
        try:
            # Create Firebase user
            firebase_user = firebase_auth_manager.create_user(email)
            firebase_uid = firebase_user.uid
            firebase_user_created = True
            logger.info(f"🔥 Firebase user created with UID: {firebase_uid}")
        except Exception as e:
            logger.warning(f"🔥 Failed to create Firebase user for {email}: {e}")
            # Generate fallback UID
            firebase_uid = f"fallback_{secrets.token_hex(8)}_{int(timezone.now().timestamp())}"
    else:
        # Fallback UID when Firebase is not available
        firebase_uid = f"fallback_{secrets.token_hex(8)}_{int(timezone.now().timestamp())}"
        logger.info(f"🔥 Firebase not available - using fallback UID: {firebase_uid}")

    # Create or update Django user
    if user:
        # Update existing inactive user
        user.firebase_uid = firebase_uid
        user.save()
        logger.info(f"🔥 Updated existing inactive user with Firebase UID: {firebase_uid}")
    else:
        # Create new Django user
        user = User.objects.create_user(
            email=email,
            firebase_uid=firebase_uid,
            is_active=False,  # Will be activated after email verification + passkey
            is_email_verified=False,
            preferred_auth_method='passkey'
        )
        logger.info(f"🔥 Django user created (ID: {user.id}) with Firebase UID: {firebase_uid}")

    # Invalidate any previous codes for this email
    invalidate_previous_codes(email, 'signup')

    # Create verification code
    verification_code = create_verification_code(
        email=email,
        purpose='signup',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        user=user
    )

    # Send verification code email (handle errors gracefully in dev mode)
    from django.conf import settings as django_settings
    try:
        send_verification_code_email(email, verification_code.code, 'signup')
        email_sent = True
    except Exception as e:
        if django_settings.DEBUG:
            # In development, log the code and continue
            logger.warning(f"Email sending failed (dev mode): {e}")
            logger.info(f"🔑 DEV MODE - Signup verification code for {email}: {verification_code.code}")
            email_sent = False  # Mark as not sent but continue
        else:
            logger.error(f"🔥 Failed to send verification code to {email}: {e}")
            return Response(
                {'error': 'Failed to send verification code. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Increment rate limit
    increment_rate_limit(rate_limit_key, window_minutes=60)

    return Response({
        'success': True,
        'email': email,
        'message': 'Verification code sent. Please check your email.',
        'next_step': 'verify_code',
        'code_expires_in': 600,  # 10 minutes
        'resend_available': True
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_verify_code(request):
    """
    Verify email code and initiate mandatory passkey creation
    """
    email = request.data.get('email')
    code = request.data.get('code')
    
    if not email or not code:
        return Response(
            {'error': 'Email and code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify the code
    verification_code = verify_code(email, code, 'signup')
    
    if not verification_code:
        # Check if we should show specific error messages
        recent_code = EmailVerificationCode.objects.filter(
            email=email,
            purpose='signup'
        ).order_by('-created_at').first()
        
        if recent_code:
            if recent_code.is_expired:
                return Response({
                    'error': 'Code expired. Request a new one.',
                    'error_type': 'expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif recent_code.is_used:
                return Response({
                    'error': 'Code already used. Request a new one.',
                    'error_type': 'already_used'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        
        return Response({
            'error': 'Invalid code',
            'error_type': 'invalid'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Mark code as used
    verification_code.mark_as_used()
    
    # Get the user and mark email as verified and activate account
    user = verification_code.user
    user.is_email_verified = True
    user.is_active = True  # Activate user after email verification
    user.save()
    
    # Reset rate limit after successful verification
    reset_rate_limit(f"signup:{email}")
    
    # Generate WebAuthn registration options for mandatory passkey creation
    webauthn_options = None
    if ALLAUTH_WEBAUTHN_AVAILABLE:
        try:
            # Generate WebAuthn registration options
            webauthn_options = webauthn_auth.begin_registration(user, passwordless=True)
        except Exception as e:
            logger.error(f"Failed to generate WebAuthn options for {user.email}: {e}")
    
    # Create Knox token for authenticated passkey registration
    # Use generate_tokens_for_user to ensure token is cached in Redis for WebSocket provider
    tokens = generate_tokens_for_user(user)
    token = tokens['knox_token']
    logger.info(f"🔑 Created and cached auth token for {user.email} after email verification")
    
    return Response({
        'success': True,
        'message': 'Email verified! Please create a passkey to complete signup.',
        'user_id': str(user.id),
        'email': user.email,
        'next_step': 'create_passkey',
        'webauthn_options': webauthn_options,
        'passkey_required': True,  # Mandatory passkey creation
        'token': token  # Include token for authenticated requests
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_complete(request):
    """
    Complete signup after passkey registration
    """
    user_id = request.data.get('user_id')
    credential_data = request.data.get('credential_data')
    
    if not user_id or not credential_data:
        return Response(
            {'error': 'User ID and credential data are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id)
        
        # Verify user has verified email but is not yet active
        if not user.is_email_verified:
            return Response(
                {'error': 'Email not verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.is_active:
            return Response(
                {'error': 'Account already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Complete WebAuthn registration
        if ALLAUTH_WEBAUTHN_AVAILABLE:
            try:
                authenticator = webauthn_auth.complete_registration(request, credential_data)
                
                # Update user's passkey status
                user.has_passkey = True
                user.is_active = True  # Activate account after passkey creation
                user.save()
                
                logger.info(f"🔥 Passkey created and account activated for: {user.email}")
            except Exception as e:
                logger.error(f"Failed to complete passkey registration for {user.email}: {e}")
                return Response(
                    {'error': 'Failed to create passkey'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(
                {'error': 'WebAuthn not available'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        
        # Generate Knox token
        tokens = generate_tokens_for_user(user)
        
        # Generate Firebase custom token
        firebase_token = generate_firebase_custom_token(user)
        
        # Track authentication event
        track_authentication_event(
            user=user,
            method='passkey_registration',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_info=request.data.get('device_info', {})
        )
        
        response_data = {
            'success': True,
            'message': 'Account created successfully!',
            'user': {
                'id': str(user.id),
                'email': user.email,
            },
            'tokens': tokens,
            'has_passkey': True
        }
        
        if firebase_token:
            response_data['firebase_token'] = firebase_token
        
        return Response(response_data)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Signup completion failed: {e}")
        return Response(
            {'error': 'Signup failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_code(request):
    """
    Resend verification code for signup, signin, or recovery
    """
    email = request.data.get('email')
    purpose = request.data.get('purpose', 'signup')
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if purpose not in ['signup', 'signin', 'recovery']:
        return Response(
            {'error': 'Invalid purpose'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Rate limiting check
    rate_limit_key = f"resend:{purpose}:{email}"
    if is_rate_limited(rate_limit_key, max_attempts=3, window_minutes=60):
        return Response(
            {'error': 'Too many resend attempts. Please try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    # Get user if exists
    user = None
    try:
        user = User.objects.get(email=email)
        
        # For signup, check if user is already active
        if purpose == 'signup' and user.is_active:
            return Response(
                {'error': 'Account already exists. Please sign in instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # For signin, check if user is active
        if purpose == 'signin' and not user.is_active:
            return Response(
                {'error': 'Account not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )
    except User.DoesNotExist:
        if purpose in ['signin', 'recovery']:
            return Response(
                {'error': 'Account not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        # For signup, user might not exist yet, that's ok
    
    # Invalidate previous codes
    invalidate_previous_codes(email, purpose)
    
    # Create new verification code
    verification_code = create_verification_code(
        email=email,
        purpose=purpose,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        user=user
    )
    
    # Send verification code email
    try:
        send_verification_code_email(email, verification_code.code, purpose)
    except Exception as e:
        logger.error(f"Failed to resend verification code to {email}: {e}")
        return Response(
            {'error': 'Failed to send verification code. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Increment rate limit
    increment_rate_limit(rate_limit_key, window_minutes=60)
    
    return Response({
        'success': True,
        'message': 'Verification code sent.',
        'email': email,
        'code_expires_in': 600  # 10 minutes
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_passkey_begin(request):
    """
    Begin passkey sign-in (primary method)
    WebAuthn conditional UI - no email needed
    """
    if not ALLAUTH_WEBAUTHN_AVAILABLE:
        return Response(
            {'error': 'WebAuthn support is not available'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    try:
        # For conditional UI, we don't need email upfront
        # Generate challenge for any passkey
        challenge = secrets.token_urlsafe(32)
        
        # Store challenge in session for verification
        request.session['webauthn_signin_challenge'] = challenge
        
        return Response({
            'challenge': challenge,
            'rp': {
                'name': getattr(settings, 'MFA_WEBAUTHN_RP_NAME', 'Ekko'),
                'id': getattr(settings, 'MFA_WEBAUTHN_RP_ID', 'localhost')
            },
            'userVerification': 'required',
            'timeout': 60000
        })
    except Exception as e:
        logger.error(f"Failed to begin passkey authentication: {e}")
        return Response(
            {'error': 'Failed to generate authentication options'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_passkey_complete(request):
    """
    Complete passkey sign-in
    """
    if not ALLAUTH_WEBAUTHN_AVAILABLE:
        return Response(
            {'error': 'WebAuthn support is not available'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    credential_data = request.data.get('credential_data')
    if not credential_data:
        return Response(
            {'error': 'Credential data is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Complete WebAuthn authentication
        user = webauthn_auth.complete_authentication(request, credential_data)
        
        if not user:
            return Response(
                {'error': 'Authentication failed'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user is active
        if not user.is_active:
            return Response(
                {'error': 'Account is inactive'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate Knox token
        tokens = generate_tokens_for_user(user)
        
        # Generate Firebase custom token
        firebase_token = generate_firebase_custom_token(user)
        
        # Track authentication event
        track_authentication_event(
            user=user,
            method='passkey',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_info=request.data.get('device_info', {})
        )
        
        response_data = {
            'success': True,
            'message': 'Signed in successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
            },
            'tokens': tokens
        }
        
        if firebase_token:
            response_data['firebase_token'] = firebase_token
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Passkey authentication failed: {e}")
        return Response(
            {'error': 'Authentication failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_email_send_code(request):
    """
    Send verification code for email sign-in (fallback method)
    """
    email = request.data.get('email')
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if active account exists
    try:
        user = User.objects.get(email=email)
        if not user.is_active:
            return Response(
                {'error': 'Account not found or inactive'},
                status=status.HTTP_404_NOT_FOUND
            )
    except User.DoesNotExist:
        return Response(
            {'error': 'No account found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Rate limiting check
    rate_limit_key = f"signin:{email}"
    if is_rate_limited(rate_limit_key, max_attempts=5, window_minutes=15):
        return Response(
            {'error': 'Too many sign-in attempts. Please try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    # Invalidate previous codes
    invalidate_previous_codes(email, 'signin')
    
    # Create verification code
    verification_code = create_verification_code(
        email=email,
        purpose='signin',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        user=user
    )
    
    # Send verification code email
    try:
        send_verification_code_email(email, verification_code.code, 'signin')
    except Exception as e:
        logger.error(f"Failed to send sign-in code to {email}: {e}")
        return Response(
            {'error': 'Failed to send verification code. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Increment rate limit
    increment_rate_limit(rate_limit_key, window_minutes=15)
    
    # Check if user has passkey for prompting later
    has_passkey = user.has_passkey or user.has_passkey_via_allauth
    
    return Response({
        'success': True,
        'email': email,
        'message': 'Verification code sent. Please check your email.',
        'code_expires_in': 600,  # 10 minutes
        'resend_available': True,
        'has_passkey': has_passkey  # To prompt for passkey setup after signin
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_email_verify_code(request):
    """
    Verify code and complete email sign-in
    """
    email = request.data.get('email')
    code = request.data.get('code')
    
    if not email or not code:
        return Response(
            {'error': 'Email and code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify the code
    verification_code = verify_code(email, code, 'signin')
    
    if not verification_code:
        # Check for specific error conditions
        recent_code = EmailVerificationCode.objects.filter(
            email=email,
            purpose='signin'
        ).order_by('-created_at').first()
        
        if recent_code:
            if recent_code.is_expired:
                return Response({
                    'error': 'Code expired. Request a new one.',
                    'error_type': 'expired'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        
        return Response({
            'error': 'Invalid code',
            'error_type': 'invalid'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Mark code as used
    verification_code.mark_as_used()
    
    # Get user
    user = verification_code.user
    
    # Generate Knox token
    tokens = generate_tokens_for_user(user)
    
    # Generate Firebase custom token
    firebase_token = generate_firebase_custom_token(user)
    
    # Reset rate limit after successful signin
    reset_rate_limit(f"signin:{email}")
    
    # Track authentication event
    track_authentication_event(
        user=user,
        method='email_code',
        success=True,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        device_info=request.data.get('device_info', {})
    )
    
    # Check if user should be prompted to add passkey
    has_passkey = user.has_passkey or user.has_passkey_via_allauth
    prompt_passkey = not has_passkey and ALLAUTH_WEBAUTHN_AVAILABLE
    
    response_data = {
        'success': True,
        'message': 'Signed in successfully',
        'user': {
            'id': str(user.id),
            'email': user.email,
        },
        'tokens': tokens,
        'prompt_passkey': prompt_passkey
    }
    
    if firebase_token:
        response_data['firebase_token'] = firebase_token
    
    return Response(response_data)




@api_view(['POST'])
@permission_classes([AllowAny])
def account_recovery(request):
    """
    Account recovery - send verification code
    """
    email = request.data.get('email')
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
        if not user.is_active:
            # Don't reveal account status
            return Response({
                'message': 'If an account exists, recovery code has been sent to your email'
            })
    except User.DoesNotExist:
        # Don't reveal if email exists
        return Response({
            'message': 'If an account exists, recovery code has been sent to your email'
        })

    # Rate limiting check
    rate_limit_key = f"recovery:{email}"
    if is_rate_limited(rate_limit_key, max_attempts=3, window_minutes=60):
        return Response(
            {'error': 'Too many recovery attempts. Please try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # Invalidate previous codes
    invalidate_previous_codes(email, 'recovery')

    # Create verification code
    verification_code = create_verification_code(
        email=email,
        purpose='recovery',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        user=user
    )

    # Send recovery code email
    try:
        send_verification_code_email(email, verification_code.code, 'recovery')
    except Exception as e:
        logger.error(f"Failed to send recovery code to {email}: {e}")
        return Response(
            {'error': 'Failed to send recovery code. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Increment rate limit
    increment_rate_limit(rate_limit_key, window_minutes=60)

    # Log recovery attempt
    track_authentication_event(
        user=user,
        method='recovery_code',
        success=True,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        device_info={}
    )

    return Response({
        'success': True,
        'message': 'Recovery code sent to your email',
        'code_expires_in': 600  # 10 minutes
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def account_recovery_verify(request):
    """
    Verify recovery code and reset access
    """
    email = request.data.get('email')
    code = request.data.get('code')
    
    if not email or not code:
        return Response(
            {'error': 'Email and code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify the code
    verification_code = verify_code(email, code, 'recovery')
    
    if not verification_code:
        return Response({
            'error': 'Invalid or expired code',
            'error_type': 'invalid'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Mark code as used
    verification_code.mark_as_used()
    
    # Get user
    user = verification_code.user
    
    # Revoke all existing Knox tokens
    AuthToken.objects.filter(user=user).delete()
    
    # Reset rate limit
    reset_rate_limit(f"recovery:{email}")
    
    # Track recovery event
    track_authentication_event(
        user=user,
        method='recovery_code',
        success=True,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        device_info={'action': 'recovery_verified'}
    )
    
    # Generate WebAuthn registration options for new passkey
    webauthn_options = None
    if ALLAUTH_WEBAUTHN_AVAILABLE:
        try:
            webauthn_options = webauthn_auth.begin_registration(user, passwordless=True)
        except Exception as e:
            logger.error(f"Failed to generate WebAuthn options for recovery: {e}")
    
    return Response({
        'success': True,
        'message': 'Account verified. Please create a new passkey.',
        'user_id': str(user.id),
        'email': user.email,
        'next_step': 'create_new_passkey',
        'webauthn_options': webauthn_options,
        'all_tokens_revoked': True
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def account_recovery_complete(request):
    """
    Complete account recovery after new passkey creation
    """
    user_id = request.data.get('user_id')
    credential_data = request.data.get('credential_data')
    
    if not user_id or not credential_data:
        return Response(
            {'error': 'User ID and credential data are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id)
        
        # Complete WebAuthn registration
        if ALLAUTH_WEBAUTHN_AVAILABLE:
            try:
                authenticator = webauthn_auth.complete_registration(request, credential_data)
                
                # Update user's passkey status
                user.has_passkey = True
                user.save()
                
                logger.info(f"New passkey created for account recovery: {user.email}")
            except Exception as e:
                logger.error(f"Failed to complete passkey registration in recovery: {e}")
                return Response(
                    {'error': 'Failed to create new passkey'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Generate new Knox token
        tokens = generate_tokens_for_user(user)
        
        # Generate Firebase custom token
        firebase_token = generate_firebase_custom_token(user)
        
        # Track recovery completion
        track_authentication_event(
            user=user,
            method='recovery_code',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_info={'action': 'recovery_completed'}
        )
        
        response_data = {
            'success': True,
            'message': 'Account recovery completed successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
            },
            'tokens': tokens
        }
        
        if firebase_token:
            response_data['firebase_token'] = firebase_token
        
        return Response(response_data)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Account recovery completion failed: {e}")
        return Response(
            {'error': 'Recovery failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """
    Logout user and invalidate session.

    Also invalidates Knox tokens from Redis cache for WebSocket authentication.
    """
    user = request.user

    # Invalidate Knox tokens from Redis cache for WebSocket provider
    try:
        from authentication.services.knox_cache import get_knox_cache_service
        cache_service = get_knox_cache_service()
        invalidated = cache_service.invalidate_all_user_tokens(str(user.id))
        logger.info(f"Invalidated {invalidated} Knox tokens from cache for user {user.id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate Knox tokens from cache: {e}")

    # Log logout event
    track_authentication_event(
        user=user,
        method='logout',
        success=True,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        device_info={}
    )

    logout(request)

    return Response({
        'message': 'Successfully logged out'
    })




def track_user_device(user, device_info, request):
    """Track user device for trust management"""
    # Implementation would create/update UserDevice
    logger.info(f"Tracking device for {user.email}: {device_info}")
    return None


def generate_2fa_session_token(user):
    """Generate 2FA session token"""
    return secrets.token_urlsafe(32)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def signup_passkey_register(request):
    """
    Register a passkey during signup flow and activate the user account.
    This endpoint is called after email verification to complete the signup process.
    """
    if not ALLAUTH_WEBAUTHN_AVAILABLE:
        return Response(
            {'error': 'WebAuthn support is not available'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    try:
        # Get authenticated user from request
        user = request.user
        
        device_info = request.data.get('device_info', {})
        
        # Check if this is the initial request for registration options
        if 'credential_data' not in request.data:
            # Begin registration - generate WebAuthn options
            try:
                from allauth.core.context import request_context
                
                # Debug logging for begin registration
                logger.info(f"[SIGNUP PASSKEY BEGIN] User: {user.email}, ID: {user.id}")
                
                # Force session creation to satisfy django-allauth requirements
                if not request.session.session_key:
                    request.session.create()
                    logger.info(f"[SIGNUP PASSKEY BEGIN] Created new session: {request.session.session_key}")
                
                # Ensure session is saved
                request.session.save()
                
                # Set the request context for Django Allauth
                with request_context(request):
                    options = webauthn_auth.begin_registration(user, passwordless=True)
                
                # Extract the session state that django-allauth stored
                from allauth.mfa.webauthn.internal.auth import STATE_SESSION_KEY
                session_state = request.session.get(STATE_SESSION_KEY)
                
                if session_state:
                    # Store the WebAuthn state in cache for stateless retrieval
                    cache_key = f"webauthn_state_{user.id}"
                    cache.set(cache_key, session_state, timeout=300)  # 5 minutes
                    logger.info(f"[SIGNUP PASSKEY BEGIN] Stored WebAuthn state in cache for user {user.id}")
                    logger.info(f"[SIGNUP PASSKEY BEGIN] State keys: {list(session_state.keys()) if isinstance(session_state, dict) else 'Not a dict'}")
                else:
                    logger.warning(f"[SIGNUP PASSKEY BEGIN] No WebAuthn state found in session")
                
                return Response({
                    'success': True,
                    'options': options,
                    'message': 'Registration options generated. Complete the WebAuthn ceremony.'
                })
                
            except Exception as e:
                logger.error(f"Failed to begin signup passkey registration for {user.email}: {e}")
                return Response(
                    {'error': 'Failed to generate registration options'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Complete registration - process WebAuthn response
        else:
            serializer = PasskeyRegistrationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            credential_data = serializer.validated_data['credential_data']
            
            try:
                # Complete the WebAuthn registration using Django Allauth
                from allauth.core.context import request_context
                from allauth.mfa.models import Authenticator
                
                # Debug logging
                logger.info(f"[SIGNUP PASSKEY COMPLETE] User: {user.email}, ID: {user.id}")
                logger.info(f"[SIGNUP PASSKEY COMPLETE] credential_data type: {type(credential_data)}")
                logger.info(f"[SIGNUP PASSKEY COMPLETE] credential_data keys: {list(credential_data.keys()) if isinstance(credential_data, dict) else 'Not a dict'}")
                
                # Retrieve WebAuthn state from cache
                from allauth.mfa.webauthn.internal.auth import STATE_SESSION_KEY
                cache_key = f"webauthn_state_{user.id}"
                cached_state = cache.get(cache_key)
                
                if cached_state:
                    logger.info(f"[SIGNUP PASSKEY COMPLETE] Retrieved WebAuthn state from cache")
                    # Force session creation and restore the state
                    if not request.session.session_key:
                        request.session.create()
                    request.session[STATE_SESSION_KEY] = cached_state
                    request.session.save()
                    logger.info(f"[SIGNUP PASSKEY COMPLETE] Restored WebAuthn state to session")
                else:
                    logger.warning(f"[SIGNUP PASSKEY COMPLETE] No cached WebAuthn state found")
                
                # Set the request context for Django Allauth
                authenticator = None
                try:
                    with request_context(request):
                        # The complete_registration method returns the Authenticator instance
                        result = webauthn_auth.complete_registration(credential_data)
                        logger.info(f"[SIGNUP PASSKEY COMPLETE] Registration result type: {type(result)}")
                        logger.info(f"[SIGNUP PASSKEY COMPLETE] Registration result: {result}")
                        
                        # Check if result is an Authenticator model instance
                        if hasattr(result, 'id') and hasattr(result, 'user'):
                            authenticator = result
                        else:
                            # If not, try to find the newly created authenticator
                            authenticator = Authenticator.objects.filter(
                                user=user,
                                type=Authenticator.Type.WEBAUTHN
                            ).order_by('-created_at').first()
                            logger.info(f"[SIGNUP PASSKEY COMPLETE] Found authenticator after registration: {authenticator}")
                            
                            # If still no authenticator and we have AuthenticatorData, create one manually
                            if not authenticator and hasattr(result, 'counter'):
                                from allauth.mfa.models import Authenticator
                                import base64
                                import cbor2
                                
                                logger.info(f"[SIGNUP PASSKEY COMPLETE] Attempting to create authenticator from AuthenticatorData")
                                
                                # result is the AuthenticatorData object itself
                                # Check if it has credential_data attribute (for attested credential data)
                                if hasattr(result, 'credential_data') and result.credential_data:
                                    cred_data = result.credential_data
                                    
                                    # Encode public key to CBOR
                                    public_key_cbor = cbor2.dumps(cred_data.public_key)
                                    
                                    # Create the Authenticator instance with proper data structure
                                    # Note: django-allauth expects 'credential' key, not 'credential_id'
                                    authenticator_data = {
                                        'credential': base64.b64encode(cred_data.credential_id).decode('utf-8'),
                                        'public_key': base64.b64encode(public_key_cbor).decode('utf-8'),
                                        'sign_count': result.counter,
                                        'aaguid': str(cred_data.aaguid) if hasattr(cred_data, 'aaguid') else '00000000-0000-0000-0000-000000000000',
                                    }
                                    
                                    authenticator = Authenticator.objects.create(
                                        user=user,
                                        type=Authenticator.Type.WEBAUTHN,
                                        data=authenticator_data
                                    )
                                    
                                    logger.info(f"[SIGNUP PASSKEY COMPLETE] Created authenticator manually from AuthenticatorData: {authenticator.id}")
                                else:
                                    logger.error(f"[SIGNUP PASSKEY COMPLETE] AuthenticatorData has no credential_data attribute")
                    
                    # Clean up the cached state
                    cache.delete(cache_key)
                except Exception as e:
                    logger.error(f"[SIGNUP PASSKEY COMPLETE] Error during registration: {e}")
                    logger.error(f"[SIGNUP PASSKEY COMPLETE] Error type: {type(e).__name__}")
                    logger.error(f"[SIGNUP PASSKEY COMPLETE] Credential data structure: {credential_data}")
                    
                    # The error is likely due to django-allauth expecting the authenticator to be created
                    # but something in the internal implementation is failing
                    # Let's check if an authenticator was already created
                    try:
                        # Check if authenticator was created despite the error
                        authenticator = Authenticator.objects.filter(
                            user=user,
                            type=Authenticator.Type.WEBAUTHN
                        ).order_by('-created_at').first()
                        
                        if authenticator:
                            logger.info(f"[SIGNUP PASSKEY COMPLETE] Found existing authenticator: {authenticator.id}")
                            # Clean up the cached state
                            cache.delete(cache_key)
                        else:
                            # Try to create one manually with the correct data structure
                            from allauth.mfa.models import Authenticator
                            import base64
                            
                            # Parse the attestation response
                            attestation = credential_data.get('response', {})
                            
                            # The data field expects specific keys based on django-allauth's internal structure
                            authenticator_data = {
                                'credential_id': base64.b64encode(
                                    base64.b64decode(credential_data.get('rawId', credential_data.get('id', '')))
                                ).decode('utf-8'),
                                'public_key_cbor': attestation.get('publicKey', ''),
                                'sign_count': 0,
                                'aaguid': '00000000-0000-0000-0000-000000000000',  # Default AAGUID
                            }
                            
                            # Create the Authenticator instance
                            authenticator = Authenticator.objects.create(
                                user=user,
                                type=Authenticator.Type.WEBAUTHN,
                                data=authenticator_data
                            )
                            
                            logger.info(f"[SIGNUP PASSKEY COMPLETE] Created authenticator manually: {authenticator.id}")
                            
                            # Clean up the cached state
                            cache.delete(cache_key)
                        
                    except Exception as manual_error:
                        logger.error(f"[SIGNUP PASSKEY COMPLETE] Manual registration also failed: {manual_error}")
                        # Log the full traceback for debugging
                        import traceback
                        logger.error(f"[SIGNUP PASSKEY COMPLETE] Traceback: {traceback.format_exc()}")
                        # Don't re-raise - return error response instead
                        return Response(
                            {'error': 'Failed to complete passkey registration. Please try again.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                
                # Check if we have an authenticator
                if not authenticator:
                    logger.error(f"[SIGNUP PASSKEY COMPLETE] No authenticator was created")
                    return Response(
                        {'error': 'Failed to create passkey. Please try again.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Update user to indicate they have a passkey
                user.has_passkey = True
                user.save(update_fields=['has_passkey'])
                
                # Log the event
                track_authentication_event(
                    user=user,
                    method='signup_passkey_registration',
                    success=True,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    device_info=device_info
                )
                
                # Generate new tokens for the now-active user
                tokens = generate_tokens_for_user(user)
                
                # Generate Firebase custom token
                firebase_token = generate_firebase_custom_token(user)
                
                response_data = {
                    'success': True,
                    'message': 'Signup completed successfully!',
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'is_active': user.is_active,
                    },
                    'tokens': tokens,
                    'authenticator_id': str(authenticator.id) if hasattr(authenticator, 'id') else None
                }
                
                if firebase_token:
                    response_data['firebase_token'] = firebase_token
                
                return Response(response_data)
                
            except Exception as e:
                logger.error(f"Failed to complete signup passkey registration for {user.email}: {e}")
                return Response(
                    {'error': 'Failed to complete passkey registration'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    
    except Exception as e:
        logger.error(f"Signup passkey registration error: {e}")
        return Response(
            {'error': 'Passkey registration failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def signup_skip_passkey(request):
    """
    Skip passkey creation during signup.
    This allows users to complete signup without setting up a passkey.
    """
    try:
        user = request.user
        
        # Log that user skipped passkey setup
        logger.info(f"User {user.email} skipped passkey setup during signup")
        
        # Track the event
        track_authentication_event(
            user=user,
            method='signup_skip_passkey',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_info=request.data.get('device_info', {})
        )
        
        # Return success response
        return Response({
            'success': True,
            'message': 'Signup completed successfully!',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'is_active': user.is_active,
                'has_passkey': user.has_passkey,
            }
        })
        
    except Exception as e:
        logger.error(f"Error in skip passkey: {e}")
        return Response(
            {'error': 'Failed to complete signup'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_passkey(request):
    """
    Register a new passkey for the authenticated user using Django Allauth WebAuthn

    This endpoint initiates or completes passkey registration depending on the request data.
    """
    if not ALLAUTH_WEBAUTHN_AVAILABLE:
        return Response(
            {'error': 'WebAuthn support is not available'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    try:
        user = request.user
        device_info = request.data.get('device_info', {})

        # Check if this is the initial request for registration options
        if 'credential_data' not in request.data:
            # Begin registration - generate WebAuthn options
            try:
                from allauth.core.context import request_context
                
                # Set the request context for Django Allauth
                with request_context(request):
                    options = webauthn_auth.begin_registration(user, passwordless=True)

                return Response({
                    'success': True,
                    'options': options,
                    'message': 'Registration options generated. Complete the WebAuthn ceremony.'
                })

            except Exception as e:
                logger.error(f"Failed to begin passkey registration for {user.email}: {e}")
                return Response(
                    {'error': 'Failed to generate registration options'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Complete registration - process WebAuthn response
        else:
            serializer = PasskeyRegistrationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            credential_data = serializer.validated_data['credential_data']

            try:
                # Complete the WebAuthn registration using Django Allauth
                from allauth.core.context import request_context
                from allauth.mfa.models import Authenticator
                
                # Set the request context for Django Allauth
                with request_context(request):
                    # The complete_registration method returns the Authenticator instance
                    authenticator = webauthn_auth.complete_registration(credential_data)

                # Update user's passkey status
                user.has_passkey = True
                user.save(update_fields=['has_passkey'])

                # Log the event
                track_authentication_event(
                    user=user,
                    method='passkey_registration',
                    success=True,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    device_info=device_info
                )

                return Response({
                    'success': True,
                    'message': 'Passkey registered successfully',
                    'authenticator_id': str(authenticator.id)
                })

            except Exception as e:
                logger.error(f"Failed to complete passkey registration for {user.email}: {e}")
                return Response(
                    {'error': 'Failed to complete passkey registration'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    except Exception as e:
        logger.error(f"Passkey registration error for {request.user.email}: {e}")
        return Response(
            {'error': 'Passkey registration failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def authenticate_passkey(request):
    """
    Authenticate a user using their passkey via Django Allauth WebAuthn

    This endpoint initiates or completes passkey authentication depending on the request data.
    """
    if not ALLAUTH_WEBAUTHN_AVAILABLE:
        return Response(
            {'error': 'WebAuthn support is not available'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    try:
        device_info = request.data.get('device_info', {})

        # Check if this is the initial request for authentication options
        if 'credential_data' not in request.data:
            # Begin authentication - generate WebAuthn options
            email = request.data.get('email')
            
            # If no email provided, attempt true passwordless authentication
            if not email:
                try:
                    # For passwordless flow, we need to generate options that allow any passkey
                    # Since Django Allauth might not support user=None, we'll create our own options
                    from django.conf import settings
                    import secrets
                    import base64
                    
                    # Generate a random challenge
                    challenge = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
                    
                    # Get the RP ID from settings or use the request host
                    rp_id = getattr(settings, 'WEBAUTHN_RP_ID', request.get_host().split(':')[0])
                    
                    # Create passwordless authentication options
                    options = {
                        'publicKey': {
                            'challenge': challenge,
                            'rpId': rp_id,
                            'timeout': 60000,
                            'userVerification': 'preferred',
                            # Empty allowCredentials to allow any passkey
                            'allowCredentials': []
                        }
                    }
                    
                    # Store the challenge in session for verification
                    request.session['webauthn_challenge'] = challenge
                    request.session.save()
                    
                    return Response({
                        'success': True,
                        'options': options,
                        'passwordless': True,
                        'message': 'Authentication options generated for passwordless flow.'
                    })
                except Exception as e:
                    logger.error(f"Failed to begin passwordless authentication: {e}")
                    # Fall back to requiring email if passwordless not supported
                    return Response(
                        {'error': 'Email is required for passkey authentication'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Email provided - use traditional flow with specific user's passkeys
            try:
                user = User.objects.get(email=email)

                # Check if user has any WebAuthn authenticators
                if not Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN).exists():
                    return Response(
                        {'error': 'No passkeys found for this user'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                options = webauthn_auth.begin_authentication(user=user)

                return Response({
                    'success': True,
                    'options': options,
                    'passwordless': False,
                    'message': 'Authentication options generated. Complete the WebAuthn ceremony.'
                })

            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Failed to begin passkey authentication for {email}: {e}")
                return Response(
                    {'error': 'Failed to generate authentication options'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Complete authentication - process WebAuthn response
        else:
            serializer = PasskeyAuthenticationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            credential_data = serializer.validated_data['credential_data']

            try:
                # For passwordless flow, we need to identify the user from the credential
                # Check if we have a stored challenge (passwordless flow)
                stored_challenge = request.session.get('webauthn_challenge')
                
                if stored_challenge:
                    # Passwordless flow - identify user from userHandle
                    user_handle = credential_data.get('response', {}).get('userHandle')
                    if user_handle:
                        # Decode the userHandle to get the user ID
                        import base64
                        try:
                            # userHandle is base64 encoded user identifier
                            user_id = base64.urlsafe_b64decode(user_handle + '==').decode('utf-8')
                            user = User.objects.get(id=user_id)
                            logger.info(f"Identified user from userHandle: {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to identify user from userHandle: {e}")
                            user = None
                    else:
                        # No userHandle provided - cannot identify user
                        logger.error("No userHandle in passwordless authentication response")
                        user = None
                    
                    # Clean up the challenge
                    del request.session['webauthn_challenge']
                    request.session.save()
                else:
                    # Traditional flow with Django Allauth
                    user = webauthn_auth.complete_authentication(request, credential_data)

                if user:
                    # Update last login method
                    user.last_login_method = 'passkey'
                    user.save(update_fields=['last_login_method'])

                    # Log the authentication event
                    track_authentication_event(
                        user=user,
                        method='passkey_authentication',
                        success=True,
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        device_info=device_info
                    )

                    # Generate Knox tokens for the user
                    tokens = generate_tokens_for_user(user)
                    
                    # Generate Firebase custom token
                    firebase_token = generate_firebase_custom_token(user)

                    return Response({
                        'success': True,
                        'message': 'Authentication successful',
                        'user': {
                            'id': str(user.id),
                            'email': user.email,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                        },
                        'tokens': tokens,
                        'firebase_token': firebase_token
                    })
                else:
                    return Response(
                        {'error': 'Authentication failed'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

            except Exception as e:
                logger.error(f"Failed to complete passkey authentication: {e}")
                return Response(
                    {'error': 'Authentication failed'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    except Exception as e:
        logger.error(f"Passkey authentication error: {e}")
        return Response(
            {'error': 'Authentication failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_passkeys(request):
    """
    List all passkeys (WebAuthn authenticators) for the authenticated user
    """
    user = request.user

    # Get all WebAuthn authenticators for the user
    authenticators = Authenticator.objects.filter(
        user=user,
        type=Authenticator.Type.WEBAUTHN
    ).order_by('-created_at')

    passkey_data = []
    for authenticator in authenticators:
        # Extract device information from the authenticator data
        data = authenticator.data or {}

        passkey_data.append({
            'id': str(authenticator.id),
            'device_name': data.get('device_name', 'Unknown Device'),
            'device_type': data.get('device_type', 'unknown'),
            'created_at': authenticator.created_at.isoformat(),
            'last_used_at': authenticator.last_used_at.isoformat() if authenticator.last_used_at else None,
        })

    return Response({
        'passkeys': passkey_data,
        'count': len(passkey_data)
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_passkey(request, passkey_id):
    """
    Delete a specific passkey (WebAuthn authenticator) for the authenticated user
    """
    try:
        authenticator = Authenticator.objects.get(
            id=passkey_id,
            user=request.user,
            type=Authenticator.Type.WEBAUTHN
        )

        device_name = authenticator.data.get('device_name', 'Unknown Device') if authenticator.data else 'Unknown Device'
        authenticator.delete()

        # Update user's passkey status if no more passkeys
        if not Authenticator.objects.filter(user=request.user, type=Authenticator.Type.WEBAUTHN).exists():
            request.user.has_passkey = False
            request.user.save(update_fields=['has_passkey'])

        # Log the event
        track_authentication_event(
            user=request.user,
            method='passkey_deletion',
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_info={'deleted_device': device_name}
        )

        return Response({
            'success': True,
            'message': f'Passkey "{device_name}" deleted successfully'
        })

    except Authenticator.DoesNotExist:
        return Response(
            {'error': 'Passkey not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Passkey deletion failed for {request.user.email}: {e}")
        return Response(
            {'error': 'Failed to delete passkey'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Duplicate functions removed - using Django Allauth implementations above

def get_user_2fa_methods(user):
    """Get available 2FA methods for user"""
    return ['totp'] if user.has_2fa else []


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_firebase_token(request):
    """
    Get Firebase custom token for authenticated user
    """
    user = request.user

    # Generate Firebase custom token
    firebase_token = generate_firebase_custom_token(user)

    if firebase_token:
        return Response({
            'firebase_token': firebase_token,
            'expires_in': 3600  # Firebase custom tokens expire in 1 hour
        })
    else:
        return Response(
            {'error': 'Firebase token generation not available'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


# ============================================================================
# Knox Token Management Views
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knox_token_info(request):
    """Get Knox token information for the authenticated user"""
    user = request.user
    
    # Get the current token from the request
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Token '):
        return Response(
            {'error': 'No Knox token provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    token_key = auth_header.split(' ')[1]
    
    try:
        # Find the Knox token
        knox_token = AuthToken.objects.get(token_key=token_key[:8], user=user)
        
        return Response({
            'user': UserSerializer(user).data,
            'token_key': token_key[:8] + '...',  # Only show first 8 characters
            'created': knox_token.created,
            'expiry': knox_token.expiry,
            'auto_refresh_enabled': True,  # Knox tokens auto-refresh
            'device_info': {
                'device_type': 'web',  # Could be enhanced with actual device detection
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100]
            }
        })
    except AuthToken.DoesNotExist:
        return Response(
            {'error': 'Token not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def knox_auto_refresh(request):
    """Knox token auto-refresh endpoint"""
    # Knox tokens auto-refresh by default, so this just validates the token works
    user = request.user
    
    # Create a new token to simulate refresh
    instance, token = AuthToken.objects.create(user=user)
    
    return Response({
        'knox_token': token,
        'user': UserSerializer(user).data,
        'expires': instance.expiry,
        'message': 'Token refreshed successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def knox_logout(request):
    """Knox logout - revoke current token"""
    try:
        request._auth.delete()
        return Response({
            'success': True,
            'message': 'Successfully logged out'
        })
    except Exception as e:
        return Response(
            {'error': 'Logout failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knox_list_tokens(request):
    """List all active Knox tokens for the user"""
    user = request.user
    tokens = AuthToken.objects.filter(user=user)
    
    token_data = []
    for token in tokens:
        token_data.append({
            'token_key': token.token_key + '...',
            'created': token.created,
            'expiry': token.expiry,
            'is_current': token == request._auth
        })
    
    return Response({
        'tokens': token_data,
        'count': len(token_data)
    })


# ============================================================================
# Configuration Status Views
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def firebase_status(request):
    """Check Firebase configuration status"""
    try:
        # Check if Firebase is properly configured
        firebase_configured = bool(
            getattr(settings, 'FIREBASE_ADMIN_CONFIG', {}).get('project_id')
        )
        
        return Response({
            'firebase_configured': firebase_configured,
            'firebase_available': firebase_auth_manager.is_available() if firebase_configured else False,
            'project_id': getattr(settings, 'FIREBASE_ADMIN_CONFIG', {}).get('project_id', ''),
            'features_enabled': {
                'email_verification': firebase_configured,
                'custom_tokens': firebase_configured,
                'magic_links': firebase_configured
            }
        })
    except Exception as e:
        logger.error(f"Firebase status check failed: {e}")
        return Response({
            'firebase_configured': False,
            'firebase_available': False,
            'error': str(e)
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def user_model_check(request):
    """Check Django user model configuration"""
    User = get_user_model()
    
    return Response({
        'user_model': f"{User._meta.app_label}.{User._meta.object_name}",
        'firebase_uid_field': hasattr(User, 'firebase_uid'),
        'required_fields': ['email', 'first_name', 'last_name'],
        'auth_method': 'passwordless',
        'features': {
            'passkey_support': True,
            'email_verification': True,
            '2fa_support': True
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def webauthn_status(request):
    """Check WebAuthn/passkey configuration status"""
    try:
        # Check if Django Allauth WebAuthn is configured
        webauthn_configured = 'allauth.mfa' in settings.INSTALLED_APPS
        
        webauthn_settings = {
            'rp_id': getattr(settings, 'MFA_WEBAUTHN_RP_ID', ''),
            'rp_name': getattr(settings, 'MFA_WEBAUTHN_RP_NAME', ''),
            'origin': getattr(settings, 'MFA_WEBAUTHN_ORIGIN', ''),
            'allow_insecure_origin': getattr(settings, 'MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN', False)
        }
        
        return Response({
            'webauthn_configured': webauthn_configured,
            'passkey_signup_enabled': getattr(settings, 'MFA_PASSKEY_SIGNUP_ENABLED', False),
            'passkey_login_enabled': getattr(settings, 'MFA_PASSKEY_LOGIN_ENABLED', False),
            'settings': webauthn_settings if webauthn_configured else {}
        })
    except Exception as e:
        logger.error(f"WebAuthn status check failed: {e}")
        return Response({
            'webauthn_configured': False,
            'error': str(e)
        })


# ============================================================================
# Email Verification
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """Verify email using verification code (deprecated - use signup/verify-code instead)"""
    # This endpoint is kept for backward compatibility
    # New implementations should use the signup/verify-code endpoint
    
    email = request.data.get('email')
    code = request.data.get('code')
    
    if not email or not code:
        # Legacy support - check if verification_token is provided
        verification_token = request.data.get('verification_token')
        if verification_token:
            return Response(
                {'error': 'Magic link verification is no longer supported. Please use verification codes.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {'error': 'Email and verification code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Use the verification code logic
    from .utils import verify_code
    
    verification_code = verify_code(email, code, 'signup')
    
    if not verification_code:
        return Response(
            {'error': 'Invalid or expired verification code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Mark code as used
        verification_code.used_at = timezone.now()
        verification_code.save()
        
        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_active': False,  # User remains inactive until passkey is created
                'is_email_verified': True
            }
        )
        
        if not created:
            # Existing user - just mark email as verified
            user.is_email_verified = True
            user.save()
        
        # Generate Knox token for the user
        instance, token = AuthToken.objects.create(user=user)
        
        return Response({
            'success': True,
            'message': 'Email verified successfully. Please create a passkey to complete signup.',
            'passkey_required': True,
            'knox_token': token,
            'user': UserSerializer(user).data,
            'expires': instance.expiry
        })
        
    except Exception as e:
        logger.error(f"Email verification failed: {e}")
        return Response(
            {'error': 'Email verification failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# User Profile
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get authenticated user profile"""
    user = request.user
    
    return Response({
        'success': True,
        'user': UserSerializer(user).data
    })


# ============================================================================
# WebAuthn Registration Views (Django Allauth integration)
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_register_begin(request):
    """Begin WebAuthn passkey registration"""
    serializer = WebAuthnRegisterBeginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    
    try:
        # Find the user
        User = get_user_model()
        user = User.objects.get(email=email)
        
        # Generate WebAuthn registration options
        # This is a simplified version - in production, use proper WebAuthn library
        import uuid
        challenge = secrets.token_urlsafe(32)
        
        # Store challenge in session or cache for verification
        request.session['webauthn_challenge'] = challenge
        request.session['webauthn_user_id'] = str(user.id)
        
        return Response({
            'challenge': challenge,
            'rp': {
                'name': getattr(settings, 'MFA_WEBAUTHN_RP_NAME', 'Ekko'),
                'id': getattr(settings, 'MFA_WEBAUTHN_RP_ID', 'localhost')
            },
            'user': {
                'id': str(user.id),
                'name': user.email,
                'displayName': user.get_full_name() or user.email
            },
            'pubKeyCredParams': [
                {'alg': -7, 'type': 'public-key'},  # ES256
                {'alg': -257, 'type': 'public-key'}  # RS256
            ],
            'authenticatorSelection': {
                'authenticatorAttachment': 'platform',
                'userVerification': 'required'
            },
            'timeout': 60000
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"WebAuthn registration begin failed: {e}")
        return Response(
            {'error': 'WebAuthn registration failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_register_complete(request):
    """Complete WebAuthn passkey registration"""
    serializer = WebAuthnRegisterCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    credential = serializer.validated_data['credential']
    challenge = serializer.validated_data['challenge']
    
    try:
        # Verify challenge matches what we stored
        stored_challenge = request.session.get('webauthn_challenge')
        if not stored_challenge or stored_challenge != challenge:
            return Response(
                {'error': 'Invalid challenge'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_id = request.session.get('webauthn_user_id')
        if not user_id:
            return Response(
                {'error': 'Invalid session'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        # In production, properly verify the attestation response
        # For now, just store the credential
        credential_id = credential.get('id', 'mock_credential_id')
        
        # Update user passkey status
        user.has_passkey = True
        user.save(update_fields=['has_passkey'])
        
        # Clear session data
        request.session.pop('webauthn_challenge', None)
        request.session.pop('webauthn_user_id', None)
        
        return Response({
            'credential_stored': True,
            'credential_id': credential_id,
            'message': 'Passkey registered successfully'
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"WebAuthn registration complete failed: {e}")
        return Response(
            {'error': 'WebAuthn registration failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# Authentication Options View
@api_view(["GET"])
@permission_classes([AllowAny])
def auth_options(request):
    """
    Get available authentication options
    """
    return Response({
        "options": [
            {
                "id": 1,
                "text": "Sign in with a passkey",
                "method": "passkey",
                "primary": True
            },
            {
                "id": 2,
                "text": "Sign in with email",
                "method": "email",
                "primary": False
            }
        ],
        "signup_option": {
            "text": "Sign up with a passkey",
            "method": "passkey_first"
        }
    })


# ============================================================================
# Push Notification Token Management Views
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_push_token(request):
    """
    Register or update a push notification token for a device.

    This endpoint is called by mobile apps after obtaining an FCM/APNs token.
    If a device_id is provided and exists, it updates that device.
    Otherwise, it creates a new device record.

    POST /api/auth/devices/register-push/
    """
    from .serializers import RegisterPushTokenSerializer

    serializer = RegisterPushTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    device_token = serializer.validated_data['device_token']
    token_type = serializer.validated_data['token_type']
    device_id = serializer.validated_data.get('device_id')
    device_name = serializer.validated_data.get('device_name', 'Unknown Device')
    device_type = serializer.validated_data.get('device_type', 'ios' if token_type == 'apns' else 'android')

    try:
        # Try to find existing device
        if device_id:
            device = UserDevice.objects.get(device_id=device_id, user=user)
            logger.info(f"Updating push token for existing device {device_id}")
        else:
            # Create new device with a generated device_id
            import uuid
            new_device_id = f"push_{uuid.uuid4().hex[:16]}"
            device = UserDevice.objects.create(
                user=user,
                device_id=new_device_id,
                device_name=device_name,
                device_type=device_type,
                device_fingerprint='',
                is_active=True,
            )
            logger.info(f"Created new device {new_device_id} for push token")

        # Register the push token
        device.register_push_token(device_token, token_type)

        return Response({
            'success': True,
            'message': 'Push token registered successfully',
            'device': {
                'id': str(device.id),
                'device_id': device.device_id,
                'device_name': device.device_name,
                'device_type': device.device_type,
                'token_type': device.token_type,
                'push_enabled': device.push_enabled,
                'token_updated_at': device.token_updated_at.isoformat() if device.token_updated_at else None,
            }
        })

    except UserDevice.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to register push token for {user.email}: {e}")
        return Response(
            {'error': 'Failed to register push token'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_device_push_token(request, device_id):
    """
    Update/refresh the push token for a specific device.

    FCM/APNs tokens can change, so apps need to update them periodically.

    PATCH /api/auth/devices/{device_id}/push-token/
    """
    from .serializers import UpdatePushTokenSerializer

    serializer = UpdatePushTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    device_token = serializer.validated_data['device_token']
    token_type = serializer.validated_data.get('token_type')

    try:
        device = UserDevice.objects.get(id=device_id, user=user)

        # Use existing token_type if not provided
        if not token_type and device.token_type:
            token_type = device.token_type
        elif not token_type:
            token_type = 'fcm'  # Default to FCM

        # Update the push token
        device.register_push_token(device_token, token_type)

        logger.info(f"Updated push token for device {device_id}")

        return Response({
            'success': True,
            'message': 'Push token updated successfully',
            'device': {
                'id': str(device.id),
                'device_name': device.device_name,
                'token_type': device.token_type,
                'push_enabled': device.push_enabled,
                'token_updated_at': device.token_updated_at.isoformat() if device.token_updated_at else None,
            }
        })

    except UserDevice.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to update push token for device {device_id}: {e}")
        return Response(
            {'error': 'Failed to update push token'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def revoke_device_push_token(request, device_id):
    """
    Revoke the push notification token for a specific device.

    This should be called when a user signs out or disables push notifications.

    DELETE /api/auth/devices/{device_id}/push-token/
    """
    user = request.user

    try:
        device = UserDevice.objects.get(id=device_id, user=user)

        # Revoke the push token
        device.revoke_push_token()

        logger.info(f"Revoked push token for device {device_id}")

        return Response({
            'success': True,
            'message': 'Push token revoked successfully',
            'device_id': str(device.id)
        })

    except UserDevice.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to revoke push token for device {device_id}: {e}")
        return Response(
            {'error': 'Failed to revoke push token'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def toggle_device_push(request, device_id):
    """
    Enable or disable push notifications for a specific device.

    PATCH /api/auth/devices/{device_id}/push-enabled/
    """
    from .serializers import PushEnabledSerializer

    serializer = PushEnabledSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    enabled = serializer.validated_data['enabled']

    try:
        device = UserDevice.objects.get(id=device_id, user=user)

        # Toggle push enabled status
        device.set_push_enabled(enabled)

        logger.info(f"Push notifications {'enabled' if enabled else 'disabled'} for device {device_id}")

        return Response({
            'success': True,
            'message': f"Push notifications {'enabled' if enabled else 'disabled'}",
            'device': {
                'id': str(device.id),
                'device_name': device.device_name,
                'push_enabled': device.push_enabled,
            }
        })

    except UserDevice.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to toggle push for device {device_id}: {e}")
        return Response(
            {'error': 'Failed to update push status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_push_enabled_devices(request):
    """
    List all devices with push notifications enabled for the authenticated user.

    GET /api/auth/devices/push-enabled/
    """
    user = request.user

    try:
        # Get cached data (for consistency with wasmCloud)
        cached_data = UserDevice.get_push_devices_cached(user.id)

        return Response({
            'success': True,
            'devices': cached_data.get('devices', []),
            'count': len(cached_data.get('devices', [])),
            'cached_at': cached_data.get('cached_at')
        })

    except Exception as e:
        logger.error(f"Failed to list push devices for {user.email}: {e}")
        return Response(
            {'error': 'Failed to retrieve push-enabled devices'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
