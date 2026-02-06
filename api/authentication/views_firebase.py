"""
Firebase Token Exchange Views

Handles exchanging Firebase ID tokens for Django JWT tokens,
enabling unified authentication between Firebase UI and Django Allauth.
"""

import logging
from typing import Dict, Any

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .firebase_utils import firebase_auth_manager
# UserSession model removed - using Knox tokens instead
from .utils import track_user_device

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_token_exchange(request):
    """
    Exchange Firebase ID token for Django JWT tokens
    
    This endpoint allows the dashboard to authenticate users via Firebase UI
    and receive Django JWT tokens for API access.
    
    Request:
        {
            "firebase_token": "firebase_id_token_here",
            "device_info": {
                "device_type": "web",
                "platform": "Chrome",
                "user_agent": "...",
                "webauthn_supported": true
            }
        }
    
    Response:
        {
            "access_token": "jwt_access_token",
            "refresh_token": "jwt_refresh_token",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_email_verified": true,
                "preferred_auth_method": "email"
            },
            "session": {
                "session_id": "uuid",
                "device_trusted": false,
                "expires_at": "2025-08-15T10:30:00Z"
            }
        }
    """
    try:
        # Validate request data
        firebase_token = request.data.get('firebase_token')
        device_info = request.data.get('device_info', {})
        
        if not firebase_token:
            return Response(
                {'error': 'Firebase token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if Firebase is available
        if not firebase_auth_manager.is_available():
            return Response(
                {'error': 'Firebase authentication is not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Verify Firebase ID token
        try:
            decoded_token = firebase_auth_manager.verify_id_token(firebase_token)
        except Exception as e:
            logger.error(f"Firebase token verification failed: {e}")
            return Response(
                {'error': 'Invalid Firebase token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Extract user information from Firebase token
        firebase_uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        email_verified = decoded_token.get('email_verified', False)
        name = decoded_token.get('name', '')
        
        if not email:
            return Response(
                {'error': 'Email not found in Firebase token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse name into first_name and last_name
        name_parts = name.split(' ', 1) if name else ['', '']
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Get or create Django user
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,  # Set username to email
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_email_verified': email_verified,
                    'preferred_auth_method': 'email',
                    'firebase_uid': firebase_uid,  # Store Firebase UID for future reference
                }
            )
            
            # Update user information if they already exist
            if not created:
                updated = False
                if not user.firebase_uid:
                    user.firebase_uid = firebase_uid
                    updated = True
                if not user.is_email_verified and email_verified:
                    user.is_email_verified = email_verified
                    updated = True
                if not user.first_name and first_name:
                    user.first_name = first_name
                    updated = True
                if not user.last_name and last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    user.save()
            
            # Track device
            device = track_user_device(user, device_info, request)
            
            # Generate Django JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            # Prepare response data
            response_data = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_email_verified': user.is_email_verified,
                    'preferred_auth_method': user.preferred_auth_method,
                    'firebase_uid': user.firebase_uid,
                },
                'auth_method': 'firebase',
                'device_trusted': device.is_trusted if device else False,
            }
            
            logger.info(f"Firebase token exchange successful for user: {email}")
            return Response(response_data, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Firebase token exchange error: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_custom_token(request):
    """
    Generate Firebase custom token for authenticated Django users
    
    This endpoint allows Django-authenticated users to get Firebase custom tokens
    for client-side Firebase features.
    
    Request:
        {
            "user_id": 123  # Optional, defaults to current user
        }
    
    Response:
        {
            "custom_token": "firebase_custom_token_here",
            "expires_in": 3600
        }
    """
    try:
        # Check if Firebase is available
        if not firebase_auth_manager.is_available():
            return Response(
                {'error': 'Firebase authentication is not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Get user (from JWT token or request data)
        user = request.user if request.user.is_authenticated else None
        user_id = request.data.get('user_id')
        
        if user_id and not user:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate Firebase custom token
        try:
            # Use Firebase UID if available, otherwise use Django user ID
            firebase_uid = getattr(user, 'firebase_uid', None) or str(user.id)
            
            # Additional claims for the custom token
            additional_claims = {
                'django_user_id': user.id,
                'email': user.email,
                'email_verified': user.is_email_verified,
            }
            
            custom_token = firebase_auth_manager.create_custom_token(
                firebase_uid, 
                additional_claims
            )
            
            return Response({
                'custom_token': custom_token.decode('utf-8'),
                'expires_in': 3600,  # 1 hour
                'firebase_uid': firebase_uid,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Firebase custom token generation failed: {e}")
            return Response(
                {'error': 'Failed to generate Firebase token'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Firebase custom token error: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def firebase_config(request):
    """
    Get Firebase web configuration for frontend
    
    Response:
        {
            "config": {
                "apiKey": "...",
                "authDomain": "...",
                "projectId": "..."
            },
            "available": true
        }
    """
    try:
        from django.conf import settings
        
        firebase_web_config = getattr(settings, 'FIREBASE_WEB_CONFIG', {})
        firebase_available = firebase_auth_manager.is_available()
        
        return Response({
            'config': firebase_web_config,
            'available': firebase_available,
            'features': {
                'email_link': True,
                'email_password': True,
                'google_signin': bool(firebase_web_config.get('apiKey')),
                'custom_tokens': firebase_available,
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Firebase config error: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
