from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PasskeyDevice

User = get_user_model()


class PasskeyDeviceSerializer(serializers.ModelSerializer):
    """Serializer for passkey devices."""
    
    class Meta:
        model = PasskeyDevice
        fields = [
            'id', 'name', 'created_at', 'last_used_at',
            'backup_eligible', 'backup_state', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'last_used_at', 'backup_eligible', 'backup_state']


class PasskeyRegistrationBeginSerializer(serializers.Serializer):
    """Request serializer for beginning passkey registration."""
    
    platform_only = serializers.BooleanField(default=False, required=False)
    device_info = serializers.JSONField(required=False)


class PasskeyRegistrationCompleteSerializer(serializers.Serializer):
    """Request serializer for completing passkey registration."""
    
    credential_data = serializers.JSONField(required=True)
    device_name = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PasskeyAuthenticationBeginSerializer(serializers.Serializer):
    """Request serializer for beginning passkey authentication."""
    
    email = serializers.EmailField(required=False, allow_blank=True)
    device_info = serializers.JSONField(required=False)


class PasskeyAuthenticationCompleteSerializer(serializers.Serializer):
    """Request serializer for completing passkey authentication."""
    
    credential_data = serializers.JSONField(required=True)
    device_info = serializers.JSONField(required=False)


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for authentication responses."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'email', 'first_name', 'last_name']