"""
Profile Views for User Profile Management API

Provides endpoints for:
- Profile viewing and editing
- Preferences management
- Session management
- Data export
- Account deletion
"""

import uuid
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import get_user_model
from django.utils import timezone
from knox.models import AuthToken

from ..serializers.profile_serializers import (
    ProfileSerializer, ProfileUpdateSerializer, PreferencesSerializer,
    ConnectedServiceSerializer, SessionSerializer,
    ExportRequestSerializer, ExportResponseSerializer,
    DeleteAccountSerializer
)
from authentication.models import UserDevice

User = get_user_model()


class ProfileView(APIView):
    """
    GET: Get current user's profile
    PATCH: Update current user's profile
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get the authenticated user's profile"""
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update the authenticated user's profile"""
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            # Return full profile after update
            return Response(ProfileSerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PreferencesView(APIView):
    """
    GET: Get user preferences
    PATCH: Update user preferences
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get user preferences"""
        user = request.user
        preferences = {
            'preferred_auth_method': user.preferred_auth_method,
            'notification_preferences': {},  # TODO: Load from notification settings
            'theme': 'system',  # TODO: Store in user profile or separate table
            'timezone': 'UTC',
            'language': 'en',
        }
        serializer = PreferencesSerializer(preferences)
        return Response(serializer.data)

    def patch(self, request):
        """Update user preferences"""
        serializer = PreferencesSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            user = request.user
            data = serializer.validated_data

            # Update auth method if provided
            if 'preferred_auth_method' in data:
                user.preferred_auth_method = data['preferred_auth_method']
                user.save(update_fields=['preferred_auth_method'])

            # TODO: Store other preferences (theme, timezone, language)

            return Response({
                'message': 'Preferences updated successfully',
                'preferences': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AvatarView(APIView):
    """
    POST: Upload user avatar
    DELETE: Remove user avatar
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Upload a new avatar"""
        # TODO: Implement avatar upload with proper storage
        # For now, return a placeholder response
        return Response({
            'message': 'Avatar upload not yet implemented',
            'avatar_url': None
        }, status=status.HTTP_501_NOT_IMPLEMENTED)

    def delete(self, request):
        """Remove user avatar"""
        # TODO: Implement avatar deletion
        return Response({
            'message': 'Avatar removed successfully'
        })


class ConnectedServicesView(APIView):
    """
    GET: List connected services/devices
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List user's connected services and devices"""
        user = request.user
        services = []

        # Get devices from UserDevice model
        devices = UserDevice.objects.filter(user=user, is_active=True)
        for device in devices:
            services.append({
                'id': device.id,
                'service_type': 'device',
                'name': device.device_name,
                'connected_at': device.created_at,
                'last_used': device.last_used,
                'is_active': device.is_active,
            })

        # Check for Firebase connection
        if user.firebase_uid:
            services.append({
                'id': str(uuid.uuid4()),  # Placeholder
                'service_type': 'firebase',
                'name': 'Firebase Authentication',
                'connected_at': user.created_at,
                'last_used': user.updated_at,
                'is_active': True,
            })

        serializer = ConnectedServiceSerializer(services, many=True)
        return Response(serializer.data)


class ConnectedServiceDetailView(APIView):
    """
    DELETE: Disconnect a specific service
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, service_id):
        """Disconnect a service"""
        user = request.user

        # Try to find and delete the device
        try:
            device = UserDevice.objects.get(id=service_id, user=user)
            device.is_active = False
            device.save(update_fields=['is_active'])
            return Response({'message': 'Service disconnected successfully'})
        except UserDevice.DoesNotExist:
            return Response(
                {'error': 'Service not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class SessionsView(APIView):
    """
    GET: List active sessions
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List user's active sessions (Knox tokens)"""
        user = request.user
        sessions = []

        # Get current token from request
        current_token = request.auth

        # Get all auth tokens for user
        tokens = AuthToken.objects.filter(user=user)
        for token in tokens:
            # Check if token is expired
            if token.expiry and token.expiry < timezone.now():
                continue

            sessions.append({
                'id': token.digest[:16],  # Use first 16 chars of digest as ID
                'device_info': 'Unknown Device',  # Knox doesn't store device info by default
                'ip_address': '0.0.0.0',  # Would need to store this separately
                'created_at': token.created,
                'last_used': token.created,  # Knox doesn't track last used
                'expires_at': token.expiry,
                'is_current': current_token and token.digest == current_token.digest if hasattr(current_token, 'digest') else False,
            })

        serializer = SessionSerializer(sessions, many=True)
        return Response(serializer.data)


class SessionDetailView(APIView):
    """
    DELETE: Revoke a specific session
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, session_id):
        """Revoke a specific session"""
        user = request.user

        # Find token by digest prefix
        try:
            token = AuthToken.objects.get(
                user=user,
                digest__startswith=session_id
            )
            token.delete()
            return Response({'message': 'Session revoked successfully'})
        except AuthToken.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class RevokeAllSessionsView(APIView):
    """
    POST: Revoke all sessions except current
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Revoke all sessions except the current one"""
        user = request.user
        current_token = request.auth

        # Delete all tokens except current
        tokens = AuthToken.objects.filter(user=user)
        revoked_count = 0

        for token in tokens:
            # Skip current token if we can identify it
            if current_token and hasattr(current_token, 'digest'):
                if token.digest == current_token.digest:
                    continue
            token.delete()
            revoked_count += 1

        return Response({
            'message': f'Revoked {revoked_count} session(s)',
            'revoked_count': revoked_count
        })


class ExportDataView(APIView):
    """
    POST: Request data export
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Request a data export"""
        serializer = ExportRequestSerializer(data=request.data)
        if serializer.is_valid():
            # TODO: Implement async data export job
            # For now, return a placeholder response
            export_id = uuid.uuid4()
            response_data = {
                'export_id': export_id,
                'status': 'pending',
                'download_url': None,
                'expires_at': timezone.now() + timezone.timedelta(days=7),
                'message': 'Data export has been queued. You will receive an email when it is ready.'
            }
            response_serializer = ExportResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteAccountView(APIView):
    """
    POST: Delete user account
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Delete the user's account"""
        serializer = DeleteAccountSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user

            # Soft delete or hard delete depending on requirements
            # For now, we'll deactivate the account
            user.is_active = False
            user.save(update_fields=['is_active'])

            # Delete all auth tokens
            AuthToken.objects.filter(user=user).delete()

            return Response({
                'message': 'Account has been deleted successfully'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
