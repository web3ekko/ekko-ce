import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from knox.models import AuthToken

from .serializers import (
    PasskeyDeviceSerializer,
    PasskeyRegistrationBeginSerializer,
    PasskeyRegistrationCompleteSerializer,
    PasskeyAuthenticationBeginSerializer,
    PasskeyAuthenticationCompleteSerializer,
    UserSerializer,
)
from .services import WebAuthnService
from .models import PasskeyDevice

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def passkey_register_begin(request):
    """
    Begin passkey registration for authenticated user.
    """
    serializer = PasskeyRegistrationBeginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        service = WebAuthnService()
        platform_only = serializer.validated_data.get('platform_only', False)
        options = service.generate_registration_options(
            user=request.user,
            platform_only=platform_only
        )
        
        # Log what we're sending for debugging
        logger.info(f"Generated registration options for user {request.user.email}")
        logger.info(f"RP ID: {options['publicKey']['rp']['id']}")
        logger.info(f"Platform only: {platform_only}")
        logger.info(f"Authenticator selection: {options['publicKey'].get('authenticatorSelection', {})}")
        
        return Response({
            'options': options,
            'success': True
        })
    except Exception as e:
        logger.error(f"Failed to generate registration options: {e}")
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def passkey_register_complete(request):
    """
    Complete passkey registration for authenticated user.
    """
    logger.debug(f"Received registration completion request from user: {request.user.email}")
    logger.debug(f"Request data type: {type(request.data)}")
    logger.debug(f"Request data: {request.data}")
    
    serializer = PasskeyRegistrationCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Serializer validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    logger.debug(f"Serializer validated data: {serializer.validated_data}")
    
    try:
        service = WebAuthnService()
        device = service.complete_registration(
            user=request.user,
            credential_data=serializer.validated_data['credential_data'],
            device_name=serializer.validated_data.get('device_name')
        )
        
        logger.info(f"Registered passkey device {device.id} for user {request.user.email}")
        
        return Response({
            'success': True,
            'device': PasskeyDeviceSerializer(device).data,
            'message': 'Passkey registered successfully'
        })
    except Exception as e:
        logger.error(f"Failed to complete registration: {e}")
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def passkey_authenticate_begin(request):
    """
    Begin passkey authentication.
    Supports both email-based and passwordless flows.
    """
    serializer = PasskeyAuthenticationBeginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data.get('email')
    user = None
    passwordless = not bool(email)
    
    try:
        if email:
            # Email-based flow
            try:
                user = User.objects.get(email=email)
                # Check if user has any passkeys
                if not user.passkey_devices.filter(is_active=True).exists():
                    return Response({
                        'error': 'No passkeys registered for this account',
                        'success': False
                    }, status=status.HTTP_404_NOT_FOUND)
            except User.DoesNotExist:
                return Response({
                    'error': 'No account found with this email',
                    'success': False
                }, status=status.HTTP_404_NOT_FOUND)
        
        service = WebAuthnService()
        options = service.generate_authentication_options(
            user=user,
            passwordless=passwordless
        )
        
        logger.info(f"Generated authentication options (passwordless={passwordless})")
        return Response({
            'options': options,
            'success': True,
            'passwordless': passwordless
        })
    except Exception as e:
        logger.error(f"Failed to generate authentication options: {e}")
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def passkey_authenticate_complete(request):
    """
    Complete passkey authentication and issue tokens.
    """
    serializer = PasskeyAuthenticationCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        service = WebAuthnService()
        user, device = service.complete_authentication(
            credential_data=serializer.validated_data['credential_data']
        )
        
        # Create Knox token
        _, token = AuthToken.objects.create(user)
        
        logger.info(f"Successful authentication for user {user.email} with device {device.id}")
        
        return Response({
            'success': True,
            'user': UserSerializer(user).data,
            'token': token,
            'tokens': {
                'access': token,
                'refresh': token  # Knox uses same token
            },
            'device': PasskeyDeviceSerializer(device).data,
            'message': 'Authentication successful'
        })
    except Exception as e:
        logger.error(f"Failed to complete authentication: {e}")
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_passkey_devices(request):
    """
    List all passkey devices for the authenticated user.
    """
    devices = request.user.passkey_devices.filter(is_active=True)
    serializer = PasskeyDeviceSerializer(devices, many=True)
    
    return Response({
        'success': True,
        'devices': serializer.data
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_passkey_device(request, device_id):
    """
    Delete (deactivate) a passkey device.
    """
    try:
        device = request.user.passkey_devices.get(id=device_id, is_active=True)
        device.is_active = False
        device.save()
        
        logger.info(f"Deactivated passkey device {device_id} for user {request.user.email}")
        
        return Response({
            'success': True,
            'message': 'Passkey removed successfully'
        })
    except PasskeyDevice.DoesNotExist:
        return Response({
            'error': 'Device not found',
            'success': False
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_passkey_device(request, device_id):
    """
    Update passkey device name.
    """
    try:
        device = request.user.passkey_devices.get(id=device_id, is_active=True)
        
        name = request.data.get('name', '').strip()
        if name:
            device.name = name
            device.save()
            
            logger.info(f"Updated passkey device {device_id} name for user {request.user.email}")
            
            return Response({
                'success': True,
                'device': PasskeyDeviceSerializer(device).data
            })
        else:
            return Response({
                'error': 'Name is required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PasskeyDevice.DoesNotExist:
        return Response({
            'error': 'Device not found',
            'success': False
        }, status=status.HTTP_404_NOT_FOUND)