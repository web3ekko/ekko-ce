"""
Verification Code Authentication Views

Implements the new authentication flows with 6-digit verification codes
instead of magic links.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from knox.models import AuthToken

from .views import generate_tokens_for_user
from .models import EmailVerificationCode
from .serializers import (
    CheckAccountStatusSerializer,
    SignupWithCodeSerializer,
    VerifyCodeSerializer,
    SigninEmailCodeSerializer,
    ResendCodeSerializer,
    RecoveryRequestSerializer,
    UserSerializer,
)
from .utils import (
    create_verification_code,
    send_verification_code_email,
    verify_code,
    invalidate_previous_codes,
    is_rate_limited,
    increment_rate_limit,
    get_device_info,
    track_user_device,
    track_authentication_event,
)
from .firebase_utils import firebase_auth_manager

User = get_user_model()
logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def check_account_status(request):
    """
    Check if an account exists and its status
    Returns: no_account, inactive_account, or active_account
    """
    serializer = CheckAccountStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    
    try:
        user = User.objects.get(email=email)
        if user.is_active:
            status = 'active_account'
        else:
            status = 'inactive_account'
    except User.DoesNotExist:
        status = 'no_account'
    
    return Response({
        'status': status,
        'exists': status != 'no_account',  # Backward compatibility
        'message': {
            'no_account': 'No account found',
            'inactive_account': 'Account exists but is not active',
            'active_account': 'Active account exists'
        }.get(status, 'Unknown status')
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_verify_code(request):
    """
    Verify the 6-digit code sent during signup
    """
    serializer = VerifyCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']

    # Verify the code
    verification_code, error_reason = verify_code(email, code, 'signup')

    if not verification_code:
        error_messages = {
            'not_found': 'Invalid code. Please check and try again.',
            'expired': 'Code has expired. Please request a new one.',
            'used': 'This code has already been used. Please request a new one.',
        }
        return Response({
            'error': error_messages.get(error_reason, 'Invalid code'),
            'error_code': error_reason
        }, status=status.HTTP_400_BAD_REQUEST)
    
    
    try:
        # Mark code as used
        verification_code.used_at = timezone.now()
        verification_code.save()
        
        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_active': True,  # Activate user after email verification
                'is_email_verified': True
            }
        )
        
        logger.info(f"User get_or_create result - email: {email}, created: {created}, is_active: {user.is_active}")
        
        if not created:
            # Existing user - mark email as verified and activate
            logger.info(f"Existing user found: {user.email}, is_active before: {user.is_active}")
            user.is_active = True  # Activate user after email verification
            user.is_email_verified = True  # Don't check hasattr, just set it
            user.save(update_fields=['is_active', 'is_email_verified'])
            logger.info(f"User saved with is_active=True, calling refresh_from_db...")
            # Refresh from DB to ensure we have the latest data
            user.refresh_from_db()
            logger.info(f"User after refresh: {user.email}, is_active: {user.is_active}")
            
            # Double-check by querying directly
            db_user = User.objects.get(pk=user.pk)
            logger.info(f"Direct DB query - user: {db_user.email}, is_active: {db_user.is_active}")
        else:
            logger.info(f"New user created: {user.email}, is_active: {user.is_active}")
        
        # Create Knox token for authenticated session (even for inactive users)
        # This allows them to complete passkey registration
        # Use generate_tokens_for_user to ensure token is cached in Redis for WebSocket provider
        tokens = generate_tokens_for_user(user)
        token_key = tokens['knox_token']
        
        # Ensure we have the latest user state
        user.refresh_from_db()
        
        # Log final user state before response
        logger.info(f"Final user state before response - email: {user.email}, is_active: {user.is_active}, is_email_verified: {user.is_email_verified}")
        
        # Return success - user must now create passkey
        return Response({
            'success': True,
            'message': 'Email verified! Please create a passkey to complete signup.',
            'passkey_required': True,
            'next_step': 'create_passkey',
            'token': token_key,  # Include token for authenticated passkey registration
            'user': UserSerializer(user).data,
            'is_active': user.is_active  # This should now be True
        })
        
    except Exception as e:
        logger.error(f"Error in signup verification: {e}")
        return Response({
            'error': 'Verification failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def signup_complete_dev(request):
    """
    Complete signup without passkey in development mode
    Only available when DEBUG=True and for users who have verified their email
    """
    from django.conf import settings
    
    if not settings.DEBUG:
        return Response({
            'error': 'This endpoint is only available in development mode'
        }, status=status.HTTP_403_FORBIDDEN)
    
    user = request.user
    
    # Check if user has verified email but is not active
    if not hasattr(user, 'is_email_verified') or not user.is_email_verified:
        return Response({
            'error': 'Email not verified'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if user.is_active:
        return Response({
            'error': 'Account already active'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Activate user without passkey in dev mode
    user.is_active = True
    user.save()
    
    logger.info(f"🚀 Dev mode: Account activated without passkey for: {user.email}")
    
    # Return user data
    return Response({
        'success': True,
        'message': 'Account activated successfully (dev mode)',
        'user': UserSerializer(user).data,
        'token': request.auth.token_key if hasattr(request.auth, 'token_key') else None
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_passkey_begin(request):
    """
    Begin passkey authentication - no email needed
    """
    # WebAuthn conditional UI doesn't require email
    # This would integrate with Django Allauth WebAuthn
    
    return Response({
        'challenge': 'mock_challenge_for_webauthn',
        'timeout': 60000,
        'rpId': 'localhost',
        'userVerification': 'required',
        'message': 'Use your passkey to sign in'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_passkey_complete(request):
    """
    Complete passkey authentication
    """
    credential_id = request.data.get('credentialId')
    client_data = request.data.get('clientDataJSON')
    authenticator_data = request.data.get('authenticatorData')
    signature = request.data.get('signature')
    user_handle = request.data.get('userHandle')
    
    if not all([credential_id, client_data, authenticator_data, signature]):
        return Response({
            'error': 'Missing required passkey data'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # For now, we need to implement proper WebAuthn verification
        # This would involve:
        # 1. Verifying the signature against the challenge
        # 2. Finding the user by credential_id
        # 3. Validating the authenticator data
        
        # TODO: Integrate with Django Allauth MFA WebAuthn properly
        # For now, return an informative error
        logger.info("Passkey authentication attempted but WebAuthn integration pending")
        
        return Response({
            'error': 'Passkey authentication is being implemented. Please use email authentication for now.',
            'fallback': 'email'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)
        
    except Exception as e:
        logger.error(f"Passkey authentication error: {e}")
        return Response({
            'error': 'Passkey authentication failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_email_send_code(request):
    """
    Send verification code for email sign-in
    """
    from django.conf import settings as django_settings

    serializer = SigninEmailCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    device_info = get_device_info(request)

    # Check rate limiting
    if is_rate_limited(f'signin:{email}', max_attempts=5, window_minutes=15):
        return Response({
            'error': 'Too many sign-in attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Increment rate limit counter
    increment_rate_limit(f'signin:{email}', window_minutes=15)

    # Invalidate previous codes
    invalidate_previous_codes(email, 'signin')

    # Create new code
    code = create_verification_code(
        email=email,
        purpose='signin',
        ip_address=device_info['ip_address'],
        user_agent=device_info['user_agent'],
        user=User.objects.get(email=email)
    )

    # Send code via email (handle errors gracefully in dev mode)
    try:
        send_verification_code_email(email, code.code, 'signin')
        logger.info(f"Sign-in code sent to {email}")
    except Exception as e:
        if django_settings.DEBUG:
            # In development, log the code and continue
            logger.warning(f"Email sending failed (dev mode): {e}")
            logger.info(f"🔑 DEV MODE - Verification code for {email}: {code.code}")
        else:
            # In production, raise the error
            raise

    return Response({
        'success': True,
        'message': 'Enter the code we sent to your email'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signin_email_verify_code(request):
    """
    Verify code and complete email sign-in
    """
    serializer = VerifyCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    device_info = get_device_info(request)

    # Verify the code
    verification_code, error_reason = verify_code(email, code, 'signin')

    if not verification_code:
        # Try to find the most recent code for this email to track attempts
        recent_code = EmailVerificationCode.objects.filter(
            email=email,
            purpose='signin',
            used_at__isnull=True
        ).order_by('-created_at').first()

        if recent_code:
            recent_code.attempts += 1
            recent_code.save(update_fields=['attempts'])

            if recent_code.attempts >= 3:
                return Response({
                    'error': 'Too many verification attempts. Please request a new code.',
                    'error_code': 'max_attempts'
                }, status=status.HTTP_400_BAD_REQUEST)

        error_messages = {
            'not_found': 'Invalid code. Please check and try again.',
            'expired': 'Code has expired. Please request a new one.',
            'used': 'This code has already been used. Please request a new one.',
        }
        return Response({
            'error': error_messages.get(error_reason, 'Invalid code'),
            'error_code': error_reason
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Mark code as used
        verification_code.used_at = timezone.now()
        verification_code.save()
        
        # Get user
        user = User.objects.get(email=email, is_active=True)
        
        # Track device
        device = track_user_device(user, device_info, request)

        # Generate Knox token and cache to Redis for WebSocket provider
        tokens = generate_tokens_for_user(user)
        token_key = tokens['knox_token']
        
        # Track successful authentication
        track_authentication_event(
            user=user,
            method='email_code',
            success=True,
            ip_address=device_info['ip_address'],
            user_agent=device_info['user_agent'],
            device_info=device_info
        )
        
        # Check if user has passkey
        prompt_passkey = False
        if hasattr(user, 'has_passkey'):
            prompt_passkey = not user.has_passkey
        
        return Response({
            'success': True,
            'token': token_key,
            'user': UserSerializer(user).data,
            'prompt_passkey': prompt_passkey,
            'message': 'Signed in successfully'
        })
        
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_code(request):
    """
    Resend verification code
    """
    serializer = ResendCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    purpose = serializer.validated_data['purpose']
    device_info = get_device_info(request)
    
    # Check rate limiting based on purpose
    if purpose == 'signup':
        rate_limit_key = f'signup:{email}'
        max_attempts = 3
        window = 3600  # 1 hour
    elif purpose == 'signin':
        rate_limit_key = f'signin:{email}'
        max_attempts = 5
        window = 900  # 15 minutes
    else:  # recovery
        rate_limit_key = f'recovery:{email}'
        max_attempts = 3
        window = 3600  # 1 hour
    
    if is_rate_limited(rate_limit_key, max_attempts=max_attempts, window_minutes=window//60):
        return Response({
            'error': 'Too many resend attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Increment rate limit
    increment_rate_limit(rate_limit_key, window_minutes=window//60)
    
    # Invalidate previous codes
    invalidate_previous_codes(email, purpose)
    
    # Get user if exists
    user = None
    if purpose != 'signup':
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if account exists for recovery
            if purpose == 'recovery':
                return Response({
                    'success': True,
                    'message': 'If an account exists, a code will be sent'
                })
            else:
                return Response({
                    'error': 'Account not found'
                }, status=status.HTTP_404_NOT_FOUND)
    
    # Create new code
    code = create_verification_code(
        email=email,
        purpose=purpose,
        ip_address=device_info['ip_address'],
        user_agent=device_info['user_agent'],
        user=user
    )

    # Send code (handle errors gracefully in dev mode)
    from django.conf import settings as django_settings
    try:
        send_verification_code_email(email, code.code, purpose)
    except Exception as e:
        if django_settings.DEBUG:
            logger.warning(f"Email sending failed (dev mode): {e}")
            logger.info(f"🔑 DEV MODE - Verification code for {email}: {code.code}")
        else:
            raise

    return Response({
        'success': True,
        'message': 'New code sent!'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def recovery_request(request):
    """
    Request account recovery
    """
    serializer = RecoveryRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    device_info = get_device_info(request)
    
    # Check rate limiting
    if is_rate_limited(f'recovery:{email}', max_attempts=3, window_minutes=60):
        return Response({
            'error': 'Too many recovery attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Don't reveal if account exists
    response_message = 'Check your email for recovery code'
    
    try:
        user = User.objects.get(email=email)
        
        # Increment rate limit
        increment_rate_limit(f'recovery:{email}', window_minutes=60)
        
        # Invalidate previous codes
        invalidate_previous_codes(email, 'recovery')
        
        # Create recovery code
        code = create_verification_code(
            email=email,
            purpose='recovery',
            ip_address=device_info['ip_address'],
            user_agent=device_info['user_agent'],
            user=user
        )

        # Send recovery code (handle errors gracefully in dev mode)
        from django.conf import settings as django_settings
        try:
            send_verification_code_email(email, code.code, 'recovery')
            logger.info(f"Recovery code sent to {email}")
        except Exception as e:
            if django_settings.DEBUG:
                logger.warning(f"Email sending failed (dev mode): {e}")
                logger.info(f"🔑 DEV MODE - Recovery code for {email}: {code.code}")
            else:
                raise
        
    except User.DoesNotExist:
        # Don't reveal account doesn't exist
        logger.info(f"Recovery requested for non-existent account: {email}")
    
    return Response({
        'success': True,
        'message': response_message
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def recovery_verify_code(request):
    """
    Verify recovery code and prepare for passkey reset
    """
    serializer = VerifyCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    code = serializer.validated_data['code']

    # Verify the code
    verification_code, error_reason = verify_code(email, code, 'recovery')

    if not verification_code:
        error_messages = {
            'not_found': 'Invalid code. Please check and try again.',
            'expired': 'Code has expired. Please request a new one.',
            'used': 'This code has already been used. Please request a new one.',
        }
        return Response({
            'error': error_messages.get(error_reason, 'Invalid code'),
            'error_code': error_reason
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Mark code as used
        verification_code.used_at = timezone.now()
        verification_code.save()

        # Get user
        user = User.objects.get(email=email)

        # Revoke all Knox tokens
        user.auth_token_set.all().delete()

        logger.info(f"Account recovery verified for {email}, all tokens revoked")

        # User must now create new passkey
        return Response({
            'success': True,
            'message': 'Account verified',
            'passkey_required': True,
            'next_step': 'create_new_passkey'
        })

    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_token(request):
    """
    Validate Knox token and return user info.

    Used by frontend to check if stored token is still valid on app startup
    and before protected route access. Returns 401 if token is invalid/expired.
    """
    user = request.user
    return Response({
        'valid': True,
        'user': {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_email_verified': getattr(user, 'is_email_verified', False),
            'has_passkey': getattr(user, 'has_passkey', False),
        }
    })


