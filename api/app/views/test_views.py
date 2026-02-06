"""
Test-Only Views for E2E Testing Support

These endpoints are ONLY available when DEBUG=True and provide utilities
for E2E tests to access verification codes and other test-related data.

WARNING: These endpoints should NEVER be exposed in production.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from authentication.models import EmailVerificationCode
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_verification_code(request):
    """
    Test-only endpoint to retrieve verification codes (DEBUG mode only).

    This endpoint allows E2E tests to retrieve valid verification codes
    without needing to parse API logs or use hardcoded fallback codes.

    Query Parameters:
        email (required): The email address to get the verification code for
        purpose (optional): The verification purpose ('signup', 'signin', 'recovery')
                           Defaults to 'signup'

    Returns:
        200: { "code": "123456", "expires_at": "2024-01-01T00:00:00Z" }
        400: { "error": "email parameter required" }
        403: { "error": "Not available in production" }
        404: { "code": null, "error": "No valid code found" }

    Usage in E2E tests:
        response = requests.get(
            f"{api_url}/api/test/verification-code/",
            params={'email': 'test@example.com', 'purpose': 'signup'}
        )
        code = response.json()['code']
    """
    # Security: Only available in DEBUG mode
    if not settings.DEBUG:
        logger.warning(
            "Attempted to access test verification endpoint in production mode"
        )
        return Response(
            {'error': 'Not available in production'},
            status=status.HTTP_403_FORBIDDEN
        )

    email = request.query_params.get('email')
    purpose = request.query_params.get('purpose', 'signup')

    if not email:
        return Response(
            {'error': 'email parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate purpose
    valid_purposes = ['signup', 'signin', 'recovery']
    if purpose not in valid_purposes:
        return Response(
            {'error': f'Invalid purpose. Must be one of: {valid_purposes}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find the most recent valid (unused, unexpired) code
    code = EmailVerificationCode.objects.filter(
        email__iexact=email,
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=timezone.now()
    ).order_by('-created_at').first()

    if code:
        logger.debug(
            f"[E2E Test] Returning verification code for {email} (purpose: {purpose})"
        )
        return Response({
            'code': code.code,
            'expires_at': code.expires_at.isoformat(),
            'purpose': code.purpose,
            'created_at': code.created_at.isoformat()
        })

    logger.debug(
        f"[E2E Test] No valid verification code found for {email} (purpose: {purpose})"
    )
    return Response(
        {'code': None, 'error': 'No valid code found'},
        status=status.HTTP_404_NOT_FOUND
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Simple health check endpoint for test utilities.

    Returns:
        200: { "status": "ok", "debug_mode": true/false }
    """
    return Response({
        'status': 'ok',
        'debug_mode': settings.DEBUG,
        'test_endpoints_available': settings.DEBUG
    })
